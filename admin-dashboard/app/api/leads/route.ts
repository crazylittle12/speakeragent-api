import { NextResponse } from "next/server"
import type { Lead, DashboardStats } from "@/lib/types"

const mockLeads: Lead[] = [
  {
    id: "1",
    eventName: "TechCrunch Disrupt 2026",
    organizationName: "TechCrunch Events",
    contactName: "Sarah Chen",
    contactEmail: "sarah.chen@techcrunch.com",
    contactPhone: "+1 (415) 555-0123",
    eventDate: "2026-09-15",
    eventLocation: "San Francisco, CA",
    estimatedBudget: 25000,
    expectedAttendance: 5000,
    topicFocus: "AI & Future of Work",
    status: "new",
    triageScore: 92,
    createdAt: "2026-03-15T10:30:00Z",
    notes: "Looking for keynote speaker on AI transformation. Very interested in our expertise.",
    source: "Website Form",
    eventType: "Conference"
  },
  {
    id: "2",
    eventName: "Global Leadership Summit",
    organizationName: "Leadership Excellence Institute",
    contactName: "Michael Torres",
    contactEmail: "m.torres@leadershipexcellence.org",
    contactPhone: "+1 (212) 555-0456",
    eventDate: "2026-06-20",
    eventLocation: "New York, NY",
    estimatedBudget: 35000,
    expectedAttendance: 2500,
    topicFocus: "Executive Leadership",
    status: "contacted",
    triageScore: 88,
    createdAt: "2026-03-14T14:15:00Z",
    notes: "Annual summit for C-suite executives. Looking for transformational leadership content.",
    source: "Referral",
    eventType: "Summit"
  },
  {
    id: "3",
    eventName: "Healthcare Innovation Forum",
    organizationName: "MedTech Alliance",
    contactName: "Dr. Emily Watson",
    contactEmail: "ewatson@medtechalliance.com",
    contactPhone: "+1 (617) 555-0789",
    eventDate: "2026-05-10",
    eventLocation: "Boston, MA",
    estimatedBudget: 18000,
    expectedAttendance: 800,
    topicFocus: "Healthcare Technology",
    status: "qualified",
    triageScore: 75,
    createdAt: "2026-03-13T09:00:00Z",
    notes: "Focus on digital health transformation and patient experience.",
    source: "LinkedIn",
    eventType: "Forum"
  },
  {
    id: "4",
    eventName: "Startup Founders Retreat",
    organizationName: "Venture Capital Partners",
    contactName: "James Liu",
    contactEmail: "james@vcpartners.io",
    contactPhone: "+1 (650) 555-0321",
    eventDate: "2026-04-25",
    eventLocation: "Napa Valley, CA",
    estimatedBudget: 15000,
    expectedAttendance: 150,
    topicFocus: "Entrepreneurship",
    status: "proposal_sent",
    triageScore: 82,
    createdAt: "2026-03-12T16:45:00Z",
    notes: "Exclusive retreat for portfolio company founders. High-touch event.",
    source: "Email Campaign",
    eventType: "Retreat"
  },
  {
    id: "5",
    eventName: "Women in Tech Conference",
    organizationName: "WiT Foundation",
    contactName: "Amanda Foster",
    contactEmail: "amanda@witfoundation.org",
    contactPhone: "+1 (206) 555-0654",
    eventDate: "2026-08-05",
    eventLocation: "Seattle, WA",
    estimatedBudget: 20000,
    expectedAttendance: 3000,
    topicFocus: "Diversity & Inclusion",
    status: "negotiating",
    triageScore: 90,
    createdAt: "2026-03-11T11:30:00Z",
    notes: "Looking for inspiring keynote on breaking barriers in tech leadership.",
    source: "Conference",
    eventType: "Conference"
  },
  {
    id: "6",
    eventName: "Financial Services Summit",
    organizationName: "Global Banking Forum",
    contactName: "Robert Kim",
    contactEmail: "rkim@globalbankingforum.com",
    contactPhone: "+1 (312) 555-0987",
    eventDate: "2026-07-12",
    eventLocation: "Chicago, IL",
    estimatedBudget: 40000,
    expectedAttendance: 1200,
    topicFocus: "FinTech Innovation",
    status: "booked",
    triageScore: 95,
    createdAt: "2026-03-10T08:20:00Z",
    notes: "Premium event. Contract signed for 90-minute keynote plus workshop.",
    source: "Referral",
    eventType: "Summit"
  },
  {
    id: "7",
    eventName: "EdTech World Conference",
    organizationName: "Education Innovation Network",
    contactName: "Lisa Park",
    contactEmail: "lpark@edinnov.net",
    contactPhone: "+1 (512) 555-0147",
    eventDate: "2026-10-08",
    eventLocation: "Austin, TX",
    estimatedBudget: 12000,
    expectedAttendance: 2000,
    topicFocus: "Education Technology",
    status: "new",
    triageScore: 68,
    createdAt: "2026-03-15T07:45:00Z",
    notes: "New inquiry about AI in education keynote.",
    source: "Website Form",
    eventType: "Conference"
  },
  {
    id: "8",
    eventName: "Sustainability Leaders Forum",
    organizationName: "Green Business Council",
    contactName: "David Green",
    contactEmail: "dgreen@greenbiz.council",
    contactPhone: "+1 (303) 555-0258",
    eventDate: "2026-04-18",
    eventLocation: "Denver, CO",
    estimatedBudget: 22000,
    expectedAttendance: 600,
    topicFocus: "Sustainability",
    status: "lost",
    triageScore: 45,
    createdAt: "2026-03-05T13:00:00Z",
    notes: "Budget constraints led to booking a local speaker instead.",
    source: "LinkedIn",
    eventType: "Forum"
  },
  {
    id: "9",
    eventName: "Sales Excellence Summit",
    organizationName: "National Sales Association",
    contactName: "Chris Martinez",
    contactEmail: "cmartinez@nsa-sales.org",
    contactPhone: "+1 (469) 555-0369",
    eventDate: "2026-05-28",
    eventLocation: "Dallas, TX",
    estimatedBudget: 28000,
    expectedAttendance: 1500,
    topicFocus: "Sales & Marketing",
    status: "contacted",
    triageScore: 79,
    createdAt: "2026-03-14T10:00:00Z",
    notes: "Looking for motivational speaker with sales background.",
    source: "Email Campaign",
    eventType: "Summit"
  },
  {
    id: "10",
    eventName: "HR Innovation Conference",
    organizationName: "People First Institute",
    contactName: "Jennifer Adams",
    contactEmail: "jadams@peoplefirst.org",
    contactPhone: "+1 (404) 555-0471",
    eventDate: "2026-09-22",
    eventLocation: "Atlanta, GA",
    estimatedBudget: 16000,
    expectedAttendance: 900,
    topicFocus: "Human Resources",
    status: "qualified",
    triageScore: 72,
    createdAt: "2026-03-13T15:30:00Z",
    notes: "Focus on future of work and employee experience.",
    source: "Website Form",
    eventType: "Conference"
  }
]

