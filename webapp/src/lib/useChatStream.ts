import { useEffect, useMemo, useRef, useState } from 'react'
import { wsClient } from '@/lib/ws'
import { z } from 'zod'

const Envelope = z.object({
  type: z.string(),
  project_id: z.string().nullable().optional(),
  payload: z.unknown(),
  correlationId: z.string().optional(),
  timestamp: z.string().optional(),
})

const ChatPayload = z.object({
  role: z.enum(['user', 'agent', 'system']).optional(),
  content: z.string().optional(),
  msgId: z.string().optional(),
  attachments: z.array(z.object({ type: z.string(), url: z.string().optional(), dataUrl: z.string().optional() })).optional()
})

const ToolPayload = z.object({
  subtype: z.literal('tool').optional(),
  data: z.unknown()
})

export type ChatMessage = {
  id: string
  role: 'user' | 'agent' | 'system' | 'tool'
  content?: string
  attachments?: { type: 'image', url?: string, dataUrl?: string }[]
  toolPayload?: unknown
  ts?: string
}

export function useChatStream(project_id: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const atBottomRef = useRef(true)

  useEffect(() => {
    // reset on project change
    setMessages([])
  }, [project_id])

  useEffect(() => {
    const unsub = wsClient.subscribe({ project_id, onMessage: (ev) => {
      const parsed = Envelope.safeParse(ev)
      if (!parsed.success) return
      const { type, payload } = parsed.data
      if (type === 'chat') {
        const p = ChatPayload.safeParse(payload)
        if (!p.success) return
        const role = p.data.role ?? 'agent'
        const msg: ChatMessage = {
          id: crypto.randomUUID(),
          role,
          content: p.data.content,
          attachments: (p.data.attachments?.map(a => ({ type: a.type as 'image', url: a.url, dataUrl: a.dataUrl })) ?? []),
          ts: new Date().toISOString(),
        }
        setMessages(prev => mergeIfSameRole(prev, msg))
      } else if (type === 'action') {
        const t = ToolPayload.safeParse(payload)
        if (!t.success) return
        const msg: ChatMessage = { id: crypto.randomUUID(), role: 'tool', toolPayload: t.data.data, ts: new Date().toISOString() }
        setMessages(prev => [...prev, msg])
      } else if (type === 'scene') {
        // Screenshot ready → render as image attachment
        const p = (payload as any) ?? {}
        if (p?.kind === 'screenshot' && p?.url) {
          const msg: ChatMessage = { id: crypto.randomUUID(), role: 'system', attachments: [{ type: 'image', url: String(p.url) }], ts: new Date().toISOString() }
          setMessages(prev => [...prev, msg])
        }
      }
    }})
    return () => unsub()
  }, [project_id])

  // Auto-scroll if already at bottom
  useEffect(() => {
    if (atBottomRef.current) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const onScroll = (el: HTMLDivElement | null) => {
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    atBottomRef.current = nearBottom
  }

  return { messages, bottomRef, onScroll }
}

function mergeIfSameRole(prev: ChatMessage[], msg: ChatMessage): ChatMessage[] {
  if (prev.length && prev[prev.length - 1].role === msg.role && msg.role !== 'tool') {
    const last = prev[prev.length - 1]
    const merged: ChatMessage = {
      ...last,
      content: [last.content ?? '', msg.content ?? ''].filter(Boolean).join('\n')
    }
    return [...prev.slice(0, -1), merged]
  }
  return [...prev, msg]
}
