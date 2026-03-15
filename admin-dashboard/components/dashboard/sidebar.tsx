"use client"

import { cn } from "@/lib/utils"
import type { View } from "@/lib/types"
import { LayoutDashboard, List, Settings, ChevronLeft, ChevronRight, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface SidebarProps {
  currentView: View
  onViewChange: (view: View) => void
  collapsed: boolean
  onCollapse: (collapsed: boolean) => void
}

const navItems = [
  { id: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
  { id: "leads" as const, label: "All Leads", icon: List },
  { id: "admin" as const, label: "Admin", icon: Users },
  { id: "settings" as const, label: "Settings", icon: Settings },
]

export function Sidebar({ currentView, onViewChange, collapsed, onCollapse }: SidebarProps) {
  return (
    <aside
      className={cn(
        "flex h-full flex-col bg-[#1e293b] text-white transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 p-4 border-b border-white/10">
        <div className="flex size-8 items-center justify-center rounded-lg bg-white/10 text-sm font-bold">
          SA
        </div>
        {!collapsed && (
          <span className="font-semibold text-sm">SpeakerAgent.AI</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              currentView === item.id
                ? "bg-white/10 text-white"
                : "text-white/70 hover:bg-white/5 hover:text-white"
            )}
          >
            <item.icon className="size-5 shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {/* Collapse Button */}
      <div className="p-3 border-t border-white/10">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onCollapse(!collapsed)}
          className="w-full justify-center text-white/70 hover:text-white hover:bg-white/5"
        >
          {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
          {!collapsed && <span className="ml-2">Collapse</span>}
        </Button>
      </div>

      {/* User Profile */}
      <div className="p-3 border-t border-white/10">
        <div className={cn("flex items-center gap-3", collapsed && "justify-center")}>
          <Avatar className="size-8">
            <AvatarFallback className="bg-white/10 text-white text-xs">LV</AvatarFallback>
          </Avatar>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">Dr. Leigh Vinocur</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
