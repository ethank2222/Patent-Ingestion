const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = {};
  }

  if (!response.ok) {
    const message = payload.error || `Request failed with ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

export async function listPatents(params) {
  const query = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/patents${suffix}`);
}

export async function getPatent(publicationNumber) {
  return request(`/patents/${publicationNumber}`);
}

export async function requestSummary(publicationNumber, mode = "deep") {
  return request(`/patents/${publicationNumber}/summaries`, {
    method: "POST",
    body: JSON.stringify({ mode })
  });
}

export async function getSummaryJob(jobId) {
  return request(`/summaries/${jobId}`);
}
