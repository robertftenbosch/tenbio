const API_BASE = '/api/v1'

export type Organism = 'ecoli' | 'yeast'
export type Strategy = 'most_frequent' | 'weighted'

export interface OptimizeProteinRequest {
  sequence: string
  organism: Organism
  strategy?: Strategy
}

export interface OptimizeDNARequest {
  sequence: string
  organism: Organism
  strategy?: Strategy
}

export interface OptimizeResponse {
  original_protein: string
  optimized_dna: string
  organism: string
  strategy: string
  length_bp: number
  length_aa: number
  gc_content: number
  original_dna?: string
  original_length_bp?: number
  codons_changed?: number
  codons_unchanged?: number
}

export interface TranslateResponse {
  dna_sequence: string
  protein_sequence: string
  length_bp: number
  length_aa: number
}

export async function optimizeProtein(request: OptimizeProteinRequest): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE}/optimize/protein`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to optimize protein')
  }

  return response.json()
}

export async function optimizeDNA(request: OptimizeDNARequest): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE}/optimize/dna`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to optimize DNA')
  }

  return response.json()
}

export async function translateDNA(sequence: string): Promise<TranslateResponse> {
  const response = await fetch(`${API_BASE}/optimize/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sequence }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to translate DNA')
  }

  return response.json()
}
