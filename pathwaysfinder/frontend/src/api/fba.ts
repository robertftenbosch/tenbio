import { ChassisInfo, FBARequest, FBAResponse } from '../types/fba'

const API_BASE = '/api/v1/simulate'

export async function listChassis(): Promise<ChassisInfo[]> {
  const r = await fetch(`${API_BASE}/chassis`)
  if (!r.ok) {
    let detail = `Failed to list chassis (${r.status})`
    try {
      detail = (await r.json()).detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return r.json()
}

export async function runFBA(req: FBARequest, signal?: AbortSignal): Promise<FBAResponse> {
  const r = await fetch(`${API_BASE}/fba`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    let detail = `FBA request failed (${r.status})`
    try {
      detail = (await r.json()).detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return r.json()
}
