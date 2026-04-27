import { useEffect, useMemo, useRef, useState } from 'react'
import { listChassis, runFBA } from '../../api/fba'
import { ChassisInfo, FBAResponse } from '../../types/fba'

interface Props {
  /**
   * Optional list of reaction IDs from the user's current Pathway. When
   * provided, the panel offers them as quick "knock out this part" toggles
   * — same channel a future pathway-overlay will use.
   */
  pathwayReactionIds?: string[]
}

const STATUS_COLORS: Record<string, string> = {
  optimal: 'bg-green-100 text-green-800 border-green-300',
  infeasible: 'bg-red-100 text-red-800 border-red-300',
  unbounded: 'bg-amber-100 text-amber-800 border-amber-300',
}

function formatFlux(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  if (Math.abs(value) < 0.0001) return value.toExponential(2)
  return value.toFixed(3)
}

const COMMON_TARGETS: { id: string; label: string }[] = [
  { id: 'EX_etoh_e', label: 'EX_etoh_e — ethanol' },
  { id: 'EX_succ_e', label: 'EX_succ_e — succinate' },
  { id: 'EX_ac_e', label: 'EX_ac_e — acetate' },
  { id: 'EX_lac__D_e', label: 'EX_lac__D_e — D-lactate' },
  { id: 'EX_pyr_e', label: 'EX_pyr_e — pyruvate' },
  { id: 'EX_for_e', label: 'EX_for_e — formate' },
  { id: 'EX_nh4_e', label: 'EX_nh4_e — ammonium' },
]


