import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, FileCheck2, ShieldCheck, UserRoundSearch } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api, authHeaders } from "@/lib/api";

type CandidateRecord = {
  candidate_id: string;
  job_id: string;
  fit_score: number;
  verification_score: number;
  assessment_score: number;
  final_score: number;
  fairness_note?: string | null;
};

function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-grid bg-[size:28px_28px]">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-8">
        <header className="mb-8 flex flex-col gap-6 rounded-[32px] border border-border/80 bg-white/80 px-6 py-5 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Litmus / AI ATS
            </p>
            <h1 className="mt-2 text-3xl font-bold">Verify what candidates claim.</h1>
          </div>
          <nav className="flex gap-3">
            <Link to="/">
              <Button variant={location.pathname === "/" ? "default" : "secondary"}>
                Applicant Portal
              </Button>
            </Link>
            <Link to="/recruiter">
              <Button
                variant={location.pathname === "/recruiter" ? "default" : "secondary"}
              >
                Recruiter Dashboard
              </Button>
            </Link>
          </nav>
        </header>
        {children}
      </div>
    </div>
  );
}

function ApplicantPage() {
  const [token, setToken] = useState("");
  const [jobId, setJobId] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [candidateId, setCandidateId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resume) {
      setStatusMessage("Attach a resume before submitting.");
      return;
    }

    const payload = new FormData();
    payload.append("job_id", jobId);
    payload.append("name", name);
    payload.append("email", email);
    payload.append("github_url", githubUrl);
    payload.append("linkedin_url", linkedinUrl);
    payload.append("portfolio_url", portfolioUrl);
    payload.append("resume", resume);

    const response = await api.post("/api/v1/applications", payload, {
      headers: {
        ...authHeaders(token),
        "Content-Type": "multipart/form-data",
      },
    });
    setCandidateId(response.data.candidate_id);
    setStatusMessage(response.data.message);
  }

  return (
    <Shell>
      <main className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Applicant Intake</CardTitle>
            <CardDescription>
              All submissions route through the gateway and enter the async pipeline from
              there.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4" onSubmit={onSubmit}>
              <input
                className="field"
                placeholder="Applicant JWT"
                value={token}
                onChange={(event) => setToken(event.target.value)}
              />
              <div className="grid gap-4 md:grid-cols-2">
                <input
                  className="field"
                  placeholder="Job ID"
                  value={jobId}
                  onChange={(event) => setJobId(event.target.value)}
                />
                <input
                  className="field"
                  placeholder="Full name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </div>
              <input
                className="field"
                placeholder="Email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <div className="grid gap-4 md:grid-cols-3">
                <input
                  className="field"
                  placeholder="https://github.com/..."
                  value={githubUrl}
                  onChange={(event) => setGithubUrl(event.target.value)}
                />
                <input
                  className="field"
                  placeholder="https://linkedin.com/..."
                  value={linkedinUrl}
                  onChange={(event) => setLinkedinUrl(event.target.value)}
                />
                <input
                  className="field"
                  placeholder="https://portfolio.example"
                  value={portfolioUrl}
                  onChange={(event) => setPortfolioUrl(event.target.value)}
                />
              </div>
              <input
                className="field file:mr-4 file:rounded-full file:border-0 file:bg-secondary file:px-4 file:py-2"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                type="file"
                onChange={(event) => setResume(event.target.files?.[0] ?? null)}
              />
              <Button type="submit" size="lg">
                Submit Application
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="grid gap-6">
          <Card className="bg-slate-950 text-slate-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-slate-50">
                <ShieldCheck className="h-5 w-5 text-orange-400" />
                Secure-by-default pipeline
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm text-slate-200">
              <p>JWT on every route except health.</p>
              <p>Resume validation capped at 10MB.</p>
              <p>Frontend uses only the gateway base URL.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Submission Result</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="rounded-2xl bg-muted px-4 py-3">
                {statusMessage || "No submission yet."}
              </p>
              <p className="font-mono text-xs text-muted-foreground">
                Candidate ID: {candidateId || "pending"}
              </p>
            </CardContent>
          </Card>
        </div>
      </main>
    </Shell>
  );
}

function RecruiterPage() {
  const [token, setToken] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [jobId, setJobId] = useState("");

  const candidatesQuery = useQuery({
    queryKey: ["candidates", jobId, token],
    enabled: jobId.length > 0 && token.length > 0,
    refetchInterval: 10000,
    queryFn: async () => {
      const response = await api.get<{ candidates: CandidateRecord[] }>(
        `/api/v1/jobs/${jobId}/candidates`,
        {
          headers: authHeaders(token),
        },
      );
      return response.data.candidates;
    },
  });

  async function createJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await api.post(
      "/api/v1/jobs",
      { title, description },
      { headers: authHeaders(token) },
    );
    setJobId(response.data.job.job_id);
  }

  return (
    <Shell>
      <main className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Create Job</CardTitle>
            <CardDescription>
              Recruiter actions stay on the gateway and are role-gated with recruiter JWTs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4" onSubmit={createJob}>
              <input
                className="field"
                placeholder="Recruiter JWT"
                value={token}
                onChange={(event) => setToken(event.target.value)}
              />
              <input
                className="field"
                placeholder="Senior Backend Engineer"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
              <textarea
                className="field min-h-40 resize-none"
                placeholder="Paste the full job description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
              <Button type="submit">
                <BriefcaseBusiness className="mr-2 h-4 w-4" />
                Create Job
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserRoundSearch className="h-5 w-5 text-primary" />
                Candidate Rankings
              </CardTitle>
              <CardDescription>
                Polling runs through React Query against the gateway every 10 seconds.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl bg-muted px-4 py-3 text-sm">
                Active job ID: <span className="font-mono">{jobId || "not created"}</span>
              </div>
              <div className="grid gap-3">
                {(candidatesQuery.data ?? []).map((candidate) => (
                  <div
                    key={candidate.candidate_id}
                    className="rounded-3xl border border-border bg-white/80 p-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="space-y-1">
                        <p className="font-semibold">{candidate.candidate_id}</p>
                        <p className="text-sm text-muted-foreground">
                          Fit {candidate.fit_score} · Verify {candidate.verification_score} ·
                          Assess {candidate.assessment_score}
                        </p>
                      </div>
                      <div className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
                        {candidate.final_score}
                      </div>
                    </div>
                    {candidate.fairness_note ? (
                      <p className="mt-3 text-sm text-muted-foreground">
                        {candidate.fairness_note}
                      </p>
                    ) : null}
                  </div>
                ))}
                {!candidatesQuery.isFetching && (candidatesQuery.data?.length ?? 0) === 0 ? (
                  <div className="rounded-3xl border border-dashed border-border p-6 text-sm text-muted-foreground">
                    No scored candidates yet.
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
          <Card className="border-orange-200 bg-orange-50/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileCheck2 className="h-5 w-5 text-primary" />
                Reviewer Notes
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-700">
              This shell intentionally stops at gateway traffic. Recruiter-facing candidate
              detail pages can layer onto the scoring service contract without exposing
              internal service ports.
            </CardContent>
          </Card>
        </div>
      </main>
    </Shell>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ApplicantPage />} />
      <Route path="/recruiter" element={<RecruiterPage />} />
    </Routes>
  );
}
