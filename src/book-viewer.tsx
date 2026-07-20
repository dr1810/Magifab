import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BookOpen, ChevronLeft, ChevronRight, FileText, Loader2, Sparkles, Upload } from 'lucide-react'
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy, type PDFPageProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { CompanionWidget } from './components/CompanionWidget'
import { BookPromptBubbles } from './components/BookPromptBubbles'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { useAccessibility } from './accessibility-context'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import type { SceneState } from './services/scene/SceneState'
import type { PromptQuestion } from './types/movie'

GlobalWorkerOptions.workerSrc = workerUrl

type BookViewerProps = { onBack: () => void }
type RenderedPage = { pageNumber: number; text: string; image: string }
type CachedSpread = { pages: RenderedPage[]; sceneState: SceneState }

function pageRange(pageNumber: number, pageCount: number) {
  const pageStart = Math.max(1, pageNumber % 2 === 0 ? pageNumber - 1 : pageNumber)
  return { pageStart, pageEnd: Math.min(pageCount, pageStart + 1) }
}

function fallbackState(bookId: string, pageStart: number, pageEnd: number): SceneState {
  return {
    sceneId: `${bookId}:pages:${pageStart}-${pageEnd}`, interval: Math.floor((pageStart - 1) / 2), startTime: pageStart, endTime: pageEnd,
    sceneSummary: `Pages ${pageStart}–${pageEnd} are being understood. Choose a prompt when you want help.`,
    subtitle: null, characters: [], relationships: [], timeline: [`Reading pages ${pageStart}–${pageEnd}`], memory: [], importantObjects: [], emotions: [], causeEffect: [],
    promptBubbles: [
      { id: 'book-who', kind: 'character_identity', label: 'Who is this character?', question: 'Who is this character?', priority: 1 },
      { id: 'book-emotion', kind: 'emotion', label: 'Why do they feel this way?', question: 'Why does this character feel this way?', priority: 2 },
      { id: 'book-memory', kind: 'timeline', label: 'What happened earlier?', question: 'What happened earlier?', priority: 3 },
      { id: 'book-place', kind: 'scene', label: 'Where are they now?', question: 'Where are they now?', priority: 4 },
      { id: 'book-object', kind: 'object', label: 'What does this mean?', question: 'What does this object or word mean?', priority: 5 },
    ],
    accessibilityHints: { vocabulary: [], emotions: [] }, conversation: { sceneExplanation: 'MagiFab is preparing a simple explanation for this part of the story.', simplifications: [] },
    story: { currentGoal: null, timelinePosition: `Pages ${pageStart}–${pageEnd}`, storySoFar: [], unresolvedThreads: [] },
    metadata: { movieId: bookId, generatedAt: Date.now(), knowledgeRevision: 0, frameTimestamp: null },
  }
}

async function renderPage(pdf: PDFDocumentProxy, pageNumber: number): Promise<RenderedPage> {
  const page: PDFPageProxy = await pdf.getPage(pageNumber)
  const viewport = page.getViewport({ scale: Math.min(1.6, Math.max(1, window.devicePixelRatio)) })
  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(viewport.width)
  canvas.height = Math.ceil(viewport.height)
  const context = canvas.getContext('2d', { alpha: false })
  if (!context) throw new Error('Canvas rendering is unavailable.')
  await page.render({ canvas, canvasContext: context, viewport }).promise
  const textContent = await page.getTextContent()
  const text = textContent.items.map((item) => {
    if (!('str' in item)) return ''
    return `${item.str}${'hasEOL' in item && item.hasEOL ? '\n' : ' '}`
  }).join('').trim()
  return { pageNumber, text, image: canvas.toDataURL('image/jpeg', 0.82) }
}

function PdfPage({ page, side }: { page: RenderedPage | null; side: 'left' | 'right' }) {
  return <article className={`book-sheet ${side}`} aria-label={page ? `Page ${page.pageNumber}` : 'Blank page'}>
    {page ? <><img src={page.image} alt={`PDF page ${page.pageNumber}`} draggable={false}/><div className="book-page-text-layer" aria-label={`Selectable text for page ${page.pageNumber}`}>{page.text}</div><span className="book-page-number">{page.pageNumber}</span></> : <span className="book-blank-page"/>}
  </article>
}

