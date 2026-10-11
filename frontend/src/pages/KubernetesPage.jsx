/**
 * KubernetesPage — Phase 5 Kubernetes Intelligence dashboard.
 *
 * Features:
 * - Live cluster status panel
 * - Static YAML manifest analyzer
 * - Pod status analyzer
 * - GitHub Actions log correlator (paste CI logs → detect Kubernetes errors)
 * All operations are strictly read-only — no cluster mutations.
 */

import React, { useState } from 'react'
import KubernetesStatusCard from '../components/KubernetesStatusCard'
import { analyzeKubernetes, analyzeKubernetesManifest } from '../services/kubernetes'

/* ── Severity helpers ───────────────────────────────────────── */

const SEV_COLORS = {
  critical: { bg: 'rgba(220,38,38,0.10)', border: '#dc2626', text: '#dc2626' },
  high:     { bg: 'rgba(234,88,12,0.10)',  border: '#ea580c', text: '#ea580c' },
  medium:   { bg: 'rgba(202,138,4,0.10)',  border: '#ca8a04', text: '#ca8a04' },
  low:      { bg: 'rgba(37,99,235,0.10)',  border: '#2563eb', text: '#2563eb' },
  info:     { bg: 'rgba(107,114,128,0.08)',border: '#6b7280', text: '#6b7280' },
}

function SeverityBadge({ severity }) {
  const sev = (severity || 'info').toLowerCase()
  const c = SEV_COLORS[sev] || SEV_COLORS.info
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 7px',
      borderRadius: '4px',
      fontSize: '10px',
      fontWeight: 700,
      letterSpacing: '0.06em',
      background: c.bg,
      color: c.text,
      border: `1px solid ${c.border}`,
    }}>
      {sev.toUpperCase()}
    </span>
  )
}

/* ── EvidenceList ───────────────────────────────────────────── */

