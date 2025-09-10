import { Link, Outlet, useLocation } from 'react-router-dom'

export default function App() {
  const loc = useLocation()
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b sticky top-0 z-10 bg-background/80 backdrop-blur">
        <div className="container flex items-center justify-between py-3">
          <h1 className="font-semibold">AI GameDev Dashboard</h1>
          <nav className="flex gap-4 text-sm">
            <Link className={linkCls(loc.pathname === '/')} to="/">Dashboard</Link>
            <Link className={linkCls(loc.pathname.startsWith('/logs'))} to="/logs">Logs</Link>
            <Link className={linkCls(loc.pathname.startsWith('/settings'))} to="/settings">Settings</Link>
            <Link className={linkCls(loc.pathname.startsWith('/dependencies'))} to="/dependencies">Dependencies</Link>
          </nav>
        </div>
      </header>
      <main className="container py-4">
        <Outlet />
      </main>
    </div>
  )
}

function linkCls(active: boolean) {
  return `hover:underline ${active ? 'text-primary' : ''}`
}
