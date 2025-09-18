import React, { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { useTasks } from '@/hooks/useTasks';
import { Task, askOneShot } from '@/lib/api';
import { useChatStream } from '@/lib/useChatStream';
import { renderMarkdown } from '@/lib/markdown';

export default function ExecutionWorkspace() {
  const project_id = useAppStore((s) => s.project_id);
  const [confirmingAction, setConfirmingAction] = useState<{ taskId: number; action: string } | null>(null);
  const [showAutomatableList, setShowAutomatableList] = useState(false);
  const [showAgentMessages, setShowAgentMessages] = useState(false);
  const [executingTaskId, setExecutingTaskId] = useState<number | null>(null);

  // Chat stream for agent responses
  const { messages, bottomRef } = useChatStream(project_id);

  const {
    tasks,
    loading,
    error,
    startTask,
    finishTask,
    importTasksFromPlan,
    getTaskStats,
    getCurrentTask,
    getNextAvailableTask
  } = useTasks(project_id);

  const stats = getTaskStats();
  const currentTask = getCurrentTask();
  const nextTask = getNextAvailableTask();

  // Handlers

  const handleCompleteTask = async (taskId: number) => {
    setConfirmingAction({ taskId, action: 'complete' });
  };

  const handleConfirmAction = async () => {
    if (!confirmingAction) return;

    try {
      if (confirmingAction.action === 'complete') {
        await finishTask(confirmingAction.taskId);
      }
    } catch (err) {
      console.error('Error completing action:', err);
    } finally {
      setConfirmingAction(null);
    }
  };


  const handleExecuteTask = async (taskId: number) => {
    const task = tasks.find(t => t.id === taskId);
    if (!task || !project_id) return;

    try {
      // Primero marcar la tarea como en progreso
      await startTask(taskId);

      // Construir el prompt para ejecutar la tarea
      const prompt = `
Ejecuta la siguiente tarea del proyecto:

TAREA: ${task.taskId} - ${task.title}
DESCRIPCIÓN: ${task.description}

CRITERIOS DE ACEPTACIÓN:
${task.acceptance}

Por favor:
1. Analiza la tarea y los criterios de aceptación
2. Ejecuta los pasos necesarios para completar la tarea
3. Verifica que se cumplan todos los criterios
4. Proporciona un resumen de lo realizado

¡Comienza ahora!`;

      // Ejecutar usando askOneShot como en el chat
      await askOneShot(project_id, prompt);

    } catch (err) {
      console.error('Error executing task:', err);
    }
  };

  const handleTaskDetails = async (taskId: number) => {
    const task = tasks.find(t => t.id === taskId);
    if (!task || !project_id) return;

    try {
      const prompt = `
Analiza los detalles de esta tarea:

TAREA: ${task.taskId} - ${task.title}
DESCRIPCIÓN: ${task.description}
ESTADO: ${task.status}

CRITERIOS DE ACEPTACIÓN:
${task.acceptance}

${task.evidence?.length > 0 ? `EVIDENCIA ACTUAL:
${JSON.stringify(task.evidence, null, 2)}` : ''}

Por favor proporciona:
1. Análisis detallado de la tarea
2. Pasos sugeridos para completarla
3. Evaluación del estado actual
4. Recomendaciones para continuar`;

      await askOneShot(project_id, prompt);
    } catch (err) {
      console.error('Error getting task details:', err);
    }
  };

  const getTaskProgress = (task: Task) => {
    if (task.status === 'done') return 100;
    if (task.status === 'in_progress') return 50;
    return 0;
  };

  // Automation helpers
  const isAutomatable = (task: Task) => {
    // Tasks are automatable if they involve setup, configuration, or code generation
    const automatableKeywords = [
      'configuración', 'setup', 'inicialización', 'estructura',
      'código base', 'template', 'scaffolding', 'documentación',
      'readme', 'archivo', 'carpeta', 'directorio'
    ];

    const text = `${task.title} ${task.description}`.toLowerCase();
    return automatableKeywords.some(keyword => text.includes(keyword));
  };

  const calculateTimeSavings = () => {
    return tasks
      .filter(t => isAutomatable(t))
      .reduce((total, task) => total + (task.estimatedHours || 2), 0);
  };

  const handleAutomateTask = async (taskId: number) => {
    try {
      await handleExecuteTask(taskId);
    } catch (err) {
      console.error('Error automating task:', err);
    }
  };

  const handleAutomateAvailable = async () => {
    const automatableTasks = tasks.filter(t => isAutomatable(t) && t.status === 'pending');

    if (automatableTasks.length === 0) return;

    try {
      // Execute the first automatable task
      await handleExecuteTask(automatableTasks[0].id);
    } catch (err) {
      console.error('Error starting automation:', err);
    }
  };

  if (!project_id) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <ExecutionIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-600">Selecciona un proyecto</h3>
          <p className="text-gray-500">Para ejecutar y monitorear tareas</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 mb-4">Error al cargar las tareas</div>
          <p className="text-gray-500 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Recargar
          </button>
        </div>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'in_progress': return 'bg-blue-100 text-blue-800';
      case 'pending': return 'bg-gray-100 text-gray-800';
      case 'blocked': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed': return 'Completada';
      case 'in_progress': return 'En Progreso';
      case 'pending': return 'Pendiente';
      case 'blocked': return 'Bloqueada';
      default: return status;
    }
  };

  return (
    <div className="flex-1 flex">
      {/* Main Execution Area */}
      <div className={`${showAgentMessages ? 'w-1/2' : 'flex-1'} p-6 overflow-y-auto`}>
        {/* Execution Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Ejecución de Tareas</h2>
              <p className="text-gray-600">Monitorea y ejecuta las tareas aprobadas del plan</p>
            </div>
            <div className="flex gap-2">
              {tasks.length === 0 && (
                <button
                  onClick={importTasksFromPlan}
                  disabled={loading}
                  className="px-4 py-2 border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                  <AutomateIcon className="w-4 h-4" />
                  Importar Tareas
                </button>
              )}
              <button
                onClick={() => setShowAgentMessages(!showAgentMessages)}
                className={`px-4 py-2 border rounded-lg transition-colors flex items-center gap-2 ${
                  showAgentMessages
                    ? 'bg-purple-600 text-white border-purple-600 hover:bg-purple-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                <ChatIcon className="w-4 h-4" />
                {showAgentMessages ? 'Ocultar' : 'Ver'} Respuestas IA
                {messages.length > 0 && (
                  <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                    {messages.length}
                  </span>
                )}
              </button>
              <button
                onClick={() => nextTask && handleExecuteTask(nextTask.id)}
                disabled={loading || !nextTask}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:bg-gray-400"
              >
                <PlayIcon className="w-4 h-4" />
                {nextTask ? 'Ejecutar Siguiente' : 'Sin Tareas Disponibles'}
              </button>
            </div>
          </div>

          {/* Progress Overview */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
                <div className="text-sm text-gray-600">Completadas</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{stats.inProgress}</div>
                <div className="text-sm text-gray-600">En Progreso</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-600">{stats.pending}</div>
                <div className="text-sm text-gray-600">Pendientes</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">{stats.progress}%</div>
                <div className="text-sm text-gray-600">Progreso Total</div>
              </div>
            </div>
          </div>
        </div>

        {/* Tasks List */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <TaskListIcon className="w-5 h-5" />
            Lista de Tareas
          </h3>

          <div className="space-y-3">
            {loading && (
              <div className="text-center py-8">
                <div className="text-gray-500">Cargando tareas...</div>
              </div>
            )}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                Error: {error}
              </div>
            )}
            {!loading && tasks.length === 0 && (
              <div className="text-center py-8">
                <div className="text-gray-500">No hay tareas disponibles</div>
                <button
                  onClick={importTasksFromPlan}
                  className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Importar desde Plan
                </button>
              </div>
            )}
            {tasks.map((task) => (
              <div key={task.id} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-mono">
                        {task.taskId}
                      </span>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                        {getStatusText(task.status)}
                      </span>
                      {task.assignedTo && (
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                          👤 {task.assignedTo}
                        </span>
                      )}
                    </div>

                    <h4 className="font-medium text-gray-900 mb-2">{task.title}</h4>

                    {/* Progress Bar */}
                    <div className="mb-3">
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-gray-600">Progreso</span>
                        <span className="font-medium">{getTaskProgress(task)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            task.status === 'done' ? 'bg-green-500' :
                            task.status === 'in_progress' ? 'bg-blue-500' : 'bg-gray-300'
                          }`}
                          style={{ width: `${getTaskProgress(task)}%` }}
                        />
                      </div>
                    </div>

                    {/* Time Information */}
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <div className="flex items-center gap-1">
                        <ClockIcon className="w-4 h-4" />
                        <span>Estimado: {task.estimatedHours}h</span>
                      </div>
                      {(task.actualHours || 0) > 0 && (
                        <div className="flex items-center gap-1">
                          <TimerIcon className="w-4 h-4" />
                          <span>Actual: {task.actualHours}h</span>
                        </div>
                      )}
                      {task.startedAt && (
                        <div className="flex items-center gap-1">
                          <StartIcon className="w-4 h-4" />
                          <span>Iniciado: {new Date(task.startedAt).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Task Actions */}
                  <div className="flex items-center gap-2 ml-4">
                    {task.status === 'pending' && (
                      <button
                        onClick={() => handleExecuteTask(task.id)}
                        disabled={loading}
                        className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
                      >
                        Iniciar
                      </button>
                    )}
                    {task.status === 'in_progress' && (
                      <button
                        onClick={() => handleCompleteTask(task.id)}
                        disabled={loading}
                        className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 transition-colors disabled:opacity-50"
                      >
                        Completar
                      </button>
                    )}
                    <button
                      onClick={() => handleTaskDetails(task.id)}
                      disabled={loading}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded transition-colors disabled:opacity-50"
                      title="Ver detalles y criterios de aceptación"
                    >
                      <MoreIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Automation Panel */}
        <div className="mt-8 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-6">
          <h3 className="font-medium text-purple-900 mb-4 flex items-center gap-2">
            <AutomateIcon className="w-5 h-5" />
            Automatización Inteligente
          </h3>
          <p className="text-purple-800 text-sm mb-4">
            El asistente de IA puede ejecutar automáticamente ciertas tareas como configuración de proyecto,
            generación de código base y documentación.
          </p>

          {/* Automation Stats */}
          <div className="mb-4 grid grid-cols-2 gap-4">
            <div className="bg-white bg-opacity-50 rounded p-3">
              <div className="text-sm text-purple-700">Tareas Automatizables</div>
              <div className="text-xl font-bold text-purple-900">
                {tasks.filter(t => isAutomatable(t)).length}
              </div>
            </div>
            <div className="bg-white bg-opacity-50 rounded p-3">
              <div className="text-sm text-purple-700">Tiempo Estimado Ahorrado</div>
              <div className="text-xl font-bold text-purple-900">
                {calculateTimeSavings()}h
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleAutomateAvailable}
              disabled={loading || tasks.filter(t => isAutomatable(t) && t.status === 'pending').length === 0}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Automatizar Disponibles ({tasks.filter(t => isAutomatable(t) && t.status === 'pending').length})
            </button>
            <button
              onClick={() => setShowAutomatableList(!showAutomatableList)}
              className="px-4 py-2 border border-purple-300 text-purple-700 rounded-lg hover:bg-purple-50 transition-colors text-sm"
            >
              {showAutomatableList ? 'Ocultar' : 'Ver'} Tareas Automatizables
            </button>
          </div>

          {/* Automatable Tasks List */}
          {showAutomatableList && (
            <div className="mt-4 bg-white bg-opacity-50 rounded-lg p-4">
              <h4 className="text-sm font-medium text-purple-900 mb-3">Tareas que pueden automatizarse:</h4>
              <div className="space-y-2">
                {tasks.filter(t => isAutomatable(t)).map(task => (
                  <div key={task.id} className="flex items-center justify-between py-2 px-3 bg-white rounded border">
                    <div>
                      <span className="text-sm font-medium">{task.taskId}</span>
                      <span className="text-sm text-gray-600 ml-2">{task.title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 rounded-full text-xs ${
                        task.status === 'done' ? 'bg-green-100 text-green-800' :
                        task.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {getStatusText(task.status)}
                      </span>
                      {task.status === 'pending' && (
                        <button
                          onClick={() => handleAutomateTask(task.id)}
                          disabled={loading}
                          className="px-2 py-1 bg-purple-600 text-white rounded text-xs hover:bg-purple-700 disabled:opacity-50"
                        >
                          Automatizar
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {tasks.filter(t => isAutomatable(t)).length === 0 && (
                  <div className="text-sm text-gray-500 italic">No hay tareas automatizables disponibles</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Agent Messages Panel */}
      {showAgentMessages && (
        <div className="w-1/2 border-l border-gray-200 bg-white flex flex-col">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <h3 className="font-medium text-gray-900 flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              Respuesta del Agente IA
              {executingTaskId && (
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                  Ejecutando Tarea
                </span>
              )}
            </h3>
            <button
              onClick={() => {
                setShowAgentMessages(false);
                setExecutingTaskId(null);
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              ×
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-4">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  <div className="mb-2">Esperando respuesta del agente...</div>
                  <div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mx-auto"></div>
                </div>
              ) : (
                messages.slice(-10).map((message) => ( // Solo mostrar los últimos 10 mensajes
                  <div
                    key={message.id}
                    className={`p-3 rounded-lg max-w-full ${
                      message.role === 'user'
                        ? 'bg-blue-50 border border-blue-200 ml-4'
                        : message.role === 'agent'
                        ? 'bg-gray-50 border border-gray-200 mr-4'
                        : 'bg-yellow-50 border border-yellow-200'
                    }`}
                  >
                    <div className="text-xs text-gray-500 mb-1 capitalize">
                      {message.role === 'agent' ? '🤖 Agente IA' : message.role === 'user' ? '👤 Usuario' : '⚙️ Sistema'}
                      {message.ts && (
                        <span className="ml-2">
                          {new Date(message.ts).toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                    <div className="text-sm">
                      {message.content ? (
                        <div
                          className="prose prose-sm max-w-none"
                          dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
                        />
                      ) : (
                        <span className="text-gray-500 italic">(Sin contenido)</span>
                      )}
                    </div>
                    {message.attachments?.map((att, i) => (
                      <div key={i} className="mt-2">
                        {att.type === 'image' && (
                          <img
                            src={att.url || att.dataUrl}
                            alt="Attachment"
                            className="max-w-full h-auto rounded border"
                          />
                        )}
                      </div>
                    ))}
                    {message.toolPayload && (
                      <div className="mt-2 p-2 bg-white rounded border text-xs">
                        <pre>{JSON.stringify(message.toolPayload, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                ))
              )}
              <div ref={bottomRef} />
            </div>
          </div>
          {executingTaskId && (
            <div className="p-4 border-t border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Ejecutando tarea...</span>
                <button
                  onClick={() => {
                    setExecutingTaskId(null);
                    // Aquí podríamos añadir lógica para marcar como completada
                  }}
                  className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 transition-colors"
                >
                  Marcar como Completada
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Side Panel */}
      <div className="w-80 border-l border-gray-200 bg-gray-50 p-6">
        <h3 className="font-medium text-gray-900 mb-4">Panel de Control</h3>

        <div className="space-y-4">
          {/* Current Task */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Tarea Actual</h4>
            {currentTask ? (
              <div className="space-y-2">
                <div className="text-sm font-medium">{currentTask.taskId}: {currentTask.title}</div>
                <div className="text-xs text-gray-600">
                  {getStatusText(currentTask.status)} - {getTaskProgress(currentTask)}% completado
                </div>
                <div className="text-xs text-gray-500 max-h-20 overflow-y-auto">
                  {currentTask.description}
                </div>
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => handleCompleteTask(currentTask.id)}
                    disabled={loading}
                    className="px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50"
                  >
                    Completar
                  </button>
                  <button
                    onClick={() => handleTaskDetails(currentTask.id)}
                    disabled={loading}
                    className="px-2 py-1 border border-gray-300 text-gray-700 rounded text-xs hover:bg-gray-50 disabled:opacity-50"
                  >
                    Detalles
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-500">No hay tarea en progreso</div>
            )}
          </div>

          {/* Quick Actions */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Acciones Rápidas</h4>
            <div className="space-y-2">
              <button
                onClick={() => nextTask && handleExecuteTask(nextTask.id)}
                disabled={loading || !nextTask}
                className="w-full p-2 text-sm text-left border border-gray-200 rounded hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                🚀 {nextTask ? `Ejecutar ${nextTask.taskId}` : 'Sin tareas disponibles'}
              </button>
              {currentTask && (
                <button
                  onClick={() => handleCompleteTask(currentTask.id)}
                  disabled={loading}
                  className="w-full p-2 text-sm text-left border border-gray-200 rounded hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  ⏸️ Completar tarea actual
                </button>
              )}
              <button
                className="w-full p-2 text-sm text-left border border-gray-200 rounded hover:bg-gray-50 transition-colors"
              >
                📊 Total: {stats.total} tareas
              </button>
              {tasks.length === 0 && (
                <button
                  onClick={importTasksFromPlan}
                  disabled={loading}
                  className="w-full p-2 text-sm text-left border border-gray-200 rounded hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  🔧 Importar tareas del plan
                </button>
              )}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Actividad Reciente</h4>
            <div className="space-y-2">
              {tasks
                .filter(t => t.startedAt || t.completedAt)
                .sort((a, b) => {
                  const aTime = new Date(a.completedAt || a.startedAt || 0).getTime();
                  const bTime = new Date(b.completedAt || b.startedAt || 0).getTime();
                  return bTime - aTime;
                })
                .slice(0, 3)
                .map(task => {
                  const isCompleted = task.status === 'done';
                  const time = isCompleted ? task.completedAt : task.startedAt;
                  return (
                    <div key={task.id} className="text-xs">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${
                          isCompleted ? 'bg-green-500' : 'bg-blue-500'
                        }`}></div>
                        <span className="text-gray-600">
                          {task.taskId} {isCompleted ? 'completada' : 'iniciada'}
                        </span>
                      </div>
                      <div className="text-gray-500 ml-4">
                        {time ? new Date(time).toLocaleString() : 'Fecha desconocida'}
                      </div>
                    </div>
                  );
                })}
              {tasks.filter(t => t.startedAt || t.completedAt).length === 0 && (
                <div className="text-xs text-gray-500">Sin actividad reciente</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmingAction && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">
              Confirmar {confirmingAction.action === 'complete' ? 'Completar Tarea' : 'Acción'}
            </h3>
            <p className="text-gray-600 mb-6">
              {confirmingAction.action === 'complete'
                ? '¿Estás seguro de que quieres marcar esta tarea como completada?'
                : '¿Estás seguro de que quieres realizar esta acción?'}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmingAction(null)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmAction}
                disabled={loading}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {loading ? 'Procesando...' : 'Confirmar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Icons
function ExecutionIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8,5.14V19.14L19,12.14L8,5.14Z" />
    </svg>
  );
}

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8,5.14V19.14L19,12.14L8,5.14Z" />
    </svg>
  );
}

function AutomateIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10M10,22C9.75,22 9.54,21.82 9.5,21.58L9.13,18.93C8.5,18.68 7.96,18.34 7.44,17.94L4.95,18.95C4.73,19.03 4.46,18.95 4.34,18.73L2.34,15.27C2.22,15.05 2.27,14.78 2.46,14.63L4.57,12.97L4.5,12L4.57,11L2.46,9.37C2.27,9.22 2.22,8.95 2.34,8.73L4.34,5.27C4.46,5.05 4.73,4.96 4.95,5.05L7.44,6.05C7.96,5.66 8.5,5.32 9.13,5.07L9.5,2.42C9.54,2.18 9.75,2 10,2H14C14.25,2 14.46,2.18 14.5,2.42L14.87,5.07C15.5,5.32 16.04,5.66 16.56,6.05L19.05,5.05C19.27,4.96 19.54,5.05 19.66,5.27L21.66,8.73C21.78,8.95 21.73,9.22 21.54,9.37L19.43,11L19.5,12L19.43,13L21.54,14.63C21.73,14.78 21.78,15.05 21.66,15.27L19.66,18.73C19.54,18.95 19.27,19.03 19.05,18.95L16.56,17.95C16.04,18.34 15.5,18.68 14.87,18.93L14.5,21.58C14.46,21.82 14.25,22 14,22H10M11.25,4L10.88,6.61C9.68,6.86 8.62,7.5 7.85,8.39L5.44,7.35L4.69,8.65L6.8,10.2C6.4,11.37 6.4,12.64 6.8,13.8L4.68,15.36L5.43,16.66L7.86,15.62C8.63,16.5 9.68,17.14 10.87,17.38L11.24,20H12.76L13.13,17.39C14.32,17.14 15.37,16.5 16.14,15.62L18.57,16.66L19.32,15.36L17.2,13.81C17.6,12.64 17.6,11.37 17.2,10.2L19.31,8.65L18.56,7.35L16.15,8.39C15.38,7.5 14.32,6.86 13.12,6.62L12.75,4H11.25Z" />
    </svg>
  );
}

function TaskListIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M3,5H9V11H3V5M5,7V9H7V7H5M11,7H21V9H11V7M11,15H21V17H11V15M5,20L1.5,16.5L2.91,15.09L5,17.17L9.59,12.58L11,14L5,20Z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M16.2,16.2L11,13V7H12.5V12.2L17,14.7L16.2,16.2Z" />
    </svg>
  );
}

function TimerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M15,1H9V3H15V1M11,14H13V8H11M19.03,7.39L20.45,5.97C20,5.46 19.55,5 19.04,4.56L17.62,6C16.07,4.74 14.12,4 12,4A9,9 0 0,0 3,13A9,9 0 0,0 12,22C17,22 21,17.97 21,13C21,10.88 20.26,8.93 19.03,7.39Z" />
    </svg>
  );
}

function StartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M7,6H17V9L21,5L17,1V4H5V11H7V6M17,18H7V15L3,19L7,23V20H19V13H17V18Z" />
    </svg>
  );
}

function MoreIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,16A2,2 0 0,1 14,18A2,2 0 0,1 12,20A2,2 0 0,1 10,18A2,2 0 0,1 12,16M12,10A2,2 0 0,1 14,12A2,2 0 0,1 12,14A2,2 0 0,1 10,12A2,2 0 0,1 12,10M12,4A2,2 0 0,1 14,6A2,2 0 0,1 12,8A2,2 0 0,1 10,6A2,2 0 0,1 12,4Z" />
    </svg>
  );
}

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,3C17.5,3 22,6.58 22,11C22,15.42 17.5,19 12,19C10.76,19 9.57,18.82 8.47,18.5C5.55,21 2,21 2,21C4.33,18.67 4.7,17.1 4.75,16.5C3.05,15.07 2,13.13 2,11C2,6.58 6.5,3 12,3Z" />
    </svg>
  );
}