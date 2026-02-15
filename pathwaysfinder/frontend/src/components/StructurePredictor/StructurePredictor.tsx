import { useState, useEffect, useCallback } from 'react'
import { ChainInput as ChainInputType, JobStatus, ProtenixModel } from '../../types/structure'
import { submitPrediction, getJobStatus, getAvailableModels, preloadModel } from '../../api/structure'
import { ChainInputForm } from './ChainInput'
import { StructureViewer } from './StructureViewer'

interface StructurePredictorProps {
  /** Pre-populate with a protein sequence (e.g. from Parts Library) */
  initialSequence?: string
  initialName?: string
}

const speedTierLabel: Record<string, { text: string; color: string }> = {
  fast: { text: 'Fast', color: 'bg-green-100 text-green-700' },
  medium: { text: 'Medium', color: 'bg-yellow-100 text-yellow-700' },
  slow: { text: 'Slow', color: 'bg-orange-100 text-orange-700' },
}

const featureColors: Record<string, string> = {
  MSA: 'bg-blue-100 text-blue-700',
  Template: 'bg-purple-100 text-purple-700',
  'RNA MSA': 'bg-pink-100 text-pink-700',
  ESM: 'bg-indigo-100 text-indigo-700',
  ISM: 'bg-violet-100 text-violet-700',
  Constraints: 'bg-amber-100 text-amber-700',
}

