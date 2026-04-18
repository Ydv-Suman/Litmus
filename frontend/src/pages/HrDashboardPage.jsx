import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { getHrApplications } from '../services/api'

const STATUS_STYLES = {
  submitted: 'bg-sky-100 text-sky-800',
  screening_failed: 'bg-rose-100 text-rose-800',
  assessment_invited: 'bg-emerald-100 text-emerald-800',
  assessment_completed: 'bg-violet-100 text-violet-800',
}

const STATUS_LABELS = {
  submitted: 'Submitted',
  screening_failed: 'Screening Failed',
  assessment_invited: 'Assessment Invited',
  assessment_completed: 'Assessment Done',
}

function HrDashboardPage() {
  const navigate = useNavigate()
  const [hrUser, setHrUser] = useState(null)
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  useEffect(() => {
    const stored = localStorage.getItem('hr_user')
    if (!stored) {
      navigate('/hr/login', { replace: true })
      return
    }
    const user = JSON.parse(stored)
    setHrUser(user)

    getHrApplications(user.id)
      .then((data) => {
        setApplications(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'Failed to load applications.')
        setLoading(false)
      })
  }, [navigate])

  const handleLogout = () => {
    localStorage.removeItem('hr_user')
    navigate('/hr/login', { replace: true })
  }

  const filtered = applications.filter((app) => {
    const matchesSearch =
      search === '' ||
      app.full_name.toLowerCase().includes(search.toLowerCase()) ||
      app.email.toLowerCase().includes(search.toLowerCase()) ||
      app.job.title.toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === 'all' || app.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(167,243,208,0.34),transparent_24%),linear-gradient(135deg,#f3fff8_0%,#f3fbff_55%,#eef6f9_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-7xl">

        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[0.28em] text-emerald-800">
              HR Dashboard
            </p>
            <h1 className="mt-2 text-3xl font-black sm:text-4xl">
              Applicants
            </h1>
            {hrUser && (
              <p className="mt-1 text-sm text-slate-500">
                {hrUser.full_name} &middot; {hrUser.company_name} &middot; {hrUser.department}
              </p>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="rounded-full border border-slate-200 bg-white/85 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur hover:bg-slate-50"
          >
            Log out
          </button>
        </div>

        {/* Nav tabs */}
        <div className="mt-8 flex flex-wrap items-center gap-1 rounded-2xl border border-slate-200 bg-white/80 p-1 w-fit">
          {[
            { value: 'all', label: 'All' },
            { value: 'submitted', label: 'Submitted' },
            { value: 'screening_failed', label: 'Failed' },
            { value: 'assessment_invited', label: 'Invited' },
            { value: 'assessment_completed', label: 'Assessed' },
          ].map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setStatusFilter(tab.value)}
              className={`rounded-xl px-4 py-2 text-sm font-semibold transition-colors ${
                statusFilter === tab.value
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="mt-4">
          <input
            type="text"
            placeholder="Search name, email, or job..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full max-w-sm rounded-full border border-slate-200 bg-white px-4 py-2 text-sm shadow-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
          />
        </div>

        {/* Stats row */}
        {!loading && !error && (
          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { label: 'Total', count: applications.length, color: 'text-slate-700' },
              { label: 'Submitted', count: applications.filter(a => a.status === 'submitted').length, color: 'text-sky-700' },
              { label: 'Screening Failed', count: applications.filter(a => a.status === 'screening_failed').length, color: 'text-rose-700' },
              { label: 'Assessment Done', count: applications.filter(a => a.status === 'assessment_completed').length, color: 'text-violet-700' },
            ].map(({ label, count, color }) => (
              <div key={label} className="rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-sm">
                <p className={`text-2xl font-black ${color}`}>{count}</p>
                <p className="mt-0.5 text-xs font-medium text-slate-500">{label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Content */}
        <div className="mt-6 rounded-[2rem] border border-emerald-200/80 bg-white/90 shadow-[0_28px_80px_rgba(15,23,42,0.10)] backdrop-blur overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-sm text-slate-500">Loading applications...</div>
          ) : error ? (
            <div className="p-12 text-center text-sm text-rose-600">{error}</div>
          ) : filtered.length === 0 ? (
            <div className="p-12 text-center text-sm text-slate-500">
              {applications.length === 0 ? 'No applications yet.' : 'No results match your filters.'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70">
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Applicant</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Job</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">MCQ Score</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Links</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Applied</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map((app) => (
                    <tr key={app.application_id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <p className="font-semibold text-slate-900">{app.full_name}</p>
                        <p className="text-xs text-slate-500">{app.email}</p>
                        {app.phone && <p className="text-xs text-slate-400">{app.phone}</p>}
                      </td>
                      <td className="px-6 py-4">
                        <p className="font-medium text-slate-800">{app.job.title}</p>
                        <p className="text-xs text-slate-500">{app.job.department}</p>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLES[app.status] ?? 'bg-slate-100 text-slate-700'}`}>
                          {STATUS_LABELS[app.status] ?? app.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {app.assessment_score != null ? (
                          <div>
                            <span className="text-base font-black text-violet-700">
                              {app.assessment_score}
                            </span>
                            <span className="text-xs text-slate-400"> / 50</span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-col gap-1">
                          {app.github_url && (
                            <a href={app.github_url} target="_blank" rel="noreferrer" className="text-xs text-emerald-700 underline-offset-2 hover:underline">
                              GitHub
                            </a>
                          )}
                          {app.linkedin_url && (
                            <a href={app.linkedin_url} target="_blank" rel="noreferrer" className="text-xs text-sky-700 underline-offset-2 hover:underline">
                              LinkedIn
                            </a>
                          )}
                          {!app.github_url && !app.linkedin_url && (
                            <span className="text-xs text-slate-400">—</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-500 whitespace-nowrap">
                        {app.submitted_at
                          ? new Date(app.submitted_at).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}

export default HrDashboardPage
