import { FormEvent, useRef, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { useChatStream } from '@/lib/useChatStream'
import { sendChat } from '@/lib/api'
import MessageList from './MessageList'

export default function ChatPane() {
  const projectId = useAppStore(s => s.projectId)
  const { messages, bottomRef, onScroll } = useChatStream(projectId)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

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

  return (
    <div className="flex flex-col h-full">
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
          onChange={e => setText(e.target.value)}
          disabled={!projectId || sending}
          aria-disabled={!projectId || sending}
        />
        <button className="px-3 py-1 rounded bg-primary text-primary-foreground disabled:opacity-50" disabled={!projectId || sending}>
          {sending ? 'Enviando…' : 'Enviar'}
        </button>
      </form>
    </div>
  )
}

