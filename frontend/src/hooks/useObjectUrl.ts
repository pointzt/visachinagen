'use client'

import { useEffect, useMemo, useRef } from 'react'
import { base64ToBlob } from '@/lib/chinaVisa'

/** Object URL for base64 image data. The previous URL is revoked whenever the data changes. */
export function useObjectUrl(base64: string | null | undefined, type = 'image/jpeg'): string | null {
  const url = useMemo(() => (base64 ? URL.createObjectURL(base64ToBlob(base64, type)) : null), [base64, type])
  const previous = useRef<string | null>(null)
  useEffect(() => {
    if (previous.current && previous.current !== url) URL.revokeObjectURL(previous.current)
    previous.current = url
  }, [url])
  return url
}
