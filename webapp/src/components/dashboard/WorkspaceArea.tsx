import React from 'react';
import { useAppStore } from '@/store/appStore';
import ChatWorkspace from './workspaces/ChatWorkspace';
import ConsensusWorkspace from './workspaces/ConsensusWorkspace';
import ExecutionWorkspace from './workspaces/ExecutionWorkspace';
import ContextWorkspace from './workspaces/ContextWorkspace';

interface WorkspaceAreaProps {
  workspace: 'chat' | 'consensus' | 'execution' | 'context';
}

export default function WorkspaceArea({ workspace }: WorkspaceAreaProps) {
  const project_id = useAppStore((s) => s.project_id);

  // Show project selection prompt if no project and workspace requires it
  if (!project_id && workspace !== 'chat') {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center p-8">
          <ProjectRequiredIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-600 mb-2">Proyecto Requerido</h3>
          <p className="text-gray-500 mb-4">
            Selecciona o crea un proyecto para acceder a {getWorkspaceName(workspace)}
          </p>
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-lg border border-blue-200">
            <ArrowIcon className="w-4 h-4 text-blue-600" />
            <span className="text-sm text-blue-700">Usa el panel lateral para gestionar proyectos</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      {/* Workspace Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getWorkspaceIcon(workspace)}
            <div>
              <h1 className="text-xl font-semibold text-gray-800">
                {getWorkspaceName(workspace)}
              </h1>
              <p className="text-sm text-gray-600">
                {getWorkspaceDescription(workspace)}
              </p>
            </div>
          </div>

          {/* Workspace-specific actions */}
          <div className="flex items-center gap-2">
            {workspace === 'chat' && (
              <button className="px-3 py-1 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                Nueva Conversación
              </button>
            )}
            {workspace === 'consensus' && (
              <div className="flex gap-2">
                <button className="px-3 py-1 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                  Refinar Plan
                </button>
                <button className="px-3 py-1 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
                  Aprobar Plan
                </button>
              </div>
            )}
            {workspace === 'execution' && (
              <button className="px-3 py-1 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
                Ejecutar Tarea
              </button>
            )}
            {workspace === 'context' && (
              <button className="px-3 py-1 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                Editar Contexto
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Workspace Content */}
      <div className="flex-1 overflow-hidden">
        {workspace === 'chat' && <ChatWorkspace />}
        {workspace === 'consensus' && <ConsensusWorkspace />}
        {workspace === 'execution' && <ExecutionWorkspace />}
        {workspace === 'context' && <ContextWorkspace />}
      </div>
    </div>
  );
}

function getWorkspaceName(workspace: string): string {
  const names = {
    chat: 'Chat & AI Assistant',
    consensus: 'Consenso de Plan',
    execution: 'Ejecución de Tareas',
    context: 'Contexto del Proyecto'
  };
  return names[workspace as keyof typeof names] || workspace;
}

function getWorkspaceDescription(workspace: string): string {
  const descriptions = {
    chat: 'Conversa con el asistente de IA para planificar y resolver problemas',
    consensus: 'Revisa, refina y aprueba los planes de desarrollo generados por la IA',
    execution: 'Ejecuta tareas del plan aprobado y monitorea el progreso',
    context: 'Visualiza y gestiona el estado actual del proyecto'
  };
  return descriptions[workspace as keyof typeof descriptions] || '';
}

function getWorkspaceIcon(workspace: string) {
  const iconProps = { className: "w-6 h-6" };

  switch (workspace) {
    case 'chat':
      return <ChatIcon {...iconProps} className="w-6 h-6 text-blue-600" />;
    case 'consensus':
      return <ConsensusIcon {...iconProps} className="w-6 h-6 text-purple-600" />;
    case 'execution':
      return <ExecutionIcon {...iconProps} className="w-6 h-6 text-green-600" />;
    case 'context':
      return <ContextIcon {...iconProps} className="w-6 h-6 text-orange-600" />;
    default:
      return null;
  }
}

// Icons
function ProjectRequiredIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M9,3V4H4V6H5V19A2,2 0 0,0 7,21H17A2,2 0 0,0 19,19V6H20V4H15V3H9M7,6H17V19H7V6M9,8V17H11V8H9M13,8V17H15V8H13Z" />
    </svg>
  );
}

function ArrowIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M4,11V13H16L10.5,18.5L11.92,19.92L19.84,12L11.92,4.08L10.5,5.5L16,11H4Z" />
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

function ConsensusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M9,11H15L13,9L15,7H9V9L11,11L9,13V11M7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17A5,5 0 0,1 7,12M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z" />
    </svg>
  );
}

function ExecutionIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8,5.14V19.14L19,12.14L8,5.14Z" />
    </svg>
  );
}

function ContextIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M13,9H18.5L13,3.5V9M6,2H14L20,8V20A2,2 0 0,1 18,22H6C4.89,22 4,21.1 4,20V4C4,2.89 4.89,2 6,2M15,18V16H6V18H15M18,14V12H6V14H18Z" />
    </svg>
  );
}