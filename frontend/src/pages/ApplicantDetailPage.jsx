import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'

import { getHrApplicationDetail } from '../services/api'

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

function ScoreBar({ score, max, color = 'bg-emerald-500' }) {
  const pct = max > 0 ? Math.min(100, (score / max) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-slate-100">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-black text-slate-700 w-16 text-right">
        {score} / {max}
      </span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-6 shadow-sm">
      <h2 className="text-xs font-extrabold uppercase tracking-[0.26em] text-slate-400 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function ResumeSection({ resumeDetail, resumePoints, pipelineMax }) {
  const parsed = resumeDetail?.parsed
  const match = resumeDetail?.reality_match

  if (!parsed && !match) {
    return (
      <Section title="Resume & Job Match">
        {resumePoints != null ? (
          <>
            <ScoreBar score={resumePoints} max={20} color="bg-emerald-500" />
            <p className="mt-3 text-xs text-slate-400">Detailed breakdown not available — applicant was processed before analysis storage was enabled.</p>
          </>
        ) : (
          <p className="text-sm text-slate-400">No resume data stored.</p>
        )}
      </Section>
    )
  }

  return (
    <Section title="Resume & Job Match">
      {match && (
        <div className="mb-5">
          <ScoreBar
            score={match.total_points ?? 0}
            max={match.max_points ?? 20}
            color="bg-emerald-500"
          />
          {match.red_flags?.length > 0 && (
            <ul className="mt-3 space-y-1">
              {match.red_flags.map((f, i) => (
                <li key={i} className="flex gap-2 text-xs text-rose-600">
                  <span className="shrink-0">✗</span>{f}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {parsed && (
        <div className="space-y-4 text-sm">
          {parsed.name && (
            <div>
              <p className="font-black text-slate-900 text-base">{parsed.name}</p>
              {parsed.current_title && <p className="text-slate-500">{parsed.current_title}</p>}
            </div>
          )}
          {parsed.summary && (
            <p className="text-slate-700 leading-6">{parsed.summary}</p>
          )}

          {parsed.skills && Object.keys(parsed.skills).length > 0 && (
            <div>
              <p className="font-semibold text-slate-600 mb-2">Skills</p>
              <div className="flex flex-wrap gap-2">
                {Object.values(parsed.skills).flat().map((s, i) => (
                  <span key={i} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {parsed.experience?.length > 0 && (
            <div>
              <p className="font-semibold text-slate-600 mb-2">Experience</p>
              <ul className="space-y-2">
                {parsed.experience.slice(0, 4).map((exp, i) => (
                  <li key={i} className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                    <p className="font-semibold text-slate-800">{exp.title} {exp.company ? `@ ${exp.company}` : ''}</p>
                    <p className="text-xs text-slate-400">{exp.start_date} – {exp.end_date ?? 'Present'}</p>
                    {exp.description && <p className="mt-1 text-xs text-slate-600 line-clamp-2">{exp.description}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {match?.skills_vs_job?.details?.length > 0 && (
            <div>
              <p className="font-semibold text-slate-600 mb-2">Skill Match Breakdown</p>
              <div className="flex flex-wrap gap-2">
                {match.skills_vs_job.details.map((d, i) => (
                  <span key={i} className={`rounded-full px-3 py-1 text-xs font-medium ${d.found_on_resume ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-700'}`}>
                    {d.found_on_resume ? '✓' : '✗'} {d.skill}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Section>
  )
}

function GitHubSection({ githubDetail, githubUrl }) {
  if (!githubDetail) {
    return (
      <Section title="GitHub Analysis">
        {githubUrl ? (
          <>
            <a href={githubUrl} target="_blank" rel="noreferrer"
              className="text-sm font-semibold text-emerald-700 underline-offset-2 hover:underline">
              {githubUrl}
            </a>
            <p className="mt-2 text-xs text-slate-400">Detailed analysis not available — applicant was processed before analysis storage was enabled.</p>
          </>
        ) : (
          <p className="text-sm text-slate-400">No GitHub profile provided by this applicant.</p>
        )}
      </Section>
    )
  }

  const score = githubDetail.credibility_score ?? githubDetail.score ?? null
  const maxScore = githubDetail.max_score ?? githubDetail.credibility_max ?? 100

  return (
    <Section title="GitHub Analysis">
      {score != null && (
        <div className="mb-5">
          <ScoreBar score={score} max={maxScore} color="bg-sky-500" />
        </div>
      )}
      <div className="space-y-3 text-sm">
        {githubDetail.summary && (
          <p className="text-slate-700 leading-6">{githubDetail.summary}</p>
        )}
        {githubDetail.username && (
          <p className="text-slate-500">Username: <span className="font-semibold text-slate-800">@{githubDetail.username}</span></p>
        )}
        {githubDetail.public_repos != null && (
          <p className="text-slate-500">Public repos: <span className="font-semibold text-slate-800">{githubDetail.public_repos}</span></p>
        )}
        {githubDetail.top_languages?.length > 0 && (
          <div>
            <p className="font-semibold text-slate-600 mb-2">Top Languages</p>
            <div className="flex flex-wrap gap-2">
              {githubDetail.top_languages.map((lang, i) => (
                <span key={i} className="rounded-full bg-sky-100 px-3 py-1 text-xs font-medium text-sky-800">{lang}</span>
              ))}
            </div>
          </div>
        )}
        {githubDetail.strengths?.length > 0 && (
          <ul className="space-y-1">
            {githubDetail.strengths.map((s, i) => (
              <li key={i} className="flex gap-2 text-xs text-emerald-700"><span>✓</span>{s}</li>
            ))}
          </ul>
        )}
        {githubDetail.weaknesses?.length > 0 && (
          <ul className="space-y-1 mt-2">
            {githubDetail.weaknesses.map((w, i) => (
              <li key={i} className="flex gap-2 text-xs text-rose-600"><span>✗</span>{w}</li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  )
}

function LinkedInSection({ linkedinDetail, linkedinPoints, linkedinUrl }) {
  const analysis = linkedinDetail?.analysis
  const screening = linkedinDetail?.screening
  const isMock = analysis?.data_source === 'mock'
  const hasRealAnalysis = analysis && !isMock

  return (
    <Section title="LinkedIn">
      {linkedinPoints != null && (
        <div className="mb-5">
          <ScoreBar score={linkedinPoints} max={5} color="bg-blue-500" />
          <p className="mt-1 text-xs text-slate-400">Score based on URL validation</p>
        </div>
      )}
      <div className="space-y-3 text-sm">
        {!linkedinUrl && <p className="text-slate-400">No LinkedIn URL provided by this applicant.</p>}
        {linkedinUrl && (
          <a href={linkedinUrl} target="_blank" rel="noreferrer"
            className="inline-block text-sm font-semibold text-blue-700 underline-offset-2 hover:underline">
            {linkedinUrl}
          </a>
        )}
        {screening?.evaluated === true && (
          <p className={`font-semibold ${screening.valid_profile_shape ? 'text-emerald-700' : 'text-rose-600'}`}>
            {screening.valid_profile_shape ? '✓ Valid LinkedIn profile URL' : '✗ URL did not match a typical LinkedIn profile pattern'}
          </p>
        )}
        {hasRealAnalysis && analysis.summary && (
          <p className="text-slate-700 leading-6">{analysis.summary}</p>
        )}
        {hasRealAnalysis && analysis.strengths?.length > 0 && (
          <ul className="space-y-1">
            {analysis.strengths.map((s, i) => (
              <li key={i} className="flex gap-2 text-xs text-emerald-700"><span>✓</span>{s}</li>
            ))}
          </ul>
        )}
        {hasRealAnalysis && analysis.weaknesses?.length > 0 && (
          <ul className="space-y-1 mt-2">
            {analysis.weaknesses.map((w, i) => (
              <li key={i} className="flex gap-2 text-xs text-rose-600"><span>✗</span>{w}</li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  )
}

function AssessmentSection({ assessment, assessmentScore, assessmentSubmittedAt }) {
  if (!assessment) {
    return (
      <Section title="Assessment">
        <p className="text-sm text-slate-400">Assessment not yet taken.</p>
      </Section>
    )
  }

  const wasSubmitted = !!assessmentSubmittedAt
  const mcq = assessment.part1_mcq ?? []
  const grading = assessment.grading_notes ?? {}

  return (
    <Section title="Assessment Results">
      {!wasSubmitted ? (
        <p className="text-sm text-slate-400">Assessment was sent but not yet submitted by the candidate.</p>
      ) : (
        <>
          {assessmentScore != null && (
            <div className="mb-6">
              <ScoreBar score={assessmentScore} max={grading.mcq_total ?? 50} color="bg-violet-500" />
              <p className="mt-1 text-xs text-slate-400">MCQ score · coding challenge not auto-graded</p>
            </div>
          )}

          <div className="space-y-4">
            {mcq.map((q, i) => {
          const candidateAnswer = q.candidate_answer
          const correct = q.correct
          const isCorrect = candidateAnswer && correct && candidateAnswer.toUpperCase() === correct.toUpperCase()
          const wasAnswered = !!candidateAnswer

          return (
            <div key={q.id ?? i} className={`rounded-2xl border p-4 ${
              !wasAnswered ? 'border-slate-200 bg-slate-50' :
              isCorrect ? 'border-emerald-200 bg-emerald-50' : 'border-rose-200 bg-rose-50'
            }`}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <p className="text-xs font-extrabold uppercase tracking-wide text-slate-400">Q{q.id}</p>
                <div className="flex gap-2 text-xs font-semibold shrink-0">
                  {wasAnswered ? (
                    <>
                      <span className={isCorrect ? 'text-emerald-700' : 'text-rose-600'}>
                        {isCorrect ? '✓ Correct' : '✗ Wrong'}
                      </span>
                      {!isCorrect && correct && (
                        <span className="text-slate-500">Correct: {correct}</span>
                      )}
                    </>
                  ) : (
                    <span className="text-slate-400">Not answered</span>
                  )}
                </div>
              </div>
              <p className="text-sm font-semibold text-slate-900 mb-3">{q.question}</p>
              {q.options && (
                <ul className="space-y-1 mb-3">
                  {['A', 'B', 'C', 'D'].filter(k => q.options[k]).map(k => (
                    <li key={k} className={`rounded-xl px-3 py-2 text-xs ${
                      k === correct ? 'bg-emerald-100 font-semibold text-emerald-800' :
                      k === candidateAnswer && !isCorrect ? 'bg-rose-100 text-rose-700' :
                      'bg-white text-slate-700'
                    }`}>
                      <span className="font-black mr-1">{k})</span>{q.options[k]}
                    </li>
                  ))}
                </ul>
              )}
              {q.explanation && (
                <p className="text-xs text-slate-500 italic">{q.explanation}</p>
              )}
            </div>
          )
        })}
          </div>
        </>
      )}
    </Section>
  )
}

function ApplicantDetailPage() {
  const { userId, applicationId } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const stored = localStorage.getItem('hr_user')
    if (!stored) { navigate('/hr/login', { replace: true }); return }

    const user = JSON.parse(stored)
    if (String(user.id) !== String(userId)) { navigate('/hr/dashboard', { replace: true }); return }

    getHrApplicationDetail(userId, applicationId)
      .then((data) => { setDetail(data); setLoading(false) })
      .catch((err) => { setError(err.message || 'Failed to load.'); setLoading(false) })
  }, [userId, applicationId, navigate])

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(167,243,208,0.34),transparent_24%),linear-gradient(135deg,#f3fff8_0%,#f3fbff_55%,#eef6f9_100%)] px-4 py-8 text-slate-900 sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-4xl">
        <Link
          to="/hr/dashboard"
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/85 px-4 py-2 text-sm font-semibold text-slate-700 backdrop-blur hover:bg-slate-50"
        >
          &larr; Back to dashboard
        </Link>

        {loading && <p className="mt-8 text-sm text-slate-500">Loading...</p>}
        {error && <p className="mt-8 text-sm text-rose-600">{error}</p>}

        {detail && (
          <div className="mt-6 space-y-5">
            {/* Header card */}
            <div className="rounded-[2rem] border border-emerald-200/80 bg-white/90 p-6 shadow-[0_28px_80px_rgba(15,23,42,0.10)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-black text-slate-900">{detail.full_name}</h1>
                  <p className="mt-1 text-sm text-slate-500">{detail.email} · {detail.phone}</p>
                  <p className="mt-1 text-sm font-semibold text-slate-700">{detail.job.title} — {detail.job.department}</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLES[detail.status] ?? 'bg-slate-100 text-slate-700'}`}>
                  {STATUS_LABELS[detail.status] ?? detail.status}
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                {detail.github_url && (
                  <a href={detail.github_url} target="_blank" rel="noreferrer"
                    className="rounded-full border border-slate-200 px-4 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">
                    GitHub &rarr;
                  </a>
                )}
                {detail.linkedin_url && (
                  <a href={detail.linkedin_url} target="_blank" rel="noreferrer"
                    className="rounded-full border border-slate-200 px-4 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">
                    LinkedIn &rarr;
                  </a>
                )}
              </div>
            </div>

            <ResumeSection
              resumeDetail={detail.resume_detail}
              resumePoints={detail.pipeline_resume_points}
              pipelineMax={detail.pipeline_max}
            />
            <GitHubSection
              githubDetail={detail.github_detail}
              githubUrl={detail.github_url}
            />
            <LinkedInSection
              linkedinDetail={detail.linkedin_detail}
              linkedinPoints={detail.pipeline_linkedin_points}
              linkedinUrl={detail.linkedin_url}
            />
            <AssessmentSection
              assessment={detail.assessment}
              assessmentScore={detail.assessment_score}
              assessmentSubmittedAt={detail.assessment_submitted_at}
            />
          </div>
        )}
      </div>
    </main>
  )
}

export default ApplicantDetailPage
