"use client"

import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Lead } from "@/lib/types"
import { TriageDot } from "./triage-dot"
import { StatusBadge } from "./status-badge"
import { updateLeadStatus } from "@/lib/api"
import { format } from "date-fns"
import {
  ExternalLink,
  Copy,
  Check,
  Calendar,
  MapPin,
  Mic,
  DollarSign,
  Mail,
  Link2,
} from "lucide-react"

interface LeadDetailPanelProps {
  lead: Lead | null
  open: boolean
  onClose: () => void
  onStatusChange: () => void
}

const statusOptions: Lead["Lead Status"][] = ["New", "Contacted", "Replied", "Booked", "Passed"]

export function LeadDetailPanel({
  lead,
  open,
  onClose,
  onStatusChange,
}: LeadDetailPanelProps) {
  const [copied, setCopied] = useState(false)
  const [updating, setUpdating] = useState(false)

  if (!lead) return null

  async function handleStatusChange(newStatus: string) {
    if (!lead) return
    setUpdating(true)
    try {
      await updateLeadStatus(lead.id, newStatus)
      onStatusChange()
    } catch {
      console.error("Failed to update status")
    } finally {
      setUpdating(false)
    }
  }

  async function handleCopyHook() {
    if (!lead) return
    await navigator.clipboard.writeText(lead["The Hook"])
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function handleMarkContacted() {
    await handleStatusChange("Contacted")
  }

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className="w-full sm:max-w-lg p-0 flex flex-col">
        <SheetHeader className="px-6 pt-6 pb-4 border-b">
          <div className="flex items-start gap-3">
            <TriageDot triage={lead["Lead Triage"]} className="mt-1.5 size-4" />
            <div className="flex-1 min-w-0">
              <SheetTitle className="text-left text-lg leading-tight mb-2">
                {lead["Conference Name"]}
              </SheetTitle>
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{lead["Match Score"]}/100</Badge>
                <StatusBadge status={lead["Lead Status"]} />
              </div>
            </div>
          </div>
        </SheetHeader>

        <ScrollArea className="flex-1 px-6 py-4">
          <div className="space-y-6">
            {/* Status Selector */}
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-2 block">
                Status
              </label>
              <Select
                value={lead["Lead Status"]}
                onValueChange={handleStatusChange}
                disabled={updating}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((status) => (
                    <SelectItem key={status} value={status}>
                      <span className="flex items-center gap-2">
                        <StatusBadge status={status} />
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* The Hook */}
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-2">
                The Hook
              </h3>
              <blockquote className="border-l-4 border-primary/20 pl-4 py-2 bg-muted/30 rounded-r-md text-sm leading-relaxed italic">
                {lead["The Hook"]}
              </blockquote>
            </div>

            {/* CTA */}
            {lead["CTA"] && (
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">
                  Call to Action
                </h3>
                <p className="text-sm leading-relaxed">{lead["CTA"]}</p>
              </div>
            )}

            {/* Details */}
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-3">
                Details
              </h3>
              <div className="space-y-3">
                {lead["Event Date"] && (
                  <div className="flex items-center gap-3 text-sm">
                    <Calendar className="size-4 text-muted-foreground shrink-0" />
                    <span>{format(new Date(lead["Event Date"]), "MMMM d, yyyy")}</span>
                  </div>
                )}
                <div className="flex items-center gap-3 text-sm">
                  <MapPin className="size-4 text-muted-foreground shrink-0" />
                  <span>{lead["Event Location"]}</span>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <Mic className="size-4 text-muted-foreground shrink-0" />
                  <span>{lead["Suggested Talk"]}</span>
                </div>
                {lead["Pay Estimate"] && (
                  <div className="flex items-center gap-3 text-sm">
                    <DollarSign className="size-4 text-muted-foreground shrink-0" />
                    <span>{lead["Pay Estimate"]}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Contact */}
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-3">
                Contact
              </h3>
              <div className="space-y-3">
                {lead["Contact Email"] && (
                  <a
                    href={`mailto:${lead["Contact Email"]}`}
                    className="flex items-center gap-3 text-sm text-primary hover:underline"
                  >
                    <Mail className="size-4 shrink-0" />
                    <span>{lead["Contact Email"]}</span>
                  </a>
                )}
                <a
                  href={lead["Conference URL"]}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 text-sm text-primary hover:underline"
                >
                  <Link2 className="size-4 shrink-0" />
                  <span className="truncate">{lead["Conference URL"]}</span>
                </a>
              </div>
            </div>
          </div>
        </ScrollArea>

        {/* Actions Footer */}
        <div className="px-6 py-4 border-t bg-muted/30 flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm">
            <a
              href={lead["Conference URL"]}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="size-4 mr-1.5" />
              Open Website
            </a>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyHook}
          >
            {copied ? (
              <Check className="size-4 mr-1.5" />
            ) : (
              <Copy className="size-4 mr-1.5" />
            )}
            {copied ? "Copied!" : "Copy Hook"}
          </Button>
          {lead["Lead Status"] === "New" && (
            <Button size="sm" onClick={handleMarkContacted} disabled={updating}>
              Mark Contacted
            </Button>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
