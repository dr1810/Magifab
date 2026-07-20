import { useSyncExternalStore, useState, type ReactNode } from 'react'
import { Bug, ChevronDown, ChevronUp } from 'lucide-react'
import { getCompanionDebugTrace, subscribeCompanionDebugTrace } from '../services/debugTraceStore'

function Data({ value }: { value: unknown }) {
  return <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-950/90 p-3 text-xs leading-5 text-slate-100">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>
}

export function CompanionDebugPanel() {
  const [open, setOpen] = useState(false)
  const trace = useSyncExternalStore(subscribeCompanionDebugTrace, getCompanionDebugTrace, getCompanionDebugTrace)
  if (!import.meta.env.DEV) return null
  const issues = trace?.issues ?? []
  return <aside className="fixed bottom-3 right-3 z-[100] w-[min(94vw,760px)] rounded-xl border border-amber-300/50 bg-slate-900/95 text-white shadow-2xl backdrop-blur" aria-label="Companion pipeline debug panel">
    <button type="button" className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-bold" onClick={() => setOpen((value) => !value)}><span className="inline-flex items-center gap-2"><Bug size={16} className="text-amber-300"/>Companion Debug Pipeline {issues.length > 0 && <span className="rounded bg-red-600 px-2 py-0.5 text-[10px]">{issues.length} issue{issues.length === 1 ? '' : 's'}</span>}</span>{open ? <ChevronDown size={16}/> : <ChevronUp size={16}/>}</button>
    {open && <div className="max-h-[72vh] space-y-4 overflow-y-auto border-t border-white/15 p-4">
      {!trace ? <p className="rounded border border-red-400/60 bg-red-950/50 p-3 text-sm text-red-100">No backend companion query trace has been received in this session.</p> : <>
        <Section title="USER QUESTION"><Data value={trace.user_question}/></Section>
        <Section title="STEP 1 · Current Context" issues={issues.filter((issue) => issue.stage.includes('STEP 1'))}><Data value={trace.current_context}/></Section>
        <Section title="STEP 2 · Retrieval" issues={issues.filter((issue) => issue.stage.includes('STEP 2'))}><Data value={trace.retrieval}/></Section>
        <Section title="STEP 3 · Exact Prompt"><Data value={trace.prompt}/></Section>
        <Section title="STEP 4 · Raw Gemini Response"><Data value={trace.gemini_response}/></Section>
        <Section title="STEP 5 · Parsed JSON"><Data value={trace.parsed_json}/><Data value={trace.formatted_response}/></Section>
        <Section title="STEP 6 · Final UI"><Data value={trace.final_ui}/></Section>
      </>}
    </div>}
  </aside>
}

function Section({ title, issues = [], children }: { title: string; issues?: Array<{ stage: string; message: string }>; children: ReactNode }) {
  return <section className={issues.length ? 'rounded border border-red-500 bg-red-950/35 p-3' : ''}><h3 className="mb-2 text-xs font-bold tracking-wider text-amber-200">{title}</h3>{issues.map((issue) => <p key={`${issue.stage}:${issue.message}`} className="mb-2 rounded bg-red-600/35 p-2 text-xs text-red-100">{issue.message}</p>)}{children}</section>
}
