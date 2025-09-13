import { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { getAgentStatus, startAgent, stopAgent } from '@/lib/api'

export default function AgentControls(){
  const projectId = useAppStore(s => s.projectId)
  const pushToast = useAppStore(s => s.pushToast)
  const [status, setStatus] = useState<{running:boolean, agentType?: string, pid?: number, lastError?: string}>({ running: false })
  const [busy, setBusy] = useState(false)

  async function refresh(){
    try { setStatus(await getAgentStatus()) } catch { /* ignore */ }
  }

  useEffect(() => { refresh() }, [])

  async function onStart(){
    if (!projectId){ pushToast('Selecciona un proyecto'); return }
    setBusy(true)
    try {
      await startAgent(projectId, 'gemini')
      await refresh()
    } catch(e:any){
      pushToast(`No se pudo arrancar el agente: ${e?.message ?? e}`)
    } finally { setBusy(false) }
  }

  async function onStop(){
    setBusy(true)
    try {
      await stopAgent()
      await refresh()
    } catch(e:any){
      pushToast(`No se pudo parar el agente: ${e?.message ?? e}`)
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-2">
      <div className="font-medium">Agente IA</div>
      <div className="text-sm text-muted-foreground">Estado: {status.running ? 'en ejecución' : 'detenido'}</div>
      {status.lastError && <div className="text-xs text-red-600 break-all">{status.lastError}</div>}
      <div className="flex gap-2">
        <button className="btn btn-primary" onClick={onStart} disabled={busy || status.running}>Iniciar</button>
        <button className="btn" onClick={onStop} disabled={busy || !status.running}>Detener</button>
        <button className="btn" onClick={refresh} disabled={busy}>Refrescar</button>
      </div>
    </div>
  )
}

