import { useEffect } from 'react'
import { useAppStore } from '@/store/appStore'
import { wsClient } from '@/lib/ws'

export default function ChatPane() {
  const projectId = useAppStore(s => s.projectId)
  useEffect(() => {
    const unsub = wsClient.subscribe({ projectId, onMessage: (ev) => {
      // For MVP: just log
      // eslint-disable-next-line no-console
      console.log('WS event', ev)
    }})
    return () => unsub()
  }, [projectId])
  return (
    <div>
      <div className="font-medium mb-2">Chat</div>
      <div className="text-sm text-muted-foreground">Conectado a WS para: {projectId || '(sin seleccionar)'} (ver consola)</div>
    </div>
  )
}

