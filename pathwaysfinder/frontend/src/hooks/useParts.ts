import { useState, useEffect } from 'react'
import { Part } from '../types/parts'
import { fetchParts } from '../api/parts'

interface UsePartsOptions {
  search?: string
  type?: string
  organism?: string
}

interface UsePartsResult {
  parts: Part[]
  total: number
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useParts(options: UsePartsOptions = {}): UsePartsResult {
  const [parts, setParts] = useState<Part[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { search, type, organism } = options

  const loadParts = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetchParts({ search, type, organism })
      setParts(response.parts)
      setTotal(response.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setParts([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadParts()
  }, [search, type, organism])

  return {
    parts,
    total,
    loading,
    error,
    refetch: loadParts,
  }
}
