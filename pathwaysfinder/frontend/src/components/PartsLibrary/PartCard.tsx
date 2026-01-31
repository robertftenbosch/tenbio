import { Part } from '../../types/parts'

interface PartCardProps {
  part: Part
  onClick?: () => void
  draggable?: boolean
  onDragStart?: (e: React.DragEvent) => void
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

export function PartCard({ part, onClick, draggable, onDragStart }: PartCardProps) {
  const colors = TYPE_COLORS[part.type] || { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' }

  return (
    <div
      className={`rounded-lg border ${colors.border} ${colors.bg} p-4 hover:shadow-md transition-shadow ${onClick ? 'cursor-pointer' : ''} ${draggable ? 'cursor-grab active:cursor-grabbing' : ''}`}
      onClick={onClick}
      draggable={draggable}
      onDragStart={onDragStart}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-mono font-semibold text-gray-900">{part.name}</h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.text} ${colors.bg} border ${colors.border}`}>
          {TYPE_LABELS[part.type] || part.type}
        </span>
      </div>

      {part.description && (
        <p className="mt-2 text-sm text-gray-600 line-clamp-2">{part.description}</p>
      )}

      <div className="mt-3 flex items-center gap-3 text-xs text-gray-500">
        {part.organism && (
          <span className="flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
            {part.organism === 'ecoli' ? 'E. coli' : part.organism}
          </span>
        )}
        {part.source && (
          <span className="flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            {part.source}
          </span>
        )}
        <span className="flex items-center gap-1">
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {part.sequence.length} bp
        </span>
      </div>
    </div>
  )
}
