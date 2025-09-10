import { useAppStore } from '@/store/appStore'

const GATEWAY_WS = import.meta.env.VITE_WS_URL as string | undefined
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

type SubOpts = { projectId: string | null, onMessage: (data: unknown) => void }

class WSClient {
  private ws: WebSocket | null = null
  private currentProject: string | null = null
  private subs = new Set<(data: unknown) => void>()
  private backoff = 200

  subscribe({ projectId, onMessage }: SubOpts): () => void {
    this.subs.add(onMessage)
    if (projectId && projectId !== this.currentProject) {
      this.connect(projectId)
    }
    return () => { this.subs.delete(onMessage) }
  }

  private connect(projectId: string) {
    if (!GATEWAY_WS) return
    this.currentProject = projectId
    const url = new URL(GATEWAY_WS)
    url.searchParams.set('projectId', projectId)
    if (API_KEY) url.searchParams.set('apiKey', API_KEY)

    this.ws?.close()
    useAppStore.getState().setConnection('connecting')
    const ws = new WebSocket(url.toString())
    this.ws = ws
    ws.onopen = () => { useAppStore.getState().setConnection('connected'); this.backoff = 200 }
    ws.onerror = () => useAppStore.getState().setConnection('error', 'ws error')
    ws.onclose = () => {
      useAppStore.getState().setConnection('disconnected')
      // Reconnect with simple backoff
      if (this.currentProject) {
        const delay = Math.min(this.backoff, 5000)
        setTimeout(() => this.connect(this.currentProject!), delay)
        this.backoff = Math.min(this.backoff * 2, 5000)
      }
    }
    ws.onmessage = (ev) => {
      let data: unknown = ev.data
      try { data = JSON.parse(String(ev.data)) } catch { /* ignore */ }
      this.subs.forEach(fn => fn(data))
    }
  }
}

export const wsClient = new WSClient()
