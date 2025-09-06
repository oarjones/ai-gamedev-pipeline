const BASE = (import.meta.env.VITE_GATEWAY_URL as string | undefined) ?? 'http://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(new URL(path, BASE).toString(), {
    headers: { 'X-API-Key': API_KEY ?? '' }
  })
  if (!res.ok) throw new Error(`GET ${path} ${res.status}`)
  return res.json() as Promise<T>
}

