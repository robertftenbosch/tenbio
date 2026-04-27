import {
  DesignFromCompoundRequest,
  DesignFromGoalRequest,
  DesignFromGoalResponse,
  PathwayCandidatesResponse,
} from '../types/design'

const API_BASE = '/api/v1/design'

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    let detail = `Request failed (${r.status})`
    try {
      const data = await r.json()
      detail = data.detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return r.json()
}

export function designFromGoal(
  req: DesignFromGoalRequest
): Promise<DesignFromGoalResponse> {
  return postJson('/from-goal', req)
}

export function designFromCompound(
  req: DesignFromCompoundRequest
): Promise<PathwayCandidatesResponse> {
  return postJson('/from-compound', req)
}
