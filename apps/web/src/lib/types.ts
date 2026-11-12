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
}
export interface SheetSection {
  heading: string;
  points: string[];
}
export interface Flashcard {
  question: string;
  answer: string;
}
export interface StudySheetContent {
  title: string;
  summary: string;
  key_concepts: KeyConcept[];
  sections: SheetSection[];
  flashcards: Flashcard[];
  review_questions: string[];
  estimated_review_time_min: number;
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
