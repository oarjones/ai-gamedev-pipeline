import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'
import { listProjects, deleteProject, selectProject, type Project } from '@/lib/api'
import { CreateProjectWizard } from './CreateProjectWizard'

export default function ProjectsPanel() {
  const project_id = useAppStore((s) => s.project_id)
  const setProjectId = useAppStore((s) => s.setProjectId)
  const pushToast = useAppStore((s) => s.pushToast)

  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [showCreateWizard, setShowCreateWizard] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      const list = await listProjects()
      setProjects(list)
    } catch (e: any) {
      pushToast(`Error listando proyectos: ${e.message ?? e}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleSelect(id: string) {
    try {
      await selectProject(id)
      setProjectId(id)
      refresh()
    } catch (e: any) {
      pushToast(`No se pudo activar el proyecto: ${e.message ?? e}`)
    }
  }

  function handleCreate() {
    setShowCreateWizard(true)
  }

  function handleWizardClose() {
    setShowCreateWizard(false)
    refresh() // Refresh project list after wizard closes
  }

  async function handleDelete(id: string, name: string) {
    const confirm = window.confirm(`Eliminar proyecto "${name}"? Esta acción no se puede deshacer.`)
    if (!confirm) return
    try {
      await deleteProject(id)
      pushToast(`Proyecto eliminado: ${name}`)
      await refresh()
      // If deleted project was selected, pick another if available
      if (project_id === id) {
        const remaining = projects.filter((p) => p.id !== id)
        if (remaining.length > 0) {
          await handleSelect(remaining[0].id)
        }
      }
    } catch (e: any) {
      pushToast(`No se pudo eliminar: ${e.message ?? e}`)
    }
  }

  return (
    <>
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="font-medium">Proyectos</div>
          <button
            className="px-2 py-1 text-sm rounded border hover:bg-secondary"
            onClick={handleCreate}
            disabled={loading}
            title="Crear proyecto"
          >
            + Nuevo
          </button>
        </div>
      <div className="space-y-2">
        {projects.map((p) => (
          <div key={p.id} className="flex items-center gap-2">
            <button
              className={`flex-1 text-left px-2 py-1 rounded border ${project_id === p.id ? 'bg-secondary' : ''}`}
              onClick={() => handleSelect(p.id)}
              title={p.description ?? ''}
            >
              {p.name}
              <span className="opacity-60 text-xs ml-2">({p.id})</span>
            </button>
            <div className="flex items-center gap-1">
              <Link className="px-2 py-1 text-xs rounded border hover:bg-secondary" to={`/projects/${p.id}/consensus`} title="Consenso">Consenso</Link>
              <Link className="px-2 py-1 text-xs rounded border hover:bg-secondary" to={`/projects/${p.id}/execution`} title="Ejecución">Ejecución</Link>
              <Link className="px-2 py-1 text-xs rounded border hover:bg-secondary" to={`/projects/${p.id}/context`} title="Contexto">Contexto</Link>
            </div>
            <button
              className="px-2 py-1 text-xs rounded border text-red-600 hover:bg-red-50"
              onClick={() => handleDelete(p.id, p.name)}
              title="Eliminar proyecto"
            >
              Eliminar
            </button>
          </div>
        ))}
        {projects.length === 0 && (
          <div className="text-sm opacity-70">No hay proyectos. Crea uno nuevo.</div>
        )}
      </div>
      </div>
      {showCreateWizard && (
        <CreateProjectWizard onClose={handleWizardClose} />
      )}
    </>
  )
}

