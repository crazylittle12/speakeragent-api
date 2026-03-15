const API_URL = process.env.NEXT_PUBLIC_API_URL || ""

export const SPEAKER_ID = "leigh_vinocur"

export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error("Failed to fetch")
  }
  return res.json()
}

export function getDashboardUrl() {
  return `${API_URL}/api/dashboard/${SPEAKER_ID}`
}

export function getStatsUrl() {
  return `${API_URL}/api/leads/stats?speaker_id=${SPEAKER_ID}`
}

export function getLeadsUrl() {
  return `${API_URL}/api/leads?speaker_id=${SPEAKER_ID}`
}

export function getLeadUrl(id: string) {
  return `${API_URL}/api/leads/${id}`
}

export async function updateLeadStatus(id: string, status: string) {
  const res = await fetch(`${API_URL}/api/leads/${id}/status`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ status }),
  })
  if (!res.ok) {
    throw new Error("Failed to update status")
  }
  return res.json()
}
