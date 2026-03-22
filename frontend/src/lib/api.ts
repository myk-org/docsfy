import { toast } from 'sonner'
import { ApiError } from '@/types'
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
    const detail = body.detail || response.statusText
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
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
