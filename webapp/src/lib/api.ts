const BASE = (import.meta.env.VITE_GATEWAY_URL as string | undefined) ?? 'http://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(new URL(path, BASE).toString(), {
    headers: { 'X-API-Key': API_KEY ?? '' }
  })
  if (!res.ok) throw new Error(`GET ${path} ${res.status}`)
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: any): Promise<T> {
  const res = await fetch(new URL(path, BASE).toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY ?? ''
    },
    body: JSON.stringify(body ?? {})
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(`POST ${path} ${res.status}: ${msg}`)
  }
  return res.json() as Promise<T>
}

export type GatewayConfig = {
  version: string
  executables: {
    unityExecutablePath: string
    blenderExecutablePath: string
    unityProjectRoot: string
  }
  bridges: {
    unityBridgePort: number
    blenderBridgePort: number
  }
  integrations: {
    gemini: { apiKey: string, defaultModel: string }
    openai: { apiKey: string, defaultModel: string }
    anthropic: { apiKey: string, defaultModel: string }
  }
  projects: { root: string }
}

export function getConfig() {
  return apiGet<GatewayConfig>('/api/v1/config')
}

export function updateConfig(partial: Partial<GatewayConfig>) {
  return apiPost<GatewayConfig>('/api/v1/config', partial)
}

export async function startAgent(projectId: string, agentType: 'gemini'|'openai'|'claude') {
  return apiPost('/api/v1/agent/start', { projectId, agentType })
}

export async function stopAgent() {
  return apiPost('/api/v1/agent/stop', {})
}

export async function getAgentStatus() {
  return apiGet<{ running: boolean, pid?: number, cwd?: string, agentType?: string, lastError?: string }>('/api/v1/agent/status')
}

export async function sendChat(projectId: string, text: string): Promise<void> {
  const url = new URL('/api/v1/chat/send', BASE)
  url.searchParams.set('projectId', projectId)
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY ?? ''
    },
    body: JSON.stringify({ text })
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(`sendChat ${res.status}: ${msg}`)
  }
}

export async function getHealth() {
  return apiGet<{ ok: boolean, components: { name: string, running: boolean, endpoint_ok: boolean, detail: string }[] }>('/api/v1/health')
}

export async function runSelfTest(projectId?: string) {
  return apiPost<{ passed: boolean, steps: { name: string, ok: boolean, detail?: string }[] }>('/api/v1/health/selftest', projectId ? { projectId } : {})
}

export async function pipelineStart(projectId: string, agentType?: 'gemini'|'openai'|'claude') {
  return apiPost<{ ok: boolean, steps: { name: string, ok: boolean, detail?: string }[], health: any, selftest: any }>('/api/v1/pipeline/start', agentType ? { projectId, agentType } : { projectId })
}

export async function pipelineCancel() {
  return apiPost<{ cancelled: boolean }>('/api/v1/pipeline/cancel', {})
}
