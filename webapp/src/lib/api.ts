const BASE = (import.meta.env.VITE_GATEWAY_URL as string | undefined) ?? 'http://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(new URL(path, BASE).toString(), {
    headers: { 'X-API-Key': API_KEY ?? '' }
  })
  if (!res.ok) throw new Error(`GET ${path} ${res.status}`)
  return res.json() as Promise<T>
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
