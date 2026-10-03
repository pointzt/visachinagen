import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Offline',
  robots: { index: false, follow: false },
}

export default function Offline() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4 px-4 text-center">
      <img src="/icons/icon-192.png" alt="PhotoGen" className="h-16 w-16 rounded-2xl" />
      <h1 className="text-lg font-bold text-foreground">You are offline</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        PhotoGen needs an internet connection to check and correct your photo. Reconnect and try again.
      </p>
      <a href="/" className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
        Try again
      </a>
    </main>
  )
}
