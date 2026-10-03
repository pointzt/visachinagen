'use client'

import { CameraIcon, CircleCheckIcon, TriangleAlertIcon, type LucideIcon } from 'lucide-react'
import type { Decision } from '@/lib/chinaVisa'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const STYLES: Record<Decision, { className: string; icon: LucideIcon; heading: string }> = {
  pass: { className: 'border-green-200 bg-green-50 text-green-800', icon: CircleCheckIcon, heading: 'Meets the checked requirements' },
  review: { className: 'border-amber-200 bg-amber-50 text-amber-800', icon: TriangleAlertIcon, heading: 'Review before using' },
  retake: { className: 'border-red-200 bg-red-50 text-red-800', icon: CameraIcon, heading: 'Retake recommended' },
}

export default function DecisionBanner({ decision, summary, advice }: { decision: Decision; summary: string; advice: string[] }) {
  const { className, icon: Icon, heading } = STYLES[decision]
  return (
    <Alert className={cn('px-3 py-3 sm:px-4', className)}>
      <Icon />
      <AlertTitle className="font-semibold">{heading}</AlertTitle>
      <AlertDescription className="space-y-1.5 text-xs text-foreground/70">
        <p>{summary}</p>
        {advice.length > 0 && (
          <div>
            <p className="mt-2 font-medium text-foreground/80">How to get a better photo:</p>
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {advice.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </div>
        )}
      </AlertDescription>
    </Alert>
  )
}
