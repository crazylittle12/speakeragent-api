export interface Lead {
  id: string
  "Conference Name": string
  "Lead Triage": "RED" | "YELLOW" | "GREEN"
  "Match Score": number
  "Event Location": string
  "Event Date"?: string
  "The Hook": string
  "CTA"?: string
  "Lead Status": "New" | "Contacted" | "Replied" | "Booked" | "Passed"
  "Conference URL": string
  "Contact Email"?: string
  "Suggested Talk": string
  "Date Found"?: string
  speaker_id: string
  "Pay Estimate"?: string
}

export interface DashboardStats {
  total: number
  by_triage: {
    RED: number
    YELLOW: number
    GREEN: number
  }
  by_status: {
    New: number
    Contacted: number
    Replied?: number
    Booked?: number
    Passed?: number
  }
  avg_score: number
}

export interface DashboardResponse {
  speaker: {
    id: string
    full_name: string
  }
  stats: DashboardStats
  top_leads: Lead[]
}

export interface LeadsResponse {
  count: number
  leads: Lead[]
}

export type View = "dashboard" | "leads" | "admin" | "settings"
