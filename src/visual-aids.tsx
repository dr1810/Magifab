import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, MapPin, Sparkles } from 'lucide-react'
import type { Prompt, VisualAidKind } from './movie-data'
import { useAccessibility } from './accessibility-context'

type AidProps = { prompt: Prompt }
const Label = ({ children }: { children: React.ReactNode }) => (
  <p className="text-[10px] font-bold tracking-[.18em] text-amber-200 uppercase">{children}</p>
)

const Person = ({ name, tone, position }: { name: string; tone: string; position: string }) => (
  <div className={`absolute ${position} flex flex-col items-center gap-1.5`}>
    <span className={`h-11 w-11 rounded-[45%] border-2 border-white/50 ${tone} shadow-lg`} />
    <span className="text-[10px] font-semibold text-white">{name}</span>
  </div>
)

export function RelationshipDiagram() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'
  const isColorBlind = settings.colorBlindPalette

  const elaraColor = isColorBlind ? 'bg-orange-400' : 'bg-rose-300'
  const rowanColor = isColorBlind ? 'bg-sky-400' : 'bg-cyan-300'
  const lineColor = isHighContrast
    ? 'bg-white h-0.5'
    : 'bg-gradient-to-r from-rose-200 via-amber-100 to-cyan-200 h-px'
  const textBg = isHighContrast ? 'bg-slate-900 border border-white' : 'bg-white/10'

  return (
    <div className="relative h-28">
      <div className={`absolute left-[24%] top-8 w-[51%] ${lineColor}`} />
      <span className={`absolute left-1/2 top-3 -translate-x-1/2 rounded-full px-2 py-1 text-[9px] text-blue-100 ${textBg}`}>
        trusting each other
      </span>
      <Person name="Elara" tone={elaraColor} position="left-[13%] top-9" />
      <Person name="Rowan" tone={rowanColor} position="right-[13%] top-9" />
      <div className="absolute left-1/2 top-14 grid h-8 w-8 -translate-x-1/2 place-items-center rounded-full bg-amber-200 text-[#17325a] shadow-[0_0_22px_rgba(252,211,77,.65)]">
        <Sparkles size={15} />
      </div>
    </div>
  )
}

