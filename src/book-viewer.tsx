import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  BookOpen,
  Brain,
  Clock3,
  Link2,
  Loader2,
  Network,
  Send,
  Sparkles,
  Upload,
  Users,
} from 'lucide-react'

import {
  bookBackendService,
  type BookChapter,
  type BookChapterMetadata,
} from './services/backend/BookBackendService'
import { BackendRequestError } from './services/backend/apiClient'
import { companionProfilePayload } from './services/backend/profilePayload'
import { useAccessibilityProfile } from './hooks/useAccessibilityProfile'

type BookViewerProps = { onBack: () => void }
type BottomTab = 'characters' | 'relationships' | 'timeline' | 'memory' | 'map'

export function BookViewer({ onBack }: BookViewerProps) {
  const { profile } = useAccessibilityProfile()
  const inputRef = useRef<HTMLInputElement>(null)

  const [bookId, setBookId] = useState('')
  const [status, setStatus] = useState('')
  const [progress, setProgress] = useState(0)
  const [initializingExample, setInitializingExample] = useState(true)
  const [exampleUnavailable, setExampleUnavailable] = useState(false)
  const [chapterCount, setChapterCount] = useState(0)
  const [chapters, setChapters] = useState<BookChapterMetadata[]>([])
  const [activeChapterNumber, setActiveChapterNumber] = useState(1)
  const [chapter, setChapter] = useState<BookChapter | null>(null)

  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState('')
  const [isAsking, setIsAsking] = useState(false)
  const [activeTab, setActiveTab] = useState<BottomTab>('characters')

  const pageLabel = useMemo(() => {
    if (!chapter) return 'Page range unavailable'
    return `Pages ${chapter.page_start}-${chapter.page_end}`
  }, [chapter])

  async function startPipeline(id: string) {
    setError('')
    setAnswer('')
    setStatus('extracting')
    setProgress(5)
    setBookId(id)
    setChapters([])
    setChapter(null)
    await bookBackendService.start(id, companionProfilePayload(profile))
  }

  async function loadChaptersAndFirst(book: string) {
    const listing = await bookBackendService.chapters(book)
    setChapters(listing.chapters)
    setChapterCount(listing.chapters.length)
    const first = listing.chapters[0]?.chapter_number ?? 1
    setActiveChapterNumber(first)
  }

  async function loadChapter(book: string, chapterNumber: number) {
    const data = await bookBackendService.chapter(book, chapterNumber)
    setChapter(data)
  }

  useEffect(() => {
    void (async () => {
      try {
        const { book_id } = await bookBackendService.dune()
        await startPipeline(book_id)
      } catch (err: unknown) {
        if (err instanceof BackendRequestError && err.status === 404) {
          setExampleUnavailable(true)
          setError('')
          return
        }
        setError(err instanceof Error ? err.message : 'The Dune example is unavailable.')
      } finally {
        setInitializingExample(false)
      }
    })()
  }, [])

  useEffect(() => {
    if (!bookId || status === 'complete' || status === 'failed') return
    const timer = window.setInterval(() => {
      void bookBackendService
        .status(bookId)
        .then(async (next) => {
          setStatus(next.status)
          setProgress(next.percentage)
          setChapterCount(next.chapter_count ?? 0)

          if (next.status === 'complete') {
            await loadChaptersAndFirst(bookId)
          }
          if (next.status === 'failed') {
            setError(next.error ?? 'Book processing failed.')
          }
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : 'Could not check book processing.')
        })
    }, 1800)

    return () => window.clearInterval(timer)
  }, [bookId, status])

  useEffect(() => {
    if (!bookId || status !== 'complete') return
    void loadChapter(bookId, activeChapterNumber).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Could not load this chapter.')
    })
  }, [bookId, status, activeChapterNumber])

  async function upload(file: File) {
    try {
      const uploaded = await bookBackendService.upload(file)
      await startPipeline(uploaded.book_id)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not upload this book.')
    }
  }

  async function askCompanion() {
    if (!bookId || !question.trim() || isAsking) return
    setIsAsking(true)
    try {
      const result = await bookBackendService.chat(bookId, activeChapterNumber, question, companionProfilePayload(profile))
      setAnswer(result.answer)
      setQuestion('')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Companion is unavailable.')
    } finally {
      setIsAsking(false)
    }
  }

  const chapterTitle = chapter?.chapter_title ?? `Chapter ${activeChapterNumber}`

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_20%_15%,#ffe9bf_0%,transparent_28%),radial-gradient(circle_at_88%_20%,#d9ecff_0%,transparent_35%),linear-gradient(180deg,#f9f4ea,#eef3fb)] text-slate-900">
      <div className="mx-auto max-w-[1440px] px-4 pb-8 pt-6 sm:px-6 lg:px-8">
        <header className="mb-4 rounded-3xl border border-amber-200/70 bg-white/85 p-4 shadow-[0_18px_45px_rgba(18,30,56,.08)] backdrop-blur sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button onClick={onBack} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-semibold hover:bg-slate-100">
              <ArrowLeft size={16} /> Back
            </button>
            <div className="flex items-center gap-3">
              <BookOpen className="text-amber-700" size={20} />
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Book companion</p>
                <h1 className="font-serif text-xl text-slate-900 sm:text-2xl">{chapterTitle}</h1>
              </div>
            </div>
            <button onClick={() => inputRef.current?.click()} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700">
              <Upload size={15} /> Upload book
            </button>
            <input
              ref={inputRef}
              className="sr-only"
              type="file"
              accept="application/pdf,.epub,text/plain,.txt"
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.currentTarget.value = ''
                if (file) void upload(file)
              }}
            />
          </div>
        </header>

        {initializingExample ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-[0_18px_40px_rgba(18,30,56,.08)]" aria-live="polite">
            <div className="flex items-center gap-3">
              <Loader2 className="animate-spin text-amber-600" />
              <div>
                <p className="font-semibold">Connecting to your reading companion</p>
                <p className="text-sm text-slate-600">Checking for the Dune example on the backend.</p>
              </div>
            </div>
          </section>
        ) : !bookId ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-[0_18px_40px_rgba(18,30,56,.08)]" aria-live="polite">
            <div className="space-y-3">
              <h2 className="font-serif text-2xl text-slate-900">Start your reading companion</h2>
              <p className="text-sm text-slate-600">
                {exampleUnavailable
                  ? 'The deployed backend does not currently have the Dune sample loaded. Upload a PDF, EPUB, or text file to begin.'
                  : 'Upload a PDF, EPUB, or text file to begin preprocessing.'}
              </p>
              <button
                onClick={() => inputRef.current?.click()}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
              >
                <Upload size={15} /> Upload a book
              </button>
            </div>
          </section>
        ) : status !== 'complete' ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-[0_18px_40px_rgba(18,30,56,.08)]" aria-live="polite">
            <div className="flex items-center gap-3">
              <Loader2 className="animate-spin text-amber-600" />
              <div>
                <p className="font-semibold">Creating your MagiFab reading companion</p>
                <p className="text-sm text-slate-600">{status || 'waiting'} · {progress}%</p>
              </div>
            </div>
            <div className="mt-5 h-2 rounded-full bg-slate-200">
              <div className="h-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-500" style={{ width: `${Math.max(3, progress)}%` }} />
            </div>
            <p className="mt-4 text-sm text-slate-600">
              Detecting front matter, locating narrative start, segmenting chapters, and building chapter explanations.
            </p>
          </section>
        ) : (
          <div className="space-y-4">
            <section className="grid gap-4 lg:grid-cols-[270px_1fr_320px]">
              <aside className="rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_16px_36px_rgba(18,30,56,.07)]">
                <h2 className="mb-1 font-serif text-lg">Book progress</h2>
                <p className="text-xs text-slate-500">{chapterCount} chapter segments ready</p>
                <div className="mt-4 space-y-2">
                  {chapters.map((item) => {
                    const active = item.chapter_number === activeChapterNumber
                    return (
                      <button
                        key={item.chapter_number}
                        onClick={() => setActiveChapterNumber(item.chapter_number)}
                        className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                          active
                            ? 'border-amber-400 bg-amber-50 text-slate-900'
                            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                        }`}
                      >
                        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Chapter {item.chapter_number}</p>
                        <p className="line-clamp-2 text-sm font-semibold">{item.chapter_title}</p>
                        <p className="text-xs text-slate-500">pp. {item.page_start}-{item.page_end}</p>
                      </button>
                    )
                  })}
                </div>
              </aside>

              <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_16px_36px_rgba(18,30,56,.07)]">
                <div className="mb-3 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                  <span className="rounded-full bg-slate-100 px-2 py-1">{chapter?.section_label ?? 'chapter'}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-1">{pageLabel}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-1">Confidence {(chapter?.confidence ?? 0).toFixed(2)}</span>
                </div>
                <h2 className="font-serif text-2xl text-slate-900">{chapterTitle}</h2>
                <p className="mt-3 leading-7 text-slate-700">{chapter?.chapter_summary}</p>

                <div className="mt-5 rounded-2xl border border-blue-200 bg-blue-50/80 p-4">
                  <div className="mb-2 flex items-center gap-2 text-blue-900">
                    <Sparkles size={16} />
                    <p className="text-sm font-semibold">Simplified explanation</p>
                  </div>
                  <p className="text-sm leading-7 text-blue-900/90">{chapter?.simple_explanation}</p>
                </div>

                <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
                  <p className="mb-2 text-sm font-semibold text-amber-900">Important events</p>
                  <ul className="space-y-2 text-sm text-amber-900/90">
                    {(chapter?.important_events ?? []).map((item, index) => (
                      <li key={index}>• {item}</li>
                    ))}
                  </ul>
                </div>
              </article>

              <aside className="rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_16px_36px_rgba(18,30,56,.07)]">
                <h2 className="font-serif text-lg">Companion</h2>
                <p className="mt-1 text-sm text-slate-600">Ask about this chapter with profile-aware support.</p>

                {answer ? (
                  <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">{answer}</div>
                ) : null}

                <div className="mt-4 space-y-2">
                  {(chapter?.companion_questions ?? []).map((item, index) => (
                    <button
                      key={`${item.label}-${index}`}
                      onClick={() => setQuestion(item.question)}
                      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-sm hover:bg-slate-50"
                    >
                      <p className="font-semibold text-slate-800">{item.label}</p>
                      <p className="text-xs text-slate-500">{item.question}</p>
                    </button>
                  ))}
                </div>

                <div className="mt-4 flex gap-2">
                  <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        void askCompanion()
                      }
                    }}
                    placeholder="Ask a question about this chapter"
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none ring-amber-300 focus:ring"
                  />
                  <button
                    onClick={() => void askCompanion()}
                    disabled={isAsking || !question.trim()}
                    className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-3 py-2 text-white disabled:opacity-40"
                  >
                    <Send size={14} />
                  </button>
                </div>
              </aside>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_16px_36px_rgba(18,30,56,.07)]">
              <div className="flex flex-wrap gap-2">
                <TabButton active={activeTab === 'characters'} onClick={() => setActiveTab('characters')} icon={<Users size={14} />} label="Characters" />
                <TabButton active={activeTab === 'relationships'} onClick={() => setActiveTab('relationships')} icon={<Link2 size={14} />} label="Relationships" />
                <TabButton active={activeTab === 'timeline'} onClick={() => setActiveTab('timeline')} icon={<Clock3 size={14} />} label="Timeline" />
                <TabButton active={activeTab === 'memory'} onClick={() => setActiveTab('memory')} icon={<Brain size={14} />} label="Memory Aid" />
                <TabButton active={activeTab === 'map'} onClick={() => setActiveTab('map')} icon={<Network size={14} />} label="Visual Map" />
              </div>

              {activeTab === 'characters' ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {(chapter?.characters ?? []).map((item) => (
                    <div key={item.name} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                      <p className="font-semibold text-slate-900">{item.name}</p>
                      <p className="mt-1 text-sm text-slate-700">{item.description}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              {activeTab === 'relationships' ? (
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {(chapter?.relationships ?? []).map((item, index) => (
                    <div key={`${item.source}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm">
                      <p className="font-semibold text-slate-900">{item.source}</p>
                      <p className="my-1 text-slate-500">{item.relation}</p>
                      <p className="font-semibold text-slate-900">{item.target}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              {activeTab === 'timeline' ? (
                <ul className="mt-4 space-y-2 text-sm text-slate-700">
                  {(chapter?.important_events ?? []).map((item, index) => (
                    <li key={index} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">{item}</li>
                  ))}
                </ul>
              ) : null}

              {activeTab === 'memory' ? (
                <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-sm font-semibold text-amber-900">Memory aid sentence</p>
                  <p className="mt-2 text-sm leading-7 text-amber-900/90">{chapter?.memory_aid}</p>
                  {(chapter?.difficult_concepts ?? []).length ? (
                    <div className="mt-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-800">Difficult concepts</p>
                      <p className="mt-1 text-sm text-amber-900/90">{chapter?.difficult_concepts.join(' • ')}</p>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {activeTab === 'map' ? (
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <p className="mb-2 text-sm font-semibold">Nodes</p>
                    <ul className="space-y-1 text-sm text-slate-700">
                      {(chapter?.visual_relationship_map.nodes ?? []).map((node) => (
                        <li key={node.id}>• {node.label}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <p className="mb-2 text-sm font-semibold">Edges</p>
                    <ul className="space-y-1 text-sm text-slate-700">
                      {(chapter?.visual_relationship_map.edges ?? []).map((edge, index) => (
                        <li key={`${edge.source}-${index}`}>
                          {edge.source} → {edge.target} ({edge.label})
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        )}

        {error ? <p className="mt-3 rounded-xl border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}
      </div>
    </main>
  )
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition ${
        active
          ? 'border-slate-900 bg-slate-900 text-white'
          : 'border-slate-300 bg-white text-slate-700 hover:border-slate-500'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}
