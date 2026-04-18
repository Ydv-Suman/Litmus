import PortalCard from '../components/PortalCard'

const entryPoints = [
  {
    eyebrow: 'Candidate Portal',
    title: 'Apply for a job',
    description:
      'Browse open roles, review expectations, and submit an application in a focused flow.',
    href: '/apply',
    cta: 'Start application',
    surfaceClass:
      'border-amber-200/70 bg-white/70 from-amber-200 via-orange-100 to-white text-slate-900 shadow-[0_28px_70px_rgba(180,100,20,0.18)]',
    badgeClass: 'bg-amber-100 text-amber-900',
  },
  {
    eyebrow: 'HR Workspace',
    title: 'Manage hiring',
    description:
      'Review applicants, coordinate hiring activity, and keep recruiting work organized.',
    href: '/hr/login',
    cta: 'Open HR area',
    surfaceClass:
      'border-sky-200/70 bg-white/70 from-sky-200 via-cyan-50 to-white text-slate-900 shadow-[0_28px_70px_rgba(60,110,150,0.18)]',
    badgeClass: 'bg-slate-900 text-white',
  },
]

function HomePage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(249,196,74,0.35),transparent_28%),linear-gradient(135deg,#f8f5ee_0%,#eef4f8_50%,#dfe7f2_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <section className="mx-auto mb-10 max-w-4xl text-center">
        <p className="mb-3 text-xs font-extrabold uppercase tracking-[0.28em] text-amber-800">
          Litmus Hiring Hub
        </p>
        <h1 className="text-4xl font-black leading-none tracking-tight sm:text-5xl lg:text-7xl">
          Choose the space that matches your role.
        </h1>
      </section>

      <section
        className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-2"
        aria-label="Portal selection"
      >
        {entryPoints.map((entry) => (
          <PortalCard key={entry.title} entry={entry} />
        ))}
      </section>
    </main>
  )
}

export default HomePage
