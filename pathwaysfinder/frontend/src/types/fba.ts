// Mirror of pathwaysfinder/api/app/schemas/fba.py.

export interface ChassisInfo {
  key: string
  description: string
  organism: string
  kegg_organism: string
  domain: 'bacterial' | 'fungal' | 'photosynthetic' | 'mammalian'
  n_reactions: number
  biomass_objective: string
}

export interface FBARequest {
  chassis: string
  objective?: 'biomass' | 'target'
  target_reaction?: string | null
  knockouts?: string[]
  carbon_source?: string | null
  carbon_uptake?: number
  flux_limit?: number
}

export interface FluxEntry {
  reaction_id: string
  flux: number
  lower_bound: number
  upper_bound: number
  name: string | null
}

export interface FBAResponse {
  chassis: string
  objective_id: string
  objective_value: number
  growth_rate: number
  target_reaction: string | null
  target_flux: number | null
  status: string
  fluxes: FluxEntry[]
  notes: string[]
}