export function SimulationPanel({ pathwayReactionIds = [] }: Props) {
  // --- chassis registry ---------------------------------------------------
  const [chassisList, setChassisList] = useState<ChassisInfo[]>([])
  const [chassis, setChassis] = useState<string>('textbook')
  const [chassisError, setChassisError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listChassis()
      .then((rows) => {
        if (cancelled) return
        setChassisList(rows)
        if (rows.length > 0 && !rows.find((r) => r.key === chassis)) {
          setChassis(rows[0].key)
        }
      })
      .catch((e) => {
        if (!cancelled) setChassisError(e.message)
      })
    return () => {
      cancelled = true
    }
    // We deliberately don't depend on `chassis` here -- the registry only
    // needs to be fetched once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // --- simulation parameters ---------------------------------------------
  const [objective, setObjective] = useState<'biomass' | 'target'>('biomass')
  const [targetReaction, setTargetReaction] = useState('')
  const [knockoutsText, setKnockoutsText] = useState('')
  const [carbonSource, setCarbonSource] = useState('')
  const [carbonUptake, setCarbonUptake] = useState(-10)

  const knockouts = useMemo(
    () =>
      knockoutsText
        .split(/[,\s]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    [knockoutsText]
  )

  const togglePathwayKnockout = (rid: string) => {
    if (knockouts.includes(rid)) {
      setKnockoutsText(knockouts.filter((k) => k !== rid).join(', '))
    } else {
      setKnockoutsText([...knockouts, rid].join(', '))
    }
  }

  // --- run state ----------------------------------------------------------
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<FBAResponse | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const run = async () => {
    if (objective === 'target' && !targetReaction.trim()) {
      setRunError("Vul een target_reaction in (bv. 'EX_etoh_e') of zet objective op 'biomass'.")
      return
    }
    setRunning(true)
    setRunError(null)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const resp = await runFBA(
        {
          chassis,
          objective,
          target_reaction: objective === 'target' ? targetReaction.trim() : null,
          knockouts,
          carbon_source: carbonSource.trim() || null,
          carbon_uptake: carbonUptake,
          flux_limit: 30,
        },
        controller.signal
      )
      setResult(resp)
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setRunError(e instanceof Error ? e.message : 'FBA call failed')
    } finally {
      setRunning(false)
      abortRef.current = null
    }
  }

  const cancel = () => abortRef.current?.abort()

  // --- render -------------------------------------------------------------
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">
          Simulate (Flux Balance Analysis)
        </h3>
        <p className="text-sm text-gray-600 max-w-2xl mt-1">
          Run cobrapy on a genome-scale chassis model. Either maximise
          biomass (chassis viability check) or maximise a specific
          exchange reaction (predicted production rate). Knockouts and
          carbon-source overrides are applied per-call; nothing is
          persisted.
        </p>
      </div>

      {chassisError && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded">
          Could not load chassis registry: {chassisError}
        </div>
      )}

      {/* Parameters --------------------------------------------------- */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Chassis
          </label>
          <select
            value={chassis}
            onChange={(e) => setChassis(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm"
          >
            {chassisList.length === 0 ? (
              <option value="textbook">textbook (loading…)</option>
            ) : (
              chassisList.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.key} — {c.organism} ({c.n_reactions} rxns)
                </option>
              ))
            )}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Objective
          </label>
          <div className="flex gap-4 text-sm pt-1.5">
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="objective"
                value="biomass"
                checked={objective === 'biomass'}
                onChange={() => setObjective('biomass')}
              />
              biomass
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="objective"
                value="target"
                checked={objective === 'target'}
                onChange={() => setObjective('target')}
              />
              target reaction
            </label>
          </div>
        </div>

        {objective === 'target' && (
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Target reaction id
            </label>
            <input
              type="text"
              value={targetReaction}
              onChange={(e) => setTargetReaction(e.target.value)}
              placeholder="e.g. EX_etoh_e"
              list="common-targets"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm font-mono"
            />
            <datalist id="common-targets">
              {COMMON_TARGETS.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </datalist>
            <p className="mt-1 text-xs text-gray-500">
              Common: {COMMON_TARGETS.map((t) => t.id).join(', ')}.
            </p>
          </div>
        )}

        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Knockouts (reaction IDs, comma-separated)
          </label>
          <textarea
            value={knockoutsText}
            onChange={(e) => setKnockoutsText(e.target.value)}
            rows={2}
            placeholder="PFK, PGI, FBA"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm font-mono"
          />
          {pathwayReactionIds.length > 0 && (
            <div className="mt-2">
              <div className="text-xs text-gray-500 mb-1">
                Quick toggle from current pathway:
              </div>
              <div className="flex flex-wrap gap-1.5">
                {pathwayReactionIds.map((rid) => (
                  <button
                    key={rid}
                    type="button"
                    onClick={() => togglePathwayKnockout(rid)}
                    className={`text-xs font-mono px-2 py-1 rounded border transition ${
                      knockouts.includes(rid)
                        ? 'bg-red-50 border-red-300 text-red-800'
                        : 'bg-gray-50 border-gray-300 text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    {knockouts.includes(rid) ? '✕ ' : '+ '}
                    {rid}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Carbon source (exchange id)
          </label>
          <input
            type="text"
            value={carbonSource}
            onChange={(e) => setCarbonSource(e.target.value)}
            placeholder="leave empty for chassis default"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm font-mono"
          />
          <p className="mt-1 text-xs text-gray-500">
            e.g. EX_glc__D_e (glucose), EX_ac_e (acetate). Other
            carbon-source exchanges get closed when this is set.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Carbon uptake (lower bound)
          </label>
          <input
            type="number"
            step="0.5"
            value={carbonUptake}
            onChange={(e) => setCarbonUptake(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm tabular-nums"
          />
          <p className="mt-1 text-xs text-gray-500">
            Negative = uptake (cobra convention). -10 mmol/gDW/h is the
            textbook default for glucose.
          </p>
        </div>
      </div>

      {/* Run + cancel ------------------------------------------------- */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={running}
          className="px-5 py-2 bg-bio-green-700 text-white rounded-lg font-medium hover:bg-bio-green-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
        >
          {running ? 'Running FBA…' : 'Run simulation'}
        </button>
        {running && (
          <button
            type="button"
            onClick={cancel}
            className="px-3 py-1.5 text-sm bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition"
          >
            Cancel
          </button>
        )}
        {runError && (
          <span className="text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-1 rounded">
            {runError}
          </span>
        )}
      </div>

      {/* Result ------------------------------------------------------- */}
      {result && (
        <div className="space-y-4 pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-0.5">
                Result
              </div>
              <div className="text-sm text-gray-700">
                Chassis:{' '}
                <span className="font-mono text-gray-900">{result.chassis}</span>
                {' · '}objective:{' '}
                <span className="font-mono text-gray-900">{result.objective_id}</span>
              </div>
            </div>
            <span
              className={`px-3 py-1 text-xs font-medium rounded-full border ${
                STATUS_COLORS[result.status] ??
                'bg-gray-100 text-gray-800 border-gray-300'
              }`}
            >
              {result.status}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="border border-gray-200 rounded p-3">
              <div className="text-xs text-gray-500">Growth rate</div>
              <div className="text-2xl font-semibold tabular-nums text-gray-900">
                {formatFlux(result.growth_rate)}
              </div>
              <div className="text-xs text-gray-500">/ hour (biomass flux)</div>
            </div>
            {result.target_reaction && (
              <div className="border border-bio-green-200 rounded p-3 bg-bio-green-50">
                <div className="text-xs text-bio-green-700">
                  Target flux ({result.target_reaction})
                </div>
                <div className="text-2xl font-semibold tabular-nums text-bio-green-900">
                  {formatFlux(result.target_flux)}
                </div>
                <div className="text-xs text-bio-green-700">
                  mmol / gDW / h
                </div>
              </div>
            )}
          </div>

          {result.notes.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-900">
              <div className="font-medium mb-1">Solver notes</div>
              <ul className="list-disc list-inside space-y-0.5">
                {result.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}

          {result.fluxes.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-1.5">
                Top fluxes (by |flux|)
              </div>
              <div className="border border-gray-200 rounded overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-600">
                    <tr>
                      <th className="text-left font-medium px-3 py-1.5">Reaction</th>
                      <th className="text-left font-medium px-3 py-1.5">Name</th>
                      <th className="text-right font-medium px-3 py-1.5">Flux</th>
                      <th className="text-right font-medium px-3 py-1.5">Bounds</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.fluxes.map((f) => (
                      <tr
                        key={f.reaction_id}
                        className="border-t border-gray-100"
                      >
                        <td className="px-3 py-1.5 font-mono text-bio-green-700">
                          {f.reaction_id}
                        </td>
                        <td className="px-3 py-1.5 text-gray-700 truncate max-w-xs">
                          {f.name || '—'}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono tabular-nums">
                          {formatFlux(f.flux)}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono tabular-nums text-gray-500 text-xs">
                          [{formatFlux(f.lower_bound)}, {formatFlux(f.upper_bound)}]
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
