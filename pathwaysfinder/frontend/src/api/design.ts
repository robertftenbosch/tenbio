import {
  ChatStreamEvent,
  ChatStreamRequest,
  DesignFromCompoundRequest,
  DesignFromGoalRequest,
  DesignFromGoalResponse,
  PathwayCandidatesResponse,
} from '../types/design'

const API_BASE = '/api/v1/design'

async function postJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal
): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
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
  req: DesignFromGoalRequest,
  signal?: AbortSignal
): Promise<DesignFromGoalResponse> {
  return postJson('/from-goal', req, signal)
}

export function designFromCompound(
  req: DesignFromCompoundRequest,
  signal?: AbortSignal
): Promise<PathwayCandidatesResponse> {
  return postJson('/from-compound', req, signal)
}

/**
 * POST /api/v1/design/chat/stream and yield parsed SSE events.
 *
 * The endpoint emits `data: <json>\n\n` lines where the JSON is one of
 * { token } | { error } | { done }. We accumulate bytes across reads
 * because a token can land on a chunk boundary; only complete events
 * (terminated by \n\n) are yielded.
 *
 * Pass an AbortSignal to allow the caller to stop the stream cleanly
 * (e.g. unmount or "stop" button).
 */
export async function* streamChat(
  req: ChatStreamRequest,
  signal?: AbortSignal
): AsyncGenerator<ChatStreamEvent, void, void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(req),
    signal,
  })
  if (!response.ok || !response.body) {
    let detail = `Chat stream failed (${response.status})`
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE event delimiter is a blank line (\n\n).
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        for (const line of raw.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            yield JSON.parse(line.slice('data: '.length)) as ChatStreamEvent
          } catch {
            // skip malformed line
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
