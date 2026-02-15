export interface ChainInput {
  type: 'protein' | 'dna' | 'rna' | 'ligand' | 'ion'
  sequence?: string
  ligand_id?: string
  ion_id?: string
  count: number
}

export interface PredictionRequest {
  name: string
  chains: ChainInput[]
  model_name: string
  num_samples: number
}

export interface PredictionResponse {
  job_id: string
  status: string
  message: string
}

export interface ConfidenceScores {
  plddt: number | null
  ptm: number | null
  iptm: number | null
  ranking_score: number | null
}

export interface JobStatus {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  error: string | null
  confidence: ConfidenceScores | null
  structure_available: boolean
}

export interface ProtenixModel {
  name: string
  description: string
  parameters_m: number
  features: string[]
  speed_tier: 'fast' | 'medium' | 'slow'
  default: boolean
  loaded: boolean
}

export interface PreloadResponse {
  model_name: string
  status: 'loading' | 'already_loaded' | 'error'
  message: string
}

export const COMMON_IONS = ['MG', 'ZN', 'FE', 'CA', 'NA', 'K', 'MN', 'CU', 'CO'] as const
export type IonType = (typeof COMMON_IONS)[number]
