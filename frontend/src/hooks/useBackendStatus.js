/**
 * useBackendStatus hook
 *
 * Polls the backend liveness endpoint and returns connection state.
 * Used by the Dashboard to display the real-time Backend status indicator.
 *
 * States:
 *   "loading"      – initial fetch in progress
 *   "connected"    – backend responded with status "healthy"
 *   "disconnected" – request failed or returned unexpected status
 */

import { useState, useEffect, useCallback } from 'react'
import { fetchHealth } from '../services/api'

const POLL_INTERVAL_MS = 30_000 // re-check every 30 seconds

/**
 * @returns {{ status: 'loading' | 'connected' | 'disconnected', lastChecked: Date | null }}
 */
export function useBackendStatus() {
  const [status, setStatus] = useState('loading')
  const [lastChecked, setLastChecked] = useState(null)

  const check = useCallback(async () => {
    try {
      const data = await fetchHealth()
      setStatus(data?.status === 'healthy' ? 'connected' : 'disconnected')
    } catch {
      setStatus('disconnected')
    } finally {
      setLastChecked(new Date())
    }
  }, [])

  useEffect(() => {
    // Initial check on mount
    check()

    // Periodic re-check
    const timer = setInterval(check, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [check])

  return { status, lastChecked }
}
