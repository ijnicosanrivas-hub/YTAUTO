export type AgentStatus = "idle" | "running" | "waiting" | "error";

export interface AgentState {
  name: string;
  title: string;
  uses_claude: boolean;
  phases: string[];
  status: AgentStatus;
  project_id: string | null;
  phase: string | null;
  task: string | null;
  progress: number | null;
  started_at: string | null;
  finished_at: string | null;
  last_duration_s: number | null;
  last_result: string | null;
  last_error: string | null;
  runs: number;
  errors: number;
  llm_calls: number;
}

export interface Link {
  source: string;
  target: string;
  kind: "control" | "flow";
}

export interface YtEvent {
  type: string;
  project_id: string | null;
  agent: string | null;
  phase: string | null;
  data: Record<string, unknown>;
  at: string;
}

export interface PhaseView {
  project_id: string;
  phase: string;
  number: number;
  title: string;
  agent: string | null;
  kind: string;
  status: string;
  attempts: number;
  error: string | null;
  blocked_code: string | null;
  summary: string | null;
  result: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
}

export interface ProjectSpec {
  name: string;
  topic: string;
  idea?: string;
  duration_s: number;
  visual_style?: string | null;
  narration_type?: string | null;
  language: string;
  voice_type?: string | null;
  music?: string | null;
  intensity: "low" | "medium" | "high";
  platforms: string[];
  preferred_providers?: Record<string, string>;
  budget_max_eur: number;
  mode: "auto" | "custom";
  fps?: number;
  require_script_approval: boolean;
  subtitle_mode?: "karaoke" | "word_pop" | "line" | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  topic: string;
  status: string;
  duration_s: number;
  progress: number;
  next_phase: string | null;
  waiting_approval: string[];
  created_at: string;
  blocked_reason: string | null;
}

export interface ProjectView {
  project: { id: string; spec: ProjectSpec; status: string; correction_rounds: number; blocked_reason: string | null; created_at: string };
  progress: number;
  next_phase: string | null;
  waiting_approval: string[];
  phases: PhaseView[];
  memory?: { summaries: Record<string, { text: string; at: string }>; decisions: { by: string; decision: string; at: string }[] };
  llm_usage?: Record<string, unknown>[];
  costs?: Record<string, unknown>[];
}

export interface ProviderView {
  id: string;
  adapter: string;
  category: string;
  display_name: string;
  enabled: boolean;
  priority: number;
  params: Record<string, unknown>;
  monthly_budget_eur: number | null;
  max_generations_per_project: number | null;
  role: "primary" | "fallback" | "disabled";
  is_paid: boolean;
  is_local: boolean;
  required_credentials: string[];
  credentials: Record<string, string>;
  missing_credentials: string[];
  adapter_available: boolean;
  status: { healthy: boolean | null; message: string | null; last_error: string | null; error_count: number; success_count: number; last_check_at: string | null };
  capabilities: Record<string, unknown>;
}

export interface AdapterInfo {
  name: string;
  category: string;
  display_name: string;
  is_paid: boolean;
  is_local: boolean;
  required_credentials: string[];
  default_params: Record<string, unknown>;
  doc: string;
}

export interface ExportValidation {
  platform: string;
  ok: boolean;
  issues: { code: string; message: string; severity: "error" | "warning" }[];
  checked: string[];
}

export interface PlatformProfile {
  id: string;
  display_name: string;
  is_verified: boolean;
  verified_at: string | null;
  sources: string[];
  unverified: string[];
  min_duration_s: number;
  max_duration_s: number;
  encode: { width: number; height: number; fps: number; video_bitrate: string; audio_bitrate: string };
  file: {
    containers: string[];
    video_codecs: string[];
    fps_min: number | null;
    fps_max: number | null;
    max_size_mb: number | null;
    max_video_bitrate_mbps: number | null;
    platform_max_duration_s: number | null;
    require_moov_first: boolean;
    forbid_edit_lists: boolean;
  };
  metadata: { mode: string; title_max_chars: number; caption_max: number | null; description_max_bytes: number | null; hashtags_max: number };
  publish: { public_url_required: boolean; unaudited_private_only: boolean; daily_post_limit: number | null; notes: string[] };
}
