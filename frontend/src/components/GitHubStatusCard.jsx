/**
 * GitHubStatusCard component.
 *
 * Displays live connection status to the GitHub API, authenticated username,
 * and rate-limiting quotas. In case of misconfiguration, guides the developer.
 */

import React from 'react'

export default function GitHubStatusCard({ status, loading, error, onRefresh }) {
  if (loading) {
    return (
      <aside className="github-banner" aria-label="GitHub status loading">
        <div className="github-banner__content">
          <span className="status-dot status-dot--loading" aria-hidden="true" />
          <div className="github-banner__info">
            <span className="github-banner__title">Checking GitHub Connection...</span>
            <span className="github-banner__sub">Validating Personal Access Token</span>
          </div>
        </div>
      </aside>
    )
  }

  if (error || (status && !status.connected)) {
    const reasonMessage =
      status?.reason ||
      error?.message ||
      'GitHub is not connected. Configure GITHUB_TOKEN in your backend environment.'

    return (
      <aside
        className="github-banner github-banner--warning"
        aria-label="GitHub connection warning"
        id="github-status-warning"
      >
        <div className="github-banner__content">
          <span className="status-dot status-dot--disconnected" aria-hidden="true" />
          <div className="github-banner__info">
            <span className="github-banner__title">GitHub Not Connected</span>
            <span className="github-banner__sub">{reasonMessage}</span>
          </div>
        </div>
        {onRefresh && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onRefresh}
            aria-label="Retry GitHub connection check"
          >
            Retry Connection
          </button>
        )}
      </aside>
    )
  }

  return (
    <aside
      className="github-banner github-banner--connected"
      aria-label="GitHub connection status"
      id="github-status-card"
    >
      <div className="github-banner__content">
        {status?.avatar_url ? (
          <img
            src={status.avatar_url}
            alt={`${status.username} avatar`}
            className="github-banner__avatar"
          />
        ) : (
          <span className="status-dot status-dot--connected" aria-hidden="true" />
        )}
        <div className="github-banner__info">
          <span className="github-banner__title">
            Connected as <strong className="text-accent">{status?.username}</strong>
            <span className="badge badge--success">Active</span>
          </span>
          <span className="github-banner__sub">
            {status?.rate_limit_remaining !== undefined && status?.rate_limit_remaining !== null
              ? `API Rate Limit: ${status.rate_limit_remaining} requests remaining`
              : 'Authenticated via Personal Access Token'}
          </span>
        </div>
      </div>
      {onRefresh && (
        <button
          type="button"
          className="btn btn-outline btn-sm"
          onClick={onRefresh}
          aria-label="Refresh status"
        >
          Check Again
        </button>
      )}
    </aside>
  )
}
