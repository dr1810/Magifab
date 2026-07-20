import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BookOpen, ChevronLeft, ChevronRight, FileText, Loader2, Sparkles, Upload } from 'lucide-react'
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy, type PDFPageProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { CompanionWidget } from './components/CompanionWidget'
import { CompanionAvatar } from './components/CompanionAvatar'
import { BookPromptBubbles } from './components/BookPromptBubbles'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { useAccessibility } from './accessibility-context'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import { useAccessibilityProfile } from './hooks/useAccessibilityProfile'
import { getContentNarrativeGraph } from './services/narrative/NarrativeRepository'
import { StoryResolver } from './services/narrative/StoryResolver'
import type { SceneState } from './services/scene/SceneState'
import type { PromptQuestion } from './types/movie'
import { useOverlayManager } from './hooks/useOverlayManager'

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

function indexedState(bookId: string, pages: RenderedPage[]): SceneState {
  const pageStart = pages[0]?.pageNumber ?? 1
  const pageEnd = pages.at(-1)?.pageNumber ?? pageStart
  const text = pages.map((page) => page.text).join(' ').replace(/\s+/g, ' ').trim()
  const names = [...new Set((text.match(/\b[A-Z][a-z]{2,}\b/g) ?? []).filter((name) => !['The', 'This', 'That', 'And', 'For', 'With'].includes(name)))].slice(0, 3)
  const characters = names.map((name) => ({ character_id: `${bookId}:${name.toLowerCase()}`, name, reminder: `Mentioned on pages ${pageStart}–${pageEnd}.`, confidence: 1 }))
  const excerpt = text.slice(0, 280) || `Pages ${pageStart}–${pageEnd} are ready to explore.`
  const emotionalTone = /\b(afraid|fear|scared|angry|furious|sad|cry|happy|joy|excited|worried)\b/i.exec(text)?.[0]
  return {
    ...fallbackState(bookId, pageStart, pageEnd),
    sceneSummary: excerpt,
    characters,
    relationships: [{ relationship_id: `${bookId}:${pageStart}:characters`, summary: characters.length > 1 ? `${characters.map((character) => character.name).join(', ')} appear together on these pages.` : 'These pages establish the current reading moment.', confidence: 1 }],
    timeline: [`Reading pages ${pageStart}–${pageEnd}`, excerpt],
    memory: [{ summary: excerpt, confidence: 1 }],
    emotions: [{ emotion_id: `${bookId}:${pageStart}:tone`, summary: emotionalTone ? `The text names a ${emotionalTone.toLowerCase()} feeling on these pages.` : 'The text does not name a specific emotion on these pages.', confidence: 1 }],
    conversation: { sceneExplanation: excerpt, simplifications: [] },
    story: { currentGoal: excerpt, timelinePosition: `Pages ${pageStart}–${pageEnd}`, storySoFar: [excerpt], unresolvedThreads: [] },
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
  const { profile: accessibilityProfile } = useAccessibilityProfile()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const dragStartRef = useRef<number | null>(null)
  const stageRef = useRef<HTMLElement | null>(null)
  const readingSurfaceRef = useRef<HTMLDivElement | null>(null)
  const bookRef = useRef<HTMLDivElement | null>(null)
  const leftTurnRef = useRef<HTMLButtonElement | null>(null)
  const rightTurnRef = useRef<HTMLButtonElement | null>(null)
  const activeSpreadRef = useRef('')
  const sceneCacheRef = useRef(new Map<string, CachedSpread>())
  const inFlightSpreadsRef = useRef(new Map<string, Promise<CachedSpread>>())
  const loadGenerationRef = useRef(0)
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null)
  const [bookId, setBookId] = useState('')
  const [title, setTitle] = useState('Choose a PDF')
  const [pageCount, setPageCount] = useState(0)
  const [spreadStart, setSpreadStart] = useState(1)
  const [pages, setPages] = useState<RenderedPage[]>([])
  const [loading, setLoading] = useState(false)
  const [sceneState, setSceneState] = useState<SceneState | null>(null)
  const [activeBubble, setActiveBubble] = useState<PromptBubbleContent | null>(null)
  const overlays = useOverlayManager()
  const drawerOpen = overlays.isOpen('story-companion')
  const promptOpen = overlays.isOpen('prompt-guide')
  const widgetOpen = overlays.isOpen('aster')
  const promptCardOpen = overlays.isOpen('prompt-card')
  const reduceMotion = settings.reduceMotion || settings.disableAnimations
  const prompts: Array<PromptQuestion & { priority?: number }> = useMemo(() => sceneState?.promptBubbles.map((prompt) => ({ id: prompt.id, label: prompt.label, question: prompt.question, explanation: '', priority: prompt.priority })) ?? [], [sceneState])

  const prepareSpread = useCallback(async (pdf: PDFDocumentProxy, sourceId: string, nextSpreadStart: number, background = false, generation = loadGenerationRef.current) => {
    const range = pageRange(nextSpreadStart, pdf.numPages)
    const cacheKey = `${sourceId}:${range.pageStart}-${range.pageEnd}`
    const cached = sceneCacheRef.current.get(cacheKey)
    if (cached) {
      if (!background && generation === loadGenerationRef.current && activeSpreadRef.current === cacheKey) { setPages(cached.pages); setSceneState(cached.sceneState) }
      return
    }
    if (!background) setLoading(true)
    try {
      let task = inFlightSpreadsRef.current.get(cacheKey)
      if (!task) {
        task = Promise.all([renderPage(pdf, range.pageStart), range.pageEnd !== range.pageStart ? renderPage(pdf, range.pageEnd) : Promise.resolve(null)]).then((rendered) => {
          const visiblePages = rendered.filter((page): page is RenderedPage => Boolean(page))
          const graph = getContentNarrativeGraph(sourceId)
          const sceneState = graph
            ? new StoryResolver(graph).resolvePage(range.pageStart, accessibilityProfile?.aiProfile ?? null) ?? indexedState(sourceId, visiblePages)
            : indexedState(sourceId, visiblePages)
          return { pages: visiblePages, sceneState }
        })
        inFlightSpreadsRef.current.set(cacheKey, task)
      }
      const result = await task
      if (generation !== loadGenerationRef.current) return
      sceneCacheRef.current.set(cacheKey, result)
      if (!background && activeSpreadRef.current === cacheKey) {
        setPages(result.pages)
        setSceneState(result.sceneState)
        setLoading(false)
      }
    } catch (error) {
      if (generation !== loadGenerationRef.current) return
      if (!background) console.warn('[MagiFab] Book range companion preparation failed; showing local reading context.', error)
      const initialSceneState = fallbackState(sourceId, range.pageStart, range.pageEnd)
      const current = sceneCacheRef.current.get(cacheKey)
      sceneCacheRef.current.set(cacheKey, { pages: current?.pages ?? [], sceneState: initialSceneState })
      if (!background && activeSpreadRef.current === cacheKey) setSceneState(initialSceneState)
    } finally {
      inFlightSpreadsRef.current.delete(cacheKey)
      if (!background && generation === loadGenerationRef.current && activeSpreadRef.current === cacheKey) setLoading(false)
    }
  }, [accessibilityProfile?.aiProfile])

  useEffect(() => {
    if (!document || !bookId) return
    const range = pageRange(spreadStart, pageCount)
    const cacheKey = `${bookId}:${range.pageStart}-${range.pageEnd}`
    activeSpreadRef.current = cacheKey
    const generation = loadGenerationRef.current
    void prepareSpread(document, bookId, spreadStart, false, generation)
    const nextStart = range.pageEnd + 1
    if (nextStart <= pageCount) void prepareSpread(document, bookId, nextStart, true, generation)
  }, [bookId, document, prepareSpread, spreadStart])

  useEffect(() => {
    if (!document || !bookId) return
    const generation = loadGenerationRef.current
    let cancelled = false
    const indexRemainingSpreads = async () => {
      for (let pageStart = 1; pageStart <= pageCount && !cancelled && generation === loadGenerationRef.current; pageStart += 2) {
        await prepareSpread(document, bookId, pageStart, true, generation)
      }
    }
    void indexRemainingSpreads()
    return () => { cancelled = true }
  }, [bookId, document, pageCount, prepareSpread])

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
    const generation = ++loadGenerationRef.current
    overlays.closeAll()
    setActiveBubble(null)
    setLoading(true)
    try {
      const pdf = await getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise
      if (generation !== loadGenerationRef.current) { await pdf.destroy(); return }
      if (document) await document.destroy()
      sceneCacheRef.current.clear()
      inFlightSpreadsRef.current.clear()
      setDocument(pdf); setBookId(`${file.name}-${file.size}-${file.lastModified}`); setTitle(file.name.replace(/\.pdf$/i, '')); setPageCount(pdf.numPages); setSpreadStart(1); setPages([]); setSceneState(null)
    } catch (error) {
      if (generation === loadGenerationRef.current) console.warn('[MagiFab] PDF load failed', error)
    } finally { if (generation === loadGenerationRef.current) setLoading(false) }
  }
  useEffect(() => () => {
    loadGenerationRef.current += 1
    void document?.destroy()
  }, [document])
  const turn = (direction: -1 | 1) => setSpreadStart((current) => direction === 1 ? Math.min(Math.max(1, pageCount - 1), current + 2) : Math.max(1, current - 2))
  const activePrompt = prompts[0]
  const showBubble = (prompt: PromptQuestion, position?: { left: number; top: number }) => {
    setActiveBubble({ id: prompt.id, question: prompt.question, title: prompt.label, relationship: 'Reading companion', explanation: sceneState?.sceneSummary ?? '', anchor: { x: 50, y: 42 }, highlightTarget: false, absolutePosition: position })
    overlays.open('prompt-card')
  }

  return <main className="movie-experience viewer-page book-viewer-page">
    <input ref={inputRef} type="file" accept="application/pdf" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (file) void loadFile(file) }}/>
    <header className="top-bar"><div className="left-cluster"><button className="ghost-btn" onClick={onBack}><ChevronLeft size={16}/>Back</button><div><p className="eyebrow">Reading Mode</p><h2>{title}</h2></div></div><div className="right-cluster"><button className="ghost-btn" onClick={() => inputRef.current?.click()}><Upload size={16}/>Open PDF</button><button className="ghost-btn" onClick={() => overlays.open('prompt-guide')}><Sparkles size={16}/>Prompts</button><button className="ghost-btn" onClick={() => overlays.open('story-companion')}><BookOpen size={16}/>Visual Drawer</button></div></header>
    {!document ? <section className="book-upload"><FileText size={42}/><h1>Open a storybook PDF</h1><p>The original PDF stays the source of truth. MagiFab renders each page and its selectable text layer directly in the reader.</p><button className="primary-btn" onClick={() => inputRef.current?.click()}><Upload size={16}/>Choose PDF</button></section> : <section ref={stageRef} className="book-stage">
      <div className="book-toolbar"><span>Pages {pageRange(spreadStart, pageCount).pageStart}–{pageRange(spreadStart, pageCount).pageEnd} of {pageCount}</span>{loading ? <span><Loader2 className="spin" size={15}/> Loading pages</span> : <span>Help is ready when you are</span>}</div>
      <div ref={readingSurfaceRef} className="book-reading-surface">
      <div ref={bookRef} className={`storybook ${reduceMotion ? 'reduced-motion' : ''}`} role="region" aria-label="PDF storybook" tabIndex={0} onPointerDown={(event) => { dragStartRef.current = event.clientX }} onPointerUp={(event) => { const start = dragStartRef.current; dragStartRef.current = null; if (start !== null && Math.abs(event.clientX - start) > 55) turn(event.clientX < start ? 1 : -1) }}>
        <span className="book-navigation-zone left" aria-hidden="true"/><span className="book-navigation-zone right" aria-hidden="true"/>
        <button ref={leftTurnRef} className="book-turn left" onClick={() => turn(-1)} disabled={spreadStart <= 1} aria-label="Previous pages"><ChevronLeft/></button>
        <div key={spreadStart} className="book-spread page-turn"><PdfPage page={pages[0] ?? null} side="left"/><span className="book-spine"/><PdfPage page={pages[1] ?? null} side="right"/></div>
        <button ref={rightTurnRef} className="book-turn right" onClick={() => turn(1)} disabled={spreadStart + 1 >= pageCount} aria-label="Next pages"><ChevronRight/></button>
      </div>
      <BookPromptBubbles prompts={prompts} stageRef={stageRef} surfaceRef={readingSurfaceRef} bookRef={bookRef} leftTurnRef={leftTurnRef} rightTurnRef={rightTurnRef} drawerOpen={drawerOpen || promptOpen} onSelect={showBubble} onOverflow={() => overlays.open('prompt-guide')}/>
      </div>
      <div className="book-actions"><button className="ghost-btn" onClick={() => turn(-1)} disabled={spreadStart <= 1}><ChevronLeft size={16}/>Previous</button><button className="ghost-btn" onClick={() => overlays.open('story-companion')}><BookOpen size={16}/>Explore this page</button><button className="ghost-btn" onClick={() => turn(1)} disabled={spreadStart + 1 >= pageCount}>Next<ChevronRight size={16}/></button></div>
      <FloatingBubble content={activeBubble} theme="sun" reduceMotion={reduceMotion} visible={promptCardOpen} onOpenCompanion={() => { setActiveBubble(null); overlays.open('aster') }} onClose={() => { setActiveBubble(null); overlays.close('prompt-card') }}/>
      {!drawerOpen && !promptOpen && <button type="button" className="companion-launcher" onClick={() => overlays.open('aster')} aria-label={`Open ${profile?.name ?? 'Lumi'} companion`}><CompanionAvatar appearance={accessibilityProfile?.companionProfile?.appearance} name={profile?.name ?? 'Lumi'} /><span>{profile?.name ?? 'Lumi'}</span></button>}
      <CompanionWidget open={widgetOpen} name={profile?.name ?? 'Lumi'} message={sceneState?.conversation.sceneExplanation ?? 'Choose a prompt to explore this part of the story.'} theme="sun" onClose={() => overlays.close('aster')} reduceMotion={reduceMotion}/>
      <PromptPanel open={promptOpen} prompts={prompts} selectedPromptId={activePrompt?.id ?? ''} onSelectPrompt={showBubble} onClose={() => overlays.close('prompt-guide')}/>
      <VisualDrawer open={drawerOpen} sceneState={sceneState} onClose={() => overlays.close('story-companion')} presentation="book-sheet"/>
    </section>}
  </main>
}