function EvidenceList({ evidence }) {
  const [expanded, setExpanded] = useState({})
  const toggle = (i) => setExpanded(p => ({ ...p, [i]: !p[i] }))

  if (!evidence || evidence.length === 0) {
    return <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>No findings detected.</p>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {evidence.map((ev, i) => {
        const open = expanded[i] !== false // default open
        const sev = (ev.severity || 'info').toLowerCase()
        const c = SEV_COLORS[sev] || SEV_COLORS.info
        return (
          <div key={i} style={{
            borderRadius: '8px',
            border: `1px solid ${c.border}`,
            background: c.bg,
            overflow: 'hidden',
          }}>
            {/* header */}
            <div
              role="button"
              tabIndex={0}
              onClick={() => toggle(i)}
              onKeyDown={e => e.key === 'Enter' && toggle(i)}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                padding: '10px 14px', cursor: 'pointer', gap: '10px',
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', flex: 1 }}>
                <SeverityBadge severity={ev.severity} />
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontFamily: 'var(--font-family-mono)' }}>
                  {ev.resource_kind}/{ev.resource_name}
                </span>
                <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  {ev.message}
                </span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                {open ? '▲' : '▼'}
              </span>
            </div>

            {open && (
              <div style={{ padding: '0 14px 12px', borderTop: `1px solid ${c.border}33` }}>
                {/* category + confidence */}
                <div style={{ display: 'flex', gap: '12px', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginBottom: '8px', flexWrap: 'wrap' }}>
                  <span><strong>Category:</strong> {ev.category}</span>
                  <span><strong>Confidence:</strong> {Math.round((ev.confidence || 0) * 100)}%</span>
                  <span><strong>Namespace:</strong> {ev.namespace || 'default'}</span>
                  <span><strong>Source:</strong> {ev.source}</span>
                </div>
                {ev.probable_root_cause && (
                  <div style={{ fontSize: 'var(--font-size-xs)', marginBottom: '6px' }}>
                    <strong style={{ color: 'var(--color-text-secondary)' }}>Root Cause:</strong>{' '}
                    {ev.probable_root_cause}
                  </div>
                )}
                {ev.suggested_fix && (
                  <div style={{ fontSize: 'var(--font-size-xs)', color: '#16a34a', marginBottom: '6px' }}>
                    <strong>Suggested Fix:</strong> {ev.suggested_fix}
                  </div>
                )}
                <pre style={{
                  margin: '8px 0 0 0', padding: '8px', borderRadius: '6px',
                  background: 'var(--color-surface)', fontSize: '11px',
                  fontFamily: 'var(--font-family-mono)', whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all', color: 'var(--color-text-secondary)',
                }}>
                  {ev.evidence}
                </pre>
                {ev.validation_steps && ev.validation_steps.length > 0 && (
                  <div style={{ marginTop: '8px' }}>
                    <strong style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>Validation steps:</strong>
                    <ul style={{ margin: '4px 0 0 0', paddingLeft: '18px' }}>
                      {ev.validation_steps.map((s, si) => (
                        <li key={si} style={{ fontSize: '11px', fontFamily: 'var(--font-family-mono)', color: 'var(--color-text-secondary)' }}>
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ── Section tabs ───────────────────────────────────────────── */

const TABS = [
  { id: 'manifest', label: '📄 Manifest Analyzer' },
  { id: 'pod',      label: '🫛 Pod / Deployment' },
  { id: 'log',      label: '📋 CI/CD Log Correlator' },
]

/* ── ManifestTab ────────────────────────────────────────────── */

function ManifestTab() {
  const [yaml, setYaml] = useState('')
  const [filename, setFilename] = useState('manifest.yaml')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleAnalyze = async () => {
    if (!yaml.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const evidence = await analyzeKubernetesManifest(yaml, filename)
      setResult(evidence)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
        Paste any Kubernetes YAML (single or multi-document) to detect misconfigurations, deprecated APIs, label mismatches, and resource issues.
      </p>
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <label style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', flexShrink: 0 }}>Filename:</label>
        <input
          id="k8s-manifest-filename"
          type="text"
          value={filename}
          onChange={e => setFilename(e.target.value)}
          style={{
            fontSize: 'var(--font-size-xs)', fontFamily: 'var(--font-family-mono)',
            padding: '4px 8px', borderRadius: '6px', border: '1px solid var(--color-border)',
            background: 'var(--color-surface)', color: 'var(--color-text-primary)', width: '200px',
          }}
        />
      </div>
      <textarea
        id="k8s-manifest-input"
        value={yaml}
        onChange={e => setYaml(e.target.value)}
        rows={16}
        placeholder="apiVersion: apps/v1&#10;kind: Deployment&#10;metadata:&#10;  name: my-app&#10;..."
        style={{
          width: '100%', boxSizing: 'border-box',
          fontFamily: 'var(--font-family-mono)', fontSize: '12px',
          padding: '12px', borderRadius: '8px',
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface)', color: 'var(--color-text-primary)',
          resize: 'vertical', lineHeight: 1.5,
        }}
      />
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <button
          id="k8s-analyze-manifest-btn"
          type="button"
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={loading || !yaml.trim()}
        >
          {loading ? 'Analyzing…' : '⚡ Analyze Manifest'}
        </button>
        {result && (
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            {result.length} finding{result.length !== 1 ? 's' : ''} detected
          </span>
        )}
      </div>
      {error && (
        <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(220,38,38,0.08)', border: '1px solid #dc2626', fontSize: 'var(--font-size-sm)', color: '#dc2626' }}>
          {error}
        </div>
      )}
      {result && <EvidenceList evidence={result} />}
    </div>
  )
}

/* ── PodTab ─────────────────────────────────────────────────── */

function PodTab() {
  const [jsonInput, setJsonInput] = useState('')
  const [mode, setMode] = useState('pod') // 'pod' | 'deployment'
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleAnalyze = async () => {
    if (!jsonInput.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let parsed
      try {
        parsed = JSON.parse(jsonInput)
      } catch {
        throw new Error('Invalid JSON — paste a valid Kubernetes object from `kubectl get pod <name> -o json`')
      }
      const payload = mode === 'pod'
        ? { pod_status: parsed }
        : { deployment_status: parsed }
      const data = await analyzeKubernetes(payload)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
        Paste the JSON output of <code style={{ fontFamily: 'var(--font-family-mono)', fontSize: '11px' }}>kubectl get pod &lt;name&gt; -o json</code> or{' '}
        <code style={{ fontFamily: 'var(--font-family-mono)', fontSize: '11px' }}>kubectl get deployment &lt;name&gt; -o json</code>.
      </p>
      <div style={{ display: 'flex', gap: '8px' }}>
        {[{ id: 'pod', label: '🫛 Pod' }, { id: 'deployment', label: '🚀 Deployment' }].map(opt => (
          <button
            key={opt.id}
            id={`k8s-mode-${opt.id}`}
            type="button"
            className={`btn btn-sm ${mode === opt.id ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setMode(opt.id)}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <textarea
        id="k8s-resource-json-input"
        value={jsonInput}
        onChange={e => setJsonInput(e.target.value)}
        rows={16}
        placeholder={`Paste kubectl ${mode} JSON output here…`}
        style={{
          width: '100%', boxSizing: 'border-box',
          fontFamily: 'var(--font-family-mono)', fontSize: '12px',
          padding: '12px', borderRadius: '8px',
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface)', color: 'var(--color-text-primary)',
          resize: 'vertical', lineHeight: 1.5,
        }}
      />
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <button
          id="k8s-analyze-resource-btn"
          type="button"
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={loading || !jsonInput.trim()}
        >
          {loading ? 'Analyzing…' : '⚡ Analyze ' + (mode === 'pod' ? 'Pod' : 'Deployment')}
        </button>
        {result && (
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            {result.evidence?.length ?? 0} finding{(result.evidence?.length ?? 0) !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      {error && (
        <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(220,38,38,0.08)', border: '1px solid #dc2626', fontSize: 'var(--font-size-sm)', color: '#dc2626' }}>
          {error}
        </div>
      )}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {result.summary && (
            <div style={{
              padding: '10px 14px', borderRadius: '8px',
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)',
            }}>
              {result.summary}
            </div>
          )}
          <EvidenceList evidence={result.evidence} />
        </div>
      )}
    </div>
  )
}

/* ── LogCorrelatorTab ───────────────────────────────────────── */

function LogCorrelatorTab() {
  const [logText, setLogText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleCorrelate = async () => {
    if (!logText.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await analyzeKubernetes({ github_actions_log: logText })
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Correlation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
        Paste raw GitHub Actions CI/CD log output containing <code style={{ fontFamily: 'var(--font-family-mono)', fontSize: '11px' }}>kubectl</code>,
        Helm, or container runtime errors. The engine extracts and classifies embedded Kubernetes failure patterns.
      </p>
      <textarea
        id="k8s-log-input"
        value={logText}
        onChange={e => setLogText(e.target.value)}
        rows={16}
        placeholder={'Run: kubectl apply -f manifests/\nerror: error validating "deploy.yaml": ...\nHelm release failed: timed out waiting for the condition\n...'}
        style={{
          width: '100%', boxSizing: 'border-box',
          fontFamily: 'var(--font-family-mono)', fontSize: '12px',
          padding: '12px', borderRadius: '8px',
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface)', color: 'var(--color-text-primary)',
          resize: 'vertical', lineHeight: 1.5,
        }}
      />
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <button
          id="k8s-correlate-log-btn"
          type="button"
          className="btn btn-primary"
          onClick={handleCorrelate}
          disabled={loading || !logText.trim()}
        >
          {loading ? 'Correlating…' : '🔍 Correlate Log'}
        </button>
        {result && (
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            {result.evidence?.length ?? 0} pattern{(result.evidence?.length ?? 0) !== 1 ? 's' : ''} found
          </span>
        )}
      </div>
      {error && (
        <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(220,38,38,0.08)', border: '1px solid #dc2626', fontSize: 'var(--font-size-sm)', color: '#dc2626' }}>
          {error}
        </div>
      )}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {result.summary && (
            <div style={{
              padding: '10px 14px', borderRadius: '8px',
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)',
            }}>
              {result.summary}
            </div>
          )}
          <EvidenceList evidence={result.evidence} />
        </div>
      )}
    </div>
  )
}

/* ── Page ───────────────────────────────────────────────────── */

export default function KubernetesPage() {
  const [activeTab, setActiveTab] = useState('manifest')

  return (
    <>
      {/* Page header */}
      <div className="page-header">
        <h1 className="page-header__title" id="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          ☸️ Kubernetes Intelligence
          <span style={{
            fontSize: '11px', fontWeight: 700, letterSpacing: '0.06em',
            padding: '3px 8px', borderRadius: '4px',
            background: 'rgba(124,58,237,0.12)', color: '#7c3aed',
            border: '1px solid rgba(124,58,237,0.3)', fontFamily: 'var(--font-family-mono)',
          }}>
            READ-ONLY
          </span>
        </h1>
        <p className="page-header__subtitle">
          Phase 5 — Safe, read-only cluster diagnostics, manifest analysis, and CI/CD log correlation.
          No cluster mutations are ever performed.
        </p>
      </div>

      {/* Status card at top */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <KubernetesStatusCard />
      </div>

      {/* Analysis panel */}
      <div className="card" style={{ padding: 'var(--space-5)' }}>
        {/* Tab bar */}
        <div style={{
          display: 'flex', gap: '4px', borderBottom: '1px solid var(--color-border)',
          marginBottom: 'var(--space-5)', paddingBottom: '0',
        }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              id={`k8s-tab-${tab.id}`}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '8px 16px',
                fontSize: 'var(--font-size-sm)',
                fontWeight: activeTab === tab.id ? 600 : 400,
                color: activeTab === tab.id ? '#7c3aed' : 'var(--color-text-muted)',
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid #7c3aed' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'color 0.15s, border-color 0.15s',
                marginBottom: '-1px',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'manifest' && <ManifestTab />}
        {activeTab === 'pod'      && <PodTab />}
        {activeTab === 'log'      && <LogCorrelatorTab />}
      </div>

      {/* Safety advisory */}
      <div className="investigation-advisory" role="note" style={{ marginTop: 'var(--space-4)' }}>
        <svg className="investigation-advisory__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M10 2L2 17h16L10 2z" />
          <path d="M10 8v4M10 14h.01" strokeLinecap="round" />
        </svg>
        <span>
          <strong>Read-Only Guarantee.</strong> Kubernetes Intelligence (Phase 5) performs only safe, read-only diagnostics.
          No <code style={{ fontFamily: 'var(--font-family-mono)', fontSize: '11px' }}>kubectl apply</code>, no cluster mutations, no shell commands are ever executed.
          Suggested fixes require manual human review before application.
        </span>
      </div>
    </>
  )
}
