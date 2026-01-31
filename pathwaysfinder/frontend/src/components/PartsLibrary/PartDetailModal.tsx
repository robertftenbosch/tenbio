import { useState, useEffect } from 'react'
import { Part, Paper } from '../../types/parts'
import { fetchPartPapers } from '../../api/parts'

interface PartDetailModalProps {
  part: Part
  onClose: () => void
}

const TYPE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  promoter: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  rbs: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  terminator: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  gene: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
}

const TYPE_LABELS: Record<string, string> = {
  promoter: 'Promoter',
  rbs: 'RBS',
  terminator: 'Terminator',
  gene: 'Gene',
}

export function PartDetailModal({ part, onClose }: PartDetailModalProps) {
  const [papers, setPapers] = useState<Paper[]>([])
  const [loadingPapers, setLoadingPapers] = useState(true)
  const [copied, setCopied] = useState(false)

  const colors = TYPE_COLORS[part.type] || { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' }

  useEffect(() => {
    async function loadPapers() {
      try {
        const response = await fetchPartPapers(part.id)
        setPapers(response.papers)
      } catch (error) {
        console.error('Failed to load papers:', error)
      } finally {
        setLoadingPapers(false)
      }
    }
    loadPapers()
  }, [part.id])

  const copySequence = async () => {
    await navigator.clipboard.writeText(part.sequence)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
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
      <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className={`p-6 ${colors.bg} border-b ${colors.border}`}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-mono font-bold text-gray-900">{part.name}</h2>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${colors.text} ${colors.bg} border ${colors.border}`}>
                  {TYPE_LABELS[part.type] || part.type}
                </span>
              </div>
              {part.description && (
                <p className="mt-2 text-gray-600">{part.description}</p>
              )}
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

          {/* Metadata */}
          <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-600">
            {part.organism && (
              <span className="flex items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
                <strong>Organism:</strong> {part.organism === 'ecoli' ? 'E. coli' : part.organism}
              </span>
            )}
            {part.source && (
              <span className="flex items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <strong>Source:</strong> {part.source}
              </span>
            )}
            <span className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <strong>Length:</strong> {part.sequence.length} bp
            </span>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Sequence */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold text-gray-900">Sequence</h3>
              <button
                onClick={copySequence}
                className={`flex items-center gap-1 px-3 py-1 rounded text-sm transition-colors ${
                  copied
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {copied ? (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Copied!
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy
                  </>
                )}
              </button>
            </div>
            <pre className="p-4 bg-gray-50 rounded-lg border text-sm font-mono text-gray-700 overflow-x-auto whitespace-pre-wrap break-all">
              {part.sequence}
            </pre>
          </div>

          {/* Research Papers */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Related Research Papers</h3>
            {loadingPapers ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-bio-green-600"></div>
                <span className="ml-2 text-gray-600">Searching PubMed...</span>
              </div>
            ) : papers.length === 0 ? (
              <p className="text-gray-500 py-4">No related papers found.</p>
            ) : (
              <div className="space-y-4">
                {papers.map((paper, index) => (
                  <PaperCard key={paper.pmid || index} paper={paper} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function PaperCard({ paper }: { paper: Paper }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
      <a
        href={paper.url || paper.doi_url || '#'}
        target="_blank"
        rel="noopener noreferrer"
        className="text-bio-green-700 hover:text-bio-green-800 font-medium hover:underline"
      >
        {paper.title}
      </a>

      <div className="mt-1 text-sm text-gray-600">
        {paper.authors.slice(0, 3).join(', ')}
        {paper.authors.length > 3 && ` et al.`}
      </div>

      <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
        {paper.journal && <span>{paper.journal}</span>}
        {paper.year && <span>({paper.year})</span>}
        {paper.doi && (
          <a
            href={paper.doi_url || `https://doi.org/${paper.doi}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            DOI: {paper.doi}
          </a>
        )}
      </div>

      {paper.abstract && (
        <div className="mt-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            {expanded ? 'Hide abstract' : 'Show abstract'}
          </button>
          {expanded && (
            <p className="mt-2 text-sm text-gray-600 leading-relaxed">
              {paper.abstract}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
