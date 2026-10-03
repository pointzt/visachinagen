'use client'

import { useId, useState } from 'react'
import type { Guides } from '@/lib/chinaVisa'
import { useObjectUrl } from '@/hooks/useObjectUrl'
import { cn } from '@/lib/utils'
import { Field, FieldLabel } from '@/components/ui/field'
import { Switch } from '@/components/ui/switch'

interface SideBySideProps {
  original: string
  processed: string | null
  mask?: string
  guides?: Guides
  width: number
  height: number
  busy: boolean
}

function GuideOverlay({ guides, width, height }: { guides: Guides; width: number; height: number }) {
  const [bandTop, bandBottom] = guides.crown_band
  return (
    <svg className="absolute inset-0 h-full w-full pointer-events-none" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {bandTop !== null && bandBottom !== null && (
        <rect x={0} y={bandTop} width={width} height={bandBottom - bandTop} fill="#22c55e" opacity={0.12} />
      )}
      {guides.eye_max_y !== null && (
        <line x1={0} x2={width} y1={guides.eye_max_y} y2={guides.eye_max_y} stroke="#f97316" strokeWidth={1.5} strokeDasharray="6 4" />
      )}
      {guides.chin_max_y !== null && (
        <line x1={0} x2={width} y1={guides.chin_max_y} y2={guides.chin_max_y} stroke="#f97316" strokeWidth={1.5} strokeDasharray="6 4" />
      )}
      <line x1={guides.center_x} x2={guides.center_x} y1={0} y2={height} stroke="#38bdf8" strokeWidth={1} strokeDasharray="4 4" opacity={0.8} />
      {guides.crown_y !== null && <line x1={0} x2={width} y1={guides.crown_y} y2={guides.crown_y} stroke="#16a34a" strokeWidth={1.5} />}
      {guides.eye_y !== null && <line x1={0} x2={width} y1={guides.eye_y} y2={guides.eye_y} stroke="#eab308" strokeWidth={1.5} />}
      {guides.chin_y !== null && <line x1={0} x2={width} y1={guides.chin_y} y2={guides.chin_y} stroke="#16a34a" strokeWidth={1.5} />}
    </svg>
  )
}

export default function SideBySide({ original, processed, mask, guides, width, height, busy }: SideBySideProps) {
  const [showGuides, setShowGuides] = useState(true)
  const [showMask, setShowMask] = useState(false)
  const id = useId()
  const originalUrl = useObjectUrl(showMask && mask ? mask : original)
  const processedUrl = useObjectUrl(processed)

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <figure className="space-y-1.5">
          <div className="relative flex items-center justify-center overflow-hidden rounded-lg border bg-muted" style={{ aspectRatio: `${width} / ${height}` }}>
            {originalUrl && <img src={originalUrl} alt={showMask ? 'Background mask preview' : 'Original photo'} className="max-h-full max-w-full object-contain" />}
          </div>
          <figcaption className="text-center text-xs text-muted-foreground">{showMask ? 'Mask preview (pink = removed)' : 'Original'}</figcaption>
        </figure>
        <figure className="space-y-1.5">
          <div className="relative overflow-hidden rounded-lg border bg-white" style={{ aspectRatio: `${width} / ${height}` }}>
            {processedUrl ? (
              <>
                <img src={processedUrl} alt="Processed visa photo" className={cn('absolute inset-0 h-full w-full', busy && 'opacity-50')} />
                {showGuides && guides && <GuideOverlay guides={guides} width={width} height={height} />}
              </>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center p-4 text-center text-xs text-muted-foreground">No output</div>
            )}
          </div>
          <figcaption className="text-center text-xs text-muted-foreground">Processed · {width}×{height}px</figcaption>
        </figure>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-3">
        <Field orientation="horizontal" className="w-auto">
          <Switch id={`${id}-guides`} checked={showGuides} onCheckedChange={setShowGuides} />
          <FieldLabel htmlFor={`${id}-guides`} className="font-normal">Measurement guides</FieldLabel>
        </Field>
        <Field orientation="horizontal" className="w-auto">
          <Switch id={`${id}-mask`} checked={showMask} onCheckedChange={setShowMask} disabled={!mask} />
          <FieldLabel htmlFor={`${id}-mask`} className="font-normal">Background mask</FieldLabel>
        </Field>
      </div>
      {showGuides && guides && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span><span className="mr-1 inline-block h-0.5 w-3 bg-green-600 align-middle" />Crown / chin (measured)</span>
          <span><span className="mr-1 inline-block h-0.5 w-3 bg-yellow-500 align-middle" />Eye line (measured)</span>
          <span><span className="mr-1 inline-block h-2 w-3 bg-green-500/20 align-middle" />Allowed crown zone</span>
          <span><span className="mr-1 inline-block h-0.5 w-3 border-t border-dashed border-orange-500 align-middle" />Limit</span>
        </div>
      )}
    </div>
  )
}
