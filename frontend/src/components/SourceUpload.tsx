import { useEffect, useState } from 'react'

interface Snippet {
  id: string
  path: string
  content: string[]
  citation_type: 'lines' | 'page'
  start_line: number | null
  end_line: number | null
  page: number | null
}

export interface SourceDocument {
  source_id: string
  filename: string
  kind: 'text' | 'pdf'
  page_count: number | null
  line_count: number | null
  snippet_count: number
  snippets: Snippet[]
  warnings: string[]
}

function isDocument(value: unknown): value is SourceDocument {
  if (!value || typeof value !== 'object') return false
  const source = value as SourceDocument
  return typeof source.source_id === 'string' && !!source.source_id
    && typeof source.filename === 'string' && ['text', 'pdf'].includes(source.kind)
    && Array.isArray(source.warnings) && source.warnings.every((warning) => typeof warning === 'string')
    && Array.isArray(source.snippets) && source.snippets.length > 0
    && source.snippet_count === source.snippets.length
    && source.snippets.every((snippet) => snippet && typeof snippet.id === 'string'
      && Array.isArray(snippet.content) && snippet.content.every((line) => typeof line === 'string')
      && (snippet.citation_type === 'page' ? Number.isInteger(snippet.page)
        : snippet.citation_type === 'lines' && Number.isInteger(snippet.start_line) && Number.isInteger(snippet.end_line)))
}

interface Props {
  disabled: boolean
  onBusyChange: (busy: boolean) => void
  onSourceChange: (source: SourceDocument | null) => void
}

