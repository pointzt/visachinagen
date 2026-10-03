import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { Inter } from 'next/font/google'
import './globals.css'
import { cn } from '@/lib/utils'
import { TooltipProvider } from '@/components/ui/tooltip'
import ServiceWorkerRegister from '@/components/ServiceWorkerRegister'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' })

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://photogen.io'

export const metadata: Metadata = {
  title: {
    default: 'PhotoGen - Free China Visa Photo Maker Online',
    template: '%s | PhotoGen',
  },
  description:
    'Create a China visa photo for free, checked against the Chinese MFA 2016 photo requirements. AI background removal, tilt and lighting correction, and 420×560 digital or 33×48 mm print output. No signup required, no watermark.',
  keywords: [
    'China visa photo',
    'Chinese visa photo maker',
    'China visa photo online',
    'China visa photo size',
    'China visa photo 33x48',
    'China visa photo 420x560',
    'China visa photo requirements',
    'free visa photo maker',
    'visa photo no watermark',
  ],
  openGraph: {
    title: 'PhotoGen - Free China Visa Photo Maker',
    description:
      'Create a compliant China visa photo instantly. Checked against the MFA 2016 requirements. 100% free, no signup.',
    url: SITE_URL,
    siteName: 'PhotoGen',
    type: 'website',
    locale: 'en_US',
    images: [
      {
        url: `${SITE_URL}/og-image.png`,
        width: 1200,
        height: 630,
        alt: 'PhotoGen - Free China Visa Photo Maker',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'PhotoGen - Free China Visa Photo Maker',
    description:
      'China visa photos for free. No signup, no watermark, no data stored.',
    images: [`${SITE_URL}/og-image.png`],
  },
  applicationName: 'PhotoGen',
  appleWebApp: { capable: true, title: 'PhotoGen', statusBarStyle: 'default' },
  formatDetection: { telephone: false },
  robots: { index: true, follow: true },
  alternates: { canonical: SITE_URL },
  metadataBase: new URL(SITE_URL),
}

export const viewport: Viewport = {
  themeColor: '#ffffff',
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
}

const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'WebApplication',
  name: 'PhotoGen',
  url: SITE_URL,
  description:
    'Free China visa photo maker built to the Chinese MFA 2016 photo requirements.',
  applicationCategory: 'PhotographyApplication',
  operatingSystem: 'Web',
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  featureList: [
    'AI background removal',
    'Face detection',
    'Automatic framing to the MFA 2016 China visa spec',
    'Tilt, lighting and background checks',
    'No watermark',
    'No signup required',
  ],
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn('font-sans', inter.variable)}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="antialiased">
        <TooltipProvider>{children}</TooltipProvider>
        <Analytics />
        <ServiceWorkerRegister />
      </body>
    </html>
  )
}
