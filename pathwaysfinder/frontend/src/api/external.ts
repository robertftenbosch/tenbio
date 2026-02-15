// External API functions for KEGG, UniProt, and iGEM

const API_BASE = '/api/v1'

// KEGG Types
export interface KeggPathway {
  id: string
  name: string
  description?: string
  organism?: string
  url?: string
}

export interface KeggEnzyme {
  ec_number: string
  name?: string
  reaction?: string
  url?: string
}

export interface KeggGene {
  id: string
  name?: string
  definition?: string
  organism?: string
  sequence?: string
}

// UniProt Types
export interface UniprotProtein {
  accession: string
  entry_name?: string
  protein_name?: string
  gene_names: string[]
  organism?: string
  length?: number
  sequence?: string
  function?: string
  url?: string
}

// iGEM Types
export interface IgemPart {
  name: string
  type: string
  description?: string
  sequence: string
  organism?: string
  source: string
}

// KEGG API
export async function searchKeggPathways(query: string, organism = 'ecoli'): Promise<KeggPathway[]> {
  const response = await fetch(
    `${API_BASE}/kegg/pathways/search?q=${encodeURIComponent(query)}&organism=${organism}&limit=10`
  )
  if (!response.ok) return []
  const data = await response.json()
  return data.pathways || []
}

export async function searchKeggEnzymes(query: string): Promise<KeggEnzyme[]> {
  const response = await fetch(
    `${API_BASE}/kegg/enzymes/search?q=${encodeURIComponent(query)}&limit=10`
  )
  if (!response.ok) return []
  const data = await response.json()
  return data.enzymes || []
}

export async function getKeggEnzymeGenes(ecNumber: string, organism = 'ecoli'): Promise<KeggGene[]> {
  const response = await fetch(
    `${API_BASE}/kegg/enzymes/${encodeURIComponent(ecNumber)}/genes?organism=${organism}`
  )
  if (!response.ok) return []
  return response.json()
}

export async function getKeggPathwayGenes(pathwayId: string, includeSequence = false): Promise<KeggGene[]> {
  const response = await fetch(
    `${API_BASE}/kegg/pathways/${encodeURIComponent(pathwayId)}/genes?include_sequence=${includeSequence}`
  )
  if (!response.ok) return []
  return response.json()
}

export async function getKeggGeneSequence(geneId: string): Promise<string | null> {
  const response = await fetch(
    `${API_BASE}/kegg/genes/${encodeURIComponent(geneId)}?include_sequence=true`
  )
  if (!response.ok) return null
  const data = await response.json()
  return data.sequence || null
}

// UniProt API
export async function searchUniprotProteins(query: string, organism?: string): Promise<UniprotProtein[]> {
  let url = `${API_BASE}/uniprot/search?q=${encodeURIComponent(query)}&limit=10`
  if (organism) {
    url += `&organism=${encodeURIComponent(organism)}`
  }
  const response = await fetch(url)
  if (!response.ok) return []
  const data = await response.json()
  return data.proteins || []
}

export async function getCommonProtein(name: string): Promise<UniprotProtein | null> {
  const response = await fetch(`${API_BASE}/uniprot/common/${encodeURIComponent(name)}`)
  if (!response.ok) return null
  return response.json()
}

// iGEM API
export async function getPopularIgemParts(type?: string): Promise<IgemPart[]> {
  let url = `${API_BASE}/igem/popular?limit=10`
  if (type) {
    url += `&type=${encodeURIComponent(type)}`
  }
  const response = await fetch(url)
  if (!response.ok) return []
  const data = await response.json()
  return data.parts || []
}

export async function importIgemPart(partName: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/igem/import/${encodeURIComponent(partName)}`, {
    method: 'POST',
  })
  return response.json()
}
