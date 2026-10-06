/**
 * Topbar component
 *
 * Sticky top navigation bar displaying breadcrumb, phase badge,
 * and a live clock.
 */

import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const ROUTE_LABELS = {
  '/':               'Dashboard',
  '/repositories':   'Repositories',
  '/investigations': 'Investigations',
  '/deployments':    'Deployments',
  '/settings':       'Settings',
}

function LiveClock() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <time className="topbar__time" dateTime={time.toISOString()}>
      {time.toUTCString().replace('GMT', 'UTC')}
    </time>
  )
}

export default function Topbar() {
  const location = useLocation()
  const currentLabel = ROUTE_LABELS[location.pathname] ?? 'Page'

  return (
    <header className="topbar" role="banner">
      <div className="topbar__breadcrumb" aria-label="Breadcrumb">
        <span>AI DevOps Agent</span>
        <span className="topbar__breadcrumb-sep" aria-hidden="true">/</span>
        <span className="topbar__breadcrumb-current">{currentLabel}</span>
      </div>

      <div className="topbar__right">
        <span className="topbar__phase-badge">Phase 1 · Foundation</span>
        <LiveClock />
      </div>
    </header>
  )
}
