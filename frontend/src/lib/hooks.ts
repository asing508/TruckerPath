"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useSyncExternalStore } from "react";

import { api } from "./api";
import { liveStore, type LiveState } from "./live";
import type {
  ExceptionRow,
  FeedItem,
  FleetState,
  MessageRow,
  PendingActionRow,
} from "./types";

export function useLive<T>(selector: (s: LiveState) => T): T {
  return useSyncExternalStore(
    liveStore.subscribe,
    () => selector(liveStore.state),
    () => selector(liveStore.state),
  );
}

/** Re-fetch a query when the SSE stream says its domain changed. */
function useInvalidation(key: string) {
  const version = useLive((s) => s.invalidations[key] ?? 0);
  const qc = useQueryClient();
  useEffect(() => {
    if (version > 0) void qc.invalidateQueries({ queryKey: [key] });
  }, [version, qc]);
}

export function useFleetState() {
  useInvalidation("fleet");
  return useQuery({
    queryKey: ["fleet"],
    queryFn: () => api.get<FleetState>("/api/fleet/state"),
    refetchInterval: 15000,
  });
}

export function useExceptions() {
  useInvalidation("exceptions");
  return useQuery({
    queryKey: ["exceptions"],
    queryFn: () => api.get<ExceptionRow[]>("/api/exceptions"),
    refetchInterval: 20000,
  });
}

export function useActions() {
  useInvalidation("actions");
  return useQuery({
    queryKey: ["actions"],
    queryFn: () => api.get<PendingActionRow[]>("/api/actions"),
    refetchInterval: 20000,
  });
}

export function useMessages() {
  useInvalidation("messages");
  return useQuery({
    queryKey: ["messages"],
    queryFn: () => api.get<MessageRow[]>("/api/messages"),
  });
}

export function useFeedHistory() {
  return useQuery({
    queryKey: ["feed-history"],
    queryFn: () => api.get<FeedItem[]>("/api/feed"),
    staleTime: Infinity,
  });
}
