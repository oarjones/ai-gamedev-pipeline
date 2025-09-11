import { useEffect, useMemo, useRef, useState } from 'react'
import { wsClient } from '@/lib/ws'
import { useAppStore } from '@/store/appStore'

type Item = { id: string; ts: string; type: string; text: string }

export default function Timeline() {
  const projectId = useAppStore(s => s.projectId)
  const [items, setItems] = useState<Item[]>([])
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => { setItems([]) }, [projectId])

  useEffect(() => {
    const unsub = wsClient.subscribe({ projectId, onMessage: (ev) => {
      const e = ev as any
      const type = e?.type as string | undefined
      if (!type) return
      const payload = e?.payload ?? {}
      const ts = new Date().toISOString()
      let text = ''
      if (type === 'log') {
        text = payload?.line ?? payload?.message ?? JSON.stringify(payload)
      } else if (type === 'update') {
        const src = payload?.source ?? 'system'
        const evt = payload?.event ?? 'update'
        text = `[${src}] ${evt}`
      } else if (type === 'action') {
        text = `Tool event`
      } else if (type === 'chat') {
        const role = payload?.role ?? 'agent'
        const content = String(payload?.content ?? '').slice(0, 120)
        text = `[${role}] ${content}`
      } else {
        text = type
      }
      const item: Item = { id: crypto.randomUUID(), ts, type, text: sanitize(text) }
      setItems(prev => [...prev.slice(-199), item])
    }})
    return () => unsub()
  }, [projectId])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [items])

  return (
    <div className="h-40 overflow-auto text-sm" ref={listRef}>
      {items.map(it => (
        <div key={it.id} className="flex gap-2 py-0.5 border-b border-border/30">
          <span className="text-xs text-muted-foreground w-40 shrink-0">{formatTime(it.ts)}</span>
          <span className="truncate">{it.text}</span>
        </div>
      ))}
      {!items.length && <div className="text-sm text-muted-foreground"><span className="spinner" /> No events yet</div>}
    </div>
  )
}

function sanitize(s: string): string { return String(s).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '') }
function formatTime(ts: string): string {
  try { const d = new Date(ts); return d.toLocaleTimeString() } catch { return ts }
}
