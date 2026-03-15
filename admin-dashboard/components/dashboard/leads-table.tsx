"use client"

import { useState, useMemo } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { Lead } from "@/lib/types"
import { TriageDot } from "./triage-dot"
import { StatusBadge } from "./status-badge"
import { updateLeadStatus } from "@/lib/api"
import { format } from "date-fns"

interface LeadsTableProps {
  leads: Lead[] | undefined
  isLoading: boolean
  onLeadClick: (lead: Lead) => void
  onStatusChange: () => void
}

type TriageFilter = "ALL" | "RED" | "YELLOW" | "GREEN"
type StatusFilter = "ALL" | Lead["Lead Status"]
type SortBy = "score" | "date"

const statusOptions: Lead["Lead Status"][] = ["New", "Contacted", "Replied", "Booked", "Passed"]

export function LeadsTable({ leads, isLoading, onLeadClick, onStatusChange }: LeadsTableProps) {
  const [triageFilter, setTriageFilter] = useState<TriageFilter>("ALL")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL")
  const [sortBy, setSortBy] = useState<SortBy>("score")
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const filteredAndSortedLeads = useMemo(() => {
    if (!leads) return []

    let filtered = leads

    if (triageFilter !== "ALL") {
      filtered = filtered.filter((lead) => lead["Lead Triage"] === triageFilter)
    }

    if (statusFilter !== "ALL") {
      filtered = filtered.filter((lead) => lead["Lead Status"] === statusFilter)
    }

    filtered = [...filtered].sort((a, b) => {
      if (sortBy === "score") {
        return b["Match Score"] - a["Match Score"]
      }
      const dateA = a["Date Found"] ? new Date(a["Date Found"]).getTime() : 0
      const dateB = b["Date Found"] ? new Date(b["Date Found"]).getTime() : 0
      return dateB - dateA
    })

    return filtered
  }, [leads, triageFilter, statusFilter, sortBy])

  async function handleStatusChange(leadId: string, newStatus: string) {
    setUpdatingId(leadId)
    try {
      await updateLeadStatus(leadId, newStatus)
      onStatusChange()
    } catch {
      console.error("Failed to update status")
    } finally {
      setUpdatingId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-9 w-32" />
          <Skeleton className="h-9 w-32" />
          <Skeleton className="h-9 w-32" />
        </div>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                {Array.from({ length: 7 }).map((_, i) => (
                  <TableHead key={i}>
                    <Skeleton className="h-4 w-20" />
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <div className="flex rounded-lg border overflow-hidden">
          {(["ALL", "RED", "YELLOW", "GREEN"] as TriageFilter[]).map((value) => (
            <Button
              key={value}
              variant={triageFilter === value ? "default" : "ghost"}
              size="sm"
              onClick={() => setTriageFilter(value)}
              className="rounded-none border-0"
            >
              {value === "ALL" ? "All" : (
                <span className="flex items-center gap-1.5">
                  <TriageDot triage={value as Lead["Lead Triage"]} />
                  {value}
                </span>
              )}
            </Button>
          ))}
        </div>

        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
          <SelectTrigger className="w-[140px]" size="sm">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All Status</SelectItem>
            {statusOptions.map((status) => (
              <SelectItem key={status} value={status}>
                {status}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortBy)}>
          <SelectTrigger className="w-[140px]" size="sm">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="score">Score (High)</SelectItem>
            <SelectItem value="date">Date Found</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Triage</TableHead>
              <TableHead>Conference Name</TableHead>
              <TableHead className="w-20">Score</TableHead>
              <TableHead className="hidden md:table-cell">Topic</TableHead>
              <TableHead className="hidden lg:table-cell">Location</TableHead>
              <TableHead className="w-32">Status</TableHead>
              <TableHead className="hidden md:table-cell w-28">Date Found</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredAndSortedLeads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No leads found.
                </TableCell>
              </TableRow>
            ) : (
              filteredAndSortedLeads.map((lead) => (
                <TableRow
                  key={lead.id}
                  className="cursor-pointer"
                  onClick={() => onLeadClick(lead)}
                >
                  <TableCell>
                    <TriageDot triage={lead["Lead Triage"]} />
                  </TableCell>
                  <TableCell className="font-medium">
                    {(lead["Conference Name"] ?? "").length > 40
                      ? `${(lead["Conference Name"] ?? "").slice(0, 40)}...`
                      : lead["Conference Name"] ?? "-"}
                  </TableCell>
                  <TableCell>{lead["Match Score"] ?? 0}/100</TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground text-sm max-w-[200px] truncate">
                    {lead["Suggested Talk"] ?? "-"}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-muted-foreground text-sm">
                    {lead["Event Location"] ?? "-"}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Select
                      value={lead["Lead Status"]}
                      onValueChange={(v) => handleStatusChange(lead.id, v)}
                      disabled={updatingId === lead.id}
                    >
                      <SelectTrigger className="h-7 w-28 border-0 bg-transparent p-0">
                        <StatusBadge status={lead["Lead Status"]} />
                      </SelectTrigger>
                      <SelectContent>
                        {statusOptions.map((status) => (
                          <SelectItem key={status} value={status}>
                            {status}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground text-sm">
                    {lead["Date Found"]
                      ? format(new Date(lead["Date Found"]), "MMM d, yyyy")
                      : "-"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
