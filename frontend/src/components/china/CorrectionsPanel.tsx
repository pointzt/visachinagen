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
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldSeparator } from '@/components/ui/field'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

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

function SwitchField({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled: boolean; label: string }) {
  const id = useId()
  return (
    <Field orientation="horizontal" className="w-auto">
      <Switch id={id} checked={checked} disabled={disabled} onCheckedChange={onChange} />
      <FieldLabel htmlFor={id} className="font-normal">{label}</FieldLabel>
    </Field>
  )
}

function ModePicker({ value, disabled, onChange }: { value: Mode; disabled: boolean; onChange: (m: Mode) => void }) {
  return (
    <ToggleGroup type="single" variant="outline" size="sm" spacing={0} value={value} disabled={disabled}
      onValueChange={(v) => v && onChange(v as Mode)} aria-label="Correction mode">
      {MODES.map((m) => <ToggleGroupItem key={m.id} value={m.id} className="px-3 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:hover:bg-primary/90 data-[state=on]:hover:text-primary-foreground">{m.label}</ToggleGroupItem>)}
    </ToggleGroup>
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
  const id = useId()
  return (
    <Field className="gap-2">
      <div className="flex items-center justify-between">
        <FieldLabel htmlFor={id} className="font-normal">{label}</FieldLabel>
        <span className="text-sm tabular-nums text-muted-foreground">{format(shown)}</span>
      </div>
      <Slider id={id} min={min} max={max} step={step} value={[shown]} disabled={disabled} aria-label={label}
        onValueChange={([v]) => setDraft(v)}
        onValueCommit={([v]) => {
          if (v !== value) onCommit(v)
          setDraft(null)
        }} />
    </Field>
  )
}

function Section({ title, applied, children }: { title: string; applied: boolean; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        <Badge variant={applied ? 'secondary' : 'outline'}>{applied ? 'Applied' : 'Not applied'}</Badge>
      </div>
      {children}
    </section>
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
    <FieldGroup className="gap-6">
      {rot && (
        <Section title={`Straighten (${rot.angle_deg >= 0 ? '+' : ''}${rot.angle_deg.toFixed(1)}°)`} applied={rot.applied}>
          <FieldDescription>
            <span className="font-medium text-foreground">{TILT_LABEL[rot.classification]}</span> · confidence {Math.round(rot.confidence * 100)}%. {rot.reason}
          </FieldDescription>
          {rot.suggested && !rot.applied && (
            <Button variant="secondary" size="sm" className="w-fit" disabled={disabled}
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
          <FieldDescription className="text-xs">Rotation turns the whole photo rigidly. Facial features are never warped.</FieldDescription>
        </Section>
      )}

      {bg && <FieldSeparator />}
      {bg && (
        <Section title="White background" applied={bg.applied}>
          <FieldDescription>{bg.reason}</FieldDescription>
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <SwitchField label="Replace background" checked={overrides.replace_background} disabled={disabled}
              onChange={(v) => set({ replace_background: v })} />
            <SwitchField label="Refine hair edges" checked={overrides.edge_refine} disabled={disabled || !overrides.replace_background}
              onChange={(v) => set({ edge_refine: v })} />
          </div>
        </Section>
      )}

      {light && <FieldSeparator />}
      {light && (
        <Section title="Exposure & contrast" applied={light.applied}>
          <FieldDescription>{light.reason}</FieldDescription>
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
          <FieldDescription className="text-xs">Only global brightness and contrast. No smoothing, reshaping or retouching.</FieldDescription>
        </Section>
      )}

      {crop && <FieldSeparator />}
      {crop && (
        <Section title="Crop & position" applied>
          <FieldDescription>{crop.reason}</FieldDescription>
          <CommitSlider label="Zoom" value={overrides.crop.scale} min={0.9} max={1.1} step={0.005} disabled={disabled}
            format={(v) => `${Math.round(v * 100)}%`} onCommit={(v) => setCrop({ scale: v })} />
          <CommitSlider label="Move up / down" value={overrides.crop.offset_y} min={-0.08} max={0.08} step={0.0025} disabled={disabled}
            format={(v) => `${v > 0 ? '↓' : v < 0 ? '↑' : ''}${Math.abs(v * 100).toFixed(1)}%`} onCommit={(v) => setCrop({ offset_y: v })} />
          <CommitSlider label="Move left / right" value={overrides.crop.offset_x} min={-0.08} max={0.08} step={0.0025} disabled={disabled}
            format={(v) => `${v > 0 ? '→' : v < 0 ? '←' : ''}${Math.abs(v * 100).toFixed(1)}%`} onCommit={(v) => setCrop({ offset_x: v })} />
          <FieldDescription className="text-xs">Every adjustment is re-validated against the MFA rules.</FieldDescription>
        </Section>
      )}
    </FieldGroup>
  )
}
