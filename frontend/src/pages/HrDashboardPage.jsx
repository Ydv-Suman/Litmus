import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import Field from '../components/Field'
import { createJob, getHrApplications, getJobs } from '../services/api'

const STATUS_META = {
  submitted: {
    label: 'Submitted',
    pill: 'bg-sky-100 text-sky-800 border-sky-200',
    dot: 'bg-sky-500',
  },
  screening_failed: {
    label: 'Screen Failed',
    pill: 'bg-rose-100 text-rose-800 border-rose-200',
    dot: 'bg-rose-500',
  },
  assessment_invited: {
    label: 'Assessment Sent',
    pill: 'bg-amber-100 text-amber-800 border-amber-200',
    dot: 'bg-amber-500',
  },
  assessment_submitted: {
    label: 'Assessment Submitted',
    pill: 'bg-violet-100 text-violet-800 border-violet-200',
    dot: 'bg-violet-500',
  },
  assessment_completed: {
    label: 'Assessment Done',
    pill: 'bg-violet-100 text-violet-800 border-violet-200',
    dot: 'bg-violet-500',
  },
}

const initialJobForm = {
  title: '',
  description: '',
  required_skills: '',
  experience_level: 'Entry',
  location: '',
  job_type: 'Full-time',
}

function fmtDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function fmtDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function parseRequiredSkills(value) {
  return Array.from(
    new Set(
      String(value || '')
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  )
}

function scoreRatio(score, max) {
  if (!max) return 0
  return Math.max(0, Math.min(1, Number(score || 0) / Number(max || 1)))
}

function formatPercent(score, max) {
  return `${Math.round(scoreRatio(score, max) * 100)}%`
}

function SectionFrame({ sectionId, eyebrow, title, description, children, right }) {
  return (
    <section
      className="scroll-mt-28 rounded-[1.8rem] border border-slate-200/80 bg-white/92 p-6 shadow-[0_20px_56px_rgba(15,23,42,0.06)] backdrop-blur"
      id={sectionId}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-black uppercase tracking-[0.28em] text-cyan-700">
            {eyebrow}
          </p>
          <h2 className="mt-2 text-2xl font-black text-slate-950">{title}</h2>
          {description ? (
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              {description}
            </p>
          ) : null}
        </div>
        {right}
      </div>
      <div className="mt-6">{children}</div>
    </section>
  )
}

function MetricCard({ label, value, accent, helper }) {
  return (
    <div className="rounded-[1.35rem] border border-slate-200 bg-white/92 p-4 shadow-sm">
      <div className={`h-1 w-10 rounded-full ${accent}`} />
      <p className="mt-4 text-3xl font-black tracking-tight text-slate-950">{value}</p>
      <p className="mt-1 text-sm font-semibold text-slate-800">{label}</p>
      {helper ? <p className="mt-1 text-xs leading-5 text-slate-500">{helper}</p> : null}
    </div>
  )
}

function StatusPill({ status }) {
  const meta = STATUS_META[status] || {
    label: status || 'Unknown',
    pill: 'bg-slate-100 text-slate-700 border-slate-200',
  }
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold ${meta.pill}`}>
      <span className={`h-2 w-2 rounded-full ${meta.dot || 'bg-slate-400'}`} />
      {meta.label}
    </span>
  )
}

function ScoreBar({ score, max, tone = 'bg-cyan-500' }) {
  return (
    <div className="space-y-2">
      <div className="h-2 rounded-full bg-slate-100">
        <div
          className={`h-2 rounded-full ${tone}`}
          style={{ width: `${Math.round(scoreRatio(score, max) * 100)}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
        <span>{score ?? 0} / {max ?? 0}</span>
        <span>{formatPercent(score, max)}</span>
      </div>
    </div>
  )
}

