import { useState, useEffect } from 'react'
import { Part, PART_TYPES, ORGANISMS } from '../../types/parts'
import { createPart, updatePart, deletePart, PartCreateData, PartUpdateData } from '../../api/parts'

interface PartFormModalProps {
  part?: Part | null  // If provided, we're editing; otherwise creating
  onClose: () => void
  onSuccess: () => void
}

const TYPE_LABELS: Record<string, string> = {
  promoter: 'Promoter',
  rbs: 'RBS',
  terminator: 'Terminator',
  gene: 'Gene',
}

const ORGANISM_LABELS: Record<string, string> = {
  ecoli: 'E. coli',
  yeast: 'Yeast',
}

// Validate DNA sequence (only A, T, G, C allowed)
function isValidDNASequence(sequence: string): boolean {
  return /^[ATGCatgc]*$/.test(sequence)
}

export function PartFormModal({ part, onClose, onSuccess }: PartFormModalProps) {
  const isEditing = !!part

  const [formData, setFormData] = useState({
    name: part?.name || '',
    type: part?.type || 'gene',
    description: part?.description || '',
    sequence: part?.sequence || '',
    organism: part?.organism || '',
    source: part?.source || '',
  })

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Reset form when part changes
  useEffect(() => {
    if (part) {
      setFormData({
        name: part.name,
        type: part.type,
        description: part.description || '',
        sequence: part.sequence,
        organism: part.organism || '',
        source: part.source || '',
      })
    }
  }, [part])

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required'
    } else if (formData.name.length > 50) {
      newErrors.name = 'Name must be 50 characters or less'
    }

    if (!formData.type) {
      newErrors.type = 'Type is required'
    }

    if (!formData.sequence.trim()) {
      newErrors.sequence = 'Sequence is required'
    } else if (!isValidDNASequence(formData.sequence)) {
      newErrors.sequence = 'Sequence must contain only A, T, G, C characters'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    setSubmitting(true)
    setSubmitError(null)

    try {
      const data = {
        name: formData.name.trim(),
        type: formData.type,
        description: formData.description.trim() || null,
        sequence: formData.sequence.toUpperCase().trim(),
        organism: formData.organism || null,
        source: formData.source.trim() || null,
      }

      if (isEditing && part) {
        await updatePart(part.id, data as PartUpdateData)
      } else {
        await createPart(data as PartCreateData)
      }

      onSuccess()
      onClose()
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'An error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!part) return

    setSubmitting(true)
    setSubmitError(null)

    try {
      await deletePart(part.id)
      onSuccess()
      onClose()
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to delete part')
    } finally {
      setSubmitting(false)
      setShowDeleteConfirm(false)
    }
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && !submitting) {
      onClose()
    }
  }

  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }))
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">
              {isEditing ? 'Edit Part' : 'Create New Part'}
            </h2>
            <button
              onClick={onClose}
              disabled={submitting}
              className="text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Error message */}
          {submitError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {submitError}
            </div>
          )}

          {/* Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
              Part Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="name"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="e.g., BBa_J23100"
              className={`w-full px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500 ${
                errors.name ? 'border-red-300 bg-red-50' : 'border-gray-300'
              }`}
              disabled={submitting}
            />
            {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
          </div>

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Part Type <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {PART_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => handleChange('type', type)}
                  disabled={submitting}
                  className={`px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    formData.type === type
                      ? 'bg-bio-green-600 text-white border-bio-green-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:border-bio-green-400'
                  } disabled:opacity-50`}
                >
                  {TYPE_LABELS[type]}
                </button>
              ))}
            </div>
            {errors.type && <p className="mt-1 text-sm text-red-600">{errors.type}</p>}
          </div>

          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              id="description"
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Brief description of the part's function..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500 resize-none"
              disabled={submitting}
            />
          </div>

          {/* Sequence */}
          <div>
            <label htmlFor="sequence" className="block text-sm font-medium text-gray-700 mb-1">
              DNA Sequence <span className="text-red-500">*</span>
            </label>
            <textarea
              id="sequence"
              value={formData.sequence}
              onChange={(e) => handleChange('sequence', e.target.value.replace(/[^ATGCatgc]/g, ''))}
              placeholder="ATGCATGC..."
              rows={4}
              className={`w-full px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500 resize-none ${
                errors.sequence ? 'border-red-300 bg-red-50' : 'border-gray-300'
              }`}
              disabled={submitting}
            />
            <div className="mt-1 flex justify-between text-xs text-gray-500">
              <span>Only A, T, G, C characters allowed</span>
              <span>{formData.sequence.length} bp</span>
            </div>
            {errors.sequence && <p className="mt-1 text-sm text-red-600">{errors.sequence}</p>}
          </div>

          {/* Organism */}
          <div>
            <label htmlFor="organism" className="block text-sm font-medium text-gray-700 mb-1">
              Organism
            </label>
            <select
              id="organism"
              value={formData.organism}
              onChange={(e) => handleChange('organism', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
              disabled={submitting}
            >
              <option value="">Select organism (optional)</option>
              {ORGANISMS.map((org) => (
                <option key={org} value={org}>
                  {ORGANISM_LABELS[org] || org}
                </option>
              ))}
            </select>
          </div>

          {/* Source */}
          <div>
            <label htmlFor="source" className="block text-sm font-medium text-gray-700 mb-1">
              Source
            </label>
            <input
              type="text"
              id="source"
              value={formData.source}
              onChange={(e) => handleChange('source', e.target.value)}
              placeholder="e.g., iGEM, custom, literature"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
              disabled={submitting}
            />
          </div>
        </form>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          {showDeleteConfirm ? (
            <div className="flex items-center justify-between">
              <span className="text-sm text-red-600">Are you sure you want to delete this part?</span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={submitting}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={submitting}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {submitting ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                {isEditing && (
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={submitting}
                    className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
                  >
                    Delete Part
                  </button>
                )}
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  form="part-form"
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="px-6 py-2 text-sm font-medium text-white bg-bio-green-600 rounded-lg hover:bg-bio-green-700 disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Part'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
