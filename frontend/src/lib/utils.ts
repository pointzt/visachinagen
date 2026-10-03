export { cn } from "cn"

export function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb.toFixed(0)} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

export function validateImageFile(file: File): string | null {
  if (file.type && !file.type.startsWith('image/')) return 'Please upload an image file.'
  if (file.size > 15 * 1024 * 1024) return 'File size must be under 15MB.'
  return null
}
