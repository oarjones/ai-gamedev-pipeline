import { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiGet, apiPost } from '@/lib/api'

type TaskItem = {
  id: number
  taskId: string
  projectId: string
  title: string
  description: string
  acceptance: string
  status: string
  deps: string[]
  evidence: any[]
}

export default function Tasks() {
  const projectId = useAppStore(s => s.projectId)
  const pushToast = useAppStore(s => s.pushToast)
  const [items, setItems] = useState<TaskItem[]>([])
  const [selected, setSelected] = useState<TaskItem | null>(null)
  const [tool, setTool] = useState('')
  const [argsText, setArgsText] = useState('{}')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState<null|'propose'|'run'|'complete'>(null)

  async function refresh() {
    if (!projectId) return
    try {
      const list = await apiGet<TaskItem[]>(`/api/v1/tasks?projectId=${projectId}`)
      setItems(list)
      if (selected) {
        const updated = list.find(t => t.id === selected.id) || null
        setSelected(updated)
      }
    } catch (e) {
      pushToast(String(e))
    }
  }

  useEffect(() => { refresh() // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  async function importFromPlan() {
    if (!projectId) return
    try {
      const res = await apiPost(`/api/v1/tasks/import?projectId=${projectId}`, {})
      pushToast(`Imported ${res.imported} tasks`)
      refresh()
    } catch (e) { pushToast(String(e)) }
  }

  async function proposeSteps() {
    if (!selected) return
    try {
      setBusy('propose')
      await apiPost(`/api/v1/tasks/${selected.id}/propose_steps`, {})
      pushToast('Proposed steps sent to agent (see Chat)')
    } catch (e) { pushToast(String(e)) }
    finally { setBusy(null) }
  }

  async function executeTool() {
    if (!selected) return
    try {
      setBusy('run')
      const args = JSON.parse(argsText)
      const res = await apiPost(`/api/v1/tasks/${selected.id}/execute_tool`, { tool, args, confirmed })
      pushToast('Executed tool')
      refresh()
    } catch (e) { pushToast(String(e)) }
    finally { setBusy(null) }
  }

  async function completeTask() {
    if (!selected) return
    try {
      setBusy('complete')
      await apiPost(`/api/v1/tasks/${selected.id}/complete`, { acceptanceConfirmed: true })
      pushToast('Task marked as done')
      refresh()
    } catch (e) { pushToast(String(e)) }
    finally { setBusy(null) }
  }

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-5 card overflow-auto">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold flex items-center gap-2"><TasksIcon /> Tasks</h2>
          <div className="flex gap-2">
            <button className="btn" onClick={importFromPlan}><DownloadIcon /> Import from Plan</button>
            <button className="btn" onClick={refresh}><RefreshIcon /> Refresh</button>
          </div>
        </div>
        <ul className="space-y-2">
          {items.map(it => (
            <li key={it.id} className={`p-2 border rounded ${selected?.id===it.id?'bg-muted':''}`} onClick={()=>setSelected(it)}>
              <div className="text-sm font-medium">[{it.taskId}] {it.title}</div>
              <div className="text-xs opacity-70">{it.status}</div>
            </li>
          ))}
          {items.length===0 && <li className="text-sm opacity-70">No tasks. Import from plan.</li>}
        </ul>
      </div>
      <div className="col-span-7 card overflow-auto">
        {!selected && <div className="text-sm opacity-70">Select a task…</div>}
        {selected && (
          <div className="space-y-3">
            <h2 className="font-semibold">[{selected.taskId}] {selected.title}</h2>
            <div>
              <div className="text-xs opacity-70">Description</div>
              <p className="text-sm whitespace-pre-wrap">{selected.description}</p>
            </div>
            <div>
              <div className="text-xs opacity-70">Acceptance</div>
              <p className="text-sm whitespace-pre-wrap">{selected.acceptance}</p>
            </div>
            <div className="flex gap-2">
              <button className="btn" onClick={proposeSteps} disabled={busy==='propose'}>
                {busy==='propose' ? <span className="spinner"/> : <ListIcon />} Propose Steps
              </button>
            </div>
            <div className="p-2 border rounded">
              <div className="font-medium mb-1">Execute Tool (human-in-the-loop)</div>
              <div className="grid grid-cols-2 gap-2">
                <label className="text-sm">Tool
                  <input className="input" value={tool} onChange={e=>setTool(e.target.value)} placeholder="e.g. blender.export_fbx" />
                </label>
                <label className="text-sm">Args JSON
                  <input className="input" value={argsText} onChange={e=>setArgsText(e.target.value)} />
                </label>
              </div>
              <label className="text-sm inline-flex items-center gap-2 mt-2"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} /> Confirm sensitive action</label>
              <div className="mt-2"><button className="btn btn-primary" onClick={executeTool} disabled={busy==='run'}>
                {busy==='run'? <span className="spinner"/> : <PlayIcon />} Run
              </button></div>
            </div>
            <div>
              <div className="text-xs opacity-70">Evidence</div>
              <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(selected.evidence, null, 2)}</pre>
            </div>
            <div>
              <button className="btn btn-primary" onClick={completeTask} disabled={busy==='complete'}>
                {busy==='complete'? <span className="spinner"/> : <CheckIcon />} Mark as Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function TasksIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M3 6h18v2H3zm0 5h12v2H3zm0 5h18v2H3z"/></svg>) }
function DownloadIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M5 20h14v-2H5m7-14v8l3-3 1.41 1.41L12 18l-4.41-4.59L9 11l3 3V4h0z"/></svg>) }
function RefreshIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35A7.95 7.95 0 0012 4V1L7 6l5 5V7a5 5 0 11-5 5H5a7 7 0 107.75-6.96l-1.1 1.1z"/></svg>) }
function ListIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M3 5h18v2H3zm0 6h18v2H3zm0 6h18v2H3z"/></svg>) }
function PlayIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>) }
function CheckIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.2l-3.5-3.5L4 14.2l5 5 12-12-1.5-1.5z"/></svg>) }
