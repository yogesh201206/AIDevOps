/**
 * Kubernetes Intelligence API service — Phase 5.
 *
 * Provides read-only frontend methods for:
 * - Cluster connection status
 * - Static manifest analysis
 * - Composite resource analysis (pod status, deployment, events, logs)
 * - Live resource inspection (requires connected cluster)
 */

import apiClient from './api'

/**
 * Get Kubernetes cluster connectivity and configuration status.
 *
 * @returns {Promise<object>} KubernetesStatusResponse
 */
export async function getKubernetesStatus() {
  const { data } = await apiClient.get('/api/v1/kubernetes/status')
  return data
}

/**
 * Submit Kubernetes artifacts for comprehensive analysis.
 *
 * @param {object} payload - KubernetesAnalysisRequest
 *   {
 *     manifest_content?: string,
 *     pod_status?: object,
 *     deployment_status?: object,
 *     events?: object[],
 *     logs?: string,
 *     namespace?: string,
 *     resource_name?: string,
 *     github_actions_log?: string,
 *     live_inspect?: boolean,
 *   }
 * @returns {Promise<object>} KubernetesAnalysisResponse
 */
export async function analyzeKubernetes(payload) {
  const { data } = await apiClient.post('/api/v1/kubernetes/analyze', payload)
  return data
}

/**
 * Analyze a raw Kubernetes YAML manifest for defects and misconfigurations.
 *
 * @param {string} yamlContent - Raw YAML manifest text
 * @param {string} [filename]  - Optional filename for diagnostic labels
 * @returns {Promise<object[]>} Array of KubernetesEvidence items
 */
export async function analyzeKubernetesManifest(yamlContent, filename) {
  const { data } = await apiClient.post('/api/v1/kubernetes/manifests/analyze', {
    yaml_content: yamlContent,
    filename,
  })
  return data
}

/**
 * Inspect live Kubernetes resources in a target namespace (read-only).
 * Requires a connected cluster.
 *
 * @param {object} payload - KubernetesResourceInspectionRequest
 * @returns {Promise<object[]>} Array of KubernetesEvidence items
 */
export async function inspectKubernetesResources(payload) {
  const { data } = await apiClient.post('/api/v1/kubernetes/resources/inspect', payload)
  return data
}
