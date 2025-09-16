import { useEffect, useMemo, useRef, useState } from 'react'
import { apiPost } from '../lib/api'
import { useAppStore } from '@/store/appStore'
import { wsClient } from '@/lib/ws'

type CheckItem = { name: string; installed: boolean; version?: string }

export default function Dependencies() {
  const { project_id } = useAppStore()
  const [venvPath, setVenvPath] = useState('venvs/agp')
  const [requirementsPath, setRequirementsPath] = useState('mcp_unity_bridge/requirements.txt')
  const [packages, setPackages] = useState<string>('')
  const [check, setCheck] = useState<CheckItem[] | null>(null)
  const [installing, setInstalling] = useState(false)
  const [creating, setCreating] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const logsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!project_id) return
    const unsub = wsClient.subscribe({ project_id, onMessage: (data) => {
      const ev = data as any
      if (ev?.type === 'log' && ev?.payload?.source === 'deps') {
        setLogs(prev => [...prev, `[${ev.payload.step}] ${ev.payload.line}`].slice(-500))
      }
    }})
    return () => unsub()
  }, [project_id])

  useEffect(() => {
    logsRef.current?.scrollTo({ top: logsRef.current.scrollHeight })
  }, [logs])

  const onCreateVenv = async () => {
    setCreating(true)
    try {
      await apiPost('/api/v1/venv/create', { path: venvPath, project_id })
    } catch (e) { console.error(e) }
    finally { setCreating(false) }
  }

  const onInstallReqs = async () => {
    setInstalling(true)
    try {
      await apiPost('/api/v1/deps/install', { venvPath, requirementsPath, project_id })
    } catch (e) { console.error(e) }
    finally { setInstalling(false) }
  }

  const onInstallPkgs = async () => {
    const list = packages.split(/[\s,]+/).filter(Boolean)
    if (!list.length) return
    setInstalling(true)
    try {
      await apiPost('/api/v1/deps/install', { venvPath, packages: list, project_id })
    } catch (e) { console.error(e) }
    finally { setInstalling(false) }
  }

  const onCheck = async () => {
    const list = packages.split(/[\s,]+/).filter(Boolean)
    if (!list.length) return setCheck([])
    try {
      const res = await apiPost<CheckItem[]>('/api/v1/deps/check', { venvPath, packages: list })
      setCheck(res)
    } catch (e) { console.error(e); setCheck([]) }
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Venv Path</span>
            <input className="input" value={venvPath} onChange={e => setVenvPath(e.target.value)} placeholder="venvs/agp or projects/<id>/.venv" />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">requirements.txt</span>
            <input className="input" value={requirementsPath} onChange={e => setRequirementsPath(e.target.value)} placeholder="mcp_unity_bridge/requirements.txt" />
          </label>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-primary" onClick={onCreateVenv} disabled={creating}>{creating ? <span className="spinner"/> : null} Create venv</button>
          <button className="btn" onClick={onInstallReqs} disabled={installing}>{installing ? <span className="spinner"/> : null} Install from requirements</button>
        </div>
      </div>

      <div className="card space-y-3">
        <label className="block space-y-1">
          <span className="text-sm font-medium">Packages (comma or space separated)</span>
          <input className="input" value={packages} onChange={e => setPackages(e.target.value)} placeholder="openai websockets uvicorn" />
        </label>
        <div className="flex gap-2">
          <button className="btn" onClick={onCheck}>Check installed</button>
          <button className="btn btn-primary" onClick={onInstallPkgs} disabled={installing}>{installing ? <span className="spinner"/> : null} Install selected</button>
        </div>
        {check && (
          <div className="text-sm">
            {check.map(c => (
              <div key={c.name} className="flex justify-between border-b py-1">
                <span>{c.name}</span>
                <span className={c.installed ? 'text-green-600' : 'text-red-600'}>
                  {c.installed ? `Installed (${c.version ?? 'unknown'})` : 'Missing'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="text-sm font-semibold mb-2">Logs</div>
        <div ref={logsRef} className="h-64 overflow-auto text-xs font-mono whitespace-pre">
          {logs.length ? logs.map((l, i) => (<div key={i}>{l}</div>)) : <div className="text-sm text-muted-foreground"><span className="spinner"/> Waiting…</div>}
        </div>
      </div>
    </div>
  )
}
