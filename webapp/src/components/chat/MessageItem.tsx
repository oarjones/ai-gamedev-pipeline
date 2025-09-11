import { memo, useMemo, useState } from 'react'
import type { ChatMessage } from '@/lib/useChatStream'
import { renderMarkdown } from '@/lib/markdown'

type Props = { msg: ChatMessage }

export default memo(function MessageItem({ msg }: Props) {
  const roleCls = msg.role === 'user' ? 'bg-secondary' : msg.role === 'agent' ? 'bg-white/40 dark:bg-black/20' : 'bg-white/20 dark:bg-black/30'
  const Icon = useMemo(() => {
    if (msg.role === 'user') return UserIcon
    if (msg.role === 'agent') return AgentIcon
    if (msg.role === 'tool') return ToolIcon
    return SystemIcon
  }, [msg.role])
  const [expanded, setExpanded] = useState(false)
  const contentLen = (msg.content || '').length
  const shouldCollapse = contentLen > 800
  return (
    <div role="listitem" className={`rounded p-2 ${roleCls}`}>
      <div className="text-xs opacity-70 mb-1 flex items-center justify-between">
        <span className="flex items-center gap-1"><Icon /> {msg.role.toUpperCase()}</span>
        <span>{formatTime(msg.ts)}</span>
      </div>
      {msg.content && (
        <div>
          <div className={`prose prose-sm dark:prose-invert ${shouldCollapse && !expanded ? 'line-clamp-6' : ''}`} dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
          {shouldCollapse && (
            <button className="link text-xs" onClick={() => setExpanded(v => !v)}>{expanded ? 'Show less' : 'Show more'}</button>
          )}
        </div>
      )}
      {msg.attachments?.map((a, i) => a.type === 'image' ? (
        <img key={i} src={a.url ?? a.dataUrl} alt="attachment" className="mt-2 max-h-64 rounded" />
      ) : null)}
      {msg.role === 'tool' && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs">tool-call payload</summary>
          <pre className="text-xs overflow-auto">{JSON.stringify(msg.toolPayload, null, 2)}</pre>
        </details>
      )}
    </div>
  )
})

function formatTime(ts?: string) {
  if (!ts) return ''
  try { return new Date(ts).toLocaleTimeString() } catch { return ts }
}
function UserIcon(){ return (<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12a5 5 0 100-10 5 5 0 000 10zm0 2c-5 0-9 2.5-9 5v3h18v-3c0-2.5-4-5-9-5z"/></svg>) }
function AgentIcon(){ return (<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l4 4-4 4-4-4 4-4zm0 9l10 5-10 5-10-5 10-5z"/></svg>) }
function ToolIcon(){ return (<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M22 19l-6.5-6.5a5 5 0 11-1.5-1.5L20 17.5V19h2zM7 9a3 3 0 100-6 3 3 0 000 6z"/></svg>) }
function SystemIcon(){ return (<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h2v-2H3v2zm4 0h14v-2H7v2zM3 17h2v-2H3v2zm4 0h14v-2H7v2zM3 9h2V7H3v2zm4 0h14V7H7v2z"/></svg>) }
