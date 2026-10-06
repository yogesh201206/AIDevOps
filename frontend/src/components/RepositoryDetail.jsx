/**
 * RepositoryDetail component.
 *
 * Full overview of a selected repository, with tabs for:
 *  - Workflow Runs & Diagnostics
 *  - Recent Commits
 *  - Branches
 *  - Action Workflows
 */

import React, { useState, useEffect } from 'react'
import WorkflowRunsView from './WorkflowRunsView'
import { getBranches, getCommits, getWorkflows } from '../services/github'

export default function RepositoryDetail({ repo, onBack }) {
  const [activeTab, setActiveTab] = useState('runs')

  // Commits state
  const [commits, setCommits] = useState([])
  const [loadingCommits, setLoadingCommits] = useState(false)
  const [commitsError, setCommitsError] = useState(null)

  // Branches state
  const [branches, setBranches] = useState([])
  const [loadingBranches, setLoadingBranches] = useState(false)
  const [branchesError, setBranchesError] = useState(null)

  // Workflows state
  const [workflows, setWorkflows] = useState([])
  const [loadingWorkflows, setLoadingWorkflows] = useState(false)
  const [workflowsError, setWorkflowsError] = useState(null)

  useEffect(() => {
    if (activeTab === 'commits' && commits.length === 0) {
      setLoadingCommits(true)
      getCommits(repo.owner, repo.name)
        .then((data) => setCommits(data))
        .catch((err) => setCommitsError(err))
        .finally(() => setLoadingCommits(false))
    } else if (activeTab === 'branches' && branches.length === 0) {
      setLoadingBranches(true)
      getBranches(repo.owner, repo.name)
        .then((data) => setBranches(data))
        .catch((err) => setBranchesError(err))
        .finally(() => setLoadingBranches(false))
    } else if (activeTab === 'workflows' && workflows.length === 0) {
      setLoadingWorkflows(true)
      getWorkflows(repo.owner, repo.name)
        .then((data) => setWorkflows(data))
        .catch((err) => setWorkflowsError(err))
        .finally(() => setLoadingWorkflows(false))
    }
  }, [activeTab, repo.owner, repo.name])

  return (
    <article aria-label={`Repository details for ${repo.full_name}`}>
      {/* Back button */}
      <button
        type="button"
        className="repo-detail-back"
        onClick={onBack}
        aria-label="Back to all repositories"
      >
        <span aria-hidden="true">←</span> Back to Repositories
      </button>

      {/* Repo Header */}
      <header className="repo-detail-header">
        <div className="repo-detail-title-bar">
          <div className="repo-detail-title">
            <span>{repo.full_name}</span>
            <span className={`badge ${repo.private ? 'badge--private' : 'badge--public'}`}>
              {repo.private ? 'Private' : 'Public'}
            </span>
          </div>

          <a
            href={repo.html_url}
            target="_blank"
            rel="noreferrer noopener"
            className="btn btn-outline btn-sm"
          >
            Open on GitHub ↗
          </a>
        </div>

        {repo.description && (
          <p style={{ color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
            {repo.description}
          </p>
        )}

        <div className="repo-meta-tags">
          {repo.language && (
            <span>
              Language: <strong className="text-accent">{repo.language}</strong>
            </span>
          )}
          <span>
            Default branch: <code className="text-mono">{repo.default_branch}</code>
          </span>
          <span>★ {repo.stars_count} stars</span>
          <span>⑂ {repo.forks_count} forks</span>
          <span>
            Updated:{' '}
            {repo.updated_at ? new Date(repo.updated_at).toLocaleDateString() : '—'}
          </span>
        </div>
      </header>

      {/* Tabs */}
      <nav className="tabs-nav" aria-label="Repository sections">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'runs' ? 'active' : ''}`}
          onClick={() => setActiveTab('runs')}
        >
          Workflow Runs
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'commits' ? 'active' : ''}`}
          onClick={() => setActiveTab('commits')}
        >
          Recent Commits
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'branches' ? 'active' : ''}`}
          onClick={() => setActiveTab('branches')}
        >
          Branches
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'workflows' ? 'active' : ''}`}
          onClick={() => setActiveTab('workflows')}
        >
          Workflows
        </button>
      </nav>

      {/* Tab Panels */}
      {activeTab === 'runs' && (
        <WorkflowRunsView owner={repo.owner} repo={repo.name} />
      )}

      {activeTab === 'commits' && (
        <section aria-label="Recent commits">
          {loadingCommits && <p className="text-muted">Loading commits...</p>}
          {commitsError && (
            <p className="text-error">Error loading commits: {commitsError.message}</p>
          )}
          {!loadingCommits && commits.length === 0 && (
            <p className="text-muted">No commits found.</p>
          )}
          {!loadingCommits && commits.length > 0 && (
            <div>
              {commits.map((commit) => (
                <div key={commit.sha} className="commit-row">
                  <div>
                    <code className="text-mono" style={{ color: 'var(--color-accent)', marginRight: '12px' }}>
                      {commit.short_sha}
                    </code>
                    <span>{commit.message}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                    <span className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                      {commit.author} · {commit.date ? new Date(commit.date).toLocaleDateString() : ''}
                    </span>
                    <a
                      href={commit.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="btn btn-outline btn-sm"
                    >
                      View ↗
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {activeTab === 'branches' && (
        <section aria-label="Repository branches">
          {loadingBranches && <p className="text-muted">Loading branches...</p>}
          {branchesError && (
            <p className="text-error">Error loading branches: {branchesError.message}</p>
          )}
          {!loadingBranches && branches.length === 0 && (
            <p className="text-muted">No branches found.</p>
          )}
          {!loadingBranches && branches.length > 0 && (
            <div>
              {branches.map((branch) => (
                <div key={branch.name} className="branch-row">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <strong className="text-mono">{branch.name}</strong>
                    {branch.name === repo.default_branch && (
                      <span className="badge badge--accent">Default</span>
                    )}
                    {branch.protected && (
                      <span className="badge badge--private">Protected</span>
                    )}
                  </div>
                  <code className="text-mono text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                    {branch.commit_sha.slice(0, 7)}
                  </code>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {activeTab === 'workflows' && (
        <section aria-label="Configured workflows">
          {loadingWorkflows && <p className="text-muted">Loading workflows...</p>}
          {workflowsError && (
            <p className="text-error">Error loading workflows: {workflowsError.message}</p>
          )}
          {!loadingWorkflows && workflows.length === 0 && (
            <p className="text-muted">No workflow definitions found.</p>
          )}
          {!loadingWorkflows && workflows.length > 0 && (
            <div>
              {workflows.map((wf) => (
                <div key={wf.id} className="branch-row">
                  <div>
                    <strong>{wf.name}</strong>
                    <div className="text-muted text-mono" style={{ fontSize: 'var(--font-size-xs)' }}>
                      {wf.path}
                    </div>
                  </div>
                  <span className={`badge ${wf.state === 'active' ? 'badge--success' : 'badge--public'}`}>
                    {wf.state}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </article>
  )
}
