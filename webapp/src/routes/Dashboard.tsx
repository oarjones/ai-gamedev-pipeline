import ProjectsPanel from '@/components/ProjectsPanel'
import ChatPane from '@/components/chat/ChatPane'
import {ContextPanel} from '@/components/ContextPanel'
import Timeline from '@/components/Timeline'
import { useAppStore } from '@/store/appStore'

export default function Dashboard() {
  const project_id = useAppStore((s) => s.project_id)

  return (
    <div className="grid gap-3 grid-cols-12 grid-rows-[minmax(0,1fr)_auto] h-[calc(100vh-5rem)]">
      {/* Top: Chat full width */}
      <section className="col-span-12 row-span-1 overflow-auto card">
        <ChatPane />
      </section>
      {/* Bottom: Remaining panels adjusted to fill space */}
      <footer className="col-span-12 grid grid-cols-12 gap-3">
        <div className="col-span-4 card overflow-auto"><ProjectsPanel /></div>
        <div className="col-span-4 card overflow-auto">
          {project_id ? <ContextPanel project_id={project_id} /> : <div className="text-gray-500 p-4">Selecciona un proyecto para ver el contexto</div>}
        </div>
        <div className="col-span-4 card overflow-auto"><Timeline /></div>
      </footer>
    </div>
  )
}
