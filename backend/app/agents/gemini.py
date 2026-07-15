"""Gemini client, model cascade, and the streaming tool-loop harness.

Every agent in the app runs through `run_agent`: a manual function-calling
loop that persists each step (AgentStep rows) and publishes it over SSE so the
UI's Agent Trace console shows the model's actual tool calls in real time.
The investigation phase uses tools; the final phase re-asks for a structured
object (response_schema) so downstream code never parses prose.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from typing import Any, Awaitable, Callable, Type

from google import genai
from google.genai import types
from pydantic import BaseModel
from sqlmodel import Session

from ..config import GEMINI_API_KEY, GEMINI_MODEL, MODEL_PREFERENCE
from ..db import engine as db_engine
from ..models import AgentRun, AgentStep, RunStatus
from ..streams import broadcaster
from .budget import ai_budget

log = logging.getLogger("agents")

ToolFn = Callable[..., Any]


class Tool:
    def __init__(self, fn: ToolFn, name: str, description: str, parameters: dict):
        self.fn = fn
        self.name = name
        self.description = description
        self.parameters = parameters

    def declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self.parameters,
        )


def tool(name: str, description: str, parameters: dict | None = None):
    def wrap(fn: ToolFn) -> Tool:
        return Tool(fn, name, description, parameters or {"type": "object", "properties": {}})
    return wrap


@lru_cache(maxsize=1)
def client() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


@lru_cache(maxsize=1)
def resolve_model() -> str:
    if GEMINI_MODEL:
        return GEMINI_MODEL
    try:
        available = {m.name.removeprefix("models/") for m in client().models.list()}
        for candidate in MODEL_PREFERENCE:
            if candidate in available:
                return candidate
    except Exception:
        log.exception("model listing failed; falling back to preference head")
    return MODEL_PREFERENCE[0]


class Tracer:
    """Persists agent steps and mirrors them onto the SSE stream."""

    def __init__(self, run_id: int):
        self.run_id = run_id
        self.seq = 0

    def emit(self, kind: str, name: str = "", payload: Any = None) -> None:
        self.seq += 1
        data = json.dumps(payload, default=str) if payload is not None else "{}"
        if len(data) > 4000:  # keep stored payloads JSON-valid when truncating
            data = json.dumps({"truncated": True, "preview": data[:3600]})
        ts = datetime.now()
        with Session(db_engine) as s:
            s.add(AgentStep(run_id=self.run_id, seq=self.seq, kind=kind,
                            name=name, payload=data, ts=ts))
            s.commit()
        broadcaster.publish("agent_step", {
            "run_id": self.run_id, "seq": self.seq, "kind": kind,
            "name": name, "payload": json.loads(data) if payload is not None else None,
            "ts": ts,
        })


def start_run(kind: str, subject_id: str) -> tuple[int, Tracer]:
    started_at = datetime.now()
    model = resolve_model()
    with Session(db_engine) as s:
        run = AgentRun(kind=kind, subject_id=subject_id, model=model,
                       started_at=started_at)
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
    broadcaster.publish("agent_run", {
        "id": run_id,
        "kind": kind,
        "subject_id": subject_id,
        "status": "RUNNING",
        "model": model,
        "summary": "",
        "error": "",
        "started_at": started_at,
        "finished_at": None,
    })
    return run_id, Tracer(run_id)


def finish_run(run_id: int, summary: str, error: str = "") -> None:
    finished_at = datetime.now()
    with Session(db_engine) as s:
        run = s.get(AgentRun, run_id)
        if run is None:
            # the run row is gone - a demo reset wiped it out from under this
            # in-flight coroutine. Nothing to finish; just stop quietly.
            log.warning("finish_run: run %s no longer exists (likely a reset)", run_id)
            return
        run.status = RunStatus.FAILED if error else RunStatus.DONE
        run.summary = summary[:2000]
        run.error = error[:2000]
        run.finished_at = finished_at
        s.add(run)
        s.commit()
    broadcaster.publish("agent_run", {
        "id": run_id,
        "status": "FAILED" if error else "DONE",
        "summary": summary[:400],
        "error": error[:400],
        "finished_at": finished_at,
    })


_pace_lock = asyncio.Lock()
_last_call_at = 0.0
_MIN_CALL_GAP_S = 1.1

_RETRY_RE = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)


def _retry_delay_s(err: Exception) -> float | None:
    m = _RETRY_RE.search(str(err))
    return float(m.group(1)) if m else None


def _is_quota(err: Exception) -> bool:
    text = str(err)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


async def _pace() -> None:
    global _last_call_at
    async with _pace_lock:
        now = asyncio.get_event_loop().time()
        wait = _MIN_CALL_GAP_S - (now - _last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call_at = asyncio.get_event_loop().time()


# Circuit breaker: a model that returns 429 is benched until the timestamp
# below, so one exhausted quota bucket is probed once per cooldown instead of
# being re-hit by every call (which is how a cascade multiplies requests).
_cooldown_until: dict[str, float] = {}
_QUOTA_COOLDOWN_S = 15 * 60


async def _call_model(m: str, **kwargs) -> types.GenerateContentResponse:
    if not ai_budget.spend_request():
        raise RuntimeError(
            "daily AI request budget exhausted - quota resets at midnight "
            "Pacific time (raise AI_DAILY_REQUEST_BUDGET to override)")
    await _pace()
    return await client().aio.models.generate_content(model=m, **kwargs)


async def _generate(model: str, **kwargs) -> types.GenerateContentResponse:
    """Paced, circuit-broken generation. A short server-suggested retry delay
    (an RPM blip) is honored once on the same model; a real quota exhaustion
    benches the model for a cooldown and moves on. One logical request may
    touch at most two models' quota buckets (primary + one fallback)."""
    now = asyncio.get_event_loop().time()
    ordered = list(dict.fromkeys([model, *MODEL_PREFERENCE]))
    chain = [m for m in ordered if _cooldown_until.get(m, 0.0) <= now][:2]
    if not chain:
        wait = min(_cooldown_until[m] for m in ordered) - now
        raise RuntimeError(
            f"all Gemini models are cooling down after quota errors; "
            f"next probe in ~{max(1, int(wait))}s")
    last: Exception | None = None
    for m in chain:
        try:
            return await _call_model(m, **kwargs)
        except Exception as e:
            last = e
            if not _is_quota(e):
                await asyncio.sleep(1.5)  # transient server hiccup
                continue
            delay = _retry_delay_s(e)
            if delay is not None and delay <= 15:
                await asyncio.sleep(delay + 1.0)
                try:
                    return await _call_model(m, **kwargs)
                except Exception as e2:
                    last = e2
                    if not _is_quota(e2):
                        continue
                    delay = _retry_delay_s(e2)
            bench = max(delay or 0.0, _QUOTA_COOLDOWN_S)
            _cooldown_until[m] = asyncio.get_event_loop().time() + bench
            log.warning("quota exhausted on %s; benched for %ds", m, int(bench))
    raise last  # type: ignore[misc]


