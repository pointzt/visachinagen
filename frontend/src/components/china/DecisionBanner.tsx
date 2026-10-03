'use client'

import { CameraIcon, CircleCheckIcon, TriangleAlertIcon, type LucideIcon } from 'lucide-react'
import type { Decision } from '@/lib/chinaVisa'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const STYLES: Record<Decision, { variant: 'default' | 'destructive'; icon: LucideIcon; iconClass?: string; heading: string }> = {
  pass: { variant: 'default', icon: CircleCheckIcon, iconClass: 'text-emerald-600 dark:text-emerald-400', heading: 'Meets the checked requirements' },
  review: { variant: 'default', icon: TriangleAlertIcon, iconClass: 'text-amber-600 dark:text-amber-400', heading: 'Review before using' },
  retake: { variant: 'destructive', icon: CameraIcon, heading: 'Retake recommended' },
}

export default function DecisionBanner({ decision, summary, advice }: { decision: Decision; summary: string; advice: string[] }) {
  const { variant, icon: Icon, iconClass, heading } = STYLES[decision]
  return (
    <Alert variant={variant}>
      <Icon className={cn(iconClass)} />
      <AlertTitle>{heading}</AlertTitle>
      <AlertDescription>
        <p>{summary}</p>
        {advice.length > 0 && (
          <ul className="mt-1 list-disc space-y-1 pl-4">
            {advice.map((a) => <li key={a}>{a}</li>)}
          </ul>
        )}
      </AlertDescription>
    </Alert>
  )
}
