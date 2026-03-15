"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { DashboardStats } from "@/lib/types"
import { Flame } from "lucide-react"

interface StatCardsProps {
  stats: DashboardStats | undefined
  isLoading: boolean
}

export function StatCards({ stats, isLoading }: StatCardsProps) {
  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="py-4">
            <CardContent className="px-4">
              <Skeleton className="h-4 w-20 mb-3" />
              <Skeleton className="h-8 w-16 mb-2" />
              <Skeleton className="h-3 w-14" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (!stats) return null

  const byTriage = stats.by_triage ?? { RED: 0, YELLOW: 0, GREEN: 0 }

  const cards = [
    {
      title: "Total Leads",
      value: stats.total ?? 0,
      subtext: "all time",
    },
    {
      title: "Hot Leads",
      value: byTriage.RED ?? 0,
      subtext: "score >= 65",
      color: "#dc2626",
      icon: <Flame className="size-5 text-[#dc2626]" />,
    },
    {
      title: "Warm Leads",
      value: byTriage.YELLOW ?? 0,
      subtext: "score 35-64",
      color: "#d97706",
    },
    {
      title: "Avg Score",
      value: typeof stats.avg_score === "number" ? stats.avg_score.toFixed(1) : "0",
      suffix: "/100",
      subtext: "",
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title} className="py-4">
          <CardContent className="px-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm text-muted-foreground">{card.title}</p>
              {card.icon}
            </div>
            <p
              className="text-3xl font-bold"
              style={{ color: card.color }}
            >
              {card.value}
              {card.suffix && (
                <span className="text-lg text-muted-foreground">{card.suffix}</span>
              )}
            </p>
            {card.subtext && (
              <p className="text-xs text-muted-foreground mt-1">{card.subtext}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
