import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getAssessment } from '../services/api'

function normalizeOptions(options) {
  if (!options || typeof options !== 'object') {
    return null
  }

  const ordered = ['A', 'B', 'C', 'D']
  return ordered
    .filter((key) => key in options)
    .map((key) => ({ key, value: String(options[key] ?? '') }))
    .filter((entry) => entry.value.trim().length > 0)
}

function AssessmentPage() {
  const { token } = useParams()
  const [state, setState] = useState({
    status: 'loading',
    message: 'Loading assessment...',
    payload: null,
  })

  useEffect(() => {
    if (!token) {
      setState({
        status: 'error',
        message: 'Missing assessment token.',
        payload: null,
      })
      return
    }

    let active = true

    setState({
      status: 'loading',
      message: 'Loading assessment...',
      payload: null,
    })

    getAssessment(token)
      .then((payload) => {
        if (!active) return
        setState({
          status: 'success',
          message: '',
          payload,
        })
      })
      .catch((error) => {
        if (!active) return
        setState({
          status: 'error',
          message: error.message || 'Unable to load assessment.',
          payload: null,
        })
      })

    return () => {
      active = false
    }
  }, [token])

  const assessment = state.payload?.assessment ?? null
  const mcq = useMemo(() => {
    const items = assessment?.part1_mcq
    return Array.isArray(items) ? items : []
  }, [assessment])
  const coding = assessment?.part2_coding ?? null
  const meta = assessment?.meta ?? null

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.22),transparent_32%),linear-gradient(135deg,#f8f5ee_0%,#eef4f8_50%,#dfe7f2_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-5xl">
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur"
          to="/"
        >
          &larr; Back to portal
        </Link>

        <section className="mt-6 rounded-[2rem] border border-slate-200 bg-white/85 p-8 shadow-[0_28px_80px_rgba(15,23,42,0.12)] backdrop-blur">
          <div className="mb-6">
            <p className="text-xs font-extrabold uppercase tracking-[0.26em] text-sky-800">
              Technical Assessment
            </p>
            <h1 className="mt-3 text-3xl font-black sm:text-4xl">
              {meta?.job_title ? meta.job_title : 'Assessment'}
            </h1>
            {meta?.experience_level ? (
              <p className="mt-2 text-sm font-semibold text-slate-600">
                Level: {meta.experience_level}
              </p>
            ) : null}
          </div>

          {state.status !== 'success' ? (
            <div
              className={`rounded-2xl border px-4 py-3 text-sm font-medium ${
                state.status === 'error'
                  ? 'border-rose-200 bg-rose-50 text-rose-900'
                  : 'border-amber-200 bg-amber-50 text-amber-900'
              }`}
            >
              {state.message}
            </div>
          ) : null}

          {state.status === 'success' && assessment ? (
            <div className="space-y-8">
              <section>
                <h2 className="text-xl font-black text-slate-900">
                  Part 1 — Knowledge MCQ
                </h2>
                <p className="mt-2 text-sm text-slate-600">
                  Choose the best answer for each question. (Answer key is not shown.)
                </p>

                <div className="mt-6 space-y-5">
                  {mcq.map((q) => {
                    const options = normalizeOptions(q.options)
                    return (
                      <article
                        key={q.id ?? q.question}
                        className="rounded-3xl border border-slate-200 bg-slate-50 p-5"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-3">
                          <p className="text-sm font-extrabold uppercase tracking-[0.22em] text-slate-500">
                            Question {q.id ?? ''}
                          </p>
                          {q.topic ? (
                            <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                              {q.topic}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-3 whitespace-pre-wrap text-base font-semibold text-slate-900">
                          {q.question}
                        </p>
                        {options ? (
                          <ul className="mt-4 space-y-2">
                            {options.map((opt) => (
                              <li
                                key={opt.key}
                                className="rounded-2xl border border-white/60 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm"
                              >
                                <span className="mr-2 font-black">{opt.key})</span>
                                {opt.value}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </article>
                    )
                  })}
                </div>
              </section>

              <section>
                <h2 className="text-xl font-black text-slate-900">
                  Part 2 — Coding Challenge
                </h2>
                {coding ? (
                  <div className="mt-4 rounded-3xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-lg font-black text-slate-900">
                        {coding.title}
                      </p>
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                        {coding.language ? (
                          <span className="rounded-full bg-white px-3 py-1">
                            {coding.language}
                          </span>
                        ) : null}
                        {coding.time_limit_minutes ? (
                          <span className="rounded-full bg-white px-3 py-1">
                            {coding.time_limit_minutes} minutes
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {coding.instructions ? (
                      <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                        {coding.instructions}
                      </p>
                    ) : null}

                    {coding.starter_code ? (
                      <div className="mt-5">
                        <p className="text-sm font-bold text-slate-900">
                          Starter code
                        </p>
                        <pre className="mt-2 overflow-x-auto rounded-2xl bg-slate-900 p-4 text-xs text-slate-50">
                          <code>{coding.starter_code}</code>
                        </pre>
                      </div>
                    ) : null}

                    {Array.isArray(coding.test_cases) && coding.test_cases.length ? (
                      <div className="mt-5">
                        <p className="text-sm font-bold text-slate-900">
                          Test cases
                        </p>
                        <ul className="mt-2 space-y-2 text-sm text-slate-700">
                          {coding.test_cases.map((tc) => (
                            <li
                              key={tc.name ?? tc.description}
                              className="rounded-2xl border border-white/70 bg-white px-4 py-3"
                            >
                              <span className="font-black">{tc.name}:</span>{' '}
                              {tc.description}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-900">
                    Coding challenge not found in this assessment payload.
                  </div>
                )}
              </section>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  )
}

export default AssessmentPage

