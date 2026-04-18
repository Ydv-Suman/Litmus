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
  const [loggedInUser, setLoggedInUser] = useState(null)

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
      message: 'Logging in...',
    })

    try {
      const response = await loginHrUser(formData)
      const user = response.user || null
      setLoggedInUser(user)
      if (user) {
        localStorage.setItem('hr_user', JSON.stringify(user))
        navigate('/hr/dashboard')
      }
      setRequestState({
        status: 'success',
        message: response.message || 'Login successful.',
      })
    } catch (error) {
      setLoggedInUser(null)
      setRequestState({
        status: 'error',
        message: error.message || 'Failed to log in.',
      })
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(167,243,208,0.34),transparent_24%),linear-gradient(135deg,#f3fff8_0%,#f3fbff_55%,#eef6f9_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-4xl">
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/85 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur"
          to="/"
        >
          &larr; Back to portal
        </Link>

        <section className="mt-6 rounded-[2rem] border border-emerald-200/80 bg-white/90 p-8 shadow-[0_28px_80px_rgba(15,23,42,0.12)] backdrop-blur">
          <p className="text-xs font-extrabold uppercase tracking-[0.28em] text-emerald-800">
            HR Login
          </p>
          <h1 className="mt-3 text-3xl font-black sm:text-4xl">
            Return to your hiring workspace
          </h1>

          <form className="mt-8 max-w-xl" onSubmit={handleSubmit}>
            <div className="grid gap-5">
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

            {loggedInUser ? (
              <div className="mt-6 rounded-3xl border border-slate-200 bg-slate-50 p-5 text-sm leading-7 text-slate-700">
                Signed in as <strong>{loggedInUser.full_name}</strong> from{' '}
                <strong>{loggedInUser.company_name}</strong> in the{' '}
                <strong>{loggedInUser.department}</strong> team.
              </div>
            ) : null}

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <button
                className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                disabled={requestState.status === 'submitting'}
                type="submit"
              >
                {requestState.status === 'submitting' ? 'Logging in...' : 'Log in'}
              </button>
              <Link className="text-sm font-semibold text-slate-600 underline-offset-4 hover:underline" to="/hr/signup">
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
