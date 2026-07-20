export type CompanionDebugTrace = {
  user_question: string
  current_context: Record<string, unknown>
  retrieval: Record<string, unknown>
  prompt: string
  gemini_response: string
  parsed_json: Record<string, unknown>
  formatted_response: Record<string, unknown>
  final_ui: Record<string, unknown>
  issues: Array<{ stage: string; message: string }>
}

type Listener = () => void
let trace: CompanionDebugTrace | null = null
const listeners = new Set<Listener>()

export function setCompanionDebugTrace(value: CompanionDebugTrace | null) {
  trace = value
  listeners.forEach((listener) => listener())
}

export function getCompanionDebugTrace() { return trace }
export function subscribeCompanionDebugTrace(listener: Listener) { listeners.add(listener); return () => listeners.delete(listener) }

export function setCompanionDebugFailure(question: string, message: string) {
  setCompanionDebugTrace({ user_question: question, current_context: {}, retrieval: {}, prompt: '', gemini_response: '', parsed_json: {}, formatted_response: {}, final_ui: {}, issues: [{ stage: 'Client / Backend', message }] })
}
