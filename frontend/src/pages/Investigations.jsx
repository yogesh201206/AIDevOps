/**
 * Investigations page.
 *
 * Primary interface for Phase 3 AI Incident Investigation Engine:
 *  1. Shows live OmniRoute AI provider connectivity status.
 *  2. Manual launcher to trigger analysis for any GitHub repository & workflow run ID.
 *  3. Historical investigations list with filtering by repository.
 *  4. Deep dive into full diagnostic reports, root causes, evidence, and suggested fixes.
 */

import React, { useState, useEffect } from 'react'
import AIStatusCard from '../components/AIStatusCard'
import InvestigationResultCard from '../components/InvestigationResultCard'
import {
  getAIStatus,
  getInvestigations,
  getInvestigation,
  createInvestigation,
} from '../services/investigations'

export default function Investigations() {
  const [aiStatus, setAiStatus] = useState(null)
  const [loadingAiStatus, setLoadingAiStatus] = useState(true)
  const [aiStatusError, setAiStatusError] = useState(null)

  const [investigations, setInvestigations] = useState([])
  const [loadingList, setLoadingList] = useState(true)
  const [listError, setListError] = useState(null)

  const [selectedInvestigation, setSelectedInvestigation] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState(null)

  // Manual Trigger Form state
  const [ownerInput, setOwnerInput] = useState('')
  const [repoInput, setRepoInput] = useState('')
  const [runIdInput, setRunIdInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)

  // Filter state
  const [filterRepo, setFilterRepo] = useState('')

  const loadAIStatus = async () => {
    setLoadingAiStatus(true)
    setAiStatusError(null)
    try {
      const data = await getAIStatus()
      setAiStatus(data)
      return data
    } catch (err) {
      setAiStatusError(err)
      return null
    } finally {
      setLoadingAiStatus(false)
    }
  }

  const loadInvestigations = async () => {
    setLoadingList(true)
    setListError(null)
    try {
      const data = await getInvestigations()
      setInvestigations(data)
    } catch (err) {
      setListError(err)
    } finally {
      setLoadingList(false)
    }
  }

  useEffect(() => {
    loadAIStatus()
    loadInvestigations()
  }, [])

  const handleSelectInvestigation = async (invId) => {
    setLoadingDetail(true)
    setDetailError(null)
    try {
      const data = await getInvestigation(invId)
      setSelectedInvestigation(data)
    } catch (err) {
      setDetailError(err)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleManualInvestigate = async (e) => {
    e.preventDefault()
    if (!ownerInput.trim() || !repoInput.trim() || !runIdInput.trim()) return

    const runId = parseInt(runIdInput.trim(), 10)
    if (isNaN(runId) || runId <= 0) {
      setSubmitError(new Error('Workflow run ID must be a positive integer.'))
      return
    }

    setSubmitting(true)
    setSubmitError(null)
    try {
      const result = await createInvestigation(ownerInput.trim(), repoInput.trim(), runId)
      setSelectedInvestigation(result)
      // Refresh list in background
      loadInvestigations()
    } catch (err) {
      setSubmitError(err)
    } finally {
      setSubmitting(false)
    }
  }

  const filteredItems = investigations.filter((item) => {
    if (!filterRepo) return true
    return item.repository.toLowerCase().includes(filterRepo.toLowerCase())
  })

  return (
    <>
      <div className="page-header">
        <h1 className="page-header__title" id="investigations-page-title">
          AI Incident Investigations
        </h1>
        <p className="page-header__subtitle">
          Phase 3 AI Investigation Engine — Automated root-cause diagnostics, evidence extraction, and suggested fixes via OmniRoute.
        </p>
      </div>

      {/* AI Provider Status */}
      <AIStatusCard
        status={aiStatus}
        loading={loadingAiStatus}
        error={aiStatusError}
        onRefresh={loadAIStatus}
      />

      {/* Detailed Investigation View */}
      {selectedInvestigation ? (
        <div>
          <InvestigationResultCard
            investigation={selectedInvestigation}
            onBack={() => setSelectedInvestigation(null)}
          />
        </div>
      ) : (
        <>
          {/* Manual Investigation Form */}
          <section className="card" style={{ marginBottom: 'var(--space-6)' }} aria-label="Start investigation">
            <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-3)' }}>
              Start Investigation
            </h3>
            <p className="text-secondary" style={{ fontSize: 'var(--font-size-xs)', marginBottom: 'var(--space-4)' }}>
              Enter repository details and a failed GitHub Actions run ID to trigger an AI root-cause analysis.
            </p>

            <form onSubmit={handleManualInvestigate} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div style={{ flex: '1 1 180px' }}>
                <label htmlFor="input-owner" style={{ display: 'block', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
                  Owner / Org
                </label>
                <input
                  id="input-owner"
                  type="text"
                  className="input"
                  placeholder="e.g. facebook"
                  value={ownerInput}
                  onChange={(e) => setOwnerInput(e.target.value)}
                  required
                />
              </div>

              <div style={{ flex: '1 1 180px' }}>
                <label htmlFor="input-repo" style={{ display: 'block', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
                  Repository
                </label>
                <input
                  id="input-repo"
                  type="text"
                  className="input"
                  placeholder="e.g. react"
                  value={repoInput}
                  onChange={(e) => setRepoInput(e.target.value)}
                  required
                />
              </div>

              <div style={{ flex: '1 1 140px' }}>
                <label htmlFor="input-run-id" style={{ display: 'block', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
                  Run ID
                </label>
                <input
                  id="input-run-id"
                  type="number"
                  className="input"
                  placeholder="e.g. 1234567"
                  value={runIdInput}
                  onChange={(e) => setRunIdInput(e.target.value)}
                  required
                />
              </div>

              <div>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting}
                  id="btn-start-investigation"
                >
                  {submitting ? 'Analyzing with AI...' : 'Investigate Run'}
                </button>
              </div>
            </form>

            {submitError && (
              <div className="error-banner" role="alert" style={{ marginTop: 'var(--space-4)', padding: 'var(--space-4)' }}>
                <div className="error-banner__title text-error" style={{ fontSize: 'var(--font-size-sm)' }}>
                  Failed to start investigation
                </div>
                <p className="error-banner__sub" style={{ fontSize: 'var(--font-size-xs)', marginBottom: 0 }}>
                  {submitError.message}
                </p>
              </div>
            )}
          </section>

          {/* History Controls Bar */}
          <div className="controls-bar">
            <div style={{ flex: '1 1 240px', maxWidth: '360px' }}>
              <input
                type="text"
                className="input"
                placeholder="Filter history by repository..."
                value={filterRepo}
                onChange={(e) => setFilterRepo(e.target.value)}
                aria-label="Filter investigations by repository"
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={loadInvestigations}
              disabled={loadingList}
            >
              Refresh History
            </button>
          </div>

          {/* Loading Detail state */}
          {loadingDetail && (
            <div className="empty-banner">
              <p className="text-muted">Loading investigation report...</p>
            </div>
          )}

          {detailError && (
            <div className="error-banner" role="alert">
              <div className="error-banner__title text-error">Could not load report</div>
              <p className="error-banner__sub">{detailError.message}</p>
            </div>
          )}

          {/* Investigation List */}
          {loadingList && (
            <div className="empty-banner">
              <p className="text-muted">Loading investigation history...</p>
            </div>
          )}

          {listError && (
            <div className="error-banner" role="alert">
              <div className="error-banner__title text-error">Failed to load history</div>
              <p className="error-banner__sub">{listError.message}</p>
            </div>
          )}

          {!loadingList && !listError && filteredItems.length === 0 && (
            <div className="empty-banner" aria-label="No investigations found">
              <div className="empty-banner__title">No Investigations Recorded</div>
              <p className="empty-banner__sub">
                No pipeline failure investigations have been run yet. Select a failed run in the Repositories tab or trigger an investigation above.
              </p>
            </div>
          )}

          {!loadingList && filteredItems.length > 0 && (
            <div className="runs-list" role="list" aria-label="Investigation history list">
              {filteredItems.map((item) => (
                <div
                  key={item.investigation_id}
                  role="listitem"
                  className="run-item"
                  onClick={() => handleSelectInvestigation(item.investigation_id)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSelectInvestigation(item.investigation_id)}
                >
                  <div className="run-item__main">
                    <span className={`severity-badge severity-badge--${item.severity.toLowerCase()}`}>
                      {item.severity}
                    </span>
                    <div className="run-item__info">
                      <span className="run-item__name">
                        {item.repository} · {item.workflow_name} #{item.workflow_run_id}
                      </span>
                      <p className="text-secondary" style={{ fontSize: 'var(--font-size-xs)' }}>
                        {item.summary}
                      </p>
                      <div className="run-item__sub">
                        <span>Confidence: <strong>{Math.round(item.confidence * 100)}%</strong></span>
                        <span>Model: <code className="text-mono">{item.model}</code></span>
                        <span>Date: {new Date(item.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleSelectInvestigation(item.investigation_id)
                      }}
                    >
                      View Report →
                    </button>
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
