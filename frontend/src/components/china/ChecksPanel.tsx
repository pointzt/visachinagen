'use client'

import { useId, useState } from 'react'
import { CheckIcon, CircleHelpIcon, TriangleAlertIcon, XIcon, type LucideIcon } from 'lucide-react'
import type { Check, CheckStatus } from '@/lib/chinaVisa'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

const GROUPS: { id: Check['group']; label: string }[] = [
  { id: 'file', label: 'File' },
  { id: 'geometry', label: 'Size & position' },
  { id: 'face', label: 'Face & expression' },
  { id: 'pose', label: 'Head pose' },
  { id: 'background', label: 'Background' },
  { id: 'lighting', label: 'Lighting & quality' },
  { id: 'checklist', label: 'Please confirm yourself' },
]

const STATUS: Record<CheckStatus, { icon: LucideIcon; className: string }> = {
  pass: { icon: CheckIcon, className: 'bg-green-100 text-green-700' },
  warn: { icon: TriangleAlertIcon, className: 'bg-amber-100 text-amber-700' },
  fail: { icon: XIcon, className: 'bg-red-100 text-red-700' },
  unverifiable: { icon: CircleHelpIcon, className: 'bg-muted text-muted-foreground' },
}

function CheckRow({ c }: { c: Check }) {
  const { icon: Icon, className } = STATUS[c.status]
  return (
    <li className="flex gap-2 py-2">
      <span className={cn('mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full', className)}>
        <Icon className="size-2.5" strokeWidth={3} />
      </span>
      <div className="min-w-0 space-y-0.5">
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-foreground">
          {c.label}
          {c.basis === 'provisional' && c.group !== 'checklist' && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline" className="h-4 px-1.5 text-[9px] uppercase tracking-wide text-muted-foreground">provisional</Badge>
              </TooltipTrigger>
              <TooltipContent>Threshold chosen by PhotoGen to evaluate a qualitative MFA rule; not an official number.</TooltipContent>
            </Tooltip>
          )}
          {c.group !== 'checklist' && (
            <span className="text-[9px] uppercase tracking-wide text-muted-foreground">{c.stage === 'output' ? 'final file' : 'original'}</span>
          )}
        </p>
        <p className="text-[11px] text-muted-foreground">{c.message}</p>
        {c.expected && c.status !== 'unverifiable' && (
          <p className="text-[10px] text-muted-foreground/80">Required: {c.expected}{c.measured !== null && c.measured !== undefined ? ` · measured: ${c.measured}${c.unit ?? ''}` : ''}</p>
        )}
      </div>
    </li>
  )
}

export default function ChecksPanel({ checks }: { checks: Check[] }) {
  const [showPassed, setShowPassed] = useState(false)
  const id = useId()
  const counts = checks.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.status]: (acc[c.status] || 0) + 1 }), {})

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {counts.fail || 0} failed · {counts.warn || 0} warnings · {counts.pass || 0} passed
        </span>
        <div className="flex items-center gap-1.5">
          <Checkbox id={id} checked={showPassed} onCheckedChange={(v) => setShowPassed(v === true)} />
          <Label htmlFor={id} className="text-xs font-normal text-muted-foreground">Show passed</Label>
        </div>
      </div>
      {GROUPS.map((g) => {
        const items = checks.filter((c) => c.group === g.id && (showPassed || c.status !== 'pass'))
        if (!items.length) return null
        return (
          <div key={g.id}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{g.label}</p>
            <ul className="divide-y">
              {items.map((c) => <CheckRow key={c.id} c={c} />)}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
