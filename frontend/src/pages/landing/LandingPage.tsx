import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { gsap } from '@/animations/gsap'
import { useGsap } from '@/animations/gsap/useGsap'
import { revealOnScroll } from '@/animations/gsap/presets'
import { useCountUp } from '@/animations/gsap/useCountUp'
import { SceneBackdrop } from '@/three/SceneBackdrop'
import { Logo } from '@/components/layout/Sidebar'
import { ThemeToggle } from '@/components/layout/Topbar'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ROLES } from '@/types/roles'

const STAGES = [
  { name: 'Request', text: 'An employee describes what they need, adds quotes or specs, and submits.' },
  { name: 'Approve', text: 'Managers approve or reject in order, with reasons recorded at every step.' },
  { name: 'Source', text: 'Procurement sends an RFQ, vendors quote, and the team compares them side by side.' },
  { name: 'Order', text: 'The chosen vendor receives a numbered purchase order and confirms it.' },
  { name: 'Receive', text: 'The receiving team checks quantities and flags damage or shortfalls.' },
  { name: 'Pay', text: 'Finance matches invoice, order and receipt, then tracks payment.' },
]

function Fact({ value, label }: { value: number; label: string }) {
  const shown = useCountUp(value, 1.4)
  return (
    <div>
      <p className="font-display text-6xl font-medium tracking-display" aria-label={`${value} ${label}`}><span aria-hidden>{shown}</span></p>
      <p className="text-muted">{label}</p>
    </div>
  )
}

const CHAT = [
  { from: 'you', text: 'Where is PR-2041?' },
  { from: 'ai', text: 'It is with Priya Nair for department-head approval. It was submitted on 12 October.' },
  { from: 'you', text: 'Which quotation for RFQ-118 is cheapest?' },
  { from: 'ai', text: 'Northwind Supplies, about 8% below the next offer, with delivery in 9 days.' },
]

export default function LandingPage() {
  const hero = useRef<HTMLDivElement>(null)
  const page = useRef<HTMLDivElement>(null)

  // The single orchestrated moment: the hero headline lands line by line.
  useGsap(hero, () => {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })
    tl.from('[data-hero-line]', { yPercent: 40, opacity: 0, duration: 0.9, stagger: 0.12 })
      .from('[data-hero-sub]', { opacity: 0, y: 14, duration: 0.6 }, '-=0.4')
      .from('[data-hero-cta]', { opacity: 0, y: 14, duration: 0.5, stagger: 0.08 }, '-=0.3')
  })
  useGsap(page, () => {
    revealOnScroll(gsap.utils.toArray<Element>('[data-scroll]'))
  })

  return (
    <div ref={page}>
      <a href="#content" className="skip-link">Skip to content</a>
      <header className="mx-auto flex max-w-[1200px] items-center gap-u8 px-u8 py-u8 sm:px-u12">
        <Logo />
        <nav aria-label="Page sections" className="ml-auto hidden gap-u10 md:flex">
          <a href="#how" className="hover:underline">How it works</a>
          <a href="#roles" className="hover:underline">Roles</a>
          <a href="#talker" className="hover:underline">SI-Talker</a>
        </nav>
        <div className="ml-auto flex items-center gap-u3 md:ml-0"><ThemeToggle /><Link to="/login"><Button variant="dark">Sign in</Button></Link></div>
      </header>

      <main id="content">
        <section ref={hero} className="relative overflow-hidden">
          <SceneBackdrop className="absolute inset-0 opacity-70 [mask-image:linear-gradient(to_right,transparent,black_45%)]" />
          <div className="relative mx-auto max-w-[1200px] px-u8 pb-u40 pt-u28 sm:px-u12">
            <h1 className="display-xl max-w-4xl">
              <span className="block overflow-hidden"><span data-hero-line className="block">Every purchase,</span></span>
              <span className="block overflow-hidden"><span data-hero-line className="block">from request</span></span>
              <span className="block overflow-hidden"><span data-hero-line className="block">to payment.</span></span>
            </h1>
            <p data-hero-sub className="mt-u12 max-w-xl text-lg text-muted">
              ProcureHub routes requests for approval, collects vendor quotations, issues purchase orders and checks each invoice against what actually arrived.
            </p>
            <div className="mt-u12 flex flex-wrap gap-u5">
              <Link data-hero-cta to="/login"><Button size="lg">Sign in <ArrowRight className="h-5 w-5" aria-hidden /></Button></Link>
              <a data-hero-cta href="#how"><Button size="lg" variant="soft">See how it works</Button></a>
            </div>
          </div>
        </section>

        <section aria-label="At a glance" className="mx-auto grid max-w-[1200px] gap-u12 px-u8 py-u20 sm:grid-cols-3 sm:px-u12">
          <Fact value={15} label="steps tracked from request to payment" />
          <Fact value={6} label="roles, each with its own workspace" />
          <Fact value={3} label="documents matched against every invoice" />
        </section>

        <section id="how" className="mx-auto max-w-[1200px] px-u8 py-u20 sm:px-u12">
          <h2 data-scroll className="display-lg max-w-2xl">One request, six stages, no lost threads</h2>
          <ol className="mt-u16 grid gap-u8 md:grid-cols-2 lg:grid-cols-3">
            {STAGES.map((s, i) => (
              <li key={s.name} data-scroll>
                <Card className="h-full">
                  <p className="font-display text-4xl text-accent" aria-hidden>{i + 1}</p>
                  <h3 className="mt-u4 text-2xl">{s.name}</h3>
                  <p className="mt-u3 text-muted">{s.text}</p>
                </Card>
              </li>
            ))}
          </ol>
        </section>

        <section id="roles" className="mx-auto max-w-[1200px] px-u8 py-u20 sm:px-u12">
          <h2 data-scroll className="display-lg max-w-2xl">A workspace for each person in the process</h2>
          <ul className="mt-u16 grid gap-u8 sm:grid-cols-2 lg:grid-cols-3">
            {ROLES.map((r) => (
              <li key={r.id} data-scroll>
                <div className="h-full rounded-card border border-line bg-surface p-u12">
                  <h3 className="text-2xl">{r.label}</h3>
                  <p className="mt-u3 text-muted">{r.summary}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section id="talker" className="mx-auto max-w-[1200px] px-u8 py-u20 sm:px-u12">
          <div data-scroll className="grid gap-u16 rounded-card bg-ink p-u16 text-bg lg:grid-cols-2 lg:p-u24">
            <div>
              <h2 className="display-lg">Ask SI-Talker instead of searching</h2>
              <p className="mt-u8 max-w-md opacity-80">Ask about a request, a quotation or an order in plain language. Answers come only from records your role is allowed to see.</p>
              <p className="mt-u8 text-sm opacity-70">Preview of the conversation style. SI-Talker goes live in Phase 12.</p>
            </div>
            <ul className="flex flex-col gap-u5" aria-label="Example conversation">
              {CHAT.map((m, i) => (
                <li key={i} className={`max-w-[85%] rounded-card px-u8 py-u6 ${m.from === 'you' ? 'self-end bg-accent text-on-accent' : 'self-start bg-bg/15'}`}>{m.text}</li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t border-line px-u8 py-u12 text-center text-sm text-muted">ProcureHub. Foundation build, Phase 1.</footer>
    </div>
  )
}
