/**
 * AIStatusCard component.
 *
 * Displays OmniRoute provider health, model info, and connection status.
 */

import React from 'react'

export default function AIStatusCard({ status, loading, error, onRefresh }) {
  if (loading) {
    return (
      <div className="ai-status-card">
        <div className="ai-status-card__info">
          <div className="ai-status-card__indicator" style={{ background: 'var(--color-text-muted)' }} />
          <div>
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>AI Provider</span>
            <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>Checking OmniRoute status...</p>
          </div>
        </div>
      </div>
    )
  }

  const isAvailable = status?.available
  const providerName = status?.provider || 'OmniRoute'
  const modelName = status?.model || 'gpt-4o-mini'

  return (
    <div className="ai-status-card" role="region" aria-label="AI provider status">
      <div className="ai-status-card__info">
        <div
          className={`ai-status-card__indicator ${
            isAvailable ? 'ai-status-card__indicator--online' : 'ai-status-card__indicator--offline'
          }`}
          aria-hidden="true"
        />
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>
              AI Provider: {providerName}
            </span>
            <span className={`badge ${isAvailable ? 'badge--success' : 'badge--running'}`}>
              {isAvailable ? 'Connected' : 'Unavailable'}
            </span>
            <span className="badge badge--public" style={{ fontFamily: 'var(--font-mono)' }}>
              {modelName}
            </span>
          </div>
          <p className="text-secondary" style={{ fontSize: 'var(--font-size-xs)', marginTop: '2px' }}>
            {isAvailable
              ? 'OmniRoute gateway is online and ready for failure analysis.'
              : 'AI provider is unavailable. Verify that OmniRoute is running on http://localhost:20128/v1.'}
          </p>
        </div>
      </div>

      {onRefresh && (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={onRefresh}
          disabled={loading}
          aria-label="Refresh AI status"
        >
          Check AI Status
        </button>
      )}
    </div>
  )
}
