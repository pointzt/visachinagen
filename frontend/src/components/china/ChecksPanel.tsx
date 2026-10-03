'use client'

import { useId, useState } from 'react'
import { CircleCheckIcon, CircleHelpIcon, CircleXIcon, TriangleAlertIcon, type LucideIcon } from 'lucide-react'
import type { Check, CheckStatus } from '@/lib/chinaVisa'
import { SITE_NAME } from '@/lib/site'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Field, FieldLabel } from '@/components/ui/field'
import { Switch } from '@/components/ui/switch'
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
  pass: { icon: CircleCheckIcon, className: 'text-emerald-600 dark:text-emerald-400' },
  warn: { icon: TriangleAlertIcon, className: 'text-amber-600 dark:text-amber-400' },
  fail: { icon: CircleXIcon, className: 'text-destructive' },
  unverifiable: { icon: CircleHelpIcon, className: 'text-muted-foreground' },
}

function CheckRow({ c }: { c: Check }) {
  const { icon: Icon, className } = STATUS[c.status]
  return (
    <li className="flex gap-3 py-3">
      <Icon className={cn('mt-0.5 size-4 shrink-0', className)} aria-label={c.status} />
      <div className="min-w-0 space-y-1">
        <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium leading-none">
          {c.label}
          {c.basis === 'provisional' && c.group !== 'checklist' && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline" className="font-normal text-muted-foreground">provisional</Badge>
              </TooltipTrigger>
              <TooltipContent>Threshold chosen by {SITE_NAME} to evaluate a qualitative MFA rule; not an official number.</TooltipContent>
            </Tooltip>
          )}
          {c.group !== 'checklist' && (
            <Badge variant="ghost" className="font-normal text-muted-foreground">{c.stage === 'output' ? 'final file' : 'original'}</Badge>
          )}
        </p>
        <p className="text-sm text-muted-foreground">{c.message}</p>
        {c.expected && c.status !== 'unverifiable' && (
          <p className="text-xs text-muted-foreground">Required: {c.expected}{c.measured !== null && c.measured !== undefined ? ` · measured: ${c.measured}${c.unit ?? ''}` : ''}</p>
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
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant={counts.fail ? 'destructive' : 'outline'}>{counts.fail || 0} failed</Badge>
          <Badge variant="outline">{counts.warn || 0} warnings</Badge>
          <Badge variant="outline">{counts.pass || 0} passed</Badge>
        </div>
        <Field orientation="horizontal" className="w-auto">
          <Switch id={id} checked={showPassed} onCheckedChange={setShowPassed} />
          <FieldLabel htmlFor={id} className="font-normal">Show passed</FieldLabel>
        </Field>
      </div>
      {GROUPS.map((g) => {
        const items = checks.filter((c) => c.group === g.id && (showPassed || c.status !== 'pass'))
        if (!items.length) return null
        return (
          <div key={g.id}>
            <h4 className="text-xs font-medium text-muted-foreground">{g.label}</h4>
            <ul className="divide-y">
              {items.map((c) => <CheckRow key={c.id} c={c} />)}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
