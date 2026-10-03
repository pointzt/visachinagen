'use client'

import { useId, useState, type ReactNode } from 'react'
import { DownloadIcon, Redo2Icon, Undo2Icon } from 'lucide-react'
import { useImageUpload } from '@/hooks/useImageUpload'
import { useChinaVisa } from '@/hooks/useChinaVisa'
import { base64ToBlob, type Profile } from '@/lib/chinaVisa'
import { useObjectUrl } from '@/hooks/useObjectUrl'
import { formatFileSize } from '@/lib/utils'
import type { PhotoSpec } from '@/lib/types'
import PhotoUploader from '@/components/PhotoUploader'
import PrintSheet from '@/components/PrintSheet'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Spinner } from '@/components/ui/spinner'
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

function ToolCard({ title, step, children }: { title: string; step?: number; children: ReactNode }) {
  return (
    <Card className="gap-0 py-0">
      <CardHeader className="flex items-center gap-2.5 border-b px-3 py-3 sm:px-5">
        {step !== undefined && (
          <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">{step}</span>
        )}
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-3 sm:p-5">{children}</CardContent>
    </Card>
  )
}

export default function ChinaVisaTool() {
  const radioId = useId()
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
        <ToolCard title="Upload Photo" step={1}>
          <PhotoUploader onFileSelect={(f) => { cv.reset(); return load(f) }} previewUrl={previewUrl} error={uploadError} onClear={handleClear} />
        </ToolCard>
        <ToolCard title="Photo Type" step={2}>
          <div className="space-y-2">
            <RadioGroup value={profile} onValueChange={(v) => changeProfile(v as Profile)} disabled={busy} className="gap-2">
              {PROFILES.map((p) => (
                <Label key={p.id} htmlFor={`${radioId}-${p.id}`}
                  className={cn('flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 font-normal', profile === p.id && 'border-primary/40 bg-primary/5')}>
                  <RadioGroupItem id={`${radioId}-${p.id}`} value={p.id} className="mt-0.5" />
                  <span>
                    <span className="block text-sm text-foreground">{p.label}</span>
                    <span className="block text-[11px] text-muted-foreground">{p.detail}</span>
                  </span>
                </Label>
              ))}
            </RadioGroup>
            <p className="text-[10px] text-muted-foreground">Requirements: MFA Department of Consular Affairs, “Photo Requirements for Chinese Visa Application” (2016).</p>
          </div>
        </ToolCard>
        <ToolCard title="Create" step={3}>
          <Button className="w-full" size="lg" disabled={!file || busy}
            onClick={() => file && cv.start(file, profile)}>
            {cv.status === 'processing' && <Spinner />}
            {result ? 'Process again from scratch' : 'Create China Visa Photo'}
          </Button>
          {cv.error && (
            <Alert variant="destructive" className="mt-3 border-destructive/30 bg-destructive/5">
              <AlertDescription className="text-destructive">{cv.error}</AlertDescription>
            </Alert>
          )}
          <p className="mt-2 text-[11px] text-muted-foreground">
            Photos are processed in memory and not stored. Faces are never retouched, reshaped or generated.
          </p>
        </ToolCard>
      </div>

      <div className="lg:col-span-2 space-y-4">
        {!result && cv.status !== 'processing' && (
          <div className="rounded-xl border-2 border-dashed bg-card p-6 sm:p-12 flex flex-col items-center justify-center text-center min-h-48 sm:min-h-96">
            <h3 className="text-base font-semibold text-muted-foreground">Your China visa photo will appear here</h3>
            <p className="mt-1 text-sm text-muted-foreground/70">Every automatic correction is listed and can be undone.</p>
          </div>
        )}

        {cv.status === 'processing' && (
          <div className="rounded-xl bg-card p-6 ring-1 ring-foreground/10 sm:p-12 flex flex-col items-center justify-center min-h-48 sm:min-h-96 space-y-3">
            <Spinner className="size-10 text-primary" />
            <p className="font-semibold text-foreground">Analysing your photo…</p>
            <p className="text-xs text-muted-foreground">Face and pose, tilt, background, lighting, then the final file is measured.</p>
          </div>
        )}

        {result && cv.status !== 'processing' && (
          <>
            <DecisionBanner decision={result.decision} summary={result.summary} advice={result.retake_advice} />

            <ToolCard title="Original and processed">
              <SideBySide original={result.original_preview} processed={result.processed_image} mask={result.mask_preview}
                guides={result.guides} width={size[0]} height={size[1]} busy={busy} />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm" disabled={!cv.canUndo || busy || !file} onClick={() => file && cv.undo(file, profile)}><Undo2Icon /> Undo</Button>
                <Button variant="outline" size="sm" disabled={!cv.canRedo || busy || !file} onClick={() => file && cv.redo(file, profile)}><Redo2Icon /> Redo</Button>
                <Button variant="ghost" size="sm" disabled={busy || !file} onClick={() => file && cv.resetToAuto(file, profile)}>Reset to automatic</Button>
                {cv.status === 'rendering' && <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><Spinner /> Updating…</span>}
              </div>
            </ToolCard>

            <div className="grid gap-4 lg:grid-cols-2">
              <ToolCard title="Corrections">
                <CorrectionsPanel corrections={result.corrections} overrides={cv.overrides} disabled={busy || !file}
                  onChange={(next) => file && cv.apply(file, profile, next)} />
              </ToolCard>
              <div className="space-y-4">
                {result.processed_image && (
                  <ToolCard title="Download">
                    <div className="space-y-2">
                      {result.output && (
                        <p className="text-xs text-muted-foreground">
                          {result.output.width}×{result.output.height}px · {formatFileSize(result.output.file_size_kb)} · JPEG · {result.output.dpi ?? '—'} dpi
                        </p>
                      )}
                      <Button className="w-full" size="lg" onClick={download} disabled={busy}><DownloadIcon /> Download photo</Button>
                      {result.decision !== 'pass' && (
                        <p className="text-[11px] text-amber-700">Review the warnings before submitting this photo.</p>
                      )}
                    </div>
                  </ToolCard>
                )}
                <ToolCard title="Requirement checks">
                  <ChecksPanel checks={result.checks} />
                  <p className="mt-3 text-[10px] text-muted-foreground">
                    Spec {result.spec.id} v{result.spec.version} ({result.spec.source.edition}). “Provisional” marks thresholds PhotoGen uses to
                    judge qualitative rules. Passing these checks does not guarantee acceptance by the consulate.
                  </p>
                </ToolCard>
              </div>
            </div>

            {result.profile === 'paper' && processedUrl && (
              <ToolCard title="Print Sheet">
                <PrintSheet imageSrc={processedUrl} spec={PAPER_SPEC} />
              </ToolCard>
            )}
          </>
        )}
      </div>
    </div>
  )
}
