import { useState } from 'react'
import { Part } from '../../types/parts'
import {
  searchKeggPathways,
  searchKeggEnzymes,
  getKeggPathwayGenes,
  getKeggEnzymeGenes,
  getKeggGeneSequence,
  KeggPathway,
  KeggEnzyme,
  KeggGene,
} from '../../api/external'
import { createPart } from '../../api/parts'

interface KeggImportModalProps {
  onClose: () => void
  onImport: (parts: Part[]) => void
}

type SearchMode = 'pathway' | 'enzyme'

export function KeggImportModal({ onClose, onImport }: KeggImportModalProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [organism, setOrganism] = useState('ecoli')
  const [searchMode, setSearchMode] = useState<SearchMode>('enzyme')
  const [pathways, setPathways] = useState<KeggPathway[]>([])
  const [enzymes, setEnzymes] = useState<KeggEnzyme[]>([])
  const [selectedPathway, setSelectedPathway] = useState<KeggPathway | null>(null)
  const [selectedEnzyme, setSelectedEnzyme] = useState<KeggEnzyme | null>(null)
  const [genes, setGenes] = useState<KeggGene[]>([])
  const [selectedGenes, setSelectedGenes] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [loadingGenes, setLoadingGenes] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importProgress, setImportProgress] = useState({ current: 0, total: 0 })

  // Search pathways or enzymes
  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setLoading(true)
    setSelectedPathway(null)
    setSelectedEnzyme(null)
    setGenes([])
    try {
      if (searchMode === 'pathway') {
        const results = await searchKeggPathways(searchQuery, organism)
        setPathways(results)
        setEnzymes([])
      } else {
        const results = await searchKeggEnzymes(searchQuery)
        setEnzymes(results)
        setPathways([])
      }
    } catch (error) {
      console.error('Search error:', error)
    } finally {
      setLoading(false)
    }
  }

  // Load genes for selected pathway
  const handleSelectPathway = async (pathway: KeggPathway) => {
    setSelectedPathway(pathway)
    setSelectedEnzyme(null)
    setLoadingGenes(true)
    setSelectedGenes(new Set())
    try {
      const pathwayGenes = await getKeggPathwayGenes(pathway.id)
      setGenes(pathwayGenes)
    } catch (error) {
      console.error('Error loading genes:', error)
    } finally {
      setLoadingGenes(false)
    }
  }

  // Load genes for selected enzyme
  const handleSelectEnzyme = async (enzyme: KeggEnzyme) => {
    setSelectedEnzyme(enzyme)
    setSelectedPathway(null)
    setLoadingGenes(true)
    setSelectedGenes(new Set())
    try {
      const enzymeGenes = await getKeggEnzymeGenes(enzyme.ec_number, organism)
      setGenes(enzymeGenes)
    } catch (error) {
      console.error('Error loading genes:', error)
    } finally {
      setLoadingGenes(false)
    }
  }

  // Toggle gene selection
  const toggleGeneSelection = (geneId: string) => {
    setSelectedGenes(prev => {
      const newSet = new Set(prev)
      if (newSet.has(geneId)) {
        newSet.delete(geneId)
      } else {
        newSet.add(geneId)
      }
      return newSet
    })
  }

  // Select all / deselect all
  const toggleSelectAll = () => {
    if (selectedGenes.size === genes.length) {
      setSelectedGenes(new Set())
    } else {
      setSelectedGenes(new Set(genes.map(g => g.id)))
    }
  }

  // Import selected genes
  const handleImport = async () => {
    const genesToImport = genes.filter(g => selectedGenes.has(g.id))
    if (genesToImport.length === 0) return

    setImporting(true)
    setImportProgress({ current: 0, total: genesToImport.length })

    const importedParts: Part[] = []

    for (let i = 0; i < genesToImport.length; i++) {
      const gene = genesToImport[i]
      setImportProgress({ current: i + 1, total: genesToImport.length })

      try {
        // Fetch sequence for this gene
        const sequence = await getKeggGeneSequence(gene.id)

        if (sequence) {
          // Create a part from the gene
          const partData = {
            name: `KEGG_${gene.name || gene.id.replace(':', '_')}`,
            type: 'gene' as const,
            description: gene.definition || `Gene from KEGG: ${gene.id}`,
            sequence: sequence,
            organism: organism,
            source: 'KEGG',
          }

          try {
            // Try to save to database
            const savedPart = await createPart(partData)
            importedParts.push(savedPart)
          } catch (saveError) {
            // If save fails (e.g., duplicate), create a temporary part
            const tempPart: Part = {
              id: `temp-${Date.now()}-${i}`,
              name: partData.name,
              type: 'gene',
              description: partData.description,
              sequence: sequence,
              organism: organism,
              source: 'KEGG',
              created_at: new Date().toISOString(),
              updated_at: null,
            }
            importedParts.push(tempPart)
          }
        }
      } catch (error) {
        console.error(`Error importing gene ${gene.id}:`, error)
      }
    }

    setImporting(false)

    if (importedParts.length > 0) {
      onImport(importedParts)
      onClose()
    }
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b bg-amber-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Import from KEGG</h2>
              <p className="text-sm text-gray-600 mt-1">
                Search enzymes or pathways and import genes for your pathway design
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="p-4 border-b bg-gray-50">
          <div className="flex gap-3 mb-3">
            {/* Search mode toggle */}
            <div className="flex bg-gray-200 rounded-lg p-0.5">
              <button
                onClick={() => { setSearchMode('enzyme'); setPathways([]); setEnzymes([]); setGenes([]); }}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  searchMode === 'enzyme'
                    ? 'bg-white text-amber-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Enzymes
              </button>
              <button
                onClick={() => { setSearchMode('pathway'); setPathways([]); setEnzymes([]); setGenes([]); }}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  searchMode === 'pathway'
                    ? 'bg-white text-amber-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Pathways
              </button>
            </div>
            <select
              value={organism}
              onChange={(e) => setOrganism(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm"
            >
              <option value="ecoli">E. coli</option>
              <option value="sce">S. cerevisiae</option>
            </select>
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              placeholder={searchMode === 'enzyme'
                ? "Search enzymes (e.g., nitrogenase, nitrate reductase, kinase)..."
                : "Search pathways (e.g., glycolysis, amino acid, TCA cycle)..."
              }
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
            />
            <button
              onClick={handleSearch}
              disabled={loading || !searchQuery.trim()}
              className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Results List (Pathways or Enzymes) */}
          <div className="w-1/3 border-r overflow-y-auto">
            <div className="p-3 bg-gray-100 border-b">
              <h3 className="font-medium text-sm text-gray-700">
                {searchMode === 'enzyme' ? 'Enzymes' : 'Pathways'}
              </h3>
            </div>

            {searchMode === 'enzyme' ? (
              // Enzyme results
              enzymes.length === 0 ? (
                <div className="p-4 text-center text-gray-500 text-sm">
                  Search for enzymes to see results
                </div>
              ) : (
                <div className="divide-y">
                  {enzymes.map((enzyme) => (
                    <button
                      key={enzyme.ec_number}
                      onClick={() => handleSelectEnzyme(enzyme)}
                      className={`w-full p-3 text-left hover:bg-gray-50 transition-colors ${
                        selectedEnzyme?.ec_number === enzyme.ec_number ? 'bg-amber-50 border-l-4 border-amber-500' : ''
                      }`}
                    >
                      <div className="font-medium text-sm text-gray-900 line-clamp-2">{enzyme.name}</div>
                      <div className="text-xs text-amber-600 mt-0.5 font-mono">EC {enzyme.ec_number}</div>
                    </button>
                  ))}
                </div>
              )
            ) : (
              // Pathway results
              pathways.length === 0 ? (
                <div className="p-4 text-center text-gray-500 text-sm">
                  Search for pathways to see results
                </div>
              ) : (
                <div className="divide-y">
                  {pathways.map((pathway) => (
                    <button
                      key={pathway.id}
                      onClick={() => handleSelectPathway(pathway)}
                      className={`w-full p-3 text-left hover:bg-gray-50 transition-colors ${
                        selectedPathway?.id === pathway.id ? 'bg-amber-50 border-l-4 border-amber-500' : ''
                      }`}
                    >
                      <div className="font-medium text-sm text-gray-900">{pathway.name}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{pathway.id}</div>
                    </button>
                  ))}
                </div>
              )
            )}
          </div>

          {/* Genes List */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-3 bg-gray-100 border-b flex items-center justify-between">
              <h3 className="font-medium text-sm text-gray-700">
                Genes {genes.length > 0 && `(${selectedGenes.size}/${genes.length} selected)`}
              </h3>
              {genes.length > 0 && (
                <button
                  onClick={toggleSelectAll}
                  className="text-xs text-amber-600 hover:text-amber-700"
                >
                  {selectedGenes.size === genes.length ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>

            {loadingGenes ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-amber-600"></div>
                <span className="ml-2 text-gray-600">Loading genes...</span>
              </div>
            ) : !selectedPathway && !selectedEnzyme ? (
              <div className="p-4 text-center text-gray-500 text-sm">
                Select {searchMode === 'enzyme' ? 'an enzyme' : 'a pathway'} to view its genes
              </div>
            ) : genes.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">
                No genes found for this {searchMode === 'enzyme' ? 'enzyme' : 'pathway'} in {organism === 'ecoli' ? 'E. coli' : 'S. cerevisiae'}
              </div>
            ) : (
              <div className="divide-y">
                {genes.map((gene) => (
                  <label
                    key={gene.id}
                    className="flex items-start gap-3 p-3 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedGenes.has(gene.id)}
                      onChange={() => toggleGeneSelection(gene.id)}
                      className="mt-1 rounded text-amber-600 focus:ring-amber-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-sm font-medium text-gray-900">
                        {gene.name || gene.id}
                      </div>
                      {gene.definition && (
                        <div className="text-xs text-gray-600 mt-0.5 line-clamp-2">
                          {gene.definition}
                        </div>
                      )}
                      <div className="text-xs text-gray-400 mt-0.5">{gene.id}</div>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-gray-50 flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {importing && (
              <span>
                Importing {importProgress.current}/{importProgress.total} genes...
              </span>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 border rounded-lg hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              onClick={handleImport}
              disabled={selectedGenes.size === 0 || importing}
              className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
            >
              {importing ? 'Importing...' : `Import ${selectedGenes.size} Gene${selectedGenes.size !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
