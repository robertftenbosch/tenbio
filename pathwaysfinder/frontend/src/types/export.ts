export type Sbol3Format = 'json-ld' | 'rdf-xml'

export interface Sbol3ExportRequest {
  name: string
  description: string
  parts: Sbol3ExportPart[]
  format: Sbol3Format
}

export interface Sbol3ExportPart {
  name: string
  type: string
  sequence: string
  description: string
}

export interface ParseResult {
  sequence: string
  avg_quality: number
  format: string
  read_name: string
  num_reads: number
  sequence_length: number
}

export interface PartAlignmentResult {
  name: string
  type: string
  length: number
  similarity: number
}

export interface AlignmentResult {
  overall_similarity: number
  coverage_percent: number
  matching_bases: number
  reference_length: number
  query_length: number
  part_results: PartAlignmentResult[]
}

export interface SequencingImportResponse {
  parse_result: ParseResult
  alignment: AlignmentResult | null
}
