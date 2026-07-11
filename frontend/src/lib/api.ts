import { toast } from 'sonner'
import { ApiError } from '@/types'
import type { AuthResponse, ProjectsResponse, AdminSettingsResponse, AdminSettings, User, CreateUserResponse, RotateKeyResponse, AccessEntry, ModelsResponse } from '@/types'
import { encodeBranch } from '@/lib/utils'
import { REDIRECT_DELAY_MS } from './constants'

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  }
  if (options.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json'
  }

  const config: RequestInit = {
    ...options,
    credentials: 'same-origin',
    redirect: 'manual',
    headers,
  }

  console.debug('[API]', options.method || 'GET', path)
  const response = await fetch(`${path}`, config)

  if (response.type === 'opaqueredirect' || response.status === 302) {
    console.debug('[API] Error: session redirect', path)
    toast.error('Session expired. Redirecting to login...')
    setTimeout(() => { window.location.href = '/login' }, REDIRECT_DELAY_MS)
    throw new ApiError(401, 'Unauthorized', 'Session expired')
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    // Pydantic 422 returns detail as array of objects — extract messages
    let detail: string
    if (Array.isArray(body.detail)) {
      detail = body.detail.map((e: Record<string, unknown>) => String(e.msg || '')).join('; ') || response.statusText
    } else {
      detail = body.detail || response.statusText
    }
    console.debug('[API] Error:', response.status, detail)

    // Treat JSON 401 the same as a redirect — trigger session-expiry flow,
    // but skip for login endpoint (a 401 there means wrong credentials, not expired session)
    if (response.status === 401 && !path.endsWith('/auth/login')) {
      toast.error('Session expired. Redirecting to login...')
      setTimeout(() => { window.location.href = '/login' }, REDIRECT_DELAY_MS)
    }

    throw new ApiError(response.status, response.statusText, detail)
  }

  const text = await response.text()
  return text ? JSON.parse(text) : ({} as T)
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

// --- Centralized API endpoint functions ---

// Auth
export function login(username: string, apiKey: string) {
  return api.post<AuthResponse>('/api/auth/login', { username, api_key: apiKey })
}

export function getMe() {
  return api.get<AuthResponse>('/api/auth/me')
}

export function logout() {
  return api.post('/api/auth/logout')
}

export function rotateKey(body?: { new_key?: string }) {
  return api.post<{ new_api_key: string }>('/api/auth/rotate-key', body)
}

// Models
export function getModels() {
  return api.get<ModelsResponse>('/api/models')
}

export function refreshModels() {
  return api.post<ModelsResponse>('/api/models/refresh')
}

// Projects
export function getProjects() {
  return api.get<ProjectsResponse>('/api/projects')
}

export function generateDocs(payload: Record<string, unknown>) {
  return api.post('/api/generate', payload)
}

export function deleteAllVariants(name: string, owner: string) {
  return api.delete(`/api/projects/${name}?owner=${encodeURIComponent(owner)}`)
}

export function deleteVariant(name: string, branch: string, provider: string, model: string, owner: string) {
  return api.delete(`/api/projects/${name}/${encodeBranch(branch)}/${provider}/${model}?owner=${encodeURIComponent(owner)}`)
}

export function abortVariant(name: string, branch: string, provider: string, model: string, owner: string) {
  return api.post(`/api/projects/${name}/${encodeBranch(branch)}/${provider}/${model}/abort?owner=${encodeURIComponent(owner)}`)
}

// Admin - Users
export function getUsers() {
  return api.get<{ users: User[] }>('/api/admin/users')
}

export function createUser(username: string, role: string) {
  return api.post<CreateUserResponse>('/api/admin/users', { username, role })
}

export function deleteUser(username: string) {
  return api.delete(`/api/admin/users/${encodeURIComponent(username)}`)
}

export function rotateUserKey(username: string, body?: { new_api_key?: string }) {
  return api.post<RotateKeyResponse>(`/api/admin/users/${encodeURIComponent(username)}/rotate-key`, body)
}

// Admin - Access
export function grantAccess(project: string, username: string, owner: string) {
  return api.post(`/api/admin/projects/${encodeURIComponent(project)}/access`, {
    username,
    owner,
  })
}

export function getAccess(project: string, owner: string) {
  return api.get<AccessEntry[]>(`/api/admin/projects/${encodeURIComponent(project)}/access?owner=${encodeURIComponent(owner)}`)
}

export function revokeAccess(project: string, username: string, owner: string) {
  return api.delete(`/api/admin/projects/${encodeURIComponent(project)}/access/${encodeURIComponent(username)}?owner=${encodeURIComponent(owner)}`)
}

// Admin - Settings
export function getSettings() {
  return api.get<AdminSettingsResponse>('/api/admin/settings')
}

export function updateSettings(settings: Partial<AdminSettings>) {
  return api.put('/api/admin/settings', { settings })
}
