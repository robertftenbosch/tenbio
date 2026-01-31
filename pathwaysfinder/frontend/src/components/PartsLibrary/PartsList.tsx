import { useState } from 'react'
import { useParts } from '../../hooks/useParts'
import { PartCard } from './PartCard'
import { PartDetailModal } from './PartDetailModal'
import { FilterOptions } from './SearchFilter'
import { Part } from '../../types/parts'

interface PartsListProps {
  filters: FilterOptions
}

export function PartsList({ filters }: PartsListProps) {
  const [selectedPart, setSelectedPart] = useState<Part | null>(null)

  const { parts, total, loading, error } = useParts({
    search: filters.search || undefined,
    type: filters.type || undefined,
    organism: filters.organism || undefined,
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-bio-green-600"></div>
        <span className="ml-3 text-gray-600">Loading parts...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        <p className="font-medium">Error loading parts</p>
        <p className="text-sm mt-1">{error}</p>
        <p className="text-sm mt-2">Make sure the backend is running at http://localhost:8001</p>
      </div>
    )
  }

  if (parts.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="mt-2">No parts found matching your criteria</p>
      </div>
    )
  }

  return (
    <>
      <div>
        <p className="text-sm text-gray-500 mb-4">
          Showing {parts.length} of {total} parts - Click a part for details
        </p>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {parts.map((part) => (
            <PartCard
              key={part.id}
              part={part}
              onClick={() => setSelectedPart(part)}
            />
          ))}
        </div>
      </div>

      {selectedPart && (
        <PartDetailModal
          part={selectedPart}
          onClose={() => setSelectedPart(null)}
        />
      )}
    </>
  )
}
