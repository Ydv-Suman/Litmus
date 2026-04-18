import { Link } from 'react-router-dom'

const entryActions = [
  {
    title: 'Create HR account',
    description:
      'Set up your hiring workspace, connect your team role, and start owning job listings.',
    href: '/hr/signup',
    cta: 'Sign up',
    surfaceClass:
      'border-sky-200/70 bg-white/80 from-sky-200 via-cyan-50 to-white text-slate-900 shadow-[0_28px_80px_rgba(25,120,190,0.18)]',
  },
  {
    title: 'Access existing workspace',
    description:
      'Log in to review applications tied to your posted roles and continue hiring work.',
    href: '/hr/login',
    cta: 'Log in',
    surfaceClass:
      'border-emerald-200/70 bg-white/80 from-emerald-200 via-lime-50 to-white text-slate-900 shadow-[0_28px_80px_rgba(35,130,90,0.16)]',
  },
]

function HrPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(125,211,252,0.35),transparent_24%),radial-gradient(circle_at_bottom_right,rgba(167,243,208,0.32),transparent_24%),linear-gradient(135deg,#f4fbff_0%,#eef6f9_45%,#edf7ef_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-6xl">
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/85 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur"
          to="/"
        >
          &larr; Back to portal
        </Link>

        <section className="mt-8 max-w-3xl">
          <p className="text-xs font-extrabold uppercase tracking-[0.3em] text-sky-800">
            HR Workspace
          </p>
          <h1 className="mt-4 text-4xl font-black leading-none tracking-tight sm:text-5xl lg:text-6xl">
            Continue with signup or log in to your hiring desk.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">
            Job listings are assigned to HR users, and applicant submissions
            flow back through those jobs. Choose how you want to enter.
          </p>
        </section>

        <section className="mt-10 grid gap-6 lg:grid-cols-2">
          {entryActions.map((action) => (
            <article
              key={action.title}
              className={`rounded-[2rem] border p-8 ${action.surfaceClass} bg-[linear-gradient(135deg,var(--tw-gradient-stops))]`}
            >
              <p className="text-sm font-bold uppercase tracking-[0.18em] text-slate-500">
                HR entry
              </p>
              <h2 className="mt-6 text-3xl font-black leading-tight">
                {action.title}
              </h2>
              <p className="mt-4 text-base leading-8 text-slate-600">
                {action.description}
              </p>
              <Link
                className="mt-8 inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
                to={action.href}
              >
                {action.cta}
              </Link>
            </article>
          ))}
        </section>
      </div>
    </main>
  )
}

export default HrPage
