import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { getHrApplicationDetail } from '../services/api'

const STATUS_META = {
  submitted: {
    label: 'Submitted',
    pill: 'bg-sky-100 text-sky-800 border-sky-200',
  },
  screening_failed: {
    label: 'Screen Failed',
    pill: 'bg-rose-100 text-rose-800 border-rose-200',
  },
  assessment_invited: {
    label: 'Assessment Sent',
    pill: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  assessment_submitted: {
    label: 'Assessment Submitted',
    pill: 'bg-violet-100 text-violet-800 border-violet-200',
  },
  assessment_completed: {
    label: 'Assessment Done',
    pill: 'bg-violet-100 text-violet-800 border-violet-200',
  },
}

function StatusPill({ status }) {
  const meta = STATUS_META[status] || {
    label: status || 'Unknown',
    pill: 'bg-slate-100 text-slate-700 border-slate-200',
  }
  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold ${meta.pill}`}>
      {meta.label}
    </span>
  )
}

function ScoreBar({ score, max, tone = 'bg-cyan-500' }) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, Number(score || 0) / Number(max || 1))) : 0
  return (
    <div className="space-y-2">
      <div className="h-2 rounded-full bg-slate-100">
        <div className={`h-2 rounded-full ${tone}`} style={{ width: `${Math.round(ratio * 100)}%` }} />
      </div>
      <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
        <span>{score ?? 0} / {max ?? 0}</span>
        <span>{Math.round(ratio * 100)}%</span>
      </div>
    </div>
  )
}

function SectionFrame({ eyebrow, title, description, children, right }) {
  return (
    <section className="rounded-[2rem] border border-slate-200/80 bg-white/92 p-6 shadow-[0_28px_80px_rgba(15,23,42,0.08)] backdrop-blur">
      <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-start 2xl:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-black uppercase tracking-[0.28em] text-cyan-700">
            {eyebrow}
          </p>
          <h2 className="mt-2 text-2xl font-black text-slate-950">{title}</h2>
          {description ? (
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{description}</p>
          ) : null}
        </div>
        {right}
      </div>
      <div className="mt-6">{children}</div>
    </section>
  )
}

function MetricCard({ label, value, helper, accent }) {
  return (
    <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
      <div className={`h-1.5 w-16 rounded-full ${accent}`} />
      <p className="mt-4 text-3xl font-black text-slate-950">{value}</p>
      <p className="mt-1 text-sm font-semibold text-slate-700">{label}</p>
      {helper ? <p className="mt-2 text-xs text-slate-500">{helper}</p> : null}
    </div>
  )
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-[1.4rem] border border-slate-200 bg-white p-4">
      <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-slate-800">{value || '—'}</p>
    </div>
  )
}

function ChipList({ items, tone = 'bg-slate-100 text-slate-700' }) {
  if (!items?.length) {
    return <p className="text-sm text-slate-400">No items available.</p>
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item, index) => (
        <span key={`${item}-${index}`} className={`rounded-full px-3 py-1 text-xs font-bold ${tone}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

function ResumeSection({ resumeDetail, resumePoints }) {
  const parsed = resumeDetail?.parsed
  const match = resumeDetail?.reality_match

  return (
    <SectionFrame
      description="Compare the parsed resume against the role requirements and the extracted experience history."
      eyebrow="Resume"
      title="Resume and role fit"
      right={
        <div className="w-full rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4 2xl:max-w-56">
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
            Resume Score
          </p>
          <p className="mt-2 text-2xl font-black text-slate-950">
            {match?.total_points ?? resumePoints ?? 0} / {match?.max_points ?? 20}
          </p>
          <div className="mt-4">
            <ScoreBar
              max={match?.max_points ?? 20}
              score={match?.total_points ?? resumePoints ?? 0}
              tone="bg-emerald-500"
            />
          </div>
        </div>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-slate-200 bg-[#fbfaf7] p-5">
            <p className="text-lg font-black text-slate-950">
              {parsed?.name || 'Unknown candidate'}
            </p>
            {parsed?.current_title ? (
              <p className="mt-1 text-sm font-semibold text-slate-600">{parsed.current_title}</p>
            ) : null}
            {parsed?.summary ? (
              <p className="mt-4 text-sm leading-7 text-slate-600">{parsed.summary}</p>
            ) : (
              <p className="mt-4 text-sm text-slate-400">No resume summary was extracted.</p>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <InfoTile label="Email" value={parsed?.email} />
            <InfoTile label="Phone" value={parsed?.phone} />
            <InfoTile label="Location" value={parsed?.location} />
            <InfoTile label="Claimed Experience" value={`${parsed?.years_of_experience ?? 0} years`} />
          </div>

          <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
            <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
              Skills
            </p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                  Languages
                </p>
                <ChipList items={parsed?.skills?.languages || []} tone="bg-cyan-100 text-cyan-800" />
              </div>
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                  Frameworks
                </p>
                <ChipList items={parsed?.skills?.frameworks || []} tone="bg-violet-100 text-violet-800" />
              </div>
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                  Tools and data
                </p>
                <ChipList
                  items={[
                    ...(parsed?.skills?.tools || []),
                    ...(parsed?.skills?.databases || []),
                    ...(parsed?.skills?.cloud || []),
                  ]}
                  tone="bg-slate-100 text-slate-700"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
            <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
              Experience Timeline
            </p>
            <div className="mt-4 space-y-3">
              {parsed?.experience?.length ? (
                parsed.experience.map((exp, index) => (
                  <article key={`${exp.title}-${index}`} className="rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold text-slate-900">
                          {exp.title} {exp.company ? `· ${exp.company}` : ''}
                        </p>
                        <p className="mt-1 text-xs font-semibold text-slate-500">
                          {exp.start_date || '—'} to {exp.end_date || 'Present'}
                        </p>
                      </div>
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-700">
                        {exp.duration_months ?? 0} months
                      </span>
                    </div>
                    {exp.description ? (
                      <p className="mt-3 text-sm leading-6 text-slate-600">{exp.description}</p>
                    ) : null}
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-400">No structured experience entries were extracted.</p>
              )}
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
            <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
              Match Signals
            </p>
            <div className="mt-4 space-y-3">
              {match?.skills_vs_job?.details?.length ? (
                <div className="flex flex-wrap gap-2">
                  {match.skills_vs_job.details.map((item, index) => (
                    <span
                      key={`${item.skill}-${index}`}
                      className={`rounded-full px-3 py-1 text-xs font-bold ${
                        item.found_on_resume
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      {item.found_on_resume ? 'Verified' : 'Missing'} · {item.skill}
                    </span>
                  ))}
                </div>
              ) : null}
              {match?.red_flags?.length ? (
                <div className="rounded-[1.4rem] border border-rose-200 bg-rose-50 p-4">
                  <p className="text-xs font-black uppercase tracking-[0.24em] text-rose-700">
                    Red Flags
                  </p>
                  <ul className="mt-3 space-y-2 text-sm text-rose-700">
                    {match.red_flags.map((flag, index) => (
                      <li key={index}>• {flag}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No major resume alignment flags were recorded.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </SectionFrame>
  )
}

function GitHubSection({ githubDetail, githubUrl }) {
  return (
    <SectionFrame
      description="Repository evidence, detected stack, and collaboration signals from the candidate’s GitHub profile."
      eyebrow="GitHub"
      title="Engineering credibility"
      right={
        <div className="w-full rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4 2xl:max-w-56">
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
            GitHub Score
          </p>
          <p className="mt-2 text-2xl font-black text-slate-950">
            {githubDetail?.points ?? 0} / {githubDetail?.max_points ?? 40}
          </p>
          <div className="mt-4">
            <ScoreBar max={githubDetail?.max_points ?? 40} score={githubDetail?.points ?? 0} tone="bg-cyan-500" />
          </div>
        </div>
      }
    >
      {!githubDetail ? (
        <p className="text-sm text-slate-400">No GitHub analysis is stored for this candidate.</p>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-5">
            <div className="rounded-[1.5rem] border border-slate-200 bg-[#fbfaf7] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-black text-slate-950">
                    {githubDetail.name || githubDetail.owner || 'GitHub profile'}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">{githubUrl || 'No GitHub URL provided'}</p>
                </div>
                {githubUrl ? (
                  <a
                    className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50"
                    href={githubUrl}
                    rel="noreferrer"
                    target="_blank"
                  >
                    Open profile
                  </a>
                ) : null}
              </div>
              {githubDetail.criteria ? (
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {Object.entries(githubDetail.criteria).map(([key, value]) => (
                    <div key={key} className="rounded-[1.3rem] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                        {key.replaceAll('_', ' ')}
                      </p>
                      <p className="mt-2 text-xl font-black text-slate-950">
                        {value.score ?? 0} / {value.max ?? 0}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{value.reason}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
              <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
                Detected Skills
              </p>
              <div className="mt-4 space-y-4">
                <div>
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                    Primary Languages
                  </p>
                  <ChipList items={githubDetail.signals?.primary_languages || []} tone="bg-cyan-100 text-cyan-800" />
                </div>
                <div>
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                    Frameworks
                  </p>
                  <ChipList items={githubDetail.signals?.frameworks || []} tone="bg-violet-100 text-violet-800" />
                </div>
                <div>
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                    Verified Resume Skills
                  </p>
                  <ChipList items={githubDetail.signals?.matched_resume_skills || []} tone="bg-emerald-100 text-emerald-800" />
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
              <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
                Coverage Summary
              </p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <MetricCard
                  accent="bg-cyan-500"
                  helper="Repositories considered"
                  label="Repos"
                  value={githubDetail.signals?.repo_count_considered ?? 0}
                />
                <MetricCard
                  accent="bg-emerald-500"
                  helper="Recently active repositories"
                  label="Active"
                  value={githubDetail.signals?.recently_active_repositories ?? 0}
                />
              </div>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
              <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
                Unverified Claims
              </p>
              <div className="mt-4">
                <ChipList items={githubDetail.signals?.unverified_resume_skills || []} tone="bg-rose-100 text-rose-700" />
              </div>
            </div>
          </div>
        </div>
      )}
    </SectionFrame>
  )
}

function LinkedInSection({ linkedinDetail, linkedinPoints, linkedinUrl }) {
  const analysis = linkedinDetail?.analysis

  return (
    <SectionFrame
      description="Role history, endorsements, and career progression signals extracted from LinkedIn evidence."
      eyebrow="LinkedIn"
      title="Professional credibility"
      right={
        <div className="w-full rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4 2xl:max-w-56">
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
            LinkedIn Score
          </p>
          <p className="mt-2 text-2xl font-black text-slate-950">
            {analysis?.points ?? linkedinPoints ?? 0} / {analysis?.max_points ?? 30}
          </p>
          <div className="mt-4">
            <ScoreBar max={analysis?.max_points ?? 30} score={analysis?.points ?? linkedinPoints ?? 0} tone="bg-blue-500" />
          </div>
        </div>
      }
    >
      {!analysis ? (
        <p className="text-sm text-slate-400">No LinkedIn analysis is stored for this candidate.</p>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-5">
            <div className="rounded-[1.5rem] border border-slate-200 bg-[#fbfaf7] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-black text-slate-950">
                    {analysis.profile_excerpt?.current_title || analysis.signals?.current_title || 'LinkedIn profile'}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {analysis.profile_excerpt?.headline || analysis.signals?.headline || 'No headline available'}
                  </p>
                </div>
                {linkedinUrl ? (
                  <a
                    className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50"
                    href={linkedinUrl}
                    rel="noreferrer"
                    target="_blank"
                  >
                    Open profile
                  </a>
                ) : null}
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <InfoTile label="Experience entries" value={analysis.signals?.experience_count} />
                <InfoTile label="Avg tenure" value={`${analysis.signals?.average_tenure_months ?? 0} months`} />
                <InfoTile label="Relevant endorsements" value={analysis.signals?.relevant_endorsements} />
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
              <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
                Criteria Breakdown
              </p>
              <div className="mt-4 space-y-3">
                {Object.entries(analysis.criteria || {}).map(([key, value]) => (
                  <div key={key} className="rounded-[1.3rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-sm font-bold capitalize text-slate-900">
                        {key.replaceAll('_', ' ')}
                      </p>
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-700">
                        {value.score} / {value.max}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{value.reason}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
              <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
                Endorsed Skills
              </p>
              <div className="mt-4 grid gap-3">
                {(analysis.profile_excerpt?.skills || []).map((skill) => (
                  <div key={skill.name} className="flex items-center justify-between rounded-[1.2rem] border border-slate-200 bg-slate-50 px-4 py-3">
                    <span className="text-sm font-bold text-slate-800">{skill.name}</span>
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-700">
                      {skill.endorsements ?? 0} endorsements
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
              <p className="text-sm font-black uppercase tracking-[0.24em] text-slate-400">
                Visible Experience
              </p>
              <div className="mt-4 space-y-3">
                {(analysis.profile_excerpt?.experiences || []).map((experience, index) => (
                  <article key={`${experience.title}-${index}`} className="rounded-[1.3rem] border border-slate-200 bg-slate-50 p-4">
                    <p className="text-sm font-bold text-slate-900">
                      {experience.title} {experience.company ? `· ${experience.company}` : ''}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-slate-500">
                      {experience.start_date || '—'} to {experience.end_date || 'Present'}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </SectionFrame>
  )
}

function AssessmentSection({ detail }) {
  const assessment = detail?.assessment
  const mcq = assessment?.part1_mcq || []
  const coding = assessment?.part2_coding
  const assessmentScore = detail?.assessment_total_score ?? detail?.assessment_score
  const assessmentMax = detail?.assessment_total_max ?? 100
  const submittedAt = detail?.assessment_submitted_at
  const candidateSubmission = detail?.assessment_candidate_answers || null
  const codingRunResult = detail?.assessment_run_result || candidateSubmission?.coding_result || null
  const submittedCodingAnswer = candidateSubmission?.coding_answer || ''

  return (
    <SectionFrame
      description="Review how the candidate performed on the generated technical assessment."
      eyebrow="Assessment"
      title="Assessment review"
      right={
        <div className="w-full rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4 2xl:max-w-56">
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
            Assessment Score
          </p>
          <p className="mt-2 text-2xl font-black text-slate-950">
            {assessmentScore ?? 0} / {assessmentMax}
          </p>
          <div className="mt-4">
            <ScoreBar max={assessmentMax} score={assessmentScore ?? 0} tone="bg-violet-500" />
          </div>
        </div>
      }
    >
      {!assessment ? (
        <p className="text-sm text-slate-400">Assessment data is not available for this candidate yet.</p>
      ) : !submittedAt ? (
        <p className="text-sm text-slate-400">Assessment was sent, but the candidate has not submitted it yet.</p>
      ) : (
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-slate-200 bg-[#fbfaf7] p-5">
            <p className="text-sm font-bold text-slate-900">
              Submitted on {new Date(submittedAt).toLocaleString()}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              This view includes both the knowledge section and the submitted coding exercise.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <InfoTile label="MCQ" value={`${detail?.assessment_mcq_score ?? 0} / ${detail?.assessment_mcq_max ?? 50}`} />
              <InfoTile label="Coding" value={`${detail?.assessment_coding_score ?? 0} / ${detail?.assessment_coding_max ?? 50}`} />
              <InfoTile label="Final" value={`${detail?.assessment_total_score ?? assessmentScore ?? 0} / ${assessmentMax}`} />
            </div>
          </div>

          <div className="grid gap-4">
            {mcq.map((question, index) => {
              const candidateAnswer = question.candidate_answer
              const correct = question.correct
              const isCorrect =
                candidateAnswer &&
                correct &&
                candidateAnswer.toUpperCase() === correct.toUpperCase()

              return (
                <article
                  key={`${question.id}-${index}`}
                  className={`rounded-[1.6rem] border p-5 ${
                    candidateAnswer
                      ? isCorrect
                        ? 'border-emerald-200 bg-emerald-50/70'
                        : 'border-rose-200 bg-rose-50/70'
                      : 'border-slate-200 bg-white'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
                        Question {question.id}
                      </p>
                      <p className="mt-2 text-base font-black text-slate-950">{question.question}</p>
                    </div>
                    <div className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-700">
                      {candidateAnswer
                        ? isCorrect
                          ? 'Correct'
                          : `Wrong · correct ${correct}`
                        : 'No answer'}
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2">
                    {['A', 'B', 'C', 'D']
                      .filter((key) => question.options?.[key])
                      .map((key) => (
                        <div
                          key={key}
                          className={`rounded-2xl px-4 py-3 text-sm ${
                            key === correct
                              ? 'bg-emerald-100 font-bold text-emerald-900'
                              : key === candidateAnswer
                                ? 'bg-rose-100 font-bold text-rose-800'
                                : 'bg-white text-slate-700'
                          }`}
                        >
                          <span className="mr-2 font-black">{key})</span>
                          {question.options[key]}
                        </div>
                      ))}
                  </div>

                  {question.explanation ? (
                    <p className="mt-4 text-sm leading-6 text-slate-600">{question.explanation}</p>
                  ) : null}
                </article>
              )
            })}
          </div>

          {coding ? (
            <div className="rounded-[1.6rem] border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-400">
                    Coding Exercise
                  </p>
                  <h3 className="mt-2 text-xl font-black text-slate-950">{coding.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    {coding.instructions}
                  </p>
                </div>
                <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                  {coding.language || 'javascript'}
                </div>
              </div>

              <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_0.85fr]">
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-black text-slate-900">Submitted solution</p>
                    <pre className="mt-3 overflow-x-auto rounded-[1.4rem] border border-slate-200 bg-slate-950 p-4 text-xs leading-6 text-slate-100">
                      <code>{submittedCodingAnswer || 'No coding answer submitted.'}</code>
                    </pre>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
                    <p className="text-sm font-black text-slate-900">Execution result</p>
                    {codingRunResult ? (
                      <div className="mt-3 space-y-3">
                        <InfoTile
                          label="Public Tests Passed"
                          value={`${codingRunResult.passed_count ?? 0} / ${codingRunResult.total_count ?? 0}`}
                        />
                        {codingRunResult.error ? (
                          <div className="rounded-[1.2rem] border border-rose-200 bg-rose-50 p-4">
                            <p className="text-xs font-black uppercase tracking-[0.2em] text-rose-700">
                              Runtime Error
                            </p>
                            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-rose-800">
                              {codingRunResult.error}
                            </pre>
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <p className="mt-3 text-sm text-slate-500">No coding run result available.</p>
                    )}
                  </div>

                  {codingRunResult?.results?.length ? (
                    <div className="rounded-[1.4rem] border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm font-black text-slate-900">Test Results</p>
                      <div className="mt-3 space-y-3">
                        {codingRunResult.results.map((result, index) => (
                          <div
                            key={`${result.name}-${index}`}
                            className={`rounded-[1.2rem] border px-4 py-3 text-sm ${
                              result.passed
                                ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                                : 'border-rose-200 bg-rose-50 text-rose-900'
                            }`}
                          >
                            <p className="font-bold">{result.name}</p>
                            {result.description ? (
                              <p className="mt-1 text-xs leading-5">{result.description}</p>
                            ) : null}
                            {!result.passed ? (
                              <div className="mt-2 text-xs leading-5">
                                Expected: {JSON.stringify(result.expected_output)} | Actual: {JSON.stringify(result.actual)}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </SectionFrame>
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
    if (!stored) {
      navigate('/hr/login', { replace: true })
      return
    }

    const user = JSON.parse(stored)
    if (String(user.id) !== String(userId)) {
      navigate('/hr/dashboard', { replace: true })
      return
    }

    getHrApplicationDetail(userId, applicationId)
      .then((data) => {
        setDetail(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'Failed to load.')
        setLoading(false)
      })
  }, [applicationId, navigate, userId])

  const metrics = useMemo(() => {
    if (!detail) return []
    return [
      {
        label: 'Resume Fit',
        value: `${detail.pipeline_resume_points ?? 0} / 20`,
        helper: 'Resume vs role alignment',
        accent: 'bg-emerald-500',
      },
      {
        label: 'GitHub',
        value: `${detail.github_detail?.points ?? 0} / ${detail.github_detail?.max_points ?? 40}`,
        helper: 'Code credibility score',
        accent: 'bg-cyan-500',
      },
      {
        label: 'LinkedIn',
        value: `${detail.linkedin_detail?.analysis?.points ?? detail.pipeline_linkedin_points ?? 0} / 30`,
        helper: 'Professional credibility score',
        accent: 'bg-blue-500',
      },
      {
        label: 'Assessment',
        value: `${detail.assessment_total_score ?? detail.assessment_score ?? 0} / ${detail.assessment_total_max ?? 100}`,
        helper: 'Assessment result',
        accent: 'bg-violet-500',
      },
    ]
  }, [detail])

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(34,197,94,0.12),transparent_18%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,0.16),transparent_24%),linear-gradient(180deg,#f2efe8_0%,#eef5f6_45%,#f7fafb_100%)] px-4 py-6 text-slate-900 sm:px-6 lg:px-10 lg:py-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="rounded-[2.2rem] border border-white/70 bg-white/70 p-5 shadow-[0_24px_100px_rgba(15,23,42,0.10)] backdrop-blur md:p-7">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200/80 pb-6">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.36em] text-cyan-700">
                Candidate Review
              </p>
              <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950 md:text-5xl">
                {detail?.full_name || 'Loading candidate'}
              </h1>
              {detail ? (
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  Reviewing application for <span className="font-bold text-slate-800">{detail.job.title}</span>
                  {' '}in <span className="font-bold text-slate-800">{detail.job.department}</span>.
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
                to="/hr/dashboard"
              >
                Back to dashboard
              </Link>
              {detail ? <StatusPill status={detail.status} /> : null}
            </div>
          </div>

          {loading ? (
            <div className="py-20 text-center text-sm text-slate-500">Loading candidate review…</div>
          ) : error ? (
            <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-700">
              {error}
            </div>
          ) : detail ? (
            <div className="mt-6 space-y-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {metrics.map((metric) => (
                  <MetricCard
                    key={metric.label}
                    accent={metric.accent}
                    helper={metric.helper}
                    label={metric.label}
                    value={metric.value}
                  />
                ))}
              </div>

              <div className="grid gap-5 2xl:grid-cols-[0.82fr_1.18fr]">
                <section className="space-y-5">
                  <SectionFrame
                    description="High-level identity and contact information for quick coordination."
                    eyebrow="Profile"
                    title="Candidate snapshot"
                  >
                    <div className="grid gap-4 sm:grid-cols-2">
                      <InfoTile label="Email" value={detail.email} />
                      <InfoTile label="Phone" value={detail.phone} />
                      <InfoTile label="Applied On" value={new Date(detail.submitted_at).toLocaleString()} />
                      <InfoTile label="Current Status" value={STATUS_META[detail.status]?.label || detail.status} />
                    </div>
                    <div className="mt-5 grid gap-3">
                      {detail.github_url ? (
                        <a
                          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700 transition hover:bg-white"
                          href={detail.github_url}
                          rel="noreferrer"
                          target="_blank"
                        >
                          Open GitHub
                        </a>
                      ) : null}
                      {detail.linkedin_url ? (
                        <a
                          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700 transition hover:bg-white"
                          href={detail.linkedin_url}
                          rel="noreferrer"
                          target="_blank"
                        >
                          Open LinkedIn
                        </a>
                      ) : null}
                    </div>
                  </SectionFrame>
                </section>

                <section className="space-y-6">
                  <ResumeSection
                    resumeDetail={detail.resume_detail}
                    resumePoints={detail.pipeline_resume_points}
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
                  <AssessmentSection detail={detail} />
                </section>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </main>
  )
}

export default ApplicantDetailPage
