import axios from 'axios'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export type Profile = 'digital' | 'paper'
export type Decision = 'pass' | 'review' | 'retake'
export type CheckStatus = 'pass' | 'warn' | 'fail' | 'unverifiable'

export interface CropOverride {
  scale: number
  offset_x: number
  offset_y: number
}

export interface Overrides {
  rotation: 'auto' | 'off' | 'manual'
  rotation_deg: number
  replace_background: boolean
  edge_refine: boolean
  lighting: 'auto' | 'off' | 'manual'
  exposure_ev: number
  contrast: number
  crop: CropOverride
}

export const DEFAULT_OVERRIDES: Overrides = {
  rotation: 'auto',
  rotation_deg: 0,
  replace_background: true,
  edge_refine: true,
  lighting: 'auto',
  exposure_ev: 0,
  contrast: 0,
  crop: { scale: 1, offset_x: 0, offset_y: 0 },
}

export interface Check {
  id: string
  group: 'file' | 'geometry' | 'face' | 'pose' | 'background' | 'lighting' | 'checklist'
  label: string
  status: CheckStatus
  message: string
  stage: 'input' | 'output'
  basis: 'verified' | 'provisional'
  measured: string | number | null
  expected: string | null
  unit: string | null
  remedy: 'retake' | 'adjust' | null
}

export interface RotationCorrection {
  id: 'rotation'
  label: string
  applied: boolean
  mode: Overrides['rotation']
  angle_deg: number
  suggested: boolean
  suggested_angle_deg: number
  reason: string
  confidence: number
  classification: 'level' | 'camera_tilt' | 'head_tilt' | 'ambiguous'
}

export interface BackgroundCorrection {
  id: 'background'
  label: string
  applied: boolean
  edge_refine: boolean
  reason: string
}

export interface LightingCorrection {
  id: 'lighting'
  label: string
  applied: boolean
  mode: Overrides['lighting']
  exposure_ev: number
  contrast: number
  reason: string
}

export interface CropCorrection {
  id: 'crop'
  label: string
  applied: boolean
  manual: boolean
  scale: number
  adjust: CropOverride
  reason: string
}

export type Correction = RotationCorrection | BackgroundCorrection | LightingCorrection | CropCorrection

export interface Guides {
  crown_y: number | null
  eye_y: number | null
  chin_y: number | null
  crown_band: [number | null, number | null]
  eye_max_y: number | null
  chin_max_y: number | null
  center_x: number
}

export interface ChinaVisaResult {
  success: boolean
  decision: Decision
  summary: string
  profile: Profile
  spec: { id: string; version: string; name: string; source: { title: string; publisher: string; edition: string } }
  original_preview: string
  processed_image: string | null
  mask_preview?: string
  alpha_png?: string
  corrections: Correction[]
  checks: Check[]
  retake_advice: string[]
  guides?: Guides
  output?: { width: number; height: number; file_size_kb: number; dpi: number | null; quality: number }
  timings: Record<string, number>
}

export function base64ToBlob(base64: string, type: string): Blob {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new Blob([bytes], { type })
}

export async function processChinaVisa(
  file: File,
  profile: Profile,
  overrides: Overrides,
  alpha?: Blob | null,
): Promise<ChinaVisaResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('profile', profile)
  form.append('overrides', JSON.stringify(overrides))
  if (alpha) form.append('alpha', alpha, 'alpha.png')
  const res = await axios.post(`${BASE_URL}/api/v2/process`, form)
  return res.data
}
