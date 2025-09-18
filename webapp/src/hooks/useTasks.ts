import { useState, useEffect, useCallback } from 'react';
import { Task, listTasks, importTasks, completeTask, proposeTaskSteps, executeTaskTool, verifyTaskAcceptance } from '@/lib/api';
import { useWebSocket } from './useWebSocket';

export function useTasks(project_id: string | null) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(null);

  // WebSocket para updates en tiempo real
  const { lastMessage } = useWebSocket(project_id ? `/ws/projects/${project_id}` : null);

  // Cargar tareas iniciales
  const loadTasks = useCallback(async () => {
    if (!project_id) {
      setTasks([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const taskList = await listTasks(project_id);
      setTasks(taskList);

      // Encontrar tarea actual (en progreso)
      const currentTask = taskList.find(t => t.status === 'in_progress');
      setCurrentTaskId(currentTask?.id || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading tasks');
    } finally {
      setLoading(false);
    }
  }, [project_id]);

  // Efecto para cargar tareas cuando cambia el proyecto
  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // Manejar updates en tiempo real via WebSocket
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const { type, payload } = lastMessage;

      if (type === 'UPDATE' && payload?.event?.startsWith('task.')) {
        const { event, task } = payload;

        if (event === 'task.started' || event === 'task.completed' || event === 'task.updated') {
          setTasks(currentTasks => {
            const index = currentTasks.findIndex(t => t.id === task.id);
            if (index >= 0) {
              const updated = [...currentTasks];
              updated[index] = { ...updated[index], ...task };
              return updated;
            }
            return currentTasks;
          });

          if (event === 'task.started') {
            setCurrentTaskId(task.id);
          } else if (event === 'task.completed') {
            setCurrentTaskId(payload.next_task ?
              tasks.find(t => t.taskId === payload.next_task)?.id || null : null
            );
          }
        }
      }
    } catch (err) {
      console.error('Error processing WebSocket message:', err);
    }
  }, [lastMessage, tasks]);

  // Acciones de tareas
  const importTasksFromPlan = useCallback(async () => {
    if (!project_id) return;

    try {
      setLoading(true);
      await importTasks(project_id);
      await loadTasks(); // Recargar después de importar
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error importing tasks');
    } finally {
      setLoading(false);
    }
  }, [project_id, loadTasks]);

  const startTask = useCallback(async (taskId: number) => {
    try {
      setLoading(true);
      // El backend maneja el inicio de tareas automáticamente
      // Solo necesitamos refrescar la lista
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error starting task');
    } finally {
      setLoading(false);
    }
  }, [loadTasks]);

  const finishTask = useCallback(async (taskId: number, acceptanceConfirmed = true) => {
    try {
      setLoading(true);
      await completeTask(taskId, acceptanceConfirmed);
      await loadTasks(); // Recargar después de completar
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error completing task');
    } finally {
      setLoading(false);
    }
  }, [loadTasks]);

  const requestTaskSteps = useCallback(async (taskId: number) => {
    try {
      const result = await proposeTaskSteps(taskId);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error requesting task steps');
      throw err;
    }
  }, []);

  const executeTask = useCallback(async (taskId: number, tool: string, args: any, confirmed = false) => {
    try {
      const result = await executeTaskTool(taskId, tool, args, confirmed);
      await loadTasks(); // Recargar después de ejecutar
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error executing task');
      throw err;
    }
  }, [loadTasks]);

  const verifyTask = useCallback(async (taskId: number) => {
    try {
      const result = await verifyTaskAcceptance(taskId);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error verifying task');
      throw err;
    }
  }, []);

  // Obtener estadísticas de tareas
  const getTaskStats = useCallback(() => {
    const completed = tasks.filter(t => t.status === 'done').length;
    const inProgress = tasks.filter(t => t.status === 'in_progress').length;
    const pending = tasks.filter(t => t.status === 'pending').length;
    const blocked = tasks.filter(t => t.status === 'blocked').length;

    const total = tasks.length;
    const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

    return {
      completed,
      inProgress,
      pending,
      blocked,
      total,
      progress
    };
  }, [tasks]);

  // Obtener tarea actual
  const getCurrentTask = useCallback(() => {
    return currentTaskId ? tasks.find(t => t.id === currentTaskId) : null;
  }, [tasks, currentTaskId]);

  // Obtener próxima tarea disponible
  const getNextAvailableTask = useCallback(() => {
    const completedTaskIds = new Set(
      tasks.filter(t => t.status === 'done').map(t => t.taskId)
    );

    return tasks.find(t => {
      if (t.status !== 'pending') return false;

      // Verificar que todas las dependencias estén completadas
      return t.deps.every(dep => completedTaskIds.has(dep));
    });
  }, [tasks]);

  return {
    tasks,
    loading,
    error,
    currentTaskId,
    // Actions
    loadTasks,
    importTasksFromPlan,
    startTask,
    finishTask,
    requestTaskSteps,
    executeTask,
    verifyTask,
    // Computed values
    getTaskStats,
    getCurrentTask,
    getNextAvailableTask
  };
}