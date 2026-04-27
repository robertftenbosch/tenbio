import { DesignIntent } from '../../types/design'

interface Props {
  intent: DesignIntent
  modelUsed: string | null
  candidateKeggCount: number
  candidateUniprotCount: number
}

const CONFIDENCE_BADGES: Record<DesignIntent['confidence'], string> = {
  high: 'bg-green-100 text-green-800 border-green-300',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  low: 'bg-red-100 text-red-800 border-red-300',
}

const TARGET_KIND_LABELS: Record<DesignIntent['target']['kind'], string> = {
  compound: 'Small-molecule target',
  protein: 'Protein target',
  removal: 'Removal / degradation target',
}

export function IntentCard({
  intent,
  modelUsed,
  candidateKeggCount,
  candidateUniprotCount,
}: Props) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
            Parsed goal
          </div>
          <h3 className="text-lg font-semibold text-gray-900">
            {intent.target.name}
          </h3>
          <div className="text-sm text-gray-600 mt-1">
            {TARGET_KIND_LABELS[intent.target.kind]}
            {intent.target.kegg_id && (
              <>
                {' · '}
                <a
                  href={`https://www.kegg.jp/entry/${intent.target.kegg_id.replace(
                    'cpd:',
                    ''
                  )}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-bio-green-700 hover:underline"
                >
                  {intent.target.kegg_id}
                </a>
              </>
            )}
            {intent.target.uniprot_id && (
              <>
                {' · '}
                <a
                  href={`https://www.uniprot.org/uniprotkb/${intent.target.uniprot_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-bio-green-700 hover:underline"
                >
                  {intent.target.uniprot_id}
                </a>
              </>
            )}
          </div>
        </div>
        <span
          className={`px-3 py-1 text-xs font-medium rounded-full border ${
            CONFIDENCE_BADGES[intent.confidence]
          }`}
        >
          confidence: {intent.confidence}
        </span>
      </div>

      <div>
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">
          Candidate hosts
        </div>
        <div className="flex flex-wrap gap-2">
          {intent.host_candidates.map((host) => (
            <span
              key={host}
              className="px-2.5 py-1 text-sm bg-bio-green-50 text-bio-green-800 border border-bio-green-200 rounded"
            >
              {host}
            </span>
          ))}
        </div>
      </div>

      {intent.optimization_metric && (
        <div className="text-sm">
          <span className="text-gray-500">Optimize for:</span>{' '}
          <span className="font-medium text-gray-900">
            {intent.optimization_metric}
          </span>
        </div>
      )}

      {intent.constraints.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
            Constraints
          </div>
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-0.5">
            {intent.constraints.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="pt-2 border-t border-gray-100">
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
          Feasibility note
        </div>
        <p className="text-sm text-gray-700 leading-relaxed">
          {intent.feasibility_note}
        </p>
      </div>

      <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
        <div>
          Grounded with {candidateKeggCount} KEGG + {candidateUniprotCount}{' '}
          UniProt candidates
        </div>
        {modelUsed && <div>via {modelUsed}</div>}
      </div>
    </div>
  )
}
