import { Sbol3ExportRequest, SequencingImportResponse } from '../types/export'

const API_BASE = '/api/v1'

export async function exportSbol3(request: Sbol3ExportRequest): Promise<Blob> {
  const response = await fetch(`${API_BASE}/export/sbol3`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Failed to export SBOL3')
  }

  return response.blob()
}

export async function importSequencing(
  file: File,
  pathwayParts?: { name: string; type: string; sequence: string }[],
): Promise<SequencingImportResponse> {
  const formData = new FormData()
  formData.append('file', file)

  if (pathwayParts && pathwayParts.length > 0) {
    formData.append('pathway_parts_json', JSON.stringify(pathwayParts))
  }

  const response = await fetch(`${API_BASE}/import/sequencing`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Failed to import sequencing file')
  }

  return response.json()
}
