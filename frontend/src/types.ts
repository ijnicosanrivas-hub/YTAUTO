export type AgentStatus = "idle" | "running" | "waiting" | "error";

export interface AgentState {
  name: string;
  channel?: string | null;
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
  channel?: string | null;
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
  require_concept_approval?: boolean;
  require_storyboard_approval?: boolean;
  subtitle_mode?: "karaoke" | "word_pop" | "line" | null;
  channel?: string;
  brief?: { question: string; answer: string }[];
  license_map?: Record<string, string>;
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
  requires_network: boolean;
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
  publish: { privacy_options: string[]; public_url_required: boolean; unaudited_private_only: boolean; daily_post_limit: number | null; notes: string[] };
}

export interface Persona {
  character: string;
  alias: string;
  epithet: string;
  alignment: string;
  color: string;
  glyph: string;
  persona: string;
  quotes: Record<string, string>;
}

export interface Theme {
  id: string;
  name: string;
  brand: string;
  room_title: string;
  room_subtitle: string;
  palette: { accent: string; background: string; panel: string };
  agents: Record<string, Persona>;
}

// ------------------------------------------------------------------ canales y licencias
export interface PersonaRef {
  character: string;
  glyph: string;
  color: string;
}

export interface Channel {
  id: string;
  name: string;
  theme: string;
  tagline: string;
  accent: string;
  room_title: string;
  director: PersonaRef | null;
  chief: PersonaRef | null;
  has_director_image: boolean;
  /** El jefe (centro de la sala) es la cara del canal en el selector y las miniaturas. */
  has_chief_image: boolean;
}

export interface ChannelOverview {
  channel: { id: string; name: string; theme: string; tagline: string };
  accent: string;
  director: PersonaRef | null;
  chief: PersonaRef | null;
  projects: { total: number; by_status: Record<string, number> };
  current: { id: string; name: string } | null;
  running_agents: { name: string; task: string | null; progress: number | null }[];
  waiting_agents: number;
  error_agents: number;
  tokens_total: number;
  licenses: { total: number; limited: number; enabled: number };
}

export interface UsageBlock {
  tokens: { today: number; d7: number; d30: number; month: number };
  calls: { today: number; month: number; total: number };
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cost_usd_eq: number;
  seconds: number;
  by_agent: Record<string, number>;
  by_channel: Record<string, number>;
  daily: { day: string; tokens: number }[];
  last_call_at: string | null;
}

export interface License extends UsageBlock {
  id: string;
  name: string;
  channel_id: string;
  kind: "claude_session" | "api_key";
  plan: string;
  config_dir: string | null;
  secret_hint: string | null;
  monthly_token_limit: number | null;
  enabled: boolean;
  is_limited: boolean;
  limited_until: number | null;
  limited_reason: string | null;
  limited_now: boolean;
  status: "ok" | "limited" | "disabled";
  usage_pct: number | null;
  last_used_at: string | null;
  notes: string | null;
}

export interface LicensesView {
  licenses: License[];
  default: UsageBlock | null;
  totals: { tokens_month: number; calls_month: number };
  days: string[];
  channels: { id: string; name: string; theme: string }[];
  claude_slots: number;
}

export interface BriefQuestion {
  id: string;
  question: string;
  kind: "choice" | "text";
  options: string[];
  why: string;
}

export interface BriefQuestions {
  reading: string;
  questions: BriefQuestion[];
  source: "claude" | "base";
  director: PersonaRef | null;
}

// ------------------------------------------------------------------ monitor de tokens en vivo
export type LiveStatus = "ok" | "aviso" | "freno" | "agotada" | "inactiva";

