/**
 * Sidebar component
 *
 * Fixed left-side navigation. Active route is highlighted via React Router's
 * NavLink. Placeholder routes show "coming soon" state when visited.
 */

import { NavLink, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  {
    group: 'Main',
    items: [
      {
        path: '/',
        label: 'Dashboard',
        icon: (
          <svg className="nav-item__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <rect x="2" y="2" width="7" height="7" rx="1.5" />
            <rect x="11" y="2" width="7" height="7" rx="1.5" />
            <rect x="2" y="11" width="7" height="7" rx="1.5" />
            <rect x="11" y="11" width="7" height="7" rx="1.5" />
          </svg>
        ),
      },
    ],
  },
  {
    group: 'Integrations',
    items: [
      {
        path: '/repositories',
        label: 'Repositories',
        icon: (
          <svg className="nav-item__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M3 5a2 2 0 012-2h10a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V5z" />
            <path d="M7 9h6M7 12h4" strokeLinecap="round" />
          </svg>
        ),
      },
      {
        path: '/investigations',
        label: 'Investigations',
        icon: (
          <svg className="nav-item__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="9" cy="9" r="5" />
          <path d="M15 15l3 3" strokeLinecap="round" />
        </svg>
        ),
      },
      {
        path: '/deployments',
        label: 'Deployments',
        icon: (
          <svg className="nav-item__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M10 3l7 4v6l-7 4-7-4V7l7-4z" />
            <path d="M10 3v14M3.5 7l6.5 4 6.5-4" strokeLinecap="round" />
          </svg>
        ),
      },
    ],
  },
  {
    group: 'System',
    items: [
      {
        path: '/settings',
        label: 'Settings',
        icon: (
          <svg className="nav-item__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="10" cy="10" r="2.5" />
            <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.41 1.41M14.37 14.37l1.41 1.41M4.22 15.78l1.41-1.41M14.37 5.63l1.41-1.41" strokeLinecap="round" />
          </svg>
        ),
      },
    ],
  },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside className="sidebar" role="navigation" aria-label="Main navigation">
      {/* Logo / brand */}
      <div className="sidebar__logo">
        <div className="sidebar__logo-mark" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 1L14 4.5V11.5L8 15L2 11.5V4.5L8 1Z" />
          </svg>
        </div>
        <div className="sidebar__logo-text">
          <span className="sidebar__logo-title">AI DevOps Agent</span>
          <span className="sidebar__logo-sub">v0.1 · phase 1</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav" aria-label="Page navigation">
        {NAV_ITEMS.map((section) => (
          <div key={section.group}>
            <div className="sidebar__section-label">{section.group}</div>
            {section.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `nav-item${isActive ? ' active' : ''}`
                }
                aria-label={item.label}
                id={`nav-${item.label.toLowerCase()}`}
              >
                {item.icon}
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar__footer">
        <div className="sidebar__version">
          <span>Phase 1</span>
          <span className="sidebar__env-badge">Foundation</span>
        </div>
      </div>
    </aside>
  )
}