export function TimelineDiagram() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'
  const isColorBlind = settings.colorBlindPalette

  const foundTone = isColorBlind ? 'bg-sky-400' : 'bg-cyan-300'
  const planTone = isColorBlind ? 'bg-amber-300' : 'bg-amber-200'
  const leaveTone = isColorBlind ? 'bg-orange-400' : 'bg-rose-300'

  const timelineSteps = [
    { text: 'Found the seed', tone: foundTone },
    { text: 'Made a plan', tone: planTone },
    { text: 'Leaving now', tone: leaveTone },
  ]

  const lineBg = isHighContrast ? 'bg-white' : 'bg-white/15'
  const indicatorBg = isHighContrast ? 'bg-white border border-white text-white' : 'bg-amber-200 text-[#19345c]'

  return (
    <div className="relative flex h-28 items-center justify-between px-2">
      <div className={`absolute left-6 right-6 top-1/2 h-1 -translate-y-1/2 rounded-full ${lineBg}`} />
      {timelineSteps.map((step, index) => (
        <div key={step.text} className="z-10 flex flex-col items-center gap-2">
          <span className={`h-5 w-5 rounded-full border-4 border-[#183965] ${step.tone}`} />
          <span className="max-w-16 text-center text-[10px] leading-3 text-blue-100">{step.text}</span>
          {index === 2 && (
            <span className={`absolute -bottom-1 rounded-full px-2 py-0.5 text-[9px] font-bold ${indicatorBg}`}>
              now
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

export function CauseEffectDiagram() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'

  const blockClass = isHighContrast
    ? 'border border-white bg-slate-900 text-white'
    : 'bg-white/10 text-white'

  const step1Color = isHighContrast ? '' : 'text-cyan-100 bg-cyan-200/20'
  const step2Color = isHighContrast ? '' : 'text-amber-100 bg-amber-200/20'
  const step3Color = isHighContrast ? '' : 'text-rose-100 bg-rose-200/20'

  return (
    <div className="flex h-28 items-center justify-center gap-2 sm:gap-4">
      <div className={`rounded-2xl px-3 py-3 text-center text-[10px] font-semibold ${blockClass} ${step1Color}`}>
        Storm
        <br />
        is coming
      </div>
      <ArrowRight className="text-amber-200" size={20} />
      <div className={`rounded-2xl px-3 py-3 text-center text-[10px] font-semibold ${blockClass} ${step2Color}`}>
        They use
        <br />
        the seed
      </div>
      <ArrowRight className="text-amber-200" size={20} />
      <div className={`rounded-2xl px-3 py-3 text-center text-[10px] font-semibold ${blockClass} ${step3Color}`}>
        They can
        <br />
        find home
      </div>
    </div>
  )
}

export function EmotionDiagram() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'

  const lineClass = isHighContrast ? 'bg-white h-0.5' : 'bg-white/20 h-px'
  const elaraGrad = isHighContrast ? 'bg-white border border-white' : 'bg-gradient-to-t from-rose-400/60 to-amber-200/70'
  const rowanGrad = isHighContrast ? 'bg-white border border-white' : 'bg-gradient-to-t from-cyan-500/60 to-cyan-200/70'

  return (
    <div className="relative flex h-28 items-end justify-around px-6">
      <div className="flex flex-col items-center gap-2">
        <div className={`h-16 w-16 rounded-t-full rounded-b-[35%] ${elaraGrad}`} />
        <span className="text-[10px] text-rose-100">Elara · hopeful</span>
      </div>
      <div className="flex flex-col items-center gap-2">
        <div className={`h-10 w-16 rounded-t-full rounded-b-[35%] ${rowanGrad}`} />
        <span className="text-[10px] text-cyan-100">Rowan · worried</span>
      </div>
      <div className={`absolute left-[30%] right-[30%] top-4 ${lineClass}`} />
    </div>
  )
}

export function ObjectDiagram() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'
  const reduceDistractions = settings.reduceDistractions

  const fillClass = isHighContrast ? 'bg-white border border-white' : 'bg-amber-200/15'
  const seedBg = isHighContrast ? 'bg-white text-black' : 'bg-gradient-to-br from-amber-100 to-amber-300 text-[#234168]'
  const tagClass = isHighContrast ? 'border border-white bg-slate-900 text-white' : 'border border-white/20 bg-white/5 text-blue-100'

  return (
    <div className="relative grid h-28 place-items-center">
      {!reduceDistractions && (
        <div className={`absolute h-20 w-20 rounded-full blur-xl ${fillClass}`} />
      )}
      <div className={`z-10 grid h-12 w-12 place-items-center rounded-[45%] shadow-[0_0_26px_rgba(252,211,77,.7)] ${seedBg}`}>
        <Sparkles size={23} />
      </div>
      <span className={`absolute left-[13%] top-5 rounded-full px-2 py-1 text-[9px] ${tagClass}`}>
        guides them
      </span>
      <span className={`absolute right-[11%] bottom-5 rounded-full px-2 py-1 text-[9px] ${tagClass}`}>
        glows near exit
      </span>
    </div>
  )
}

export function Memory() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'
  const tagClass = isHighContrast ? 'border border-white bg-slate-900 text-white' : 'border border-white/20 bg-white/10 text-blue-100'
  const nowClass = isHighContrast ? 'border border-white bg-slate-900 text-amber-200' : 'bg-amber-200/20 text-amber-100'

  return (
    <div className="flex h-28 items-center justify-center gap-3">
      <div className={`rounded-2xl px-4 py-3 text-center text-[10px] ${tagClass}`}>
        Before
        <br />
        <b className="text-white">Moon gate</b>
      </div>
      <ArrowRight className="text-amber-200" size={20} />
      <div className={`rounded-2xl px-4 py-3 text-center text-[10px] ${nowClass}`}>
        Now
        <br />
        <b>Follow the seed</b>
      </div>
    </div>
  )
}

export function Location() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'
  const containerClass = isHighContrast ? 'border border-white bg-slate-900 text-white' : 'border border-cyan-100/35 bg-cyan-200/10 text-cyan-100'
  const lineClass = isHighContrast ? 'bg-white' : 'bg-amber-200/70'

  return (
    <div className="grid h-28 place-items-center">
      <div className={`relative h-20 w-48 rounded-[45%] ${containerClass}`}>
        <MapPin className="absolute left-[30%] top-5 text-rose-200" size={23} />
        <span className="absolute right-4 top-6 text-[10px]">Glasshouse</span>
        <div className={`absolute bottom-3 left-4 right-5 h-px ${lineClass}`} />
      </div>
    </div>
  )
}

export function Conversation() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'
  const bubble1 = isHighContrast ? 'border border-white bg-slate-900 text-white' : 'bg-rose-200/20 text-rose-100'
  const bubble2 = isHighContrast ? 'border border-white bg-slate-900 text-white' : 'bg-cyan-200/20 text-cyan-100'

  return (
    <div className="flex h-28 items-center justify-center gap-3">
      <span className={`rounded-2xl rounded-bl-sm px-3 py-2 text-[10px] ${bubble1}`}>“Trust me.”</span>
      <span className={`rounded-2xl rounded-br-sm px-3 py-2 text-[10px] ${bubble2}`}>“I do.”</span>
    </div>
  )
}

