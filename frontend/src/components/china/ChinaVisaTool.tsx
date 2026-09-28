'use client'

import { useState } from 'react'
import { useImageUpload } from '@/hooks/useImageUpload'
import { useChinaVisa } from '@/hooks/useChinaVisa'
import { base64ToBlob, type Profile } from '@/lib/chinaVisa'
import { useObjectUrl } from '@/hooks/useObjectUrl'
import { formatFileSize } from '@/lib/utils'
import type { PhotoSpec } from '@/lib/types'
import PhotoUploader from '@/components/PhotoUploader'
import PrintSheet from '@/components/PrintSheet'
import Card from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import Spinner from '@/components/ui/Spinner'
import SideBySide from './SideBySide'
import DecisionBanner from './DecisionBanner'
import CorrectionsPanel from './CorrectionsPanel'
import ChecksPanel from './ChecksPanel'

const PROFILES: { id: Profile; label: string; detail: string; size: [number, number] }[] = [
  { id: 'digital', label: 'Digital (online application)', detail: '420×560 px JPEG, 40–120 KB', size: [420, 560] },
  { id: 'paper', label: 'Paper (application form)', detail: '33×48 mm at 300 dpi', size: [390, 567] },
]

const PAPER_SPEC: PhotoSpec = {
  name: 'Chinese Visa (paper)',
  country: 'China',
  dimensions: { width_px: 390, height_px: 567, width_mm: 33, height_mm: 48, dpi: 300 },
  background: { color: '#FFFFFF', name: 'White' },
  face_requirements: { head_height_percent: 0.635, eye_level_percent: 0.6, min_head_height_mm: 28, max_head_height_mm: 33 },
  file_requirements: { max_size_kb: 0, formats: ['JPEG'], color_mode: 'RGB' },
  rules: [],
}

