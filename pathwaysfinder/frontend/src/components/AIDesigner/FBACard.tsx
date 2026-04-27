import { FBASummary } from '../../types/design'

interface Props {
  fba: FBASummary
}

const STATUS_COLORS: Record<string, string> = {
  optimal: 'bg-green-100 text-green-800 border-green-300',
  infeasible: 'bg-red-100 text-red-800 border-red-300',
  unbounded: 'bg-amber-100 text-amber-800 border-amber-300',
}

function formatFlux(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  if (Math.abs(value) < 0.01) return value.toExponential(2)
  return value.toFixed(3)
}

export function FBACard({ fba }: Props) {
  const isProductionTarget = fba.target_reaction !== null
  const statusBadge = STATUS_COLORS[fba.status] ?? 'bg-gray-100 text-gray-800 border-gray-300'

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
            Predicted production (FBA)
          </div>
          <h3 className="text-lg font-semibold text-gray-900">
            {isProductionTarget
              ? 'Maximum production at steady state'
              : 'Chassis viability check'}
          </h3>
          <div className="text-sm text-gray-600 mt-1">
            chassis:{' '}
            <span className="font-mono text-gray-900">{fba.chassis}</span>
            {' · '}objective:{' '}
            <span className="font-mono text-gray-900">{fba.objective_id}</span>
          </div>
        </div>
        <span
          className={`px-3 py-1 text-xs font-medium rounded-full border ${statusBadge}`}
        >
          {fba.status}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="border border-gray-200 rounded p-3">
          <div className="text-xs text-gray-500 mb-0.5">Growth rate</div>
          <div className="text-2xl font-semibold text-gray-900 tabular-nums">
            {formatFlux(fba.growth_rate)}
          </div>
          <div className="text-xs text-gray-500">/ hour (biomass flux)</div>
        </div>

        {isProductionTarget && (
          <div className="border border-bio-green-200 rounded p-3 bg-bio-green-50">
            <div className="text-xs text-bio-green-700 mb-0.5">
              Target flux ({fba.target_reaction})
            </div>
            <div className="text-2xl font-semibold text-bio-green-900 tabular-nums">
              {formatFlux(fba.target_flux)}
            </div>
            <div className="text-xs text-bio-green-700">
              mmol / gDW / h (max while staying viable)
            </div>
          </div>
        )}
      </div>

      {!isProductionTarget && (
        <p className="text-sm text-gray-600 leading-relaxed">
          The target compound doesn't map cleanly to an exchange reaction
          in this chassis's genome-scale model. Showing the unmodified
          chassis growth rate as a viability baseline. Future work
          (Phase 2 follow-up): overlay the candidate pathway's enzymes
          onto the chassis model so this becomes a real production
          prediction.
        </p>
      )}

      {fba.notes.length > 0 && (
        <div className="border-t border-gray-100 pt-3">
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
            Solver notes
          </div>
          <ul className="text-xs text-gray-700 list-disc list-inside space-y-0.5">
            {fba.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
