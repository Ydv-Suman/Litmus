import { useEffect, useMemo, useState } from 'react'
import Editor from '@monaco-editor/react'
import { Link, useParams } from 'react-router-dom'

import {
  getAssessment,
  runAssessmentCode,
  submitAssessment,
} from '../services/api'

function normalizeOptions(options) {
  if (!options || typeof options !== 'object') {
    return []
  }

  return ['A', 'B', 'C', 'D']
    .filter((key) => key in options)
    .map((key) => ({ key, value: String(options[key] ?? '') }))
    .filter((entry) => entry.value.trim())
}

function editorLanguage(language) {
  const normalized = String(language || '').toLowerCase()
  if (normalized === 'python') return 'python'
  return 'javascript'
}

function stringifyValue(value) {
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

function AssessmentPage() {
  const { token } = useParams()
  const [pageState, setPageState] = useState({
    status: 'loading',
    message: 'Loading assessment...',
    payload: null,
  })
  const [mcqAnswers, setMcqAnswers] = useState({})
  const [codingAnswer, setCodingAnswer] = useState('')
  const [runState, setRunState] = useState({
    status: 'idle',
    message: '',
    result: null,
  })
  const [submitState, setSubmitState] = useState({
    status: 'idle',
    message: '',
  })

  useEffect(() => {
    if (!token) {
      setPageState({
        status: 'error',
        message: 'Missing assessment token.',
        payload: null,
      })
      return
    }

    let active = true
    setPageState({
      status: 'loading',
      message: 'Loading assessment...',
      payload: null,
    })
    setRunState({
      status: 'idle',
      message: '',
      result: null,
    })
    setSubmitState({
      status: 'idle',
      message: '',
    })

    getAssessment(token)
      .then((payload) => {
        if (!active) return

        const submission = payload.candidate_submission || {}
        const assessment = payload.assessment || {}
        const coding = assessment.part2_coding || {}

        setMcqAnswers(submission.mcq_answers || {})
        setCodingAnswer(submission.coding_answer || coding.starter_code || '')
        setPageState({
          status: 'success',
          message: '',
          payload,
        })
      })
      .catch((error) => {
        if (!active) return
        setPageState({
          status: 'error',
          message: error.message || 'Unable to load assessment.',
          payload: null,
        })
      })

    return () => {
      active = false
    }
  }, [token])

  const assessment = pageState.payload?.assessment ?? null
  const candidateSubmission = pageState.payload?.candidate_submission ?? null
  const assessmentStatus = pageState.payload?.status ?? ''
  const storedScores = pageState.payload?.scores ?? null
  const mcq = useMemo(() => {
    const items = assessment?.part1_mcq
    return Array.isArray(items) ? items : []
  }, [assessment])
  const coding = assessment?.part2_coding ?? null
  const meta = assessment?.meta ?? null
  const codingLanguage = coding?.language || 'javascript'
  const codingTests = Array.isArray(coding?.test_cases) ? coding.test_cases : []
  const hasRunnableTests = codingTests.every(
    (testCase) =>
      testCase &&
      Object.prototype.hasOwnProperty.call(testCase, 'input') &&
      Object.prototype.hasOwnProperty.call(testCase, 'expected_output'),
  )

  const handleMcqAnswerChange = (questionId, value) => {
    setMcqAnswers((current) => ({
      ...current,
      [String(questionId)]: value,
    }))
  }

  const handleRunCode = async () => {
    if (!token || !coding) return
    setRunState({
      status: 'running',
      message: 'Running public test cases...',
      result: null,
    })

    try {
      const response = await runAssessmentCode(token, {
        coding_answer: codingAnswer,
        coding_language: codingLanguage,
      })
      setRunState({
        status: response.result?.status === 'ok' ? 'success' : 'error',
        message:
          response.result?.status === 'ok'
            ? 'Code run completed.'
            : response.result?.error || 'Code run failed.',
        result: response.result || null,
      })
    } catch (error) {
      setRunState({
        status: 'error',
        message: error.message || 'Unable to run code.',
        result: null,
      })
    }
  }

  const handleSubmitAssessment = async () => {
    if (!token || !assessment) return
    setSubmitState({
      status: 'submitting',
      message: 'Submitting your answers...',
    })

    try {
      const response = await submitAssessment(token, {
        mcq_answers: mcqAnswers,
        coding_answer: codingAnswer,
        coding_language: codingLanguage,
      })
      setSubmitState({
        status: 'success',
        message: response.message || 'Assessment submitted successfully.',
      })
      setPageState((current) =>
        current.payload
          ? {
              ...current,
              payload: {
                ...current.payload,
                candidate_submission: {
                  mcq_answers: mcqAnswers,
                  coding_answer: codingAnswer,
                  coding_language: codingLanguage,
                  submitted_at: response.submitted_at,
                },
                scores: response.scores || current.payload.scores,
                status: response.status || 'assessment_submitted',
              },
            }
          : current,
      )
    } catch (error) {
      setSubmitState({
        status: 'error',
        message: error.message || 'Unable to submit assessment.',
      })
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.22),transparent_32%),linear-gradient(135deg,#f8f5ee_0%,#eef4f8_50%,#dfe7f2_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-6xl">
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur"
          to="/"
        >
          &larr; Back to portal
        </Link>

        <section className="mt-6 rounded-[2rem] border border-slate-200 bg-white/85 p-8 shadow-[0_28px_80px_rgba(15,23,42,0.12)] backdrop-blur">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
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
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
              Status: {assessmentStatus || 'pending'}
              {candidateSubmission?.submitted_at ? (
                <div className="mt-1 text-xs font-medium text-slate-500">
                  Last submitted:{' '}
                  {new Date(candidateSubmission.submitted_at).toLocaleString()}
                </div>
              ) : null}
            </div>
          </div>

          {pageState.status !== 'success' ? (
            <div
              className={`rounded-2xl border px-4 py-3 text-sm font-medium ${
                pageState.status === 'error'
                  ? 'border-rose-200 bg-rose-50 text-rose-900'
                  : 'border-amber-200 bg-amber-50 text-amber-900'
              }`}
            >
              {pageState.message}
            </div>
          ) : null}

          {pageState.status === 'success' && assessment ? (
            <div className="space-y-8">
              <section>
                <h2 className="text-xl font-black text-slate-900">
                  Part 1 — Knowledge MCQ
                </h2>
                <p className="mt-2 text-sm text-slate-600">
                  Answer each question based on the role requirements. Your
                  selections are saved only when you submit.
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
                        <fieldset className="mt-4 space-y-2">
                          {options.map((opt) => (
                            <label
                              key={opt.key}
                              className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/60 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm"
                            >
                              <input
                                checked={mcqAnswers[String(q.id)] === opt.key}
                                className="mt-1"
                                name={`mcq-${q.id}`}
                                onChange={() => handleMcqAnswerChange(q.id, opt.key)}
                                type="radio"
                                value={opt.key}
                              />
                              <span>
                                <span className="mr-2 font-black">{opt.key})</span>
                                {opt.value}
                              </span>
                            </label>
                          ))}
                        </fieldset>
                      </article>
                    )
                  })}
                </div>
              </section>

              <section>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-black text-slate-900">
                      Part 2 — Coding Challenge
                    </h2>
                    <p className="mt-2 text-sm text-slate-600">
                      Write your solution in Monaco, run public tests, then
                      submit the final answer.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                    {coding?.language ? (
                      <span className="rounded-full bg-slate-100 px-3 py-1">
                        {coding.language}
                      </span>
                    ) : null}
                    {coding?.time_limit_minutes ? (
                      <span className="rounded-full bg-slate-100 px-3 py-1">
                        {coding.time_limit_minutes} minutes
                      </span>
                    ) : null}
                  </div>
                </div>

                {coding ? (
                  <div className="mt-4 rounded-3xl border border-slate-200 bg-slate-50 p-5">
                    <p className="text-lg font-black text-slate-900">
                      {coding.title}
                    </p>

                    {coding.instructions ? (
                      <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                        {coding.instructions}
                      </p>
                    ) : null}

                    <div className="mt-6 overflow-hidden rounded-3xl border border-slate-900/10">
                      <Editor
                        defaultLanguage={editorLanguage(codingLanguage)}
                        height="420px"
                        language={editorLanguage(codingLanguage)}
                        onChange={(value) => setCodingAnswer(value || '')}
                        options={{
                          fontSize: 14,
                          minimap: { enabled: false },
                          padding: { top: 16 },
                          scrollBeyondLastLine: false,
                        }}
                        theme="vs-dark"
                        value={codingAnswer}
                      />
                    </div>

                    <div className="mt-5 flex flex-wrap items-center gap-3">
                      <button
                        className="rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={runState.status === 'running' || !hasRunnableTests}
                        onClick={handleRunCode}
                        type="button"
                      >
                        {runState.status === 'running'
                          ? 'Running tests...'
                          : 'Run public tests'}
                      </button>
                      {!hasRunnableTests ? (
                        <p className="text-sm text-slate-500">
                          Public test execution is not available for this
                          assessment payload yet.
                        </p>
                      ) : null}
                    </div>

                    {runState.message ? (
                      <div
                        className={`mt-4 rounded-2xl border px-4 py-3 text-sm font-medium ${
                          runState.status === 'success'
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                            : runState.status === 'error'
                              ? 'border-rose-200 bg-rose-50 text-rose-900'
                              : 'border-sky-200 bg-sky-50 text-sky-900'
                        }`}
                      >
                        {runState.message}
                      </div>
                    ) : null}

                    {runState.result?.results?.length ? (
                      <div className="mt-5">
                        <p className="text-sm font-bold text-slate-900">
                          Public test results
                        </p>
                        <ul className="mt-3 space-y-2">
                          {runState.result.results.map((testResult) => (
                            <li
                              key={testResult.name}
                              className={`rounded-2xl border px-4 py-3 text-sm ${
                                testResult.passed
                                  ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                                  : 'border-rose-200 bg-rose-50 text-rose-900'
                              }`}
                            >
                              <div className="font-semibold">
                                {testResult.name} —{' '}
                                {testResult.passed ? 'Passed' : 'Failed'}
                              </div>
                              <div className="mt-1 text-xs">
                                {testResult.description}
                              </div>
                              {!testResult.passed ? (
                                <div className="mt-2 text-xs">
                                  Expected:{' '}
                                  {stringifyValue(testResult.expected_output)} |
                                  {' '}Actual: {stringifyValue(testResult.actual)}
                                </div>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {codingTests.length ? (
                      <div className="mt-5">
                        <p className="text-sm font-bold text-slate-900">
                          Public test cases
                        </p>
                        <ul className="mt-2 space-y-2 text-sm text-slate-700">
                          {codingTests.map((tc) => (
                            <li
                              key={tc.name ?? tc.description}
                              className="rounded-2xl border border-white/70 bg-white px-4 py-3"
                            >
                              <div className="font-black">{tc.name}</div>
                              <div>{tc.description}</div>
                              {hasRunnableTests ? (
                                <div className="mt-2 text-xs text-slate-500">
                                  Input: {stringifyValue(tc.input)} | Expected:{' '}
                                  {stringifyValue(tc.expected_output)}
                                </div>
                              ) : null}
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

              {submitState.message ? (
                <div
                  className={`rounded-2xl border px-4 py-3 text-sm font-medium ${
                    submitState.status === 'success'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                      : submitState.status === 'error'
                        ? 'border-rose-200 bg-rose-50 text-rose-900'
                        : 'border-sky-200 bg-sky-50 text-sky-900'
                  }`}
                >
                  {submitState.message}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <button
                  className="rounded-full bg-sky-700 px-6 py-3 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={submitState.status === 'submitting'}
                  onClick={handleSubmitAssessment}
                  type="button"
                >
                  {submitState.status === 'submitting'
                    ? 'Submitting...'
                    : 'Submit assessment'}
                </button>
              </div>

              {storedScores ? (
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <h3 className="text-lg font-black text-slate-900">
                    Score Summary
                  </h3>
                  <div className="mt-4 grid gap-3 text-sm text-slate-700 sm:grid-cols-2">
                    <div className="rounded-2xl bg-white px-4 py-3">
                      MCQ: {storedScores.assessment_mcq_score ?? 0} /{' '}
                      {storedScores.assessment_mcq_max ?? 0}
                    </div>
                    <div className="rounded-2xl bg-white px-4 py-3">
                      Coding: {storedScores.assessment_coding_score ?? 0} /{' '}
                      {storedScores.assessment_coding_max ?? 0}
                    </div>
                    <div className="rounded-2xl bg-white px-4 py-3">
                      Assessment total:{' '}
                      {storedScores.assessment_total_score ?? 0} /{' '}
                      {storedScores.assessment_total_max ?? 0}
                    </div>
                    <div className="rounded-2xl bg-white px-4 py-3">
                      Final score: {storedScores.final_score ?? 0} /{' '}
                      {storedScores.final_score_max ?? 0}
                    </div>
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
