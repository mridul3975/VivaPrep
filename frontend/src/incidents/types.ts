export interface RequestSpec { method: string; path: string; body: unknown }
export interface Experiment { name: string; concurrent: boolean; requests: RequestSpec[] }
export interface Observation {
  name: string; concurrent: boolean; passed?: boolean | null; error?: string
  responses: (RequestSpec & { status: number; response: string; milliseconds: number; error?: string })[]
  database_before: Record<string, unknown>; database_after: Record<string, unknown>
  trace: { path: string; line: number; thread: number; source: string }[]; logs: string
}
export interface Execution { id?: string; scope?: string; passed: boolean | null; experiments: Observation[]; files_sha256: string }
export interface Plan {
  id: string; action: 'inspect' | 'replay' | 'test_fix' | 'experiment' | 'discuss'; response: string; instruction: string
  citations: { path: string; line_start: number; line_end: number; quote: string }[]; experiment: Experiment | null
}
export interface Lab {
  instruction_draft?: { text: string; original: string | null; reviewed: boolean }
  id: string; title: string; status: 'preparing' | 'running' | 'ready' | 'error'; error: string; files: Record<string, string>; original_files: Record<string, string>
  scenario?: { title: string; description: string; reproduction: Experiment; regressions: Experiment[] }
  baseline?: Execution; broken_evidence?: Execution; latest?: Execution; conversation: Plan[]; plan?: Plan | null
  solved: boolean; current_execution: boolean
}
export interface Catalogue { runner_available: boolean; usage: { used: number; limit: number; remaining: number }; labs: { id: string; title: string; status: string; updated_at: string }[] }
