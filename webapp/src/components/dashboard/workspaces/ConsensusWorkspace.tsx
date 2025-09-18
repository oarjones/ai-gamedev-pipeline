import React, { useState, useEffect, useCallback } from 'react';
import { useAppStore } from '@/store/appStore';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost, apiPatch, apiDelete, apiPut } from '@/lib/api';
import { TaskPlan, PlanSummary, Task } from '@/types';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragOverlay,
  DragStartEvent
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

// Component for individual sortable task
function SortableTask({
  task,
  onEdit,
  onDelete,
  onAddTaskAbove,
  onAddTaskBelow,
  isEditing,
  editValue,
  onEditChange,
  onEditSave,
  onEditCancel,
  isPlanApproved,
  isEditingApprovedPlan
}: {
  task: Task;
  onEdit: (task: Task) => void;
  onDelete: (code: string) => void;
  onAddTaskAbove: (taskCode: string) => void;
  onAddTaskBelow: (taskCode: string) => void;
  isEditing: boolean;
  editValue: { title: string; description: string };
  onEditChange: (field: string, value: string) => void;
  onEditSave: () => void;
  onEditCancel: () => void;
  isPlanApproved?: boolean;
  isEditingApprovedPlan?: boolean;
}) {
  const isCompleted = task.status === 'done';
  const isReadOnly = (isPlanApproved && !isEditingApprovedPlan) || isCompleted;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: task.code,
    disabled: isReadOnly
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow ${
        isDragging ? 'cursor-grabbing' : ''
      } ${isCompleted ? 'opacity-60 bg-gray-50' : ''} ${
        isPlanApproved ? 'bg-green-25 border-green-200' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            {!isReadOnly ? (
              <button
                {...attributes}
                {...listeners}
                className="cursor-grab hover:bg-gray-100 p-1 rounded"
                title="Arrastrar para reordenar"
              >
                <DragIcon className="w-5 h-5 text-gray-400" />
              </button>
            ) : isCompleted ? (
              <div className="p-1 rounded">
                <CheckIcon className="w-5 h-5 text-green-500" />
              </div>
            ) : (
              <div className="p-1 rounded">
                <ApproveIcon className="w-5 h-5 text-green-500" />
              </div>
            )}
            <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-mono">
              {task.code}
            </span>
            {task.status && (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                task.status === 'done'
                  ? 'bg-green-100 text-green-800'
                  : task.status === 'in_progress'
                  ? 'bg-yellow-100 text-yellow-800'
                  : task.status === 'blocked'
                  ? 'bg-red-100 text-red-800'
                  : 'bg-gray-100 text-gray-800'
              }`}>
                {task.status === 'done' ? 'Completada' :
                 task.status === 'in_progress' ? 'En progreso' :
                 task.status === 'blocked' ? 'Bloqueada' : 'Pendiente'}
              </span>
            )}
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
              task.priority === 1
                ? 'bg-red-100 text-red-800'
                : 'bg-blue-100 text-blue-800'
            }`}>
              Prioridad {task.priority}
            </span>
          </div>

          {isEditing && !isCompleted ? (
            <div className="space-y-2">
              <input
                type="text"
                value={editValue.title}
                onChange={(e) => onEditChange('title', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Título de la tarea"
              />
              <textarea
                value={editValue.description}
                onChange={(e) => onEditChange('description', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                rows={3}
                placeholder="Descripción de la tarea"
              />
              <div className="flex gap-2">
                <button
                  onClick={onEditSave}
                  className="px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                >
                  Guardar
                </button>
                <button
                  onClick={onEditCancel}
                  className="px-3 py-1 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 text-sm"
                >
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <>
              <h4 className={`font-medium mb-1 ${isCompleted ? 'text-gray-600 line-through' : 'text-gray-900'}`}>
                {task.title}
              </h4>
              <p className={`text-sm mb-3 ${isCompleted ? 'text-gray-500' : 'text-gray-600'}`}>
                {task.description}
              </p>
            </>
          )}

          {task.dependencies.length > 0 && (
            <div className="flex items-center gap-2">
              <DependencyIcon className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-500">
                Depende de: {task.dependencies.join(', ')}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1 ml-4">
          {!isReadOnly ? (
            <>
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => onAddTaskAbove(task.code)}
                  className="p-1 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                  title="Añadir tarea arriba"
                >
                  <PlusUpIcon className="w-3 h-3" />
                </button>
                <button
                  onClick={() => onAddTaskBelow(task.code)}
                  className="p-1 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                  title="Añadir tarea abajo"
                >
                  <PlusDownIcon className="w-3 h-3" />
                </button>
              </div>
              <button
                onClick={() => onEdit(task)}
                className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                title="Editar tarea"
              >
                <EditIcon className="w-4 h-4" />
              </button>
              <button
                onClick={() => onDelete(task.code)}
                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                title="Eliminar tarea"
              >
                <DeleteIcon className="w-4 h-4" />
              </button>
            </>
          ) : isCompleted ? (
            <div className="px-3 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
              Tarea completada
            </div>
          ) : (
            <div className="px-3 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
              Plan aprobado - Solo lectura
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ConsensusWorkspace() {
  const project_id = useAppStore((s) => s.project_id);
  const queryClient = useQueryClient();

  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [localTasks, setLocalTasks] = useState<Task[]>([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [editingTaskCode, setEditingTaskCode] = useState<string | null>(null);
  const [editValue, setEditValue] = useState({ title: '', description: '' });
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  const [showRefineDialog, setShowRefineDialog] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState('');
  const [isEditingApprovedPlan, setIsEditingApprovedPlan] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Fetch list of plans
  const { data: allPlans, isLoading: isLoadingPlans } = useQuery<PlanSummary[]>({
    queryKey: ['plans', project_id],
    queryFn: () => apiGet(`/api/v1/plans?project_id=${project_id}`),
    enabled: !!project_id,
    select: (data) => (Array.isArray(data) ? data : [])
  });

  // Filter plans: if there's an approved plan, show only that one; otherwise show all
  const plans = React.useMemo(() => {
    if (!allPlans) return [];
    const approvedPlan = allPlans.find(p => p.status === 'approved' || p.status === 'accepted');
    return approvedPlan ? [approvedPlan] : allPlans;
  }, [allPlans]);

  // Select the latest plan by default
  useEffect(() => {
    if (plans && plans.length > 0) {
      setSelectedPlanId(plans[0].id);
    }
  }, [plans]);

  // Fetch details of the selected plan
  const { data: planDetails, isLoading: isLoadingPlanDetails } = useQuery<TaskPlan>({
    queryKey: ['plan', selectedPlanId],
    queryFn: () => apiGet(`/api/v1/plans/${selectedPlanId}`),
    enabled: !!selectedPlanId,
  });

  // Check if current plan is approved
  const isPlanApproved = planDetails?.status === 'approved' || planDetails?.status === 'accepted';

  // Initialize local tasks when plan details are loaded
  useEffect(() => {
    if (planDetails) {
      setLocalTasks([...planDetails.tasks]);
      setHasUnsavedChanges(false);
    }
  }, [planDetails]);

  // Save plan mutation
  const savePlanMutation = useMutation({
    mutationFn: async (tasks: Task[]) => {
      if (isPlanApproved && isEditingApprovedPlan) {
        // Overwrite approved plan without creating new version
        return apiPut(`/api/v1/plans/${selectedPlanId}/overwrite`, {
          tasks: tasks
        });
      } else {
        // Create new version for proposed plans
        return apiPatch(`/api/v1/plans/${selectedPlanId}/apply-changes`, {
          tasks: tasks
        });
      }
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['plan', selectedPlanId] });
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      setHasUnsavedChanges(false);
      setShowSaveConfirm(false);

      if (isPlanApproved && isEditingApprovedPlan) {
        setIsEditingApprovedPlan(false);
        console.log('Plan aprobado actualizado:', data);
      }
    },
  });

  // Refine plan mutation
  const refinePlanMutation = useMutation({
    mutationFn: async (data: { tasks: Task[]; prompt: string }) => {
      return apiPost<TaskPlan>(`/api/v1/plans/${selectedPlanId}/refine`, {
        tasks: data.tasks,
        refinement_prompt: data.prompt
      });
    },
    onSuccess: (refinedPlan: TaskPlan) => {
      // Update local tasks with refined plan but don't save to DB yet
      setLocalTasks(refinedPlan.tasks);
      setHasUnsavedChanges(true);
      setShowRefineDialog(false);
      setRefinePrompt('');
    },
  });

  // Reorder tasks and update codes
  const reorderTasks = useCallback((tasks: Task[]) => {
    return tasks.map((task, index) => ({
      ...task,
      code: `T-${String(index + 1).padStart(3, '0')}`
    }));
  }, []);

  // Handle drag end
  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setLocalTasks((items) => {
        const oldIndex = items.findIndex((item) => item.code === active.id);
        const newIndex = items.findIndex((item) => item.code === over.id);
        const movedItems = arrayMove(items, oldIndex, newIndex);
        const reorderedItems = reorderTasks(movedItems);
        setHasUnsavedChanges(true);
        return reorderedItems;
      });
    }
    setActiveId(null);
  }, [reorderTasks]);

  // Handle drag start
  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  }, []);

  // Handle task edit
  const handleEditTask = useCallback((task: Task) => {
    setEditingTaskCode(task.code);
    setEditValue({ title: task.title, description: task.description });
  }, []);

  // Handle task edit save
  const handleEditSave = useCallback(() => {
    setLocalTasks((tasks) => {
      const updatedTasks = tasks.map((task) =>
        task.code === editingTaskCode
          ? { ...task, title: editValue.title, description: editValue.description }
          : task
      );
      setHasUnsavedChanges(true);
      return updatedTasks;
    });
    setEditingTaskCode(null);
    setEditValue({ title: '', description: '' });
  }, [editingTaskCode, editValue]);

  // Handle task edit cancel
  const handleEditCancel = useCallback(() => {
    setEditingTaskCode(null);
    setEditValue({ title: '', description: '' });
  }, []);

  // Handle task delete
  const handleDeleteTask = useCallback((code: string) => {
    setLocalTasks((tasks) => {
      const filteredTasks = tasks.filter((task) => task.code !== code);
      const reorderedTasks = reorderTasks(filteredTasks);
      setHasUnsavedChanges(true);
      return reorderedTasks;
    });
  }, [reorderTasks]);

  // Handle add task above
  const handleAddTaskAbove = useCallback((targetCode: string) => {
    setLocalTasks((tasks) => {
      const targetIndex = tasks.findIndex((task) => task.code === targetCode);
      if (targetIndex === -1) return tasks;

      const newTask: Task = {
        code: `T-NEW-${Date.now()}`, // Temporary code, will be reordered
        title: 'Nueva tarea',
        description: 'Descripción de la nueva tarea',
        dependencies: [],
        priority: 2,
        status: 'pending'
      };

      const newTasks = [...tasks];
      newTasks.splice(targetIndex, 0, newTask);
      const reorderedTasks = reorderTasks(newTasks);
      setHasUnsavedChanges(true);
      return reorderedTasks;
    });
  }, [reorderTasks]);

  // Handle add task below
  const handleAddTaskBelow = useCallback((targetCode: string) => {
    setLocalTasks((tasks) => {
      const targetIndex = tasks.findIndex((task) => task.code === targetCode);
      if (targetIndex === -1) return tasks;

      const newTask: Task = {
        code: `T-NEW-${Date.now()}`, // Temporary code, will be reordered
        title: 'Nueva tarea',
        description: 'Descripción de la nueva tarea',
        dependencies: [],
        priority: 2,
        status: 'pending'
      };

      const newTasks = [...tasks];
      newTasks.splice(targetIndex + 1, 0, newTask);
      const reorderedTasks = reorderTasks(newTasks);
      setHasUnsavedChanges(true);
      return reorderedTasks;
    });
  }, [reorderTasks]);

  // Handle save
  const handleSave = useCallback(() => {
    if (hasUnsavedChanges) {
      setShowSaveConfirm(true);
    }
  }, [hasUnsavedChanges]);

  // Confirm save
  const confirmSave = useCallback(() => {
    savePlanMutation.mutate(localTasks);
  }, [localTasks, savePlanMutation]);

  // Handle refine
  const handleRefine = useCallback(() => {
    setShowRefineDialog(true);
  }, []);

  // Confirm refine
  const confirmRefine = useCallback(() => {
    refinePlanMutation.mutate({ tasks: localTasks, prompt: refinePrompt });
  }, [localTasks, refinePrompt, refinePlanMutation]);

  // Accept plan mutation
  const acceptPlanMutation = useMutation({
    mutationFn: async () => {
      console.log('Attempting to accept plan:', selectedPlanId);
      // First accept the plan
      await apiPatch(`/api/v1/plans/${selectedPlanId}/accept`, {});
      // Then clean up old versions
      await apiDelete(`/api/v1/plans/cleanup/${project_id}`);
      return { accepted: true };
    },
    onSuccess: (data) => {
      console.log('Plan accepted and old versions cleaned up:', data);
      // Force refresh all plan-related queries
      queryClient.invalidateQueries({ queryKey: ['plan'] });
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.refetchQueries({ queryKey: ['plan', selectedPlanId] });
      queryClient.refetchQueries({ queryKey: ['plans', project_id] });
      alert('Plan aprobado exitosamente! Las versiones anteriores han sido eliminadas.');
    },
    onError: (error) => {
      console.error('Error accepting plan:', error);
      alert('Error al aprobar el plan: ' + error.message);
    },
  });

  // Handle accept plan
  const handleAcceptPlan = useCallback(() => {
    console.log('handleAcceptPlan called', { hasUnsavedChanges, selectedPlanId });
    if (hasUnsavedChanges) {
      alert('Tienes cambios sin guardar. Por favor, guarda los cambios antes de aprobar el plan.');
      return;
    }
    if (!selectedPlanId) {
      alert('No hay plan seleccionado');
      return;
    }
    console.log('Calling acceptPlanMutation.mutate()');
    acceptPlanMutation.mutate();
  }, [hasUnsavedChanges, acceptPlanMutation, selectedPlanId]);

  if (!project_id) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <ConsensusIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-600">Selecciona un proyecto</h3>
          <p className="text-gray-500">Para revisar y aprobar planes de desarrollo</p>
        </div>
      </div>
    );
  }

  if (isLoadingPlans) {
    return (
        <div className="flex-1 flex items-center justify-center">
            <p>Cargando planes...</p>
        </div>
    )
  }

  if (!plans || plans.length === 0) {
    return (
        <div className="flex-1 flex items-center justify-center">
            <p>No se encontraron planes para este proyecto.</p>
        </div>
    )
  }

  if (isLoadingPlanDetails) {
    return (
        <div className="flex-1 flex items-center justify-center">
            <p>Cargando detalles del plan...</p>
        </div>
    )
  }

  if (!planDetails) {
    return (
        <div className="flex-1 flex items-center justify-center">
            <p>Selecciona un plan para ver sus detalles.</p>
        </div>
    )
  }

  return (
    <div className="flex-1 flex">
      {/* Plan Review Area */}
      <div className="flex-1 p-6 overflow-y-auto">
        {/* Plan Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Plan de Desarrollo</h2>
              <div className="flex items-center gap-3 mt-2">
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                  isPlanApproved
                    ? 'bg-green-100 text-green-800'
                    : planDetails.status === 'rejected'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {isPlanApproved
                    ? 'APROBADO'
                    : planDetails.status === 'rejected'
                    ? 'RECHAZADO'
                    : 'PROPUESTO'}
                </span>
                <span className="text-sm text-gray-500">
                  Versión {planDetails.version} • Creado por {planDetails.created_by}
                </span>
                {isPlanApproved && (
                  <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                    Plan Activo
                  </span>
                )}
                {hasUnsavedChanges && !isPlanApproved && (
                  <span className="px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-xs font-medium">
                    Cambios sin guardar
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <select
                  value={selectedPlanId || ''}
                  onChange={(e) => setSelectedPlanId(Number(e.target.value))}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                  {plans?.map(p => (
                      <option key={p.id} value={p.id}>Version {p.version}</option>
                  ))}
              </select>
              {!isPlanApproved && (
                <>
                  <button
                    onClick={handleSave}
                    disabled={!hasUnsavedChanges}
                    className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 ${
                      hasUnsavedChanges
                        ? 'bg-blue-600 text-white hover:bg-blue-700'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                  >
                    <SaveIcon className="w-4 h-4" />
                    Guardar
                  </button>
                  <button
                    onClick={handleRefine}
                    className="px-4 py-2 border border-orange-300 text-orange-700 bg-orange-50 rounded-lg hover:bg-orange-100 transition-colors flex items-center gap-2"
                  >
                    <RefineIcon className="w-4 h-4" />
                    Refinar con IA
                  </button>
                </>
              )}
              {isPlanApproved && (
                <>
                  {!isEditingApprovedPlan ? (
                    <div className="flex gap-2">
                      <div className="px-4 py-2 bg-green-50 border border-green-200 text-green-700 rounded-lg flex items-center gap-2">
                        <ApproveIcon className="w-4 h-4" />
                        Plan Aprobado - Solo Lectura
                      </div>
                      <button
                        onClick={() => setIsEditingApprovedPlan(true)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
                      >
                        <EditIcon className="w-4 h-4" />
                        Editar Plan
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <div className="px-4 py-2 bg-orange-50 border border-orange-200 text-orange-700 rounded-lg flex items-center gap-2">
                        <EditIcon className="w-4 h-4" />
                        Editando Plan Aprobado
                      </div>
                      <button
                        onClick={handleSave}
                        disabled={!hasUnsavedChanges}
                        className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 ${
                          hasUnsavedChanges
                            ? 'bg-green-600 text-white hover:bg-green-700'
                            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                        }`}
                      >
                        <SaveIcon className="w-4 h-4" />
                        Sobrescribir Plan
                      </button>
                      <button
                        onClick={() => {
                          setIsEditingApprovedPlan(false);
                          setLocalTasks([...planDetails.tasks]);
                          setHasUnsavedChanges(false);
                        }}
                        className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        Cancelar
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-medium text-blue-900 mb-2">Resumen del Plan</h3>
            <p className="text-blue-800 text-sm">{planDetails.summary}</p>
          </div>
        </div>

        {/* Tasks List with Drag and Drop */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <TaskIcon className="w-5 h-5" />
            Tareas Propuestas ({localTasks.length})
            <span className="text-sm text-gray-500 font-normal ml-2">
              Arrastra para reordenar
            </span>
          </h3>

          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={localTasks.filter(t => {
                // Allow dragging non-completed tasks, and if plan is approved, only when editing
                return t.status !== 'done' && (!isPlanApproved || isEditingApprovedPlan);
              }).map(t => t.code)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-3">
                {localTasks.map((task) => (
                  <SortableTask
                    key={task.code}
                    task={task}
                    onEdit={handleEditTask}
                    onDelete={handleDeleteTask}
                    onAddTaskAbove={handleAddTaskAbove}
                    onAddTaskBelow={handleAddTaskBelow}
                    isEditing={editingTaskCode === task.code}
                    editValue={editValue}
                    onEditChange={(field, value) =>
                      setEditValue(prev => ({ ...prev, [field]: value }))
                    }
                    onEditSave={handleEditSave}
                    onEditCancel={handleEditCancel}
                    isPlanApproved={isPlanApproved}
                    isEditingApprovedPlan={isEditingApprovedPlan}
                  />
                ))}
              </div>
            </SortableContext>
            <DragOverlay>
              {activeId ? (
                <div className="bg-white border-2 border-blue-400 rounded-lg p-4 shadow-xl opacity-90">
                  {localTasks.find(t => t.code === activeId)?.title}
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        </div>

        {/* Approval Actions */}
        {!isPlanApproved ? (
          <div className="mt-8 bg-gray-50 border border-gray-200 rounded-lg p-6">
            <h3 className="font-medium text-gray-900 mb-4">Acciones de Consenso</h3>
            <div className="space-y-3">
              <div className="flex gap-3">
                <button
                  onClick={(e) => {
                    console.log('Button clicked', e);
                    handleAcceptPlan();
                  }}
                  disabled={hasUnsavedChanges || acceptPlanMutation.isPending}
                  className={`px-6 py-3 rounded-lg transition-colors flex items-center gap-2 ${
                    hasUnsavedChanges || acceptPlanMutation.isPending
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : 'bg-green-600 text-white hover:bg-green-700'
                  }`}
                  title={`Plan ID: ${selectedPlanId}, Unsaved: ${hasUnsavedChanges}, Pending: ${acceptPlanMutation.isPending}`}
                >
                  <ApproveIcon className="w-5 h-5" />
                  {acceptPlanMutation.isPending ? 'Aprobando...' : 'Aprobar Plan'}
                </button>
                <button className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2">
                  <RejectIcon className="w-5 h-5" />
                  Rechazar
                </button>
              </div>
              {hasUnsavedChanges && (
                <p className="text-sm text-orange-600 bg-orange-50 p-3 rounded-lg">
                  ⚠️ Tienes cambios sin guardar. Guarda los cambios antes de aprobar el plan.
                </p>
              )}
              <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg">
                <p className="font-medium mb-1">Al aprobar este plan:</p>
                <ul className="text-xs space-y-1 ml-4">
                  <li>• Se marcará como el plan activo del proyecto</li>
                  <li>• Se generará/actualizará el contexto inicial</li>
                  <li>• Las tareas estarán listas para la ejecución</li>
                  <li>• Se notificará al sistema para comenzar el desarrollo</li>
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-8 bg-green-50 border border-green-200 rounded-lg p-6">
            <h3 className="font-medium text-green-800 mb-4 flex items-center gap-2">
              <ApproveIcon className="w-5 h-5" />
              Plan Aprobado y Activo
            </h3>
            <div className="text-sm text-green-700 bg-green-100 p-3 rounded-lg">
              <p className="font-medium mb-1">Este plan ha sido aprobado y está activo:</p>
              <ul className="text-xs space-y-1 ml-4">
                <li>• Todas las tareas están en modo solo lectura</li>
                <li>• El contexto del proyecto ha sido generado</li>
                <li>• Las tareas están listas para la ejecución</li>
                <li>• Puedes continuar al workspace de Ejecución</li>
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Side Panel */}
      <div className="w-80 border-l border-gray-200 bg-gray-50 p-6">
        <h3 className="font-medium text-gray-900 mb-4">Información del Plan</h3>

        <div className="space-y-4">
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Estadísticas</h4>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Total de tareas:</span>
                <span className="font-medium">{localTasks.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Completadas:</span>
                <span className="font-medium text-green-600">
                  {localTasks.filter(t => t.status === 'done').length}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">En progreso:</span>
                <span className="font-medium text-yellow-600">
                  {localTasks.filter(t => t.status === 'in_progress').length}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Alta prioridad:</span>
                <span className="font-medium text-red-600">
                  {localTasks.filter(t => t.priority === 1).length}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Con dependencias:</span>
                <span className="font-medium">
                  {localTasks.filter(t => t.dependencies.length > 0).length}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Historial</h4>
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                <span className="text-gray-600">Plan generado por IA</span>
              </div>
              <div className="text-xs text-gray-500 ml-4">Hace 2 horas</div>
              {hasUnsavedChanges && (
                <>
                  <div className="flex items-center gap-2 text-sm">
                    <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                    <span className="text-gray-600">Cambios pendientes</span>
                  </div>
                  <div className="text-xs text-gray-500 ml-4">En caché local</div>
                </>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Notas</h4>
            <textarea
              className="w-full h-20 text-sm border border-gray-300 rounded p-2 resize-none"
              placeholder="Añade notas sobre este plan..."
            />
          </div>
        </div>
      </div>

      {/* Save Confirmation Dialog */}
      {showSaveConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-4">
              {isPlanApproved && isEditingApprovedPlan ? 'Confirmar Sobrescritura' : 'Confirmar Guardado'}
            </h3>
            <p className="text-gray-600 mb-6">
              {isPlanApproved && isEditingApprovedPlan
                ? '¿Estás seguro de que quieres sobrescribir el plan aprobado? Esto actualizará las tareas sin crear una nueva versión y regenerará el contexto del proyecto.'
                : '¿Estás seguro de que quieres guardar los cambios? Esto reemplazará completamente el plan actual en la base de datos.'
              }
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowSaveConfirm(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={confirmSave}
                className={`px-4 py-2 rounded-lg text-white ${
                  isPlanApproved && isEditingApprovedPlan
                    ? 'bg-orange-600 hover:bg-orange-700'
                    : 'bg-blue-600 hover:bg-blue-700'
                }`}
              >
                {isPlanApproved && isEditingApprovedPlan ? 'Sobrescribir Plan' : 'Guardar cambios'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Refine Dialog */}
      {showRefineDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-4">Refinar Plan con IA</h3>
            <p className="text-gray-600 mb-4">
              Describe los cambios o mejoras que deseas que la IA aplique al plan:
            </p>
            <textarea
              value={refinePrompt}
              onChange={(e) => setRefinePrompt(e.target.value)}
              className="w-full h-32 border border-gray-300 rounded-lg p-3 mb-4"
              placeholder="Ej: Añade más detalles técnicos, divide las tareas grandes, prioriza el rendimiento..."
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowRefineDialog(false);
                  setRefinePrompt('');
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={confirmRefine}
                disabled={!refinePrompt.trim()}
                className={`px-4 py-2 rounded-lg ${
                  refinePrompt.trim()
                    ? 'bg-orange-600 text-white hover:bg-orange-700'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                }`}
              >
                Refinar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Icons
function ConsensusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M9,11H15L13,9L15,7H9V9L11,11L9,13V11M7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17A5,5 0 0,1 7,12M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z" />
    </svg>
  );
}

function TaskIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
    </svg>
  );
}

function EditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z" />
    </svg>
  );
}

function RefineIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2A3,3 0 0,1 15,5V11A3,3 0 0,1 12,14A3,3 0 0,1 9,11V5A3,3 0 0,1 12,2M19,11C19,14.53 16.39,17.44 13,17.93V21H11V17.93C7.61,17.44 5,14.53 5,11H7A5,5 0 0,0 12,16A5,5 0 0,0 17,11H19Z" />
    </svg>
  );
}

function DependencyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2A2,2 0 0,1 14,4C14,4.74 13.6,5.39 13,5.73V7.27C13.6,7.61 14,8.26 14,9A2,2 0 0,1 12,11A2,2 0 0,1 10,9A2,2 0 0,1 12,7A2,2 0 0,1 14,9A2,2 0 0,1 12,11V12.27C12.6,12.61 13,13.26 13,14A2,2 0 0,1 11,16A2,2 0 0,1 9,14A2,2 0 0,1 11,12A2,2 0 0,1 13,14A2,2 0 0,1 11,16V17.27C11.4,17.61 11.8,18.26 11.8,19A2,2 0 0,1 9.8,21A2,2 0 0,1 7.8,19A2,2 0 0,1 9.8,17A2,2 0 0,1 11.8,19Z" />
    </svg>
  );
}

function DeleteIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z" />
    </svg>
  );
}

function ApproveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M11,16.5L18,9.5L16.59,8.09L11,13.67L7.91,10.59L6.5,12L11,16.5Z" />
    </svg>
  );
}

function RejectIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2C17.53,2 22,6.47 22,12C22,17.53 17.53,22 12,22C6.47,22 2,17.53 2,12C2,6.47 6.47,2 12,2M15.59,7L12,10.59L8.41,7L7,8.41L10.59,12L7,15.59L8.41,17L12,13.41L15.59,17L17,15.59L13.41,12L17,8.41L15.59,7Z" />
    </svg>
  );
}

function DragIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M7,19V17H9V19H7M11,19V17H13V19H11M15,19V17H17V19H15M7,15V13H9V15H7M11,15V13H13V15H11M15,15V13H17V15H15M7,11V9H9V11H7M11,11V9H13V11H11M15,11V9H17V11H15M7,7V5H9V7H7M11,7V5H13V7H11M15,7V5H17V7H15Z" />
    </svg>
  );
}

function SaveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M15,9H5V5H15M12,19A3,3 0 0,1 9,16A3,3 0 0,1 12,13A3,3 0 0,1 15,16A3,3 0 0,1 12,19M17,3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V7L17,3Z" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M11,16.5L18,9.5L16.59,8.09L11,13.67L7.91,10.59L6.5,12L11,16.5Z" />
    </svg>
  );
}

function PlusUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z" />
      <path d="M7,14L12,9L17,14H7Z" fill="currentColor" opacity="0.3" />
    </svg>
  );
}

function PlusDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z" />
      <path d="M7,10L12,15L17,10H7Z" fill="currentColor" opacity="0.3" />
    </svg>
  );
}