async def run_agent(
    *,
    kind: str,
    subject_id: str,
    system: str,
    prompt: str | list[types.Part],
    tools: list[Tool],
    output_schema: Type[BaseModel],
    max_steps: int = 8,
    temperature: float = 0.3,
) -> tuple[BaseModel | None, int]:
    """Tool loop then structured finalization. Returns (output, run_id)."""
    if not ai_budget.try_start_run(kind):
        return None, 0
    run_id, tracer = start_run(kind, subject_id)
    model = resolve_model()
    registry = {t.name: t for t in tools}

    parts = [types.Part.from_text(text=prompt)] if isinstance(prompt, str) else prompt
    contents: list[types.Content] = [types.Content(role="user", parts=parts)]
    tool_cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        tools=[types.Tool(function_declarations=[t.declaration() for t in tools])] or None,
    )

    try:
        for _ in range(max_steps):
            resp = await _generate(model, contents=contents, config=tool_cfg)
            candidate = resp.candidates[0]
            calls = resp.function_calls or []
            if not calls:
                if resp.text:
                    tracer.emit("thought", payload={"text": resp.text[:1500]})
                break
            contents.append(candidate.content)
            response_parts = []
            for fc in calls:
                args = dict(fc.args or {})
                tracer.emit("tool_call", name=fc.name, payload=args)
                impl = registry.get(fc.name)
                if impl is None:
                    result: Any = {"error": f"unknown tool {fc.name}"}
                else:
                    try:
                        result = await asyncio.to_thread(impl.fn, **args)
                    except Exception as e:
                        result = {"error": str(e)[:500]}
                tracer.emit("tool_result", name=fc.name,
                            payload=result if isinstance(result, (dict, list)) else {"result": result})
                response_parts.append(types.Part.from_function_response(
                    name=fc.name, response={"result": result}))
            contents.append(types.Content(role="user", parts=response_parts))

        # finalization: force the structured contract, no more tools
        contents.append(types.Content(role="user", parts=[types.Part.from_text(
            text="Finalize now. Produce the structured output object exactly per schema, "
                 "grounded only in the tool evidence above.")]))
        final = await _generate(
            model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=output_schema,
            ),
        )
        parsed = final.parsed
        if parsed is None:
            parsed = output_schema.model_validate_json(final.text)
        tracer.emit("output", payload=json.loads(parsed.model_dump_json()))
        finish_run(run_id, summary=_summary_of(parsed))
        return parsed, run_id
    except Exception as e:
        log.exception("agent run %s failed", run_id)
        tracer.emit("error", payload={"error": str(e)[:800]})
        finish_run(run_id, summary="", error=str(e))
        return None, run_id


async def structured_call(
    *,
    system: str,
    parts: list[types.Part],
    output_schema: Type[BaseModel],
    model: str | None = None,
    temperature: float = 0.1,
) -> BaseModel:
    """One-shot structured generation (used for document vision extraction)."""
    resp = await _generate(
        model or resolve_model(),
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=output_schema,
        ),
    )
    parsed = resp.parsed
    if parsed is None:
        parsed = output_schema.model_validate_json(resp.text)
    return parsed


def _summary_of(model_obj: BaseModel) -> str:
    for attr in ("summary", "rationale", "memo", "answer_markdown", "risk_level"):
        if hasattr(model_obj, attr):
            return str(getattr(model_obj, attr))[:400]
    return model_obj.__class__.__name__
