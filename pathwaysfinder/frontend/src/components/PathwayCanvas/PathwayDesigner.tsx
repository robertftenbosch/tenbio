import { useState, useCallback, useRef } from 'react'
import { Part } from '../../types/parts'
import { SequencingImportResponse, Sbol3Format } from '../../types/export'
import { useParts } from '../../hooks/useParts'
import { PartCard } from '../PartsLibrary/PartCard'
import { PathwayCanvas } from './PathwayCanvas'
import { KeggImportModal } from './KeggImportModal'
import { exportSbol3, importSequencing } from '../../api/exportImport'

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

  // SBOL3 export state
  const [sbol3Format, setSbol3Format] = useState<Sbol3Format>('json-ld')
  const [sbol3Loading, setSbol3Loading] = useState(false)

  // Sequencing import state
  const [showSequencing, setShowSequencing] = useState(false)
  const [seqLoading, setSeqLoading] = useState(false)
  const [seqResult, setSeqResult] = useState<SequencingImportResponse | null>(null)
  const [seqError, setSeqError] = useState<string | null>(null)
  const seqFileRef = useRef<HTMLInputElement>(null)

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

  const downloadBlob = (blob: Blob, filename: string) => {
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

  // --- SBOL3 Export ---
  const handleExportSbol3 = async () => {
    setSbol3Loading(true)
    try {
      const blob = await exportSbol3({
        name: pathwayParts.map(p => p.name).join('_'),
        description: `Synthetic pathway: ${pathwayParts.map(p => p.name).join(' → ')}`,
        parts: pathwayParts.map(p => ({
          name: p.name,
          type: p.type,
          sequence: p.sequence,
          description: p.description || '',
        })),
        format: sbol3Format,
      })
      const ext = sbol3Format === 'rdf-xml' ? 'xml' : 'jsonld'
      downloadBlob(blob, `pathway_${Date.now()}.${ext}`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'SBOL3 export failed')
    } finally {
      setSbol3Loading(false)
    }
  }

  // --- CSV Plate Map ---
  const exportPlateMap = () => {
    const wells = generateWellPositions()
    const rows = ['Well,Part_Name,Part_Type,Sequence_Length,Concentration_nM']
    pathwayParts.forEach((part, idx) => {
      const well = wells[idx] || `?${idx + 1}`
      rows.push(`${well},${part.name},${part.type},${part.sequence.length},10`)
    })
    downloadFile(rows.join('\n'), `plate_map_${Date.now()}.csv`, 'text/csv')
  }

  // --- CSV Assembly Worklist ---
  const exportAssemblyWorklist = () => {
    const wells = generateWellPositions()
    const rows = ['Step,Source_Plate,Source_Well,Dest_Plate,Dest_Well,Volume_uL,Component']
    pathwayParts.forEach((part, idx) => {
      const well = wells[idx] || `?${idx + 1}`
      rows.push(`${idx + 1},Parts_Plate,${well},Assembly_Plate,A1,2.0,${part.name}`)
    })
    downloadFile(rows.join('\n'), `assembly_worklist_${Date.now()}.csv`, 'text/csv')
  }

  const generateWellPositions = (): string[] => {
    const rows = 'ABCDEFGH'
    const positions: string[] = []
    for (let col = 1; col <= 12; col++) {
      for (let row = 0; row < 8; row++) {
        positions.push(`${rows[row]}${col}`)
      }
    }
    return positions
  }

  // --- Sequencing Import ---
  const handleSequencingFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setSeqLoading(true)
    setSeqError(null)
    setSeqResult(null)

    try {
      const parts = pathwayParts.length > 0
        ? pathwayParts.map(p => ({ name: p.name, type: p.type, sequence: p.sequence }))
        : undefined
      const result = await importSequencing(file, parts)
      setSeqResult(result)
    } catch (err) {
      setSeqError(err instanceof Error ? err.message : 'Failed to import sequencing file')
    } finally {
      setSeqLoading(false)
      // Reset file input so the same file can be re-uploaded
      if (seqFileRef.current) seqFileRef.current.value = ''
    }
  }

  const getSimilarityColor = (similarity: number) => {
    if (similarity >= 95) return 'text-green-700 bg-green-100'
    if (similarity >= 80) return 'text-yellow-700 bg-yellow-100'
    return 'text-red-700 bg-red-100'
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
                  onClick={() => setShowSequencing(!showSequencing)}
                  className="px-3 py-1.5 bg-teal-600 text-white rounded-lg text-sm hover:bg-teal-700"
                >
                  Verify Sequence
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
            <div className="mb-4 p-3 bg-gray-50 rounded-lg border space-y-3">
              {/* Sequence Formats */}
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-2">Sequence Formats</p>
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

              {/* Standards (SBOL3) */}
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-2">Standards</p>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={sbol3Format}
                    onChange={(e) => setSbol3Format(e.target.value as Sbol3Format)}
                    className="px-2 py-1.5 border rounded text-sm"
                  >
                    <option value="json-ld">JSON-LD</option>
                    <option value="rdf-xml">RDF/XML</option>
                  </select>
                  <button
                    onClick={handleExportSbol3}
                    disabled={sbol3Loading}
                    className="px-3 py-1.5 bg-emerald-600 text-white rounded text-sm hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {sbol3Loading ? 'Exporting...' : 'Download SBOL3'}
                  </button>
                </div>
              </div>

              {/* Lab Automation */}
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-2">Lab Automation</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={exportPlateMap}
                    className="px-3 py-1.5 bg-orange-600 text-white rounded text-sm hover:bg-orange-700"
                  >
                    Plate Map CSV
                  </button>
                  <button
                    onClick={exportAssemblyWorklist}
                    className="px-3 py-1.5 bg-amber-600 text-white rounded text-sm hover:bg-amber-700"
                  >
                    Assembly Worklist CSV
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Sequencing Verification Panel */}
          {showSequencing && pathwayParts.length > 0 && (
            <div className="mb-4 p-3 bg-teal-50 rounded-lg border border-teal-200">
              <p className="text-xs font-medium text-teal-800 uppercase mb-2">Sequencing Verification</p>
              <div className="flex items-center gap-2 mb-2">
                <input
                  ref={seqFileRef}
                  type="file"
                  accept=".fastq,.fq,.ab1,.abi"
                  onChange={handleSequencingFile}
                  className="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-teal-600 file:text-white hover:file:bg-teal-700"
                />
              </div>
              <p className="text-xs text-gray-500 mb-2">Upload .fastq, .fq, .ab1, or .abi files</p>

              {seqLoading && (
                <div className="text-sm text-teal-700 py-2">Parsing sequencing file...</div>
              )}

              {seqError && (
                <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{seqError}</div>
              )}

              {seqResult && (
                <div className="space-y-3">
                  {/* Parse results */}
                  <div className="bg-white rounded p-2 border">
                    <p className="text-xs font-medium text-gray-700 mb-1">Read Info</p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
                      <span>Read: <strong>{seqResult.parse_result.read_name}</strong></span>
                      <span>Format: <strong>{seqResult.parse_result.format.toUpperCase()}</strong></span>
                      <span>Length: <strong>{seqResult.parse_result.sequence_length} bp</strong></span>
                      <span>Avg Quality: <strong className={seqResult.parse_result.avg_quality >= 20 ? 'text-green-700' : 'text-red-700'}>
                        Q{seqResult.parse_result.avg_quality}
                      </strong></span>
                    </div>
                  </div>

                  {/* Alignment results */}
                  {seqResult.alignment && (
                    <div className="bg-white rounded p-2 border">
                      <p className="text-xs font-medium text-gray-700 mb-1">Alignment to Pathway</p>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 mb-2">
                        <span>Similarity: <strong className={getSimilarityColor(seqResult.alignment.overall_similarity) + ' px-1 rounded'}>
                          {seqResult.alignment.overall_similarity}%
                        </strong></span>
                        <span>Coverage: <strong>{seqResult.alignment.coverage_percent}%</strong></span>
                        <span>Matching: <strong>{seqResult.alignment.matching_bases}/{seqResult.alignment.reference_length} bp</strong></span>
                        <span>Query: <strong>{seqResult.alignment.query_length} bp</strong></span>
                      </div>

                      {/* Per-part results */}
                      <div className="space-y-1">
                        {seqResult.alignment.part_results.map((pr, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-xs">
                            <span className={`inline-block px-1.5 py-0.5 rounded font-mono ${
                              pr.type === 'promoter' ? 'bg-blue-200' :
                              pr.type === 'rbs' ? 'bg-purple-200' :
                              pr.type === 'terminator' ? 'bg-red-200' :
                              'bg-green-200'
                            }`}>
                              {pr.name}
                            </span>
                            <span className="text-gray-400">{pr.length} bp</span>
                            <span className={`px-1.5 py-0.5 rounded font-medium ${getSimilarityColor(pr.similarity)}`}>
                              {pr.similarity}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
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
