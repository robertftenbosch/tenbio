import { useState } from 'react'
import { useParts } from '../../hooks/useParts'
import { PartCard } from './PartCard'
import { PartDetailModal } from './PartDetailModal'
import { PartFormModal } from './PartFormModal'
import { FilterOptions } from './SearchFilter'
import { Part } from '../../types/parts'

interface PartsListProps {
  filters: FilterOptions
  onPredictStructure?: (sequence: string, name?: string) => void
}

export function PartsList({ filters, onPredictStructure }: PartsListProps) {
  const [selectedPart, setSelectedPart] = useState<Part | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingPart, setEditingPart] = useState<Part | null>(null)

  const { parts, total, loading, error, refetch } = useParts({
    search: filters.search || undefined,
    type: filters.type || undefined,
    organism: filters.organism || undefined,
  })

  const handleEditPart = (part: Part) => {
    setSelectedPart(null)  // Close detail modal if open
    setEditingPart(part)
  }

  const handleFormSuccess = () => {
    refetch()
  }

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

  return (
    <>
      {/* Header with Create button */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">
          {parts.length === 0
            ? 'No parts found matching your criteria'
            : `Showing ${parts.length} of ${total} parts`}
        </p>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-bio-green-600 text-white rounded-lg hover:bg-bio-green-700 transition-colors text-sm font-medium"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Part
        </button>
      </div>

      {parts.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="mt-2">No parts found</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-4 text-bio-green-600 hover:text-bio-green-700 font-medium"
          >
            Create your first part
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {parts.map((part) => (
            <PartCard
              key={part.id}
              part={part}
              onClick={() => setSelectedPart(part)}
              onEdit={() => handleEditPart(part)}
            />
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {selectedPart && (
        <PartDetailModal
          part={selectedPart}
          onClose={() => setSelectedPart(null)}
          onEdit={() => handleEditPart(selectedPart)}
          onPredictStructure={onPredictStructure}
        />
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <PartFormModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleFormSuccess}
        />
      )}

      {/* Edit Modal */}
      {editingPart && (
        <PartFormModal
          part={editingPart}
          onClose={() => setEditingPart(null)}
          onSuccess={handleFormSuccess}
        />
      )}
    </>
  )
}
