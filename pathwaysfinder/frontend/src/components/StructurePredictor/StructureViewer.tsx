import { useEffect, useRef, useState } from 'react'
import { getStructureUrl } from '../../api/structure'

interface StructureViewerProps {
  jobId: string
}

type ViewStyle = 'cartoon' | 'stick' | 'surface'

export function StructureViewer({ jobId }: StructureViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null)
  const [viewerInstance, setViewerInstance] = useState<any>(null)
  const [style, setStyle] = useState<ViewStyle>('cartoon')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load 3Dmol.js and structure
  useEffect(() => {
    if (!viewerRef.current) return

    const load = async () => {
      setLoading(true)
      setError(null)

      try {
        // Dynamically import 3Dmol
        const $3Dmol = (window as any).$3Dmol
        if (!$3Dmol) {
          setError('3Dmol.js not loaded. Add the script tag to index.html.')
          setLoading(false)
          return
        }

        // Create viewer
        const viewer = $3Dmol.createViewer(viewerRef.current, {
          backgroundColor: '#f8f9fa',
        })

        // Fetch CIF data
        const url = getStructureUrl(jobId)
        const response = await fetch(url)
        if (!response.ok) throw new Error('Failed to download structure')
        const cifData = await response.text()

        // Load into viewer
        viewer.addModel(cifData, 'cif')
        applyStyle(viewer, 'cartoon')
        viewer.zoomTo()
        viewer.render()

        setViewerInstance(viewer)
      } catch (e: any) {
        setError(e.message || 'Failed to load structure')
      } finally {
        setLoading(false)
      }
    }

    load()

    return () => {
      if (viewerInstance) {
        viewerInstance.clear()
      }
    }
  }, [jobId])

  // Update style when changed
  useEffect(() => {
    if (viewerInstance) {
      applyStyle(viewerInstance, style)
      viewerInstance.render()
    }
  }, [style, viewerInstance])

  const applyStyle = (viewer: any, viewStyle: ViewStyle) => {
    viewer.setStyle({}, {})

    if (viewStyle === 'cartoon') {
      // Color by pLDDT-like scheme (by b-factor) — blue=high, red=low
      viewer.setStyle(
        {},
        {
          cartoon: {
            colorscheme: {
              prop: 'b',
              gradient: 'rwb',
              min: 0,
              max: 100,
            },
          },
        }
      )
    } else if (viewStyle === 'stick') {
      viewer.setStyle({}, { stick: { radius: 0.15 } })
    } else if (viewStyle === 'surface') {
      viewer.setStyle({}, { cartoon: { opacity: 0.5 } })
      viewer.addSurface(
        (window as any).$3Dmol.SurfaceType.VDW,
        {
          opacity: 0.7,
          colorscheme: {
            prop: 'b',
            gradient: 'rwb',
            min: 0,
            max: 100,
          },
        },
        {}
      )
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-2 bg-gray-100 border-b">
        <span className="text-xs font-medium text-gray-600 mr-2">Style:</span>
        {(['cartoon', 'stick', 'surface'] as ViewStyle[]).map((s) => (
          <button
            key={s}
            onClick={() => setStyle(s)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              style === s
                ? 'bg-bio-green-600 text-white'
                : 'bg-white text-gray-600 border hover:bg-gray-50'
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-2">
          {viewerInstance && (
            <button
              onClick={() => {
                viewerInstance.zoomTo()
                viewerInstance.render()
              }}
              className="px-2 py-1 text-xs bg-white text-gray-600 border rounded hover:bg-gray-50 transition-colors"
            >
              Reset View
            </button>
          )}
          <a
            href={getStructureUrl(jobId)}
            download={`${jobId}.cif`}
            className="px-2 py-1 text-xs bg-white text-gray-600 border rounded hover:bg-gray-50 transition-colors"
          >
            Download CIF
          </a>
        </div>
      </div>

      {/* Viewer area */}
      <div className="relative" style={{ height: '400px' }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-bio-green-600"></div>
            <span className="ml-2 text-gray-600">Loading structure...</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
            <div className="text-center">
              <p className="text-red-600 text-sm">{error}</p>
              <p className="text-gray-500 text-xs mt-2">
                Ensure 3Dmol.js is loaded via a script tag in index.html
              </p>
            </div>
          </div>
        )}
        <div ref={viewerRef} style={{ width: '100%', height: '100%' }} />
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 p-2 bg-gray-50 border-t text-xs text-gray-500">
        <span className="font-medium">Confidence (pLDDT):</span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: '#0053D6' }}></span>
          Very high (&gt;90)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: '#65CBF3' }}></span>
          High (70-90)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: '#FFDB13' }}></span>
          Low (50-70)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: '#FF7D45' }}></span>
          Very low (&lt;50)
        </span>
      </div>
    </div>
  )
}
