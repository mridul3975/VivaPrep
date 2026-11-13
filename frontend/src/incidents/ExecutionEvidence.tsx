import { useState } from 'react'
import type { Execution } from './types'

export default function ExecutionEvidence({ evidence, title }: { evidence: Execution; title: string }) {
  const [index, setIndex] = useState(0)
  const current = evidence.experiments[index] ?? evidence.experiments[0]
  if (!current) return null
  return <section className="incident-evidence" aria-label={title}>
    <div className="incident-section-heading"><h2>{title}</h2><span>{evidence.passed === true ? 'All checks passed' : evidence.passed === false ? 'A check failed' : 'Investigation · unscored'}</span></div>
    {evidence.experiments.length > 1 && <label className="incident-test-picker">Experiment<select value={index} onChange={event => setIndex(Number(event.target.value))}>{evidence.experiments.map((row, i) => <option key={i} value={i}>{row.name} · {row.passed ? 'passed' : 'failed'}</option>)}</select></label>}
    <p>{current.name} · {current.concurrent ? 'Requests started together' : 'Requests sent sequentially'} · fresh application data</p>
    {current.error && <p className="inline-error">{current.error}</p>}
    <ol className="incident-requests">{current.responses.map((response, i) => <li key={i}><div><code>{response.method} {response.path}</code><strong>{response.status || 'No response'}</strong><span>{response.milliseconds ?? 0} ms</span></div><details><summary>Request and response {i + 1}</summary><pre>{JSON.stringify(response.body, null, 2)}</pre><pre>{response.error || response.response}</pre></details></li>)}</ol>
    {Object.keys(current.database_after).length > 0 && <details open><summary>Database before and after</summary><div className="incident-db"><div><h3>Before requests</h3><pre>{JSON.stringify(current.database_before, null, 2)}</pre></div><div><h3>After requests</h3><pre>{JSON.stringify(current.database_after, null, 2)}</pre></div></div></details>}
    <details><summary>Executed source lines · {current.trace.length} observations</summary><p className="field-note">Thread IDs distinguish overlapping request handlers. Quotes belong to this execution snapshot.</p><ol className="incident-trace">{current.trace.map((point, i) => <li key={i}><code>{point.path}:{point.line} · thread {point.thread}</code><pre>{point.source}</pre></li>)}</ol></details>
    <details><summary>Application logs</summary><pre>{current.logs || 'No additional log output.'}</pre></details>
    <p className="field-note">These are execution observations from finite checks, not proof of correctness for every input.</p>
  </section>
}
