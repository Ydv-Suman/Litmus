import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import Field from '../components/Field'
import { loginHrUser } from '../services/api'

const initialFormData = {
  email: '',
  password: '',
}

function HrLoginPage() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState(initialFormData)
  const [requestState, setRequestState] = useState({
    status: 'idle',
    message: '',
  })

  const handleChange = (event) => {
    const { name, value } = event.target
    setFormData((current) => ({
      ...current,
      [name]: value,
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setRequestState({
      status: 'submitting',
      message: 'Opening workspace…',
    })

    try {
      const response = await loginHrUser(formData)
      const user = response.user || null
      if (user) {
        localStorage.setItem('hr_user', JSON.stringify(user))
        navigate('/hr/dashboard', { replace: true })
      }
    } catch (error) {
      localStorage.removeItem('hr_user')
      setRequestState({
        status: 'error',
        message: error.message || 'Failed to log in.',
      })
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(34,197,94,0.10),transparent_18%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,0.12),transparent_24%),linear-gradient(180deg,#f4f0e8_0%,#f3f7f7_48%,#fafcfc_100%)] px-4 py-6 text-slate-900 sm:px-6 lg:px-8 lg:py-10">
      <div className="mx-auto max-w-xl">
        <div className="mb-5">
          <Link
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white"
            to="/"
          >
            &larr; Back to portal
          </Link>
        </div>

        <section className="rounded-[2rem] border border-slate-200/80 bg-white/92 p-6 shadow-[0_22px_70px_rgba(15,23,42,0.08)] backdrop-blur md:p-8">
          <p className="text-[11px] font-black uppercase tracking-[0.28em] text-cyan-700">
            HR Portal
          </p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950 md:text-4xl">
            Sign in
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Open your hiring workspace.
          </p>

          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
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
              label="Password"
              name="password"
              onChange={handleChange}
              placeholder="Your password"
              required
              type="password"
              value={formData.password}
            />

            {requestState.message ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
                  requestState.status === 'error'
                    ? 'border-rose-200 bg-rose-50 text-rose-900'
                    : 'border-cyan-200 bg-cyan-50 text-cyan-900'
                }`}
              >
                {requestState.message}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <button
                className="rounded-full bg-slate-950 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                disabled={requestState.status === 'submitting'}
                type="submit"
              >
                {requestState.status === 'submitting' ? 'Opening…' : 'Log in'}
              </button>
              <Link
                className="text-sm font-bold text-slate-600 underline-offset-4 hover:underline"
                to="/hr/signup"
              >
                Need an account? Sign up
              </Link>
            </div>
          </form>
        </section>
      </div>
    </main>
  )
}

export default HrLoginPage
