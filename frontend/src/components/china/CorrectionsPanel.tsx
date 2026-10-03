'use client'

import { useId, useState } from 'react'
import type {
  BackgroundCorrection,
  Correction,
  CropCorrection,
  LightingCorrection,
  Overrides,
  RotationCorrection,
} from '@/lib/chinaVisa'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Slider } from '@/components/ui/slider'

interface CorrectionsPanelProps {
  corrections: Correction[]
  overrides: Overrides
  disabled: boolean
  onChange: (next: Overrides) => void
}

type Mode = 'auto' | 'off' | 'manual'

const TILT_LABEL: Record<RotationCorrection['classification'], string> = {
  level: 'Level',
  camera_tilt: 'Camera tilt',
  head_tilt: 'Head tilt',
  ambiguous: 'Uncertain',
}

const MODES: { id: Mode; label: string }[] = [
  { id: 'auto', label: 'Automatic' },
  { id: 'off', label: 'None' },
  { id: 'manual', label: 'Manual' },
]

function Toggle({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled: boolean; label: string }) {
  const id = useId()
  return (
    <div className="flex items-center gap-1.5">
      <Checkbox id={id} checked={checked} disabled={disabled} onCheckedChange={(v) => onChange(v === true)} />
      <Label htmlFor={id} className="text-xs font-normal">{label}</Label>
    </div>
  )
}

function ModePicker({ value, disabled, onChange }: { value: Mode; disabled: boolean; onChange: (m: Mode) => void }) {
  const id = useId()
  return (
    <RadioGroup value={value} onValueChange={(v) => onChange(v as Mode)} disabled={disabled} className="flex gap-3">
      {MODES.map((m) => (
        <div key={m.id} className="flex items-center gap-1.5">
          <RadioGroupItem id={`${id}-${m.id}`} value={m.id} />
          <Label htmlFor={`${id}-${m.id}`} className="text-xs font-normal">{m.label}</Label>
        </div>
      ))}
    </RadioGroup>
  )
}

/** A slider that only commits on release, so each drag is one undo step and one render. */
function CommitSlider({ label, value, min, max, step, format, disabled, onCommit }: {
  label: string; value: number; min: number; max: number; step: number
  format: (v: number) => string; disabled: boolean; onCommit: (v: number) => void
}) {
  // Only holds a value while the user is dragging; otherwise the committed value is shown.
  const [draft, setDraft] = useState<number | null>(null)
  const shown = draft ?? value
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-[11px]">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">{format(shown)}</span>
      </div>
      <Slider min={min} max={max} step={step} value={[shown]} disabled={disabled} aria-label={label}
        onValueChange={([v]) => setDraft(v)}
        onValueCommit={([v]) => {
          if (v !== value) onCommit(v)
          setDraft(null)
        }} />
    </div>
  )
}

function Section({ title, applied, children }: { title: string; applied: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-2.5 rounded-lg border p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-foreground">{title}</p>
        <Badge variant={applied ? 'default' : 'secondary'} className="text-[10px]">
          {applied ? 'Applied' : 'Not applied'}
        </Badge>
      </div>
      {children}
    </div>
  )
}

