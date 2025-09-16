import { useEffect, useRef, useState } from 'react'
import { wsClient } from '@/lib/ws'
import { useAppStore } from '@/store/appStore'

type LogLine = { ts: string, level: string, source?: string, message: string }

export default function Logs() {
  const project_id = useAppStore(s => s.project_id)
  const [lines, setLines] = useState<LogLine[]>([])
  const boxRef = useRef<HTMLDivElement | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => { setLines([]) }, [project_id])

  useEffect(() => {
    const unsub = wsClient.subscribe({ project_id, onMessage: (ev) => {
      const e = ev as any
      if (e?.type !== 'log') return
      const p = e?.payload || {}
      const line: LogLine = { ts: new Date().toISOString(), level: p.level || 'info', source: p.source, message: p.line || p.message || '' }
      setLines(prev => [...prev.slice(-999), line])
    }})
    return () => unsub()
  }, [project_id])

  useEffect(() => {
    if (autoScroll) boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight })
  }, [lines, autoScroll])

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-semibold flex items-center gap-2"><LogIcon /> Logs</h2>
        <label className="text-xs inline-flex items-center gap-1"><input type="checkbox" checked={autoScroll} onChange={e=>setAutoScroll(e.target.checked)} /> Auto-scroll</label>
      </div>
      <div ref={boxRef} className="h-[60vh] overflow-auto text-xs font-mono whitespace-pre">
        {lines.map((l, i) => (
          <div key={i} className="px-1 py-0.5 border-b border-border/40">
            <span className="text-muted-foreground">{formatTime(l.ts)}</span>
            <span className="ml-2 badge">{(l.level||'info').toUpperCase()}</span>
            {l.source && <span className="ml-2 opacity-70">[{l.source}]</span>}
            <span className="ml-2">{l.message}</span>
          </div>
        ))}
        {!lines.length && <div className="text-sm text-muted-foreground"><span className="spinner" /> Waiting for log events…</div>}
      </div>
    </div>
  )
}

function LogIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h2v-2H3v2zm4 0h14v-2H7v2zM3 17h2v-2H3v2zm4 0h14v-2H7v2zM3 9h2V7H3v2zm4 0h14V7H7v2z"/></svg>) }
function formatTime(ts: string){ try { return new Date(ts).toLocaleTimeString() } catch { return ts } }
