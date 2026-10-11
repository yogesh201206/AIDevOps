/**
 * KubernetesStatusCard component — Phase 5.
 *
 * Displays real-time Kubernetes cluster connectivity and configuration
 * status as a polished dashboard card matching the AI/GitHub status cards.
 * Always shows read-only mode badge (never hides safety state).
 */

import React, { useState, useEffect, useCallback } from 'react'
import { getKubernetesStatus } from '../services/kubernetes'

const ICON_K8S = (
  <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.5" stroke="currentColor" aria-hidden="true" style={{ width: 18, height: 18 }}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 2v4M12 18v4M2 12h4M18 12h4" strokeLinecap="round" />
    <circle cx="12" cy="12" r="3" fill="currentColor" />
    <path d="M5.64 5.64l2.83 2.83M15.54 15.54l2.83 2.83M18.36 5.64l-2.83 2.83M8.46 15.54l-2.83 2.83" strokeLinecap="round" />
  </svg>
)

const ICON_CHECK = (
  <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style={{ width: 14, height: 14 }}>
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
  </svg>
)

const ICON_CROSS = (
  <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style={{ width: 14, height: 14 }}>
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
  </svg>
)

const ICON_LOCK = (
  <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style={{ width: 12, height: 12 }}>
    <path fillRule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clipRule="evenodd" />
  </svg>
)

function StatusRow({ label, ok, text }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '4px 0',
      borderBottom: '1px solid var(--color-border)',
      fontSize: 'var(--font-size-xs)',
    }}>
      <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: ok ? '#16a34a' : '#dc2626' }}>
        {ok ? ICON_CHECK : ICON_CROSS}
        <span style={{ fontWeight: 600 }}>{text}</span>
      </span>
    </div>
  )
}

export default function KubernetesStatusCard() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getKubernetesStatus()
      setStatus(data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Could not reach Kubernetes API')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const connectColor = status?.connected ? '#16a34a' : status?.configured ? '#d97706' : '#6b7280'

  return (
    <div className="status-card" id="kubernetes-status-card" aria-label="Kubernetes Cluster Status">
      <div className="status-card__header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: '#7c3aed' }}>{ICON_K8S}</span>
          <span className="status-card__title">Kubernetes</span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '9px',
              fontWeight: 700,
              letterSpacing: '0.05em',
              background: 'rgba(124,58,237,0.12)',
              color: '#7c3aed',
              border: '1px solid rgba(124,58,237,0.3)',
            }}
            title="This integration is strictly read-only. No cluster mutations are performed."
          >
            {ICON_LOCK}
            READ-ONLY
          </span>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={refresh}
          disabled={loading}
          aria-label="Refresh Kubernetes status"
          style={{ fontSize: '11px', padding: '3px 8px' }}
        >
          {loading ? '…' : '↻ Refresh'}
        </button>
      </div>

      <div className="status-card__body">
        {loading && !status && (
          <p className="text-secondary" style={{ fontSize: 'var(--font-size-xs)' }}>
            Checking cluster connectivity…
          </p>
        )}

        {error && (
          <p style={{ fontSize: 'var(--font-size-xs)', color: '#dc2626' }}>
            {error}
          </p>
        )}

        {status && (
          <>
            {/* Primary dot indicator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <span
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: '50%',
                  background: connectColor,
                  boxShadow: status.connected ? `0 0 0 3px ${connectColor}33` : 'none',
                  display: 'inline-block',
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                {status.connected
                  ? `Connected — ${status.cluster_name || status.current_context || 'cluster'}`
                  : status.configured
                  ? 'Configured, cluster unreachable'
                  : 'Static Analysis Mode'}
              </span>
            </div>

            {/* Status rows */}
            <StatusRow label="Client Installed" ok={status.installed} text={status.installed ? 'Yes' : 'No'} />
            <StatusRow label="Kubeconfig Present" ok={status.configured} text={status.configured ? 'Yes' : 'Not found'} />
            <StatusRow label="Cluster Reachable" ok={status.connected} text={status.connected ? 'Yes' : 'No'} />

            {/* Server version */}
            {status.server_version && (
              <div style={{ marginTop: '8px', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                Server: <code className="text-mono">{status.server_version}</code>
                {status.current_context && (
                  <> · Context: <code className="text-mono">{status.current_context}</code></>
                )}
              </div>
            )}

            {/* Status message */}
            <div style={{
              marginTop: '8px',
              padding: '6px 8px',
              borderRadius: '4px',
              background: 'var(--color-surface)',
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-secondary)',
              borderLeft: `2px solid ${connectColor}`,
            }}>
              {status.message}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
