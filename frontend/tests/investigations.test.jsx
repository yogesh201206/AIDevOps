/**
 * Frontend Tests for Phase 3: AI DevOps Investigation Engine.
 *
 * Covers:
 *  - AI status display (connected and unavailable)
 *  - "Investigate with AI" button display on failed runs
 *  - Investigation loading state
 *  - Successful AI result rendering (Summary, Root Cause, Evidence, Confidence, Suggested Fix, Validation)
 *  - Evidence expandable / collapsible detail
 *  - Safety advisory banner ("Suggested Fix != Automatically Applied Fix")
 *  - Error handling when OmniRoute / API is unavailable
 *  - Investigations page empty state and list rendering
 *
 * All API calls are mocked.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AIStatusCard from '../src/components/AIStatusCard'
import InvestigationResultCard from '../src/components/InvestigationResultCard'
import WorkflowRunsView from '../src/components/WorkflowRunsView'
import Investigations from '../src/pages/Investigations'
import * as investigationsService from '../src/services/investigations'
import * as githubService from '../src/services/github'

// Mock services
vi.mock('../src/services/investigations', () => ({
  getAIStatus: vi.fn(),
  createInvestigation: vi.fn(),
  getInvestigations: vi.fn(),
  getInvestigation: vi.fn(),
}))

vi.mock('../src/services/github', () => ({
  getWorkflowRuns: vi.fn(),
  getWorkflowJobs: vi.fn(),
  getWorkflowLogs: vi.fn(),
}))

const mockInvestigationResult = {
  investigation_id: 'inv_abc123',
  repository: 'test-org/test-repo',
  workflow_run_id: 1001,
  workflow_name: 'CI Build & Test',
  status: 'completed',
  summary: 'The build failed because pytest could not locate the requests module.',
  root_causes: [
    {
      cause: 'Missing Python Dependency',
      explanation: 'ModuleNotFoundError: No module named requests in test_runner.py line 4',
      confidence: 0.92,
    },
  ],
  evidence: [
    {
      source: 'Run pytest suite',
      detail: 'ModuleNotFoundError: No module named requests\nProcess exited with status 1',
      importance: 'high',
    },
  ],
  affected_components: ['Backend API tests'],
  severity: 'high',
  confidence: 0.89,
  suggested_fixes: [
    {
      description: 'Add requests>=2.31.0 to requirements.txt.',
      reason: 'Ensures the library is installed during the setup step.',
    },
  ],
  validation_steps: [
    'Run pytest locally to confirm tests pass.',
    'Push fix to re-trigger GitHub Actions workflow.',
  ],
  model: 'gpt-4o-mini',
  provider: 'omniroute',
  created_at: '2026-10-08T17:00:00Z',
}

describe('AI Status Display Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Connected" when OmniRoute is operational', () => {
    render(
      <AIStatusCard
        status={{ configured: true, available: true, provider: 'omniroute', model: 'gpt-4o-mini' }}
        loading={false}
        error={null}
      />
    )
    expect(screen.getByText(/AI Provider: omniroute/i)).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByText(/gpt-4o-mini/i)).toBeInTheDocument()
  })

  it('renders "Unavailable" when OmniRoute is offline', () => {
    render(
      <AIStatusCard
        status={{ configured: true, available: false, provider: 'omniroute', model: 'gpt-4o-mini' }}
        loading={false}
        error={null}
      />
    )
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByText(/AI provider is unavailable/i)).toBeInTheDocument()
  })
})

describe('InvestigationResultCard Tests', () => {
  it('renders safety advisory banner prominently', () => {
    render(<InvestigationResultCard investigation={mockInvestigationResult} />)
    expect(
      screen.getByText(/Suggested Fix ≠ Automatically Applied Fix/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Phase 3 provides analysis and suggested fixes only/i)
    ).toBeInTheDocument()
  })

  it('renders summary, root causes, confidence, and suggested fixes', () => {
    render(<InvestigationResultCard investigation={mockInvestigationResult} />)
    expect(screen.getByText(/Executive Summary/i)).toBeInTheDocument()
    expect(screen.getByText(mockInvestigationResult.summary)).toBeInTheDocument()
    expect(screen.getByText(/Missing Python Dependency/i)).toBeInTheDocument()
    expect(screen.getByText(/89% High/i)).toBeInTheDocument()
    expect(screen.getByText(/HIGH SEVERITY/i)).toBeInTheDocument()
    expect(screen.getByText(/Add requests>=2.31.0 to requirements.txt./i)).toBeInTheDocument()
    expect(screen.getByText(/Run pytest locally to confirm tests pass./i)).toBeInTheDocument()
  })

  it('toggles evidence visibility on header click', () => {
    render(<InvestigationResultCard investigation={mockInvestigationResult} />)
    // Initially open
    expect(screen.getByText(/Process exited with status 1/i)).toBeInTheDocument()

    // Click header to collapse
    const toggleBtn = screen.getByText(/Source: Run pytest suite/i)
    fireEvent.click(toggleBtn)
    expect(screen.queryByText(/Process exited with status 1/i)).not.toBeInTheDocument()

    // Click again to expand
    fireEvent.click(toggleBtn)
    expect(screen.getByText(/Process exited with status 1/i)).toBeInTheDocument()
  })
})

describe('WorkflowRunsView "Investigate with AI" Tests', () => {
  const failedRun = {
    id: 1001,
    workflow_id: 1,
    workflow_name: 'CI Build & Test',
    status: 'completed',
    conclusion: 'failure',
    branch: 'main',
    commit_sha: 'abcdef123',
    commit_short_sha: 'abcdef1',
    event: 'push',
    html_url: 'https://github.com/test-org/test-repo/actions/runs/1001',
    run_number: 12,
    is_failed: true,
  }

  const failedJob = {
    id: 501,
    run_id: 1001,
    name: 'Build',
    status: 'completed',
    conclusion: 'failure',
    is_failed: true,
    steps: [
      { name: 'Setup', number: 1, status: 'completed', conclusion: 'success', is_failed: false },
      { name: 'Test', number: 2, status: 'completed', conclusion: 'failure', is_failed: true },
    ],
    failed_steps: [
      { name: 'Test', number: 2, status: 'completed', conclusion: 'failure', is_failed: true },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
    githubService.getWorkflowRuns.mockResolvedValue([failedRun])
    githubService.getWorkflowJobs.mockResolvedValue([failedJob])
    githubService.getWorkflowLogs.mockResolvedValue({
      run_id: 1001,
      available: true,
      content: 'Exit code 1',
    })
  })

  it('displays "Investigate with AI" button on failed run diagnostics', async () => {
    render(<WorkflowRunsView owner="test-org" repo="test-repo" />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /investigate failure with ai/i })).toBeInTheDocument()
    })
  })

  it('triggers investigation, shows loading state, and renders result card', async () => {
    investigationsService.createInvestigation.mockResolvedValueOnce(mockInvestigationResult)

    render(<WorkflowRunsView owner="test-org" repo="test-repo" />)

    const button = await screen.findByRole('button', { name: /investigate failure with ai/i })
    fireEvent.click(button)

    // Check loading indicator appears
    expect(screen.getByText(/Analyzing workflow run with AI DevOps Engine.../i)).toBeInTheDocument()

    // Wait for investigation result to display
    await waitFor(() => {
      expect(screen.getByText(mockInvestigationResult.summary)).toBeInTheDocument()
      expect(screen.getByText(/Missing Python Dependency/i)).toBeInTheDocument()
    })
  })

  it('handles AI provider unavailable error gracefully', async () => {
    investigationsService.createInvestigation.mockRejectedValueOnce(
      new Error('AI provider is unavailable. Verify that OmniRoute is running.')
    )

    render(<WorkflowRunsView owner="test-org" repo="test-repo" />)

    const button = await screen.findByRole('button', { name: /investigate failure with ai/i })
    fireEvent.click(button)

    await waitFor(() => {
      expect(screen.getByText(/AI Investigation Failed/i)).toBeInTheDocument()
      expect(screen.getByText(/AI provider is unavailable. Verify that OmniRoute is running./i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /retry ai investigation/i })).toBeInTheDocument()
    })
  })
})

describe('Investigations Page Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    investigationsService.getAIStatus.mockResolvedValue({
      configured: true,
      available: true,
      provider: 'omniroute',
      model: 'gpt-4o-mini',
    })
  })

  it('renders page header and empty history state when no investigations exist', async () => {
    investigationsService.getInvestigations.mockResolvedValueOnce([])

    render(
      <MemoryRouter>
        <Investigations />
      </MemoryRouter>
    )

    expect(screen.getByText('AI Incident Investigations')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('No Investigations Recorded')).toBeInTheDocument()
    })
  })

  it('renders historical investigations list and opens detail on click', async () => {
    const historyItem = {
      investigation_id: 'inv_abc123',
      repository: 'test-org/test-repo',
      workflow_run_id: 1001,
      workflow_name: 'CI Build & Test',
      status: 'completed',
      summary: 'Missing dependency caused test failure.',
      severity: 'high',
      confidence: 0.89,
      model: 'gpt-4o-mini',
      provider: 'omniroute',
      created_at: '2026-10-08T17:00:00Z',
    }
    investigationsService.getInvestigations.mockResolvedValueOnce([historyItem])
    investigationsService.getInvestigation.mockResolvedValueOnce(mockInvestigationResult)

    render(
      <MemoryRouter>
        <Investigations />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/test-org\/test-repo · CI Build & Test #1001/i)).toBeInTheDocument()
    })

    // Click to view detailed report
    const viewBtn = screen.getByRole('button', { name: /view report/i })
    fireEvent.click(viewBtn)

    await waitFor(() => {
      expect(screen.getByText(mockInvestigationResult.summary)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /back to list/i })).toBeInTheDocument()
    })
  })
})
