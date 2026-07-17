import { useCallback, useEffect, useState } from 'react'
import { getAccessibilityProfile } from '../services/accessibilityProfileService'
import type { AccessibilityProfile } from '../types/accessibility-profile'

export function useAccessibilityProfile() {
  const [profile, setProfile] = useState<AccessibilityProfile | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    setProfile(await getAccessibilityProfile())
    setLoading(false)
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  return { profile, loading, refresh }
}
