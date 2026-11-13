/** Types partagés côté web. */

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type CourseStatus =
  | "recording"
  | "transcribing"
  | "generating"
  | "ready"
  | "failed";

export interface Course {
  id: string;
  title: string;
  subject: string | null;
  tags: string[];
  language: string;
  status: CourseStatus;
  audio_url: string | null;
  duration_sec: number;
  created_at: string;
  updated_at: string;
}

export interface Transcript {
  id: string;
  course_id: string;
  full_text: string;
  segments: Array<{ start?: number; end?: number; text: string }>;
  provider: string;
  model: string;
  created_at: string;
}

export interface KeyConcept {
  term: string;
  definition: string;
  importance?: "high" | "medium";
  example?: string;
}
export interface SheetSection {
  heading: string;
  type?: SectionType;
  points: string[];
}
export interface Formula {
  name: string;
  expression: string;
  meaning?: string;
}
export interface Flashcard {
  question: string;
  answer: string;
}
export type SectionType =
  | "normal"
  | "definition"
  | "formula"
  | "example"
  | "warning"
  | "tip";

export interface StudySheetContent {
  title: string;
  summary: string;
  learning_objectives?: string[];
  key_concepts: KeyConcept[];
  sections: SheetSection[];
  formulas?: Formula[];
  pitfalls?: string[];
  mnemonics?: string[];
  flashcards: Flashcard[];
  review_questions: string[];
  estimated_review_time_min: number;
  domain?: string;
  domain_label?: string;
  disclaimer?: string;
}
export interface StudySheet {
  id: string;
  course_id: string;
  content: StudySheetContent;
  model: string;
  version: number;
  created_at: string;
}
export interface Job {
  id: string;
  course_id: string;
  type: string;
  status: string;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}
export interface CourseDetail extends Course {
  transcript: Transcript | null;
  study_sheet: StudySheet | null;
  jobs: Job[];
}
export interface ApiKey {
  id: string;
  provider: string;
  key_hint: string;
  is_default: boolean;
  created_at: string;
}

// --- Admin ---
export interface AdminUser extends User {
  course_count: number;
  key_mode: string;
  byok_providers: string[];
  platform_providers: string[];
}
export interface PlatformKey {
  id: string;
  provider: string;
  account_label: string;
  key_hint: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface KeyMode {
  key_mode: string;
  platform_available: string[];
}
export interface AdminStats {
  total_users: number;
  active_users: number;
  total_courses: number;
  ready_courses: number;
  failed_courses: number;
  total_jobs: number;
  queued_jobs: number;
  running_jobs: number;
  failed_jobs: number;
}
export interface AdminJob extends Job {
  user_email: string;
  course_title: string;
}

// --- Système / présence ---
export interface ServiceStatus {
  name: string;
  status: string;
  error?: string | null;
  workers?: string[];
}
export interface SystemInfo {
  app: {
    name: string;
    version: string;
    environment: string;
    python: string;
    platform: string;
    uptime_seconds: number;
  };
  services: ServiceStatus[];
  storage_backend: string;
  rate_limit: { enabled: boolean; backend: string };
}
export interface OnlineUser {
  user_id: string;
  email: string;
  display_name: string;
  last_seen: number;
  idle_seconds: number;
}
export interface OnlineInfo {
  count: number;
  users: OnlineUser[];
}

// --- Téléchargements desktop ---
export interface DownloadItem {
  filename: string;
  size: number;
  os: string;
  arch: string;
  version: string;
  url: string;
}

// --- Alertes / usage ---
export interface Alert {
  id: string;
  severity: string;
  category: string;
  title: string;
  message: string;
  user_id: string | null;
  metadata_: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}
export interface UserUsage {
  user_id: string;
  email: string;
  key_mode: string;
  audio_minutes: number;
  sheet_count: number;
  cost_usd: number;
  quota_audio_minutes: number;
  quota_sheet_count: number;
  abuse_flags: string[];
}

// --- Admin complet ---
export interface EmailLog {
  id: string;
  to_email: string;
  subject: string;
  template: string;
  status: string;
  error: string | null;
  created_at: string;
}
export interface SmtpConfig {
  host: string;
  port: number;
  user: string;
  use_tls: boolean;
  from_addr: string;
  configured: boolean;
}

// --- Révision ---
export interface Sheet {
  id: string;
  course_id: string | null;
  title: string;
  subject: string | null;
  tags: string[];
  is_manual: boolean;
  content: Record<string, unknown>;
  created_at: string;
}
export interface ExamFolder {
  id: string;
  name: string;
  exam_date: string | null;
  description: string;
  created_at: string;
  item_count: number;
}
export interface QuizQuestion {
  id: string;
  position: number;
  question: string;
  choices: string[];
  correct_index: number;
  explanation: string;
}
export interface Quiz {
  id: string;
  title: string;
  model: string;
  created_at: string;
  questions: QuizQuestion[];
}
