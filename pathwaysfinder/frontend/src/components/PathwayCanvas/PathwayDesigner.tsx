import { useState, useCallback } from 'react'
import { Part } from '../../types/parts'
import { useParts } from '../../hooks/useParts'
import { PartCard } from '../PartsLibrary/PartCard'
import { PathwayCanvas } from './PathwayCanvas'
import { KeggImportModal } from './KeggImportModal'

interface PathwayPart extends Part {
  x: number
  y: number
  instanceId: string  // Unique ID for each instance in pathway
}

export function PathwayDesigner() {
  const [pathwayParts, setPathwayParts] = useState<PathwayPart[]>([])
  const [selectedType, setSelectedType] = useState<string>('')
  const [showExport, setShowExport] = useState(false)
  const [showKeggImport, setShowKeggImport] = useState(false)
  const [importedParts, setImportedParts] = useState<Part[]>([])

  const { parts, loading, refetch } = useParts({ type: selectedType || undefined })

  // Combine local parts with imported parts
  const allParts = [...parts, ...importedParts.filter(ip =>
    selectedType === '' || ip.type === selectedType
  )]

  // Handle imported KEGG genes
  const handleKeggImport = (newParts: Part[]) => {
    setImportedParts(prev => [...prev, ...newParts])
    refetch() // Refresh to pick up any saved parts
  }

  const handleDragStart = (e: React.DragEvent, part: Part) => {
    e.dataTransfer.setData('application/json', JSON.stringify(part))
    e.dataTransfer.effectAllowed = 'copy'
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const data = e.dataTransfer.getData('application/json')
    if (data) {
      const part: Part = JSON.parse(data)
      const newPart: PathwayPart = {
        ...part,
        x: 0,
        y: 0,
        instanceId: `${part.id}-${Date.now()}`,
      }
      setPathwayParts(prev => [...prev, newPart])
    }
  }, [])

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }

  const handleRemovePart = useCallback((instanceId: string) => {
    setPathwayParts(prev => prev.filter(p => p.instanceId !== instanceId))
  }, [])

  const handlePartsChange = useCallback((newParts: PathwayPart[]) => {
    setPathwayParts(newParts)
  }, [])

  const getFullSequence = () => {
    return pathwayParts.map(p => p.sequence).join('')
  }

  const exportFasta = () => {
    const sequence = getFullSequence()
    const partNames = pathwayParts.map(p => p.name).join('_')
    const fasta = `>Pathway_${partNames}\n${sequence.match(/.{1,80}/g)?.join('\n') || sequence}`
    downloadFile(fasta, `pathway_${Date.now()}.fasta`, 'text/plain')
  }

  const exportGenBank = () => {
    const sequence = getFullSequence()
    const partNames = pathwayParts.map(p => p.name).join('_')
    const date = new Date().toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase()

    let features = ''
    let position = 1
    pathwayParts.forEach(part => {
      const end = position + part.sequence.length - 1
      features += `     ${part.type.padEnd(15)} ${position}..${end}\n`
      features += `                     /label="${part.name}"\n`
      features += `                     /note="${part.description || ''}"\n`
      position = end + 1
    })

    const genbank = `LOCUS       Pathway_construct        ${sequence.length} bp    DNA     linear   SYN ${date}
DEFINITION  Synthetic pathway: ${partNames}
ACCESSION   .
VERSION     .
KEYWORDS    synthetic biology; pathway design
SOURCE      synthetic construct
  ORGANISM  synthetic construct
FEATURES             Location/Qualifiers
${features}ORIGIN
${formatGenbankSequence(sequence)}
//`
    downloadFile(genbank, `pathway_${Date.now()}.gb`, 'text/plain')
  }

  const formatGenbankSequence = (seq: string) => {
    let result = ''
    for (let i = 0; i < seq.length; i += 60) {
      const lineNum = (i + 1).toString().padStart(9, ' ')
      const chunk = seq.slice(i, i + 60)
      const formatted = chunk.match(/.{1,10}/g)?.join(' ') || chunk
      result += `${lineNum} ${formatted.toLowerCase()}\n`
    }
    return result
  }

  const downloadFile = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const copySequence = async () => {
    await navigator.clipboard.writeText(getFullSequence())
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Parts Library Sidebar */}
      <div className="lg:w-80 flex-shrink-0">
        <div className="bg-white rounded-lg shadow-sm border p-4">
          <h3 className="font-semibold text-gray-900 mb-3">Parts Library</h3>
          <p className="text-xs text-gray-500 mb-3">Drag parts to add to pathway</p>

          {/* Type filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg mb-4 text-sm"
          >
            <option value="">All types</option>
            <option value="promoter">Promoters</option>
            <option value="rbs">RBS</option>
            <option value="gene">Genes</option>
            <option value="terminator">Terminators</option>
          </select>

          {/* Import from KEGG button */}
          <button
            onClick={() => setShowKeggImport(true)}
            className="w-full px-3 py-2 mb-4 text-sm font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 transition-colors"
          >
            Import from KEGG
          </button>

          {/* Parts list */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {loading ? (
              <div className="text-center py-4 text-gray-500">Loading...</div>
            ) : (
              allParts.map(part => (
                <div
                  key={part.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, part)}
                  className="cursor-grab active:cursor-grabbing"
                >
                  <PartCard part={part} />
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Canvas Area */}
      <div className="flex-1">
        <div className="bg-white rounded-lg shadow-sm border p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-gray-900">Pathway Canvas</h3>
              <p className="text-xs text-gray-500">
                {pathwayParts.length === 0
                  ? 'Drop parts here to build your pathway'
                  : `${pathwayParts.length} parts - ${getFullSequence().length} bp total`}
              </p>
            </div>
            {pathwayParts.length > 0 && (
              <div className="flex gap-2">
                <button
                  onClick={() => setShowExport(!showExport)}
                  className="px-3 py-1.5 bg-bio-green-600 text-white rounded-lg text-sm hover:bg-bio-green-700"
                >
                  Export
                </button>
                <button
                  onClick={() => setPathwayParts([])}
                  className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300"
                >
                  Clear
                </button>
              </div>
            )}
          </div>

          {/* Export options */}
          {showExport && pathwayParts.length > 0 && (
            <div className="mb-4 p-3 bg-gray-50 rounded-lg border">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={exportFasta}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                >
                  Download FASTA
                </button>
                <button
                  onClick={exportGenBank}
                  className="px-3 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700"
                >
                  Download GenBank
                </button>
                <button
                  onClick={copySequence}
                  className="px-3 py-1.5 bg-gray-600 text-white rounded text-sm hover:bg-gray-700"
                >
                  Copy Sequence
                </button>
              </div>
            </div>
          )}

          {/* Drop zone / Canvas */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className={`min-h-[200px] ${pathwayParts.length === 0 ? 'flex items-center justify-center' : ''}`}
          >
            {pathwayParts.length === 0 ? (
              <div className="text-center text-gray-400 border-2 border-dashed border-gray-300 rounded-lg p-8 w-full">
                <svg className="mx-auto h-12 w-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                <p>Drag and drop parts here</p>
                <p className="text-xs mt-1">Build: Promoter → RBS → Gene → Terminator</p>
              </div>
            ) : (
              <PathwayCanvas
                parts={pathwayParts}
                onPartsChange={handlePartsChange}
                onRemovePart={handleRemovePart}
              />
            )}
          </div>

          {/* Pathway order hint */}
          {pathwayParts.length > 0 && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-sm text-blue-800">
                <strong>Current order:</strong>{' '}
                {pathwayParts.map((p, i) => (
                  <span key={p.instanceId}>
                    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-mono ${
                      p.type === 'promoter' ? 'bg-blue-200' :
                      p.type === 'rbs' ? 'bg-purple-200' :
                      p.type === 'terminator' ? 'bg-red-200' :
                      'bg-green-200'
                    }`}>
                      {p.name}
                    </span>
                    {i < pathwayParts.length - 1 && <span className="mx-1">→</span>}
                  </span>
                ))}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* KEGG Import Modal */}
      {showKeggImport && (
        <KeggImportModal
          onClose={() => setShowKeggImport(false)}
          onImport={handleKeggImport}
        />
      )}
    </div>
  )
}
