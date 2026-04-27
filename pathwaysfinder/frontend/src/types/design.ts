// Mirror of pathwaysfinder/api/app/schemas/design.py.

export type TargetKind = 'compound' | 'protein' | 'removal'
export type Confidence = 'high' | 'medium' | 'low'
export type OptimizationMetric = 'yield' | 'rate' | 'titer' | 'robustness'

export interface TargetSpec {
  kind: TargetKind
  name: string
  kegg_id: string | null
  uniprot_id: string | null
  smiles: string | null
}

export interface DesignIntent {
  raw_query: string
  target: TargetSpec
  host_candidates: string[]
  optimization_metric: OptimizationMetric | null
  constraints: string[]
  feasibility_note: string
  confidence: Confidence
}

export interface CompoundRef {
  id: string
  name: string | null
}

export interface GeneRef {
  id: string
  name: string | null
  definition: string | null
  organism: string | null
  ec_number: string | null
}

export interface ReactionStep {
  reaction_id: string
  reaction_name: string | null
  equation: string | null
  ec_numbers: string[]
  substrates: string[]
  products: string[]
  candidate_genes: GeneRef[]
  depth: number
}

export interface PathwayCandidatesResponse {
  target: CompoundRef
  host: string
  max_depth_used: number
  reactions: ReactionStep[]
  notes: string[]
}

export interface DesignFromGoalRequest {
  query: string
  skip_grounding?: boolean
  materialize?: boolean
  host?: string
  max_depth?: number
}

export interface DesignFromGoalResponse {
  intent: DesignIntent
  candidate_kegg_count: number
  candidate_uniprot_count: number
  model_used: string | null
  pathway_candidates: PathwayCandidatesResponse | null
}

export interface DesignFromCompoundRequest {
  compound: string
  host?: string
  max_depth?: number
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface ChatStreamRequest {
  messages: ChatMessage[]
  intent?: DesignIntent | null
  temperature?: number
  max_tokens?: number
}

/**
 * SSE events emitted by /api/v1/design/chat/stream. Always exactly one
 * of `token`, `error`, or `done` is set.
 */
export type ChatStreamEvent =
  | { token: string }
  | { error: string }
  | { done: true; model?: string }
