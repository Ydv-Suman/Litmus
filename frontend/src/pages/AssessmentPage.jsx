import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getAssessment, submitAssessmentAnswers } from '../services/api'

function normalizeOptions(options) {
  if (!options || typeof options !== 'object') return null
  return ['A', 'B', 'C', 'D']
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
  const [answers, setAnswers] = useState({})
  const [submitState, setSubmitState] = useState({ status: 'idle', result: null, message: '' })

  useEffect(() => {
    if (!token) {
      setState({ status: 'error', message: 'Missing assessment token.', payload: null })
      return
    }
    let active = true
    setState({ status: 'loading', message: 'Loading assessment...', payload: null })
    getAssessment(token)
      .then((payload) => {
        if (!active) return
        setState({ status: 'success', message: '', payload })
        if (payload.already_submitted) {
          setSubmitState({ status: 'done', result: null, message: 'You have already submitted this assessment.' })
        }
      })
      .catch((error) => {
        if (!active) return
        setState({ status: 'error', message: error.message || 'Unable to load assessment.', payload: null })
      })
    return () => { active = false }
  }, [token])

  const assessment = state.payload?.assessment ?? null
  const mcq = useMemo(() => {
    const items = assessment?.part1_mcq
    return Array.isArray(items) ? items : []
  }, [assessment])
  const coding = assessment?.part2_coding ?? null
  const meta = assessment?.meta ?? null

  const handleAnswer = (questionId, letter) => {
    if (submitState.status === 'done' || submitState.status === 'submitting') return
    setAnswers((prev) => ({ ...prev, [String(questionId)]: letter }))
  }

  const handleSubmit = async () => {
    if (mcq.length > 0 && Object.keys(answers).length < mcq.length) {
      setSubmitState({ status: 'error', result: null, message: `Please answer all ${mcq.length} MCQ questions before submitting.` })
      return
    }
    setSubmitState({ status: 'submitting', result: null, message: 'Submitting...' })
    try {
      const result = await submitAssessmentAnswers(token, answers)
      setSubmitState({ status: 'done', result, message: result.message || 'Submitted!' })
    } catch (err) {
      setSubmitState({ status: 'error', result: null, message: err.message || 'Submission failed.' })
    }
  }

  const alreadyDone = submitState.status === 'done'

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

          {/* Score result card */}
          {alreadyDone && submitState.result ? (
            <div className="mb-8 rounded-3xl border border-emerald-200 bg-emerald-50 p-6">
              <p className="text-xs font-extrabold uppercase tracking-[0.26em] text-emerald-800">
                Assessment Submitted
              </p>
              <p className="mt-3 text-4xl font-black text-emerald-900">
                {submitState.result.mcq_score} / {submitState.result.mcq_total}
              </p>
              <p className="mt-1 text-sm text-emerald-700">
                {submitState.result.correct} of {submitState.result.total_questions} MCQ questions correct
              </p>
            </div>
          ) : null}

          {alreadyDone && !submitState.result ? (
            <div className="mb-8 rounded-3xl border border-sky-200 bg-sky-50 px-5 py-4 text-sm font-medium text-sky-900">
              {submitState.message}
            </div>
          ) : null}

          {state.status === 'success' && assessment ? (
            <div className="space-y-8">
              <section>
                <h2 className="text-xl font-black text-slate-900">Part 1 — Knowledge MCQ</h2>
                <p className="mt-2 text-sm text-slate-600">
                  {alreadyDone
                    ? 'Your answers are locked.'
                    : 'Choose the best answer for each question.'}
                </p>

                <div className="mt-6 space-y-5">
                  {mcq.map((q) => {
                    const options = normalizeOptions(q.options)
                    const selected = answers[String(q.id)]
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
                            {options.map((opt) => {
                              const isSelected = selected === opt.key
                              return (
                                <li key={opt.key}>
                                  <button
                                    type="button"
                                    disabled={alreadyDone}
                                    onClick={() => handleAnswer(q.id, opt.key)}
                                    className={`w-full rounded-2xl border px-4 py-3 text-left text-sm shadow-sm transition-colors ${
                                      isSelected
                                        ? 'border-sky-400 bg-sky-50 font-semibold text-sky-900 ring-2 ring-sky-200'
                                        : 'border-white/60 bg-white text-slate-800 hover:border-slate-300 hover:bg-slate-50'
                                    } disabled:cursor-default`}
                                  >
                                    <span className="mr-2 font-black">{opt.key})</span>
                                    {opt.value}
                                  </button>
                                </li>
                              )
                            })}
                          </ul>
                        ) : null}
                      </article>
                    )
                  })}
                </div>
              </section>

              <section>
                <h2 className="text-xl font-black text-slate-900">Part 2 — Coding Challenge</h2>
                {coding ? (
                  <div className="mt-4 rounded-3xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-lg font-black text-slate-900">{coding.title}</p>
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                        {coding.language ? (
                          <span className="rounded-full bg-white px-3 py-1">{coding.language}</span>
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
                        <p className="text-sm font-bold text-slate-900">Starter code</p>
                        <pre className="mt-2 overflow-x-auto rounded-2xl bg-slate-900 p-4 text-xs text-slate-50">
                          <code>{coding.starter_code}</code>
                        </pre>
                      </div>
                    ) : null}
                    {Array.isArray(coding.test_cases) && coding.test_cases.length ? (
                      <div className="mt-5">
                        <p className="text-sm font-bold text-slate-900">Test cases</p>
                        <ul className="mt-2 space-y-2 text-sm text-slate-700">
                          {coding.test_cases.map((tc) => (
                            <li
                              key={tc.name ?? tc.description}
                              className="rounded-2xl border border-white/70 bg-white px-4 py-3"
                            >
                              <span className="font-black">{tc.name}:</span> {tc.description}
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

              {/* Submit section */}
              {!alreadyDone ? (
                <div className="border-t border-slate-200 pt-6">
                  {submitState.message && submitState.status === 'error' ? (
                    <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-900">
                      {submitState.message}
                    </div>
                  ) : null}
                  <div className="flex items-center gap-4">
                    <button
                      type="button"
                      disabled={submitState.status === 'submitting'}
                      onClick={handleSubmit}
                      className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {submitState.status === 'submitting' ? 'Submitting...' : 'Submit MCQ Answers'}
                    </button>
                    <p className="text-xs text-slate-500">
                      {Object.keys(answers).length} / {mcq.length} answered
                    </p>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </main>
  )
}

export default AssessmentPage
