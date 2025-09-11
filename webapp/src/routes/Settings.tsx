import { useEffect, useState } from 'react'
import { GatewayConfig, getConfig, updateConfig } from '../lib/api'

type Tab = 'executables' | 'gemini_cli' | 'projects'

function Input({ label, value, onChange, placeholder }: { label: string, value: string | number, onChange: (v: string) => void, placeholder?: string }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      <input className="input" value={String(value ?? '')} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        />
    </label>
  )
}

export default function Settings() {
  const [tab, setTab] = useState<Tab>('executables')
  const [cfg, setCfg] = useState<GatewayConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getConfig().then(setCfg).catch(e => setError(String(e)))
  }, [])

  const mask = (s: string) => (s && s.startsWith('****') ? s : s)

  const onSave = async () => {
    if (!cfg) return
    setSaving(true); setError(null); setSaved(false)
    try {
      const next = await updateConfig(cfg)
      setCfg(next)
      setSaved(true)
    } catch (e: any) {
      setError(String(e?.message ?? e))
    } finally {
      setSaving(false)
      setTimeout(() => setSaved(false), 2000)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button className={`btn ${tab==='executables' ? 'btn-primary' : ''}`} onClick={() => setTab('executables')}>Executables</button>
        <button className={`btn ${tab==='gemini_cli' ? 'btn-primary' : ''}`} onClick={() => setTab('gemini_cli')}>Gemini CLI</button>
        <button className={`btn ${tab==='projects' ? 'btn-primary' : ''}`} onClick={() => setTab('projects')}>Projects</button>
      </div>

      {!cfg && !error && <div className="text-sm">Loading...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      {cfg && tab==='executables' && (
        <div className="card space-y-3">
          <Input label="Unity.exe" value={cfg.executables.unityExecutablePath}
                 onChange={v => setCfg({ ...cfg, executables: { ...cfg.executables, unityExecutablePath: v } })}
                 placeholder="C:\\Program Files\\Unity\\...\\Unity.exe" />
          <Input label="Blender.exe" value={cfg.executables.blenderExecutablePath}
                 onChange={v => setCfg({ ...cfg, executables: { ...cfg.executables, blenderExecutablePath: v } })}
                 placeholder="C:\\Program Files\\Blender Foundation\\...\\blender.exe" />
          <Input label="Unity Project Root" value={cfg.executables.unityProjectRoot}
                 onChange={v => setCfg({ ...cfg, executables: { ...cfg.executables, unityProjectRoot: v } })}
                 placeholder="projects" />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Unity Bridge Port" value={cfg.bridges.unityBridgePort}
                   onChange={v => setCfg({ ...cfg, bridges: { ...cfg.bridges, unityBridgePort: Number(v)||0 } })}
                   placeholder="8001" />
            <Input label="Blender Bridge Port" value={cfg.bridges.blenderBridgePort}
                   onChange={v => setCfg({ ...cfg, bridges: { ...cfg.bridges, blenderBridgePort: Number(v)||0 } })}
                   placeholder="8002" />
          </div>
        </div>
      )}

      {cfg && tab==='gemini_cli' && (
        <div className="card space-y-3">
          <Input label="Gemini CLI Command"
                 value={cfg.providers?.geminiCli?.command || ''}
                 onChange={v => setCfg({ ...cfg, providers: { ...cfg.providers, geminiCli: { ...(cfg.providers?.geminiCli||{}), command: v } } as any })}
                 placeholder="gemini o ruta absoluta a tu wrapper" />
          <div className="text-xs text-muted-foreground">Puedes indicar un ejecutable en PATH (p.ej. "gemini") o una ruta absoluta a tu wrapper/script.</div>
        </div>
      )}

      {cfg && tab==='projects' && (
        <div className="card space-y-3">
          <Input label="Projects Root" value={cfg.projects.root}
                 onChange={v => setCfg({ ...cfg, projects: { root: v } })}
                 placeholder="projects" />
        </div>
      )}

      <div className="flex items-center gap-2">
        <button className="btn btn-primary" onClick={onSave} disabled={saving || !cfg}>Save</button>
        {saving && <span className="text-sm">Saving...</span>}
        {saved && <span className="text-sm text-green-600">Saved</span>}
      </div>

      <div className="text-xs text-muted-foreground">Gateway URL y API key siguen en `.env` del frontend.</div>
    </div>
  )
}
