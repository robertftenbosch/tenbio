import { useState } from 'react'
import { ChainInput as ChainInputType, COMMON_IONS } from '../../types/structure'

interface ChainInputProps {
  onAdd: (chain: ChainInputType) => void
}

type ChainType = ChainInputType['type']

export function ChainInputForm({ onAdd }: ChainInputProps) {
  const [type, setType] = useState<ChainType>('protein')
  const [sequence, setSequence] = useState('')
  const [ligandId, setLigandId] = useState('')
  const [ionId, setIonId] = useState<string>('MG')
  const [count, setCount] = useState(1)

  const handleAdd = () => {
    const chain: ChainInputType = { type, count }

    if (type === 'protein' || type === 'dna' || type === 'rna') {
      if (!sequence.trim()) return
      chain.sequence = sequence.trim().toUpperCase()
    } else if (type === 'ligand') {
      if (!ligandId.trim()) return
      chain.ligand_id = ligandId.trim()
    } else if (type === 'ion') {
      chain.ion_id = ionId
    }

    onAdd(chain)
    setSequence('')
    setLigandId('')
    setCount(1)
  }

  const isValid = () => {
    if (type === 'protein' || type === 'dna' || type === 'rna') return sequence.trim().length > 0
    if (type === 'ligand') return ligandId.trim().length > 0
    if (type === 'ion') return !!ionId
    return false
  }

  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <h4 className="text-sm font-semibold text-gray-700 mb-3">Add Chain</h4>

      {/* Chain type selector */}
      <div className="flex gap-1 mb-3">
        {(['protein', 'dna', 'rna', 'ligand', 'ion'] as ChainType[]).map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
              type === t
                ? 'bg-bio-green-600 text-white'
                : 'bg-white text-gray-600 border hover:bg-gray-100'
            }`}
          >
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Conditional fields */}
      {(type === 'protein' || type === 'dna' || type === 'rna') && (
        <div className="mb-3">
          <label className="block text-xs font-medium text-gray-600 mb-1">
            {type === 'protein' ? 'Amino Acid' : type === 'dna' ? 'DNA' : 'RNA'} Sequence
          </label>
          <textarea
            value={sequence}
            onChange={(e) => setSequence(e.target.value)}
            placeholder={
              type === 'protein'
                ? 'MVSKGEELFTGVVPILVELD...'
                : type === 'dna'
                ? 'ATCGATCG...'
                : 'AUCGAUCG...'
            }
            rows={3}
            className="w-full px-3 py-2 text-sm font-mono border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500 resize-none"
          />
        </div>
      )}

      {type === 'ligand' && (
        <div className="mb-3">
          <label className="block text-xs font-medium text-gray-600 mb-1">
            CCD Code or SMILES
          </label>
          <input
            type="text"
            value={ligandId}
            onChange={(e) => setLigandId(e.target.value)}
            placeholder="e.g. ATP, NAG, or a SMILES string"
            className="w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
          />
          <p className="text-xs text-gray-400 mt-1">
            Use CCD codes (e.g. ATP, GTP, HEM) or SMILES notation
          </p>
        </div>
      )}

      {type === 'ion' && (
        <div className="mb-3">
          <label className="block text-xs font-medium text-gray-600 mb-1">Ion</label>
          <select
            value={ionId}
            onChange={(e) => setIonId(e.target.value)}
            className="w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
          >
            {COMMON_IONS.map((ion) => (
              <option key={ion} value={ion}>
                {ion}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Count and Add button */}
      <div className="flex items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Copies</label>
          <input
            type="number"
            value={count}
            onChange={(e) => setCount(Math.max(1, parseInt(e.target.value) || 1))}
            min={1}
            max={26}
            className="w-20 px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={!isValid()}
          className="px-4 py-2 text-sm font-medium text-white bg-bio-green-600 rounded-lg hover:bg-bio-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Add Chain
        </button>
      </div>
    </div>
  )
}
