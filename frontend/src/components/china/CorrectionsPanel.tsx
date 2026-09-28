'use client'

import { useState } from 'react'
import type {
  BackgroundCorrection,
  Correction,
  CropCorrection,
  LightingCorrection,
  Overrides,
  RotationCorrection,
} from '@/lib/chinaVisa'

interface CorrectionsPanelProps {
  corrections: Correction[]
  overrides: Overrides
  disabled: boolean
  onChange: (next: Overrides) => void
}

const TILT_LABEL: Record<RotationCorrection['classification'], string> = {
  level: 'Level',
  camera_tilt: 'Camera tilt',
  head_tilt: 'Head tilt',
  ambiguous: 'Uncertain',
}

function Toggle({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled: boolean; label: string }) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-gray-600">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

/** A range input that only commits on release, so each drag is one undo step and one render. */
function CommitSlider({ label, value, min, max, step, format, disabled, onCommit }: {
  label: string; value: number; min: number; max: number; step: number
  format: (v: number) => string; disabled: boolean; onCommit: (v: number) => void
}) {
  // Only holds a value while the user is dragging; otherwise the committed value is shown.
  const [draft, setDraft] = useState<number | null>(null)
  const shown = draft ?? value
  const commit = () => {
    if (draft !== null && draft !== value) onCommit(draft)
    setDraft(null)
  }
  return (
    <div>
      <div className="flex justify-between text-[11px] mb-1">
        <span className="text-gray-500">{label}</span>
        <span className="text-gray-400 tabular-nums">{format(shown)}</span>
      </div>
      <input type="range" className="w-full" min={min} max={max} step={step} value={shown} disabled={disabled}
        onChange={(e) => setDraft(Number(e.target.value))} onMouseUp={commit} onTouchEnd={commit} onKeyUp={commit} />
    </div>
  )
}

function Section({ title, applied, children }: { title: string; applied: boolean; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-100 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-gray-800">{title}</p>
        <span className={`text-[10px] rounded-full px-2 py-0.5 ${applied ? 'bg-primary-50 text-primary-700' : 'bg-gray-100 text-gray-500'}`}>
          {applied ? 'Applied' : 'Not applied'}
        </span>
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
          <p className="text-[11px] text-gray-500">
            <span className="font-medium text-gray-600">{TILT_LABEL[rot.classification]}</span> · confidence {Math.round(rot.confidence * 100)}% — {rot.reason}
          </p>
          <p className="text-[10px] text-gray-400">Rotation turns the whole photo rigidly. Facial features are never warped.</p>
          {rot.suggested && !rot.applied && (
            <button type="button" disabled={disabled}
              onClick={() => set({ rotation: 'manual', rotation_deg: rot.suggested_angle_deg })}
              className="w-full rounded-md border border-primary-200 bg-primary-50 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-100">
              Straighten by {rot.suggested_angle_deg.toFixed(1)}° (suggested)
            </button>
          )}
          <div className="flex gap-3">
            {(['auto', 'off', 'manual'] as const).map((m) => (
              <label key={m} className="flex items-center gap-1 text-xs text-gray-600">
                <input type="radio" name="rotation" checked={overrides.rotation === m} disabled={disabled}
                  onChange={() => set({ rotation: m, rotation_deg: m === 'manual' ? (rot.applied ? rot.angle_deg : rot.suggested_angle_deg) : 0 })} />
                {m === 'auto' ? 'Automatic' : m === 'off' ? 'None' : 'Manual'}
              </label>
            ))}
          </div>
          {overrides.rotation === 'manual' && (
            <CommitSlider label="Angle" value={overrides.rotation_deg} min={-15} max={15} step={0.1} disabled={disabled}
              format={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}°`} onCommit={(v) => set({ rotation_deg: v })} />
          )}
        </Section>
      )}

      {bg && (
        <Section title="White background" applied={bg.applied}>
          <p className="text-[11px] text-gray-500">{bg.reason}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <Toggle label="Replace background" checked={overrides.replace_background} disabled={disabled}
              onChange={(v) => set({ replace_background: v })} />
            <Toggle label="Refine hair edges" checked={overrides.edge_refine} disabled={disabled || !overrides.replace_background}
              onChange={(v) => set({ edge_refine: v })} />
          </div>
        </Section>
      )}

      {light && (
        <Section title="Exposure & contrast" applied={light.applied}>
          <p className="text-[11px] text-gray-500">{light.reason}</p>
          <p className="text-[10px] text-gray-400">Only global brightness/contrast. No smoothing, reshaping or retouching.</p>
          <div className="flex gap-3">
            {(['auto', 'off', 'manual'] as const).map((m) => (
              <label key={m} className="flex items-center gap-1 text-xs text-gray-600">
                <input type="radio" name="lighting" checked={overrides.lighting === m} disabled={disabled}
                  onChange={() => set({ lighting: m, exposure_ev: m === 'manual' ? light.exposure_ev : 0, contrast: m === 'manual' ? light.contrast : 0 })} />
                {m === 'auto' ? 'Automatic' : m === 'off' ? 'None' : 'Manual'}
              </label>
            ))}
          </div>
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
          <p className="text-[11px] text-gray-500">{crop.reason}</p>
          <CommitSlider label="Zoom" value={overrides.crop.scale} min={0.9} max={1.1} step={0.005} disabled={disabled}
            format={(v) => `${Math.round(v * 100)}%`} onCommit={(v) => setCrop({ scale: v })} />
          <CommitSlider label="Move up / down" value={overrides.crop.offset_y} min={-0.08} max={0.08} step={0.0025} disabled={disabled}
            format={(v) => `${v > 0 ? '↓' : v < 0 ? '↑' : ''}${Math.abs(v * 100).toFixed(1)}%`} onCommit={(v) => setCrop({ offset_y: v })} />
          <CommitSlider label="Move left / right" value={overrides.crop.offset_x} min={-0.08} max={0.08} step={0.0025} disabled={disabled}
            format={(v) => `${v > 0 ? '→' : v < 0 ? '←' : ''}${Math.abs(v * 100).toFixed(1)}%`} onCommit={(v) => setCrop({ offset_x: v })} />
          <p className="text-[10px] text-gray-400">Every adjustment is re-validated against the MFA rules.</p>
        </Section>
      )}
    </div>
  )
}
