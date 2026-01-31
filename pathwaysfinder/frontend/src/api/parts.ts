import { PartListResponse, Part, PapersResponse } from '../types/parts'

const API_BASE = '/api/v1'

interface FetchPartsParams {
  search?: string
  type?: string
  organism?: string
  skip?: number
  limit?: number
}

export async function fetchParts(params: FetchPartsParams = {}): Promise<PartListResponse> {
  const searchParams = new URLSearchParams()

  if (params.search) searchParams.set('search', params.search)
  if (params.type) searchParams.set('type', params.type)
  if (params.organism) searchParams.set('organism', params.organism)
  if (params.skip !== undefined) searchParams.set('skip', String(params.skip))
  if (params.limit !== undefined) searchParams.set('limit', String(params.limit))

  const queryString = searchParams.toString()
  const url = `${API_BASE}/parts${queryString ? `?${queryString}` : ''}`

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch parts: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchPartById(id: string): Promise<Part> {
  const response = await fetch(`${API_BASE}/parts/${id}`)

  if (!response.ok) {
    throw new Error(`Failed to fetch part: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchPartPapers(id: string): Promise<PapersResponse> {
  const response = await fetch(`${API_BASE}/parts/${id}/papers`)

  if (!response.ok) {
    throw new Error(`Failed to fetch papers: ${response.statusText}`)
  }

  return response.json()
}
