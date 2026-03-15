"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Users } from "lucide-react"

interface User {
  id: string
  name: string
  email: string
  signupDate: string
  totalRequests: number
  leadsFound: number
  leadsDelivered: number
}

const mockUsers: User[] = [
  {
    id: "1",
    name: "Dr. Leigh Vinocur",
    email: "leigh@example.com",
    signupDate: "2025-01-15",
    totalRequests: 45,
    leadsFound: 128,
    leadsDelivered: 112,
  },
  {
    id: "2",
    name: "Marcus Chen",
    email: "marcus.chen@example.com",
    signupDate: "2025-02-03",
    totalRequests: 32,
    leadsFound: 87,
    leadsDelivered: 74,
  },
  {
    id: "3",
    name: "Sarah Williams",
    email: "sarah.w@example.com",
    signupDate: "2025-02-20",
    totalRequests: 28,
    leadsFound: 65,
    leadsDelivered: 58,
  },
  {
    id: "4",
    name: "James Rodriguez",
    email: "jrodriguez@example.com",
    signupDate: "2025-03-01",
    totalRequests: 15,
    leadsFound: 42,
    leadsDelivered: 38,
  },
  {
    id: "5",
    name: "Emily Thompson",
    email: "emily.t@example.com",
    signupDate: "2025-03-10",
    totalRequests: 8,
    leadsFound: 23,
    leadsDelivered: 19,
  },
]

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function AdminView() {
  const totalUsers = mockUsers.length
  const totalLeadsFound = mockUsers.reduce((sum, user) => sum + user.leadsFound, 0)
  const totalLeadsDelivered = mockUsers.reduce((sum, user) => sum + user.leadsDelivered, 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Admin Dashboard
        </h1>
        <p className="text-muted-foreground">
          Manage users and monitor system activity
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
                <Users className="size-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalUsers}</p>
                <p className="text-sm text-muted-foreground">Total Users</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-500/10">
                <span className="text-lg font-bold text-emerald-600">{totalLeadsFound}</span>
              </div>
              <div>
                <p className="text-2xl font-bold">{totalLeadsFound}</p>
                <p className="text-sm text-muted-foreground">Leads Found</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-blue-500/10">
                <span className="text-lg font-bold text-blue-600">{totalLeadsDelivered}</span>
              </div>
              <div>
                <p className="text-2xl font-bold">{totalLeadsDelivered}</p>
                <p className="text-sm text-muted-foreground">Leads Delivered</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Users</CardTitle>
          <CardDescription>All registered users and their activity</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Signup Date</TableHead>
                <TableHead className="text-right">Total Requests</TableHead>
                <TableHead className="text-right">Leads Found</TableHead>
                <TableHead className="text-right">Leads Delivered</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockUsers.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.name}</TableCell>
                  <TableCell className="text-muted-foreground">{user.email}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(user.signupDate)}</TableCell>
                  <TableCell className="text-right">{user.totalRequests}</TableCell>
                  <TableCell className="text-right">{user.leadsFound}</TableCell>
                  <TableCell className="text-right">{user.leadsDelivered}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
