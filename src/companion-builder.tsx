import { motion } from 'framer-motion'
import { Bot, Cat, Check, Circle, Dog, Feather, Leaf, Orbit, PawPrint, PersonStanding, Sparkles, WandSparkles } from 'lucide-react'
import { useMemo, useState } from 'react'

export type CompanionProfile = {
  name: string
  appearance: string
  personality: string
  voice: string
  voiceSpeed: string
  speakingStyle: string
  interactionMode: string
  conversationStyle: string
  emotionalSupport: string
}

type Appearance = { name: string; Icon: typeof Sparkles; tone: string; iconTone: string }

const appearances: Appearance[] = [
  { name: 'Human', Icon: PersonStanding, tone: 'from-rose-200 to-amber-100', iconTone: 'text-rose-600' },
  { name: 'Robot', Icon: Bot, tone: 'from-cyan-200 to-blue-100', iconTone: 'text-cyan-700' },
  { name: 'Fox', Icon: PawPrint, tone: 'from-orange-200 to-amber-100', iconTone: 'text-orange-600' },
  { name: 'Owl', Icon: Feather, tone: 'from-violet-200 to-indigo-100', iconTone: 'text-violet-700' },
  { name: 'Dog', Icon: Dog, tone: 'from-yellow-200 to-orange-100', iconTone: 'text-amber-700' },
  { name: 'Cat', Icon: Cat, tone: 'from-pink-200 to-rose-100', iconTone: 'text-pink-600' },
  { name: 'Bear', Icon: PawPrint, tone: 'from-stone-300 to-amber-100', iconTone: 'text-stone-700' },
  { name: 'Fantasy Spirit', Icon: WandSparkles, tone: 'from-fuchsia-200 to-indigo-100', iconTone: 'text-fuchsia-700' },
  { name: 'Alien', Icon: Orbit, tone: 'from-lime-200 to-emerald-100', iconTone: 'text-emerald-700' },
  { name: 'Floating Orb', Icon: Circle, tone: 'from-sky-200 to-violet-100', iconTone: 'text-sky-600' },
]

const personalities = [
  ['Friendly', 'Warm, welcoming, and easy to talk to.'],
  ['Patient', 'I’ll take things at your pace, without rushing.'],
  ['Teacher', 'I explain things clearly and step by step.'],
  ['Storyteller', 'I make each scene feel connected and meaningful.'],
  ['Calm', 'A quiet, reassuring presence whenever you need me.'],
  ['Cheerful', 'I bring light energy and a bright perspective.'],
  ['Funny', 'I keep explanations playful when it fits the moment.'],
  ['Curious', 'I notice details and love exploring them with you.'],
  ['Supportive', 'I’m here to help you feel confident and understood.'],
  ['Encouraging', 'I celebrate your progress and cheer you on.'],
] as const

const names = ['Nova', 'Lumi', 'Echo', 'Sage', 'Milo', 'Kai', 'Aster', 'Orion']
const interactionModes = ['Only when I ask', 'Occasionally', 'Whenever something important happens', 'Stay beside me throughout the movie']
const emotionalSupport = ['Celebrate when I understand something', 'Encourage me if I seem confused', 'Stay quiet', 'Use positive reinforcement', 'React to emotional scenes']
const conversationStyles = ['Short responses', 'Natural conversations', 'Detailed explanations', 'Ask me questions', 'Explain using examples']

function SelectButton({ active, children, onClick, compact = false }: { active: boolean; children: React.ReactNode; onClick: () => void; compact?: boolean }) {
  return <button type="button" onClick={onClick} className={`rounded-xl border text-left transition ${compact ? 'px-3 py-2 text-xs' : 'px-3 py-3 text-sm'} ${active ? 'border-amber-300 bg-amber-300/15 text-white shadow-[0_0_0_1px_rgba(252,211,77,.15)]' : 'border-white/10 bg-white/[.035] text-blue-100 hover:border-blue-200/50 hover:bg-white/[.08]'}`}><span className="flex items-center gap-2"><span className={`grid h-4 w-4 shrink-0 place-items-center rounded-full border ${active ? 'border-amber-300 bg-amber-300 text-slate-900' : 'border-white/30'}`}>{active && <Check size={10} strokeWidth={3}/>}</span>{children}</span></button>
}

