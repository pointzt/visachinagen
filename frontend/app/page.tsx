import ChinaVisaTool from '@/components/china/ChinaVisaTool'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const STEPS = [
  { title: 'Upload Your Photo', desc: 'Take a photo with your phone or webcam against a plain background. Supports JPG, PNG, and HEIC.' },
  { title: 'Automatic Checks', desc: 'PhotoGen checks head pose, tilt, lighting, background, and framing against the Chinese MFA 2016 photo requirements.' },
  { title: 'Review Corrections', desc: 'See the original and corrected photo side by side, toggle each correction, and fine-tune with manual sliders.' },
  { title: 'Download for Free', desc: 'Download the 420×560 digital photo for the online application, or a 33×48 mm print sheet. No watermark, no signup.' },
]

const FAQS = [
  { q: 'Is PhotoGen really free?', a: 'Yes — 100% free with no watermarks, no signup, and unlimited usage. PhotoGen is open-source software.' },
  { q: 'Is my photo stored on your servers?', a: 'No. Your photo is processed and returned immediately. We do not store any images or personal data.' },
  { q: 'What size is a China visa photo?', a: 'The digital photo for the online application is 420×560 px and 40–120 KB. A printed photo is 33×48 mm with a white background.' },
  { q: 'What if my photo fails a check?', a: 'PhotoGen explains which requirement failed and whether it can be corrected automatically or needs a retake.' },
  { q: 'Do I need to remove the background myself?', a: 'No. PhotoGen removes the background with AI and replaces it with the required plain white.' },
]

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-40 border-b bg-card">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg overflow-hidden">
              <img src="/logo.jpg" alt="PhotoGen" className="h-full w-full object-cover" />
            </div>
            <div>
              <h1 className="text-sm font-bold leading-none text-foreground">PhotoGen</h1>
              <p className="text-[11px] text-muted-foreground">Free China Visa Photo Maker</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="hidden border-green-200 bg-green-50 text-[11px] text-green-700 sm:inline-flex">
              <span className="size-1.5 rounded-full bg-green-500" />
              Free & Unlimited
            </Badge>
            <a href="https://github.com/deidaraiorek/photogen" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 rounded-full border bg-secondary px-2.5 py-0.5 transition-colors hover:bg-muted">
              <svg className="size-3.5 text-foreground/80" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
              <span className="text-[11px] font-medium text-foreground/80">Open Source</span>
            </a>
          </div>
        </div>
      </header>

      <main className="flex-1 mx-auto max-w-6xl w-full px-3 sm:px-4 py-4 sm:py-8">
        <div className="mb-4 sm:mb-8 text-center">
          <h2 className="text-xl font-bold text-foreground sm:text-2xl">Create Your China Visa Photo Online for Free</h2>
          <p className="mt-1.5 text-xs text-muted-foreground sm:text-sm">Checked against the Chinese MFA 2016 photo requirements — no signup required</p>
        </div>

        <ChinaVisaTool />

        <section className="mt-16 space-y-16">
          <div>
            <h2 className="mb-8 text-center text-lg font-bold text-foreground">How to Make a China Visa Photo at Home</h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step, i) => (
                <Card key={step.title} className="gap-2 py-5">
                  <CardHeader className="flex items-center gap-2.5 px-5">
                    <span className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">{i + 1}</span>
                    <CardTitle className="text-sm font-semibold">{step.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="px-5 text-xs leading-relaxed text-muted-foreground">{step.desc}</CardContent>
                </Card>
              ))}
            </div>
          </div>


          <div>
            <h2 className="mb-6 text-center text-lg font-bold text-foreground">Frequently Asked Questions</h2>
            <Accordion type="single" collapsible className="mx-auto max-w-3xl rounded-xl bg-card px-5 ring-1 ring-foreground/10">
              {FAQS.map((faq) => (
                <AccordionItem key={faq.q} value={faq.q}>
                  <AccordionTrigger className="text-sm">{faq.q}</AccordionTrigger>
                  <AccordionContent className="leading-relaxed text-muted-foreground">{faq.a}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </section>
      </main>

      <footer className="border-t bg-card">
        <div className="mx-auto max-w-6xl px-4 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-muted-foreground">
          <p>PhotoGen — Free China visa photo maker powered by open-source AI</p>
          <p>No data stored · No account required · 100% free</p>
        </div>
      </footer>
    </div>
  )
}