function CandidateDrawer({ application, onClose, hrUserId }) {
  if (!application) return null

  const screeningScore = application.pipeline_total ?? 0
  const screeningMax = application.pipeline_max ?? 0
  const assessmentScore = application.assessment_total_score ?? application.assessment_score ?? 0
  const assessmentMax = application.assessment_total_max ?? 100

  const timeline = [
    {
      label: 'Applied',
      value: fmtDateTime(application.submitted_at),
      description: `${application.full_name} applied to ${application.job.title}.`,
    },
    {
      label: 'Resume Screening',
      value: application.screening_passed == null ? 'Pending' : application.screening_passed ? 'Passed' : 'Failed',
      description:
        application.pipeline_total != null
          ? `Screening score ${application.pipeline_total} / ${application.pipeline_max}.`
          : 'Screening not yet scored.',
    },
    {
      label: 'Assessment Sent',
      value: fmtDateTime(application.assessment_sent_at),
      description: application.assessment_sent_at ? 'Candidate received the technical assessment.' : 'Assessment not sent.',
    },
    {
      label: 'Assessment Submitted',
      value: fmtDateTime(application.assessment_submitted_at),
      description:
        application.assessment_submitted_at
          ? `Assessment score ${assessmentScore} / ${assessmentMax}.`
          : 'Candidate has not submitted the assessment.',
    },
  ]

  return (
    <>
      <button
        className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-xl flex-col overflow-hidden border-l border-slate-200 bg-[#f7f4ec] shadow-[0_20px_80px_rgba(15,23,42,0.32)]">
        <div className="border-b border-slate-200 bg-white/80 px-6 py-5 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.28em] text-cyan-700">
                Candidate Snapshot
              </p>
              <h3 className="mt-2 text-2xl font-black text-slate-950">
                {application.full_name}
              </h3>
              <p className="mt-1 text-sm text-slate-600">{application.email}</p>
            </div>
            <button
              className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
              onClick={onClose}
            >
              Close
            </button>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <StatusPill status={application.status} />
            <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-bold text-white">
              {application.job.title}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-[1.4rem] border border-slate-200 bg-white p-4">
              <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-400">
                Screening
              </p>
              <p className="mt-3 text-2xl font-black text-slate-950">
                {screeningScore} / {screeningMax}
              </p>
              <div className="mt-4">
                <ScoreBar max={screeningMax} score={screeningScore} tone="bg-cyan-500" />
              </div>
            </div>
            <div className="rounded-[1.4rem] border border-slate-200 bg-white p-4">
              <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-400">
                Assessment
              </p>
              <p className="mt-3 text-2xl font-black text-slate-950">
                {assessmentScore} / {assessmentMax}
              </p>
              <div className="mt-4">
                <ScoreBar max={assessmentMax} score={assessmentScore} tone="bg-violet-500" />
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-[1.5rem] border border-slate-200 bg-white p-5">
            <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-400">
              Timeline
            </p>
            <ol className="mt-5 space-y-5">
              {timeline.map((item) => (
                <li key={item.label} className="flex gap-4">
                  <div className="mt-1 h-3 w-3 rounded-full bg-cyan-500" />
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-slate-900">{item.label}</p>
                    <p className="mt-0.5 text-xs font-semibold text-slate-500">{item.value}</p>
                    <p className="mt-1 text-sm text-slate-600">{item.description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className="mt-6 rounded-[1.5rem] border border-slate-200 bg-white p-5">
            <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-400">
              Links
            </p>
            <div className="mt-4 grid gap-3">
              <Link
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-800 transition hover:bg-slate-100"
                to={`/hr/${hrUserId}/applicants/${application.application_id}`}
              >
                Open full candidate review
              </Link>
              {application.github_url ? (
                <a
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-800 transition hover:bg-slate-100"
                  href={application.github_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  View GitHub profile
                </a>
              ) : null}
              {application.linkedin_url ? (
                <a
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-800 transition hover:bg-slate-100"
                  href={application.linkedin_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  View LinkedIn profile
                </a>
              ) : null}
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}

function DashboardModal({ isOpen, onClose, children, widthClass = 'max-w-6xl' }) {
  if (!isOpen) return null

  return (
    <>
      <button
        aria-label="Close modal"
        className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className={`w-full ${widthClass}`}>
          <div className="mb-3 flex justify-end">
            <button
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
              onClick={onClose}
              type="button"
            >
              Close
            </button>
          </div>
          {children}
        </div>
      </div>
    </>
  )
}

function HrDashboardPage() {
  const navigate = useNavigate()
  const [hrUser, setHrUser] = useState(null)
  const [applications, setApplications] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selected, setSelected] = useState(null)
  const [activePanel, setActivePanel] = useState(null)
  const [jobForm, setJobForm] = useState(initialJobForm)
  const [jobFormState, setJobFormState] = useState({
    status: 'idle',
    message: '',
  })

  useEffect(() => {
    const stored = localStorage.getItem('hr_user')
    if (!stored) {
      navigate('/hr/login', { replace: true })
      return
    }

    const user = JSON.parse(stored)
    setHrUser(user)

    Promise.all([getHrApplications(user.id), getJobs()])
      .then(([applicationsData, jobsData]) => {
        setApplications(Array.isArray(applicationsData) ? applicationsData : [])
        setJobs(
          Array.isArray(jobsData)
            ? jobsData.filter((job) => String(job.hr_user_id) === String(user.id))
            : [],
        )
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'Failed to load dashboard data.')
        setLoading(false)
      })
  }, [navigate])

  const handleLogout = () => {
    localStorage.removeItem('hr_user')
    navigate('/hr/login', { replace: true })
  }

  const handleJobFormChange = (event) => {
    const { name, value } = event.target
    setJobForm((current) => ({
      ...current,
      [name]: value,
    }))
  }

  const handleCreateJob = async (event) => {
    event.preventDefault()
    if (!hrUser) return

    const requiredSkills = parseRequiredSkills(jobForm.required_skills)
    if (!requiredSkills.length) {
      setJobFormState({
        status: 'error',
        message: 'Add at least one required skill.',
      })
      return
    }

    setJobFormState({
      status: 'submitting',
      message: 'Publishing job listing...',
    })

    try {
      const response = await createJob({
        title: jobForm.title,
        description: jobForm.description,
        required_skills: requiredSkills,
        experience_level: jobForm.experience_level,
        department: hrUser.department,
        location: jobForm.location.trim() || null,
        job_type: jobForm.job_type,
        hr_user_id: hrUser.id,
      })

      const createdJob = response.job || null
      setJobs((current) =>
        createdJob ? [...current, createdJob].sort((a, b) => a.title.localeCompare(b.title)) : current,
      )
      setJobForm(initialJobForm)
      setJobFormState({
        status: 'success',
        message: response.message || 'Job listing created successfully.',
      })
    } catch (err) {
      setJobFormState({
        status: 'error',
        message: err.message || 'Failed to create job listing.',
      })
    }
  }

  const filteredApplications = useMemo(
    () =>
      applications.filter((app) => {
        const matchesSearch =
          search === '' ||
          app.full_name.toLowerCase().includes(search.toLowerCase()) ||
          app.email.toLowerCase().includes(search.toLowerCase()) ||
          app.job.title.toLowerCase().includes(search.toLowerCase())
        const matchesStatus = statusFilter === 'all' || app.status === statusFilter
        return matchesSearch && matchesStatus
      }),
    [applications, search, statusFilter],
  )

  const applicantCountByJobId = useMemo(() => {
    const counts = new Map()
    for (const application of applications) {
      const jobId = application?.job?.id
      if (jobId == null) continue
      counts.set(jobId, (counts.get(jobId) || 0) + 1)
    }
    return counts
  }, [applications])

  const dashboardMetrics = useMemo(
    () => [
      {
        label: 'Open Roles',
        value: jobs.length,
        helper: 'Listings currently visible to candidates',
        accent: 'bg-cyan-500',
      },
      {
        label: 'Candidate Queue',
        value: applications.length,
        helper: 'Applications attached to your job listings',
        accent: 'bg-slate-900',
      },
      {
        label: 'Assessment Ready',
        value: applications.filter((a) => a.status === 'assessment_invited').length,
        helper: 'Candidates waiting to complete the assessment',
        accent: 'bg-amber-500',
      },
      {
        label: 'Reviewed',
        value: applications.filter((a) => ['assessment_completed', 'assessment_submitted'].includes(a.status)).length,
        helper: 'Candidates with completed assessments',
        accent: 'bg-violet-500',
      },
    ],
    [applications, jobs.length],
  )

  const dashboardNav = [
    {
      key: 'create',
      label: 'Create a job listing',
      description: 'Publish a role with skills and scope for the screening pipeline.',
    },
    {
      key: 'listings',
      label: 'Active listings',
      description: 'Review live roles and applicant volume without leaving the dashboard.',
    },
    {
      key: 'applications',
      label: 'Applications',
      description: 'Open the full candidate queue with filters, scores, and review actions.',
    },
  ]

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(34,197,94,0.12),transparent_18%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,0.16),transparent_24%),linear-gradient(180deg,#f2efe8_0%,#eef5f6_45%,#f7fafb_100%)] px-4 py-6 text-slate-900 sm:px-6 lg:px-10 lg:py-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="rounded-[2.2rem] border border-white/70 bg-white/70 p-5 shadow-[0_24px_100px_rgba(15,23,42,0.10)] backdrop-blur md:p-7">
          <div className="flex flex-wrap items-start justify-between gap-6 border-b border-slate-200/80 pb-6">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.36em] text-cyan-700">
                Hiring Control Room
              </p>
              <h1 className="mt-3 max-w-3xl text-3xl font-black tracking-tight text-slate-950 md:text-5xl">
                Recruit, review, and move candidates without losing context.
              </h1>
              {hrUser ? (
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  Signed in as <span className="font-bold text-slate-800">{hrUser.full_name}</span>
                  {' '}for <span className="font-bold text-slate-800">{hrUser.company_name}</span> in the
                  {' '}<span className="font-bold text-slate-800">{hrUser.department}</span> hiring lane.
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
                to="/"
              >
                Back to portal
              </Link>
              <button
                className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800"
                onClick={handleLogout}
              >
                Log out
              </button>
            </div>
          </div>

          <div className="mt-6 rounded-[1.5rem] border border-slate-200/80 bg-white/80 p-3 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-[11px] font-black uppercase tracking-[0.26em] text-slate-400">
                  Workspace Navigation
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  Jump directly to the part of the hiring workflow you need.
                </p>
              </div>
              <nav className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                {dashboardNav.map((item) => (
                  <button
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-white"
                    onClick={() => setActivePanel(item.key)}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {dashboardMetrics.map((metric) => (
              <MetricCard
                key={metric.label}
                accent={metric.accent}
                helper={metric.helper}
                label={metric.label}
                value={metric.value}
              />
            ))}
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            {dashboardNav.map((item) => (
              <button
                key={item.key}
                className="rounded-[1.5rem] border border-slate-200 bg-white/88 p-5 text-left shadow-sm transition hover:border-cyan-300 hover:bg-white"
                onClick={() => setActivePanel(item.key)}
                type="button"
              >
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
                  Workspace
                </p>
                <h3 className="mt-3 text-xl font-black text-slate-950">{item.label}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      <DashboardModal
        isOpen={activePanel === 'create'}
        onClose={() => setActivePanel(null)}
        widthClass="max-w-4xl"
      >
        <SectionFrame
          description="Publish a role with the skills and context your applicant scoring pipeline will use."
          eyebrow="Role Setup"
          title="Create a job listing"
          right={
            <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-600">
              Department: {hrUser?.department ?? '—'}
            </div>
          }
        >
          <form className="space-y-5" onSubmit={handleCreateJob}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Job title"
                name="title"
                onChange={handleJobFormChange}
                placeholder="Senior Backend Engineer"
                required
                value={jobForm.title}
              />

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-800">
                  Experience level
                </span>
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:bg-white"
                  name="experience_level"
                  onChange={handleJobFormChange}
                  value={jobForm.experience_level}
                >
                  <option value="Entry">Entry</option>
                  <option value="Mid">Mid</option>
                  <option value="Senior">Senior</option>
                </select>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-800">
                  Job type
                </span>
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:bg-white"
                  name="job_type"
                  onChange={handleJobFormChange}
                  value={jobForm.job_type}
                >
                  <option value="Full-time">Full-time</option>
                  <option value="Part-time">Part-time</option>
                  <option value="Contract">Contract</option>
                  <option value="Internship">Internship</option>
                </select>
              </label>

              <Field
                label="Location"
                name="location"
                onChange={handleJobFormChange}
                placeholder="Remote or Monroe, LA"
                value={jobForm.location}
              />
            </div>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-800">
                Role description
              </span>
              <textarea
                className="min-h-36 w-full rounded-[1.7rem] border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-900 outline-none transition focus:border-cyan-500 focus:bg-white"
                name="description"
                onChange={handleJobFormChange}
                placeholder="Describe the impact, day-to-day ownership, and constraints that matter for this role."
                required
                value={jobForm.description}
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-800">
                Required skills
              </span>
              <textarea
                className="min-h-28 w-full rounded-[1.7rem] border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-900 outline-none transition focus:border-cyan-500 focus:bg-white"
                name="required_skills"
                onChange={handleJobFormChange}
                placeholder="Go, Gin, PostgreSQL, React, Docker"
                required
                value={jobForm.required_skills}
              />
              <p className="mt-2 text-xs font-medium text-slate-500">
                Separate skills with commas or line breaks. These feed the screening and assessment prompts.
              </p>
            </label>

            {jobFormState.message ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
                  jobFormState.status === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                    : jobFormState.status === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-900'
                      : 'border-sky-200 bg-sky-50 text-sky-900'
                }`}
              >
                {jobFormState.message}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <button
                className="rounded-full bg-slate-950 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                disabled={jobFormState.status === 'submitting'}
                type="submit"
              >
                {jobFormState.status === 'submitting' ? 'Publishing…' : 'Publish job'}
              </button>
              <p className="text-sm text-slate-500">
                New roles appear in the applicant form immediately after save.
              </p>
            </div>
          </form>
        </SectionFrame>
      </DashboardModal>

      <DashboardModal
        isOpen={activePanel === 'listings'}
        onClose={() => setActivePanel(null)}
        widthClass="max-w-5xl"
      >
        <SectionFrame
          description="Track the roles currently collecting applicants and see where volume is accumulating."
          eyebrow="Role Inventory"
          title="Your active listings"
          right={
            <div className="rounded-full bg-slate-950 px-3 py-1 text-xs font-bold text-white">
              {jobs.length} live
            </div>
          }
        >
          {jobs.length === 0 ? (
            <div className="rounded-[1.7rem] border border-dashed border-slate-200 bg-slate-50 px-5 py-8 text-sm text-slate-500">
              No active roles yet. Publish one from the create listing workspace to start receiving applications.
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {jobs.map((job) => (
                <article
                  key={job.id}
                  className="rounded-[1.7rem] border border-slate-200 bg-[#fbfaf7] p-5 transition hover:border-cyan-300 hover:bg-white"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs font-black uppercase tracking-[0.22em] text-slate-400">
                        Role #{job.id}
                      </p>
                      <h3 className="mt-2 text-lg font-black text-slate-950">
                        {job.title}
                      </h3>
                      <p className="mt-2 text-sm text-slate-600">
                        {job.experience_level} · {job.job_type}
                        {job.location ? ` · ${job.location}` : ''}
                      </p>
                    </div>
                    <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-bold text-slate-700">
                      {applicantCountByJobId.get(job.id) || 0} applicants
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </SectionFrame>
      </DashboardModal>

      <DashboardModal
        isOpen={activePanel === 'applications'}
        onClose={() => setActivePanel(null)}
        widthClass="max-w-[1180px]"
      >
        <SectionFrame
          description="Filter quickly, compare scores, and open a candidate review without leaving the queue."
          eyebrow="Candidate Queue"
          title="Applications"
          right={
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-bold text-slate-700">
                {filteredApplications.length} visible
              </div>
            </div>
          }
        >
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {[
                { value: 'all', label: 'All' },
                { value: 'submitted', label: 'Submitted' },
                { value: 'screening_failed', label: 'Failed' },
                { value: 'assessment_invited', label: 'Invited' },
                { value: 'assessment_submitted', label: 'Submitted Assessments' },
                { value: 'assessment_completed', label: 'Completed' },
              ].map((tab) => (
                <button
                  key={tab.value}
                  className={`rounded-full px-4 py-2 text-sm font-bold transition ${
                    statusFilter === tab.value
                      ? 'bg-slate-950 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                  onClick={() => setStatusFilter(tab.value)}
                  type="button"
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <input
              className="w-full rounded-full border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:bg-white lg:max-w-sm"
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, email, or role"
              type="text"
              value={search}
            />
          </div>

          <div className="mt-6">
            {loading ? (
              <div className="rounded-[1.6rem] border border-slate-200 bg-slate-50 px-6 py-12 text-center text-sm text-slate-500">
                Loading your applicant queue…
              </div>
            ) : error ? (
              <div className="rounded-[1.6rem] border border-rose-200 bg-rose-50 px-6 py-12 text-center text-sm font-semibold text-rose-700">
                {error}
              </div>
            ) : filteredApplications.length === 0 ? (
              <div className="rounded-[1.6rem] border border-slate-200 bg-slate-50 px-6 py-12 text-center text-sm text-slate-500">
                {applications.length === 0
                  ? 'No applications have landed in your queue yet.'
                  : 'No applicants match the current filters.'}
              </div>
            ) : (
              <div className="grid gap-4">
                {filteredApplications.map((app) => (
                  <article
                    key={app.application_id}
                    className="grid gap-5 rounded-[1.8rem] border border-slate-200 bg-white p-5 shadow-sm transition hover:border-cyan-300 hover:shadow-[0_18px_60px_rgba(15,23,42,0.08)] lg:grid-cols-[1.1fr_0.7fr_0.6fr]"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-3">
                        <Link
                          className="text-lg font-black text-slate-950 underline-offset-4 hover:text-cyan-700 hover:underline"
                          to={`/hr/${hrUser.id}/applicants/${app.application_id}`}
                        >
                          {app.full_name}
                        </Link>
                        <StatusPill status={app.status} />
                      </div>
                      <p className="mt-2 text-sm font-semibold text-slate-600">
                        {app.job.title}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-500">
                        <span>{app.email}</span>
                        <span>{app.phone || 'No phone'}</span>
                        <span>Applied {fmtDate(app.submitted_at)}</span>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
                      <div>
                        <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-400">
                          Screening Score
                        </p>
                        <p className="mt-2 text-xl font-black text-slate-950">
                          {app.pipeline_total ?? 0} / {app.pipeline_max ?? 0}
                        </p>
                        <div className="mt-3">
                          <ScoreBar max={app.pipeline_max ?? 0} score={app.pipeline_total ?? 0} tone="bg-cyan-500" />
                        </div>
                      </div>
                      <div>
                        <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-400">
                          Assessment
                        </p>
                        <p className="mt-2 text-xl font-black text-slate-950">
                          {app.assessment_score ?? 0} / 50
                        </p>
                        <div className="mt-3">
                          <ScoreBar max={50} score={app.assessment_score ?? 0} tone="bg-violet-500" />
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col justify-between gap-3 rounded-[1.5rem] bg-[#f7f4ec] p-4">
                      <div>
                        <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-400">
                          Actions
                        </p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">
                          Open the review page for full parsed resume, GitHub, LinkedIn, and assessment context.
                        </p>
                      </div>
                      <div className="grid gap-2">
                        <Link
                          className="rounded-full bg-slate-950 px-4 py-3 text-center text-sm font-bold text-white transition hover:bg-slate-800"
                          to={`/hr/${hrUser.id}/applicants/${app.application_id}`}
                        >
                          Open review
                        </Link>
                        <button
                          className="rounded-full border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
                          onClick={() => setSelected(app)}
                          type="button"
                        >
                          Quick view
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </SectionFrame>
      </DashboardModal>

      <CandidateDrawer application={selected} hrUserId={hrUser?.id} onClose={() => setSelected(null)} />
    </main>
  )
}

export default HrDashboardPage
