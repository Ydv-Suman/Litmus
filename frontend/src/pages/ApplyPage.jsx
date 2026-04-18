import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import Field from '../components/Field'
import JobSelect from '../components/JobSelect'
import { getJobs, submitApplication } from '../services/api'

const RESUME_PDF_TYPES = new Set(['application/pdf', 'application/x-pdf'])

const initialFormData = {
  full_name: '',
  email: '',
  phone: '+1',
  job_id: '',
  github_url: '',
  linkedin_url: '',
  resume: null,
  informationConfirmed: false,
  verificationConsent: false,
}

function formatPhoneNumber(value) {
  const rawDigits = value.replace(/\D/g, '')

  if (!rawDigits.length || rawDigits === '1') {
    return '+1'
  }

  const digits = value.trim().startsWith('+1')
    ? rawDigits.slice(1, 11)
    : rawDigits.length > 10 && rawDigits.startsWith('1')
      ? rawDigits.slice(1, 11)
      : rawDigits.slice(0, 10)
  const areaCode = digits.slice(0, 3)
  const prefix = digits.slice(3, 6)
  const lineNumber = digits.slice(6, 10)

  let formatted = '+1'

  if (areaCode) {
    formatted += ` (${areaCode}`
  }

  if (areaCode.length === 3) {
    formatted += ')'
  }

  if (prefix) {
    formatted += ` ${prefix}`
  }

  if (lineNumber) {
    formatted += `-${lineNumber}`
  }

  return formatted
}

