'use client'

import { useState } from 'react'
import PhotoTool from '@/components/PhotoTool'
import ChinaVisaTool from '@/components/china/ChinaVisaTool'

const TABS = [
  { id: 'passport', label: 'Passport & visa photos' },
  { id: 'china', label: '🇨🇳 China visa (MFA 2016 checks)' },
] as const

type Tab = (typeof TABS)[number]['id']

export default function ToolSwitcher() {
  const [tab, setTab] = useState<Tab>('passport')
  return (
    <div className="space-y-4">
      <div role="tablist" className="flex gap-1 rounded-xl border border-gray-200 bg-white p-1 w-full sm:w-fit mx-auto">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`flex-1 sm:flex-none rounded-lg px-3 py-1.5 text-xs sm:text-sm font-medium transition-colors ${tab === t.id ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'passport' ? <PhotoTool /> : <ChinaVisaTool />}
    </div>
  )
}
