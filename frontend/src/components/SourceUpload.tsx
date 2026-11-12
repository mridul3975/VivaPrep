import { useEffect, useState, type ReactNode } from 'react'
import Icon from './Icon'
import UiloraEffect from './UiloraEffect'
import { useAuth } from '../auth/context'
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
  prepared_example?: string
  reused?: boolean
  saved_practice?: unknown
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
  return (
    typeof source.source_id === 'string' &&
    !!source.source_id &&
    typeof source.filename === 'string' &&
    ['text', 'pdf'].includes(source.kind) &&
    Array.isArray(source.warnings) &&
    source.warnings.every((warning) => typeof warning === 'string') &&
    Array.isArray(source.snippets) &&
    source.snippets.length > 0 &&
    source.snippet_count === source.snippets.length &&
    source.snippets.every(
      (snippet) =>
        snippet &&
        typeof snippet.id === 'string' &&
        Array.isArray(snippet.content) &&
        snippet.content.every((line) => typeof line === 'string') &&
        (snippet.citation_type === 'page'
          ? Number.isInteger(snippet.page)
          : snippet.citation_type === 'lines' &&
            Number.isInteger(snippet.start_line) &&
            Number.isInteger(snippet.end_line)),
    )
  )
}
interface Props {
  restoredSource?: SourceDocument | null
  beforeSourceChange?: () => Promise<void>
  disabled: boolean
  compact?: boolean
  embedded?: boolean
  practiceAction?: ReactNode
  onBusyChange: (busy: boolean) => void
  onSourceChange: (source: SourceDocument | null) => void
}
export default function SourceUpload({
  restoredSource,
  beforeSourceChange,
  disabled,
  compact = false,
  embedded = false,
  practiceAction,
  onBusyChange,
  onSourceChange,
}: Props) {
  const { apiFetch, storageMode } = useAuth()
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [dragging, setDragging] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [previousRestore, setPreviousRestore] = useState(restoredSource)
  if (restoredSource !== previousRestore && restoredSource !== undefined) {
    setPreviousRestore(restoredSource)
    setSource(restoredSource); setSelected(0); setError(''); setNotice(restoredSource ? 'Restored from history.' : 'Material closed.'); setLoading(false)
  }
  useEffect(() => {
    let active = true
    const controller = new AbortController()
    async function restore() {
      try {
        const response = await apiFetch('/sources/current', {
          signal: controller.signal,
        })
        if (response.status === 204) return
        const result = await response.json()
        if (!response.ok)
          throw new Error(
            result?.error ??
              'Could not restore the upload. Upload your file again.',
          )
        if (!isDocument(result))
          throw new Error(
            'Could not restore the upload. Upload your file again.',
          )
        if (active) {
          setSource(result)
          onSourceChange(result)
        }
      } catch (error) {
        if (active)
          setError(
            error instanceof Error ? error.message : 'Upload your file again.',
          )
      } finally {
        if (active) {
          setLoading(false)
          setRestoring(false)
          onBusyChange(false)
        }
      }
    }
    void restore()
    return () => {
      active = false
      controller.abort()
    }
  }, [apiFetch, onBusyChange, onSourceChange])
  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (file) await processFile(file)
  }
  async function processFile(file: File) {
    if (disabled || loading) return
    setError('')
    setNotice('')
    const pdf = file.name.toLowerCase().endsWith('.pdf')
    const limit = pdf ? 5 * 1024 * 1024 : 256 * 1024
    if (!file.size || file.size > limit) {
      setError(
        'Choose a non-empty file: PDFs up to 5 MiB, or source/text files up to 256 KiB.',
      )
      return
    }
    setLoading(true)
    onBusyChange(true)
    try {
      await beforeSourceChange?.()
      const form = new FormData()
      form.append('source_file', file)
      const response = await apiFetch('/sources', {
        method: 'POST',
        body: form,
        signal: AbortSignal.timeout(25_000),
      })
      const result = await response.json()
      if (!response.ok)
        throw new Error(
          typeof result?.error === 'string'
            ? result.error
            : 'The upload could not be processed.',
        )
      if (!isDocument(result))
        throw new Error(
          'The server returned an invalid evidence preview. Please retry.',
        )
      setSource(result)
      onSourceChange(result)
      setSelected(0)
      setNotice(result.reused ? 'Restored from history.' : 'File processed. Review the extracted evidence below.')
    } catch (error) {
      setError(
        error instanceof Error && error.name === 'TimeoutError'
          ? 'Processing took too long. Try a smaller file.'
          : error instanceof TypeError
            ? 'Could not reach the upload service. Please retry.'
            : error instanceof Error
              ? error.message
              : 'The upload failed. Please retry.',
      )
    } finally {
      setLoading(false)
      onBusyChange(false)
    }
  }
  async function chooseExample() {
    if (disabled || loading) return
    setLoading(true); onBusyChange(true); setError('')
    try {
      await beforeSourceChange?.()
      const response = await apiFetch('/sources/example', { method: 'POST' })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'Could not open the example.')
      if (!isDocument(result)) throw new Error('The example could not be read. Retry.')
      setSource(result); onSourceChange(result); setSelected(0); setNotice('Prepared Python example selected. Questions are free; AI feedback on your explanations uses 1 answer review per submission.')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not open the example.') }
    finally { setLoading(false); onBusyChange(false) }
  }
  async function removeUpload() {
    if (!source || disabled || loading) return
    setLoading(true)
    onBusyChange(true)
    setError('')
    try {
      await beforeSourceChange?.()
      const response = await apiFetch(storageMode === 'postgresql' ? `/sources/${source.source_id}/close` : `/sources/${source.source_id}`, {
        method: storageMode === 'postgresql' ? 'POST' : 'DELETE',
      })
      if (!response.ok && response.status !== 404)
        throw new Error('Could not remove the upload. Please retry.')
      setSource(null)
      onSourceChange(null)
      setNotice('Material closed. Saved practice remains in History.')
    } catch {
      setError('Could not remove the upload. Please retry.')
    } finally {
      setLoading(false)
      onBusyChange(false)
    }
  }
  const snippet = source?.snippets[selected]
  const sourceCounts = source
    ? `${source.kind === 'pdf' ? `${source.page_count} ${source.page_count === 1 ? 'page' : 'pages'}` : `${source.line_count} lines`} · ${source.snippet_count} ${source.snippet_count === 1 ? 'snippet' : 'snippets'}`
    : ''
  const accept =
    '.pdf,.py,.js,.jsx,.ts,.tsx,.md,.txt,.java,.c,.cpp,.h,.css,.html,.json,.yaml,.yml'
  const materialDetails = (
    <>
      {source && snippet && (
        <details className="source-preview">
          <summary>
            <span>
              <Icon name="book" size={16} />
              Preview extracted evidence
            </span>
            <Icon name="chevron" size={15} />
          </summary>
          <div className="preview-toolbar">
            <span>
              {snippet.citation_type === 'page'
                ? `Page ${snippet.page}`
                : `Lines ${snippet.start_line}–${snippet.end_line}`}
            </span>
            <div className="snippet-controls">
              <button
                type="button"
                className="icon-button"
                disabled={loading || selected === 0}
                onClick={() => setSelected(selected - 1)}
                aria-label="Previous snippet"
              >
                <Icon name="chevron" size={14} className="rotate-180" />
              </button>
              <span>
                {selected + 1} / {source.snippet_count}
              </span>
              <button
                type="button"
                className="icon-button"
                disabled={loading || selected + 1 === source.snippet_count}
                onClick={() => setSelected(selected + 1)}
                aria-label="Next snippet"
              >
                <Icon name="chevron" size={14} />
              </button>
            </div>
          </div>
          <div className="source-lines preview-lines">
            {snippet.content.map((line, index) => (
              <div key={index} className="source-line">
                {snippet.citation_type === 'lines' && (
                  <span className="line-number">
                    {(snippet.start_line ?? 1) + index}
                  </span>
                )}
                <span>{line || ' '}</span>
              </div>
            ))}
          </div>
          {source.warnings.map((warning) => (
            <p key={warning} className="preview-note">
              {warning}
            </p>
          ))}
          {source.kind === 'pdf' && (
            <p className="preview-note">
              Check tables, equations, and columns against the original PDF.
            </p>
          )}
        </details>
      )}
      <details className="file-requirements">
        <summary>
          File requirements & privacy
          <Icon name="info" size={13} />
        </summary>
        <p>
          One UTF-8 source/text file, or a searchable PDF with up to 20 pages.
          Scanned-only and password-protected PDFs are not supported. Your
          {storageMode === 'postgresql'
            ? 'material and submitted answers are saved to your account. Closing material keeps it in History. Permanent deletion is available there. '
            : 'upload is kept in this browser session for up to one hour and cleared on server restart. A new upload replaces the previous one. '}
          Selected excerpts are sent to Groq to generate and evaluate questions.
        </p>
      </details>
    </>
  )
  return (
    <section
      className={`material-panel ${compact ? 'material-panel-compact' : ''} ${embedded ? 'material-panel-embedded' : ''}`}
      aria-labelledby="material-heading"
    >
      {!embedded && <UiloraEffect variant="aurora" />}
      {!compact && !embedded && !source?.prepared_example && <div className="example-choice"><button type="button" className="button button-secondary" disabled={disabled || loading} onClick={() => { void chooseExample() }}>Use Python example<Icon name="code" size={16} /></button><p>A short prime checker with explanation questions. Questions and source checks are free; AI feedback uses a review allowance.</p></div>}
      {source?.prepared_example && <p className="example-label">Prepared Python example · No AI generation needed</p>}
      {!compact && !embedded && (
        <div className="material-heading">
          <h2 id="material-heading">Start with your material.</h2>
          <p>
            Notes, a guide, or the code you’re learning. <br />
            Make it the starting point.
          </p>
        </div>
      )}
      {(compact || embedded) && (
        <h2 id="material-heading" className="sr-only">
          Your study material
        </h2>
      )}
      {!source ? (
        <div
          className={`upload-zone ${dragging ? 'is-dragging' : ''} ${loading || disabled ? 'is-disabled' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
            if (!disabled && !loading) setDragging(true)
          }}
          onDragLeave={(event) => {
            if (
              !(event.relatedTarget instanceof Node) ||
              !event.currentTarget.contains(event.relatedTarget)
            )
              setDragging(false)
          }}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            if (disabled || loading) return
            if (event.dataTransfer.files.length !== 1) {
              setError('Choose one file at a time.')
              return
            }
            const file = event.dataTransfer.files[0]
            if (file) void processFile(file)
          }}
        >
          <Icon name="upload" size={30} />
          <strong>
            {restoring
              ? 'Getting your material ready…'
              : loading
                ? 'Reading your material…'
                : embedded ? 'Upload your project' : 'Drop your material here'}
          </strong>
          <span>
            {loading ? (
              'This will only take a moment.'
            ) : (
              <>
                or <span className="browse-text">browse files</span> to upload
              </>
            )}
          </span>
          <input
            id="source-file"
            className="dropzone-input"
            type="file"
            aria-label="Upload study material"
            onChange={upload}
            disabled={disabled || loading}
            accept={accept}
            aria-describedby="source-help"
          />
        </div>
      ) : (
        <div className="uploaded-file">
          <span className="document-icon">
            <Icon name="file" size={24} />
          </span>
          <div className="uploaded-file-info">
            <strong title={source.filename}>{source.filename}</strong>
            {!compact && <p>{sourceCounts}</p>}
          </div>
          <div className="file-actions">
            <label
              className={`file-replace ${disabled || loading ? 'is-disabled' : ''}`}
            >
              <span>Replace</span>
              <input
                id="source-file"
                type="file"
                aria-label="Replace study material"
                onChange={upload}
                disabled={disabled || loading}
                accept={accept}
                aria-describedby="source-help"
              />
            </label>
            <button
              type="button"
              className="icon-button"
              disabled={disabled || loading}
              aria-label="Close material"
              title="Close material"
              onClick={removeUpload}
            >
              <Icon name="close" size={17} />
            </button>
          </div>
        </div>
      )}
      {!compact && (
        <p id="source-help" className="upload-limits">
          Searchable PDF <span>up to 5 MiB</span>
          <span className="limit-divider">·</span>Source / text{' '}
          <span>up to 256 KiB</span>
        </p>
      )}
      {compact && (
        <span id="source-help" className="sr-only">
          PDF up to 5 MiB and 20 pages, or UTF-8 source/text up to 256 KiB.
        </span>
      )}
      <p
        role="status"
        className={
          compact || embedded
            ? 'sr-only'
            : `upload-notice ${notice || (loading && !restoring) ? 'has-notice' : ''}`
        }
      >
        {loading && !restoring ? 'Processing your material…' : notice}
      </p>
      {error && (
        <p role="alert" className="inline-error">
          <Icon name="info" size={17} />
          {error}
        </p>
      )}
      {compact ? (
        <div className="compact-material-footer">
          <details className="material-details">
            <summary>
              Material details
              <Icon name="chevron" size={14} />
              {source && source.warnings.length > 0 && (
                <span>{source.warnings.length} notices</span>
              )}
            </summary>
            <div className="material-details-body">
              {source && <p className="full-filename">{source.filename}</p>}
              {source && <p className="material-counts">{sourceCounts}</p>}
              {materialDetails}
            </div>
          </details>
          <div className="material-practice-action">{practiceAction}</div>
        </div>
      ) : (
        materialDetails
      )}
    </section>
  )
}
