import { useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { pipelineStart, pipelineCancel } from '@/lib/api'

type Step = { name: string, ok: boolean, detail?: string }

export default function PipelineLauncher() {
  const projectId = useAppStore(s => s.projectId)
  const [open, setOpen] = useState(false)
  const [running, setRunning] = useState(false)
  const [steps, setSteps] = useState<Step[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const onStart = async () => {
    if (!projectId) { setError('Selecciona un proyecto'); return }
    setRunning(true); setError(null); setSteps(null)
    try {
      const res = await pipelineStart(projectId)
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
      <button className="btn btn-primary" onClick={() => setOpen(true)}>Start Full Pipeline</button>
      {open && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="card w-[520px] max-w-[95vw]">
            <div className="flex justify-between items-center mb-2">
              <div className="font-semibold">Start Full Pipeline</div>
              <button className="btn" onClick={() => setOpen(false)}>Close</button>
            </div>
            <div className="space-y-3">
              <div className="text-sm text-muted-foreground">Proyecto: <span className="font-mono">{projectId ?? '-'}</span></div>
              {error && <div className="text-sm text-red-600">{error}</div>}
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={onStart} disabled={!projectId || running}>Run</button>
                <button className="btn" onClick={onCancel} disabled={!running}>Cancel</button>
              </div>
              {steps && (
                <div className="text-sm border rounded">
                  {steps.map((s, i) => (
                    <div key={i} className="flex justify-between border-b px-2 py-1">
                      <span>{s.name}</span>
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

