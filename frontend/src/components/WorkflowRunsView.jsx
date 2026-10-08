/**
 * WorkflowRunsView component.
 *
 * Displays recent GitHub Actions workflow runs, highlights failures,
 * and allows deep diagnostics into jobs, steps, and failure logs.
 * Foundation for Phase 3 AI-driven root cause investigation.
 */

import React, { useState, useEffect } from 'react'
import { getWorkflowRuns, getWorkflowJobs, getWorkflowLogs } from '../services/github'
import { createInvestigation } from '../services/investigations'
import InvestigationResultCard from './InvestigationResultCard'

function StatusBadge({ status, conclusion, isFailed }) {
  if (isFailed) {
    return <span className="badge badge--failure">FAILED</span>
  }
  if (conclusion === 'success') {
    return <span className="badge badge--success">Success</span>
  }
  if (conclusion === 'cancelled') {
    return <span className="badge badge--public">Cancelled</span>
  }
  if (conclusion === 'skipped') {
    return <span className="badge badge--public">Skipped</span>
  }
  if (status === 'in_progress') {
    return <span className="badge badge--running">In Progress</span>
  }
  if (status === 'queued') {
    return <span className="badge badge--running">Queued</span>
  }
  return <span className="badge badge--public">{conclusion || status}</span>
}

