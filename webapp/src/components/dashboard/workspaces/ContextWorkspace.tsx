import React from 'react';
import { useAppStore } from '@/store/appStore';
import { ContextPanel } from '../../ContextPanel';

export default function ContextWorkspace() {
  const project_id = useAppStore((s) => s.project_id);

  if (!project_id) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <ContextIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-600">Selecciona un proyecto</h3>
          <p className="text-gray-500">Para ver y gestionar el contexto del proyecto</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex">
      {/* Main Context Area */}
      <div className="flex-1 p-6 overflow-y-auto">
        {/* Enhanced Context Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Contexto del Proyecto</h2>
              <p className="text-gray-600">Estado actual, decisiones y progreso del desarrollo</p>
            </div>
            <div className="flex gap-2">
              <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2">
                <ExportIcon className="w-4 h-4" />
                Exportar
              </button>
              <button className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors flex items-center gap-2">
                <RefreshIcon className="w-4 h-4" />
                Actualizar Contexto
              </button>
            </div>
          </div>

          {/* Project Status Overview */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                  <StatusIcon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="text-sm text-blue-700">Estado del Proyecto</div>
                  <div className="text-lg font-bold text-blue-900">En Desarrollo</div>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-green-600 rounded-lg flex items-center justify-center">
                  <ProgressIcon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="text-sm text-green-700">Progreso General</div>
                  <div className="text-lg font-bold text-green-900">65%</div>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-purple-600 rounded-lg flex items-center justify-center">
                  <PhaseIcon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="text-sm text-purple-700">Fase Actual</div>
                  <div className="text-lg font-bold text-purple-900">Ejecución</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Context Panel with Enhanced Layout */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <ContextPanel project_id={project_id} />
        </div>

        {/* Additional Context Insights */}
        <div className="mt-6 grid grid-cols-2 gap-6">
          {/* Key Metrics */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <MetricsIcon className="w-5 h-5" />
              Métricas Clave
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Tareas completadas</span>
                <span className="font-medium">8 / 12</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Tiempo invertido</span>
                <span className="font-medium">24.5 horas</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Código generado</span>
                <span className="font-medium">3,2K líneas</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Assets creados</span>
                <span className="font-medium">15 archivos</span>
              </div>
            </div>
          </div>

          {/* Recent Changes */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <HistoryIcon className="w-5 h-5" />
              Cambios Recientes
            </h3>
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 bg-green-500 rounded-full mt-2"></div>
                <div>
                  <div className="text-sm font-medium">Movimiento del personaje implementado</div>
                  <div className="text-xs text-gray-500">Hace 2 horas</div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                <div>
                  <div className="text-sm font-medium">Contexto actualizado automáticamente</div>
                  <div className="text-xs text-gray-500">Hace 4 horas</div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 bg-purple-500 rounded-full mt-2"></div>
                <div>
                  <div className="text-sm font-medium">Nueva decisión: Usar sprites 2D</div>
                  <div className="text-xs text-gray-500">Ayer</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Enhanced Side Panel */}
      <div className="w-80 border-l border-gray-200 bg-gray-50 p-6">
        <h3 className="font-medium text-gray-900 mb-4">Panel de Análisis</h3>

        <div className="space-y-4">
          {/* AI Insights */}
          <div className="bg-gradient-to-br from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-blue-900 mb-2 flex items-center gap-2">
              <AIIcon className="w-4 h-4" />
              Insights de IA
            </h4>
            <div className="text-sm text-blue-800 space-y-2">
              <p>• El progreso está dentro de lo esperado</p>
              <p>• Se recomienda priorizar T-003 para mantener el cronograma</p>
              <p>• Considera añadir tests unitarios</p>
            </div>
          </div>

          {/* Project Health */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Salud del Proyecto</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Código</span>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span className="text-sm font-medium">Buena</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Cronograma</span>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  <span className="text-sm font-medium">En riesgo</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Calidad</span>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span className="text-sm font-medium">Excelente</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Acciones Rápidas</h4>
            <div className="space-y-2">
              <button className="w-full p-2 text-sm text-left border border-gray-200 rounded hover:bg-gray-50 transition-colors flex items-center gap-2">
                <GenerateIcon className="w-4 h-4" />
                Generar resumen ejecutivo
              </button>
              <button className="w-full p-2 text-sm text-left border border-gray-200 rounded hover:bg-gray-50 transition-colors flex items-center gap-2">
                <ShareIcon className="w-4 h-4" />
                Compartir estado
              </button>
              <button className="w-full p-2 text-sm text-left border border-gray-200 rounded hover:bg-gray-50 transition-colors flex items-center gap-2">
                <ArchiveIcon className="w-4 h-4" />
                Crear snapshot
              </button>
            </div>
          </div>

          {/* Context Timeline */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Línea de Tiempo</h4>
            <div className="space-y-2">
              <div className="text-xs">
                <div className="font-medium">Versión 3</div>
                <div className="text-gray-500">Contexto actualizado - Hoy 14:30</div>
              </div>
              <div className="text-xs">
                <div className="font-medium">Versión 2</div>
                <div className="text-gray-500">Tareas completadas - Ayer 16:45</div>
              </div>
              <div className="text-xs">
                <div className="font-medium">Versión 1</div>
                <div className="text-gray-500">Contexto inicial - 2 días</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Icons
function ContextIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M13,9H18.5L13,3.5V9M6,2H14L20,8V20A2,2 0 0,1 18,22H6C4.89,22 4,21.1 4,20V4C4,2.89 4.89,2 6,2M15,18V16H6V18H15M18,14V12H6V14H18Z" />
    </svg>
  );
}

function ExportIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z" />
    </svg>
  );
}

function StatusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M11,16.5L18,9.5L16.59,8.09L11,13.67L7.91,10.59L6.5,12L11,16.5Z" />
    </svg>
  );
}

function ProgressIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M13,2.05V5.08C16.39,5.57 19,8.47 19,12C19,12.9 18.82,13.75 18.5,14.54L21.12,16.07C21.68,14.83 22,13.45 22,12C22,6.82 18.05,2.55 13,2.05M12,19C8.13,19 5,15.87 5,12C5,8.47 7.61,5.57 11,5.08V2.05C5.94,2.55 2,6.81 2,12A10,10 0 0,0 12,22C15.3,22 18.23,20.39 20.05,17.91L17.45,16.38C16.17,18 14.21,19 12,19Z" />
    </svg>
  );
}

function PhaseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8,5.14V19.14L19,12.14L8,5.14Z" />
    </svg>
  );
}

function MetricsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M22,21H2V3H4V19H6V10H10V19H12V6H16V19H18V14H22V21Z" />
    </svg>
  );
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M13.5,8H12V13L16.28,15.54L17,14.33L13.5,12.25V8M13,3A9,9 0 0,0 4,12H1L4.96,16.03L9,12H6A7,7 0 0,1 13,5A7,7 0 0,1 20,12A7,7 0 0,1 13,19C11.07,19 9.32,18.21 8.06,16.94L6.64,18.36C8.27,20 10.5,21 13,21A9,9 0 0,0 22,12A9,9 0 0,0 13,3" />
    </svg>
  );
}

function AIIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,9A1.5,1.5 0 0,1 19,10.5A1.5,1.5 0 0,1 17.5,12M10.5,12A1.5,1.5 0 0,1 9,10.5A1.5,1.5 0 0,1 10.5,9A1.5,1.5 0 0,1 12,10.5A1.5,1.5 0 0,1 10.5,12M12,2C13.1,2 14,2.9 14,4C14,5.1 13.1,6 12,6C10.9,6 10,5.1 10,4C10,2.9 10.9,2 12,2M21,9V7H15L13.5,7.5C13.1,4.04 11.36,3 10,3H8C5.24,3 3,5.24 3,8V16L7,20H17C19.76,20 22,17.76 22,15V12C22,10.9 21.1,10 20,10H18V9A1,1 0 0,1 19,8H21M20,15A2,2 0 0,1 18,17H8L5,14V8A2,2 0 0,1 7,6H9V8A2,2 0 0,0 11,10H20V15Z" />
    </svg>
  );
}

function GenerateIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8,3A2,2 0 0,0 6,5V9A2,2 0 0,1 4,11H3V13H4A2,2 0 0,1 6,15V19A2,2 0 0,0 8,21H10V19H8V14A2,2 0 0,0 6,12A2,2 0 0,0 8,10V5H10V3M16,3A2,2 0 0,1 18,5V9A2,2 0 0,0 20,11H21V13H20A2,2 0 0,0 18,15V19A2,2 0 0,1 16,21H14V19H16V14A2,2 0 0,1 18,12A2,2 0 0,1 16,10V5H14V3H16Z" />
    </svg>
  );
}

function ShareIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18,16.08C17.24,16.08 16.56,16.38 16.04,16.85L8.91,12.7C8.96,12.47 9,12.24 9,12C9,11.76 8.96,11.53 8.91,11.3L15.96,7.19C16.5,7.69 17.21,8 18,8A3,3 0 0,0 21,5A3,3 0 0,0 18,2A3,3 0 0,0 15,5C15,5.24 15.04,5.47 15.09,5.7L8.04,9.81C7.5,9.31 6.79,9 6,9A3,3 0 0,0 3,12A3,3 0 0,0 6,15C6.79,15 7.5,14.69 8.04,14.19L15.16,18.34C15.11,18.55 15.08,18.77 15.08,19C15.08,20.61 16.39,21.91 18,21.91C19.61,21.91 20.92,20.61 20.92,19A2.92,2.92 0 0,0 18,16.08Z" />
    </svg>
  );
}

function ArchiveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M3,3H21V7H3V3M4,8H20V21H4V8M9.5,11A0.5,0.5 0 0,0 9,11.5V13H15V11.5A0.5,0.5 0 0,0 14.5,11H9.5Z" />
    </svg>
  );
}