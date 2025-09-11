import { FormEvent, useRef, useState, useEffect } from 'react'
import { useAppStore } from '@/store/appStore'
import { useChatStream } from '@/lib/useChatStream'
import { sendChat, startAgent, getAgentStatus } from '@/lib/api'
import MessageList from './MessageList'

export default function ChatPane() {
  const projectId = useAppStore(s => s.projectId)
  const { messages, bottomRef } = useChatStream(projectId)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [agentType] = useState<'gemini'>('gemini')
  const [agentStatus, setAgentStatus] = useState<{running:boolean, agentType?: string, pid?: number, lastError?: string} | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const MAX_LEN = 1000
  const [atBottom, setAtBottom] = useState(true)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!projectId || !text.trim()) return
    setSending(true)
    try {
      await sendChat(projectId, text.trim())
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

  async function ensureAgentStarted() {
    if (!projectId) return
    try {
      await startAgent(projectId, agentType)
      const st = await getAgentStatus()
      setAgentStatus(st)
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error(e)
    }
  }

  // Start agent when project or agentType changes
  useEffect(() => {
    if (projectId) ensureAgentStarted()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, agentType])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm">Provider:</span>
        <span className="badge">Gemini CLI</span>
        <button className="btn" type="button" onClick={ensureAgentStarted}><RefreshIcon /> Re/Start</button>
        {agentStatus && (
          <span className="text-xs text-muted-foreground">
            {agentStatus.agentType ?? agentType}: {agentStatus.running ? 'Running' : 'Stopped'} {agentStatus.pid ? `(pid ${agentStatus.pid})` : ''}
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
          placeholder={projectId ? 'Escribe un mensaje…' : 'Selecciona un proyecto…'}
          value={text}
          onChange={e => setText(e.target.value.slice(0, MAX_LEN))}
          disabled={!projectId || sending}
          aria-disabled={!projectId || sending}
          maxLength={MAX_LEN}
        />
        <button className="btn btn-primary" disabled={!projectId || sending}>
          {sending ? <span className="spinner" /> : <SendIcon />} Enviar
        </button>
      </form>
      <div className="mt-1 text-right text-xs text-muted-foreground">{text.length}/{MAX_LEN}</div>
    </div>
  )
}

function RefreshIcon(){ return (<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35A7.95 7.95 0 0012 4V1L7 6l5 5V7a5 5 0 11-5 5H5a7 7 0 107.75-6.96l-1.1 1.1z"/></svg>) }
function SendIcon(){ return (<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>) }
