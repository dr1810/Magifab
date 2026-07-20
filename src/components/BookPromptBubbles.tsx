import { useEffect, useLayoutEffect, useMemo, useState, type CSSProperties, type RefObject } from 'react'
import type { PromptQuestion } from '../types/movie'

type BookPrompt = PromptQuestion & { priority?: number }

type Rect = { left: number; top: number; width: number; height: number }
type Placement = { bubble: Rect; callout: Rect }

type BookPromptBubblesProps = {
  prompts: BookPrompt[]
  stageRef: RefObject<HTMLElement | null>
  surfaceRef: RefObject<HTMLDivElement | null>
  bookRef: RefObject<HTMLDivElement | null>
  leftTurnRef: RefObject<HTMLButtonElement | null>
  rightTurnRef: RefObject<HTMLButtonElement | null>
  drawerOpen: boolean
  onSelect: (prompt: PromptQuestion, callout: { left: number; top: number }) => void
  onOverflow: () => void
}

const bubbleWidth = 220
const bubbleHeight = 58
const calloutWidth = 320
const calloutHeight = 240
const arrowPadding = 120
const edgePadding = 12

function overlaps(first: Rect, second: Rect) {
  return first.left < second.left + second.width && first.left + first.width > second.left && first.top < second.top + second.height && first.top + first.height > second.top
}

function toRect(rect: DOMRect): Rect {
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height }
}

function padded(rect: DOMRect): Rect {
  return { left: rect.left - arrowPadding, top: rect.top - arrowPadding, width: rect.width + arrowPadding * 2, height: rect.height + arrowPadding * 2 }
}

