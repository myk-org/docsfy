export type ProjectStatus = 'generating' | 'ready' | 'error' | 'aborted'
export type UserRole = 'admin' | 'user' | 'viewer'
export type AIProvider = 'claude' | 'gemini' | 'cursor'
export type RepoType = 'app' | 'tests' | 'library' | 'framework'
export type AvailableModels = Record<string, Array<{id: string; name: string}>>

export interface ComboboxOption {
  value: string
  label: string
}

export interface Project {
  name: string
  branch: string
  ai_provider: string
  ai_model: string
  owner: string
  repo_url: string
  status: ProjectStatus
  current_stage: string | null
  last_commit_sha: string | null
  last_generated: string | null
  page_count: number
  error_message: string | null
  plan_json: string | null
  repo_type: RepoType | null
  total_cost_usd: number | null
  vision_provider: string | null
  vision_model: string | null
  generation_id: string | null
  generation_duration: number | null
  generation_started_at: string | null
  created_at: string
  updated_at: string
}

export interface GenerateRequest {
  repo_url?: string
  repo_path?: string
  ai_provider?: string
  ai_model?: string
  ai_cli_timeout?: number
  force?: boolean
  branch?: string
  repo_type?: RepoType
}

export interface DocPlan {
  project_name: string
  tagline: string
  navigation: NavGroup[]
  repo_url?: string
}

export interface NavGroup {
  group: string
  pages: DocPage[]
}

export interface DocPage {
  slug: string
  title: string
  description: string
}

export interface User {
  id: number
  username: string
  role: UserRole
  created_at: string
}

export interface AccessEntry {
  username: string
}

export interface AuthResponse {
  username: string
  role: string
  is_admin: boolean
}

export interface ProjectsResponse {
  projects: Project[]
  known_branches: Record<string, string[]>
  available_models?: AvailableModels
  total_cost_usd: number
}

export interface CreateUserResponse {
  username: string
  api_key: string
  role: string
}

export interface RotateKeyResponse {
  username: string
  new_api_key: string
}

/**
 * WebSocket messages use `provider`/`model` field names, while the Project
 * type uses `ai_provider`/`ai_model` to match the backend DB schema. This is
 * intentional — the WS handler in DashboardPage maps between the two.
 */
export type WebSocketMessage = SyncMessage | ProgressMessage | StatusChangeMessage

export interface SyncMessage {
  type: 'sync'
  projects: Project[]
  known_branches: Record<string, string[]>
  total_cost_usd: number
}

export interface ProgressMessage {
  type: 'progress'
  name: string
  branch: string
  provider: string
  model: string
  owner: string
  status: string
  current_stage?: string
  page_count?: number
  plan_json?: string | null
  error_message?: string | null
  generation_id?: string | null
  generation_started_at?: string | null
}

export interface StatusChangeMessage {
  type: 'status_change'
  name: string
  branch: string
  provider: string
  model: string
  owner: string
  status: string
  page_count?: number
  last_generated?: string | null
  last_commit_sha?: string | null
  error_message?: string | null
  generation_id?: string | null
  generation_duration?: number | null
}

export class ApiError extends Error {
  status: number
  statusText: string
  detail: string

  constructor(status: number, statusText: string, detail: string) {
    super(detail)
    this.status = status
    this.statusText = statusText
    this.detail = detail
  }
}

export interface LogEntry {
  id: string
  type: 'done' | 'active' | 'error' | 'pending'
  message: string
  timestamp: number
}

export interface AdminSettings {
  default_ai_provider: string
  default_ai_model: string
  ai_cli_timeout: number
  max_concurrent_pages: number
  vision_provider: string
  vision_model: string
}

export interface AdminSettingsResponse {
  settings: AdminSettings
  env_overrides: Record<string, string>
}
