'use client'

import { useCallback, useRef, useState } from 'react'
import {
  DEFAULT_OVERRIDES,
  base64ToBlob,
  processChinaVisa,
  type ChinaVisaResult,
  type Overrides,
  type Profile,
} from '@/lib/chinaVisa'

type Status = 'idle' | 'processing' | 'rendering' | 'done' | 'error'

function errorMessage(e: unknown): string {
  return (
    (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
    (e as { message?: string })?.message ||
    'Processing failed. Please try again.'
  )
}

/**
 * Runs the China visa engine and keeps an undo/redo history of override states.
 * The first call segments the photo; later edits send back the returned matte so the server
 * only re-renders (seconds instead of a full re-segmentation). Nothing is stored server-side.
 */
export function useChinaVisa() {
  const [result, setResult] = useState<ChinaVisaResult | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<Overrides[]>([DEFAULT_OVERRIDES])
  const [index, setIndex] = useState(0)
  const alphaRef = useRef<Blob | null>(null)
  const requestRef = useRef(0)

  const overrides = history[index]

  const run = useCallback(async (file: File, profile: Profile, ov: Overrides, reuseMatte: boolean) => {
    const id = ++requestRef.current
    setStatus(reuseMatte ? 'rendering' : 'processing')
    setError(null)
    try {
      const res = await processChinaVisa(file, profile, ov, reuseMatte ? alphaRef.current : null)
      if (id !== requestRef.current) return
      if (res.alpha_png) alphaRef.current = base64ToBlob(res.alpha_png, 'image/png')
      setResult(res)
      setStatus('done')
    } catch (e) {
      if (id !== requestRef.current) return
      setError(errorMessage(e))
      setStatus('error')
    }
  }, [])

  const start = useCallback(
    (file: File, profile: Profile) => {
      alphaRef.current = null
      setHistory([DEFAULT_OVERRIDES])
      setIndex(0)
      return run(file, profile, DEFAULT_OVERRIDES, false)
    },
    [run],
  )

  const apply = useCallback(
    (file: File, profile: Profile, next: Overrides) => {
      setHistory((h) => [...h.slice(0, index + 1), next])
      setIndex((i) => i + 1)
      return run(file, profile, next, true)
    },
    [index, run],
  )

  const goto = useCallback(
    (file: File, profile: Profile, target: number) => {
      if (target < 0 || target >= history.length) return
      setIndex(target)
      return run(file, profile, history[target], true)
    },
    [history, run],
  )

  const rerender = useCallback(
    (file: File, profile: Profile) => run(file, profile, overrides, alphaRef.current !== null),
    [overrides, run],
  )

  const reset = useCallback(() => {
    requestRef.current++
    alphaRef.current = null
    setResult(null)
    setStatus('idle')
    setError(null)
    setHistory([DEFAULT_OVERRIDES])
    setIndex(0)
  }, [])

  return {
    result,
    status,
    error,
    overrides,
    canUndo: index > 0,
    canRedo: index < history.length - 1,
    start,
    apply,
    undo: (file: File, profile: Profile) => goto(file, profile, index - 1),
    redo: (file: File, profile: Profile) => goto(file, profile, index + 1),
    resetToAuto: (file: File, profile: Profile) => apply(file, profile, DEFAULT_OVERRIDES),
    rerender,
    reset,
  }
}
