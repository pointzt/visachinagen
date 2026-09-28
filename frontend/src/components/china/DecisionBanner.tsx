'use client'

import type { Decision } from '@/lib/chinaVisa'

const STYLES: Record<Decision, { box: string; title: string; icon: string; heading: string }> = {
  pass: { box: 'bg-green-50 border-green-200', title: 'text-green-800', icon: '✅', heading: 'Meets the checked requirements' },
  review: { box: 'bg-amber-50 border-amber-200', title: 'text-amber-800', icon: '⚠️', heading: 'Review before using' },
  retake: { box: 'bg-red-50 border-red-200', title: 'text-red-800', icon: '📷', heading: 'Retake recommended' },
}

export default function DecisionBanner({ decision, summary, advice }: { decision: Decision; summary: string; advice: string[] }) {
  const s = STYLES[decision]
  return (
    <div className={`rounded-xl border p-3 sm:p-4 ${s.box}`}>
      <div className="flex items-start gap-2.5">
        <span className="text-lg leading-none">{s.icon}</span>
        <div className="space-y-1.5 min-w-0">
          <p className={`font-semibold text-sm ${s.title}`}>{s.heading}</p>
          <p className="text-xs text-gray-600">{summary}</p>
          {advice.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-700 mt-2">How to get a better photo:</p>
              <ul className="mt-1 space-y-1">
                {advice.map((a) => (
                  <li key={a} className="text-xs text-gray-600 flex gap-1.5"><span className="shrink-0">•</span>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