export function BookViewer({ onBack }: BookViewerProps) {
  const { settings } = useAccessibility()
  const { profile } = useCompanionProfile()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const dragStartRef = useRef<number | null>(null)
  const stageRef = useRef<HTMLElement | null>(null)
  const readingSurfaceRef = useRef<HTMLDivElement | null>(null)
  const bookRef = useRef<HTMLDivElement | null>(null)
  const leftTurnRef = useRef<HTMLButtonElement | null>(null)
  const rightTurnRef = useRef<HTMLButtonElement | null>(null)
  const activeSpreadRef = useRef('')
  const sceneCacheRef = useRef(new Map<string, CachedSpread>())
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null)
  const [bookId, setBookId] = useState('')
  const [title, setTitle] = useState('Choose a PDF')
  const [pageCount, setPageCount] = useState(0)
  const [spreadStart, setSpreadStart] = useState(1)
  const [pages, setPages] = useState<RenderedPage[]>([])
  const [loading, setLoading] = useState(false)
  const [sceneState, setSceneState] = useState<SceneState | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [widgetOpen, setWidgetOpen] = useState(false)
  const [promptOpen, setPromptOpen] = useState(false)
  const [activeBubble, setActiveBubble] = useState<PromptBubbleContent | null>(null)
  const reduceMotion = settings.reduceMotion || settings.disableAnimations
  const prompts: Array<PromptQuestion & { priority?: number }> = useMemo(() => sceneState?.promptBubbles.map((prompt) => ({ id: prompt.id, label: prompt.label, question: prompt.question, explanation: '', priority: prompt.priority })) ?? [], [sceneState])

  const prepareSpread = useCallback(async (pdf: PDFDocumentProxy, sourceId: string, nextSpreadStart: number, background = false) => {
    const range = pageRange(nextSpreadStart, pdf.numPages)
    const cacheKey = `${sourceId}:${range.pageStart}-${range.pageEnd}`
    const cached = sceneCacheRef.current.get(cacheKey)
    if (cached) {
      if (!background && activeSpreadRef.current === cacheKey) { setPages(cached.pages); setSceneState(cached.sceneState) }
      return
    }
    let extractedText = ''
    if (!background) setLoading(true)
    try {
      const rendered = await Promise.all([renderPage(pdf, range.pageStart), range.pageEnd !== range.pageStart ? renderPage(pdf, range.pageEnd) : Promise.resolve(null)])
      const visiblePages = rendered.filter((page): page is RenderedPage => Boolean(page))
      extractedText = visiblePages.map((page) => page.text).join('\n\n')
      const initialSceneState = fallbackState(sourceId, range.pageStart, range.pageEnd)
      sceneCacheRef.current.set(cacheKey, { pages: visiblePages, sceneState: initialSceneState })
      if (!background && activeSpreadRef.current === cacheKey) {
        setPages(visiblePages)
        setSceneState(initialSceneState)
        setLoading(false)
      }
    } catch (error) {
      if (!background) console.warn('[MagiFab] Book range companion preparation failed; showing local reading context.', error)
      const initialSceneState = fallbackState(sourceId, range.pageStart, range.pageEnd)
      const current = sceneCacheRef.current.get(cacheKey)
      sceneCacheRef.current.set(cacheKey, { pages: current?.pages ?? [], sceneState: initialSceneState })
      if (!background && activeSpreadRef.current === cacheKey) setSceneState(initialSceneState)
    } finally {
      if (!background && activeSpreadRef.current === cacheKey) setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!document || !bookId) return
    const range = pageRange(spreadStart, pageCount)
    const cacheKey = `${bookId}:${range.pageStart}-${range.pageEnd}`
    activeSpreadRef.current = cacheKey
    void prepareSpread(document, bookId, spreadStart)
    const nextStart = range.pageEnd + 1
    if (nextStart <= pageCount) void prepareSpread(document, bookId, nextStart, true)
  }, [bookId, document, prepareSpread, spreadStart])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!document || event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return
      if (event.key === 'ArrowRight' || event.key === 'PageDown') { event.preventDefault(); setSpreadStart((current) => Math.min(Math.max(1, pageCount - 1), current + 2)) }
      if (event.key === 'ArrowLeft' || event.key === 'PageUp') { event.preventDefault(); setSpreadStart((current) => Math.max(1, current - 2)) }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [document, pageCount])

  const loadFile = async (file: File) => {
    if (file.type !== 'application/pdf') return
    setLoading(true)
    try {
      const pdf = await getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise
      sceneCacheRef.current.clear()
      setDocument(pdf); setBookId(`${file.name}-${file.size}-${file.lastModified}`); setTitle(file.name.replace(/\.pdf$/i, '')); setPageCount(pdf.numPages); setSpreadStart(1); setPages([]); setSceneState(null)
    } finally { setLoading(false) }
  }
  const turn = (direction: -1 | 1) => setSpreadStart((current) => direction === 1 ? Math.min(Math.max(1, pageCount - 1), current + 2) : Math.max(1, current - 2))
  const activePrompt = prompts[0]
  const showBubble = (prompt: PromptQuestion, position?: { left: number; top: number }) => setActiveBubble({ id: prompt.id, question: prompt.question, title: prompt.label, relationship: 'Reading companion', explanation: sceneState?.sceneSummary ?? '', anchor: { x: 50, y: 42 }, highlightTarget: false, absolutePosition: position })

  return <main className="movie-experience viewer-page book-viewer-page">
    <input ref={inputRef} type="file" accept="application/pdf" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (file) void loadFile(file) }}/>
    <header className="top-bar"><div className="left-cluster"><button className="ghost-btn" onClick={onBack}><ChevronLeft size={16}/>Back</button><div><p className="eyebrow">Reading Mode</p><h2>{title}</h2></div></div><div className="right-cluster"><button className="ghost-btn" onClick={() => inputRef.current?.click()}><Upload size={16}/>Open PDF</button><button className="ghost-btn" onClick={() => setPromptOpen(true)}><Sparkles size={16}/>Prompts</button><button className="ghost-btn" onClick={() => setDrawerOpen(true)}><BookOpen size={16}/>Visual Drawer</button></div></header>
    {!document ? <section className="book-upload"><FileText size={42}/><h1>Open a storybook PDF</h1><p>The original PDF stays the source of truth. MagiFab renders each page and its selectable text layer directly in the reader.</p><button className="primary-btn" onClick={() => inputRef.current?.click()}><Upload size={16}/>Choose PDF</button></section> : <section ref={stageRef} className="book-stage">
      <div className="book-toolbar"><span>Pages {pageRange(spreadStart, pageCount).pageStart}–{pageRange(spreadStart, pageCount).pageEnd} of {pageCount}</span>{loading ? <span><Loader2 className="spin" size={15}/> Loading pages</span> : <span>Help is ready when you are</span>}</div>
      <div ref={readingSurfaceRef} className="book-reading-surface">
      <div ref={bookRef} className={`storybook ${reduceMotion ? 'reduced-motion' : ''}`} role="region" aria-label="PDF storybook" tabIndex={0} onPointerDown={(event) => { dragStartRef.current = event.clientX }} onPointerUp={(event) => { const start = dragStartRef.current; dragStartRef.current = null; if (start !== null && Math.abs(event.clientX - start) > 55) turn(event.clientX < start ? 1 : -1) }}>
        <span className="book-navigation-zone left" aria-hidden="true"/><span className="book-navigation-zone right" aria-hidden="true"/>
        <button ref={leftTurnRef} className="book-turn left" onClick={() => turn(-1)} disabled={spreadStart <= 1} aria-label="Previous pages"><ChevronLeft/></button>
        <div key={spreadStart} className="book-spread page-turn"><PdfPage page={pages[0] ?? null} side="left"/><span className="book-spine"/><PdfPage page={pages[1] ?? null} side="right"/></div>
        <button ref={rightTurnRef} className="book-turn right" onClick={() => turn(1)} disabled={spreadStart + 1 >= pageCount} aria-label="Next pages"><ChevronRight/></button>
      </div>
      <BookPromptBubbles prompts={prompts} stageRef={stageRef} surfaceRef={readingSurfaceRef} bookRef={bookRef} leftTurnRef={leftTurnRef} rightTurnRef={rightTurnRef} drawerOpen={drawerOpen} onSelect={showBubble} onOverflow={() => setPromptOpen(true)}/>
      </div>
      <div className="book-actions"><button className="ghost-btn" onClick={() => turn(-1)} disabled={spreadStart <= 1}><ChevronLeft size={16}/>Previous</button><button className="ghost-btn" onClick={() => setDrawerOpen(true)}><BookOpen size={16}/>Explore this page</button><button className="ghost-btn" onClick={() => turn(1)} disabled={spreadStart + 1 >= pageCount}>Next<ChevronRight size={16}/></button></div>
      <FloatingBubble content={activeBubble} theme="sun" reduceMotion={reduceMotion} visible={Boolean(activeBubble)} onOpenCompanion={() => setWidgetOpen(true)} onClose={() => setActiveBubble(null)}/>
      <CompanionWidget open={widgetOpen} name={profile?.name ?? 'Lumi'} message={sceneState?.conversation.sceneExplanation ?? 'Choose a prompt to explore this part of the story.'} theme="sun" onClose={() => setWidgetOpen(false)} reduceMotion={reduceMotion}/>
      <PromptPanel open={promptOpen} prompts={prompts} selectedPromptId={activePrompt?.id ?? ''} onSelectPrompt={(prompt) => showBubble(prompt)} onClose={() => setPromptOpen(false)}/>
      <VisualDrawer open={drawerOpen} sceneState={sceneState} onClose={() => setDrawerOpen(false)} presentation="book-sheet"/>
    </section>}
  </main>
}