export default function CorrectionsPanel({ corrections, overrides, disabled, onChange }: CorrectionsPanelProps) {
  const rot = corrections.find((c) => c.id === 'rotation') as RotationCorrection | undefined
  const bg = corrections.find((c) => c.id === 'background') as BackgroundCorrection | undefined
  const light = corrections.find((c) => c.id === 'lighting') as LightingCorrection | undefined
  const crop = corrections.find((c) => c.id === 'crop') as CropCorrection | undefined
  const set = (patch: Partial<Overrides>) => onChange({ ...overrides, ...patch })
  const setCrop = (patch: Partial<Overrides['crop']>) => set({ crop: { ...overrides.crop, ...patch } })

  return (
    <div className="space-y-3">
      {rot && (
        <Section title={`Straighten (${rot.angle_deg >= 0 ? '+' : ''}${rot.angle_deg.toFixed(1)}°)`} applied={rot.applied}>
          <p className="text-[11px] text-muted-foreground">
            <span className="font-medium text-foreground/80">{TILT_LABEL[rot.classification]}</span> · confidence {Math.round(rot.confidence * 100)}% — {rot.reason}
          </p>
          <p className="text-[10px] text-muted-foreground/80">Rotation turns the whole photo rigidly. Facial features are never warped.</p>
          {rot.suggested && !rot.applied && (
            <Button variant="outline" size="sm" className="w-full border-primary/30 text-primary" disabled={disabled}
              onClick={() => set({ rotation: 'manual', rotation_deg: rot.suggested_angle_deg })}>
              Straighten by {rot.suggested_angle_deg.toFixed(1)}° (suggested)
            </Button>
          )}
          <ModePicker value={overrides.rotation} disabled={disabled}
            onChange={(m) => set({ rotation: m, rotation_deg: m === 'manual' ? (rot.applied ? rot.angle_deg : rot.suggested_angle_deg) : 0 })} />
          {overrides.rotation === 'manual' && (
            <CommitSlider label="Angle" value={overrides.rotation_deg} min={-15} max={15} step={0.1} disabled={disabled}
              format={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}°`} onCommit={(v) => set({ rotation_deg: v })} />
          )}
        </Section>
      )}

      {bg && (
        <Section title="White background" applied={bg.applied}>
          <p className="text-[11px] text-muted-foreground">{bg.reason}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            <Toggle label="Replace background" checked={overrides.replace_background} disabled={disabled}
              onChange={(v) => set({ replace_background: v })} />
            <Toggle label="Refine hair edges" checked={overrides.edge_refine} disabled={disabled || !overrides.replace_background}
              onChange={(v) => set({ edge_refine: v })} />
          </div>
        </Section>
      )}

      {light && (
        <Section title="Exposure & contrast" applied={light.applied}>
          <p className="text-[11px] text-muted-foreground">{light.reason}</p>
          <p className="text-[10px] text-muted-foreground/80">Only global brightness/contrast. No smoothing, reshaping or retouching.</p>
          <ModePicker value={overrides.lighting} disabled={disabled}
            onChange={(m) => set({ lighting: m, exposure_ev: m === 'manual' ? light.exposure_ev : 0, contrast: m === 'manual' ? light.contrast : 0 })} />
          {overrides.lighting === 'manual' && (
            <>
              <CommitSlider label="Exposure" value={overrides.exposure_ev} min={-0.3} max={0.5} step={0.05} disabled={disabled}
                format={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)} EV`} onCommit={(v) => set({ exposure_ev: v })} />
              <CommitSlider label="Contrast" value={overrides.contrast} min={0} max={0.25} step={0.01} disabled={disabled}
                format={(v) => `+${Math.round(v * 100)}%`} onCommit={(v) => set({ contrast: v })} />
            </>
          )}
        </Section>
      )}

      {crop && (
        <Section title="Crop & position" applied>
          <p className="text-[11px] text-muted-foreground">{crop.reason}</p>
          <CommitSlider label="Zoom" value={overrides.crop.scale} min={0.9} max={1.1} step={0.005} disabled={disabled}
            format={(v) => `${Math.round(v * 100)}%`} onCommit={(v) => setCrop({ scale: v })} />
          <CommitSlider label="Move up / down" value={overrides.crop.offset_y} min={-0.08} max={0.08} step={0.0025} disabled={disabled}
            format={(v) => `${v > 0 ? '↓' : v < 0 ? '↑' : ''}${Math.abs(v * 100).toFixed(1)}%`} onCommit={(v) => setCrop({ offset_y: v })} />
          <CommitSlider label="Move left / right" value={overrides.crop.offset_x} min={-0.08} max={0.08} step={0.0025} disabled={disabled}
            format={(v) => `${v > 0 ? '→' : v < 0 ? '←' : ''}${Math.abs(v * 100).toFixed(1)}%`} onCommit={(v) => setCrop({ offset_x: v })} />
          <p className="text-[10px] text-muted-foreground/80">Every adjustment is re-validated against the MFA rules.</p>
        </Section>
      )}
    </div>
  )
}
