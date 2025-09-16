import { FormEvent, useRef, useState, useEffect } from 'react'
import { useAppStore } from '@/store/appStore'
import { useChatStream } from '@/lib/useChatStream'
import { askOneShot, startAgent, getAgentStatus, systemStart } from '@/lib/api'
import MessageList from './MessageList'

export default function ChatPane() {
  const project_id = useAppStore(s => s.project_id)
  const { messages, bottomRef } = useChatStream(project_id)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [agentType] = useState<'gemini'>('gemini')
  const [agentStatus, setAgentStatus] = useState<{running:boolean, agentType?: string, pid?: number, lastError?: string} | null>(null)
  const [bridgesStatus, setBridgesStatus] = useState<string>('unknown')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const MAX_LEN = 1000
  const [atBottom, setAtBottom] = useState(true)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!project_id || !text.trim()) return
    setSending(true)
    try {
      // One-shot: route via /agent/ask; server will broadcast both user and agent messages
      await askOneShot(project_id, text.trim())
      setText('')
      inputRef.current?.focus()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err)
      useAppStore.getState().pushToast('Error enviando mensaje')
    } finally {
      setSending(false)
    }
  }

  async function startBridges() {
    try {
      setBridgesStatus('starting')
      useAppStore.getState().pushToast('Iniciando bridges...')
      await systemStart(project_id ?? undefined)
      setBridgesStatus('running')
      useAppStore.getState().pushToast('Bridges iniciados')
      return true
    } catch (e) {
      console.error('Error starting bridges:', e)
      setBridgesStatus('error')
      useAppStore.getState().pushToast('Error iniciando bridges')
      return false
    }
  }

  async function ensureAgentStarted() {
    if (!project_id) return
    
    try {
      // Primero intentar iniciar el agente
      await startAgent(project_id, agentType)
      const st = await getAgentStatus()
      setAgentStatus(st)
    } catch (e: any) {
      console.error('Error starting agent:', e)
      
      // Si el error es de bridges, intentar iniciarlos automáticamente
      if (e.message?.includes('Bridges not ready')) {
        useAppStore.getState().pushToast('Bridges no están listos, iniciando automáticamente...')
        
        const bridgesOk = await startBridges()
        if (bridgesOk) {
          // Esperar un momento para que los bridges se estabilicen
          setTimeout(async () => {
            try {
              await startAgent(project_id, agentType)
              const st = await getAgentStatus()
              setAgentStatus(st)
              useAppStore.getState().pushToast('Agente iniciado exitosamente')
            } catch (retryError) {
              console.error('Retry error:', retryError)
              useAppStore.getState().pushToast('Error iniciando agente después de bridges')
            }
          }, 3000)
        }
      } else {
        useAppStore.getState().pushToast('Error iniciando agente')
      }
    }
  }

  // Optional: previously ensured agent/bridges; for one-shot not required. Keep disabled.
  useEffect(() => {
    // no-op in one-shot mode
  }, [project_id, agentType])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-sm">Modo:</span>
        <span className="badge">One‑Shot</span>
        {bridgesStatus !== 'unknown' && (
          <span className={`text-xs ${bridgesStatus === 'running' ? 'text-green-600' : bridgesStatus === 'error' ? 'text-red-600' : 'text-yellow-600'}`}>
            Bridges: {bridgesStatus}
          </span>
        )}
      </div>
      <div className="flex-1 min-h-0 relative">
        <MessageList messages={messages} onAtBottomChange={setAtBottom} bottomRef={bottomRef} />
        {!atBottom && (
          <button className="btn btn-primary absolute bottom-3 right-3 shadow-lg" onClick={() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })}>
            ↓ New messages
          </button>
        )}
      </div>
      <form onSubmit={onSubmit} className="mt-2 flex gap-2" aria-label="Enviar mensaje">
        <input
          ref={inputRef}
          type="text"
          className="flex-1 input"
          placeholder={project_id ? `Enviar mensaje a ${agentType}...` : "Selecciona un proyecto"}
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX_LEN))}
          disabled={sending || !project_id}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={sending || !text.trim() || !project_id}
        >
          {sending ? 'Enviando...' : 'Enviar'}
        </button>
      </form>
    </div>
  )
}

function RefreshIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  )
}
