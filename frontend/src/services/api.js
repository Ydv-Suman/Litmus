const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)

  if (!response.ok) {
    let message = 'Request failed.'

    try {
      const errorPayload = await response.json()
      message = errorPayload.detail || errorPayload.message || message
    } catch {
      message = response.statusText || message
    }

    throw new Error(message)
  }

  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    return response.json()
  }

  return response.text()
}

export function submitApplication(applicationData) {
  const formData = new FormData()

  Object.entries(applicationData).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      formData.append(key, value)
    }
  })

  return apiRequest('/submitApplication', {
    method: 'POST',
    body: formData,
  })
}

export function getJobs() {
  return apiRequest('/jobs')
}

export function getAssessment(token) {
  return apiRequest(`/assessment/${encodeURIComponent(token)}`)
}

export function submitAssessmentAnswers(token, answers) {
  return apiRequest(`/assessment/${encodeURIComponent(token)}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
}

export function signupHrUser(payload) {
  return apiRequest('/hr/signup', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
}

export function loginHrUser(payload) {
  return apiRequest('/hr/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
}

export function getHrApplications(userId) {
  return apiRequest(`/hr/${userId}/applications`)
}

export function getHrApplicationDetail(userId, applicationId) {
  return apiRequest(`/hr/${userId}/applications/${applicationId}`)
}

export { apiRequest, API_BASE_URL }
