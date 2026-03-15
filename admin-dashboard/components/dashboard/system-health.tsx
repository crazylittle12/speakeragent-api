"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Activity, Database, Bot, Clock } from "lucide-react"

interface StatusItemProps {
  label: string
  status: "operational" | "connected" | "active" | "warning" | "error"
  icon: React.ReactNode
}

function StatusItem({ label, status, icon }: StatusItemProps) {
  const statusColors = {
    operational: "bg-emerald-500",
    connected: "bg-emerald-500",
    active: "bg-emerald-500",
    warning: "bg-amber-500",
    error: "bg-red-500",
  }

  const statusLabels = {
    operational: "Operational",
    connected: "Connected",
    active: "Active",
    warning: "Warning",
    error: "Error",
  }

  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-3">
        <div className="text-muted-foreground">{icon}</div>
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className={`size-2 rounded-full ${statusColors[status]}`} />
        <span className="text-sm text-muted-foreground">{statusLabels[status]}</span>
      </div>
    </div>
  )
}

export function SystemHealth() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Activity className="size-4" />
          System Health
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <StatusItem
          label="API Status"
          status="operational"
          icon={<Activity className="size-4" />}
        />
        <StatusItem
          label="Airtable Connection"
          status="connected"
          icon={<Database className="size-4" />}
        />
        <StatusItem
          label="Claude AI"
          status="active"
          icon={<Bot className="size-4" />}
        />
        <div className="flex items-center justify-between py-2 border-t mt-2 pt-3">
          <div className="flex items-center gap-3">
            <div className="text-muted-foreground">
              <Clock className="size-4" />
            </div>
            <span className="text-sm font-medium">Last Run</span>
          </div>
          <span className="text-sm text-muted-foreground">2 hours ago</span>
        </div>
      </CardContent>
    </Card>
  )
}
