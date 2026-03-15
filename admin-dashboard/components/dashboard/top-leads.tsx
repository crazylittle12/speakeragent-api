"use client"

import type { Lead } from "@/lib/types"
import { LeadCard, LeadCardSkeleton } from "./lead-card"

interface TopLeadsProps {
  leads: Lead[] | undefined
  isLoading: boolean
  onLeadClick: (lead: Lead) => void
}

export function TopLeads({ leads, isLoading, onLeadClick }: TopLeadsProps) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Top Leads</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => <LeadCardSkeleton key={i} />)
        ) : leads?.length ? (
          leads.slice(0, 5).map((lead) => (
            <LeadCard key={lead.id} lead={lead} onClick={() => onLeadClick(lead)} />
          ))
        ) : (
          <p className="text-muted-foreground col-span-full">No leads found.</p>
        )}
      </div>
    </div>
  )
}
