/**
 * GitHub API service layer.
 *
 * Centralizes all GitHub integration network calls.
 * Communicates exclusively with the FastAPI backend, never directly with GitHub.
 */

import apiClient from './api'

/**
 * Fetch GitHub connection status (connected, username, rate limit).
 * @returns {Promise<{ connected: boolean, username?: string, reason?: string, rate_limit_remaining?: number }>}
 */
export async function getGitHubStatus() {
  const { data } = await apiClient.get('/api/v1/github/status')
  return data
}

/**
 * List accessible GitHub repositories for the authenticated user.
 * @param {{ page?: number, per_page?: number, sort?: string }} [params]
 * @returns {Promise<Array<object>>}
 */
export async function getRepositories(params = {}) {
  const { data } = await apiClient.get('/api/v1/github/repositories', { params })
  return data
}

/**
 * Fetch detailed metadata for a single repository.
 * @param {string} owner
 * @param {string} repo
 * @returns {Promise<object>}
 */
export async function getRepository(owner, repo) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}`)
  return data
}

/**
 * List branches for a repository.
 * @param {string} owner
 * @param {string} repo
 * @returns {Promise<Array<{ name: string, commit_sha: string, protected: boolean }>>}
 */
export async function getBranches(owner, repo) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/branches`)
  return data
}

/**
 * List recent commits for a repository.
 * @param {string} owner
 * @param {string} repo
 * @param {{ page?: number, per_page?: number }} [params]
 * @returns {Promise<Array<object>>}
 */
export async function getCommits(owner, repo, params = {}) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/commits`, { params })
  return data
}

/**
 * List GitHub Actions workflows in a repository.
 * @param {string} owner
 * @param {string} repo
 * @returns {Promise<Array<object>>}
 */
export async function getWorkflows(owner, repo) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/workflows`)
  return data
}

/**
 * List recent workflow runs for a repository.
 * @param {string} owner
 * @param {string} repo
 * @param {{ status?: string, branch?: string, page?: number, per_page?: number }} [params]
 * @returns {Promise<Array<object>>}
 */
export async function getWorkflowRuns(owner, repo, params = {}) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/runs`, { params })
  return data
}

/**
 * Fetch details for a specific workflow run.
 * @param {string} owner
 * @param {string} repo
 * @param {number|string} runId
 * @returns {Promise<object>}
 */
export async function getWorkflowRun(owner, repo, runId) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/runs/${runId}`)
  return data
}

/**
 * Fetch jobs and steps for a workflow run, identifying failed steps.
 * @param {string} owner
 * @param {string} repo
 * @param {number|string} runId
 * @returns {Promise<Array<object>>}
 */
export async function getWorkflowJobs(owner, repo, runId) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/runs/${runId}/jobs`)
  return data
}

/**
 * Retrieve diagnostic failure logs for a workflow run.
 * @param {string} owner
 * @param {string} repo
 * @param {number|string} runId
 * @param {{ max_lines?: number }} [params]
 * @returns {Promise<{ run_id: number, job_id?: number, available: boolean, content?: string, truncated: boolean, total_lines?: number, message?: string }>}
 */
export async function getWorkflowLogs(owner, repo, runId, params = {}) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/runs/${runId}/logs`, { params })
  return data
}

/**
 * Retrieve raw logs for a specific workflow job.
 * @param {string} owner
 * @param {string} repo
 * @param {number|string} jobId
 * @param {{ max_lines?: number }} [params]
 * @returns {Promise<object>}
 */
export async function getJobLogs(owner, repo, jobId, params = {}) {
  const { data } = await apiClient.get(`/api/v1/github/repositories/${owner}/${repo}/jobs/${jobId}/logs`, { params })
  return data
}
