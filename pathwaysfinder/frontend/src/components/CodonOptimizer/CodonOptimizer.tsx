import { useState } from 'react'
import { optimizeProtein, optimizeDNA, translateDNA, OptimizeResponse, Organism } from '../../api/optimize'

type InputType = 'protein' | 'dna'

export function CodonOptimizer() {
  const [inputType, setInputType] = useState<InputType>('protein')
  const [sequence, setSequence] = useState('')
  const [organism, setOrganism] = useState<Organism>('ecoli')
  const [result, setResult] = useState<OptimizeResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handleOptimize = async () => {
    if (!sequence.trim()) {
      setError('Please enter a sequence')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      let response: OptimizeResponse
      if (inputType === 'protein') {
        response = await optimizeProtein({ sequence, organism })
      } else {
        response = await optimizeDNA({ sequence, organism })
      }
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Optimization failed')
    } finally {
      setLoading(false)
    }
  }

  const handleTranslate = async () => {
    if (!sequence.trim() || inputType !== 'dna') return

    setLoading(true)
    setError(null)

    try {
      const response = await translateDNA(sequence)
      setSequence(response.protein_sequence)
      setInputType('protein')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Translation failed')
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const downloadFasta = () => {
    if (!result) return
    const fasta = `>Optimized_${organism}_${result.length_aa}aa\n${result.optimized_dna.match(/.{1,80}/g)?.join('\n') || result.optimized_dna}`
    const blob = new Blob([fasta], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `optimized_${organism}.fasta`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Codon Optimizer</h2>
      <p className="text-sm text-gray-600 mb-6">
        Optimize DNA sequences for expression in E. coli or yeast
      </p>

      {/* Input type toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setInputType('protein')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            inputType === 'protein'
              ? 'bg-bio-green-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          Protein Sequence
        </button>
        <button
          onClick={() => setInputType('dna')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            inputType === 'dna'
              ? 'bg-bio-green-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          DNA Sequence
        </button>
      </div>

      {/* Sequence input */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {inputType === 'protein' ? 'Amino Acid Sequence' : 'DNA Sequence'}
        </label>
        <textarea
          value={sequence}
          onChange={(e) => setSequence(e.target.value)}
          placeholder={inputType === 'protein'
            ? 'Enter amino acid sequence (e.g., MSKGEELFTGVVPILVELD...)'
            : 'Enter DNA sequence (e.g., ATGAGCAAAGGC...)'
          }
          className="w-full h-32 px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
        />
        <p className="text-xs text-gray-500 mt-1">
          {sequence.replace(/\s/g, '').length} {inputType === 'protein' ? 'amino acids' : 'nucleotides'}
        </p>
      </div>

      {/* Organism selection */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Target Organism
        </label>
        <div className="flex gap-4">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="organism"
              value="ecoli"
              checked={organism === 'ecoli'}
              onChange={() => setOrganism('ecoli')}
              className="text-bio-green-600 focus:ring-bio-green-500"
            />
            <span className="text-sm">E. coli</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="organism"
              value="yeast"
              checked={organism === 'yeast'}
              onChange={() => setOrganism('yeast')}
              className="text-bio-green-600 focus:ring-bio-green-500"
            />
            <span className="text-sm">S. cerevisiae (Yeast)</span>
          </label>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={handleOptimize}
          disabled={loading || !sequence.trim()}
          className="px-4 py-2 bg-bio-green-600 text-white rounded-lg font-medium hover:bg-bio-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Optimizing...' : 'Optimize Codons'}
        </button>
        {inputType === 'dna' && (
          <button
            onClick={handleTranslate}
            disabled={loading || !sequence.trim()}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Translate to Protein
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="border-t pt-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Optimized Sequence</h3>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Length</p>
              <p className="text-lg font-semibold">{result.length_bp} bp</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Protein</p>
              <p className="text-lg font-semibold">{result.length_aa} aa</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">GC Content</p>
              <p className="text-lg font-semibold">{result.gc_content}%</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Organism</p>
              <p className="text-lg font-semibold">{result.organism === 'ecoli' ? 'E. coli' : 'Yeast'}</p>
            </div>
          </div>

          {result.codons_changed !== undefined && (
            <p className="text-sm text-gray-600 mb-4">
              {result.codons_changed} codons changed, {result.codons_unchanged} unchanged
            </p>
          )}

          {/* Optimized DNA */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">Optimized DNA</label>
              <div className="flex gap-2">
                <button
                  onClick={() => copyToClipboard(result.optimized_dna)}
                  className={`px-3 py-1 text-sm rounded transition-colors ${
                    copied ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
                <button
                  onClick={downloadFasta}
                  className="px-3 py-1 text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 rounded"
                >
                  Download FASTA
                </button>
              </div>
            </div>
            <pre className="p-4 bg-gray-50 rounded-lg border text-sm font-mono text-gray-700 overflow-x-auto whitespace-pre-wrap break-all max-h-48">
              {result.optimized_dna}
            </pre>
          </div>

          {/* Original protein */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-2">Original Protein</label>
            <pre className="p-4 bg-gray-50 rounded-lg border text-sm font-mono text-gray-700 overflow-x-auto whitespace-pre-wrap break-all max-h-32">
              {result.original_protein}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
