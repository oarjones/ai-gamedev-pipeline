import React, { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { CreateProjectWizard } from '../CreateProjectWizard';
import { useQuery } from '@tanstack/react-query';
import { listProjects, selectProject, deleteProject, type Project } from '@/lib/api';

interface ProjectSidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  activeWorkspace: string;
  onWorkspaceChange: (workspace: 'chat' | 'consensus' | 'execution' | 'context') => void;
}

export default function ProjectSidebar({
  collapsed,
  onToggleCollapse,
  activeWorkspace,
  onWorkspaceChange
}: ProjectSidebarProps) {
  const project_id = useAppStore((s) => s.project_id);
  const setProjectId = useAppStore((s) => s.setProjectId);
  const pushToast = useAppStore((s) => s.pushToast);
  const [showCreateWizard, setShowCreateWizard] = useState(false);

  const { data: projects = [], refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects
  });

  const activeProject = projects.find(p => p.id === project_id);

  const handleSelectProject = async (id: string) => {
    try {
      await selectProject(id);
      setProjectId(id);
      pushToast('Proyecto seleccionado');
    } catch (error: any) {
      pushToast(`Error: ${error.message}`);
    }
  };

  const handleDeleteProject = async (id: string, name: string) => {
    const confirmed = window.confirm(
      `¿Estás seguro de que quieres eliminar el proyecto "${name}"?\n\nEsta acción no se puede deshacer y eliminará todos los datos del proyecto.`
    );

    if (!confirmed) return;

    try {
      await deleteProject(id, true); // true = purge data

      // If we deleted the active project, clear it
      if (project_id === id) {
        setProjectId('');
      }

      // Refresh the projects list
      refetch();
      pushToast(`Proyecto "${name}" eliminado correctamente`);
    } catch (error: any) {
      pushToast(`Error al eliminar proyecto: ${error.message}`);
    }
  };

  const workspaces = [
    {
      id: 'chat' as const,
      name: 'Chat & AI',
      icon: ChatIcon,
      color: 'blue',
      description: 'Conversación con IA'
    },
    {
      id: 'consensus' as const,
      name: 'Consenso',
      icon: ConsensusIcon,
      color: 'purple',
      description: 'Revisar y aprobar planes'
    },
    {
      id: 'execution' as const,
      name: 'Ejecución',
      icon: ExecutionIcon,
      color: 'green',
      description: 'Desarrollar tareas'
    },
    {
      id: 'context' as const,
      name: 'Contexto',
      icon: ContextIcon,
      color: 'orange',
      description: 'Estado del proyecto'
    }
  ];

  if (collapsed) {
    return (
      <div className="w-16 bg-white border-r border-gray-200 flex flex-col">
        <button
          onClick={onToggleCollapse}
          className="p-4 hover:bg-gray-50 border-b border-gray-200"
        >
          <MenuIcon className="w-6 h-6 text-gray-600" />
        </button>

        {workspaces.map((workspace) => {
          const Icon = workspace.icon;
          const isActive = activeWorkspace === workspace.id;
          return (
            <button
              key={workspace.id}
              onClick={() => onWorkspaceChange(workspace.id)}
              className={`p-4 hover:bg-gray-50 border-b border-gray-100 transition-colors ${
                isActive ? `bg-${workspace.color}-50 border-${workspace.color}-200` : ''
              }`}
              title={workspace.name}
            >
              <Icon className={`w-6 h-6 ${
                isActive ? `text-${workspace.color}-600` : 'text-gray-500'
              }`} />
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <>
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Workspace</h2>
          <button
            onClick={onToggleCollapse}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <MenuIcon className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Project Section */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-700">Proyecto</h3>
            <button
              onClick={() => setShowCreateWizard(true)}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1"
            >
              <PlusIcon className="w-3 h-3" />
              Nuevo
            </button>
          </div>

          {activeProject ? (
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <ProjectActiveIcon className="w-4 h-4 text-blue-600" />
                  <span className="font-medium text-blue-900 text-sm">{activeProject.name}</span>
                </div>
                <button
                  onClick={() => handleDeleteProject(activeProject.id, activeProject.name)}
                  className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                  title="Eliminar proyecto"
                >
                  <DeleteIcon className="w-4 h-4" />
                </button>
              </div>
              <p className="text-xs text-blue-700">{activeProject.description || 'Sin descripción'}</p>
              <div className="mt-2 flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <StatusDot className="text-green-500" />
                  <span className="text-xs text-blue-600">Activo</span>
                </div>
                <div className="text-xs text-gray-500">
                  ID: {activeProject.id}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-center">
              <ProjectInactiveIcon className="w-8 h-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600 mb-2">No hay proyecto seleccionado</p>
              <button
                onClick={() => setShowCreateWizard(true)}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                Crear nuevo proyecto
              </button>
            </div>
          )}

          {/* Project List */}
          {projects.length > 0 && (
            <div className="mt-3">
              <h4 className="text-xs font-medium text-gray-500 mb-2">Cambiar proyecto</h4>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {projects
                  .filter(p => p.id !== project_id)
                  .slice(0, 3)
                  .map((project) => (
                    <div key={project.id} className="flex items-center gap-1">
                      <button
                        onClick={() => handleSelectProject(project.id)}
                        className="flex-1 text-left p-2 text-xs text-gray-600 hover:bg-gray-50 rounded transition-colors"
                      >
                        {project.name}
                      </button>
                      <button
                        onClick={() => handleDeleteProject(project.id, project.name)}
                        className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="Eliminar proyecto"
                      >
                        <DeleteIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        {/* Workspace Tabs */}
        <div className="flex-1 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Espacios de Trabajo</h3>
          <div className="space-y-2">
            {workspaces.map((workspace) => {
              const Icon = workspace.icon;
              const isActive = activeWorkspace === workspace.id;
              const colorClasses = {
                blue: isActive ? 'bg-blue-50 border-blue-200 text-blue-700' : 'hover:bg-blue-50',
                purple: isActive ? 'bg-purple-50 border-purple-200 text-purple-700' : 'hover:bg-purple-50',
                green: isActive ? 'bg-green-50 border-green-200 text-green-700' : 'hover:bg-green-50',
                orange: isActive ? 'bg-orange-50 border-orange-200 text-orange-700' : 'hover:bg-orange-50'
              };

              return (
                <button
                  key={workspace.id}
                  onClick={() => onWorkspaceChange(workspace.id)}
                  disabled={!project_id && workspace.id !== 'chat'}
                  className={`w-full p-3 rounded-lg border transition-all text-left ${
                    !project_id && workspace.id !== 'chat'
                      ? 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed'
                      : colorClasses[workspace.color]
                  } ${isActive ? 'shadow-sm' : ''}`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-5 h-5 ${
                      !project_id && workspace.id !== 'chat'
                        ? 'text-gray-400'
                        : isActive
                          ? `text-${workspace.color}-600`
                          : `text-${workspace.color}-500`
                    }`} />
                    <div className="flex-1">
                      <div className="font-medium text-sm">{workspace.name}</div>
                      <div className={`text-xs ${
                        !project_id && workspace.id !== 'chat'
                          ? 'text-gray-400'
                          : isActive
                            ? `text-${workspace.color}-600`
                            : 'text-gray-500'
                      }`}>
                        {workspace.description}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="p-4 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Acciones Rápidas</h3>
          <div className="space-y-2">
            <button className="w-full p-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg text-left flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" />
              Configuración
            </button>
            <button className="w-full p-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg text-left flex items-center gap-2">
              <LogsIcon className="w-4 h-4" />
              Ver Logs
            </button>
          </div>
        </div>
      </div>

      {showCreateWizard && (
        <CreateProjectWizard onClose={() => {
          setShowCreateWizard(false);
          refetch();
        }} />
      )}
    </>
  );
}

// Icons
function MenuIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z" />
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

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z" />
    </svg>
  );
}

function ProjectActiveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M11,16.5L18,9.5L16.59,8.09L11,13.67L7.91,10.59L6.5,12L11,16.5Z" />
    </svg>
  );
}

function ProjectInactiveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M9,3V4H4V6H5V19A2,2 0 0,0 7,21H17A2,2 0 0,0 19,19V6H20V4H15V3H9M7,6H17V19H7V6M9,8V17H11V8H9M13,8V17H15V8H13Z" />
    </svg>
  );
}

function StatusDot({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 8 8" fill="currentColor">
      <circle cx="4" cy="4" r="3" />
    </svg>
  );
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.22,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.22,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.68 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z" />
    </svg>
  );
}

function LogsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M13,9H18.5L13,3.5V9M6,2H14L20,8V20A2,2 0 0,1 18,22H6C4.89,22 4,21.1 4,20V4C4,2.89 4.89,2 6,2M8,12V14H16V12H8M8,16V18H13V16H8Z" />
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