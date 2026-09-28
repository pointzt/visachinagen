'use client'

import { useState } from 'react'
import type { Guides } from '@/lib/chinaVisa'
import { useObjectUrl } from '@/hooks/useObjectUrl'

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
  const originalUrl = useObjectUrl(showMask && mask ? mask : original)
  const processedUrl = useObjectUrl(processed)

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <figure className="space-y-1.5">
          <div className="relative rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex items-center justify-center" style={{ aspectRatio: `${width} / ${height}` }}>
            {originalUrl && <img src={originalUrl} alt={showMask ? 'Background mask preview' : 'Original photo'} className="max-h-full max-w-full object-contain" />}
          </div>
          <figcaption className="text-[11px] text-gray-500 text-center">{showMask ? 'Mask preview (pink = removed)' : 'Original'}</figcaption>
        </figure>
        <figure className="space-y-1.5">
          <div className="relative rounded-lg overflow-hidden border border-gray-200 bg-white" style={{ aspectRatio: `${width} / ${height}` }}>
            {processedUrl ? (
              <>
                <img src={processedUrl} alt="Processed visa photo" className={`absolute inset-0 h-full w-full ${busy ? 'opacity-50' : ''}`} />
                {showGuides && guides && <GuideOverlay guides={guides} width={width} height={height} />}
              </>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400 p-4 text-center">No output</div>
            )}
          </div>
          <figcaption className="text-[11px] text-gray-500 text-center">Processed · {width}×{height}px</figcaption>
        </figure>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={showGuides} onChange={(e) => setShowGuides(e.target.checked)} /> Measurement guides
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={showMask} onChange={(e) => setShowMask(e.target.checked)} disabled={!mask} /> Background mask
        </label>
      </div>
      {showGuides && guides && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500">
          <span><span className="inline-block w-3 h-0.5 bg-green-600 align-middle mr-1" />Crown / chin (measured)</span>
          <span><span className="inline-block w-3 h-0.5 bg-yellow-500 align-middle mr-1" />Eye line (measured)</span>
          <span><span className="inline-block w-3 h-2 bg-green-500/20 align-middle mr-1" />Allowed crown zone</span>
          <span><span className="inline-block w-3 h-0.5 border-t border-dashed border-orange-500 align-middle mr-1" />Limit</span>
        </div>
      )}
    </div>
  )
}
