import { Link } from 'react-router-dom'

function HrPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(135deg,#eff6ff_0%,#f8fafc_55%,#e0f2fe_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-4xl rounded-[2rem] border border-sky-200 bg-white/85 p-8 shadow-[0_28px_80px_rgba(15,23,42,0.1)]">
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700"
          to="/"
        >
          &larr; Back to portal
        </Link>
        <p className="mt-6 text-xs font-extrabold uppercase tracking-[0.26em] text-sky-800">
          HR Workspace
        </p>
        <h1 className="mt-4 text-4xl font-black">HR area is ready for the next screen.</h1>
        <p className="mt-4 max-w-2xl text-base leading-8 text-slate-600">
          The applicant flow is implemented. This HR section can next be wired
          to job listings, applicant review, and status management screens.
        </p>
      </div>
    </main>
  )
}

export default HrPage
