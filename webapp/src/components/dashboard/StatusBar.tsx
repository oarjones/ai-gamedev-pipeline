import React from 'react';
import { useAppStore } from '@/store/appStore';

export default function StatusBar() {
  const project_id = useAppStore((s) => s.project_id);

  return (
    <div className="h-8 bg-gray-800 text-gray-300 flex items-center justify-between px-6 text-sm">
      {/* Left side - Project info */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <StatusDot className="text-green-400" />
          <span>Sistema Activo</span>
        </div>
        {project_id && (
          <div className="flex items-center gap-2">
            <ProjectIcon className="w-4 h-4" />
            <span>Proyecto: {project_id}</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <ConnectionIcon className="w-4 h-4 text-blue-400" />
          <span>Gateway Conectado</span>
        </div>
      </div>

      {/* Center - Current activity */}
      <div className="flex items-center gap-2">
        <ActivityIcon className="w-4 h-4 text-yellow-400" />
        <span>
          {project_id ? 'Listo para trabajar' : 'Esperando selección de proyecto'}
        </span>
      </div>

      {/* Right side - System info */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <ClockIcon className="w-4 h-4" />
          <span>{new Date().toLocaleTimeString()}</span>
        </div>
        <div className="flex items-center gap-2">
          <UserIcon className="w-4 h-4" />
          <span>Developer</span>
        </div>
      </div>
    </div>
  );
}

// Icons
function StatusDot({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 8 8" fill="currentColor">
      <circle cx="4" cy="4" r="3" />
    </svg>
  );
}

function ProjectIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M9,3V4H4V6H5V19A2,2 0 0,0 7,21H17A2,2 0 0,0 19,19V6H20V4H15V3H9M7,6H17V19H7V6M9,8V17H11V8H9M13,8V17H15V8H13Z" />
    </svg>
  );
}

function ConnectionIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M15,9H9V10.5H15V9M13,16.5H18V15H13V16.5M13,12.5H18V11H13V12.5M3,5V19A2,2 0 0,0 5,21H11V19.5L15.5,15H5V5H19V9H21V5A2,2 0 0,0 19,3H5A2,2 0 0,0 3,5M24,13.47L22.53,12L20.5,14.03L18.47,12L17,13.47L19.03,15.5L17,17.53L18.47,19L20.5,16.97L22.53,19L24,17.53L21.97,15.5L24,13.47Z" />
    </svg>
  );
}

function ActivityIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M23,11.01L18,8V5L11,2L4,5V11L1,13L11,22L21,13V11.01M11,6.3L15.75,8.5L11,10.7L6.25,8.5L11,6.3M5,7.05L10,9.5V14.5L5,12.05V7.05M13,14.5V9.5L18,7.05V12.05L13,14.5Z" />
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

function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,4A4,4 0 0,1 16,8A4,4 0 0,1 12,12A4,4 0 0,1 8,8A4,4 0 0,1 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z" />
    </svg>
  );
}