import { useState } from 'react'
import { getHealth, runSelfTest } from '@/lib/api'
import { useAppStore } from '@/store/appStore'

export default function SelfTestPanel() {
  const projectId = useAppStore(s => s.projectId)
  const [loading, setLoading] = useState(false)
  const [health, setHealth] = useState<null | { ok: boolean, components: { name: string, running: boolean, endpoint_ok: boolean, detail: string }[] }>(null)
  const [report, setReport] = useState<null | { passed: boolean, steps: { name: string, ok: boolean, detail?: string }[] }>(null)

  const onHealth = async () => {
    setLoading(true)
    try { setHealth(await getHealth()) } catch (e) { console.error(e) } finally { setLoading(false) }
  }
  const onSelfTest = async () => {
    setLoading(true)
    try { setReport(await runSelfTest(projectId || undefined)) } catch (e) { console.error(e) } finally { setLoading(false) }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <button className="btn" onClick={onHealth} disabled={loading}>Check Health</button>
        <button className="btn btn-primary" onClick={onSelfTest} disabled={loading}>Run Self-Test</button>
      </div>
      {health && (
        <div className="text-sm">
          <div className={health.ok ? 'text-green-600' : 'text-red-600'}>Overall: {health.ok ? 'OK' : 'Issues detected'}</div>
          {health.components.map(c => (
            <div key={c.name} className="flex justify-between border-b py-1">
              <span>{c.name}</span>
              <span className={c.endpoint_ok ? 'text-green-600' : 'text-red-600'}>{c.running ? 'running' : 'stopped'} · {c.endpoint_ok ? 'endpoint ok' : 'endpoint fail'}</span>
            </div>
          ))}
        </div>
      )}
      {report && (
        <div className="text-sm">
          <div className={report.passed ? 'text-green-600' : 'text-red-600'}>Self-Test: {report.passed ? 'PASSED' : 'FAILED'}</div>
          {report.steps.map((s, i) => (
            <div key={i} className="flex justify-between border-b py-1">
              <span>{s.name}</span>
              <span className={s.ok ? 'text-green-600' : 'text-red-600'}>{s.ok ? 'ok' : 'fail'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

