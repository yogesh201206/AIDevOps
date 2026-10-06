/**
 * Smoke tests – Dashboard render
 *
 * Validates that:
 *   1. The application renders without throwing
 *   2. The page title "AI DevOps Agent" is visible
 *   3. The sidebar navigation is present
 *   4. The Backend status card exists in the DOM
 *
 * The backend health endpoint is mocked so the tests run offline
 * and do not depend on a running server.
 *
 * NOTE: App.jsx owns <BrowserRouter>. Tests render layout + pages
 * directly inside <MemoryRouter> to avoid a nested-router error.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route, Outlet } from 'react-router-dom'
import MainLayout from '../src/layouts/MainLayout'
import Dashboard   from '../src/pages/Dashboard'
import ComingSoon  from '../src/pages/ComingSoon'

// ── Mock the API service ─────────────────────────────────────────────────────
vi.mock('../src/services/api', () => ({
  fetchHealth: vi.fn().mockResolvedValue({ status: 'healthy', service: 'ai-devops-agent-backend' }),
  fetchReadiness: vi.fn().mockResolvedValue({ status: 'ready' }),
  default: {},
}))

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Renders the full app shell (MainLayout + page) inside a MemoryRouter.
 * This avoids the "two <Router>s" error caused by App.jsx's BrowserRouter.
 */
function renderWithRouter(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index             element={<Dashboard />} />
          <Route path="/repositories"   element={<ComingSoon />} />
          <Route path="/investigations" element={<ComingSoon />} />
          <Route path="/deployments"    element={<ComingSoon />} />
          <Route path="/settings"       element={<ComingSoon />} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('Dashboard smoke tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders without crashing', () => {
    expect(() => renderWithRouter()).not.toThrow()
  })

  it('shows the application title', async () => {
    renderWithRouter()
    const heading = await screen.findByRole('heading', { name: /AI DevOps Agent/i, level: 1 })
    expect(heading).toBeInTheDocument()
  })

  it('renders the sidebar navigation', () => {
    renderWithRouter()
    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    expect(nav).toBeInTheDocument()
  })

  it('renders the Dashboard nav link as active on root route', () => {
    renderWithRouter('/')
    const dashboardLink = screen.getByRole('link', { name: /dashboard/i })
    expect(dashboardLink).toBeInTheDocument()
    expect(dashboardLink.className).toContain('active')
  })

  it('renders the backend status card', async () => {
    renderWithRouter()
    const card = await screen.findByRole('article', { name: /backend connection status/i })
    expect(card).toBeInTheDocument()
  })

  it('shows "Connected" after successful health check', async () => {
    renderWithRouter()
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
    })
  })

  it('shows "Disconnected" when health check fails', async () => {
    const { fetchHealth } = await import('../src/services/api')
    fetchHealth.mockRejectedValueOnce(new Error('Network error'))

    renderWithRouter()
    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument()
    })
  })
})

describe('Navigation smoke tests', () => {
  it('renders sidebar links for all primary routes', () => {
    renderWithRouter()
    expect(screen.getByRole('link', { name: /repositories/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /investigations/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /deployments/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /settings/i })).toBeInTheDocument()
  })

  it('shows Phase 1 badge in sidebar footer', () => {
    renderWithRouter()
    const phaseBadges = screen.getAllByText('Phase 1')
    expect(phaseBadges.length).toBeGreaterThanOrEqual(1)
    expect(phaseBadges[0]).toBeInTheDocument()
  })
})

