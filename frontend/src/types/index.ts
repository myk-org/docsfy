export type ProjectStatus = 'generating' | 'ready' | 'error' | 'aborted'
export type UserRole = 'admin' | 'user' | 'viewer'
export type AIProvider = 'claude' | 'gemini' | 'cursor'

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

export interface AuthResponse {
  username: string
  role: string
  is_admin: boolean
}

export interface ProjectsResponse {
  projects: Project[]
  known_models: Record<string, string[]>
  known_branches: Record<string, string[]>
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
  known_models: Record<string, string[]>
  known_branches: Record<string, string[]>
}

export interface ProgressMessage {
  type: 'progress'
  name: string
  branch: string
  provider: string
  model: string
  owner: string
  status: string
  current_stage: string
  page_count: number
  plan_json: string | null
  error_message: string | null
}

export interface StatusChangeMessage {
  type: 'status_change'
  name: string
  branch: string
  provider: string
  model: string
  owner: string
  status: string
  page_count: number
  last_generated: string | null
  last_commit_sha: string | null
  error_message: string | null
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
