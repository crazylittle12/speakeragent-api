"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import type { Lead } from "@/lib/types"
import { TriageDot } from "./triage-dot"
import { StatusBadge } from "./status-badge"
import { MapPin } from "lucide-react"

interface LeadCardProps {
  lead: Lead
  onClick: () => void
}

export function LeadCard({ lead, onClick }: LeadCardProps) {
  return (
    <Card
      className="cursor-pointer transition-all hover:shadow-md hover:border-primary/20 py-4"
      onClick={onClick}
    >
      <CardContent className="px-4">
        <div className="flex items-start gap-3">
          <TriageDot triage={lead["Lead Triage"]} className="mt-1.5" />
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 mb-2">
              <h3 className="font-semibold text-sm leading-tight line-clamp-2">
                {lead["Conference Name"]}
              </h3>
              <Badge variant="secondary" className="shrink-0 text-xs">
                {lead["Match Score"]}/100
              </Badge>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
              <MapPin className="size-3" />
              <span className="truncate">{lead["Event Location"]}</span>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-1 mb-3">
              {lead["Suggested Talk"]}
            </p>
            <StatusBadge status={lead["Lead Status"]} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function LeadCardSkeleton() {
  return (
    <Card className="py-4">
      <CardContent className="px-4">
        <div className="flex items-start gap-3">
          <Skeleton className="size-3 rounded-full mt-1.5" />
          <div className="flex-1">
            <div className="flex items-start justify-between gap-2 mb-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-5 w-12" />
            </div>
            <Skeleton className="h-3 w-28 mb-2" />
            <Skeleton className="h-3 w-48 mb-3" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
