import { useState } from 'react'
import { Link } from 'react-router-dom'

import Field from '../components/Field'
import { signupHrUser } from '../services/api'

const initialFormData = {
  email: '',
  password: '',
  full_name: '',
  company_name: '',
  department: '',
  phone: '+1',
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

function HrSignupPage() {
  const [formData, setFormData] = useState(initialFormData)
  const [requestState, setRequestState] = useState({
    status: 'idle',
    message: '',
  })

  const handleChange = (event) => {
    const { name, value } = event.target
    const nextValue = name === 'phone' ? formatPhoneNumber(value) : value
    setFormData((current) => ({
      ...current,
      [name]: nextValue,
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setRequestState({
      status: 'submitting',
      message: 'Creating HR account...',
    })

    try {
      const response = await signupHrUser({
        ...formData,
        phone: formData.phone === '+1' ? null : formData.phone,
      })
      setRequestState({
        status: 'success',
        message: response.message || 'HR account created successfully.',
      })
      setFormData(initialFormData)
    } catch (error) {
      setRequestState({
        status: 'error',
        message: error.message || 'Failed to create HR account.',
      })
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(125,211,252,0.3),transparent_24%),linear-gradient(135deg,#f4fbff_0%,#eef6f9_45%,#edf7ef_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-5xl">
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/85 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur"
          to="/hr/login"
        >
          &larr; Back to login
        </Link>

        <section className="mt-6 rounded-[2rem] border border-sky-200/80 bg-white/85 p-8 shadow-[0_28px_80px_rgba(15,23,42,0.12)] backdrop-blur">
          <p className="text-xs font-extrabold uppercase tracking-[0.28em] text-sky-800">
            HR Signup
          </p>
          <h1 className="mt-3 text-3xl font-black sm:text-4xl">
            Create your hiring workspace
          </h1>

          <form className="mt-8" onSubmit={handleSubmit}>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field
                label="Full name"
                name="full_name"
                onChange={handleChange}
                placeholder="Suman Yadav"
                required
                value={formData.full_name}
              />
              <Field
                label="Work email"
                name="email"
                onChange={handleChange}
                placeholder="hr@company.com"
                required
                type="email"
                value={formData.email}
              />
              <Field
                label="Company name"
                name="company_name"
                onChange={handleChange}
                placeholder="Litmus"
                required
                value={formData.company_name}
              />
              <Field
                label="Department"
                name="department"
                onChange={handleChange}
                placeholder="Talent Acquisition"
                required
                value={formData.department}
              />
              <Field
                inputMode="tel"
                label="Phone"
                name="phone"
                onChange={handleChange}
                pattern="^\+1 \(\d{3}\) \d{3}-\d{4}$"
                placeholder="+1 (234) 567-8900"
                title="Phone number must be in the format +1 (111) 111-1111"
                value={formData.phone}
              />
            </div>

            <div className="mt-5 max-w-xl">
              <Field
                label="Password"
                name="password"
                onChange={handleChange}
                placeholder="At least 8 characters"
                required
                type="password"
                value={formData.password}
              />
            </div>

            {requestState.message ? (
              <div
                className={`mt-6 rounded-2xl border px-4 py-3 text-sm font-medium ${
                  requestState.status === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                    : requestState.status === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-900'
                      : 'border-sky-200 bg-sky-50 text-sky-900'
                }`}
              >
                {requestState.message}
              </div>
            ) : null}

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <button
                className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                disabled={requestState.status === 'submitting'}
                type="submit"
              >
                {requestState.status === 'submitting'
                  ? 'Creating...'
                  : 'Create account'}
              </button>
              <Link className="text-sm font-semibold text-slate-600 underline-offset-4 hover:underline" to="/hr/login">
                Already have an account? Log in
              </Link>
            </div>
          </form>
        </section>
      </div>
    </main>
  )
}

export default HrSignupPage
