/**
 * Dashboard page
 *
 * The only fully functional page in Phase 1.
 *
 * Features:
 *  - System Status card with a REAL backend connection check
 *  - Displays Connected / Disconnected / Loading based on the
 *    actual GET /api/v1/health response (never hardcoded)
 *  - System info card with build metadata
 *  - Phase roadmap card
 */

import { useBackendStatus } from '../hooks/useBackendStatus'

/* ── Helpers ─────────────────────────────────────────────────── */

function StatusDot({ status }) {
  return <span className={`status-dot status-dot--${status}`} aria-hidden="true" />
}

function StatusLabel({ status }) {
  const labels = {
    connected:    'Connected',
    disconnected: 'Disconnected',
    loading:      'Checking...',
  }
  return (
    <span className={`status-label status-label--${status}`}>
      {labels[status] ?? status}
    </span>
  )
}

function BackendStatusCard() {
  const { status, lastChecked } = useBackendStatus()

  const lastCheckedLabel = lastChecked
    ? lastChecked.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  return (
    <article
      className="card card--accent"
      aria-label="Backend connection status"
      id="backend-status-card"
    >
      <div className="card__header">
        <h2 className="card__title">System Status</h2>
        <span className="card__label">Live</span>
      </div>

      <div className="info-list">
        <div className="info-item">
          <span className="info-item__label">Backend</span>
          <div className="status-indicator">
            <StatusDot status={status} />
            <StatusLabel status={status} />
          </div>
        </div>
        <div className="info-item">
          <span className="info-item__label">Last checked</span>
          <span className="info-item__value">{lastCheckedLabel}</span>
        </div>
        <div className="info-item">
          <span className="info-item__label">Health endpoint</span>
          <span className="info-item__value info-item__value--accent">
            /api/v1/health
          </span>
        </div>
      </div>
    </article>
  )
}

function SystemInfoCard() {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

  return (
    <article className="card" aria-label="System information" id="system-info-card">
      <div className="card__header">
        <h2 className="card__title">Configuration</h2>
        <span className="card__label">Phase 1</span>
      </div>
      <div className="info-list">
        <div className="info-item">
          <span className="info-item__label">Phase</span>
          <span className="info-item__value">1 · Foundation</span>
        </div>
        <div className="info-item">
          <span className="info-item__label">Frontend</span>
          <span className="info-item__value">React + Vite</span>
        </div>
        <div className="info-item">
          <span className="info-item__label">Backend</span>
          <span className="info-item__value">FastAPI + Uvicorn</span>
        </div>
        <div className="info-item">
          <span className="info-item__label">API base</span>
          <span className="info-item__value info-item__value--accent">{apiBase}</span>
        </div>
      </div>
    </article>
  )
}

function RoadmapCard() {
  const phases = [
    { id: 1, label: 'Foundation',              status: 'active' },
    { id: 2, label: 'GitHub Integration',      status: 'upcoming' },
    { id: 3, label: 'AI Investigation Engine', status: 'upcoming' },
    { id: 4, label: 'Docker & Kubernetes',     status: 'upcoming' },
    { id: 5, label: 'Security & CI/CD',        status: 'upcoming' },
  ]

  return (
    <article className="card" aria-label="Phase roadmap" id="roadmap-card">
      <div className="card__header">
        <h2 className="card__title">Roadmap</h2>
        <span className="card__label">5 phases</span>
      </div>
      <div className="info-list">
        {phases.map((phase) => (
          <div className="info-item" key={phase.id}>
            <span className="info-item__label">
              Phase {phase.id} · {phase.label}
            </span>
            <span
              className="info-item__value"
              style={{
                color:
                  phase.status === 'active'
                    ? 'var(--color-success)'
                    : 'var(--color-text-muted)',
              }}
            >
              {phase.status === 'active' ? 'In Progress' : 'Upcoming'}
            </span>
          </div>
        ))}
      </div>
    </article>
  )
}

/* ── Page ────────────────────────────────────────────────────── */

export default function Dashboard() {
  return (
    <>
      <div className="page-header">
        <h1 className="page-header__title" id="page-title">AI DevOps Agent</h1>
        <p className="page-header__subtitle">
          Phase 1 foundation — backend connected, infrastructure ready.
        </p>
      </div>

      <div className="dashboard-grid">
        <BackendStatusCard />
        <SystemInfoCard />
        <RoadmapCard />
      </div>
    </>
  )
}
