/**
 * ComingSoon page
 *
 * Displayed for routes that are planned but not yet implemented.
 * Each phase-2+ page uses this as a placeholder.
 */

import { useLocation } from 'react-router-dom'

const PAGE_META = {
  '/repositories':   { title: 'Repositories',   phase: 2, description: 'Browse and connect GitHub repositories for deployment monitoring.' },
  '/investigations': { title: 'Investigations', phase: 3, description: 'AI-powered root cause analysis of failed deployments.' },
  '/deployments':    { title: 'Deployments',    phase: 2, description: 'Track deployment history, failures, and rollback status.' },
  '/settings':       { title: 'Settings',        phase: 2, description: 'Configure API tokens, integrations, and notification preferences.' },
}

export default function ComingSoon() {
  const location = useLocation()
  const meta = PAGE_META[location.pathname] ?? {
    title: 'Coming Soon',
    phase: 2,
    description: 'This feature is planned for a future phase.',
  }

  return (
    <div className="coming-soon" role="main" aria-label={`${meta.title} - coming soon`}>
      <div className="coming-soon__icon" aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v6l3 3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <h1 className="coming-soon__title">{meta.title}</h1>
      <p className="coming-soon__sub">{meta.description}</p>
      <span className="coming-soon__badge">Planned · Phase {meta.phase}</span>
    </div>
  )
}
