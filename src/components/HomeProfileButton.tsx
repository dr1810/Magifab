import { UserRoundCog } from 'lucide-react'

export function HomeProfileButton({ onClick }: { onClick: () => void }) {
  return <button onClick={onClick} aria-label="Open accessibility profile" title="Accessibility Profile" className="fixed right-44 top-7 z-20 grid h-10 w-10 place-items-center rounded-full border border-white/25 bg-white/10 text-amber-200 shadow-lg backdrop-blur transition hover:bg-white/20 focus-visible:outline focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-amber-200 sm:right-48"><UserRoundCog size={18}/><span className="sr-only">Accessibility Profile</span></button>
}
