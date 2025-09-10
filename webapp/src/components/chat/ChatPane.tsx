import { FormEvent, useRef, useState, useEffect } from 'react'
import { useAppStore } from '@/store/appStore'
import { useChatStream } from '@/lib/useChatStream'
import { sendChat, startAgent, getAgentStatus } from '@/lib/api'
import MessageList from './MessageList'

export default function ChatPane() {
  const projectId = useAppStore(s => s.projectId)
  const { messages, bottomRef, onScroll } = useChatStream(projectId)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [agentType, setAgentType] = useState<'gemini'|'openai'|'claude'>('gemini')
  const [agentStatus, setAgentStatus] = useState<{running:boolean, agentType?: string, pid?: number, lastError?: string} | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const MAX_LEN = 1000

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
        <label className="text-sm">Agent:</label>
        <select className="input" value={agentType} onChange={e => setAgentType(e.target.value as any)}>
          <option value="gemini">Gemini (MCP)</option>
          <option value="openai">OpenAI</option>
          <option value="claude">Claude</option>
        </select>
        <button className="btn" type="button" onClick={ensureAgentStarted}>Re/Start</button>
        {agentStatus && (
          <span className="text-xs text-muted-foreground">
            {agentStatus.agentType ?? agentType}: {agentStatus.running ? 'Running' : 'Stopped'} {agentStatus.pid ? `(pid ${agentStatus.pid})` : ''}
          </span>
        )}
      </div>
      <div className="flex-1 min-h-0">
        <MessageList messages={messages} onScroll={onScroll} bottomRef={bottomRef} />
      </div>
      <form onSubmit={onSubmit} className="mt-2 flex gap-2" aria-label="Enviar mensaje">
        <input
          ref={inputRef}
          type="text"
          className="flex-1 border rounded px-2 py-1"
          placeholder={projectId ? 'Escribe un mensaje…' : 'Selecciona un proyecto…'}
          value={text}
          onChange={e => setText(e.target.value.slice(0, MAX_LEN))}
          disabled={!projectId || sending}
          aria-disabled={!projectId || sending}
          maxLength={MAX_LEN}
        />
        <button className="px-3 py-1 rounded bg-primary text-primary-foreground disabled:opacity-50" disabled={!projectId || sending}>
          {sending ? 'Enviando…' : 'Enviar'}
        </button>
      </form>
      <div className="mt-1 text-right text-xs text-muted-foreground">{text.length}/{MAX_LEN}</div>
    </div>
  )
}
