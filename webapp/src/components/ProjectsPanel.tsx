import { useAppStore } from '@/store/appStore'

export default function ProjectsPanel() {
  const projectId = useAppStore(s => s.projectId)
  const setProjectId = useAppStore(s => s.setProjectId)
  return (
    <div>
      <div className="font-medium mb-2">Proyectos</div>
      <div className="space-y-2">
        {['test-api-project', 'active-test-project'].map(id => (
          <button
            key={id}
            className={`w-full text-left px-2 py-1 rounded border ${projectId === id ? 'bg-secondary' : ''}`}
            onClick={() => setProjectId(id)}
          >
            {id}
          </button>
        ))}
      </div>
    </div>
  )
}

