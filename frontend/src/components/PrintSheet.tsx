'use client'

import { useMemo, useState } from 'react'
import type { PhotoSpec } from '@/lib/types'
import { PAPER_SIZES, computePrintSheetLayout, renderPrintSheet } from '@/lib/printSheet'
import { DownloadIcon } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

interface PrintSheetProps {
  imageSrc: string
  spec: PhotoSpec
  filter?: string
}

export default function PrintSheet({ imageSrc, spec, filter }: PrintSheetProps) {
  const [paperId, setPaperId] = useState(PAPER_SIZES[0].id)
  const [downloading, setDownloading] = useState(false)

  const paper = PAPER_SIZES.find((p) => p.id === paperId) || PAPER_SIZES[0]
  const layout = useMemo(
    () => computePrintSheetLayout(paper, spec.dimensions.width_mm, spec.dimensions.height_mm),
    [paper, spec.dimensions.width_mm, spec.dimensions.height_mm]
  )

  async function handleDownload() {
    setDownloading(true)
    try {
      const dataUrl = await renderPrintSheet(imageSrc, paper, layout, spec.dimensions.dpi)
      const link = document.createElement('a')
      link.href = dataUrl
      link.download = `print-sheet-${paper.id}.jpg`
      link.click()
    } finally {
      setDownloading(false)
    }
  }

  const previewAspect = paper.width_mm / paper.height_mm

  return (
    <div className="space-y-3">
      <ToggleGroup type="single" variant="outline" size="sm" spacing={2} value={paperId}
        onValueChange={(v) => v && setPaperId(v)} className="flex-wrap">
        {PAPER_SIZES.map((p) => (
          <ToggleGroupItem key={p.id} value={p.id}
            className="text-xs data-[state=on]:border-primary data-[state=on]:bg-primary/10 data-[state=on]:text-primary">
            {p.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {layout.count === 0 ? (
        <Alert className="border-amber-200 bg-amber-50 text-amber-800">
          <AlertDescription className="text-amber-800">This photo doesn&apos;t fit on the selected paper size.</AlertDescription>
        </Alert>
      ) : (
        <>
          <div
            className="mx-auto rounded-lg border bg-muted p-2"
            style={{ aspectRatio: previewAspect, maxWidth: previewAspect >= 1 ? '100%' : 260 }}
          >
            <div
              className="relative w-full h-full bg-white shadow-sm rounded overflow-hidden"
              style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${layout.cols}, 1fr)`,
                gridTemplateRows: `repeat(${layout.rows}, 1fr)`,
                gap: `${(layout.gutterMm / paper.height_mm) * 100}% ${(layout.gutterMm / paper.width_mm) * 100}%`,
                padding: `${(layout.offsetYMm / paper.height_mm) * 100}% ${(layout.offsetXMm / paper.width_mm) * 100}%`,
              }}
            >
              {Array.from({ length: layout.count }).map((_, i) => (
                <div key={i} className="overflow-hidden border border-dashed border-foreground/20">
                  <img
                    src={imageSrc}
                    alt={`Copy ${i + 1}`}
                    className="w-full h-full object-cover"
                    style={{ filter }}
                  />
                </div>
              ))}
            </div>
          </div>

          <p className="text-center text-[11px] text-muted-foreground">
            {layout.count} photo{layout.count === 1 ? '' : 's'} ({layout.cols}x{layout.rows}) on {paper.label}
          </p>

          <Button onClick={handleDownload} disabled={downloading} className="w-full" size="lg" variant="secondary">
            {downloading ? <Spinner /> : <DownloadIcon />}
            Download Print Sheet
          </Button>
        </>
      )}
    </div>
  )
}
