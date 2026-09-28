'use client'

import { useState } from 'react'
import type { Check, CheckStatus } from '@/lib/chinaVisa'

const GROUPS: { id: Check['group']; label: string }[] = [
  { id: 'file', label: 'File' },
  { id: 'geometry', label: 'Size & position' },
  { id: 'face', label: 'Face & expression' },
  { id: 'pose', label: 'Head pose' },
  { id: 'background', label: 'Background' },
  { id: 'lighting', label: 'Lighting & quality' },
  { id: 'checklist', label: 'Please confirm yourself' },
]

const ICON: Record<CheckStatus, string> = { pass: '✓', warn: '!', fail: '✕', unverifiable: '?' }
const COLOR: Record<CheckStatus, string> = {
  pass: 'bg-green-100 text-green-700',
  warn: 'bg-amber-100 text-amber-700',
  fail: 'bg-red-100 text-red-700',
  unverifiable: 'bg-gray-100 text-gray-500',
}

function CheckRow({ c }: { c: Check }) {
  return (
    <li className="flex gap-2 py-1.5">
      <span className={`mt-0.5 h-4 w-4 shrink-0 rounded-full text-[10px] font-bold flex items-center justify-center ${COLOR[c.status]}`}>{ICON[c.status]}</span>
      <div className="min-w-0">
        <p className="text-xs text-gray-800">
          {c.label}
          {c.basis === 'provisional' && c.group !== 'checklist' && (
            <span title="Threshold chosen by PhotoGen to evaluate a qualitative MFA rule; not an official number." className="ml-1.5 rounded bg-gray-100 px-1 py-px text-[9px] uppercase tracking-wide text-gray-500">provisional</span>
          )}
          {c.group !== 'checklist' && (
            <span className="ml-1.5 text-[9px] uppercase tracking-wide text-gray-400">{c.stage === 'output' ? 'final file' : 'original'}</span>
          )}
        </p>
        <p className="text-[11px] text-gray-500">{c.message}</p>
        {c.expected && c.status !== 'unverifiable' && (
          <p className="text-[10px] text-gray-400">Required: {c.expected}{c.measured !== null && c.measured !== undefined ? ` · measured: ${c.measured}${c.unit ?? ''}` : ''}</p>
        )}
      </div>
    </li>
  )
}

export default function ChecksPanel({ checks }: { checks: Check[] }) {
  const [showPassed, setShowPassed] = useState(false)
  const counts = checks.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.status]: (acc[c.status] || 0) + 1 }), {})

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">
          {counts.fail || 0} failed · {counts.warn || 0} warnings · {counts.pass || 0} passed
        </span>
        <label className="flex items-center gap-1.5 text-gray-500">
          <input type="checkbox" checked={showPassed} onChange={(e) => setShowPassed(e.target.checked)} /> Show passed
        </label>
      </div>
      {GROUPS.map((g) => {
        const items = checks.filter((c) => c.group === g.id && (showPassed || c.status !== 'pass'))
        if (!items.length) return null
        return (
          <div key={g.id}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{g.label}</p>
            <ul className="divide-y divide-gray-50">
              {items.map((c) => <CheckRow key={c.id} c={c} />)}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
