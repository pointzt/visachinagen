'use client'

import { useId, useState } from 'react'
import { DownloadIcon, ImageIcon, Redo2Icon, RotateCcwIcon, Undo2Icon } from 'lucide-react'
import { useImageUpload } from '@/hooks/useImageUpload'
import { useChinaVisa } from '@/hooks/useChinaVisa'
import { base64ToBlob, type Profile } from '@/lib/chinaVisa'
import { useObjectUrl } from '@/hooks/useObjectUrl'
import { formatFileSize } from '@/lib/utils'
import type { PhotoSpec } from '@/lib/types'
import PhotoUploader from '@/components/PhotoUploader'
import PrintSheet from '@/components/PrintSheet'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Field, FieldContent, FieldDescription, FieldLabel, FieldLegend, FieldSet, FieldTitle } from '@/components/ui/field'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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

  const issues = result ? result.checks.filter((c) => c.group !== 'checklist' && (c.status === 'fail' || c.status === 'warn')).length : 0

  return (
    <div className="grid items-start gap-6 lg:grid-cols-3">
      <Card className="lg:sticky lg:top-20">
        <CardHeader>
          <CardTitle>Your photo</CardTitle>
          <CardDescription>A front-facing photo against a plain background works best.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <PhotoUploader onFileSelect={(f) => { cv.reset(); return load(f) }} previewUrl={previewUrl} error={uploadError} onClear={handleClear} />
          <Separator />
          <FieldSet>
            <FieldLegend variant="label">Photo type</FieldLegend>
            <FieldDescription>MFA Department of Consular Affairs, “Photo Requirements for Chinese Visa Application” (2016).</FieldDescription>
            <RadioGroup value={profile} onValueChange={(v) => changeProfile(v as Profile)} disabled={busy}>
              {PROFILES.map((p) => (
                <FieldLabel key={p.id} htmlFor={`${radioId}-${p.id}`}>
                  <Field orientation="horizontal">
                    <FieldContent>
                      <FieldTitle>{p.label}</FieldTitle>
                      <FieldDescription>{p.detail}</FieldDescription>
                    </FieldContent>
                    <RadioGroupItem id={`${radioId}-${p.id}`} value={p.id} />
                  </Field>
                </FieldLabel>
              ))}
            </RadioGroup>
          </FieldSet>
        </CardContent>
        <CardFooter className="flex-col items-stretch gap-3">
          <Button size="lg" disabled={!file || busy} onClick={() => file && cv.start(file, profile)}>
            {cv.status === 'processing' && <Spinner />}
            {result ? 'Process again from scratch' : 'Create China visa photo'}
          </Button>
          {cv.error && (
            <Alert variant="destructive">
              <AlertDescription>{cv.error}</AlertDescription>
            </Alert>
          )}
          <p className="text-xs text-muted-foreground">
            Photos are processed in memory and not stored. Faces are never retouched, reshaped or generated.
          </p>
        </CardFooter>
      </Card>

      <div className="space-y-6 lg:col-span-2">
        {!result && cv.status !== 'processing' && (
          <Empty className="min-h-96 border border-dashed">
            <EmptyHeader>
              <EmptyMedia variant="icon"><ImageIcon /></EmptyMedia>
              <EmptyTitle>Your China visa photo will appear here</EmptyTitle>
              <EmptyDescription>Upload a photo and press Create. Every automatic correction is listed and can be undone.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}

        {cv.status === 'processing' && (
          <Empty className="min-h-96 border">
            <EmptyHeader>
              <EmptyMedia variant="icon"><Spinner /></EmptyMedia>
              <EmptyTitle>Analysing your photo…</EmptyTitle>
              <EmptyDescription>Face and pose, tilt, background and lighting are checked, then the final file is measured.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}

        {result && cv.status !== 'processing' && (
          <>
            <DecisionBanner decision={result.decision} summary={result.summary} advice={result.retake_advice} />

            <Card>
              <CardHeader>
                <CardTitle>Original and processed</CardTitle>
                {result.output && (
                  <CardDescription>
                    {result.output.width}×{result.output.height} px · {formatFileSize(result.output.file_size_kb)} · JPEG · {result.output.dpi ?? '—'} dpi
                  </CardDescription>
                )}
                <CardAction>
                  <ButtonGroup>
                    <Button variant="outline" size="icon-sm" aria-label="Undo" disabled={!cv.canUndo || busy || !file} onClick={() => file && cv.undo(file, profile)}><Undo2Icon /></Button>
                    <Button variant="outline" size="icon-sm" aria-label="Redo" disabled={!cv.canRedo || busy || !file} onClick={() => file && cv.redo(file, profile)}><Redo2Icon /></Button>
                    <Button variant="outline" size="sm" disabled={busy || !file} onClick={() => file && cv.resetToAuto(file, profile)}><RotateCcwIcon /> Reset</Button>
                  </ButtonGroup>
                </CardAction>
              </CardHeader>
              <CardContent>
                <SideBySide original={result.original_preview} processed={result.processed_image} mask={result.mask_preview}
                  guides={result.guides} width={size[0]} height={size[1]} busy={busy} />
              </CardContent>
              {result.processed_image && (
                <CardFooter className="flex-col items-stretch gap-2 sm:flex-row sm:items-center">
                  <p className="text-sm text-muted-foreground sm:mr-auto">
                    {cv.status === 'rendering' ? <span className="flex items-center gap-2"><Spinner /> Updating…</span>
                      : result.decision !== 'pass' ? 'Review the warnings before submitting this photo.' : 'Ready to submit.'}
                  </p>
                  <Button size="lg" onClick={download} disabled={busy}><DownloadIcon /> Download photo</Button>
                </CardFooter>
              )}
            </Card>

            <Tabs defaultValue="corrections">
              <TabsList>
                <TabsTrigger value="corrections">Corrections</TabsTrigger>
                <TabsTrigger value="checks">
                  Requirement checks
                  {issues > 0 && <Badge variant="secondary" className="h-5 min-w-5 rounded-full px-1 tabular-nums">{issues}</Badge>}
                </TabsTrigger>
              </TabsList>
              <TabsContent value="corrections">
                <Card>
                  <CardHeader>
                    <CardTitle>Corrections</CardTitle>
                    <CardDescription>Each automatic change can be turned off or adjusted. Every change is re-validated.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <CorrectionsPanel corrections={result.corrections} overrides={cv.overrides} disabled={busy || !file}
                      onChange={(next) => file && cv.apply(file, profile, next)} />
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="checks">
                <Card>
                  <CardHeader>
                    <CardTitle>Requirement checks</CardTitle>
                    <CardDescription>
                      Spec {result.spec.id} v{result.spec.version} ({result.spec.source.edition}). Passing these checks does not guarantee acceptance by the consulate.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ChecksPanel checks={result.checks} />
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            {result.profile === 'paper' && processedUrl && (
              <Card>
                <CardHeader>
                  <CardTitle>Print sheet</CardTitle>
                  <CardDescription>Several 33×48 mm copies on one sheet, ready to print.</CardDescription>
                </CardHeader>
                <CardContent>
                  <PrintSheet imageSrc={processedUrl} spec={PAPER_SPEC} />
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  )
}
