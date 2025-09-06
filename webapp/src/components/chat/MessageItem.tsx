import { memo } from 'react'
import type { ChatMessage } from '@/lib/useChatStream'
import { renderMarkdown } from '@/lib/markdown'

type Props = { msg: ChatMessage }

export default memo(function MessageItem({ msg }: Props) {
  const roleCls = msg.role === 'user' ? 'bg-secondary' : msg.role === 'agent' ? 'bg-white/40 dark:bg-black/20' : 'bg-white/20 dark:bg-black/30'
  return (
    <div role="listitem" className={`rounded p-2 ${roleCls}`}>
      <div className="text-xs opacity-70 mb-1">{msg.role.toUpperCase()}</div>
      {msg.content && (
        <div className="prose prose-sm dark:prose-invert" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
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

