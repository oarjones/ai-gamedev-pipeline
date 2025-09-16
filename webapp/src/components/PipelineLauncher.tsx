import { useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { pipelineStart, pipelineCancel } from '@/lib/api'

type Step = { name: string, ok: boolean, detail?: string }

export default function PipelineLauncher() {
  const project_id = useAppStore(s => s.project_id)
  const [open, setOpen] = useState(false)
  const [running, setRunning] = useState(false)
  const [steps, setSteps] = useState<Step[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const onStart = async () => {
    if (!project_id) { setError('Selecciona un proyecto'); return }
    setRunning(true); setError(null); setSteps(null)
    try {
      const res = await pipelineStart(project_id)
      setSteps(res.steps)
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setRunning(false)
    }
  }

  const onCancel = async () => {
    setRunning(true)
    try { await pipelineCancel() } catch { /* ignore */ } finally { setRunning(false); setOpen(false) }
  }

  return (
    <div className="space-y-2">
      <button className="btn btn-primary" onClick={() => setOpen(true)}>
        <PlayIcon /> Start Full Pipeline
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="card w-[520px] max-w-[95vw]">
            <div className="flex justify-between items-center mb-2">
              <div className="font-semibold">Start Full Pipeline</div>
              <button className="btn" onClick={() => setOpen(false)}><CloseIcon /> Close</button>
            </div>
            <div className="space-y-3">
              <div className="text-sm text-muted-foreground">Proyecto: <span className="font-mono">{project_id ?? '-'}</span></div>
              {error && <div className="text-sm text-red-600">{error}</div>}
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={onStart} disabled={!project_id || running}>
                  {running ? <span className="spinner" /> : <PlayIcon />} Run
                </button>
                <button className="btn" onClick={onCancel} disabled={!running}><StopIcon /> Cancel</button>
              </div>
              {steps && (
                <div className="text-sm border rounded">
                  {steps.map((s, i) => (
                    <div key={i} className="flex justify-between border-b px-2 py-1">
                      <span className="truncate max-w-[70%]">{s.name}</span>
                      <span className={s.ok ? 'text-green-600' : 'text-red-600'}>{s.ok ? 'ok' : 'fail'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function PlayIcon(){
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
  )
}
function StopIcon(){
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 6h12v12H6z"/></svg>
  )
}
function CloseIcon(){
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.3 5.71L12 12l6.3 6.29-1.42 1.42L10.59 13.4 4.3 19.71 2.88 18.29 9.17 12 2.88 5.71 4.3 4.29 10.59 10.6 16.88 4.29z"/></svg>
  )
}