function ApplyPage() {
  const [formData, setFormData] = useState(initialFormData)
  const [submissionState, setSubmissionState] = useState({
    status: 'idle',
    message: '',
  })
  const [jobsState, setJobsState] = useState({
    status: 'loading',
    jobs: [],
    message: '',
  })

  useEffect(() => {
    let active = true

    getJobs()
      .then((jobs) => {
        if (!active) {
          return
        }

        setJobsState({
          status: 'success',
          jobs,
          message: jobs.length ? '' : 'No open jobs are available right now.',
        })
      })
      .catch((error) => {
        if (!active) {
          return
        }

        setJobsState({
          status: 'error',
          jobs: [],
          message: error.message || 'Unable to load available jobs.',
        })
      })

    return () => {
      active = false
    }
  }, [])

  const handleFieldChange = (event) => {
    const { checked, name, type, value, files } = event.target
    let nextValue =
      type === 'checkbox' ? checked : files ? files[0] ?? null : value

    if (name === 'phone' && typeof nextValue === 'string') {
      nextValue = formatPhoneNumber(nextValue)
    }

    if (name === 'resume' && files) {
      const selectedFile = files[0] ?? null
      const isPdfFile =
        selectedFile &&
        selectedFile.name.toLowerCase().endsWith('.pdf') &&
        RESUME_PDF_TYPES.has(selectedFile.type)

      if (selectedFile && !isPdfFile) {
        event.target.value = ''
        setSubmissionState({
          status: 'error',
          message: 'Resume must be a PDF file.',
        })
        setFormData((current) => ({
          ...current,
          resume: null,
        }))
        return
      }

      setSubmissionState((current) =>
        current.status === 'error' && current.message === 'Resume must be a PDF file.'
          ? { status: 'idle', message: '' }
          : current,
      )
    }

    setFormData((current) => ({
      ...current,
      [name]: nextValue,
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    if (!formData.resume) {
      setSubmissionState({
        status: 'error',
        message: 'Resume must be a PDF file.',
      })
      return
    }

    setSubmissionState({
      status: 'submitting',
      message: 'Submitting application...',
    })

    try {
      const response = await submitApplication({
        ...formData,
        job_id: Number(formData.job_id),
      })

      setSubmissionState({
        status: 'success',
        message: response.assessment_url
          ? `${response.message || 'Application submitted successfully.'} Open your assessment at ${response.assessment_url}`
          : response.message || 'Application submitted successfully.',
      })
      setFormData(initialFormData)
    } catch (error) {
      setSubmissionState({
        status: 'error',
        message: error.message || 'Failed to submit application.',
      })
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(249,196,74,0.28),transparent_28%),linear-gradient(135deg,#f8f5ee_0%,#eef4f8_50%,#dfe7f2_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-5xl">
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur"
          to="/"
        >
          &larr; Back to portal
        </Link>

        <section className="mt-6">
          <form
            className="rounded-[2rem] border border-slate-200 bg-white/85 p-8 shadow-[0_28px_80px_rgba(15,23,42,0.12)] backdrop-blur"
            onSubmit={handleSubmit}
          >
            <div className="mb-6">
              <p className="text-xs font-extrabold uppercase tracking-[0.26em] text-amber-800">
                Application Form
              </p>
              <h1 className="mt-3 text-3xl font-black sm:text-4xl">
                Submit your details
              </h1>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field
                label="Full name"
                name="full_name"
                onChange={handleFieldChange}
                placeholder="John Smith"
                required
                value={formData.full_name}
              />
              <Field
                label="Email"
                name="email"
                onChange={handleFieldChange}
                placeholder="john@example.com"
                required
                type="email"
                value={formData.email}
              />
              <Field
                label="Phone"
                inputMode="tel"
                name="phone"
                onChange={handleFieldChange}
                pattern="^\+1 \(\d{3}\) \d{3}-\d{4}$"
                placeholder="(111) 111-1111"
                required
                title="Phone number must be in the format +1 (111) 111-1111"
                value={formData.phone}
              />
              <JobSelect
                jobs={jobsState.jobs}
                message={jobsState.message}
                name="job_id"
                onChange={handleFieldChange}
                required
                status={jobsState.status}
                value={formData.job_id}
              />
            </div>

            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              <Field
                label="GitHub URL"
                name="github_url"
                onChange={handleFieldChange}
                placeholder="https://github.com/username"
                type="url"
                value={formData.github_url}
              />
              <Field
                label="LinkedIn URL"
                name="linkedin_url"
                onChange={handleFieldChange}
                placeholder="https://linkedin.com/in/username"
                required
                type="url"
                value={formData.linkedin_url}
              />
            </div>

            <label className="mt-5 block">
              <span className="mb-2 block text-sm font-semibold text-slate-800">
                Resume
              </span>
              <input
                accept=".pdf,application/pdf"
                className="block w-full rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-700 file:mr-4 file:rounded-full file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white"
                name="resume"
                onChange={handleFieldChange}
                required
                type="file"
              />
              <span className="mt-2 block text-xs font-medium text-slate-500">
                PDF only
              </span>
            </label>

            <div className="mt-6 rounded-3xl border border-slate-200 bg-slate-50 p-5">
              <p className="text-sm font-semibold text-slate-900">
                Policy acknowledgement
              </p>
              <label className="mt-4 flex items-start gap-3">
                <input
                  checked={formData.informationConfirmed}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-400"
                  name="informationConfirmed"
                  onChange={handleFieldChange}
                  required
                  type="checkbox"
                />
                <span className="text-sm leading-7 text-slate-700">
                  I confirm that all information provided is correct.
                </span>
              </label>
              <label className="mt-4 flex items-start gap-3">
                <input
                  checked={formData.verificationConsent}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-400"
                  name="verificationConsent"
                  onChange={handleFieldChange}
                  required
                  type="checkbox"
                />
                <span className="text-sm leading-7 text-slate-700">
                  I allow the recruiter to verify my information through the
                  websites and apps I provided.
                </span>
              </label>
            </div>

            {submissionState.message ? (
              <div
                className={`mt-6 rounded-2xl border px-4 py-3 text-sm font-medium ${
                  submissionState.status === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                    : submissionState.status === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-900'
                      : 'border-amber-200 bg-amber-50 text-amber-900'
                }`}
              >
                {submissionState.message}
              </div>
            ) : null}

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <button
                className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                disabled={
                  submissionState.status === 'submitting' ||
                  jobsState.status === 'loading' ||
                  jobsState.jobs.length === 0
                }
                type="submit"
              >
                {submissionState.status === 'submitting'
                  ? 'Submitting...'
                  : 'Submit application'}
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  )
}

export default ApplyPage
