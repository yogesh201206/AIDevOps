/**
 * API service layer.
 *
 * All HTTP calls to the backend go through this module.
 * Components never import axios directly.
 *
 * Base URL is configured via the VITE_API_BASE_URL environment variable
 * (default: http://localhost:8000).
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/**
 * Pre-configured Axios instance shared across all API calls.
 * Centralise headers, interceptors, and error handling here.
 */
const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 8000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

// ── Response interceptor: normalise errors ──────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Attach a human-readable message and error metadata for UI error states
    const detail = error?.response?.data?.detail
    const message =
      (typeof detail === 'object' && detail !== null ? detail.message : detail) ??
      error?.message ??
      'An unexpected error occurred'
    const err = new Error(message)
    err.code = typeof detail === 'object' && detail !== null ? detail.code : null
    err.status = error?.response?.status
    return Promise.reject(err)
  }
)

// ── Health endpoints ─────────────────────────────────────────────────────────

/**
 * Fetch liveness status from the backend.
 * Returns the parsed JSON response body.
 * Throws an Error if the request fails.
 *
 * @returns {{ status: string, service: string }}
 */
export async function fetchHealth() {
  const { data } = await apiClient.get('/api/v1/health')
  return data
}

/**
 * Fetch readiness status from the backend.
 *
 * @returns {{ status: string, service: string, environment: string, version: string, checks: object }}
 */
export async function fetchReadiness() {
  const { data } = await apiClient.get('/api/v1/health/ready')
  return data
}

// ── Future endpoints (Phase 2+) ─────────────────────────────────────────────
// export async function fetchRepositories() { ... }
// export async function fetchInvestigations() { ... }
// export async function startInvestigation(payload) { ... }
// export async function fetchDeployments() { ... }

export default apiClient
