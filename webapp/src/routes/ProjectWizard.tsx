import { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiGet, apiPost } from '@/lib/api'

type Manifest = {
  version?: string
  pitch: string
  genre: string
  mechanics: string
  platform?: string
  target?: string
  visual_style: string
  references?: string
  constraints?: string
  kpis?: string
  milestones?: string
}

export default function ProjectWizard() {
  const projectId = useAppStore(s => s.projectId)
  const pushToast = useAppStore(s => s.pushToast)
  const [mf, setMf] = useState<Manifest>({ pitch: '', genre: '', mechanics: '', visual_style: '' })
  const [loading, setLoading] = useState(false)
  const [planText, setPlanText] = useState('')

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    apiGet(`/api/v1/projects/${projectId}/manifest`).then((d) => setMf({ ...mf, ...d })).catch(()=>{}).finally(()=>setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  async function saveManifest() {
    if (!projectId) { pushToast('Select a project first'); return }
    try {
      setLoading(true)
      await apiPost(`/api/v1/projects/${projectId}/manifest`, mf)
      pushToast('Manifest saved')
    } catch (e) {
      pushToast(String(e))
    } finally { setLoading(false) }
  }

  async function proposePlan() {
    if (!projectId) { pushToast('Select a project first'); return }
    try {
      setLoading(true)
      await apiPost(`/api/v1/projects/${projectId}/plan/propose`, {})
      pushToast('Plan proposal sent to agent (check Chat)')
    } catch (e) {
      pushToast(String(e))
    } finally { setLoading(false) }
  }

  async function savePlan() {
    if (!projectId) { pushToast('Select a project first'); return }
    try {
      setLoading(true)
      const plan = JSON.parse(planText)
      await apiPost(`/api/v1/projects/${projectId}/plan`, { plan })
      pushToast('Plan of record saved')
    } catch (e) {
      pushToast('Invalid JSON or save error: ' + String(e))
    } finally { setLoading(false) }
  }

  function set<K extends keyof Manifest>(k: K, v: string) {
    setMf(s => ({ ...s, [k]: v }))
  }

  if (!projectId) return <div className="card">Select a project to configure.</div>

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-6 card">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold flex items-center gap-2"><WandIcon /> Project Wizard</h2>
          {loading && <span className="spinner" aria-label="loading" />}
        </div>
        <div className="space-y-2 text-sm">
          <Field label="Pitch" value={mf.pitch} onChange={v=>set('pitch',v)} required />
          <Field label="Género" value={mf.genre} onChange={v=>set('genre',v)} required />
          <Field label="Mecánicas" value={mf.mechanics} onChange={v=>set('mechanics',v)} required textarea />
          <Field label="Plataforma" value={mf.platform ?? ''} onChange={v=>set('platform',v)} />
          <Field label="Target" value={mf.target ?? ''} onChange={v=>set('target',v)} />
          <Field label="Estilo visual" value={mf.visual_style} onChange={v=>set('visual_style',v)} required />
          <Field label="Referencias" value={mf.references ?? ''} onChange={v=>set('references',v)} />
          <Field label="Restricciones" value={mf.constraints ?? ''} onChange={v=>set('constraints',v)} />
          <Field label="KPIs" value={mf.kpis ?? ''} onChange={v=>set('kpis',v)} />
          <Field label="Milestones" value={mf.milestones ?? ''} onChange={v=>set('milestones',v)} />
        </div>
        <div className="mt-3 flex gap-2">
          <button className="btn btn-primary" onClick={saveManifest} disabled={loading}>
            {loading ? <span className="spinner"/> : null} Save Manifest
          </button>
          <button className="btn" onClick={proposePlan} disabled={loading}>
            {loading ? <span className="spinner"/> : null} Generate Plan (via Agent)
          </button>
        </div>
      </div>
      <div className="col-span-6 card">
        <h2 className="font-semibold mb-2">Plan of Record</h2>
        <p className="text-xs opacity-70 mb-2">Pega aquí el JSON propuesto por el agente (se guardará como YAML).</p>
        <textarea className="textarea h-80" value={planText} onChange={e=>setPlanText(e.target.value)} placeholder='{ "phases": [], "tasks": [], "risks": [], "deliverables": [] }' />
        <div className="mt-2"><button className="btn btn-primary" onClick={savePlan} disabled={loading}>
          {loading ? <span className="spinner"/> : null} Save Plan
        </button></div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, required=false, textarea=false }: { label: string, value: string, onChange: (v:string)=>void, required?: boolean, textarea?: boolean }) {
  return (
    <label className="block">
      <div className="text-xs opacity-70 mb-1">{label}{required && <span className="text-red-500"> *</span>}</div>
      {textarea ? (
        <textarea className="textarea" value={value} onChange={e=>onChange(e.target.value)} />
      ) : (
        <input className="input" value={value} onChange={e=>onChange(e.target.value)} />
      )}
    </label>
  )
}

function WandIcon(){
  return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M2 22l14-14 4 4-14 14H2v-4zM18.5 3l2.5 2.5-2 2L16.5 5l2-2z"/></svg>)
}
