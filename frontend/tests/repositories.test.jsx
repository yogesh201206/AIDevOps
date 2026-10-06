/**
 * Frontend Tests for GitHub Repositories and Workflow Diagnostics.
 *
 * Tests:
 *  - Repositories page rendering
 *  - Loading state
 *  - Repository list rendering
 *  - Empty repository state
 *  - GitHub authentication error banner
 *  - Workflow run rendering
 *  - Failed workflow display
 *  - Failed job and failed step display
 *
 * All network calls to the backend are mocked so tests run completely offline.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Repositories from '../src/pages/Repositories'
import WorkflowRunsView from '../src/components/WorkflowRunsView'
import * as githubService from '../src/services/github'

// Mock the GitHub service module
vi.mock('../src/services/github', () => ({
  getGitHubStatus: vi.fn(),
  getRepositories: vi.fn(),
  getRepository: vi.fn(),
  getBranches: vi.fn(),
  getCommits: vi.fn(),
  getWorkflows: vi.fn(),
  getWorkflowRuns: vi.fn(),
  getWorkflowRun: vi.fn(),
  getWorkflowJobs: vi.fn(),
  getWorkflowLogs: vi.fn(),
  getJobLogs: vi.fn(),
}))

const mockRepos = [
  {
    id: 1,
    name: 'ai-devops-agent',
    full_name: 'org/ai-devops-agent',
    owner: 'org',
    private: true,
    html_url: 'https://github.com/org/ai-devops-agent',
    description: 'DevOps automation agent with AI',
    default_branch: 'main',
    language: 'Python',
    stars_count: 42,
    forks_count: 5,
    open_issues_count: 1,
    updated_at: '2026-10-06T12:00:00Z',
  },
  {
    id: 2,
    name: 'public-docs',
    full_name: 'org/public-docs',
    owner: 'org',
    private: false,
    html_url: 'https://github.com/org/public-docs',
    description: 'Public documentation repository',
    default_branch: 'master',
    language: 'Markdown',
    stars_count: 10,
    forks_count: 0,
    open_issues_count: 0,
    updated_at: '2026-10-06T10:00:00Z',
  },
]

const mockRuns = [
  {
    id: 101,
    workflow_id: 1,
    workflow_name: 'CI Pipeline',
    status: 'completed',
    conclusion: 'failure',
    branch: 'main',
    commit_sha: 'a1b2c3d4e5f6',
    commit_short_sha: 'a1b2c3d',
    commit_message: 'fix: broken configuration',
    event: 'push',
    html_url: 'https://github.com/org/ai-devops-agent/actions/runs/101',
    run_number: 45,
    is_failed: true,
  },
  {
    id: 102,
    workflow_id: 1,
    workflow_name: 'CI Pipeline',
    status: 'completed',
    conclusion: 'success',
    branch: 'feature-1',
    commit_sha: 'f6e5d4c3b2a1',
    commit_short_sha: 'f6e5d4c',
    commit_message: 'feat: add feature',
    event: 'pull_request',
    html_url: 'https://github.com/org/ai-devops-agent/actions/runs/102',
    run_number: 46,
    is_failed: false,
  },
]

const mockJobs = [
  {
    id: 201,
    run_id: 101,
    name: 'unit-tests',
    status: 'completed',
    conclusion: 'failure',
    is_failed: true,
    steps: [
      {
        name: 'Set up Python 3.14',
        status: 'completed',
        conclusion: 'success',
        number: 1,
        is_failed: false,
      },
      {
        name: 'Run pytest suite',
        status: 'completed',
        conclusion: 'failure',
        number: 2,
        is_failed: true,
      },
    ],
    failed_steps: [
      {
        name: 'Run pytest suite',
        status: 'completed',
        conclusion: 'failure',
        number: 2,
        is_failed: true,
      },
    ],
  },
]

function renderRepositories() {
  return render(
    <MemoryRouter initialEntries={['/repositories']}>
      <Routes>
        <Route path="/repositories" element={<Repositories />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Repositories Page Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page header and title', async () => {
    githubService.getGitHubStatus.mockResolvedValueOnce({
      connected: true,
      username: 'devops-bot',
      rate_limit_remaining: 4999,
    })
    githubService.getRepositories.mockResolvedValueOnce(mockRepos)

    renderRepositories()

    expect(screen.getByRole('heading', { name: /GitHub Repositories/i })).toBeInTheDocument()
  })

  it('shows loading state while fetching GitHub connection status', () => {
    githubService.getGitHubStatus.mockReturnValue(new Promise(() => {}))

    renderRepositories()

    expect(screen.getByLabelText(/GitHub status loading/i)).toBeInTheDocument()
    expect(screen.getByText(/Checking GitHub Connection.../i)).toBeInTheDocument()
  })

  it('renders repository list with metadata when authenticated', async () => {
    githubService.getGitHubStatus.mockResolvedValueOnce({
      connected: true,
      username: 'devops-bot',
      rate_limit_remaining: 4999,
    })
    githubService.getRepositories.mockResolvedValueOnce(mockRepos)

    renderRepositories()

    await waitFor(() => {
      expect(screen.getByText('ai-devops-agent')).toBeInTheDocument()
      expect(screen.getByText('public-docs')).toBeInTheDocument()
    })

    // Private and Public badges
    expect(screen.getAllByText('Private').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Public').length).toBeGreaterThanOrEqual(1)

    // Languages
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Markdown')).toBeInTheDocument()
  })

  it('renders empty repository state when no repos are found', async () => {
    githubService.getGitHubStatus.mockResolvedValueOnce({
      connected: true,
      username: 'devops-bot',
      rate_limit_remaining: 5000,
    })
    githubService.getRepositories.mockResolvedValueOnce([])

    renderRepositories()

    await waitFor(() => {
      expect(screen.getByText('No Repositories Found')).toBeInTheDocument()
    })
  })

  it('displays GitHub authentication warning when token is not configured', async () => {
    githubService.getGitHubStatus.mockResolvedValueOnce({
      connected: false,
      reason: 'GitHub token is not configured',
    })

    renderRepositories()

    await waitFor(() => {
      expect(screen.getByText('GitHub Not Connected')).toBeInTheDocument()
      expect(screen.getByText(/GitHub token is not configured/i)).toBeInTheDocument()
    })
  })

  it('filters repositories by search input', async () => {
    githubService.getGitHubStatus.mockResolvedValueOnce({
      connected: true,
      username: 'devops-bot',
      rate_limit_remaining: 4999,
    })
    githubService.getRepositories.mockResolvedValueOnce(mockRepos)

    renderRepositories()

    await waitFor(() => {
      expect(screen.getByText('ai-devops-agent')).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText(/Search repositories/i)
    fireEvent.change(searchInput, { target: { value: 'docs' } })

    expect(screen.queryByText('ai-devops-agent')).not.toBeInTheDocument()
    expect(screen.getByText('public-docs')).toBeInTheDocument()
  })
})

describe('Workflow Runs & Failure Diagnostics Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders workflow runs and displays prominent FAILED indicator', async () => {
    githubService.getWorkflowRuns.mockResolvedValueOnce(mockRuns)
    githubService.getWorkflowJobs.mockResolvedValueOnce(mockJobs)
    githubService.getWorkflowLogs.mockResolvedValueOnce({
      run_id: 101,
      available: true,
      content: 'FAILED tests/test_app.py::test_database',
      truncated: false,
    })

    render(
      <MemoryRouter>
        <WorkflowRunsView owner="org" repo="ai-devops-agent" />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getAllByText(/CI Pipeline/i).length).toBeGreaterThanOrEqual(1)
    })

    // Assert FAILED badge is visible for failed run
    const failedBadges = screen.getAllByText('FAILED')
    expect(failedBadges.length).toBeGreaterThanOrEqual(1)

    // Assert Success badge is visible for successful run
    expect(screen.getByText('Success')).toBeInTheDocument()
  })

  it('displays failed jobs and failed steps in run diagnostics', async () => {
    githubService.getWorkflowRuns.mockResolvedValueOnce(mockRuns)
    githubService.getWorkflowJobs.mockResolvedValueOnce(mockJobs)
    githubService.getWorkflowLogs.mockResolvedValueOnce({
      run_id: 101,
      available: true,
      content: 'Traceback (most recent call last):\nAssertionError',
      truncated: false,
    })

    render(
      <MemoryRouter>
        <WorkflowRunsView owner="org" repo="ai-devops-agent" />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('unit-tests')).toBeInTheDocument()
    })

    // Failed job badge
    expect(screen.getByText('FAILED JOB')).toBeInTheDocument()

    // Failed step
    expect(screen.getByText(/Run pytest suite/i)).toBeInTheDocument()
    expect(screen.getByText('FAILED STEP')).toBeInTheDocument()

    // Diagnostic logs rendered
    await waitFor(() => {
      expect(screen.getByText(/Diagnostic Log Snippet/i)).toBeInTheDocument()
      expect(screen.getByText(/Traceback/i)).toBeInTheDocument()
    })
  })
})