export function Summary() {
  const { settings } = useAccessibility()
  const isHighContrast = settings.contrast === 'High Contrast'
  const c1 = isHighContrast ? 'border border-white' : 'bg-cyan-200/40'
  const c2 = isHighContrast ? 'border border-white' : 'bg-amber-200/60'
  const c3 = isHighContrast ? 'border border-white' : 'bg-rose-200/45'

  return (
    <div className="flex h-28 items-center justify-center gap-3">
      <span className={`h-12 w-12 rounded-full ${c1}`} />
      <ArrowRight className="text-amber-200" />
      <span className={`h-12 w-12 rounded-[40%] ${c2}`} />
      <ArrowRight className="text-amber-200" />
      <span className={`h-12 w-12 rounded-full ${c3}`} />
    </div>
  )
}

const aids: Record<VisualAidKind, () => React.ReactNode> = {
  relationships: RelationshipDiagram,
  timeline: TimelineDiagram,
  cause: CauseEffectDiagram,
  emotion: EmotionDiagram,
  object: ObjectDiagram,
  summary: Summary,
  conversation: Conversation,
  memory: Memory,
  location: Location,
}

export function VisualAid({ prompt }: AidProps) {
  const reduceMotionSetting = useReducedMotion()
  const { settings } = useAccessibility()
  const reduceMotion = settings.reduceMotion || settings.disableAnimations || reduceMotionSetting

  const Aid = aids[prompt.kind] || Summary

  return (
    <motion.section
      key={prompt.id}
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.28 }}
      className={`rounded-3xl border border-white/15 bg-[#112b56]/90 px-4 py-3 shadow-2xl backdrop-blur-xl sm:px-5 ${
        settings.contrast === 'High Contrast' ? 'border-2 border-white bg-black' : ''
      }`}
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <Label>VISUAL CLUE</Label>
          <h2 className="mt-1 font-serif text-lg text-white">{prompt.question}</h2>
        </div>
        <span className="mt-1 rounded-full bg-amber-200/15 px-2.5 py-1 text-[10px] font-semibold text-amber-100">
          simple view
        </span>
      </div>
      <Aid />
      <p className="sr-only">{prompt.answer}</p>
    </motion.section>
  )
}

// Aliases as requested by components list
export { VisualAid as VisualAidCanvas }
