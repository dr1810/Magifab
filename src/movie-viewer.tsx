import { useCallback, useEffect, useMemo, useRef, useState, type FocusEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { CompanionWidget } from './components/CompanionWidget'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import { askCompanion } from './services/assistantService'
import { companionAIService, type SceneExplanation } from './services/ai/CompanionAIService'
import type { CapturedVideoFrame } from './services/ai/VideoFrameCaptureService'
import { objectDetectionService } from './services/detection/ObjectDetectionService'
import { visionUnderstandingService } from './services/vision/VisionUnderstandingService'
import { semanticMovieKnowledge } from './services/semantic/SemanticMovieKnowledge'
import { semanticMatchingService } from './services/semantic/SemanticMatchingService'
import { knowledgeRetriever } from './services/knowledge/KnowledgeRetriever'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
import type { MovieId, PromptQuestion, SceneData } from './types/movie'

type MovieViewerProps = {
  movie: MovieId
  onBack: () => void
  onOpenAccessibilitySettings?: () => void
}

type PromptKnowledge = {
  question: string
  answer: string
  visualAid?: { kind: string; label: string; anchor: { x: number; y: number } }
  relatedCharacters: string[]
  objects: string[]
  timelineContext: string
}

export function MovieViewer({ movie, onBack, onOpenAccessibilitySettings = () => undefined }: MovieViewerProps) {
  const { movie: movieData, scene, loading, totalDuration, updateScene } = useMoviePlayback(movie)
  const { profile } = useCompanionProfile()
  const { settings } = useAccessibility()

  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [volume, setVolume] = useState(72)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [promptOpen, setPromptOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [widgetOpen, setWidgetOpen] = useState(false)
  const [activeBubble, setActiveBubble] = useState<PromptBubbleContent | null>(null)
  const currentSceneIdRef = useRef<string>('')
  const explanationRequestIdRef = useRef(0)
  const frameCaptureRef = useRef<(() => CapturedVideoFrame) | null>(null)
  const isSeekingRef = useRef(false)
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')

  const prompts = scene?.prompts ?? []
  const [selectedPromptId, setSelectedPromptId] = useState<string>('')

  useEffect(() => {
    if (prompts.length > 0) {
      setSelectedPromptId((current) => current || prompts[0].id)
    }
  }, [prompts])

  useEffect(() => {
    const sceneId = scene?.sceneId ?? ''
    currentSceneIdRef.current = sceneId
    setActiveBubble((bubble) => bubble?.id.startsWith(`${sceneId}:`) ? bubble : null)
  }, [scene?.sceneId])

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    if (import.meta.env.DEV) console.debug('[MagiFab playback] viewer resume request', { movieId: movie, currentTimeBeforeResume: currentTime, savedTimestamp })
    setCurrentTime(savedTimestamp)
    if (savedTimestamp > 0) void updateScene(savedTimestamp)
    setActiveBubble(null)
    setWidgetOpen(false)
  }, [movie])

  useEffect(() => {
    if (!movieData) return
    const timer = window.setTimeout(() => savePlaybackTimestamp(movie, currentTime, duration || totalDuration), 300)
    return () => window.clearTimeout(timer)
  }, [currentTime, duration, movie, movieData, totalDuration])

  const selectedPrompt = useMemo(
    () => prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0],
    [prompts, selectedPromptId],
  )

  const buildPromptBubble = useCallback((sceneData: SceneData, prompt: PromptQuestion, target?: { kind: string; label: string; anchor: { x: number; y: number } }): PromptBubbleContent => {
    const normalizedQuestion = prompt.question.trim().toLowerCase()
    const promptLabel = prompt.label.trim().toLowerCase()
    const questionType = normalizedQuestion.includes('who') || promptLabel.includes('who')
      ? 'Who is that?'
      : normalizedQuestion.includes('what') && normalizedQuestion.includes('happened')
        ? 'What just happened?'
        : normalizedQuestion.includes('why') && normalizedQuestion.includes('sad')
          ? 'Why are they sad?'
          : normalizedQuestion.includes('object') || promptLabel.includes('object')
            ? 'What is this object?'
            : normalizedQuestion.includes('why') && normalizedQuestion.includes('matter')
              ? 'Why does it matter?'
              : 'Why did they do that?'

    const knownCharacter = sceneData.characterList.find((character) => {
      const name = character.name.toLowerCase()
      return normalizedQuestion.includes(name) || prompt.explanation.toLowerCase().includes(name)
    }) ?? sceneData.characterList[0]

    const relationship = knownCharacter
      ? sceneData.relationshipGraph.find((edge) => edge.from.includes(knownCharacter.name) || edge.to.includes(knownCharacter.name))
      : undefined

    const title = target?.label || (questionType === 'Who is that?' && knownCharacter
      ? knownCharacter.name
      : prompt.label)

    return {
      id: `${sceneData.sceneId}:${prompt.id}`,
      question: questionType,
      title,
      relationship: target?.kind === 'object' ? sceneData.highlightObject.reason : questionType === 'Who is that?'
        ? relationship?.label ?? knownCharacter?.role ?? 'Character context'
        : sceneData.emotion,
      explanation: prompt.explanation,
      anchor: target?.anchor ?? { x: sceneData.companionPosition.x, y: Math.max(14, Math.min(76, sceneData.companionPosition.y)) },
      highlightTarget: target?.kind === 'character' || target?.kind === 'object' || questionType === 'Who is that?',
    }
  }, [])

  const selectPrompt = (prompt: PromptQuestion) => {
    if (!scene || !movieData || isSeekingRef.current) return
    setSelectedPromptId(prompt.id)
    setPromptOpen(false)
    setDrawerOpen(false)
    setWidgetOpen(false)
    setActiveBubble(null)

    const isCharacterQuestion = /\bwho\b/i.test(prompt.question) || /\bwho\b/i.test(prompt.label)
    const requestId = ++explanationRequestIdRef.current
    const knowledgeRequest = { movieId: movieData.id, sceneId: scene.sceneId, timestamp: scene.timestamp, question: prompt.question }

    if (isCharacterQuestion) {
      const loadingBubble = buildPromptBubble(scene, prompt)
      setActiveBubble({
        ...loadingBubble,
        title: 'Looking closely',
        relationship: '',
        explanation: '',
        highlightTarget: false,
        loading: true,
      })

      void knowledgeRetriever.getOrCreate<SceneExplanation>(knowledgeRequest, async () => {
        const frame = frameCaptureRef.current?.()
        if (!frame) throw new Error('Frame capture is unavailable.')
        const memory = semanticMovieKnowledge.load(movieData)
        const semanticScene = semanticMovieKnowledge.scene(movieData, frame.timestamp)
        const detections = await objectDetectionService.detect(frame)
        const understanding = await visionUnderstandingService.understand(frame, detections.detections)
        const match = semanticMatchingService.match({ detections: detections.detections, understanding, memory, scene: semanticScene })

        if (!match.characterFound || !match.character || !match.anchor || !match.detectionId) {
          return {
            character: null, characterFound: false, confidence: match.confidence,
            emotion: understanding.emotions[0] ?? scene.emotion,
            explanation: 'I can’t confidently identify a visible character in this frame.',
            anchor: { x: scene.companionPosition.x, y: scene.companionPosition.y, width: 12, height: 18 },
            visualAidType: 'highlight',
          }
        }

        semanticMovieKnowledge.recordVerifiedObservation(movieData, semanticScene.sceneId, {
          detectionId: match.detectionId, className: detections.detections.find((item) => item.id === match.detectionId)?.className ?? 'unknown',
          timestamp: frame.timestamp, confidence: match.confidence, characterId: match.character.id, bbox: match.anchor,
        })
        try {
          const response = await companionAIService.personalizeExplanation(prompt.question, {
            character: match.character, scene: { summary: semanticScene.summary, location: semanticScene.location, emotions: semanticScene.emotions, importantEvents: semanticScene.importantEvents },
            visualUnderstanding: { scene: understanding.scene, actions: understanding.actions, emotions: understanding.emotions, interactions: understanding.interactions },
          })
          return { character: match.character.name, characterFound: true, confidence: match.confidence, anchor: match.anchor, visualAidType: 'magnifier', ...response }
        } catch {
          return {
            character: match.character.name, characterFound: true, confidence: match.confidence, anchor: match.anchor, visualAidType: 'magnifier',
            emotion: understanding.emotions[0] ?? scene.emotion,
            explanation: `${match.character.name} is visible here. ${semanticScene.summary}`,
          }
        }
      }).then(({ record }) => {
          if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
          const result = record.value
          const bubble = buildPromptBubble(scene, prompt)
          setActiveBubble({
            ...bubble,
            title: result.characterFound ? result.character ?? 'Character' : 'No person detected',
            relationship: result.characterFound ? result.emotion : 'No visible character',
            explanation: result.explanation,
            anchor: result.characterFound ? { x: result.anchor.x, y: result.anchor.y } : bubble.anchor,
            visualAnchor: result.characterFound ? result.anchor : undefined,
            visualAidType: result.visualAidType,
            highlightTarget: result.characterFound,
          })
          setAssistantText(result.explanation)
          if (settings.voiceAssistance || settings.readPrompts) {
            void speakText({ text: result.explanation, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
          }
        }).catch(() => {
          if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
          setActiveBubble(null)
          setAssistantText('I’m still preparing this explanation. You can try the prompt again in a moment.')
        })
      return
    }

    void knowledgeRetriever.getOrCreate<PromptKnowledge>(knowledgeRequest, async () => {
      const result = await askCompanion(movieData, scene.timestamp, prompt.question)
      return {
        question: prompt.question,
        answer: result.answer,
        visualAid: result.target,
        relatedCharacters: scene.characterList.map((character) => character.name),
        objects: [scene.highlightObject.name],
        timelineContext: scene.timelineData.map((item) => item.label).join(' → '),
      }
    }).then(({ record }) => {
        if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
        const result = record.value
        setActiveBubble(buildPromptBubble(scene, prompt, result.visualAid))
        setAssistantText(result.answer)
        if (settings.voiceAssistance || settings.readPrompts) {
          void speakText({
            text: result.answer,
            rate: settings.voiceSpeed,
            volume: Math.min(1, settings.voiceVolume / 100),
          })
        }
    }).catch(() => {
        if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
        setAssistantText('I’m still preparing this explanation. You can try the prompt again in a moment.')
    })
  }
  const openPromptPanel = () => {
    setDrawerOpen(false)
    setPromptOpen(true)
  }
  const togglePromptPanel = () => {
    setDrawerOpen(false)
    setPromptOpen((open) => !open)
  }
  const openVisualDrawer = () => {
    setPromptOpen(false)
    setDrawerOpen(true)
  }
  const closeBubbles = () => {
    explanationRequestIdRef.current += 1
    setActiveBubble(null)
    setWidgetOpen(false)
    setPromptOpen(false)
    void stopSpeech()
  }

  const handleSeeking = useCallback(() => {
    isSeekingRef.current = true
    explanationRequestIdRef.current += 1
    setActiveBubble(null)
    setWidgetOpen(false)
    void stopSpeech()
  }, [])

  const handleFrameCaptureReady = useCallback((capture: (() => CapturedVideoFrame) | null) => {
    frameCaptureRef.current = capture
  }, [])

  const openCompanionFromBubble = useCallback(() => {
    setWidgetOpen(true)
  }, [])

  const closePromptBubble = useCallback(() => {
    explanationRequestIdRef.current += 1
    setActiveBubble(null)
  }, [])

  if (loading || !movieData || !scene) {
    return (
      <div className="loading-screen">
        <Loader2 className="spin" /> Preparing viewer...
      </div>
    )
  }

  return (
    <main className="movie-experience viewer-page">
      <TopBar
        movie={movieData}
        onBack={() => { savePlaybackTimestamp(movie, currentTime, duration || totalDuration); onBack() }}
        onOpenPrompts={openPromptPanel}
        onOpenDrawer={openVisualDrawer}
      />

      <div className="viewer-layout" style={{ position: 'relative' }}>
        <MoviePlayer
          movie={movieData}
          scene={scene}
          playing={playing}
          muted={muted}
          volume={volume}
          currentTime={currentTime}
          totalTime={duration || totalDuration}
          onPlayToggle={() => setPlaying((value) => !value)}
          onMuteToggle={() => setMuted((value) => !value)}
          onVolumeChange={setVolume}
          onSeek={(next) => {
            setCurrentTime(next)
            void updateScene(next)
          }}
          onTimeChange={(next) => {
            setCurrentTime(next)
            void updateScene(next)
          }}
          onDurationChange={setDuration}
          onSeeking={handleSeeking}
          onSeekComplete={(timestamp) => {
            isSeekingRef.current = false
            setCurrentTime(timestamp)
            updateScene(timestamp, true)
          }}
          onVideoFrameCaptureReady={handleFrameCaptureReady}
          promptOpen={promptOpen}
          onTogglePromptPanel={togglePromptPanel}
          onOpenVisualDrawer={openVisualDrawer}
          onOpenPromptPanel={openPromptPanel}
          onCloseOverlays={() => {
            explanationRequestIdRef.current += 1
            setPromptOpen(false)
            setDrawerOpen(false)
            setActiveBubble(null)
          }}
          onOpenAccessibilitySettings={onOpenAccessibilitySettings}
          onCloseBubbles={closeBubbles}
          reduceMotion={settings.reduceMotion || settings.disableAnimations}
          overlays={
            <>
              <FloatingBubble
                content={activeBubble}
                theme={movieData.companionTheme}
                reduceMotion={settings.reduceMotion || settings.disableAnimations}
                visible={Boolean(activeBubble)}
                onOpenCompanion={openCompanionFromBubble}
                onClose={closePromptBubble}
              />
              <CompanionWidget
                open={widgetOpen}
                name={profile?.name || 'Lumi'}
                message={assistantText}
                theme={movieData.companionTheme}
                onClose={() => setWidgetOpen(false)}
                reduceMotion={settings.reduceMotion || settings.disableAnimations}
              />
              <PromptPanel
                open={promptOpen}
                prompts={prompts}
                selectedPromptId={selectedPrompt?.id ?? ''}
                onSelectPrompt={selectPrompt}
                onClose={() => setPromptOpen(false)}
              />
            </>
          }
          drawerOverlay={
            <VisualDrawer
              open={drawerOpen}
              scene={scene}
              onClose={() => setDrawerOpen(false)}
              onMouseEnter={() => setDrawerOpen(true)}
              onMouseLeave={() => setDrawerOpen(false)}
              onFocus={() => setDrawerOpen(true)}
              onBlur={(event: FocusEvent<HTMLElement>) => {
                if (!event.currentTarget.contains(event.relatedTarget)) setDrawerOpen(false)
              }}
            />
          }
        />
      </div>
    </main>
  )
}
