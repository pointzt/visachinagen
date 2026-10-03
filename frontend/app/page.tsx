import Link from 'next/link'
import ChinaVisaTool from '@/components/china/ChinaVisaTool'
import { ModeToggle } from '@/components/mode-toggle'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { REPO_URL, SITE_NAME } from '@/lib/site'

const STEPS = [
  { title: 'Upload Your Photo', desc: 'Take a photo with your phone or webcam against a plain background. Supports JPG, PNG, and HEIC.' },
  { title: 'Automatic Checks', desc: 'China Visa Generator checks head pose, tilt, lighting, background, and framing against the Chinese MFA 2016 photo requirements.' },
  { title: 'Review Corrections', desc: 'See the original and corrected photo side by side, toggle each correction, and fine-tune with manual sliders.' },
  { title: 'Download for Free', desc: 'Download the 420×560 digital photo for the online application, or a 33×48 mm print sheet. No watermark, no signup.' },
]

const FAQS = [
  { q: 'Is China Visa Generator really free?', a: 'Yes — 100% free with no watermarks, no signup, and unlimited usage. It is open-source software.' },
  { q: 'Is my photo stored on your servers?', a: 'No. Your photo is processed and returned immediately. We do not store any images or personal data.' },
  { q: 'What size is a China visa photo?', a: 'The digital photo for the online application is 420×560 px and 40–120 KB. A printed photo is 33×48 mm with a white background.' },
  { q: 'What if my photo fails a check?', a: 'China Visa Generator explains which requirement failed and whether it can be corrected automatically or needs a retake.' },
  { q: 'Do I need to remove the background myself?', a: 'No. China Visa Generator removes the background with AI and replaces it with the required plain white.' },
]

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}

export default function Home() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
          <Link href="/" className="flex items-center gap-2">
            <img src="/icons/icon-192.png" alt="" className="size-7 rounded-md" />
            <span className="font-semibold tracking-tight">{SITE_NAME}</span>
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <Button variant="ghost" size="icon" asChild>
              <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
                <GitHubIcon />
                <span className="sr-only">GitHub</span>
              </a>
            </Button>
            <ModeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:py-12">
        <section className="mb-8 flex flex-col items-center gap-3 text-center sm:mb-12">
          <Badge variant="secondary">Chinese MFA 2016 photo requirements</Badge>
          <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Create your China visa photo online for free
          </h1>
          <p className="max-w-xl text-muted-foreground text-balance">
            Upload a photo, and every size, pose, background and lighting rule is checked and corrected. No signup, no watermark.
          </p>
        </section>

        <ChinaVisaTool />

        <section className="mt-20 space-y-6">
          <div className="space-y-1 text-center">
            <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
            <p className="text-muted-foreground">Make a China visa photo at home in four steps.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <Card key={step.title}>
                <CardHeader>
                  <Badge variant="outline" className="mb-2 size-7 rounded-full p-0">{i + 1}</Badge>
                  <CardTitle>{step.title}</CardTitle>
                  <CardDescription>{step.desc}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>

        <section className="mx-auto mt-20 max-w-3xl space-y-6">
          <h2 className="text-center text-2xl font-semibold tracking-tight">Frequently asked questions</h2>
          <Accordion type="single" collapsible className="w-full">
            {FAQS.map((faq) => (
              <AccordionItem key={faq.q} value={faq.q}>
                <AccordionTrigger>{faq.q}</AccordionTrigger>
                <AccordionContent className="text-muted-foreground">{faq.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      </main>

      <Separator />
      <footer className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row">
        <p>{SITE_NAME}. Free China visa photos, powered by open-source AI.</p>
        <p>No data stored · No account · Free</p>
      </footer>
    </div>
  )
}
