import React from 'react';
import { useAppStore } from '@/store/appStore';

export default function ConsensusWorkspace() {
  const project_id = useAppStore((s) => s.project_id);

  // Mock plan data - in real implementation, fetch from API
  const mockPlan = {
    id: 1,
    version: 1,
    status: 'proposed',
    summary: 'Plan inicial para desarrollo del juego de plataformas 2D',
    created_by: 'AI Assistant',
    created_at: '2024-01-15T10:30:00Z',
    tasks: [
      {
        code: 'T-001',
        title: 'Configuración inicial del proyecto',
        description: 'Crear la estructura base del proyecto Unity y configurar las carpetas principales',
        dependencies: [],
        priority: 1,
        status: 'pending'
      },
      {
        code: 'T-002',
        title: 'Implementar movimiento del personaje',
        description: 'Crear el controlador básico para el movimiento horizontal y salto del personaje',
        dependencies: ['T-001'],
        priority: 1,
        status: 'pending'
      },
      {
        code: 'T-003',
        title: 'Sistema de colisiones',
        description: 'Implementar detección de colisiones con plataformas y obstáculos',
        dependencies: ['T-002'],
        priority: 2,
        status: 'pending'
      }
    ]
  };

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
                <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs font-medium">
                  Pendiente de Aprobación
                </span>
                <span className="text-sm text-gray-500">
                  Versión {mockPlan.version} • Creado por {mockPlan.created_by}
                </span>
              </div>
            </div>
            <div className="flex gap-2">
              <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2">
                <EditIcon className="w-4 h-4" />
                Editar
              </button>
              <button className="px-4 py-2 border border-orange-300 text-orange-700 bg-orange-50 rounded-lg hover:bg-orange-100 transition-colors flex items-center gap-2">
                <RefineIcon className="w-4 h-4" />
                Refinar
              </button>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-medium text-blue-900 mb-2">Resumen del Plan</h3>
            <p className="text-blue-800 text-sm">{mockPlan.summary}</p>
          </div>
        </div>

        {/* Tasks List */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <TaskIcon className="w-5 h-5" />
            Tareas Propuestas ({mockPlan.tasks.length})
          </h3>

          <div className="space-y-3">
            {mockPlan.tasks.map((task, index) => (
              <div key={task.code} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-mono">
                        {task.code}
                      </span>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        task.priority === 1
                          ? 'bg-red-100 text-red-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}>
                        Prioridad {task.priority}
                      </span>
                    </div>
                    <h4 className="font-medium text-gray-900 mb-1">{task.title}</h4>
                    <p className="text-gray-600 text-sm mb-3">{task.description}</p>

                    {task.dependencies.length > 0 && (
                      <div className="flex items-center gap-2">
                        <DependencyIcon className="w-4 h-4 text-gray-400" />
                        <span className="text-xs text-gray-500">
                          Depende de: {task.dependencies.join(', ')}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <button className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors" title="Editar tarea">
                      <EditIcon className="w-4 h-4" />
                    </button>
                    <button className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors" title="Eliminar tarea">
                      <DeleteIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Approval Actions */}
        <div className="mt-8 bg-gray-50 border border-gray-200 rounded-lg p-6">
          <h3 className="font-medium text-gray-900 mb-4">Acciones de Consenso</h3>
          <div className="flex gap-3">
            <button className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2">
              <ApproveIcon className="w-5 h-5" />
              Aprobar Plan
            </button>
            <button className="px-6 py-3 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors flex items-center gap-2">
              <RefineIcon className="w-5 h-5" />
              Solicitar Refinamiento
            </button>
            <button className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2">
              <RejectIcon className="w-5 h-5" />
              Rechazar
            </button>
          </div>
        </div>
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
                <span className="font-medium">{mockPlan.tasks.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Alta prioridad:</span>
                <span className="font-medium text-red-600">
                  {mockPlan.tasks.filter(t => t.priority === 1).length}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Con dependencias:</span>
                <span className="font-medium">
                  {mockPlan.tasks.filter(t => t.dependencies.length > 0).length}
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