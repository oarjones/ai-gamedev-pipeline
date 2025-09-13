import ProjectsPanel from '@/components/ProjectsPanel'
import ChatPane from '@/components/chat/ChatPane'
import ContextPanel from '@/components/ContextPanel'
import ToolsPanel from '@/components/ToolsPanel'
import Timeline from '@/components/Timeline'
import SelfTestPanel from '@/components/SelfTestPanel'
import AgentControls from '@/components/AgentControls'
import PipelineLauncher from '@/components/PipelineLauncher'

export default function Dashboard() {
  return (
    <div className="grid gap-3 grid-cols-12 grid-rows-[minmax(0,1fr)_auto] h-[calc(100vh-5rem)]">
      {/* Left: Projects */}
      <section className="col-span-3 row-span-1 overflow-auto card">
        <ProjectsPanel />
      </section>
      {/* Center: Chat */}
      <section className="col-span-6 row-span-1 overflow-auto card">
        <ChatPane />
      </section>
      {/* Right: Context & Tools stacked */}
      <section className="col-span-3 row-span-1 flex flex-col gap-3">
        <div className="card flex-1 overflow-auto"><ContextPanel /></div>
        <div className="card flex-1 overflow-auto"><ToolsPanel /></div>
      </section>
      {/* Bottom: Timeline spans all */}
      <footer className="col-span-12 grid grid-cols-12 gap-3">
        <div className="col-span-3 card overflow-auto"><PipelineLauncher /></div>
        <div className="col-span-3 card overflow-auto"><AgentControls /></div>
        <div className="col-span-3 card overflow-auto"><SelfTestPanel /></div>
        <div className="col-span-3 card overflow-auto"><Timeline /></div>
      </footer>
    </div>
  )
}
