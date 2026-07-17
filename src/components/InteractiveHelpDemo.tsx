import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import { useState } from 'react'

const examples = [
  { prompt: 'Who is that?', response: 'That is Elara. She is the garden keeper’s daughter, and she is trying to protect the glowing seed.' },
  { prompt: "What’s happening?", response: 'Elara is showing her friend the seed because it may help them find the hidden path home.' },
  { prompt: 'Why does it matter?', response: 'The seed is important because it glows near the secret exit. It gives them hope when they feel lost.' },
]

export function InteractiveHelpDemo() {
  const [active, setActive] = useState(0)
  const reduceMotion = useReducedMotion()
  return <div className="rounded-lg border border-white/15 bg-white/5 p-7"><div className="flex items-center gap-3 text-xs font-bold tracking-wider text-amber-300"><span className="grid h-9 w-9 place-items-center rounded-full bg-amber-200 text-slate-900"><Sparkles size={16}/></span>MAGIFAB IS HERE</div><h3 className="mt-7 font-serif text-3xl">Need a little help<br/>with this moment?</h3><div className="mt-5 space-y-3">{examples.map((example, index) => <button key={example.prompt} onClick={() => setActive(index)} aria-pressed={active === index} className={`flex w-full items-center justify-between rounded-full border px-4 py-3 text-left text-sm transition ${active === index ? 'border-amber-300 bg-amber-300/15 text-white shadow-[0_0_20px_rgba(252,211,77,.12)]' : 'border-white/15 bg-white/5 hover:border-amber-300'}`}><span>{example.prompt}</span><span className="text-amber-300">+</span></button>)}</div><AnimatePresence mode="wait">{active >= 0 && <motion.div key={examples[active].prompt} initial={reduceMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }} transition={{ duration: reduceMotion ? 0 : .22 }} className="mt-5 rounded-2xl rounded-tl-sm border border-white/15 bg-white/[.08] p-4 text-sm leading-6 text-blue-50"><span className="block text-[10px] font-bold tracking-[.16em] text-amber-200">LUMI EXPLAINS</span><p className="mt-1">{examples[active].response}</p></motion.div>}</AnimatePresence></div>
}
