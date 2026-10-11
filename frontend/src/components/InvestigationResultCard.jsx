/**
 * InvestigationResultCard component.
 *
 * Renders structured DevOps AI root cause analysis reports with
 * expandable evidence, actionable suggested fixes, validation steps,
 * and safety advisories.
 */

import React, { useState } from 'react'

function getConfidenceMeta(score) {
  const num = typeof score === 'number' ? score : parseFloat(score) || 0
  const pct = Math.round(num * 100)
  if (num >= 0.90) return { label: `${pct}% Very High`, className: 'confidence-pill--high' }
  if (num >= 0.75) return { label: `${pct}% High`, className: 'confidence-pill--high' }
  if (num >= 0.50) return { label: `${pct}% Medium`, className: 'confidence-pill--medium' }
  return { label: `${pct}% Low`, className: 'confidence-pill--low' }
}

export default function InvestigationResultCard({ investigation, onBack }) {
  const [expandedEvidence, setExpandedEvidence] = useState({})

  if (!investigation) return null

  const toggleEvidence = (index) => {
    setExpandedEvidence((prev) => {
      const current = prev[index] ?? true
      return {
        ...prev,
        [index]: !current,
      }
    })
  }

  const confidenceMeta = getConfidenceMeta(investigation.confidence)
  const severity = (investigation.severity || 'high').toLowerCase()
  const severityClass = `severity-badge--${severity}`

  return (
    <article className="investigation-report" aria-label="AI Investigation Report">
      {/* Safety & Scope Notice */}
      <div className="investigation-advisory" role="note">
        <svg
          className="investigation-advisory__icon"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path d="M10 2L2 17h16L10 2z" />
          <path d="M10 8v4M10 14h.01" strokeLinecap="round" />
        </svg>
        <span>
          <strong>Suggested Fix ≠ Automatically Applied Fix.</strong> Phase 3 provides analysis and suggested fixes only. No automatic changes are executed.
        </span>
      </div>

      {/* Header */}
      <div className="investigation-report__header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h3 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, color: 'var(--color-text-primary)' }}>
              AI Investigation
            </h3>
            <span className={`severity-badge ${severityClass}`}>
              {severity.toUpperCase()} SEVERITY
            </span>
            <span className={`confidence-pill ${confidenceMeta.className}`}>
              Confidence: {confidenceMeta.label}
            </span>
          </div>

          <p className="text-secondary" style={{ fontSize: 'var(--font-size-sm)', marginTop: '4px' }}>
            Workflow: <strong>{investigation.workflow_name}</strong> · Run #{investigation.workflow_run_id} · Repository:{' '}
            <span className="text-mono">{investigation.repository}</span>
          </p>
        </div>

        <div className="investigation-report__meta">
          <span className="badge badge--public">
            Model: {investigation.model || 'gpt-4o-mini'}
          </span>
          <span className="badge badge--public">
            Provider: {investigation.provider || 'OmniRoute'}
          </span>
          {onBack && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onBack}>
              ← Back to List
            </button>
          )}
        </div>
      </div>

      {/* Section 1: Executive Summary */}
      <section className="investigation-section">
        <h4 className="investigation-section__title">
          <span>Executive Summary</span>
        </h4>
        <div className="investigation-summary-box">
          {investigation.summary}
        </div>
      </section>

      {/* Section 2: Root Causes */}
      {investigation.root_causes && investigation.root_causes.length > 0 && (
        <section className="investigation-section">
          <h4 className="investigation-section__title">
            <span>Probable Root Cause{investigation.root_causes.length > 1 ? 's' : ''}</span>
          </h4>
          <div>
            {investigation.root_causes.map((rc, idx) => {
              const rcConf = getConfidenceMeta(rc.confidence)
              return (
                <div key={idx} className="root-cause-card">
                  <div className="root-cause-card__header">
                    <span className="root-cause-card__title">
                      {idx + 1}. {rc.cause}
                    </span>
                    <span className={`confidence-pill ${rcConf.className}`} style={{ fontSize: '10px' }}>
                      {rcConf.label}
                    </span>
                  </div>
                  <p className="root-cause-card__body">{rc.explanation}</p>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Section 3: Supporting Evidence */}
      {investigation.evidence && investigation.evidence.length > 0 && (
        <section className="investigation-section">
          <h4 className="investigation-section__title">
            <span>Diagnostic Evidence ({investigation.evidence.length})</span>
          </h4>
          <div>
            {investigation.evidence.map((ev, idx) => {
              const isExpanded = expandedEvidence[idx] ?? true
              return (
                <div key={idx} className="evidence-card">
                  <div
                    className="evidence-card__header"
                    onClick={() => toggleEvidence(idx)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && toggleEvidence(idx)}
                  >
                    <span className="evidence-card__source">
                      <span>Source: {ev.source}</span>
                      <span className="badge badge--running" style={{ fontSize: '10px' }}>
                        {ev.importance || 'high'}
                      </span>
                    </span>
                    <span className="text-secondary" style={{ fontSize: 'var(--font-size-xs)' }}>
                      {isExpanded ? 'Hide Evidence ▲' : 'Show Evidence ▼'}
                    </span>
                  </div>
                  {isExpanded && (
                    <div className="evidence-card__body">
                      {ev.detail}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Section 3.1: Docker Intelligence Analysis (Phase 4) */}
      {investigation.docker_evidence && investigation.docker_evidence.length > 0 && (
        <section className="investigation-section" aria-label="Docker Intelligence Analysis">
          <h4 className="investigation-section__title">
            <span>🐳 Docker Intelligence ({investigation.docker_evidence.length})</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {investigation.docker_evidence.map((dev, idx) => {
              const devConf = getConfidenceMeta(dev.confidence)
              const devSev = (dev.severity || 'high').toLowerCase()
              const isExpanded = expandedEvidence[`docker_${idx}`] ?? true
              return (
                <div key={idx} className="evidence-card" style={{ borderLeft: '3px solid var(--color-primary)' }}>
                  <div
                    className="evidence-card__header"
                    onClick={() => toggleEvidence(`docker_${idx}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && toggleEvidence(`docker_${idx}`)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span className="badge badge--public" style={{ textTransform: 'capitalize' }}>
                        Component: {dev.component}
                      </span>
                      <span className={`severity-badge severity-badge--${devSev}`} style={{ fontSize: '10px' }}>
                        {devSev.toUpperCase()}
                      </span>
                      <span className={`confidence-pill ${devConf.className}`} style={{ fontSize: '10px' }}>
                        {devConf.label}
                      </span>
                      <span style={{ fontWeight: 600, color: 'var(--color-text-primary)', fontSize: 'var(--font-size-sm)' }}>
                        {dev.message}
                      </span>
                    </div>
                    <span className="text-secondary" style={{ fontSize: 'var(--font-size-xs)' }}>
                      {isExpanded ? 'Hide Evidence ▲' : 'Show Evidence ▼'}
                    </span>
                  </div>
                  {isExpanded && (
                    <div className="evidence-card__body">
                      <div style={{ marginBottom: '6px', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                        <strong>Source:</strong> {dev.source} · <strong>Category:</strong> {dev.category}
                      </div>
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: 'var(--font-family-mono)', fontSize: 'var(--font-size-xs)' }}>
                        {dev.evidence}
                      </pre>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Section 3.2: Kubernetes Intelligence Analysis (Phase 5) */}
      {investigation.kubernetes_evidence && investigation.kubernetes_evidence.length > 0 && (
        <section className="investigation-section" aria-label="Kubernetes Intelligence Analysis">
          <h4 className="investigation-section__title">
            <span>☸️ Kubernetes Intelligence ({investigation.kubernetes_evidence.length})</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {investigation.kubernetes_evidence.map((kev, idx) => {
              const kevConf = getConfidenceMeta(kev.confidence)
              const kevSev = (kev.severity || 'high').toLowerCase()
              const isExpanded = expandedEvidence[`k8s_${idx}`] ?? true
              return (
                <div key={idx} className="evidence-card" style={{ borderLeft: '3px solid #7c3aed' }}>
                  <div
                    className="evidence-card__header"
                    onClick={() => toggleEvidence(`k8s_${idx}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && toggleEvidence(`k8s_${idx}`)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span className="badge badge--public" style={{ textTransform: 'capitalize', background: 'rgba(124,58,237,0.12)', color: '#7c3aed', border: '1px solid rgba(124,58,237,0.3)' }}>
                        {kev.resource_kind}/{kev.namespace}
                      </span>
                      <span className={`severity-badge severity-badge--${kevSev}`} style={{ fontSize: '10px' }}>
                        {kevSev.toUpperCase()}
                      </span>
                      <span className={`confidence-pill ${kevConf.className}`} style={{ fontSize: '10px' }}>
                        {kevConf.label}
                      </span>
                      <span style={{ fontWeight: 600, color: 'var(--color-text-primary)', fontSize: 'var(--font-size-sm)' }}>
                        {kev.message}
                      </span>
                    </div>
                    <span className="text-secondary" style={{ fontSize: 'var(--font-size-xs)' }}>
                      {isExpanded ? 'Hide Evidence ▲' : 'Show Evidence ▼'}
                    </span>
                  </div>
                  {isExpanded && (
                    <div className="evidence-card__body">
                      <div style={{ marginBottom: '6px', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                        <strong>Resource:</strong> {kev.resource_name} &nbsp;·&nbsp;
                        <strong>Source:</strong> {kev.source} &nbsp;·&nbsp;
                        <strong>Category:</strong> {kev.category}
                      </div>
                      {kev.probable_root_cause && (
                        <div style={{ marginBottom: '6px', fontSize: 'var(--font-size-xs)' }}>
                          <strong style={{ color: 'var(--color-text-secondary)' }}>Root Cause:</strong>{' '}
                          {kev.probable_root_cause}
                        </div>
                      )}
                      {kev.suggested_fix && (
                        <div style={{ marginBottom: '6px', fontSize: 'var(--font-size-xs)', color: '#16a34a' }}>
                          <strong>Suggested Fix:</strong> {kev.suggested_fix}
                        </div>
                      )}
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: 'var(--font-family-mono)', fontSize: 'var(--font-size-xs)' }}>
                        {kev.evidence}
                      </pre>
                      {kev.validation_steps && kev.validation_steps.length > 0 && (
                        <div style={{ marginTop: '8px' }}>
                          <strong style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>Validation:</strong>
                          <ul style={{ margin: '4px 0 0 0', paddingLeft: '16px' }}>
                            {kev.validation_steps.map((step, si) => (
                              <li key={si} style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-family-mono)' }}>
                                {step}
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
        </section>
      )}


      {investigation.affected_components && investigation.affected_components.length > 0 && (
        <section className="investigation-section">
          <h4 className="investigation-section__title">
            <span>Affected Components</span>
          </h4>
          <div className="component-tags">
            {investigation.affected_components.map((comp, idx) => (
              <span key={idx} className="component-tag">
                {comp}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Section 5: Suggested Fixes */}
      {investigation.suggested_fixes && investigation.suggested_fixes.length > 0 && (
        <section className="investigation-section">
          <h4 className="investigation-section__title">
            <span>Suggested Fixes (Manual Review Required)</span>
          </h4>
          <div>
            {investigation.suggested_fixes.map((fix, idx) => (
              <div key={idx} className="fix-card">
                <div className="fix-card__title">
                  <span>Recommendation #{idx + 1}</span>
                </div>
                <div className="fix-card__desc">
                  {fix.description}
                </div>
                {fix.reason && (
                  <div className="fix-card__reason">
                    <strong>Rationale:</strong> {fix.reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Section 6: Validation Steps */}
      {investigation.validation_steps && investigation.validation_steps.length > 0 && (
        <section className="investigation-section">
          <h4 className="investigation-section__title">
            <span>Validation & Verification Checklist</span>
          </h4>
          <ul className="validation-list">
            {investigation.validation_steps.map((step, idx) => (
              <li key={idx} className="validation-item">
                <span className="validation-item__num">Step {idx + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Report Footer */}
      <footer style={{ marginTop: 'var(--space-6)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
        <span>Investigation ID: <code className="text-mono">{investigation.investigation_id}</code></span>
        <span>Generated: {investigation.created_at ? new Date(investigation.created_at).toLocaleString() : 'Just now'}</span>
      </footer>
    </article>
  )
}
