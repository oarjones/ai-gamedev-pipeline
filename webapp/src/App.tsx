import { Outlet, useLocation } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'

export default function App() {
  const location = useLocation()

  // For the new dashboard, render directly without wrapper
  if (location.pathname === '/') {
    return <Outlet />
  }

  // For other routes, use the original layout
  const project_id = useAppStore(s => s.project_id)
  const hasProject = !!project_id
  const pushToast = useAppStore(s => s.pushToast)
  const onDisabledClick = (e: React.MouseEvent, label: string) => {
    e.preventDefault()
    pushToast(`Selecciona un proyecto para abrir "${label}"`)
  }
  const consensusHref = hasProject ? `/projects/${project_id}/consensus` : '/consensus'
  const contextHref = hasProject ? `/projects/${project_id}/context` : '/context'
  const isConsensus = location.pathname.includes('/consensus')
  const isContext = location.pathname.includes('/context')

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b sticky top-0 z-10 bg-background/80 backdrop-blur">
        <div className="container flex items-center justify-between py-3">
          <h1 className="font-semibold flex items-center gap-2">
            <LogoIcon /> AI GameDev Dashboard
          </h1>
          <nav className="flex gap-1 text-sm">
            <a className={linkCls(false)} href="/">New Dashboard</a>
            <a className={linkCls(location.pathname === '/old-dashboard')} href="/old-dashboard">Old Dashboard</a>
            <a className={linkCls(location.pathname.startsWith('/logs'))} href="/logs">Logs</a>
            <a className={linkCls(location.pathname.startsWith('/settings'))} href="/settings">Settings</a>
            <a className={linkCls(location.pathname.startsWith('/dependencies'))} href="/dependencies">Dependencies</a>
            {/* Project-scoped tabs: disable until a project is selected */}
            <a
              className={linkCls(location.pathname.startsWith('/sessions'), !hasProject)}
              href="/sessions"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Sessions')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Sessions' : 'Selecciona un proyecto primero'}
            >
              Sessions
            </a>
            <a
              className={linkCls(location.pathname.startsWith('/wizard'), !hasProject)}
              href="/wizard"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Wizard')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Wizard' : 'Selecciona un proyecto primero'}
            >
              Wizard
            </a>
            <a
              className={linkCls(location.pathname.startsWith('/tasks'), !hasProject)}
              href="/tasks"
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Tasks')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Tasks' : 'Selecciona un proyecto primero'}
            >
              Tasks
            </a>
            <a
              className={linkCls(isConsensus, !hasProject)}
              href={consensusHref}
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Consensus')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Consensus' : 'Selecciona un proyecto primero'}
            >
              Consensus
            </a>
            <a
              className={linkCls(isContext, !hasProject)}
              href={contextHref}
              onClick={hasProject ? undefined : (e) => onDisabledClick(e, 'Context')}
              aria-disabled={!hasProject}
              title={hasProject ? 'Context' : 'Selecciona un proyecto primero'}
            >
              Context
            </a>
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