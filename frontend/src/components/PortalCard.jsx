import { NavLink } from 'react-router-dom'

function PortalCard({ entry }) {
  return (
    <NavLink
      className={`group relative flex min-h-[320px] flex-col justify-between overflow-hidden rounded-[2rem] border p-7 transition duration-200 hover:-translate-y-1 hover:shadow-[0_32px_80px_rgba(15,23,42,0.16)] focus-visible:-translate-y-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20 sm:min-h-[360px] sm:p-8 ${entry.surfaceClass}`}
      to={entry.href}
    >
      <div
        className="absolute inset-0 bg-gradient-to-br opacity-90"
        aria-hidden="true"
      />
      <div className="relative">
        <span
          className={`inline-flex rounded-full px-4 py-2 text-xs font-bold uppercase tracking-[0.22em] ${entry.badgeClass}`}
        >
          {entry.eyebrow}
        </span>
        <h2 className="mt-6 max-w-sm text-3xl font-black leading-tight sm:text-4xl">
          {entry.title}
        </h2>
        <p className="mt-4 max-w-md text-base leading-7 text-slate-700">
          {entry.description}
        </p>
      </div>
      <div className="relative flex items-center justify-between rounded-full bg-white/70 px-5 py-4 backdrop-blur-md">
        <span className="text-sm font-bold sm:text-base">{entry.cta}</span>
        <span className="text-lg transition duration-200 group-hover:translate-x-1">
          &rarr;
        </span>
      </div>
    </NavLink>
  )
}

export default PortalCard
