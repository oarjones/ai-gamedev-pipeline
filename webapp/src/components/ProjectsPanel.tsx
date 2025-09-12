import { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { listProjects, createProject, deleteProject, selectProject, type Project } from '@/lib/api'

export default function ProjectsPanel() {
  const projectId = useAppStore((s) => s.projectId)
  const setProjectId = useAppStore((s) => s.setProjectId)
  const pushToast = useAppStore((s) => s.pushToast)

  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)

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

  async function handleCreate() {
    const name = window.prompt('Nombre del nuevo proyecto:')?.trim()
    if (!name) return
    try {
      const proj = await createProject({ name })
      await handleSelect(proj.id)
      pushToast(`Proyecto creado: ${proj.name}`)
    } catch (e: any) {
      pushToast(`No se pudo crear: ${e.message ?? e}`)
    }
  }

  async function handleDelete(id: string, name: string) {
    const confirm = window.confirm(`Eliminar proyecto "${name}"? Esta acciÃ³n no se puede deshacer.`)
    if (!confirm) return
    try {
      await deleteProject(id)
      pushToast(`Proyecto eliminado: ${name}`)
      await refresh()
      // If deleted project was selected, pick another if available
      if (projectId === id) {
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
              className={`flex-1 text-left px-2 py-1 rounded border ${projectId === p.id ? 'bg-secondary' : ''}`}
              onClick={() => handleSelect(p.id)}
              title={p.description ?? ''}
            >
              {p.name}
              <span className="opacity-60 text-xs ml-2">({p.id})</span>
            </button>
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
  )
}


