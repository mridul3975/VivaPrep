export interface DefenseResult {
  score: number | null; passed: boolean
  criteria: { id: string; question: string; status: 'met' | 'partial' | 'missed' | 'uncertain'; explanation: string; evidence: { version: string; line_start: number; line_end: number; quote: string }[] }[]
}

export default function DebugDefenseResult({ result, current }: { result: DefenseResult; current: boolean }) {
  return <>
    <div className="section-heading"><h3>Viva feedback</h3><span>{current ? result.score === null ? 'Inconclusive' : `${result.score} / 100` : 'Previous review'}</span></div>
    {!current && <p role="status">Your repair or answers changed. Check the repair and submit the viva again for current feedback.</p>}
    <p className="field-note">AI assessment of your reasoning, separate from the solution score. Code citations are copied from this exercise. This review does not run your proposed input.</p>
    {result.criteria.map(item => <article className="debug-viva-criterion" key={item.id}>
      <h4>{item.question}</h4><p><strong>{({ met: 'Understood', partial: 'Partly explained', missed: 'Needs work', uncertain: 'Not enough evidence' })[item.status]}</strong> · {item.explanation}</p>
      <details><summary>Code evidence</summary>{item.evidence.map((cite, index) => <div key={index}><p>{({ broken: 'Broken code', reference: 'Uploaded source', repair: 'Your reviewed repair' })[cite.version] ?? cite.version} · excerpt lines {cite.line_start}–{cite.line_end}</p><pre>{cite.quote}</pre></div>)}</details>
    </article>)}
  </>
}