export default function ChinaVisaTool() {
  const [profile, setProfile] = useState<Profile>('digital')
  const { file, previewUrl, error: uploadError, load, clear } = useImageUpload()
  const cv = useChinaVisa()
  const busy = cv.status === 'processing' || cv.status === 'rendering'
  const result = cv.result
  const size = PROFILES.find((p) => p.id === (result?.profile ?? profile))!.size

  const processedUrl = useObjectUrl(result?.processed_image)

  function handleClear() {
    clear()
    cv.reset()
  }

  function changeProfile(p: Profile) {
    setProfile(p)
    if (file && result) cv.rerender(file, p)
  }

  function download() {
    if (!result?.processed_image) return
    // The exact bytes the server validated: no re-encoding in the browser.
    const url = URL.createObjectURL(base64ToBlob(result.processed_image, 'image/jpeg'))
    const a = document.createElement('a')
    a.href = url
    a.download = `china-visa-${result.profile}-${result.output?.width}x${result.output?.height}.jpg`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-1">
        <Card title="Upload Photo" step={1}>
          <PhotoUploader onFileSelect={(f) => { cv.reset(); return load(f) }} previewUrl={previewUrl} error={uploadError} onClear={handleClear} />
        </Card>
        <Card title="Photo Type" step={2}>
          <div className="space-y-2">
            {PROFILES.map((p) => (
              <label key={p.id} className={`flex items-start gap-2 rounded-lg border p-2.5 cursor-pointer ${profile === p.id ? 'border-primary-300 bg-primary-50/50' : 'border-gray-200'}`}>
                <input type="radio" className="mt-0.5" checked={profile === p.id} onChange={() => changeProfile(p.id)} disabled={busy} />
                <span>
                  <span className="block text-sm text-gray-800">{p.label}</span>
                  <span className="block text-[11px] text-gray-500">{p.detail}</span>
                </span>
              </label>
            ))}
            <p className="text-[10px] text-gray-400">Requirements: MFA Department of Consular Affairs, “Photo Requirements for Chinese Visa Application” (2016).</p>
          </div>
        </Card>
        <Card title="Create" step={3}>
          <Button className="w-full" size="lg" disabled={!file || busy} loading={cv.status === 'processing'}
            onClick={() => file && cv.start(file, profile)}>
            {result ? 'Process again from scratch' : 'Create China Visa Photo'}
          </Button>
          {cv.error && <p className="mt-3 text-sm text-red-600 rounded-lg bg-red-50 border border-red-100 p-2.5">{cv.error}</p>}
          <p className="mt-2 text-[11px] text-gray-400">
            Photos are processed in memory and not stored. Faces are never retouched, reshaped or generated.
          </p>
        </Card>
      </div>

      <div className="lg:col-span-2 space-y-4">
        {!result && cv.status !== 'processing' && (
          <div className="rounded-xl border-2 border-dashed border-gray-200 bg-white p-6 sm:p-12 flex flex-col items-center justify-center text-center min-h-48 sm:min-h-96">
            <h3 className="font-semibold text-gray-400 text-base">Your China visa photo will appear here</h3>
            <p className="text-gray-300 mt-1 text-sm">Every automatic correction is listed and can be undone.</p>
          </div>
        )}

        {cv.status === 'processing' && (
          <div className="rounded-xl border border-gray-200 bg-white p-6 sm:p-12 flex flex-col items-center justify-center min-h-48 sm:min-h-96 space-y-3">
            <Spinner size="lg" />
            <p className="font-semibold text-gray-700">Analysing your photo…</p>
            <p className="text-xs text-gray-400">Face and pose, tilt, background, lighting, then the final file is measured.</p>
          </div>
        )}

        {result && cv.status !== 'processing' && (
          <>
            <DecisionBanner decision={result.decision} summary={result.summary} advice={result.retake_advice} />

            <Card title="Original and processed">
              <SideBySide original={result.original_preview} processed={result.processed_image} mask={result.mask_preview}
                guides={result.guides} width={size[0]} height={size[1]} busy={busy} />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm" disabled={!cv.canUndo || busy || !file} onClick={() => file && cv.undo(file, profile)}>↶ Undo</Button>
                <Button variant="outline" size="sm" disabled={!cv.canRedo || busy || !file} onClick={() => file && cv.redo(file, profile)}>↷ Redo</Button>
                <Button variant="ghost" size="sm" disabled={busy || !file} onClick={() => file && cv.resetToAuto(file, profile)}>Reset to automatic</Button>
                {cv.status === 'rendering' && <span className="flex items-center gap-1.5 text-xs text-gray-400"><Spinner size="sm" /> Updating…</span>}
              </div>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Corrections">
                <CorrectionsPanel corrections={result.corrections} overrides={cv.overrides} disabled={busy || !file}
                  onChange={(next) => file && cv.apply(file, profile, next)} />
              </Card>
              <div className="space-y-4">
                {result.processed_image && (
                  <Card title="Download">
                    <div className="space-y-2">
                      {result.output && (
                        <p className="text-xs text-gray-500">
                          {result.output.width}×{result.output.height}px · {formatFileSize(result.output.file_size_kb)} · JPEG · {result.output.dpi ?? '—'} dpi
                        </p>
                      )}
                      <Button className="w-full" size="lg" onClick={download} disabled={busy}>Download photo</Button>
                      {result.decision !== 'pass' && (
                        <p className="text-[11px] text-amber-700">Review the warnings before submitting this photo.</p>
                      )}
                    </div>
                  </Card>
                )}
                <Card title="Requirement checks">
                  <ChecksPanel checks={result.checks} />
                  <p className="mt-3 text-[10px] text-gray-400">
                    Spec {result.spec.id} v{result.spec.version} ({result.spec.source.edition}). “Provisional” marks thresholds PhotoGen uses to
                    judge qualitative rules. Passing these checks does not guarantee acceptance by the consulate.
                  </p>
                </Card>
              </div>
            </div>

            {result.profile === 'paper' && processedUrl && (
              <Card title="Print Sheet">
                <PrintSheet imageSrc={processedUrl} spec={PAPER_SPEC} />
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  )
}