function calculateStats(leads: Lead[]): DashboardStats {
  const totalLeads = leads.length
  const newLeads = leads.filter(l => l.status === "new").length
  const bookedLeads = leads.filter(l => l.status === "booked").length
  const totalRevenue = leads
    .filter(l => l.status === "booked")
    .reduce((sum, l) => sum + l.estimatedBudget, 0)
  const avgTriageScore = Math.round(
    leads.reduce((sum, l) => sum + l.triageScore, 0) / leads.length
  )
  const conversionRate = totalLeads > 0 
    ? Math.round((bookedLeads / totalLeads) * 100) 
    : 0

  return {
    totalLeads,
    newLeads,
    bookedLeads,
    totalRevenue,
    avgTriageScore,
    conversionRate
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const status = searchParams.get("status")
  const search = searchParams.get("search")?.toLowerCase()
  const sortBy = searchParams.get("sortBy") || "createdAt"
  const sortOrder = searchParams.get("sortOrder") || "desc"

  let filteredLeads = [...mockLeads]

  // Filter by status
  if (status && status !== "all") {
    filteredLeads = filteredLeads.filter(lead => lead.status === status)
  }

  // Filter by search term
  if (search) {
    filteredLeads = filteredLeads.filter(lead =>
      lead.eventName.toLowerCase().includes(search) ||
      lead.organizationName.toLowerCase().includes(search) ||
      lead.contactName.toLowerCase().includes(search) ||
      lead.contactEmail.toLowerCase().includes(search)
    )
  }

  // Sort leads
  filteredLeads.sort((a, b) => {
    let aVal: string | number = ""
    let bVal: string | number = ""

    switch (sortBy) {
      case "triageScore":
        aVal = a.triageScore
        bVal = b.triageScore
        break
      case "eventDate":
        aVal = a.eventDate
        bVal = b.eventDate
        break
      case "estimatedBudget":
        aVal = a.estimatedBudget
        bVal = b.estimatedBudget
        break
      case "createdAt":
      default:
        aVal = a.createdAt
        bVal = b.createdAt
        break
    }

    if (sortOrder === "asc") {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
    }
    return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
  })

  const stats = calculateStats(mockLeads)

  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 300))

  return NextResponse.json({
    leads: filteredLeads,
    stats,
    total: filteredLeads.length
  })
}
