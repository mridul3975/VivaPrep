import { useRef } from 'react'

// A display-only token layer; React escapes every token. The textarea owns editing.
function tokens(code: string) {
  return code.split(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\/\/[^\n]*|#[^\n]*|\b(?:def|return|class|function|const|let|var|if|else|for|while|import|from|async|await|True|False|None|true|false|null|throw|new|export)\b|\b\d+(?:\.\d+)?\b|@[\w.]+)/g).map((part, i) => {
    const kind = /^(\/\/|#)/.test(part) ? 'comment' : /^["'`]/.test(part) ? 'string' : /^\d/.test(part) ? 'number' : /^@/.test(part) ? 'decorator' : /^(def|return|class|function|const|let|var|if|else|for|while|import|from|async|await|True|False|None|true|false|null|throw|new|export)$/.test(part) ? 'keyword' : ''
    return <span key={i} className={kind ? `code-token-${kind}` : undefined}>{part}</span>
  })
}

export default function CodeEditor({ code, startLine, disabled, onChange }: { code: string; startLine: number; disabled: boolean; onChange: (code: string) => void }) {
  const highlight = useRef<HTMLPreElement>(null)
  const gutter = useRef<HTMLDivElement>(null)
  const lines = code.split('\n')
  return <div className="exercise-code-canvas" style={{ height: `${Math.min(18, Math.max(5, lines.length + 1)) * 24 + 32}px` }}>
    <div className="exercise-gutter" aria-hidden="true"><div ref={gutter}>{lines.map((_, i) => <div key={i}>{startLine + i}</div>)}</div></div>
    <div className="exercise-code-input">
      <pre ref={highlight} aria-hidden="true">{tokens(code)}{'\n'}</pre>
      <textarea aria-label="Challenge code" value={code} maxLength={12000} spellCheck={false} autoCapitalize="off" autoCorrect="off" disabled={disabled} onChange={event => onChange(event.target.value)} onScroll={event => {
        const { scrollTop, scrollLeft } = event.currentTarget
        if (highlight.current) highlight.current.style.transform = `translate(${-scrollLeft}px, ${-scrollTop}px)`
        if (gutter.current) gutter.current.style.transform = `translateY(${-scrollTop}px)`
      }} />
    </div>
  </div>
}
