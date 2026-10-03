import type { MetadataRoute } from 'next'
import { SITE_NAME, SITE_SHORT_NAME } from '@/lib/site'

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/',
    name: SITE_NAME,
    short_name: SITE_SHORT_NAME,
    description:
      'Create a China visa photo checked against the Chinese MFA 2016 photo requirements. Free, no signup, no watermark.',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    orientation: 'portrait',
    background_color: '#ffffff',
    theme_color: '#ffffff',
    categories: ['photo', 'utilities', 'travel'],
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}
