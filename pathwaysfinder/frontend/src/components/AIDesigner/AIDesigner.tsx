import { useState } from 'react'
import { designFromGoal } from '../../api/design'
import { DesignFromGoalResponse } from '../../types/design'
import { Part } from '../../types/parts'
import { ChatPanel } from './ChatPanel'
import { IntentCard } from './IntentCard'
import { PathwayResult } from './PathwayResult'

interface Props {
  /**
   * Called when the user clicks "Use this design". Receives synthetic
   * Parts to hand off to the Pathway Designer canvas.
   */
  onUseDesign: (parts: Part[]) => void
}

const EXAMPLE_QUERIES = [
  'Maak een organisme dat uit mest de ammoniak haalt en omzet naar N2',
  'Maak via fotosynthese componenten voor kerosine',
  'Maak de eiwitten om kaas te produceren',
  'Maak een organisme dat PFAS in water afbreekt',
  'Maak bacteriën die bloedplasma componenten produceren voor 0-negatief',
]

const HOST_OPTIONS: { code: string; label: string }[] = [
  { code: 'eco', label: 'E. coli (eco)' },
  { code: 'sce', label: 'S. cerevisiae (sce)' },
  { code: 'bsu', label: 'B. subtilis (bsu)' },
  { code: 'syn', label: 'Synechocystis sp. PCC 6803 (syn)' },
  { code: 'ppa', label: 'P. pastoris (ppa)' },
]

export function AIDesigner({ onUseDesign }: Props) {
  const [query, setQuery] = useState('')
  const [host, setHost] = useState('eco')
  const [maxDepth, setMaxDepth] = useState(2)
  const [materialize, setMaterialize] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<DesignFromGoalResponse | null>(null)

  const submit = async (overrideQuery?: string) => {
    const text = (overrideQuery ?? query).trim()
    if (text.length < 3) {
      setError('Geef een doel in (minimaal 3 tekens).')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const response = await designFromGoal({
        query: text,
        host,
        max_depth: maxDepth,
        materialize,
      })
      setResult(response)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Onbekende fout.')
    } finally {
      setLoading(false)
    }
  }

  const handleExample = (example: string) => {
    setQuery(example)
    submit(example)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900 mb-2">
          AI Designer
        </h2>
        <p className="text-gray-600 max-w-3xl">
          Beschrijf in vrije tekst wat je wil bouwen. Een lokale Gemma
          parset je doel naar een gestructureerde DesignIntent, en KEGG
          stelt een kandidaat-pathway voor in de gekozen host. Klik
          daarna op <em>Use this design</em> om de geselecteerde genen
          naar de Pathway Designer te sturen.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 space-y-4">
        <div>
          <label
            htmlFor="goal-query"
            className="block text-sm font-medium text-gray-700 mb-1.5"
          >
            Wat wil je bouwen?
          </label>
          <textarea
            id="goal-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            placeholder="Bijv. 'Maak een organisme dat uit mest de ammoniak haalt en omzet naar N2'"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label
              htmlFor="goal-host"
              className="block text-sm font-medium text-gray-700 mb-1.5"
            >
              Host (KEGG-code)
            </label>
            <select
              id="goal-host"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm"
            >
              {HOST_OPTIONS.map((h) => (
                <option key={h.code} value={h.code}>
                  {h.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              Default; kan overschreven worden door de LLM-suggestie.
            </p>
          </div>
          <div>
            <label
              htmlFor="goal-depth"
              className="block text-sm font-medium text-gray-700 mb-1.5"
            >
              BFS-diepte
            </label>
            <select
              id="goal-depth"
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm"
            >
              {[0, 1, 2, 3, 4].map((d) => (
                <option key={d} value={d}>
                  {d} (
                  {d === 0
                    ? 'directe producenten'
                    : d === 1
                    ? '1 stap terug'
                    : `${d} stappen terug`}
                  )
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-gray-700 select-none">
              <input
                type="checkbox"
                checked={materialize}
                onChange={(e) => setMaterialize(e.target.checked)}
                className="w-4 h-4"
              />
              KEGG-pathway erbij ophalen
            </label>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => submit()}
            disabled={loading || query.trim().length < 3}
            className="px-5 py-2 bg-bio-green-700 text-white rounded-lg font-medium hover:bg-bio-green-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
          >
            {loading ? 'Bezig…' : 'Parse goal'}
          </button>
          {error && (
            <span className="text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-1 rounded">
              {error}
            </span>
          )}
        </div>

        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">
            Voorbeelden
          </div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => handleExample(ex)}
                disabled={loading}
                className="text-xs px-2.5 py-1.5 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded transition text-left max-w-md truncate disabled:opacity-50"
                title={ex}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 text-center text-gray-600">
          <div className="inline-block animate-pulse">
            Gemma is je doel aan het parsen, KEGG zoekt reacties…
          </div>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <IntentCard
            intent={result.intent}
            modelUsed={result.model_used}
            candidateKeggCount={result.candidate_kegg_count}
            candidateUniprotCount={result.candidate_uniprot_count}
          />
          {result.pathway_candidates ? (
            <PathwayResult
              result={result.pathway_candidates}
              onUseDesign={onUseDesign}
            />
          ) : result.intent.target.kegg_id ? (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-900">
              Een KEGG-zoekopdracht ging niet door (mogelijk timeout).
              Probeer opnieuw of zet <em>KEGG-pathway erbij ophalen</em>{' '}
              uit voor alleen de intent.
            </div>
          ) : (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900">
              De LLM kon geen KEGG-compound vastleggen voor dit doel.
              Dit gebeurt bij eiwit-targets zonder KEGG-mapping (bv.
              caseïne, antilichamen) of zeer brede vragen. De
              feasibility-note hierboven bevat meestal een aanwijzing
              voor de juiste chassis.
            </div>
          )}
        </div>
      )}

      <ChatPanel intent={result?.intent ?? null} />
    </div>
  )
}
