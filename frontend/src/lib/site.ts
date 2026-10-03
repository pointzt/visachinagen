export const SITE_NAME = 'China Visa Generator'
export const SITE_SHORT_NAME = 'China Visa'
export const REPO_URL = 'https://github.com/pointzt/visachinagen'

// NEXT_PUBLIC_SITE_URL wins; on Vercel the production domain is provided automatically.
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'http://localhost:3000')
