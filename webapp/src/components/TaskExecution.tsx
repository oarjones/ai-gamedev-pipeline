import React, { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, askOneShot } from '@/lib/api'

type TaskItem = {
  id: number
  taskId: string
  title: string
  description: string
  status: string
  deps: string[]
}

export default function TaskExecution() {
  const { projectId } = useParams()
  const queryClient = useQueryClient()
  const { data: tasks = [] as TaskItem[] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => apiGet<TaskItem[]>(`/api/v1/tasks?projectId=${projectId}`),
    enabled: !!projectId,
  })

  const firstPending = useMemo(() => tasks.findIndex(t => t.status !== 'done'), [tasks])
  const [idx, setIdx] = useState<number>(Math.max(0, firstPending))
  const task = tasks[idx]

  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string>('')
  const [loadingAsk, setLoadingAsk] = useState(false)

  const completeTask = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/v1/tasks/${id}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ acceptanceConfirmed: true })
      })
      if (!res.ok) throw new Error(`complete ${res.status}`)
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setIdx(i => Math.min(i + 1, Math.max(0, tasks.length - 1)))
    }
  })

  const onAsk = async () => {
    if (!projectId || !question) return
    setLoadingAsk(true)
    try {
      const res = await askOneShot(projectId, question)
      setAnswer(res.answer || res.stderr || '')
    } catch (e: any) {
      setAnswer(e?.message ?? String(e))
    } finally {
      setLoadingAsk(false)
    }
  }

  return (
    <div className="grid grid-rows-[auto_1fr_auto] gap-3 h-[calc(100vh-140px)]">
      {/* Breadcrumbs / Header */}
      <div className="flex items-center justify-between">
        <nav className="text-sm text-gray-600">
          <Link to={`/projects/${projectId}/consensus`} className="hover:underline">Consenso</Link>
          <span className="mx-2">/</span>
          <Link to={`/projects/${projectId}/context`} className="hover:underline">Contexto</Link>
          <span className="mx-2">/</span>
          <span className="font-medium text-gray-800">Ejecución</span>
        </nav>
        <div className="text-sm opacity-70">Proyecto: {projectId}</div>
      </div>

      {/* Body */}
      <div className="grid grid-cols-12 gap-3 min-h-0">
        {/* Sidebar: tasks list */}
        <aside className="col-span-3 border rounded-lg p-2 overflow-auto">
          <div className="font-medium mb-2">Tareas</div>
          <div className="space-y-1">
            {tasks.map((t, i) => (
              <button
                key={t.id}
                className={`w-full text-left px-2 py-1 rounded border ${i === idx ? 'bg-secondary' : ''}`}
                onClick={() => setIdx(i)}
                title={t.description}
              >
                <span className="text-xs opacity-70 mr-1">{t.taskId}</span>
                {t.title}
                <span className="ml-2 text-xs opacity-60">[{t.status}]</span>
              </button>
            ))}
            {tasks.length === 0 && <div className="text-sm opacity-70">No hay tareas</div>}
          </div>
        </aside>

        {/* Main: work/chat area */}
        <section className="col-span-9 grid grid-rows-[auto_1fr] gap-2 min-h-0">
          <header className="card">
            {task ? (
              <div>
                <div className="text-sm text-gray-500">Tarea actual</div>
                <div className="text-lg font-semibold">{task.taskId} — {task.title}</div>
                {task.deps?.length > 0 && (
                  <div className="text-xs text-gray-500 mt-1">Depende de: {task.deps.join(', ')}</div>
                )}
              </div>
            ) : (
              <div className="text-sm opacity-70">Selecciona una tarea</div>
            )}
          </header>

          <div className="grid grid-cols-2 gap-2 min-h-0">
            <div className="card flex flex-col">
              <div className="font-medium mb-1">Chat/Trabajo</div>
              <textarea className="flex-1 border rounded p-2" placeholder="Escribe una pregunta…" value={question} onChange={e => setQuestion(e.target.value)} />
              <button className="btn btn-primary mt-2" onClick={onAsk} disabled={loadingAsk || !question}>{loadingAsk ? 'Preguntando…' : 'Preguntar a la IA'}</button>
            </div>
            <div className="card">
              <div className="font-medium mb-1">Respuesta</div>
              <div className="prose max-w-none whitespace-pre-wrap text-sm">{answer || '—'}</div>
            </div>
          </div>
        </section>
      </div>

      {/* Footer: actions */}
      <footer className="flex items-center justify-between">
        <div className="text-sm opacity-70">{tasks.length} tareas</div>
        <div className="flex gap-2">
          <button className="btn" onClick={() => setIdx(i => Math.max(0, i - 1))}>Anterior</button>
          <button className="btn btn-success" disabled={!task || completeTask.isPending} onClick={() => task && completeTask.mutate(task.id)}>Marcar como completada</button>
          <button className="btn" onClick={() => setIdx(i => Math.min(tasks.length - 1, i + 1))}>Siguiente</button>
        </div>
      </footer>
    </div>
  )
}

