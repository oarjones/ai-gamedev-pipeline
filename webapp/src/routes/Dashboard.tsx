import ProjectsPanel from '@/components/ProjectsPanel'
import ChatPane from '@/components/chat/ChatPane'
import ContextPanel from '@/components/ContextPanel'
import Timeline from '@/components/Timeline'

export default function Dashboard() {
  return (
    <div className="grid gap-3 grid-cols-12 grid-rows-[minmax(0,1fr)_auto] h-[calc(100vh-5rem)]">
      {/* Top: Chat full width */}
      <section className="col-span-12 row-span-1 overflow-auto card">
        <ChatPane />
      </section>
      {/* Bottom: Remaining panels adjusted to fill space */}
      <footer className="col-span-12 grid grid-cols-12 gap-3">
        <div className="col-span-4 card overflow-auto"><ProjectsPanel /></div>
        <div className="col-span-4 card overflow-auto"><ContextPanel /></div>
        <div className="col-span-4 card overflow-auto"><Timeline /></div>
      </footer>
    </div>
  )
}
