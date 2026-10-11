/**
 * Docker Intelligence API service.
 *
 * Phase 4: Provides frontend API client methods to trigger Docker analysis
 * and query Docker daemon status.
 */

import apiClient from './api'

/**
 * Send Docker artifacts (Dockerfile, build log, compose, container info) for analysis.
 *
 * @param {object} payload - DockerAnalysisRequest
 * @returns {Promise<object>} DockerAnalysisResponse
 */
export async function analyzeDocker(payload) {
  const { data } = await apiClient.post('/api/v1/docker/analyze', payload)
  return data
}

/**
 * Get read-only status of the host Docker daemon.
 *
 * @returns {Promise<object>} Daemon status object
 */
export async function getDockerStatus() {
  const { data } = await apiClient.get('/api/v1/docker/status')
  return data
}
