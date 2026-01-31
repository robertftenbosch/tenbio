import { useState } from 'react'
import { PartsList } from './components/PartsLibrary/PartsList'
import { SearchFilter, FilterOptions } from './components/PartsLibrary/SearchFilter'
import { PathwayDesigner } from './components/PathwayCanvas/PathwayDesigner'
import { CodonOptimizer } from './components/CodonOptimizer/CodonOptimizer'

type Tab = 'library' | 'designer' | 'optimizer'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('library')
  const [filters, setFilters] = useState<FilterOptions>({
    search: '',
    type: '',
    organism: '',
  })

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
          <nav className="flex gap-1">
            <button
              onClick={() => setActiveTab('library')}
              className={`px-4 py-2 font-medium rounded-t-lg transition-colors ${
                activeTab === 'library'
                  ? 'bg-gray-50 text-bio-green-700'
                  : 'text-bio-green-100 hover:text-white hover:bg-bio-green-600'
              }`}
            >
              Parts Library
            </button>
            <button
              onClick={() => setActiveTab('designer')}
              className={`px-4 py-2 font-medium rounded-t-lg transition-colors ${
                activeTab === 'designer'
                  ? 'bg-gray-50 text-bio-green-700'
                  : 'text-bio-green-100 hover:text-white hover:bg-bio-green-600'
              }`}
            >
              Pathway Designer
            </button>
            <button
              onClick={() => setActiveTab('optimizer')}
              className={`px-4 py-2 font-medium rounded-t-lg transition-colors ${
                activeTab === 'optimizer'
                  ? 'bg-gray-50 text-bio-green-700'
                  : 'text-bio-green-100 hover:text-white hover:bg-bio-green-600'
              }`}
            >
              Codon Optimizer
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {activeTab === 'library' && (
          <>
            <SearchFilter filters={filters} onFilterChange={setFilters} />
            <PartsList filters={filters} />
          </>
        )}
        {activeTab === 'designer' && <PathwayDesigner />}
        {activeTab === 'optimizer' && <CodonOptimizer />}
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
