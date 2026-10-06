/**
 * Repositories page.
 *
 * Primary GitHub integration interface:
 *  1. Shows live GitHub connection and PAT status.
 *  2. Lists all accessible repositories with search and filtering.
 *  3. Drill-down into repository details, branches, commits, and Actions runs.
 */

import React, { useState, useEffect } from 'react'
import GitHubStatusCard from '../components/GitHubStatusCard'
import RepositoryDetail from '../components/RepositoryDetail'
import { getGitHubStatus, getRepositories } from '../services/github'

export default function Repositories() {
  const [status, setStatus] = useState(null)
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [statusError, setStatusError] = useState(null)

  const [repos, setRepos] = useState([])
  const [loadingRepos, setLoadingRepos] = useState(false)
  const [reposError, setReposError] = useState(null)

  const [selectedRepo, setSelectedRepo] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [visibilityFilter, setVisibilityFilter] = useState('all') // 'all' | 'public' | 'private'

  // Load GitHub connection status
  const loadStatus = async () => {
    setLoadingStatus(true)
    setStatusError(null)
    try {
      const data = await getGitHubStatus()
      setStatus(data)
      return data
    } catch (err) {
      setStatusError(err)
      return null
    } finally {
      setLoadingStatus(false)
    }
  }

  // Load repositories
  const loadRepos = async () => {
    setLoadingRepos(true)
    setReposError(null)
    try {
      const data = await getRepositories()
      setRepos(data)
    } catch (err) {
      setReposError(err)
    } finally {
      setLoadingRepos(false)
    }
  }

  useEffect(() => {
    let isMounted = true

    loadStatus().then((statusData) => {
      if (isMounted && statusData?.connected) {
        loadRepos()
      }
    })

    return () => {
      isMounted = false
    }
  }, [])

  const handleRefresh = async () => {
    const statusData = await loadStatus()
    if (statusData?.connected) {
      await loadRepos()
    }
  }

  // Filter repositories
  const filteredRepos = repos.filter((r) => {
    const matchesSearch =
      r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.language && r.language.toLowerCase().includes(searchQuery.toLowerCase()))

    if (!matchesSearch) return false

    if (visibilityFilter === 'public') return !r.private
    if (visibilityFilter === 'private') return r.private
    return true
  })

  return (
    <>
      <div className="page-header">
        <h1 className="page-header__title" id="repositories-page-title">
          GitHub Repositories
        </h1>
        <p className="page-header__subtitle">
          Phase 2 GitHub Integration — Repositories, branches, commits, and Actions workflow runs.
        </p>
      </div>

      {/* GitHub Connection Status */}
      <GitHubStatusCard
        status={status}
        loading={loadingStatus}
        error={statusError}
        onRefresh={handleRefresh}
      />

      {/* Detail view of a selected repository */}
      {selectedRepo ? (
        <RepositoryDetail
          repo={selectedRepo}
          onBack={() => setSelectedRepo(null)}
        />
      ) : (
        <>
          {/* Controls Bar */}
          <div className="controls-bar">
            <div className="search-input-wrapper">
              <svg
                width="16"
                height="16"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <circle cx="8" cy="8" r="5" />
                <path d="M12 12l4 4" strokeLinecap="round" />
              </svg>
              <input
                type="search"
                className="search-input"
                placeholder="Search repositories by name, language..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search repositories"
                id="search-repositories-input"
              />
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className={`btn btn-sm ${visibilityFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setVisibilityFilter('all')}
              >
                All ({repos.length})
              </button>
              <button
                type="button"
                className={`btn btn-sm ${visibilityFilter === 'public' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setVisibilityFilter('public')}
              >
                Public
              </button>
              <button
                type="button"
                className={`btn btn-sm ${visibilityFilter === 'private' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setVisibilityFilter('private')}
              >
                Private
              </button>
            </div>
          </div>

          {/* Loading Repositories */}
          {loadingRepos && (
            <div className="empty-banner" aria-live="polite">
              <span className="status-dot status-dot--loading" style={{ margin: '0 auto 12px' }} />
              <div className="empty-banner__title">Loading repositories...</div>
              <p className="empty-banner__sub">Fetching accessible repositories from GitHub API</p>
            </div>
          )}

          {/* Repository Error Banner */}
          {reposError && (
            <div className="error-banner" role="alert" id="repos-error-banner">
              <div className="error-banner__title text-error">Unable to Load Repositories</div>
              <p className="error-banner__sub">{reposError.message}</p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={loadRepos}
              >
                Try Again
              </button>
            </div>
          )}

          {/* Empty state: No repos found or not configured */}
          {!loadingRepos && !reposError && repos.length === 0 && (
            <div className="empty-banner" id="repos-empty-state">
              <div className="empty-banner__title">No Repositories Found</div>
              <p className="empty-banner__sub">
                {status && !status.connected
                  ? 'Configure GITHUB_TOKEN in your backend environment to connect your repositories.'
                  : 'No repositories are accessible to this account or matching the query.'}
              </p>
              {status && !status.connected && (
                <div style={{ marginTop: '16px' }}>
                  <code className="text-mono" style={{ background: 'var(--color-surface-3)', padding: '6px 12px', borderRadius: '4px' }}>
                    GITHUB_TOKEN=ghp_your_personal_access_token
                  </code>
                </div>
              )}
            </div>
          )}

          {/* Filter produced 0 results */}
          {!loadingRepos && !reposError && repos.length > 0 && filteredRepos.length === 0 && (
            <div className="empty-banner">
              <div className="empty-banner__title">No Matching Repositories</div>
              <p className="empty-banner__sub">
                No repositories matched your search query "{searchQuery}".
              </p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setSearchQuery('')
                  setVisibilityFilter('all')
                }}
              >
                Clear Filters
              </button>
            </div>
          )}

          {/* Repository Grid */}
          {!loadingRepos && filteredRepos.length > 0 && (
            <div className="repo-grid" role="list" aria-label="Accessible repositories list">
              {filteredRepos.map((repo) => (
                <div
                  key={repo.id}
                  role="listitem"
                  className="repo-card"
                  onClick={() => setSelectedRepo(repo)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && setSelectedRepo(repo)}
                  aria-label={`Repository ${repo.full_name}`}
                >
                  <div>
                    <div className="repo-card__header">
                      <h2 className="repo-card__title">
                        {repo.name}
                      </h2>
                      <span className={`badge ${repo.private ? 'badge--private' : 'badge--public'}`}>
                        {repo.private ? 'Private' : 'Public'}
                      </span>
                    </div>

                    <p className="repo-card__desc">
                      {repo.description || 'No description provided.'}
                    </p>
                  </div>

                  <div className="repo-card__footer">
                    <div className="repo-card__stats">
                      {repo.language && (
                        <span>
                          <strong className="text-accent">{repo.language}</strong>
                        </span>
                      )}
                      <span>★ {repo.stars_count}</span>
                      <span>branch: <code className="text-mono">{repo.default_branch}</code></span>
                    </div>

                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <a
                        href={repo.html_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="btn btn-outline btn-sm"
                        onClick={(e) => e.stopPropagation()}
                      >
                        GitHub ↗
                      </a>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedRepo(repo)
                        }}
                      >
                        Select
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  )
}