export default function WorkflowRunsView({ owner, repo }) {
  const [runs, setRuns] = useState([])
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [runsError, setRunsError] = useState(null)

  // Selected run state
  const [selectedRun, setSelectedRun] = useState(null)
  const [jobs, setJobs] = useState([])
  const [loadingJobs, setLoadingJobs] = useState(false)
  const [jobsError, setJobsError] = useState(null)

  // Run logs state
  const [logs, setLogs] = useState(null)
  const [loadingLogs, setLoadingLogs] = useState(false)
  const [logsError, setLogsError] = useState(null)

  // AI Investigation state
  const [investigation, setInvestigation] = useState(null)
  const [investigating, setInvestigating] = useState(false)
  const [investigationError, setInvestigationError] = useState(null)

  // Status filter
  const [statusFilter, setStatusFilter] = useState('all')

  useEffect(() => {
    setInvestigation(null)
    setInvestigationError(null)
  }, [selectedRun?.id])

  useEffect(() => {
    let isMounted = true
    async function fetchRuns() {
      setLoadingRuns(true)
      setRunsError(null)
      try {
        const params = statusFilter !== 'all' ? { status: statusFilter } : {}
        const data = await getWorkflowRuns(owner, repo, params)
        if (isMounted) {
          setRuns(data)
          // If first run failed, select it by default for quick diagnostics
          if (data && data.length > 0 && !selectedRun) {
            const firstFailed = data.find((r) => r.is_failed)
            setSelectedRun(firstFailed || data[0])
          }
        }
      } catch (err) {
        if (isMounted) setRunsError(err)
      } finally {
        if (isMounted) setLoadingRuns(false)
      }
    }

    fetchRuns()
    return () => {
      isMounted = false
    }
  }, [owner, repo, statusFilter])

  // When a run is selected, fetch its jobs
  useEffect(() => {
    if (!selectedRun) return

    let isMounted = true
    async function fetchRunJobs() {
      setLoadingJobs(true)
      setJobsError(null)
      setLogs(null)
      try {
        const jobData = await getWorkflowJobs(owner, repo, selectedRun.id)
        if (isMounted) {
          setJobs(jobData)
          // Automatically fetch failure logs if the run has failed
          if (selectedRun.is_failed) {
            fetchLogs(selectedRun.id)
          }
        }
      } catch (err) {
        if (isMounted) setJobsError(err)
      } finally {
        if (isMounted) setLoadingJobs(false)
      }
    }

    fetchRunJobs()
    return () => {
      isMounted = false
    }
  }, [selectedRun?.id])

  async function fetchLogs(runId) {
    setLoadingLogs(true)
    setLogsError(null)
    try {
      const logData = await getWorkflowLogs(owner, repo, runId)
      setLogs(logData)
    } catch (err) {
      setLogsError(err)
    } finally {
      setLoadingLogs(false)
    }
  }

  async function handleInvestigate(run) {
    if (investigating) return
    const targetRun = run || selectedRun
    if (!targetRun) return

    setInvestigating(true)
    setInvestigationError(null)
    try {
      const result = await createInvestigation(owner, repo, targetRun.id)
      setInvestigation(result)
    } catch (err) {
      setInvestigationError(err)
    } finally {
      setInvestigating(false)
    }
  }

  return (
    <section aria-label="Workflow runs and diagnostics">
      {/* Run Filters */}
      <div className="controls-bar">
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="text-secondary" style={{ fontSize: 'var(--font-size-xs)' }}>
            Filter Status:
          </span>
          <button
            type="button"
            className={`btn btn-sm ${statusFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setStatusFilter('all')}
          >
            All Runs
          </button>
          <button
            type="button"
            className={`btn btn-sm ${statusFilter === 'failure' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setStatusFilter('failure')}
          >
            Failed Only
          </button>
          <button
            type="button"
            className={`btn btn-sm ${statusFilter === 'success' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setStatusFilter('success')}
          >
            Success Only
          </button>
        </div>
      </div>

      {loadingRuns && (
        <div className="empty-banner">
          <p className="text-muted">Loading workflow runs...</p>
        </div>
      )}

      {runsError && (
        <div className="error-banner" role="alert">
          <div className="error-banner__title text-error">Failed to Load Runs</div>
          <p className="error-banner__sub">{runsError.message}</p>
        </div>
      )}

      {!loadingRuns && !runsError && runs.length === 0 && (
        <div className="empty-banner">
          <div className="empty-banner__title">No Workflow Runs Found</div>
          <p className="empty-banner__sub">
            No GitHub Actions runs have been recorded for this repository matching the filter.
          </p>
        </div>
      )}

      {/* Runs List */}
      {!loadingRuns && runs.length > 0 && (
        <div className="runs-list" role="list" aria-label="Recent workflow runs">
          {runs.map((run) => {
            const isSelected = selectedRun?.id === run.id
            const cardClass = `run-item ${
              run.is_failed ? 'run-item--failed' : run.conclusion === 'success' ? 'run-item--success' : ''
            }`

            return (
              <div
                key={run.id}
                role="listitem"
                className={cardClass}
                style={{
                  outline: isSelected ? '2px solid var(--color-accent)' : 'none',
                }}
                onClick={() => setSelectedRun(run)}
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && setSelectedRun(run)}
              >
                <div className="run-item__main">
                  <StatusBadge
                    status={run.status}
                    conclusion={run.conclusion}
                    isFailed={run.is_failed}
                  />
                  <div className="run-item__info">
                    <span className="run-item__name">
                      {run.workflow_name}
                      <span className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                        #{run.run_number || run.id}
                      </span>
                    </span>
                    <div className="run-item__sub">
                      <span>branch: <strong className="text-mono">{run.branch}</strong></span>
                      <span>commit: <code className="text-mono">{run.commit_short_sha}</code></span>
                      {run.commit_message && (
                        <span className="text-muted">"{run.commit_message}"</span>
                      )}
                      <span>event: {run.event}</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <a
                    href={run.html_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="btn btn-outline btn-sm"
                    onClick={(e) => e.stopPropagation()}
                  >
                    GitHub ↗
                  </a>
                  <button
                    type="button"
                    className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                  >
                    {isSelected ? 'Viewing' : 'Inspect'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Selected Run Diagnostic Panel */}
      {selectedRun && (
        <article className="diagnostics-panel" aria-label="Run diagnostics">
          <div className="diagnostics-header">
            <div>
              <h3 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
                Run #{selectedRun.run_number || selectedRun.id}: {selectedRun.workflow_name}
              </h3>
              <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                Triggered by {selectedRun.event} on branch <span className="text-mono">{selectedRun.branch}</span> ({selectedRun.commit_short_sha})
              </p>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <StatusBadge
                status={selectedRun.status}
                conclusion={selectedRun.conclusion}
                isFailed={selectedRun.is_failed}
              />
              {selectedRun.is_failed && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => handleInvestigate(selectedRun)}
                  disabled={investigating}
                  aria-label="Investigate failure with AI"
                  id="btn-investigate-ai"
                >
                  {investigating ? 'Analyzing with AI...' : 'Investigate with AI'}
                </button>
              )}
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => fetchLogs(selectedRun.id)}
                disabled={loadingLogs}
              >
                {loadingLogs ? 'Loading Logs...' : 'Fetch Failure Logs'}
              </button>
            </div>
          </div>

          {/* Jobs & Steps Breakdown */}
          <div>
            <h4 style={{ fontSize: 'var(--font-size-sm)', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '12px' }}>
              Execution Jobs & Steps
            </h4>

            {loadingJobs && <p className="text-muted">Loading jobs breakdown...</p>}

            {jobsError && (
              <p className="text-error" style={{ fontSize: 'var(--font-size-sm)' }}>
                Failed to load jobs: {jobsError.message}
              </p>
            )}

            {!loadingJobs && jobs.length === 0 && (
              <p className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>
                No job steps reported for this run.
              </p>
            )}

            {!loadingJobs && jobs.length > 0 && (
              <div className="jobs-list">
                {jobs.map((job) => (
                  <div
                    key={job.id}
                    className={`job-card ${job.is_failed ? 'job-card--failed' : ''}`}
                  >
                    <div className="job-header">
                      <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {job.name}
                        {job.is_failed && <span className="badge badge--failure">FAILED JOB</span>}
                      </span>
                      <span className="text-mono text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                        status: {job.conclusion || job.status}
                      </span>
                    </div>

                    <div className="steps-list">
                      {job.steps.map((step) => (
                        <div
                          key={step.number}
                          className={`step-row ${step.is_failed ? 'step-row--failed' : ''}`}
                        >
                          <span>
                            #{step.number} {step.name}
                          </span>
                          <span className="text-mono">
                            {step.is_failed ? (
                              <span className="badge badge--failure">FAILED STEP</span>
                            ) : (
                              <span className="text-muted">{step.conclusion || step.status}</span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Logs View */}
          {logs && (
            <div className="log-box" aria-label="Workflow failure logs">
              <div className="log-box__header">
                <span>
                  Diagnostic Log Snippet {logs.total_lines ? `(${logs.total_lines} total lines)` : ''}
                </span>
                {logs.truncated && (
                  <span className="badge badge--running">Tail 500 lines</span>
                )}
              </div>
              <div className="log-box__content">
                {logs.content || logs.message || 'No log output available.'}
              </div>
            </div>
          )}

          {logsError && (
            <p className="text-error" style={{ fontSize: 'var(--font-size-xs)', marginTop: '12px' }}>
              Could not retrieve logs: {logsError.message}
            </p>
          )}

          {/* AI Investigation Section */}
          {investigating && (
            <div className="empty-banner" style={{ marginTop: 'var(--space-6)' }} role="status">
              <p style={{ color: 'var(--color-accent)', fontWeight: 600 }}>
                Analyzing workflow run with AI DevOps Engine...
              </p>
              <p className="text-secondary" style={{ fontSize: 'var(--font-size-xs)', marginTop: '4px' }}>
                Extracting failed jobs, sanitizing logs, and querying OmniRoute for root causes.
              </p>
            </div>
          )}

          {investigationError && (
            <div className="error-banner" role="alert" style={{ marginTop: 'var(--space-6)' }}>
              <div className="error-banner__title text-error">AI Investigation Failed</div>
              <p className="error-banner__sub">{investigationError.message}</p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleInvestigate(selectedRun)}
              >
                Retry AI Investigation
              </button>
            </div>
          )}

          {investigation && (
            <div style={{ marginTop: 'var(--space-6)' }}>
              <InvestigationResultCard
                investigation={investigation}
                onBack={() => setInvestigation(null)}
              />
            </div>
          )}
        </article>
      )}
    </section>
  )
}