export function StructurePredictor({ initialSequence, initialName }: StructurePredictorProps) {
  const [name, setName] = useState(initialName || '')
  const [chains, setChains] = useState<ChainInputType[]>([])
  const [modelName, setModelName] = useState('protenix_base_default_v1.0.0')
  const [numSamples, setNumSamples] = useState(5)
  const [models, setModels] = useState<ProtenixModel[]>([])

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [currentJob, setCurrentJob] = useState<JobStatus | null>(null)
  const [pollingId, setPollingId] = useState<number | null>(null)

  const [preloading, setPreloading] = useState(false)
  const [preloadMsg, setPreloadMsg] = useState<string | null>(null)

  const refreshModels = useCallback(() => {
    getAvailableModels().then(setModels)
  }, [])

  // Load available models
  useEffect(() => {
    refreshModels()
  }, [refreshModels])

  // Handle initial sequence prop
  useEffect(() => {
    if (initialSequence) {
      setChains([{ type: 'protein', sequence: initialSequence, count: 1 }])
      if (initialName) setName(initialName)
    }
  }, [initialSequence, initialName])

  // Poll job status
  const startPolling = useCallback(
    (jobId: string) => {
      // Clear existing poll
      if (pollingId) clearInterval(pollingId)

      const id = window.setInterval(async () => {
        try {
          const status = await getJobStatus(jobId)
          setCurrentJob(status)

          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(id)
            setPollingId(null)
          }
        } catch {
          // Keep polling on transient errors
        }
      }, 5000)

      setPollingId(id)
    },
    [pollingId]
  )

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingId) clearInterval(pollingId)
    }
  }, [pollingId])

  const handleAddChain = (chain: ChainInputType) => {
    setChains((prev) => [...prev, chain])
  }

  const handleRemoveChain = (index: number) => {
    setChains((prev) => prev.filter((_, i) => i !== index))
  }

  const handlePreload = async () => {
    setPreloading(true)
    setPreloadMsg(null)
    try {
      const result = await preloadModel(modelName)
      setPreloadMsg(result.message)
      if (result.status === 'loading') {
        // Poll models endpoint until loaded
        const pollId = window.setInterval(async () => {
          const updated = await getAvailableModels()
          setModels(updated)
          const target = updated.find((m) => m.name === modelName)
          if (target?.loaded) {
            clearInterval(pollId)
            setPreloading(false)
            setPreloadMsg(`Model '${modelName}' loaded successfully.`)
          }
        }, 3000)
        // Safety timeout: stop polling after 10 minutes
        setTimeout(() => {
          clearInterval(pollId)
          setPreloading(false)
        }, 600_000)
      } else {
        setPreloading(false)
        refreshModels()
      }
    } catch (e: any) {
      setPreloadMsg(e.message || 'Failed to preload model')
      setPreloading(false)
    }
  }

  const handleSubmit = async () => {
    if (chains.length === 0) return

    setSubmitting(true)
    setError(null)
    setCurrentJob(null)

    try {
      const response = await submitPrediction({
        name: name || 'prediction',
        chains,
        model_name: modelName,
        num_samples: numSamples,
      })

      const status = await getJobStatus(response.job_id)
      setCurrentJob(status)
      startPolling(response.job_id)
    } catch (e: any) {
      setError(e.message || 'Failed to submit prediction')
    } finally {
      setSubmitting(false)
    }
  }

  const chainTypeLabel = (chain: ChainInputType) => {
    if (chain.type === 'protein') return `Protein (${chain.sequence?.length || 0} aa)`
    if (chain.type === 'dna') return `DNA (${chain.sequence?.length || 0} nt)`
    if (chain.type === 'rna') return `RNA (${chain.sequence?.length || 0} nt)`
    if (chain.type === 'ligand') return `Ligand: ${chain.ligand_id}`
    if (chain.type === 'ion') return `Ion: ${chain.ion_id}`
    return chain.type
  }

  const chainTypeColor: Record<string, string> = {
    protein: 'bg-green-100 text-green-700',
    dna: 'bg-blue-100 text-blue-700',
    rna: 'bg-purple-100 text-purple-700',
    ligand: 'bg-amber-100 text-amber-700',
    ion: 'bg-gray-100 text-gray-700',
  }

  const selectedModel = models.find((m) => m.name === modelName)

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Structure Prediction</h2>
        <p className="text-sm text-gray-500 mb-6">
          Predict 3D biomolecular structures using Protenix (AlphaFold 3). Add protein chains,
          DNA/RNA sequences, ligands, and ions to model complexes.
        </p>

        {/* Job name */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Prediction Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. GFP monomer, Insulin-receptor complex"
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-bio-green-500"
          />
        </div>

        {/* Chain input form */}
        <ChainInputForm onAdd={handleAddChain} />

        {/* Current chains */}
        {chains.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">
              Chains ({chains.length})
            </h4>
            <div className="space-y-2">
              {chains.map((chain, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 border rounded-lg bg-white"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${chainTypeColor[chain.type]}`}
                    >
                      {chain.type.toUpperCase()}
                    </span>
                    <span className="text-sm text-gray-700">{chainTypeLabel(chain)}</span>
                    {chain.count > 1 && (
                      <span className="text-xs text-gray-400">x{chain.count}</span>
                    )}
                  </div>
                  <button
                    onClick={() => handleRemoveChain(index)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Model selector */}
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 mb-1">Model</label>
          <div className="flex items-start gap-3">
            <div className="flex-1">
              <select
                value={modelName}
                onChange={(e) => {
                  setModelName(e.target.value)
                  setPreloadMsg(null)
                }}
                className="w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-bio-green-500"
              >
                {models.length > 0
                  ? models.map((m) => (
                      <option key={m.name} value={m.name}>
                        {m.description} ({m.parameters_m}M){m.loaded ? ' [Loaded]' : ''}
                      </option>
                    ))
                  : (
                      <option value="protenix_base_default_v1.0.0">
                        Protenix base model (default)
                      </option>
                    )}
              </select>

              {/* Model details */}
              {selectedModel && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {/* Size badge */}
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                    {selectedModel.parameters_m}M params
                  </span>
                  {/* Speed tier */}
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${speedTierLabel[selectedModel.speed_tier]?.color || 'bg-gray-100 text-gray-700'}`}
                  >
                    {speedTierLabel[selectedModel.speed_tier]?.text || selectedModel.speed_tier}
                  </span>
                  {/* Feature tags */}
                  {selectedModel.features.map((f) => (
                    <span
                      key={f}
                      className={`px-2 py-0.5 rounded text-xs font-medium ${featureColors[f] || 'bg-gray-100 text-gray-600'}`}
                    >
                      {f}
                    </span>
                  ))}
                  {/* Loaded badge */}
                  {selectedModel.loaded && (
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                      Loaded
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Preload button */}
            <button
              onClick={handlePreload}
              disabled={preloading || selectedModel?.loaded}
              className="px-3 py-2 text-sm font-medium border rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              title={selectedModel?.loaded ? 'Model already loaded' : 'Preload model into GPU memory'}
            >
              {preloading ? (
                <span className="flex items-center gap-1.5">
                  <span className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-gray-600"></span>
                  Loading...
                </span>
              ) : selectedModel?.loaded ? (
                'Loaded'
              ) : (
                'Preload'
              )}
            </button>
          </div>

          {/* Preload status message */}
          {preloadMsg && (
            <p className="mt-1.5 text-xs text-gray-500">{preloadMsg}</p>
          )}
        </div>

        {/* Samples */}
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 mb-1">Samples</label>
          <input
            type="number"
            value={numSamples}
            onChange={(e) => setNumSamples(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
            min={1}
            max={20}
            className="w-20 px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-bio-green-500"
          />
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Submit button */}
        <div className="mt-6">
          <button
            onClick={handleSubmit}
            disabled={chains.length === 0 || submitting || (currentJob?.status === 'running')}
            className="px-6 py-2.5 text-sm font-medium text-white bg-bio-green-600 rounded-lg hover:bg-bio-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting
              ? 'Submitting...'
              : currentJob?.status === 'running'
              ? 'Prediction Running...'
              : 'Predict Structure'}
          </button>
        </div>
      </div>

      {/* Job Status & Results */}
      {currentJob && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Prediction Results</h3>

          {/* Status indicator */}
          <div className="flex items-center gap-3 mb-4">
            {currentJob.status === 'queued' && (
              <>
                <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
                <span className="text-sm text-gray-700">Queued -- waiting for GPU</span>
              </>
            )}
            {currentJob.status === 'running' && (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-bio-green-600"></div>
                <span className="text-sm text-gray-700">
                  {currentJob.progress || 'Running inference...'}
                </span>
              </>
            )}
            {currentJob.status === 'completed' && (
              <>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-sm text-green-700">Completed</span>
              </>
            )}
            {currentJob.status === 'failed' && (
              <>
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <span className="text-sm text-red-700">
                  Failed: {currentJob.error || 'Unknown error'}
                </span>
              </>
            )}
          </div>

          {/* Confidence scores */}
          {currentJob.confidence && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {currentJob.confidence.plddt != null && (
                <ConfidenceCard label="pLDDT" value={currentJob.confidence.plddt} max={100} />
              )}
              {currentJob.confidence.ptm != null && (
                <ConfidenceCard label="pTM" value={currentJob.confidence.ptm} max={1} />
              )}
              {currentJob.confidence.iptm != null && (
                <ConfidenceCard label="ipTM" value={currentJob.confidence.iptm} max={1} />
              )}
              {currentJob.confidence.ranking_score != null && (
                <ConfidenceCard
                  label="Ranking Score"
                  value={currentJob.confidence.ranking_score}
                  max={1}
                />
              )}
            </div>
          )}

          {/* 3D Viewer */}
          {currentJob.status === 'completed' && currentJob.structure_available && (
            <StructureViewer jobId={currentJob.job_id} />
          )}
        </div>
      )}
    </div>
  )
}

function ConfidenceCard({
  label,
  value,
  max,
}: {
  label: string
  value: number
  max: number
}) {
  const normalized = max === 1 ? value : value / 100
  const color =
    normalized >= 0.9
      ? 'text-blue-700 bg-blue-50 border-blue-200'
      : normalized >= 0.7
      ? 'text-cyan-700 bg-cyan-50 border-cyan-200'
      : normalized >= 0.5
      ? 'text-yellow-700 bg-yellow-50 border-yellow-200'
      : 'text-orange-700 bg-orange-50 border-orange-200'

  return (
    <div className={`p-3 rounded-lg border ${color}`}>
      <div className="text-xs font-medium opacity-75">{label}</div>
      <div className="text-lg font-bold mt-1">
        {max === 1 ? value.toFixed(3) : value.toFixed(1)}
      </div>
    </div>
  )
}
