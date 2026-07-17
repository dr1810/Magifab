import { Bot, Feather, PawPrint, Sparkles, UserRound } from 'lucide-react'
import type { AccessibilityProfile } from '../types/accessibility-profile'

const avatarIcon = (appearance: string) => {
  if (/robot|orb|alien/i.test(appearance)) return Bot
  if (/owl/i.test(appearance)) return Feather
  if (/fox|dog|cat|bear/i.test(appearance)) return PawPrint
  return Sparkles
}

export function CompanionProfileButton({ profile, onClick }: { profile: AccessibilityProfile | null; onClick: () => void }) {
  const Icon = profile ? avatarIcon(profile.companionProfile.appearance) : UserRound
  const label = profile ? `Open ${profile.companionProfile.name}'s profile` : 'Set Up Profile'
  return <button onClick={onClick} aria-label={label} title={profile ? 'Companion Profile' : 'Set Up Profile'} className="inline-flex h-10 items-center gap-2 rounded-full border border-white/25 bg-white/10 px-0 text-amber-200 backdrop-blur transition hover:bg-white/20"><span className="grid h-10 w-10 place-items-center rounded-full"><Icon size={18}/></span>{profile && <span className="hidden pr-3 text-xs font-semibold text-white lg:inline">{profile.companionProfile.name}</span>}</button>
}