export interface LiveUsage {
  used_5h: number;
  used_week: number;
  used_month: number;
  usd_month: number;
  limit_5h: number | null;
  limit_5h_source: "tuyo" | "observado" | null;
  limit_week: number | null;
  limit_usd: number | null;
  pct_5h: number | null;
  pct_week: number | null;
  pct_usd: number | null;
  remaining_5h: number | null;
  burn_per_min: number;
  eta_min: number | null;
  window_frees_at: string | null;
  brake: { reason: string; until: number } | null;
  status: LiveStatus;
  in_flight: number;
  limited_until: number | null;
  limited_reason: string | null;
  spark: number[];
  recent: { at: string; agent: string | null; tokens: number }[];
  calls_5h: number;
}

export interface LiveLicense extends LiveUsage {
  id: string;
  name: string;
  plan: string;
  kind: "claude_session" | "api_key";
  channel_id: string;
  channel_name: string;
  enabled: boolean;
  budget_5h_tokens: number | null;
  budget_week_tokens: number | null;
  budget_month_usd: number | null;
  observed_5h_tokens: number | null;
}

export interface LiveView {
  licenses: LiveLicense[];
  default: LiveUsage;
  totals: { used_5h: number; burn_per_min: number; in_flight: number; stopped: number; warning: number };
  warn_pct: number;
  channels: { id: string; name: string; theme: string }[];
  now: string;
}

// ---------------------------------------------------------------- cuentas conectadas (ElevenLabs, Higgsfield)
export interface ElevenSubscription {
  tier: string; used: number; limit: number; remaining: number; pct: number;
  resets_at_unix: number | null; status?: string | null; commercial_use: boolean | null; can_extend: boolean;
}

export interface ElevenView {
  linked: boolean; has_key: boolean; key_hint?: string; role?: string | null; error?: string;
  models: Record<string, string>;
  plans: Record<string, { label: string; credits: number; price_eur: number; note: string }>;
  params?: { model_id?: string; default_voice_id?: string; price_per_1k_chars_eur?: number; reserve_credits?: number };
  subscription?: ElevenSubscription;
  always_authorized: boolean;
}

export interface HiggsUse { linked: boolean; role: string | null; model: string | null; resolution?: string | null; max_per_video: number | null }

export interface HiggsView {
  cli_path: string | null;
  status: { installed: boolean; logged_in: boolean | null; credits: number | null; plan?: string | null; message: string };
  video_models: Record<string, string>;
  image_models: Record<string, string>;
  plans: Record<string, { label: string; credits: number; price_eur: number }>;
  video: HiggsUse;
  image: HiggsUse;
  price_per_credit_eur: number | null;
  reserve_credits: number | null;
  require_balance_check: boolean;
  always_authorized: Record<string, boolean>;
  help: { api: string; cli: string };
}

export interface AccountsView { elevenlabs: ElevenView; higgsfield: HiggsView; always: string[] }

// ---------------------------------------------------------------- música de la Biblioteca de audio de YouTube Studio
export interface YtTrack {
  file: string; size_mb: number; title: string | null; artist: string | null; genre: string | null; mood: string | null;
  license: string | null; attribution_required: boolean; attribution: string | null; duration_s: number | null; usable: boolean;
}

export interface YtMusicView { tracks: YtTrack[]; genres: string[]; moods: string[]; folder: string; audio_library_url: string; help_url: string }

// ---------------------------------------------------------------- estrategia del director (motor viral)
export interface HookOption { style: string; text: string; on_screen_text?: string | null; visual?: string; why?: string }
export interface RetentionBeat { at_s: number; technique: string; detail?: string }
export interface CreativeBriefView {
  concept: string; tone: string; visual_style: string; pacing: string; target_duration_s: number; music_direction: string;
  palette?: string[]; scenes: { index: number; section: string; duration_s: number; purpose: string; visual_direction: string }[];
  viral_angle?: string; target_viewer?: string; hook_options?: HookOption[]; chosen_hook?: number; story_structure?: string;
  opening_scene?: string; retention_plan?: RetentionBeat[]; cta?: string; title_options?: string[]; cover_concept?: string;
  risks?: string[]; user_notes?: string;
}
export interface ScenePromptView { scene_index: number; kind: "image" | "video"; prompt: string; search_query: string; style_tags?: string[] }
