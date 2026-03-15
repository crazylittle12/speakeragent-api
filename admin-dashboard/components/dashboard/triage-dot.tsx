"use client"

import { cn } from "@/lib/utils"
import type { Lead } from "@/lib/types"

interface TriageDotProps {
  triage: Lead["Lead Triage"]
  className?: string
}

const triageColors = {
  RED: "bg-[#dc2626]",
  YELLOW: "bg-[#d97706]",
  GREEN: "bg-[#16a34a]",
}

export function TriageDot({ triage, className }: TriageDotProps) {
  return (
    <span
      className={cn(
        "inline-block size-3 rounded-full shrink-0",
        triageColors[triage] || "bg-gray-400",
        className
      )}
    />
  )
}
