import { useState, useEffect } from 'react'
import { Part } from '../../types/parts'
import { fetchParts } from '../../api/parts'
import {
  searchKeggPathways,
  searchKeggEnzymes,
  searchUniprotProteins,
  getPopularIgemParts,
  importIgemPart,
  KeggPathway,
  KeggEnzyme,
  UniprotProtein,
  IgemPart,
} from '../../api/external'

type SearchSource = 'local' | 'kegg' | 'uniprot' | 'igem'

interface UnifiedSearchProps {
  onSelectPart?: (part: Part) => void
  onPredictStructure?: (sequence: string, name?: string) => void
}

export function UnifiedSearch({ onSelectPart, onPredictStructure }: UnifiedSearchProps) {
  const [query, setQuery] = useState('')
  const [source, setSource] = useState<SearchSource>('local')
  const [loading, setLoading] = useState(false)

  // Results state
  const [localParts, setLocalParts] = useState<Part[]>([])
  const [keggPathways, setKeggPathways] = useState<KeggPathway[]>([])
  const [keggEnzymes, setKeggEnzymes] = useState<KeggEnzyme[]>([])
  const [uniprotProteins, setUniprotProteins] = useState<UniprotProtein[]>([])
  const [igemParts, setIgemParts] = useState<IgemPart[]>([])

  const [importingPart, setImportingPart] = useState<string | null>(null)
  const [importMessage, setImportMessage] = useState<{ text: string; success: boolean } | null>(null)

  // Debounced search
  useEffect(() => {
    if (!query.trim() && source !== 'igem') {
      clearResults()
      return
    }

    const timeoutId = setTimeout(() => {
      performSearch()
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [query, source])

  // Load iGEM popular parts when switching to iGEM tab
  useEffect(() => {
    if (source === 'igem' && igemParts.length === 0) {
      loadIgemParts()
    }
  }, [source])

  const clearResults = () => {
    setLocalParts([])
    setKeggPathways([])
    setKeggEnzymes([])
    setUniprotProteins([])
  }

  const performSearch = async () => {
    if (!query.trim() && source !== 'igem') return

    setLoading(true)
    try {
      switch (source) {
        case 'local':
          const response = await fetchParts({ search: query, limit: 20 })
          setLocalParts(response.parts)
          break
        case 'kegg':
          const [pathways, enzymes] = await Promise.all([
            searchKeggPathways(query),
            searchKeggEnzymes(query),
          ])
          setKeggPathways(pathways)
          setKeggEnzymes(enzymes)
          break
        case 'uniprot':
          const proteins = await searchUniprotProteins(query)
          setUniprotProteins(proteins)
          break
        case 'igem':
          await loadIgemParts()
          break
      }
    } catch (error) {
      console.error('Search error:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadIgemParts = async () => {
    setLoading(true)
    try {
      const parts = await getPopularIgemParts()
      setIgemParts(parts)
    } catch (error) {
      console.error('Error loading iGEM parts:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleImportIgem = async (partName: string) => {
    setImportingPart(partName)
    setImportMessage(null)
    try {
      const result = await importIgemPart(partName)
      setImportMessage({ text: result.message, success: result.success })
    } catch (error) {
      setImportMessage({ text: 'Import failed', success: false })
    } finally {
      setImportingPart(null)
    }
  }

  const sources: { id: SearchSource; label: string; icon: string }[] = [
    { id: 'local', label: 'Local Parts', icon: '📦' },
    { id: 'kegg', label: 'KEGG', icon: '🧬' },
    { id: 'uniprot', label: 'UniProt', icon: '🔬' },
    { id: 'igem', label: 'iGEM', icon: '🧪' },
  ]

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      {/* Search Header */}
      <div className="p-4 border-b">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Source Tabs */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {sources.map((s) => (
              <button
                key={s.id}
                onClick={() => setSource(s.id)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  source === s.id
                    ? 'bg-white text-bio-green-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <span className="mr-1">{s.icon}</span>
                {s.label}
              </button>
            ))}
          </div>

          {/* Search Input */}
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder={
                source === 'igem'
                  ? 'Browse popular iGEM parts...'
                  : source === 'kegg'
                  ? 'Search pathways or enzymes (e.g., glycolysis, kinase)...'
                  : source === 'uniprot'
                  ? 'Search proteins (e.g., GFP, polymerase)...'
                  : 'Search local parts...'
              }
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
            />
            <svg
              className="absolute left-3 top-2.5 h-5 w-5 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="p-4 max-h-96 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-bio-green-600"></div>
            <span className="ml-2 text-gray-600">Searching...</span>
          </div>
        ) : (
          <>
            {/* Import Message */}
            {importMessage && (
              <div
                className={`mb-4 p-3 rounded-lg text-sm ${
                  importMessage.success
                    ? 'bg-green-50 text-green-700 border border-green-200'
                    : 'bg-red-50 text-red-700 border border-red-200'
                }`}
              >
                {importMessage.text}
              </div>
            )}

            {/* Local Parts Results */}
            {source === 'local' && (
              <div className="space-y-2">
                {localParts.length === 0 && query && (
                  <p className="text-gray-500 text-center py-4">No parts found</p>
                )}
                {localParts.map((part) => (
                  <LocalPartCard key={part.id} part={part} onClick={() => onSelectPart?.(part)} />
                ))}
              </div>
            )}

            {/* KEGG Results */}
            {source === 'kegg' && (
              <div className="space-y-4">
                {keggPathways.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">Pathways</h3>
                    <div className="space-y-2">
                      {keggPathways.map((pathway) => (
                        <KeggPathwayCard key={pathway.id} pathway={pathway} />
                      ))}
                    </div>
                  </div>
                )}
                {keggEnzymes.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">Enzymes</h3>
                    <div className="space-y-2">
                      {keggEnzymes.map((enzyme) => (
                        <KeggEnzymeCard key={enzyme.ec_number} enzyme={enzyme} />
                      ))}
                    </div>
                  </div>
                )}
                {keggPathways.length === 0 && keggEnzymes.length === 0 && query && (
                  <p className="text-gray-500 text-center py-4">No results found</p>
                )}
              </div>
            )}

            {/* UniProt Results */}
            {source === 'uniprot' && (
              <div className="space-y-2">
                {uniprotProteins.length === 0 && query && (
                  <p className="text-gray-500 text-center py-4">No proteins found</p>
                )}
                {uniprotProteins.map((protein) => (
                  <UniprotProteinCard
                    key={protein.accession}
                    protein={protein}
                    onPredictStructure={onPredictStructure}
                  />
                ))}
              </div>
            )}

            {/* iGEM Results */}
            {source === 'igem' && (
              <div className="space-y-2">
                <p className="text-sm text-gray-500 mb-3">
                  Popular BioBrick parts from iGEM Registry. Click "Import" to add to your local library.
                </p>
                {igemParts.map((part) => (
                  <IgemPartCard
                    key={part.name}
                    part={part}
                    onImport={() => handleImportIgem(part.name)}
                    importing={importingPart === part.name}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// Card Components
function LocalPartCard({ part, onClick }: { part: Part; onClick?: () => void }) {
  const typeColors: Record<string, string> = {
    promoter: 'bg-blue-100 text-blue-700',
    rbs: 'bg-purple-100 text-purple-700',
    terminator: 'bg-red-100 text-red-700',
    gene: 'bg-green-100 text-green-700',
  }

  return (
    <div
      onClick={onClick}
      className="p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
    >
      <div className="flex items-center justify-between">
        <span className="font-mono font-medium text-gray-900">{part.name}</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[part.type] || 'bg-gray-100'}`}>
          {part.type}
        </span>
      </div>
      {part.description && (
        <p className="text-sm text-gray-600 mt-1 line-clamp-1">{part.description}</p>
      )}
    </div>
  )
}

function KeggPathwayCard({ pathway }: { pathway: KeggPathway }) {
  return (
    <a
      href={pathway.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block p-3 border rounded-lg hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center justify-between">
        <span className="font-medium text-gray-900">{pathway.name}</span>
        <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
          {pathway.id}
        </span>
      </div>
      <p className="text-xs text-gray-500 mt-1">Click to view on KEGG</p>
    </a>
  )
}

function KeggEnzymeCard({ enzyme }: { enzyme: KeggEnzyme }) {
  return (
    <a
      href={enzyme.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block p-3 border rounded-lg hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center justify-between">
        <span className="text-gray-900">{enzyme.name}</span>
        <span className="px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-700">
          EC {enzyme.ec_number}
        </span>
      </div>
      {enzyme.reaction && (
        <p className="text-sm text-gray-600 mt-1 line-clamp-1">{enzyme.reaction}</p>
      )}
    </a>
  )
}

function UniprotProteinCard({
  protein,
  onPredictStructure,
}: {
  protein: UniprotProtein
  onPredictStructure?: (sequence: string, name?: string) => void
}) {
  return (
    <div className="p-3 border rounded-lg hover:bg-gray-50 transition-colors">
      <div className="flex items-center justify-between">
        <a
          href={protein.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1"
        >
          <div className="flex items-center justify-between">
            <div>
              <span className="font-medium text-gray-900">{protein.protein_name || protein.entry_name}</span>
              {protein.gene_names.length > 0 && (
                <span className="ml-2 text-sm text-gray-500">({protein.gene_names[0]})</span>
              )}
            </div>
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700">
              {protein.accession}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
            {protein.organism && <span>{protein.organism}</span>}
            {protein.length && <span>{protein.length} aa</span>}
          </div>
        </a>
        {onPredictStructure && protein.sequence && (
          <button
            onClick={() =>
              onPredictStructure(
                protein.sequence!,
                protein.protein_name || protein.entry_name || protein.accession
              )
            }
            className="ml-2 px-2 py-1 text-xs font-medium text-bio-green-700 bg-bio-green-50 rounded hover:bg-bio-green-100 transition-colors whitespace-nowrap"
          >
            Predict Structure
          </button>
        )}
      </div>
    </div>
  )
}

function IgemPartCard({
  part,
  onImport,
  importing,
}: {
  part: IgemPart
  onImport: () => void
  importing: boolean
}) {
  const typeColors: Record<string, string> = {
    promoter: 'bg-blue-100 text-blue-700',
    rbs: 'bg-purple-100 text-purple-700',
    terminator: 'bg-red-100 text-red-700',
    gene: 'bg-green-100 text-green-700',
  }

  return (
    <div className="p-3 border rounded-lg hover:bg-gray-50 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono font-medium text-gray-900">{part.name}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[part.type] || 'bg-gray-100'}`}>
            {part.type}
          </span>
        </div>
        <button
          onClick={onImport}
          disabled={importing}
          className="px-3 py-1 text-xs font-medium text-bio-green-700 bg-bio-green-50 rounded hover:bg-bio-green-100 disabled:opacity-50 transition-colors"
        >
          {importing ? 'Importing...' : 'Import'}
        </button>
      </div>
      {part.description && (
        <p className="text-sm text-gray-600 mt-1 line-clamp-1">{part.description}</p>
      )}
      <p className="text-xs text-gray-400 mt-1">{part.sequence.length} bp</p>
    </div>
  )
}
