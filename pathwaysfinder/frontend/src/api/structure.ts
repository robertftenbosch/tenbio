import {
  PredictionRequest,
  PredictionResponse,
  JobStatus,
  ProtenixModel,
} from '../types/structure'

const API_BASE = '/api/v1/structure'

export async function submitPrediction(
  request: PredictionRequest
): Promise<PredictionResponse> {
  const response = await fetch(`${API_BASE}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: 'Prediction service error' }))
    throw new Error(data.detail || 'Failed to submit prediction')
  }
  return response.json()
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`)
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: 'Failed to fetch job status' }))
    throw new Error(data.detail || 'Failed to fetch job status')
  }
  return response.json()
}

export function getStructureUrl(jobId: string): string {
  return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/structure`
}

export async function getAvailableModels(): Promise<ProtenixModel[]> {
  const response = await fetch(`${API_BASE}/models`)
  if (!response.ok) return []
  const data = await response.json()
  return data.models || []
}
