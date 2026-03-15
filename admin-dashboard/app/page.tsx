"use client"

import { useState } from "react"
import useSWR from "swr"
import { Sidebar } from "@/components/dashboard/sidebar"
import { MobileHeader } from "@/components/dashboard/mobile-header"
import { StatCards } from "@/components/dashboard/stat-cards"
import { TopLeads } from "@/components/dashboard/top-leads"
import { LeadsTable } from "@/components/dashboard/leads-table"
import { LeadDetailPanel } from "@/components/dashboard/lead-detail-panel"
import { SystemHealth } from "@/components/dashboard/system-health"
import { AdminView } from "@/components/dashboard/admin-view"
import { SettingsView } from "@/components/dashboard/settings-view"
import type { View } from "@/lib/types"
import { fetcher } from "@/lib/api"
import type { Lead, DashboardStats } from "@/lib/types"

interface LeadsResponse {
  leads: Lead[]
  stats: DashboardStats
  total: number
}

export default function Dashboard() {
  const [statusFilter, setStatusFilter] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [sortBy, setSortBy] = useState("createdAt")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [currentView, setCurrentView] = useState<View>("dashboard")
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const queryParams = new URLSearchParams({
    status: statusFilter,
    search: searchQuery,
    sortBy,
    sortOrder,
  })

  const { data, error, isLoading, mutate } = useSWR<LeadsResponse>(
    `/api/leads?${queryParams.toString()}`,
    fetcher,
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
    }
  )

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortBy(column)
      setSortOrder("desc")
    }
  }

  const topLeads = data?.leads
    .filter(lead => lead.status !== "lost" && lead.status !== "booked")
    .sort((a, b) => b.triageScore - a.triageScore)
    .slice(0, 3) || []

  return (
    <div className="flex min-h-screen bg-muted/30">
      {/* Desktop Sidebar */}
      <aside className={`hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 transition-all duration-300 ${sidebarCollapsed ? "lg:w-16" : "lg:w-64"}`}>
        <Sidebar 
          currentView={currentView}
          onViewChange={setCurrentView}
          collapsed={sidebarCollapsed}
          onCollapse={setSidebarCollapsed}
        />
      </aside>

      {/* Main Content */}
      <div className={`flex flex-1 flex-col transition-all duration-300 ${sidebarCollapsed ? "lg:pl-16" : "lg:pl-64"}`}>
        <MobileHeader />
        
        <main className="flex-1 p-4 lg:p-6">
          <div className="mx-auto max-w-7xl space-y-6">
            {currentView === "admin" ? (
              <AdminView />
            ) : currentView === "settings" ? (
              <SettingsView />
            ) : (
              <>
                {/* Header */}
                <div>
                  <h1 className="text-2xl font-bold tracking-tight text-foreground">
                    {currentView === "leads" ? "All Leads" : "Lead Dashboard"}
                  </h1>
                  <p className="text-muted-foreground">
                    Manage and track your speaking engagement opportunities
                  </p>
                </div>

                {/* Stats Cards - Only on Dashboard view */}
                {currentView === "dashboard" && (
                  <StatCards 
                    stats={data?.stats} 
                    isLoading={isLoading} 
                  />
                )}

                {/* Top Leads - Only on Dashboard view */}
                {currentView === "dashboard" && (
                  <TopLeads 
                    leads={topLeads} 
                    isLoading={isLoading}
                    onSelectLead={setSelectedLead}
                  />
                )}

                {/* Leads Table */}
                <LeadsTable
                  leads={data?.leads || []}
                  isLoading={isLoading}
                  error={error}
                  statusFilter={statusFilter}
                  onStatusFilterChange={setStatusFilter}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={handleSort}
                  onSelectLead={setSelectedLead}
                  onRefresh={() => mutate()}
                />

                {/* System Health - Only on Dashboard view */}
                {currentView === "dashboard" && <SystemHealth />}
              </>
            )}
          </div>
        </main>
      </div>

      {/* Lead Detail Panel */}
      <LeadDetailPanel
        lead={selectedLead}
        onClose={() => setSelectedLead(null)}
      />
    </div>
  )
}
