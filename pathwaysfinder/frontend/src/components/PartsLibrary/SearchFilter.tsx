import { PART_TYPES, ORGANISMS } from '../../types/parts'

export interface FilterOptions {
  search: string
  type: string
  organism: string
}

interface SearchFilterProps {
  filters: FilterOptions
  onFilterChange: (filters: FilterOptions) => void
}

const TYPE_LABELS: Record<string, string> = {
  promoter: 'Promoter',
  rbs: 'RBS',
  terminator: 'Terminator',
  gene: 'Gene',
}

const ORGANISM_LABELS: Record<string, string> = {
  ecoli: 'E. coli',
  yeast: 'S. cerevisiae',
}

export function SearchFilter({ filters, onFilterChange }: SearchFilterProps) {
  const handleChange = (field: keyof FilterOptions, value: string) => {
    onFilterChange({ ...filters, [field]: value })
  }

  const clearFilters = () => {
    onFilterChange({ search: '', type: '', organism: '' })
  }

  const hasFilters = filters.search || filters.type || filters.organism

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4 mb-6">
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1">
          <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-1">
            Search
          </label>
          <div className="relative">
            <input
              type="text"
              id="search"
              placeholder="Search by name or description..."
              value={filters.search}
              onChange={(e) => handleChange('search', e.target.value)}
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

        <div className="w-full md:w-40">
          <label htmlFor="type" className="block text-sm font-medium text-gray-700 mb-1">
            Part Type
          </label>
          <select
            id="type"
            value={filters.type}
            onChange={(e) => handleChange('type', e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
          >
            <option value="">All types</option>
            {PART_TYPES.map((type) => (
              <option key={type} value={type}>
                {TYPE_LABELS[type] || type}
              </option>
            ))}
          </select>
        </div>

        <div className="w-full md:w-40">
          <label htmlFor="organism" className="block text-sm font-medium text-gray-700 mb-1">
            Organism
          </label>
          <select
            id="organism"
            value={filters.organism}
            onChange={(e) => handleChange('organism', e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
          >
            <option value="">All organisms</option>
            {ORGANISMS.map((org) => (
              <option key={org} value={org}>
                {ORGANISM_LABELS[org] || org}
              </option>
            ))}
          </select>
        </div>

        {hasFilters && (
          <div className="flex items-end">
            <button
              onClick={clearFilters}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
