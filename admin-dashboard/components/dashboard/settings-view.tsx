"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Copy, Check, Save, User, Bell, Key } from "lucide-react"

export function SettingsView() {
  const [profile, setProfile] = useState({
    name: "Dr. Leigh Vinocur",
    email: "leigh.vinocur@example.com",
    bio: "Board-certified emergency physician, national media medical expert, and professional speaker specializing in healthcare, wellness, and medical topics for corporate and public audiences.",
  })

  const [notifications, setNotifications] = useState({
    newLeads: true,
    weeklySummary: true,
  })

  const [copied, setCopied] = useState(false)
  const [saved, setSaved] = useState(false)

  const maskedApiKey = "sk-••••••••••••••••••••••••3a7f"

  const handleCopyApiKey = () => {
    navigator.clipboard.writeText("sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567abc890def123a7f")
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      {/* Profile Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="size-5 text-primary" />
            <CardTitle>Profile</CardTitle>
          </div>
          <CardDescription>
            Your personal information and bio displayed to event organizers
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                value={profile.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                value={profile.email}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="bio">Bio</Label>
            <Textarea
              id="bio"
              rows={4}
              value={profile.bio}
              onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
              className="resize-none"
            />
            <p className="text-xs text-muted-foreground">
              This bio may be shared with event organizers when you express interest in a lead.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Notifications Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bell className="size-5 text-primary" />
            <CardTitle>Notifications</CardTitle>
          </div>
          <CardDescription>
            Configure how you want to be notified about new leads and updates
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="new-leads" className="text-base">Email me when new leads are found</Label>
              <p className="text-sm text-muted-foreground">
                Get instant notifications when new speaking opportunities match your profile
              </p>
            </div>
            <Switch
              id="new-leads"
              checked={notifications.newLeads}
              onCheckedChange={(checked) => setNotifications({ ...notifications, newLeads: checked })}
            />
          </div>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="weekly-summary" className="text-base">Weekly leads summary email</Label>
              <p className="text-sm text-muted-foreground">
                Receive a digest of all leads and activity every Monday morning
              </p>
            </div>
            <Switch
              id="weekly-summary"
              checked={notifications.weeklySummary}
              onCheckedChange={(checked) => setNotifications({ ...notifications, weeklySummary: checked })}
            />
          </div>
        </CardContent>
      </Card>

      {/* API Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Key className="size-5 text-primary" />
            <CardTitle>API Access</CardTitle>
          </div>
          <CardDescription>
            Your API key for programmatic access to your leads data
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="api-key">API Key</Label>
            <div className="flex gap-2">
              <Input
                id="api-key"
                value={maskedApiKey}
                readOnly
                className="font-mono text-sm bg-muted"
              />
              <Button
                variant="outline"
                size="icon"
                onClick={handleCopyApiKey}
                className="shrink-0"
              >
                {copied ? (
                  <Check className="size-4 text-green-600" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Keep your API key secret. Do not share it publicly or commit it to version control.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} className="gap-2">
          {saved ? (
            <>
              <Check className="size-4" />
              Saved!
            </>
          ) : (
            <>
              <Save className="size-4" />
              Save Changes
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
