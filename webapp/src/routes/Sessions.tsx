import { useEffect, useState } from 'react'
import { listSessions, resumeSession, type SessionItem, getSessionDetail } from '@/lib/api'
import { useAppStore } from '@/store/appStore'

export default function Sessions() {
  const project_id = useAppStore(s => s.project_id)
  const pushToast = useAppStore(s => s.pushToast)
  const [items, setItems] = useState<SessionItem[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [detail, setDetail] = useState<any | null>(null)

  useEffect(() => {
    if (!project_id) return
    setLoading(true)
    listSessions(project_id).then(setItems).catch(e => pushToast(String(e))).finally(() => setLoading(false))
  }, [project_id])

  async function onResume(id: number) {
    try {
      await resumeSession(id)
      pushToast('Session resumed')
    } catch (e) {
      pushToast(String(e))
    }
}

function SessionIcon(){
  return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M3 5h18v12H6l-3 3z"/></svg>)
}
function EyeIcon(){
  return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 5c-7 0-10 7-10 7s3 7 10 7 10-7 10-7-3-7-10-7zm0 12a5 5 0 110-10 5 5 0 010 10z"/></svg>)
}
function PlayIcon(){
  return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>)
}
  async function viewDetail(id: number) {
    setSelected(id)
    try {
      const d = await getSessionDetail(id)
      setDetail(d)
    } catch (e) {
      pushToast(String(e))
    }
  }

  if (!project_id) return <div className="card">Select a project to view sessions.</div>

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-5 card overflow-auto">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold flex items-center gap-2"><SessionIcon /> Sessions</h2>
          {loading && <span className="spinner" aria-label="loading" />}
        </div>
        <ul className="space-y-2">
          {items.map(it => (
            <li key={it.id} className={`p-2 border rounded flex items-center justify-between ${selected===it.id?'bg-[hsl(var(--secondary))]':''}`}>
              <div>
                <div className="text-sm">#{it.id} • {it.provider}</div>
                <div className="text-xs opacity-70">{new Date(it.startedAt).toLocaleString()} {it.endedAt? <span className="badge ml-1">ended</span> : <span className="badge ml-1">active</span>}</div>
              </div>
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={() => viewDetail(it.id)}><EyeIcon /> View</button>
                <button className="btn" onClick={() => onResume(it.id)}><PlayIcon /> Resume</button>
              </div>
            </li>
          ))}
          {items.length===0 && <li className="text-sm opacity-70">No sessions yet.</li>}
        </ul>
      </div>
      <div className="col-span-7 card overflow-auto">
        <h2 className="font-semibold mb-2">Details</h2>
        {!detail && <div className="text-sm opacity-70">Select a session…</div>}
        {detail && (
          <div className="space-y-3">
            {detail.summary && (
              <div>
                <h3 className="font-medium">Summary</h3>
                <pre className="text-sm whitespace-pre-wrap">{detail.summary}</pre>
              </div>
            )}
            <div>
              <h3 className="font-medium">Recent Messages</h3>
              <ul className="space-y-1 text-sm">
                {detail.recentMessages.map((m:any, i:number) => (
                  <li key={i}><span className="opacity-70">[{m.role}]</span> {m.content}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-medium">Artifacts</h3>
              <ul className="space-y-1 text-sm">
                {detail.artifacts.map((a:any, i:number) => (
                  <li key={i}><span className="opacity-70">{a.type}</span> {a.path}</li>
                ))}
                {detail.artifacts.length===0 && <li className="opacity-70">No artifacts</li>}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
