import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAppStore } from '@/store/appStore' 

export default function App() {
  const loc = useLocation()
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
            <Link className={linkCls(loc.pathname.startsWith('/sessions'))} to="/sessions">Sessions</Link>
            <Link className={linkCls(loc.pathname.startsWith('/wizard'))} to="/wizard">Wizard</Link>
            <Link className={linkCls(loc.pathname.startsWith('/tasks'))} to="/tasks">Tasks</Link>
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

function linkCls(active: boolean) {
  return `px-3 py-1.5 rounded-md hover:bg-[hsl(var(--secondary))] ${active ? 'text-[hsl(var(--primary))] border-b-2 border-[hsl(var(--primary))]' : 'text-foreground/80'}`
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
