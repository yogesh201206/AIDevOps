/**
 * Investigations API service.
 *
 * Provides API client functions to query AI provider status,
 * trigger AI-powered workflow failure investigations, and query
 * investigation history reports.
 */

import apiClient from './api'

/**
 * Fetch AI provider connectivity and configuration status.
 *
 * @returns {Promise<{ configured: boolean, available: boolean, provider: string, model: string }>}
 */
export async function getAIStatus() {
  const { data } = await apiClient.get('/api/v1/ai/status')
  return data
}

/**
 * Trigger an AI incident investigation for a workflow run.
 * Uses a longer timeout since LLM inference and log analysis may take several seconds.
 *
 * @param {string} owner - Repository owner
 * @param {string} repo - Repository name
 * @param {number} runId - Workflow run ID
 * @returns {Promise<object>} Complete InvestigationResponse
 */
export async function createInvestigation(owner, repo, runId) {
  const { data } = await apiClient.post(
    '/api/v1/investigations',
    { owner, repo, run_id: runId },
    { timeout: 120000 }
  )
  return data
}

/**
 * List historical investigations.
 *
 * @param {object} params - Query params (e.g. { repository, limit })
 * @returns {Promise<Array<object>>} List of InvestigationListItem
 */
export async function getInvestigations(params = {}) {
  const { data } = await apiClient.get('/api/v1/investigations', { params })
  return data
}

/**
 * Get detailed report for a single investigation.
 *
 * @param {string} investigationId
 * @returns {Promise<object>} InvestigationResponse
 */
export async function getInvestigation(investigationId) {
  const { data } = await apiClient.get(`/api/v1/investigations/${investigationId}`)
  return data
}
