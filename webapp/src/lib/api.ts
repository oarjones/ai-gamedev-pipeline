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

export async function apiPatch<T>(path: string, body: any): Promise<T> {
  const res = await fetch(new URL(path, BASE).toString(), {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY ?? ''
    },
    body: JSON.stringify(body ?? {})
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(`PATCH ${path} ${res.status}: ${msg}`)
  }
  return res.json() as Promise<T>
}

export async function apiPut<T>(path: string, body: any): Promise<T> {
  const res = await fetch(new URL(path, BASE).toString(), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY ?? ''
    },
    body: JSON.stringify(body ?? {})
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(`PUT ${path} ${res.status}: ${msg}`)
  }
  return res.json() as Promise<T>
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(new URL(path, BASE).toString(), {
    method: 'DELETE',
    headers: {
      'X-API-Key': API_KEY ?? ''
    }
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(`DELETE ${path} ${res.status}: ${msg}`)
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
  providers: {
    geminiCli: { command: string }
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

export async function startAgent(project_id: string, agentType: 'gemini'|'openai'|'claude') {
  return apiPost('/api/v1/agent/start', { project_id, agentType })
}

export async function stopAgent() {
  return apiPost('/api/v1/agent/stop', {})
}

export async function getAgentStatus() {
  return apiGet<{ running: boolean, pid?: number, cwd?: string, agentType?: string, lastError?: string }>('/api/v1/agent/status')
}

export async function sendChat(project_id: string, text: string): Promise<void> {
  const url = new URL('/api/v1/chat/send', BASE)
  url.searchParams.set('project_id', project_id)
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

export async function askOneShot(sessionId: string, question: string): Promise<{ sessionId: string, answer?: string | null, stderr?: string | null }> {
  return apiPost('/api/v1/agent/ask', { sessionId, question })
}

export async function getHealth() {
  return apiGet<{ ok: boolean, components: { name: string, running: boolean, endpoint_ok: boolean, detail: string }[] }>('/api/v1/health')
}

export async function runSelfTest(project_id?: string) {
  return apiPost<{ passed: boolean, steps: { name: string, ok: boolean, detail?: string }[] }>('/api/v1/health/selftest', project_id ? { project_id } : {})
}

export async function pipelineStart(project_id: string, agentType?: 'gemini'|'openai'|'claude') {
  return apiPost<{ ok: boolean, steps: { name: string, ok: boolean, detail?: string }[], health: any, selftest: any }>('/api/v1/pipeline/start', agentType ? { project_id, agentType } : { project_id })
}

export async function pipelineCancel() {
  return apiPost<{ cancelled: boolean }>('/api/v1/pipeline/cancel', {})
}

// Sessions API
export type SessionItem = { id: number, project_id: string, provider: string, startedAt: string, endedAt?: string | null, hasSummary: boolean }

export function listSessions(project_id: string, limit = 20) {
  const url = new URL('/api/v1/sessions', BASE)
  url.searchParams.set('project_id', project_id)
  url.searchParams.set('limit', String(limit))
  return apiGet<SessionItem[]>(url.pathname + url.search)
}

export function getSessionDetail(sessionId: number, recent = 10) {
  return apiGet<{ id: number, project_id: string, provider: string, startedAt: string, endedAt?: string | null, summary?: string | null, recentMessages: { role: string, content: string, tool?: string, ts: string }[], artifacts: { type: string, path: string, ts: string }[] }>(`/api/v1/sessions/${sessionId}?recent=${recent}`)
}

export function resumeSession(sessionId: number) {
  return apiPost<{ resumed: boolean, sessionId: number, runner: { running: boolean, pid?: number, cwd?: string } }>(`/api/v1/sessions/${sessionId}/resume`, {})
}


export async function systemStart(project_id?: string) {
  const body = project_id ? { project_id } : {}
  return apiPost<{ ok: boolean, statuses: Array<{ name: string, running: boolean, pid?: number, lastError?: string }> }>('/api/v1/system/start', body)
}

export async function systemStop() {
  return apiPost<{ ok: boolean }>('/api/v1/system/stop', {})
}

export async function systemStatus() {
  return apiGet<Array<{ name: string, pid?: number, running: boolean, lastStdout?: string, lastStderr?: string, lastError?: string, startedAt?: string }>>('/api/v1/system/status')
}

// Projects API
export type Project = {
  id: string
  name: string
  description?: string | null
  status: string
  createdAt: string
  updatedAt: string
  settings: Record<string, any>
}

export async function listProjects() {
  return apiGet<Project[]>('/api/v1/projects')
}

export async function getProject(project_id: string) {
  return apiGet<Project>(`/api/v1/projects/${project_id}`)
}

export async function createProject(payload: { name: string; description?: string; settings?: Record<string, any> }) {
  return apiPost<Project>('/api/v1/projects', payload)
}

export async function selectProject(project_id: string) {
  return apiPatch<{ message: string }>(`/api/v1/projects/${project_id}/select`, {})
}

export async function getActiveProject() {
  return apiGet<Project | null>('/api/v1/projects/active/current')
}

export async function deleteProject(project_id: string, purge = true) {
  const url = new URL(`/api/v1/projects/${project_id}`, BASE)
  if (purge) url.searchParams.set('purge', 'true')
  const res = await fetch(url.toString(), {
    method: 'DELETE',
    headers: { 'X-API-Key': API_KEY ?? '' }
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(`DELETE /api/v1/projects/${project_id} ${res.status}: ${msg}`)
  }
  return res.json() as Promise<{ message: string }>
}

export type ChatMessage = {
  id: number;
  msg_id: string;
  project_id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  created_at: string;
}

export async function listChatMessages(project_id: string, limit = 50): Promise<ChatMessage[]> {
  const res = await apiGet<{ items: ChatMessage[] }>(`/api/v1/chat/history?project_id=${project_id}&limit=${limit}`)
  return res.items;
}

// Tasks API
export type Task = {
  id: number
  taskId: string
  project_id: string
  title: string
  description: string
  acceptance: string
  status: 'pending' | 'in_progress' | 'done' | 'blocked'
  deps: string[]
  evidence: any[]
  priority?: number
  estimatedHours?: number
  actualHours?: number
  startedAt?: string
  completedAt?: string
  assignedTo?: string
}

export async function listTasks(project_id: string): Promise<Task[]> {
  return apiGet<Task[]>(`/api/v1/tasks?project_id=${project_id}`)
}

export async function importTasks(project_id: string) {
  return apiPost<{ imported: number }>(`/api/v1/tasks/import?project_id=${project_id}`, {})
}

export async function proposeTaskSteps(taskId: number) {
  return apiPost<{ queued: boolean, correlationId: string }>(`/api/v1/tasks/${taskId}/propose_steps`, {})
}

export async function executeTaskTool(taskId: number, tool: string, args: any, confirmed = false) {
  return apiPost<{ ok: boolean, result: any }>(`/api/v1/tasks/${taskId}/execute_tool`, {
    tool,
    args,
    confirmed
  })
}

export async function completeTask(taskId: number, acceptanceConfirmed = true) {
  return apiPost<{ done: boolean }>(`/api/v1/tasks/${taskId}/complete`, {
    acceptanceConfirmed
  })
}

export async function verifyTaskAcceptance(taskId: number) {
  return apiPost<{ queued: boolean, correlationId: string }>(`/api/v1/tasks/${taskId}/verify`, {})
}
