export interface PhotoDimensions {
  width_px: number
  height_px: number
  width_mm: number
  height_mm: number
  dpi: number
}

export interface PhotoBackground {
  color: string
  name: string
}

export interface FaceRequirements {
  head_height_percent: number
  eye_level_percent: number
  min_head_height_mm: number
  max_head_height_mm: number
}

export interface FileRequirements {
  max_size_kb: number
  formats: string[]
  color_mode: string
}

export interface PhotoSpec {
  name: string
  country: string
  dimensions: PhotoDimensions
  background: PhotoBackground
  face_requirements: FaceRequirements
  file_requirements: FileRequirements
  rules: string[]
}
