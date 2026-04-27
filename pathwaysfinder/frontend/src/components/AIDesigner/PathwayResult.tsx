import { useState, useMemo } from 'react'
import { GeneRef, PathwayCandidatesResponse, ReactionStep } from '../../types/design'
import { Part } from '../../types/parts'

interface Props {
  result: PathwayCandidatesResponse
  /**
   * Called when the user picks a route. Receives synthetic Parts (one per
   * candidate gene from the selected reactions) that the parent can hand
   * off to the Pathway Designer canvas as importedParts.
   */
  onUseDesign: (parts: Part[]) => void
}

const DEPTH_COLORS: Record<number, string> = {
  0: 'border-bio-green-400 bg-bio-green-50',
  1: 'border-blue-400 bg-blue-50',
  2: 'border-purple-400 bg-purple-50',
  3: 'border-amber-400 bg-amber-50',
  4: 'border-pink-400 bg-pink-50',
}


function geneToPart(gene: GeneRef, host: string): Part {
  // Synthetic Part record. The Pathway Designer accepts importedParts
  // that match the Part shape; the sequence stays empty until the user
  // patches it via PUT /api/v1/parts/{id} or fetches from KEGG.
  const now = new Date().toISOString()
  return {
    id: `kegg-${gene.id}`,
    name: gene.name || gene.id,
    type: 'gene',
    description:
      [gene.definition, gene.ec_number ? `EC ${gene.ec_number}` : null]
        .filter(Boolean)
        .join(' — ') || null,
    sequence: '',
    organism: gene.organism || host,
    source: 'kegg',
    created_at: now,
    updated_at: null,
  }
}


function ReactionRow({
  step,
  selected,
  onToggle,
}: {
  step: ReactionStep
  selected: boolean
  onToggle: () => void
}) {
  const depthClass = DEPTH_COLORS[step.depth] ?? DEPTH_COLORS[0]
  const hasGenes = step.candidate_genes.length > 0
  return (
    <div
      className={`border rounded-lg p-4 transition ${depthClass} ${
        selected ? 'ring-2 ring-bio-green-500' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-gray-500">
              depth {step.depth}
            </span>
            <a
              href={`https://www.kegg.jp/entry/${step.reaction_id.replace(
                'rn:',
                ''
              )}`}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-mono text-bio-green-700 hover:underline"
            >
              {step.reaction_id}
            </a>
            {step.reaction_name && (
              <span className="text-sm text-gray-700 truncate">
                {step.reaction_name}
              </span>
            )}
          </div>
          {step.equation && (
            <div className="text-xs text-gray-600 font-mono mb-2 break-all">
              {step.equation}
            </div>
          )}
          <div className="flex flex-wrap gap-1.5 mb-2">
            {step.ec_numbers.map((ec) => (
              <span
                key={ec}
                className="px-1.5 py-0.5 text-xs bg-white border border-gray-300 rounded text-gray-700"
              >
                EC {ec}
              </span>
            ))}
          </div>
          {hasGenes ? (
            <div className="space-y-1">
              {step.candidate_genes.map((gene) => (
                <div
                  key={gene.id}
                  className="text-xs flex items-baseline gap-2"
                >
                  <span className="font-mono text-bio-green-700">
                    {gene.id}
                  </span>
                  <span className="font-medium text-gray-900">
                    {gene.name}
                  </span>
                  {gene.definition && (
                    <span className="text-gray-600 truncate">
                      {gene.definition}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-gray-500 italic">
              No host gene annotated for these EC numbers — would need to
              transplant from a different organism.
            </div>
          )}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-gray-700 shrink-0 cursor-pointer">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            disabled={!hasGenes}
            className="w-4 h-4"
          />
          select
        </label>
      </div>
    </div>
  )
}


export function PathwayResult({ result, onUseDesign }: Props) {
  const [selected, setSelected] = useState<Set<string>>(() => {
    // Default: pre-select all depth=0 reactions that have at least one gene.
    return new Set(
      result.reactions
        .filter((r) => r.depth === 0 && r.candidate_genes.length > 0)
        .map((r) => r.reaction_id)
    )
  })

  const toggle = (reactionId: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(reactionId)) next.delete(reactionId)
      else next.add(reactionId)
      return next
    })
  }

  const groupedByDepth = useMemo(() => {
    const groups: Record<number, ReactionStep[]> = {}
    for (const r of result.reactions) {
      ;(groups[r.depth] ??= []).push(r)
    }
    return groups
  }, [result.reactions])

  const selectedGenes: { gene: GeneRef; host: string }[] = useMemo(() => {
    const genes: { gene: GeneRef; host: string }[] = []
    const seen = new Set<string>()
    for (const r of result.reactions) {
      if (!selected.has(r.reaction_id)) continue
      for (const g of r.candidate_genes) {
        if (seen.has(g.id)) continue
        seen.add(g.id)
        genes.push({ gene: g, host: result.host })
      }
    }
    return genes
  }, [result, selected])

  const handleUseDesign = () => {
    const parts = selectedGenes.map(({ gene, host }) => geneToPart(gene, host))
    onUseDesign(parts)
  }

  if (result.reactions.length === 0) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="text-amber-800 font-medium mb-1">
          No KEGG reactions found within the search bounds.
        </div>
        {result.notes.length > 0 && (
          <ul className="text-sm text-amber-900 list-disc list-inside space-y-1 mt-2">
            {result.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
            Candidate pathway
          </div>
          <h3 className="text-lg font-semibold text-gray-900">
            Producing {result.target.name || result.target.id} in {result.host}
          </h3>
          <div className="text-sm text-gray-600">
            {result.reactions.length} reaction
            {result.reactions.length === 1 ? '' : 's'} · BFS depth{' '}
            {result.max_depth_used}
          </div>
        </div>
        <button
          type="button"
          onClick={handleUseDesign}
          disabled={selectedGenes.length === 0}
          className="px-4 py-2 bg-bio-green-700 text-white rounded-lg font-medium hover:bg-bio-green-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
        >
          Use this design ({selectedGenes.length}{' '}
          gene{selectedGenes.length === 1 ? '' : 's'})
        </button>
      </div>

      {result.notes.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-900">
          <div className="font-medium mb-1">Search notes</div>
          <ul className="list-disc list-inside space-y-0.5">
            {result.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}

      {Object.entries(groupedByDepth)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([depth, steps]) => (
          <div key={depth}>
            <div className="text-xs font-medium text-gray-600 mb-2">
              Depth {depth}{' '}
              {Number(depth) === 0 ? '— direct producers of target' : ''}
            </div>
            <div className="space-y-2">
              {steps.map((step) => (
                <ReactionRow
                  key={step.reaction_id}
                  step={step}
                  selected={selected.has(step.reaction_id)}
                  onToggle={() => toggle(step.reaction_id)}
                />
              ))}
            </div>
          </div>
        ))}
    </div>
  )
}
