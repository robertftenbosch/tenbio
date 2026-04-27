import { useState } from 'react'
import { PartsList } from './components/PartsLibrary/PartsList'
import { SearchFilter, FilterOptions } from './components/PartsLibrary/SearchFilter'
import { UnifiedSearch } from './components/UnifiedSearch/UnifiedSearch'
import { PathwayDesigner } from './components/PathwayCanvas/PathwayDesigner'
import { CodonOptimizer } from './components/CodonOptimizer/CodonOptimizer'
import { StructurePredictor } from './components/StructurePredictor/StructurePredictor'
import { AIDesigner } from './components/AIDesigner/AIDesigner'
import { Part } from './types/parts'

type Tab = 'library' | 'search' | 'ai' | 'designer' | 'optimizer' | 'structure'

const TABS: { id: Tab; label: string }[] = [
  { id: 'library', label: 'Parts Library' },
  { id: 'search', label: 'Search Databases' },
  { id: 'ai', label: 'AI Designer' },
  { id: 'designer', label: 'Pathway Designer' },
  { id: 'optimizer', label: 'Codon Optimizer' },
  { id: 'structure', label: 'Structure Predictor' },
]

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('library')
  const [filters, setFilters] = useState<FilterOptions>({
    search: '',
    type: '',
    organism: '',
  })
  const [structureSequence, setStructureSequence] = useState<string | undefined>()
  const [structureName, setStructureName] = useState<string | undefined>()
  const [pendingDesignerParts, setPendingDesignerParts] = useState<Part[]>([])

  const navigateToStructure = (sequence: string, name?: string) => {
    setStructureSequence(sequence)
    setStructureName(name)
    setActiveTab('structure')
  }

  const handleAIDesignHandoff = (parts: Part[]) => {
    setPendingDesignerParts(parts)
    setActiveTab('designer')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-bio-green-700 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold">Tenbio Pathways Finder</h1>
          <p className="text-bio-green-100 mt-1">
            Design genetic pathways for synthetic biology
          </p>
        </div>

        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-4">
          <nav className="flex gap-1 flex-wrap">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 font-medium rounded-t-lg transition-colors ${
                  activeTab === tab.id
                    ? 'bg-gray-50 text-bio-green-700'
                    : 'text-bio-green-100 hover:text-white hover:bg-bio-green-600'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {activeTab === 'library' && (
          <>
            <SearchFilter filters={filters} onFilterChange={setFilters} />
            <PartsList filters={filters} onPredictStructure={navigateToStructure} />
          </>
        )}
        {activeTab === 'search' && (
          <>
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Search Databases</h2>
            <p className="text-gray-600 mb-6">
              Search across local parts, KEGG pathways, UniProt proteins, and iGEM BioBricks.
            </p>
            <UnifiedSearch onPredictStructure={navigateToStructure} />
          </>
        )}
        {activeTab === 'ai' && <AIDesigner onUseDesign={handleAIDesignHandoff} />}
        {activeTab === 'designer' && (
          <PathwayDesigner
            injectedImportedParts={pendingDesignerParts}
            onInjectedConsumed={() => setPendingDesignerParts([])}
          />
        )}
        {activeTab === 'optimizer' && <CodonOptimizer />}
        {activeTab === 'structure' && (
          <StructurePredictor
            initialSequence={structureSequence}
            initialName={structureName}
          />
        )}
      </main>

      <footer className="bg-gray-100 border-t mt-12">
        <div className="max-w-7xl mx-auto px-4 py-4 text-center text-gray-500 text-sm">
          Tenbio - Metabolic Pathway Designer for Synthetic Biology
        </div>
      </footer>
    </div>
  )
}

export default App
