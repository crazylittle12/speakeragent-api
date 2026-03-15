"use client"

import { cn } from "@/lib/utils"
import type { Lead } from "@/lib/types"

interface StatusBadgeProps {
  status: Lead["Lead Status"]
  className?: string
}

const statusColors = {
  New: "bg-[#3b82f6] text-white",
  Contacted: "bg-[#8b5cf6] text-white",
  Replied: "bg-[#d97706] text-white",
  Booked: "bg-[#16a34a] text-white",
  Passed: "bg-[#6b7280] text-white",
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        statusColors[status] || "bg-gray-100 text-gray-800",
        className
      )}
    >
      {status}
    </span>
  )
}
