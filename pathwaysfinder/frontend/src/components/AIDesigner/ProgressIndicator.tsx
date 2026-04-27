import { useEffect, useState } from 'react'

interface Props {
  /** Whether materialization (KEGG retro + FBA) is being run server-side. */
  materialize: boolean
  /** Called when the user clicks Cancel. */
  onCancel: () => void
}

/**
 * Phase descriptors mapped to elapsed time. The backend doesn't stream
 * progress events for /from-goal yet (single round-trip request), so we
 * approximate with timing. Numbers are upper bounds: most calls finish
 * well before the next phase fires, so the user usually only sees one or
 * two of these labels.
 */
type Phase = {
  /** Inclusive lower bound in seconds. */
  fromSec: number
  /** Short label for the spinner row. */
  label: string
  /** One-line "what's happening" hint below it. */
  detail: string
}

const PHASES_FULL: Phase[] = [
  {
    fromSec: 0,
    label: 'Goal grounding',
    detail: 'Searching KEGG /find/compound + UniProt for candidate target IDs.',
  },
  {
    fromSec: 3,
    label: 'LLM goal parse',
    detail:
      'Gemma is parsing your goal into a structured DesignIntent. First call after a docker restart can be slower while the model warms up.',
  },
  {
    fromSec: 12,
    label: 'KEGG retrosynthetic search',
    detail:
      'BFS over KEGG reactions to find enzymes producing your target, then resolving host genes per EC number.',
  },
  {
    fromSec: 35,
    label: 'Flux balance analysis',
    detail: 'Running cobrapy on the chassis to predict growth + production rate.',
  },
  {
    fromSec: 60,
    label: 'Still working',
    detail:
      'Longer than usual. If this hangs >2 minutes, check `./start.sh logs llm` or `./start.sh logs api` on the server.',
  },
]

const PHASES_LIGHT: Phase[] = [
  PHASES_FULL[0],
  PHASES_FULL[1],
  {
    fromSec: 12,
    label: 'Still working',
    detail:
      'No KEGG/FBA materialization in this run (you turned it off). The LLM is taking longer than usual — first call after a docker restart can be slow.',
  },
]


function pickPhase(elapsedSec: number, phases: Phase[]): { current: Phase; index: number } {
  let index = 0
  for (let i = 0; i < phases.length; i++) {
    if (elapsedSec >= phases[i].fromSec) index = i
  }
  return { current: phases[index], index }
}


export function ProgressIndicator({ materialize, onCancel }: Props) {
  const [elapsedMs, setElapsedMs] = useState(0)
  useEffect(() => {
    const start = performance.now()
    const id = window.setInterval(() => {
      setElapsedMs(performance.now() - start)
    }, 250)
    return () => window.clearInterval(id)
  }, [])

  const elapsedSec = elapsedMs / 1000
  const phases = materialize ? PHASES_FULL : PHASES_LIGHT
  const { current, index } = pickPhase(elapsedSec, phases)

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-2.5 h-2.5 rounded-full bg-bio-green-600 animate-pulse"
            aria-hidden
          />
          <div>
            <div className="font-semibold text-gray-900">{current.label}</div>
            <div className="text-sm text-gray-600 max-w-xl">{current.detail}</div>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span
            className="text-xs font-mono text-gray-600 tabular-nums"
            title="Time elapsed since you clicked Parse goal"
          >
            {elapsedSec.toFixed(1)}s
          </span>
          <button
            type="button"
            onClick={onCancel}
            className="text-xs px-3 py-1.5 bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition"
          >
            Cancel
          </button>
        </div>
      </div>

      <ol className="space-y-1.5 text-sm">
        {phases.map((p, i) => {
          const done = i < index
          const active = i === index
          return (
            <li
              key={p.label}
              className={`flex items-baseline gap-2 ${
                active
                  ? 'text-gray-900'
                  : done
                  ? 'text-gray-500'
                  : 'text-gray-400'
              }`}
            >
              <span
                className={`inline-flex items-center justify-center w-4 text-xs font-bold ${
                  done
                    ? 'text-bio-green-700'
                    : active
                    ? 'text-bio-green-600'
                    : 'text-gray-400'
                }`}
                aria-hidden
              >
                {done ? '✓' : active ? '▶' : '○'}
              </span>
              <span className={active ? 'font-medium' : ''}>{p.label}</span>
              {p.fromSec > 0 && (
                <span className="ml-auto text-xs text-gray-400 tabular-nums">
                  ≥ {p.fromSec}s
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
