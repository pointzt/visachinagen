import type { Metadata } from 'next'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { SITE_NAME } from '@/lib/site'

export const metadata: Metadata = {
  title: 'Offline',
  robots: { index: false, follow: false },
}

export default function Offline() {
  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <Empty>
        <EmptyHeader>
          <EmptyMedia>
            <img src="/icons/icon-192.png" alt={SITE_NAME} className="size-16 rounded-2xl" />
          </EmptyMedia>
          <EmptyTitle>You are offline</EmptyTitle>
          <EmptyDescription>
            {SITE_NAME} needs an internet connection to check and correct your photo. Reconnect and try again.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button asChild>
            {/* A full page load, not client navigation, so the request goes back through the network. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/">Try again</a>
          </Button>
        </EmptyContent>
      </Empty>
    </main>
  )
}
