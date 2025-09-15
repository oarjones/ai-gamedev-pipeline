import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAppStore } from '@/store/appStore' 

export default function App() {
  const loc = useLocation()
  const projectId = useAppStore(s => s.projectId)
  const hasProject = !!projectId
  const pushToast = useAppStore(s => s.pushToast)
  const onDisabledClick = (e: React.MouseEvent, label: string) => {
    e.preventDefault()
    pushToast(`Selecciona un proyecto para abrir "${label}"`)
  }
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b sticky top-0 z-10 bg-background/80 backdrop-blur">
        <div className="container flex items-center justify-between py-3">
          <h1 className="font-semibold flex items-center gap-2">
            <LogoIcon /> AI GameDev Dashboard
          </h1>
          <nav className="flex gap-1 text-sm">
            <Link className={linkCls(loc.pathname === '/')} to="/">Dashboard</Link>
            <Link className={linkCls(loc.pathname.startsWith('/logs'))} to="/logs">Logs</Link>
            <Link className={linkCls(loc.pathname.startsWith('/settings'))} to="/settings">Settings</Link>
            <Link className={linkCls(loc.pathname.startsWith('/dependencies'))} to="/dependencies">Dependencies</Link>
            {/* Project-scoped tabs: disable until a project is selected */}
            <Link
              className={linkCls(loc.pathname.startsWith('/sessions'), !hasProject)}
              to="/sessions"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Sessions')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Sessions' : 'Selecciona un proyecto primero'}
            >
              Sessions
            </Link>
            <Link
              className={linkCls(loc.pathname.startsWith('/wizard'), !hasProject)}
              to="/wizard"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Wizard')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Wizard' : 'Selecciona un proyecto primero'}
            >
              Wizard
            </Link>
            <Link
              className={linkCls(loc.pathname.startsWith('/tasks'), !hasProject)}
              to="/tasks"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Tasks')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Tasks' : 'Selecciona un proyecto primero'}
            >
              Tasks
            </Link>
            <Link
              className={linkCls(loc.pathname.startsWith('/consensus'), !hasProject)}
              to="/consensus"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Consensus')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Consensus' : 'Selecciona un proyecto primero'}
            >
              Consensus
            </Link>
            <Link
              className={linkCls(loc.pathname.startsWith('/context'), !hasProject)}
              to="/context"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Context')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Context' : 'Selecciona un proyecto primero'}
            >
              Context
            </Link>
          </nav>
        </div>
      </header>
      <main className="container py-4">
        <Toasts />
        <Outlet />
      </main>
    </div>
  )
}

function linkCls(active: boolean, disabled = false) {
  const base = 'px-3 py-1.5 rounded-md'
  const state = active ? 'text-[hsl(var(--primary))] border-b-2 border-[hsl(var(--primary))]' : 'text-foreground/80'
  const hover = disabled ? 'cursor-not-allowed opacity-50 pointer-events-none' : 'hover:bg-[hsl(var(--secondary))]'
  return `${base} ${state} ${hover}`
}

function LogoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2l3 6 6 .9-4.5 4.1 1.1 6-5.6-3-5.6 3 1.1-6L3 8.9 9 8z" opacity=".9" />
    </svg>
  )
}

function Toasts() {
  const toasts = useAppStore(s => s.ui.toasts)
  const pop = useAppStore(s => s.popToast)
  return (
    <div className="fixed bottom-4 right-4 space-y-2 z-50">
      {toasts.map(t => (
        <div key={t.id} className="card shadow-lg flex items-center gap-2">
          <span>{t.message}</span>
          <button className="btn btn-ghost" onClick={() => pop(t.id)}>Dismiss</button>
        </div>
      ))}
    </div>
  )
}
