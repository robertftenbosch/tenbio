export interface Part {
  id: string
  name: string
  type: 'promoter' | 'rbs' | 'terminator' | 'gene'
  description: string | null
  sequence: string
  organism: string | null
  source: string | null
  created_at: string
  updated_at: string | null
}

export interface PartListResponse {
  parts: Part[]
  total: number
}

export type PartType = Part['type']

export const PART_TYPES: PartType[] = ['promoter', 'rbs', 'terminator', 'gene']

export const ORGANISMS = ['ecoli', 'yeast'] as const
export type Organism = (typeof ORGANISMS)[number]

export interface Paper {
  pmid: string | null
  title: string | null
  authors: string[]
  abstract: string | null
  journal: string | null
  year: string | null
  doi: string | null
  doi_url: string | null
  url: string | null
}

export interface PapersResponse {
  papers: Paper[]
  query: string
}
