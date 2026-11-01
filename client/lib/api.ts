// Thin typed client for the CropTrail API. All calls go through Next's /api proxy.

export class ApiError extends Error {
  status: number;
  detail: any;
  constructor(status: number, message: string, detail?: any) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export const NETWORK_ERROR = "network";
type Listener = (down: boolean) => void;
const listeners = new Set<Listener>();
export function onConnectivity(fn: Listener) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function setDown(down: boolean) {
  listeners.forEach((fn) => fn(down));
}

export async function api<T = any>(path: string, init?: RequestInit & { json?: any }): Promise<T> {
  const opts: RequestInit = { ...init };
  if (init?.json !== undefined) {
    opts.body = JSON.stringify(init.json);
    opts.headers = { "Content-Type": "application/json", ...(init.headers || {}) };
  }
  let res: Response;
  try {
    res = await fetch(path, opts);
  } catch {
    setDown(true);
    throw new ApiError(0, NETWORK_ERROR);
  }
  if (res.status >= 502 && res.status <= 504 && !(res.headers.get("content-type") || "").includes("json")) {
    setDown(true); // proxy could not reach the server
    throw new ApiError(0, NETWORK_ERROR);
  }
  setDown(false);
  const isJson = (res.headers.get("content-type") || "").includes("json");
  const body = isJson ? await res.json() : null;
  if (!res.ok) {
    const detail = body?.detail;
    const msg = typeof detail === "string" ? detail : detail?.message || "Something went wrong. Please try again.";
    throw new ApiError(res.status, msg, detail);
  }
  return body as T;
}

// ---- types (mirror spec section 5/7) ----
export type Season = {
  season_id: string; plot_id: string; crop: string; season_label: string; sowing_date: string;
  status: "active" | "closed"; policy_number?: string | null;
};
export type Risk = {
  level: "low" | "medium" | "high" | null; score?: number; stage?: string; drivers?: string[];
  mode?: string; fixture_kind?: string | null; error?: string; notice?: string | null;
};
export type Plot = {
  plot_id: string; name: string; area_acres: number; lat: number; lon: number; survey_number?: string | null;
  nearest_market?: string | null; created_seq: number; active_season: Season | null;
  stage: { stage: string; days: number } | null; season_cost: number | null; last_log_date: string | null;
  risk: Risk | null;
};
export type Entry = {
  entry_id: string; season_id: string; entry_date: string; category: string; item: string | null;
  quantity: number | null; unit: string | null; cost_inr: number | null; source: string; created_at: string;
  logged_by?: string; plot_id?: string;
};
export type ParsedEntry = {
  entry_date: string | null; category: string | null; item: string | null; quantity: number | null;
  unit: string | null; cost_inr: number | null; plot_hint: string | null; confidence: number; missing_fields: string[];
};
export type EventT = {
  event_id: string; plot_id: string; plot_name: string; season_id: string | null; type: string; event_date: string;
  status: "suspected" | "confirmed" | "dismissed"; trigger: string; trigger_detail: string;
  is_demo?: boolean;
  report_deadline: string; seconds_left: number; past_deadline: boolean; estimated_loss_quintals: number | null;
  farmer_notes: string | null; alert_message: string | null;
  packs: { pack_id: string; generated_at: string; file_url: string; past_deadline: number }[];
};
export type Source = { type: string; label: string; ref: any; mode?: string };
export type AskResult = {
  answer: string; language: string; sources: Source[]; mode: "llm" | "fallback" | "safety"; stopped_at_cap: boolean;
  pending_action: { type: string; event_id: string } | null; notice?: string;
  spray: { verdict: "ok" | "not_advised" | "caution"; reasons: string[]; best_window: { start: string; end: string } | null } | null;
};
export type Health = {
  status: string; llm: "live" | "configured" | "unavailable" | "fallback"; weather: string; satellite: string; mandi: string;
  sample_data_enabled: boolean; demo_seed_loaded: boolean; simulation_allowed: boolean; today: string;
};