export function BookPromptBubbles({ prompts, stageRef, surfaceRef, bookRef, leftTurnRef, rightTurnRef, drawerOpen, onSelect, onOverflow }: BookPromptBubblesProps) {
  const [placements, setPlacements] = useState<Record<string, Placement>>({})
  const [overflowPlacement, setOverflowPlacement] = useState<Rect | null>(null)
  const [layoutVersion, setLayoutVersion] = useState(0)
  const visiblePrompts = useMemo(() => [...prompts].sort((first, second) => (first.priority ?? Number.MAX_SAFE_INTEGER) - (second.priority ?? Number.MAX_SAFE_INTEGER)).slice(0, 3), [prompts])
  const overflowCount = Math.max(0, prompts.length - visiblePrompts.length)

  useEffect(() => {
    const surface = surfaceRef.current
    if (!surface) return
    const update = () => setLayoutVersion((version) => version + 1)
    const observer = new ResizeObserver(update)
    observer.observe(surface)
    window.addEventListener('resize', update)
    return () => { observer.disconnect(); window.removeEventListener('resize', update) }
  }, [surfaceRef])

  useLayoutEffect(() => {
    const surface = surfaceRef.current
    const stage = stageRef.current
    const book = bookRef.current
    const leftTurn = leftTurnRef.current
    const rightTurn = rightTurnRef.current
    if (!surface || !stage || !book || !leftTurn || !rightTurn || !visiblePrompts.length || drawerOpen) { setPlacements({}); setOverflowPlacement(null); return }

    const surfaceRect = toRect(surface.getBoundingClientRect())
    const stageRect = toRect(stage.getBoundingClientRect())
    const bookRect = toRect(book.getBoundingClientRect())
    const sheets = Array.from(book.querySelectorAll<HTMLElement>('.book-sheet')).map((sheet) => toRect(sheet.getBoundingClientRect()))
    const blocked = [padded(leftTurn.getBoundingClientRect()), padded(rightTurn.getBoundingClientRect()), ...sheets]
    const drawer = document.querySelector<HTMLElement>('.book-visual-sheet')
    if (drawer) blocked.push(toRect(drawer.getBoundingClientRect()))
    const viewport: Rect = { left: edgePadding, top: Math.max(edgePadding, bookRect.top - 8), width: window.innerWidth - edgePadding * 2, height: window.innerHeight - Math.max(edgePadding, bookRect.top - 8) - edgePadding }
    const placed: Rect[] = []
    const safe = (rect: Rect, includePlaced = true) => rect.left >= viewport.left && rect.top >= viewport.top && rect.left + rect.width <= viewport.left + viewport.width && rect.top + rect.height <= viewport.top + viewport.height && !blocked.some((item) => overlaps(rect, item)) && (!includePlaced || !placed.some((item) => overlaps(rect, item)))
    const relative = (rect: Rect): Rect => ({ left: rect.left - surfaceRect.left, top: rect.top - surfaceRect.top, width: rect.width, height: rect.height })
    const next: Record<string, Placement> = {}

    visiblePrompts.forEach((prompt, index) => {
      const paragraph = sheets[index % Math.max(1, sheets.length)] ?? bookRect
      const paragraphY = paragraph.top + paragraph.height * (.24 + (index % 3) * .22)
      const candidates: Rect[] = [
        { left: paragraph.left + paragraph.width + 14, top: paragraphY - bubbleHeight / 2, width: bubbleWidth, height: bubbleHeight },
        { left: paragraph.left - bubbleWidth - 14, top: paragraphY - bubbleHeight / 2, width: bubbleWidth, height: bubbleHeight },
        { left: paragraph.left + (paragraph.width - bubbleWidth) / 2, top: paragraph.top - bubbleHeight - 12, width: bubbleWidth, height: bubbleHeight },
        { left: paragraph.left + (paragraph.width - bubbleWidth) / 2, top: paragraph.top + paragraph.height + 12, width: bubbleWidth, height: bubbleHeight },
      ]
      let bubble = candidates.find((candidate) => safe(candidate))
      if (!bubble) {
        const stackBase = candidates[0]
        bubble = Array.from({ length: 5 }, (_, stackIndex) => ({ ...stackBase, top: stackBase.top + stackIndex * (bubbleHeight + 10) })).find((candidate) => safe(candidate))
      }
      if (!bubble) return
      placed.push(bubble)
      const calloutCandidates: Rect[] = [
        { left: bubble.left + bubble.width + 12, top: bubble.top - 12, width: calloutWidth, height: calloutHeight },
        { left: bubble.left - calloutWidth - 12, top: bubble.top - 12, width: calloutWidth, height: calloutHeight },
        { left: bubble.left + (bubble.width - calloutWidth) / 2, top: bubble.top - calloutHeight - 14, width: calloutWidth, height: calloutHeight },
        { left: bubble.left + (bubble.width - calloutWidth) / 2, top: bubble.top + bubble.height + 14, width: calloutWidth, height: calloutHeight },
      ]
      const callout = calloutCandidates.find((candidate) => safe(candidate))
      if (!callout) { placed.pop(); return }
      next[prompt.id] = { bubble: relative(bubble), callout: { ...relative(callout), left: callout.left - stageRect.left, top: callout.top - stageRect.top } }
    })
    setPlacements(next)
    if (overflowCount) {
      const overflowCandidates: Rect[] = [
        { left: bookRect.left + bookRect.width / 2 - 34, top: bookRect.top + bookRect.height + 12, width: 68, height: 42 },
        { left: bookRect.left + 12, top: bookRect.top + bookRect.height + 12, width: 68, height: 42 },
        { left: bookRect.left + bookRect.width - 80, top: bookRect.top + bookRect.height + 12, width: 68, height: 42 },
      ]
      const overflow = overflowCandidates.find((candidate) => safe(candidate))
      setOverflowPlacement(overflow ? relative(overflow) : null)
    } else setOverflowPlacement(null)
  }, [bookRef, drawerOpen, layoutVersion, leftTurnRef, overflowCount, prompts, rightTurnRef, stageRef, surfaceRef, visiblePrompts])

  if (drawerOpen) return null
  return <>
    {visiblePrompts.map((prompt) => {
      const placement = placements[prompt.id]
      if (!placement) return null
      const style: CSSProperties = { left: placement.bubble.left, top: placement.bubble.top, width: placement.bubble.width }
      return <aside key={prompt.id} className="book-prompt-rail book-prompt-bubble" style={style}><button type="button" onClick={() => onSelect(prompt, { left: placement.callout.left + placement.callout.width / 2, top: placement.callout.top + placement.callout.height })}><span aria-hidden="true">💭</span><span>{prompt.label || prompt.question}</span></button></aside>
    })}
    {overflowCount > 0 && overflowPlacement && <aside className="book-prompt-rail compact book-prompt-overflow" style={overflowPlacement}><button type="button" onClick={onOverflow} aria-label={`Show ${overflowCount} additional prompts`}><span aria-hidden="true">💭</span><span>+{overflowCount}</span></button></aside>}
  </>
}
