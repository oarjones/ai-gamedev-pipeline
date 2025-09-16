import React, { useEffect, useMemo, useState } from 'react';
import { DndContext, DragEndEvent } from '@dnd-kit/core';
import { SortableContext, arrayMove, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPatch, apiPost } from '../lib/api';
import { Task, TaskPlan } from '../types';
import { useParams } from 'react-router-dom';

interface PlanSummary {
  id: number;
  version: number;
  status: string;
}

export function PlanConsensus({ project_id: propProjectId }: { project_id?: string }) {
  const params = useParams();
  const project_id = propProjectId ?? (params.project_id as string);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [tasks, setTasks] = useState<(Task & { priority?: number })[]>([]);
  const [showRefineModal, setShowRefineModal] = useState(false);
  const [refineInstructions, setRefineInstructions] = useState('');
  const queryClient = useQueryClient();

  // Cargar versiones del plan
  const { data: plans } = useQuery<PlanSummary[]>({
    queryKey: ['plans', project_id],
    queryFn: () => apiGet(`/api/v1/plans?project_id=${project_id}`),
    select: (data) => (Array.isArray(data) ? data : [])
  });

  // Cargar detalles del plan seleccionado
  const { data: planDetails } = useQuery<TaskPlan>({
    queryKey: ['plan', selectedVersion],
    queryFn: () => (selectedVersion ? apiGet(`/api/v1/plans/${selectedVersion}`) : null) as any,
    enabled: !!selectedVersion
  });

  useEffect(() => {
    if (planDetails?.tasks) {
      // mapear prioridad si existe
      setTasks(planDetails.tasks as any);
    } else {
      setTasks([]);
    }
  }, [planDetails?.id]);

  // Aceptar plan
  const acceptPlan = useMutation({
    mutationFn: (planId: number) => apiPatch(`/api/v1/plans/${planId}/accept`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      window.location.href = `/projects/${project_id}/execution`;
    }
  });

  // Refinar plan con IA (el backend puede no estar implementado todavía)
  const refinePlan = useMutation({
    mutationFn: ({ planId, instructions }: { planId: number; instructions: string }) =>
      apiPost(`/api/v1/plans/${planId}/refine`, { instructions }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      setShowRefineModal(false);
      setRefineInstructions('');
    }
  });

  // Guardar cambios (reorden/edición)
  const savePlanChanges = useMutation({
    mutationFn: async (updatedTasks: (Task & { priority?: number })[]) => {
      if (!selectedVersion) throw new Error('No hay versión de plan seleccionada');
      const updates = updatedTasks.map((t, idx) => ({
        id: t.id,
        title: t.title,
        description: t.description,
        priority: (t as any).priority ?? 1,
        idx
      }));
      return apiPatch(`/api/v1/plans/${selectedVersion}`, { update: updates });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plan', selectedVersion] });
    }
  });

  // Drag & drop: reordenar y persistir
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = tasks.findIndex((t) => t.id === active.id);
    const newIndex = tasks.findIndex((t) => t.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    const reordered = arrayMove(tasks, oldIndex, newIndex);
    setTasks(reordered);
    if (selectedVersion) {
      savePlanChanges.mutate(reordered);
    }
  };

  // Añadir tarea (local)
  const addTask = () => {
    const nextIndex = tasks.length + 1;
    const newTask: Task & { priority?: number } = {
      id: `temp-${Date.now()}`,
      code: `T-${String(nextIndex).padStart(3, '0')}`,
      title: 'Nueva tarea',
      description: '',
      dependencies: [],
      status: 'pending',
      priority: 1
    };
    setTasks((prev) => [...prev, newTask]);
  };

  // Eliminar tarea (local)
  const removeTask = (taskId: string | number) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
  };

  // Validar dependencias circulares (best-effort)
  const hasCircularDeps = useMemo(() => {
    const graph: Record<string, string[]> = {};
    tasks.forEach((t) => (graph[t.code] = t.dependencies || []));
    const visited = new Set<string>();
    const stack = new Set<string>();
    const dfs = (n: string): boolean => {
      if (stack.has(n)) return true;
      if (visited.has(n)) return false;
      visited.add(n);
      stack.add(n);
      for (const d of graph[n] || []) {
        if (dfs(d)) return true;
      }
      stack.delete(n);
      return false;
    };
    return Object.keys(graph).some(dfs);
  }, [tasks]);

  return (
    <div className="grid grid-cols-12 gap-4 h-full">
      {/* Panel izquierdo: Plan actual */}
      <div className="col-span-8 bg-white rounded-lg shadow p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Plan de Desarrollo</h2>
          <div className="flex gap-2">
            <select
              className="border rounded px-3 py-1"
              value={selectedVersion ?? ''}
              onChange={(e) => setSelectedVersion(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Seleccionar versión...</option>
              {plans?.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  v{plan.version} - {plan.status}
                </option>
              ))}
            </select>
            <button className="btn btn-secondary" onClick={addTask}>
              + Añadir Tarea
            </button>
          </div>
        </div>

        {/* Lista de tareas */}
        <DndContext onDragEnd={handleDragEnd}>
          <SortableContext items={tasks.map((t) => t.id)}>
            <div className="space-y-2">
              {tasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onRemove={(id) => removeTask(id)}
                  onEdit={(id, updates) => {
                    const next = tasks.map((t) => (t.id === id ? ({ ...t, ...updates } as any) : t));
                    setTasks(next);
                    if (selectedVersion) {
                      savePlanChanges.mutate(next);
                    }
                  }}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        {/* Estadísticas del plan */}
        {planDetails && (
          <div className="mt-6 p-4 bg-gray-50 rounded">
            <h3 className="font-medium mb-2">Estadísticas</h3>
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div>Total: {planDetails.stats.total}</div>
              <div>Completadas: {planDetails.stats.completed}</div>
              <div>Bloqueadas: {planDetails.stats.blocked}</div>
              <div>Progreso: {planDetails.stats.progress.toFixed(1)}%</div>
            </div>
          </div>
        )}
      </div>

      {/* Panel derecho */}
      <div className="col-span-4">
        {/* Refinamiento con IA */}
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <h3 className="font-medium mb-3">Refinar con IA</h3>
          <button className="btn btn-primary w-full" onClick={() => setShowRefineModal(true)} disabled={!selectedVersion}>
            Abrir modal de refinamiento
          </button>
        </div>

        {/* Acciones finales */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-medium mb-3">Acciones</h3>
          <button
            className="btn btn-success w-full mb-2"
            onClick={() => {
              if (selectedVersion && confirm('¿Aceptar este plan y comenzar la ejecución?')) {
                acceptPlan.mutate(selectedVersion);
              }
            }}
            disabled={!selectedVersion}
          >
            Aceptar Plan
          </button>
          <button className="btn btn-secondary w-full" onClick={() => savePlanChanges.mutate(tasks)} disabled={savePlanChanges.isPending || !selectedVersion}>
            {savePlanChanges.isPending ? 'Guardando...' : 'Guardar Cambios'}
          </button>
          {hasCircularDeps && <div className="text-xs text-red-600 mt-2">Advertencia: se detectaron dependencias circulares.</div>}
        </div>
      </div>

      {/* Modal de refinamiento */}
      <RefineModal
        open={showRefineModal}
        onClose={() => setShowRefineModal(false)}
        value={refineInstructions}
        setValue={setRefineInstructions}
        onSubmit={() => refinePlan.mutate({ planId: selectedVersion!, instructions: refineInstructions })}
        disabled={!selectedVersion || !refineInstructions || refinePlan.isPending}
      />
    </div>
  );
}

type TaskCardProps = {
  task: Task & { priority?: number };
  onRemove: (taskId: string | number) => void;
  onEdit: (taskId: string | number, updates: Partial<Task & { priority?: number }>) => void;
};

const TaskCard = React.memo(function TaskCard({ task, onRemove, onEdit }: TaskCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description || '');
  const [priority, setPriority] = useState<number>(Number((task as any).priority ?? 1));

  // dnd-kit sortable
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1
  };

  // Debounce actualizaciones durante edición
  useEffect(() => {
    const h = setTimeout(() => {
      if (isEditing) onEdit(task.id, { title, description, priority });
    }, 300);
    return () => clearTimeout(h);
  }, [title, description, priority, isEditing]);

  useEffect(() => {
    setTitle(task.title);
    setDescription(task.description || '');
    setPriority(Number((task as any).priority ?? 1));
  }, [task.id]);

  return (
    <div ref={setNodeRef} style={style} className="border rounded p-3 bg-white hover:shadow">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <button className="cursor-move text-gray-400 hover:text-gray-600" aria-label="Reordenar" {...attributes} {...listeners}>
              ☰
            </button>
            <span className="text-xs bg-blue-100 px-2 py-1 rounded">{task.code}</span>
            {isEditing ? (
              <input className="flex-1 border-b outline-none" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
            ) : (
              <h4 className="font-medium cursor-text" onClick={() => setIsEditing(true)} title="Editar título">
                {task.title}
              </h4>
            )}
          </div>
          {isEditing ? (
            <div className="mt-2 space-y-2">
              <textarea className="w-full border rounded p-2" placeholder="Descripción de la tarea..." value={description} onChange={(e) => setDescription(e.target.value)} />
              <div className="flex items-center gap-2 text-sm">
                <label className="text-gray-600">Prioridad:</label>
                <select className="border rounded px-2 py-1" value={priority} onChange={(e) => setPriority(Number(e.target.value))}>
                  <option value={1}>1</option>
                  <option value={2}>2</option>
                  <option value={3}>3</option>
                  <option value={4}>4</option>
                  <option value={5}>5</option>
                </select>
              </div>
              <div className="text-right">
                <button className="text-sm text-gray-600 hover:text-gray-900" onClick={() => setIsEditing(false)}>
                  Cerrar edición
                </button>
              </div>
            </div>
          ) : (
            <>
              {task.description && <p className="text-sm text-gray-700 mt-2 whitespace-pre-wrap">{task.description}</p>}
              {(task.dependencies?.length ?? 0) > 0 && (
                <div className="text-xs text-gray-500 mt-1">Depende de: {task.dependencies.join(', ')}</div>
              )}
            </>
          )}
        </div>
        <button className="text-red-500 hover:text-red-700" onClick={() => onRemove(task.id)} title="Eliminar tarea">
          ×
        </button>
      </div>
    </div>
  );
});

function RefineModal({
  open,
  onClose,
  onSubmit,
  value,
  setValue,
  disabled
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: () => void;
  value: string;
  setValue: (v: string) => void;
  disabled?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-xl p-4">
        <h3 className="text-lg font-semibold mb-2">Refinar plan con IA</h3>
        <textarea
          className="w-full border rounded p-2 h-40"
          placeholder="Describe los cambios que quieres hacer al plan..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <div className="mt-3 flex justify-end gap-2">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" onClick={onSubmit} disabled={disabled}>
            Refinar
          </button>
        </div>
      </div>
    </div>
  );
}

export default PlanConsensus;