function BuilderSection({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return <section className="border-b border-white/10 pb-7 last:border-0"><p className="text-[10px] font-bold tracking-[.18em] text-amber-300">{eyebrow}</p><h3 className="mt-1 font-serif text-2xl text-white">{title}</h3><div className="mt-4">{children}</div></section>
}

function Avatar({ appearance, size = 'large' }: { appearance: Appearance; size?: 'small' | 'large' }) {
  const { Icon } = appearance
  return <div className={`grid place-items-center rounded-[32%] bg-gradient-to-br ${appearance.tone} shadow-lg ${size === 'large' ? 'h-28 w-28' : 'h-12 w-12 rounded-2xl'}`}><Icon className={`${appearance.iconTone} ${size === 'large' ? 'h-14 w-14' : 'h-6 w-6'}`} strokeWidth={1.7}/></div>
}

export function CompanionBuilder({ onBack, onComplete }: { onBack: () => void; onComplete: (profile: CompanionProfile) => void }) {
  const [profile, setProfile] = useState<CompanionProfile>({ name: 'Lumi', appearance: 'Robot', personality: 'Patient', voice: 'Neutral', voiceSpeed: 'Normal', speakingStyle: 'Conversational', interactionMode: 'Occasionally', conversationStyle: 'Natural conversations', emotionalSupport: 'Encourage me if I seem confused' })
  const update = <K extends keyof CompanionProfile>(key: K, value: CompanionProfile[K]) => setProfile(current => ({ ...current, [key]: value }))
  const selectedAppearance = appearances.find(item => item.name === profile.appearance) ?? appearances[1]
  const personalityDescription = personalities.find(([name]) => name === profile.personality)?.[1] ?? ''
  const sample = useMemo(() => {
    const opening = profile.personality === 'Teacher' ? "I'll explain each moment clearly, step by step." : profile.personality === 'Storyteller' ? "I'll help you notice the threads that make this story shine." : profile.personality === 'Funny' ? "I'll keep the clues clear and the mood a little lighter." : "I'll help you understand the story without interrupting your movie."
    const ending = profile.interactionMode === 'Only when I ask' ? 'Just tap a prompt whenever you want me.' : profile.interactionMode === 'Stay beside me throughout the movie' ? "I'll stay close and gently guide you as the story unfolds." : 'Whenever something matters, I’ll be ready with a gentle nudge.'
    return `Hi Alex! I’m ${profile.name}. ${opening} ${ending}`
  }, [profile.name, profile.personality, profile.interactionMode])

  const generateName = () => update('name', names[Math.floor(Math.random() * names.length)])

  return <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,.8fr)]">
    <div className="max-h-[54vh] space-y-7 overflow-y-auto pr-1 xl:max-h-[58vh] xl:pr-4">
      <BuilderSection eyebrow="01 / LOOK & FEEL" title="Choose appearance"><div className="grid grid-cols-2 gap-2 sm:grid-cols-5">{appearances.map(item => <button type="button" key={item.name} onClick={() => update('appearance', item.name)} className={`relative flex flex-col items-center rounded-2xl border p-2.5 text-[11px] font-semibold transition ${profile.appearance === item.name ? 'border-amber-300 bg-amber-300/15 text-amber-100' : 'border-white/10 bg-white/[.035] text-blue-100 hover:border-white/30'}`}><Avatar appearance={item} size="small"/><span className="mt-2 text-center leading-3">{item.name}</span>{profile.appearance === item.name && <span className="absolute right-1.5 top-1.5 grid h-4 w-4 place-items-center rounded-full bg-amber-300 text-slate-900"><Check size={10} strokeWidth={3}/></span>}</button>)}</div></BuilderSection>
      <BuilderSection eyebrow="02 / PERSONALITY" title="How should they feel?"><div className="grid gap-2 sm:grid-cols-2">{personalities.map(([name, description]) => <button type="button" key={name} onClick={() => update('personality', name)} className={`rounded-xl border p-3 text-left transition ${profile.personality === name ? 'border-amber-300 bg-amber-300/15' : 'border-white/10 bg-white/[.035] hover:border-white/30'}`}><div className="flex items-center gap-2 text-sm font-semibold text-white"><span className={`grid h-4 w-4 place-items-center rounded-full border ${profile.personality === name ? 'border-amber-300 bg-amber-300 text-slate-900' : 'border-white/30'}`}>{profile.personality === name && <Check size={10} strokeWidth={3}/>}</span>{name}</div><p className="mt-1 pl-6 text-xs leading-4 text-blue-200">{description}</p></button>)}</div></BuilderSection>
      <BuilderSection eyebrow="03 / VOICE" title="Choose their voice"><div className="grid gap-4 sm:grid-cols-3"><div><p className="mb-2 text-xs font-semibold text-blue-100">Voice</p><div className="space-y-1.5">{['Female', 'Male', 'Neutral'].map(value => <SelectButton key={value} compact active={profile.voice === value} onClick={() => update('voice', value)}>{value}</SelectButton>)}</div></div><div><p className="mb-2 text-xs font-semibold text-blue-100">Voice speed</p><div className="space-y-1.5">{['Slow', 'Normal', 'Fast'].map(value => <SelectButton key={value} compact active={profile.voiceSpeed === value} onClick={() => update('voiceSpeed', value)}>{value}</SelectButton>)}</div></div><div><p className="mb-2 text-xs font-semibold text-blue-100">Speaking style</p><div className="space-y-1.5">{['Simple', 'Conversational', 'Detailed', 'Encouraging'].map(value => <SelectButton key={value} compact active={profile.speakingStyle === value} onClick={() => update('speakingStyle', value)}>{value}</SelectButton>)}</div></div></div></BuilderSection>
      <BuilderSection eyebrow="04 / A NAME JUST FOR YOU" title="What will you call them?"><div className="flex flex-col gap-3 sm:flex-row"><input value={profile.name} onChange={event => update('name', event.target.value || 'Companion')} aria-label="Companion name" maxLength={24} className="min-w-0 flex-1 rounded-xl border border-white/15 bg-white/[.06] px-4 py-3 text-sm font-semibold text-white outline-none placeholder:text-blue-300 focus:border-amber-300" placeholder="Enter a name"/><button type="button" onClick={generateName} className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-300/50 bg-amber-300/10 px-4 py-3 text-sm font-semibold text-amber-100 transition hover:bg-amber-300/20"><Sparkles size={15}/>Surprise me</button></div><div className="mt-3 flex flex-wrap gap-1.5">{names.map(name => <button type="button" key={name} onClick={() => update('name', name)} className={`rounded-full border px-2.5 py-1 text-xs transition ${profile.name === name ? 'border-amber-300 bg-amber-300 text-slate-900' : 'border-white/15 text-blue-100 hover:border-white/35'}`}>{name}</button>)}</div></BuilderSection>
      <BuilderSection eyebrow="05 / DURING THE MOVIE" title="How should they interact?"><p className="mb-2 text-xs text-blue-200">How should your companion interact during movies?</p><div className="grid gap-2 sm:grid-cols-2">{interactionModes.map(value => <SelectButton key={value} active={profile.interactionMode === value} onClick={() => update('interactionMode', value)}>{value}</SelectButton>)}</div></BuilderSection>
      <BuilderSection eyebrow="06 / EMOTIONAL SUPPORT" title="How should they support you?"><div className="grid gap-2 sm:grid-cols-2">{emotionalSupport.map(value => <SelectButton key={value} active={profile.emotionalSupport === value} onClick={() => update('emotionalSupport', value)}>{value}</SelectButton>)}</div></BuilderSection>
      <BuilderSection eyebrow="07 / CONVERSATION" title="Choose a conversation style"><div className="grid gap-2 sm:grid-cols-2">{conversationStyles.map(value => <SelectButton key={value} active={profile.conversationStyle === value} onClick={() => update('conversationStyle', value)}>{value}</SelectButton>)}</div></BuilderSection>
    </div>
    <aside className="xl:sticky xl:top-0 xl:self-start"><p className="mb-2 text-[10px] font-bold tracking-[.18em] text-amber-300">LIVE PREVIEW</p><motion.div layout className="overflow-hidden rounded-3xl border border-white/15 bg-[radial-gradient(circle_at_78%_12%,rgba(245,190,77,.22),transparent_27%),linear-gradient(155deg,#173d70,#0b2149)] p-5 shadow-xl"><div className="flex items-start justify-between"><Avatar appearance={selectedAppearance}/><span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1 text-[10px] font-bold tracking-wider text-blue-100">{profile.voice} · {profile.voiceSpeed}</span></div><motion.div key={`${profile.name}-${profile.personality}-${profile.speakingStyle}-${profile.interactionMode}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-5"><h3 className="font-serif text-3xl text-white">{profile.name}</h3><p className="mt-1 text-sm text-amber-200">{profile.personality} companion · {profile.speakingStyle} voice</p><p className="mt-4 rounded-2xl rounded-tl-sm bg-white/[.12] p-3 text-sm leading-6 text-blue-50">“{sample}”</p></motion.div><div className="mt-5 flex flex-wrap gap-1.5">{['Who is that?', 'What just happened?', 'Why does it matter?'].map(prompt => <span key={prompt} className="rounded-full border border-white/15 bg-white/[.06] px-2.5 py-1 text-[10px] text-blue-100">{prompt}</span>)}</div></motion.div><div className="mt-4 rounded-2xl border border-amber-200/15 bg-amber-200/10 p-3 text-xs leading-5 text-amber-50"><span className="font-bold">{profile.personality} by design.</span> {personalityDescription}</div></aside>
    <div className="col-span-full flex items-center justify-between border-t border-white/10 pt-5"><button type="button" onClick={onBack} className="text-sm font-semibold text-blue-100 hover:text-white">← Back</button><button type="button" onClick={() => onComplete(profile)} className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-3 text-sm font-bold text-slate-900 shadow-lg shadow-amber-400/15"><Sparkles size={15}/>Create my companion</button></div>
  </div>
}
