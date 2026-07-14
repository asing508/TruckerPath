export interface SimInfo {
  sim_now: string;
  speed: number;
  running: boolean;
  t0?: string;
}

export interface TruckPos {
  truck_id: string;
  unit: string;
  lat: number;
  lon: number;
  heading: number;
  speed_mph: number;
  status: string;
  trip_id: string | null;
  trip_status: string | null;
  eta_state: string | null;
  fuel_pct: number;
}

export interface TripRow {
  trip_id: string;
  load_id: string;
  status: string;
  driver_id: string;
  truck_id: string;
  progress_miles: number;
  total_miles: number;
  eta_state: string;
  planned_eta: string;
  projected_eta: string | null;
  geometry_id: number;
  lane: string;
  customer: string;
  detention_min: number;
  last_ping_at: string | null;
}

export interface DriverRow {
  driver_id: string;
  name: string;
  duty: string;
  terminal: string;
  trip_id: string | null;
  drive_min_remaining: number;
  window_min_remaining: number;
  cycle_min_remaining: number;
  violations: string;
  on_time_rate: number;
}

export interface FleetState {
  sim: SimInfo;
  trucks: TruckPos[];
  drivers: DriverRow[];
  trips: TripRow[];
}

export interface FeedItem {
  ts: string;
  kind: string;
  text: string;
  severity?: string;
  state?: string;
  channel?: string;
  exception_id?: number;
  trip_id?: string | null;
  run_id?: number;
  status?: string;
}

export interface ExceptionRow {
  id: number;
  type: string;
  severity: string;
  state: string;
  title: string;
  detail: Record<string, unknown>;
  trip_id: string | null;
  driver_id: string | null;
  truck_id: string | null;
  load_id: string | null;
  detected_at: string;
  updated_at: string;
  agent_run_id: number | null;
}

export interface PendingActionRow {
  id: number;
  run_id: number;
  kind: string;
  title: string;
  subject_id: string;
  impact: Record<string, unknown>;
  draft: Record<string, unknown>;
  rationale: string;
  status: string;
  created_at: string;
  decided_at: string | null;
  executed_note: string;
}

export interface AgentStepRow {
  seq: number;
  kind: string;
  name: string;
  payload: unknown;
  ts?: string;
}

export interface AgentRunRow {
  id: number;
  kind: string;
  subject_id: string;
  status: string;
  model: string;
  summary: string;
  error?: string;
  started_at: string;
  finished_at: string | null;
  steps?: AgentStepRow[];
}

export interface UnassignedLoad {
  load_id: string;
  customer_name: string;
  origin_city: string;
  origin_state: string;
  dest_city: string;
  dest_state: string;
  load_type: string;
  weight_lbs: number;
  revenue: number;
  booking_type: string;
  distance_miles: number;
  pickup_window_start: string;
  pickup_window_end: string;
  delivery_deadline: string;
  status: string;
}

export interface MessageRow {
  id: number;
  channel: string;
  to_name: string;
  to_addr: string;
  subject: string;
  body: string;
  sent_at: string;
  trip_id: string | null;
  load_id: string | null;
}

export interface PacketRow {
  id: number;
  load_id: string;
  customer: string;
  lane: string;
  revenue: number;
  booking_type: string;
  delivered_at: string;
  age_days: number;
  status: string;
  docs: { doc_type: string; filename: string; title: string }[];
  findings: string[] | null;
  invoice_total: number | null;
  agent_run_id: number | null;
}

export interface ChartSpec {
  type: "bar" | "line" | "area";
  title: string;
  x: string[];
  series: { name: string; values: number[] }[];
}