export default function SourceUpload({ disabled, onBusyChange, onSourceChange }: Props) {
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    async function restore() {
      try {
        const response = await fetch('/sources/current', { signal: controller.signal })
        if (response.status === 204) return
        const result = await response.json()
        if (!response.ok) throw new Error(result?.error ?? 'Could not restore the upload. Upload your file again.')
        if (!isDocument(result)) throw new Error('Could not restore the upload. Upload your file again.')
        if (active) {
          setSource(result)
          onSourceChange(result)
        }
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : 'Upload your file again.')
      } finally {
        if (active) {
          setLoading(false)
          onBusyChange(false)
        }
      }
    }
    void restore()
    return () => { active = false; controller.abort() }
  }, [onBusyChange, onSourceChange])

  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file || disabled || loading) return
    setError('')
    setNotice('')
    const pdf = file.name.toLowerCase().endsWith('.pdf')
    const limit = pdf ? 5 * 1024 * 1024 : 256 * 1024
    if (!file.size || file.size > limit) {
      setError('Choose a non-empty file: PDFs up to 5 MiB, or source/text files up to 256 KiB.')
      return
    }
    setLoading(true)
    onBusyChange(true)
    try {
      const form = new FormData()
      form.append('source_file', file)
      const response = await fetch('/sources', { method: 'POST', body: form, signal: AbortSignal.timeout(25_000) })
      const result = await response.json()
      if (!response.ok) throw new Error(typeof result?.error === 'string' ? result.error : 'The upload could not be processed.')
      if (!isDocument(result)) throw new Error('The server returned an invalid evidence preview. Please retry.')
      setSource(result)
      onSourceChange(result)
      setSelected(0)
      setNotice('File processed. Review the extracted evidence below.')
    } catch (error) {
      setError(error instanceof Error && error.name === 'TimeoutError'
        ? 'Processing took too long. Try a smaller file.'
        : error instanceof TypeError ? 'Could not reach the upload service. Please retry.'
        : error instanceof Error ? error.message : 'The upload failed. Please retry.')
    } finally {
      setLoading(false)
      onBusyChange(false)
    }
  }

  async function removeUpload() {
    if (!source || disabled || loading) return
    setLoading(true)
    onBusyChange(true)
    setError('')
    try {
      const response = await fetch(`/sources/${source.source_id}`, { method: 'DELETE' })
      if (!response.ok && response.status !== 404) throw new Error('Could not remove the upload. Please retry.')
      setSource(null)
      onSourceChange(null)
      setNotice('Upload removed.')
    } catch {
      setError('Could not remove the upload. Please retry.')
    } finally {
      setLoading(false)
      onBusyChange(false)
    }
  }

  const snippet = source?.snippets[selected]
  const buttonClass = 'px-3 py-2 rounded border border-[#30363d] text-sm disabled:opacity-50 disabled:cursor-not-allowed'
  return (
    <section className="mb-8 p-5 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }} aria-labelledby="material-heading">
      <h2 id="material-heading" className="text-base font-semibold mb-3">Upload study material</h2>
      <label htmlFor="source-file" className="block text-sm mb-2">Source/text file or PDF</label>
      <input id="source-file" type="file" onChange={upload} disabled={disabled || loading}
        accept=".pdf,.py,.js,.jsx,.ts,.tsx,.md,.txt,.java,.c,.cpp,.h,.css,.html,.json,.yaml,.yml"
        aria-describedby="source-help"
        className="block w-full min-w-0 text-sm file:mr-3 file:rounded file:border file:border-[#30363d] file:bg-[#161b22] file:px-3 file:py-2 file:text-[#e6edf3] disabled:opacity-60" />
      <p id="source-help" className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>
        One UTF-8 source/text file up to 256 KiB, or a searchable PDF up to 5 MiB and 20 pages.
        Scanned-only and password-protected PDFs are not supported.
        Uploads are scoped to this browser session, kept in server memory for up to one hour,
        and cleared on restart. Uploading a new file replaces your previous upload.
      </p>
      <p role="status" className="mt-3 text-sm" style={{ color: 'var(--muted)' }}>
        {loading ? 'Processing your upload…' : notice}
      </p>
      {error && <p role="alert" className="mt-3 text-sm" style={{ color: 'var(--warn)' }}>{error}</p>}
      {source && snippet && (
        <div className="mt-4">
          <p className="text-sm">
            <strong className="break-all">{source.filename}</strong>
            <span className="block mt-1" style={{ color: 'var(--muted)' }}>
              {source.kind === 'pdf' ? `${source.page_count} pages` : `${source.line_count} lines`} · {source.snippet_count} snippets
            </span>
          </p>
          <div className="flex flex-wrap items-center gap-3 mt-3 mb-3">
            <button type="button" className={buttonClass} disabled={loading || selected === 0} onClick={() => setSelected(selected - 1)}>Previous snippet</button>
            <span className="text-xs">Snippet {selected + 1} of {source.snippet_count}</span>
            <button type="button" className={buttonClass} disabled={loading || selected + 1 === source.snippet_count} onClick={() => setSelected(selected + 1)}>Next snippet</button>
          </div>
          <p className="text-xs mb-2" style={{ color: 'var(--muted)' }}>
            {snippet.citation_type === 'page' ? `Page ${snippet.page} — extracted text` : `Lines ${snippet.start_line}–${snippet.end_line}`}
          </p>
          <div className="overflow-x-auto max-h-72 p-3 rounded text-xs font-mono" style={{ background: 'var(--bg)' }}>
            {snippet.content.map((line, index) => (
              <div key={index} className="flex w-max min-w-full leading-5">
                {snippet.citation_type === 'lines' && <span className="w-10 shrink-0 pr-3 text-right select-none" style={{ color: 'var(--muted)' }}>{(snippet.start_line ?? 1) + index}</span>}
                <span className="whitespace-pre">{line || ' '}</span>
              </div>
            ))}
          </div>
          {source.warnings.map((warning) => <p key={warning} className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>{warning}</p>)}
          {source.kind === 'pdf' && <p className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>Check the extracted text against the original PDF, especially tables, equations, and columns.</p>}
          <button type="button" className={`${buttonClass} mt-3`} disabled={disabled || loading} onClick={removeUpload}>Remove upload</button>
        </div>
      )}
      <p className="mt-4 text-xs" style={{ color: 'var(--muted)' }}>
        {source ? 'Generate an AI question set from this file. Reference answers stay hidden until you submit. Replacing or removing the file clears the current practice set.'
          : 'Upload your material to generate questions, reference answers, and a grading rubric.'}
      </p>
    </section>
  )
}
