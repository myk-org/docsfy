import type { WebSocketMessage, ProjectsResponse } from '@/types'
import { WS_RECONNECT_MAX_DELAY_MS, WS_POLLING_FALLBACK_MS } from './constants'
import { api } from './api'

type MessageHandler = (message: WebSocketMessage) => void

function isPingMessage(data: unknown): data is { type: 'ping' } {
  return typeof data === 'object' && data !== null && 'type' in data && (data as Record<string, unknown>).type === 'ping'
}

class WebSocketManager {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 3
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pollingTimer: ReturnType<typeof setInterval> | null = null
  private handlers: Set<MessageHandler> = new Set()

  private getBackoffDelay(): number {
    return Math.min(1000 * Math.pow(2, this.reconnectAttempts), WS_RECONNECT_MAX_DELAY_MS)
  }

  connect(isReconnect = false): void {
    if (this.ws?.readyState === WebSocket.OPEN) return
    // Only reset reconnect counter on manual (non-reconnect) connect
    if (!isReconnect) {
      this.reconnectAttempts = 0
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/ws`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      console.debug('[WS] Connected')
      this.reconnectAttempts = 0
      this.stopPolling()
    }

    this.ws.onmessage = (event) => {
      try {
        const parsed: unknown = JSON.parse(event.data)
        if (isPingMessage(parsed)) {
          this.ws?.send(JSON.stringify({ type: 'pong' }))
          return
        }
        const message = parsed as WebSocketMessage
        console.debug('[WS] Message:', message.type, 'name' in message ? message.name : '')
        this.handlers.forEach(handler => handler(message))
      } catch {
        /* ignore parse errors */
      }
    }

    this.ws.onclose = (event) => {
      console.debug('[WS] Disconnected, code:', event.code)
      if (event.code !== 1000) this.attemptReconnect()
    }

    this.ws.onerror = () => {
      /* handled by onclose */
    }
  }

  disconnect(): void {
    this.stopPolling()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close(1000)
      this.ws = null
    }
  }

  onMessage(handler: MessageHandler): () => void {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.debug('[WS] Falling back to polling')
      this.startPolling()
      return
    }
    const delay = this.getBackoffDelay()
    this.reconnectAttempts++
    console.debug('[WS] Reconnecting, attempt', this.reconnectAttempts)
    this.reconnectTimer = setTimeout(() => this.connect(true), delay)
  }

  private startPolling(): void {
    if (this.pollingTimer) return
    this.pollingTimer = setInterval(async () => {
      try {
        const data = await api.get<ProjectsResponse>('/api/projects')
        const syncMessage: WebSocketMessage = {
          type: 'sync' as const,
          projects: data.projects,
          known_branches: data.known_branches,
          available_models: data.available_models ?? {},
          total_cost_usd: data.total_cost_usd ?? 0,
        }
        this.handlers.forEach(handler => handler(syncMessage))
      } catch {
        /* ignore polling errors */
      }
    }, WS_POLLING_FALLBACK_MS)
  }

  private stopPolling(): void {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer)
      this.pollingTimer = null
    }
  }
}

export const wsManager = new WebSocketManager()
