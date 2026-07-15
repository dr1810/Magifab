import { useEffect, useState } from 'react'
import { getCompanionProfile } from '../services/userService'
import type { CompanionProfile } from '../types/user'

export function useCompanionProfile() {
  const [profile, setProfile] = useState<CompanionProfile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void getCompanionProfile().then((data) => {
      if (!active) return
      setProfile(data)
      setLoading(false)
    })

    return () => {
      active = false
    }
  }, [])

  return { profile, loading }
}
