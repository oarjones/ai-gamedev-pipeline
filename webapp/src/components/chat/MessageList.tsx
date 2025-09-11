import { Virtuoso } from 'react-virtuoso'
import type { ChatMessage } from '@/lib/useChatStream'
import MessageItem from './MessageItem'

type Props = { messages: ChatMessage[], onAtBottomChange?: (atBottom: boolean) => void, bottomRef: React.RefObject<HTMLDivElement> }

export default function MessageList({ messages, onAtBottomChange, bottomRef }: Props) {
  const total = messages.length
  if (total > 200) {
    return (
      <div role="list" className="h-full" >
        <Virtuoso
          totalCount={messages.length}
          itemContent={(i) => <div className="mb-2"><MessageItem msg={messages[i]} /></div>}
        />
      </div>
    )
  }
  return (
    <div role="list" className="space-y-2 overflow-auto h-full" onScroll={(e) => {
      const el = e.currentTarget
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
      onAtBottomChange?.(nearBottom)
    }}>
      {messages.map(m => <MessageItem key={m.id} msg={m} />)}
      <div ref={bottomRef} />
    </div>
  )
}
