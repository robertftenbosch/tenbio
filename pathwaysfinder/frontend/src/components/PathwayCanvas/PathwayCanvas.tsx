import { useRef, useEffect, useState } from 'react'
import * as d3 from 'd3'
import { Part } from '../../types/parts'

interface PathwayPart extends Part {
  x: number
  y: number
  instanceId: string
}

interface PathwayCanvasProps {
  parts: PathwayPart[]
  onPartsChange: (parts: PathwayPart[]) => void
  onRemovePart: (partId: string) => void
}

const TYPE_COLORS: Record<string, string> = {
  promoter: '#3b82f6',  // blue
  rbs: '#8b5cf6',       // purple
  terminator: '#ef4444', // red
  gene: '#22c55e',      // green
}

const PART_HEIGHT = 40
const PART_MIN_WIDTH = 80
const CANVAS_HEIGHT = 200

export function PathwayCanvas({ parts, onPartsChange, onRemovePart }: PathwayCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(800)

  // Update container width on resize
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.clientWidth)
      }
    }
    updateWidth()
    window.addEventListener('resize', updateWidth)
    return () => window.removeEventListener('resize', updateWidth)
  }, [])

  // Draw pathway visualization
  useEffect(() => {
    if (!svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    if (parts.length === 0) return

    const g = svg.append('g')
      .attr('transform', `translate(20, ${CANVAS_HEIGHT / 2})`)

    // Calculate positions
    let currentX = 0
    const partPositions = parts.map((part, index) => {
      const width = Math.max(PART_MIN_WIDTH, part.name.length * 8)
      const pos = { ...part, x: currentX, width }
      currentX += width + 10
      return pos
    })

    // Draw connecting line (backbone)
    if (partPositions.length > 1) {
      g.append('line')
        .attr('x1', 0)
        .attr('y1', 0)
        .attr('x2', currentX - 10)
        .attr('y2', 0)
        .attr('stroke', '#9ca3af')
        .attr('stroke-width', 3)
    }

    // Draw parts
    const partGroups = g.selectAll('.part')
      .data(partPositions)
      .enter()
      .append('g')
      .attr('class', 'part')
      .attr('transform', (d) => `translate(${d.x}, 0)`)
      .style('cursor', 'pointer')

    // Part shapes based on type
    partGroups.each(function(d) {
      const group = d3.select(this)
      const color = TYPE_COLORS[d.type] || '#6b7280'
      const width = (d as any).width

      if (d.type === 'promoter') {
        // Arrow shape for promoter
        group.append('path')
          .attr('d', `M0,-${PART_HEIGHT/2} L${width-15},-${PART_HEIGHT/2} L${width},0 L${width-15},${PART_HEIGHT/2} L0,${PART_HEIGHT/2} Z`)
          .attr('fill', color)
          .attr('stroke', d3.color(color)?.darker(0.5)?.toString() || color)
          .attr('stroke-width', 2)
      } else if (d.type === 'terminator') {
        // T-shape for terminator
        group.append('rect')
          .attr('x', 0)
          .attr('y', -PART_HEIGHT/2)
          .attr('width', width)
          .attr('height', PART_HEIGHT)
          .attr('rx', 4)
          .attr('fill', color)
          .attr('stroke', d3.color(color)?.darker(0.5)?.toString() || color)
          .attr('stroke-width', 2)
        group.append('line')
          .attr('x1', width/2)
          .attr('y1', -PART_HEIGHT/2 - 10)
          .attr('x2', width/2)
          .attr('y2', PART_HEIGHT/2 + 10)
          .attr('stroke', d3.color(color)?.darker(0.5)?.toString() || color)
          .attr('stroke-width', 3)
      } else if (d.type === 'rbs') {
        // Rounded rectangle for RBS
        group.append('rect')
          .attr('x', 0)
          .attr('y', -PART_HEIGHT/2)
          .attr('width', width)
          .attr('height', PART_HEIGHT)
          .attr('rx', PART_HEIGHT/2)
          .attr('fill', color)
          .attr('stroke', d3.color(color)?.darker(0.5)?.toString() || color)
          .attr('stroke-width', 2)
      } else {
        // Rectangle for gene
        group.append('rect')
          .attr('x', 0)
          .attr('y', -PART_HEIGHT/2)
          .attr('width', width)
          .attr('height', PART_HEIGHT)
          .attr('rx', 4)
          .attr('fill', color)
          .attr('stroke', d3.color(color)?.darker(0.5)?.toString() || color)
          .attr('stroke-width', 2)
      }

      // Part label
      group.append('text')
        .attr('x', width / 2)
        .attr('y', 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-size', '11px')
        .attr('font-weight', 'bold')
        .attr('font-family', 'monospace')
        .text(d.name.length > 12 ? d.name.substring(0, 10) + '...' : d.name)

      // Delete button
      group.append('circle')
        .attr('cx', width - 5)
        .attr('cy', -PART_HEIGHT/2 + 5)
        .attr('r', 8)
        .attr('fill', '#ef4444')
        .attr('stroke', 'white')
        .attr('stroke-width', 1)
        .attr('opacity', 0)
        .attr('class', 'delete-btn')
        .style('cursor', 'pointer')
        .on('click', (event) => {
          event.stopPropagation()
          onRemovePart(d.instanceId)
        })

      group.append('text')
        .attr('x', width - 5)
        .attr('y', -PART_HEIGHT/2 + 9)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-size', '10px')
        .attr('font-weight', 'bold')
        .attr('opacity', 0)
        .attr('class', 'delete-text')
        .attr('pointer-events', 'none')
        .text('×')

      // Show delete button on hover
      group.on('mouseenter', function() {
        d3.select(this).select('.delete-btn').attr('opacity', 1)
        d3.select(this).select('.delete-text').attr('opacity', 1)
      }).on('mouseleave', function() {
        d3.select(this).select('.delete-btn').attr('opacity', 0)
        d3.select(this).select('.delete-text').attr('opacity', 0)
      })
    })

    // Add drag behavior
    const drag = d3.drag<SVGGElement, any>()
      .on('start', function() {
        d3.select(this).raise()
      })
      .on('drag', function(event, d) {
        const newX = event.x
        // Find insertion point
        const insertIndex = partPositions.findIndex((p, i) => {
          const midX = p.x + (p as any).width / 2
          return newX < midX
        })
        d3.select(this).attr('transform', `translate(${event.x}, ${event.y})`)
      })
      .on('end', function(event, d) {
        // Reorder parts based on final position
        const currentIndex = parts.findIndex(p => p.instanceId === d.instanceId)
        let newIndex = partPositions.findIndex((p) => {
          const midX = p.x + (p as any).width / 2
          return event.x < midX
        })
        if (newIndex === -1) newIndex = parts.length - 1
        if (newIndex !== currentIndex) {
          const newParts = [...parts]
          const [removed] = newParts.splice(currentIndex, 1)
          newParts.splice(newIndex > currentIndex ? newIndex - 1 : newIndex, 0, removed)
          onPartsChange(newParts)
        }
      })

    partGroups.call(drag as any)

  }, [parts, containerWidth, onPartsChange, onRemovePart])

  return (
    <div ref={containerRef} className="w-full">
      <svg
        ref={svgRef}
        width={containerWidth}
        height={CANVAS_HEIGHT}
        className="bg-white border-2 border-dashed border-gray-300 rounded-lg"
      />
    </div>
  )
}
