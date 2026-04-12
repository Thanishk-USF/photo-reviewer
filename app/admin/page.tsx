"use client"

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { Loader2, LogOut, RefreshCw, ShieldCheck } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ThemeToggle } from "@/components/theme-toggle"

type TopLearnedTag = {
  tag: string
  prior: number
}

type TopSuggestion = {
  text: string
  freq: number
}

type AdaptiveDebugProfile = {
  sampleCount: number
  scoreMeans: Record<string, number>
  scoreQuantiles: Record<string, { q10: number; q50: number; q90: number }>
  dynamicLabelCount: number
  dynamicLabelPreview: string[]
  topLearnedTags: TopLearnedTag[]
  topSuggestions: TopSuggestion[]
  adaptiveConfig: {
    enabled: boolean
    maxDocs: number
    cacheTtlSeconds: number
    maxDynamicTagLabels: number
    maxSuggestionPool: number
  }
  generatedAt: string
}

type ProfileResponse = {
  success?: boolean
  error?: string
  profile?: AdaptiveDebugProfile
}

async function readJsonSafe(response: Response): Promise<ProfileResponse> {
  try {
    return (await response.json()) as ProfileResponse
  } catch {
    return {}
  }
}

export default function AdminDebugPage() {
  const [password, setPassword] = useState("")
  const [mounted, setMounted] = useState(false)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [profile, setProfile] = useState<AdaptiveDebugProfile | null>(null)

  const loadProfile = useCallback(async (refresh = false) => {
    if (refresh) {
      setIsRefreshing(true)
    } else {
      setIsLoading(true)
    }

    try {
      setError(null)
      const response = await fetch("/api/admin/profile", { cache: "no-store" })
      const payload = await readJsonSafe(response)

      if (response.status === 401) {
        setIsAuthenticated(false)
        setProfile(null)
        return
      }

      if (!response.ok || !payload.profile) {
        throw new Error(payload.error || "Failed to load admin profile")
      }

      setIsAuthenticated(true)
      setProfile(payload.profile)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load admin profile")
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    void loadProfile()
  }, [loadProfile])

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!password.trim()) {
      setError("Enter the admin password to continue")
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const response = await fetch("/api/admin/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password }),
      })
      const payload = await readJsonSafe(response)

      if (!response.ok) {
        throw new Error(payload.error || "Login failed")
      }

      setPassword("")
      setIsAuthenticated(true)
      await loadProfile(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleLogout = async () => {
    setError(null)
    setIsSubmitting(true)
    try {
      await fetch("/api/admin/logout", { method: "POST" })
    } finally {
      setIsSubmitting(false)
      setIsAuthenticated(false)
      setProfile(null)
    }
  }

  const generatedAtLabel = useMemo(() => {
    if (!profile?.generatedAt) {
      return "N/A"
    }

    const parsed = new Date(profile.generatedAt)
    if (Number.isNaN(parsed.getTime())) {
      return profile.generatedAt
    }
    return parsed.toLocaleString()
  }, [profile?.generatedAt])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-purple-600 dark:text-purple-400" />
          <p className="mt-4 text-gray-600 dark:text-gray-300">Loading admin diagnostics...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-purple-600 p-2">
              <ShieldCheck className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 dark:text-white">Admin Diagnostics</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Adaptive learning debug panel</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {mounted && <ThemeToggle />}
            <Button variant="ghost" asChild>
              <Link href="/dashboard">Back to Dashboard</Link>
            </Button>
            {isAuthenticated && (
              <Button variant="outline" onClick={handleLogout} disabled={isSubmitting}>
                <LogOut className="mr-2 h-4 w-4" />
                Sign Out
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!isAuthenticated ? (
          <Card className="mx-auto max-w-lg dark:border-gray-700 dark:bg-gray-800">
            <CardHeader>
              <CardTitle className="dark:text-white">Admin Login</CardTitle>
              <CardDescription className="dark:text-gray-300">
                Sign in to access adaptive profiling debug data.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="admin-password" className="text-sm font-medium dark:text-gray-200">
                    Password
                  </label>
                  <Input
                    id="admin-password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    placeholder="Enter admin password"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Signing In...
                    </>
                  ) : (
                    "Sign In"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" onClick={() => void loadProfile(true)} disabled={isRefreshing}>
                {isRefreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                Refresh
              </Button>
              <span className="text-sm text-gray-600 dark:text-gray-300">Last generated: {generatedAtLabel}</span>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <Card className="dark:border-gray-700 dark:bg-gray-800">
                <CardHeader>
                  <CardDescription className="dark:text-gray-300">Samples Used</CardDescription>
                  <CardTitle className="text-3xl dark:text-white">{profile?.sampleCount ?? 0}</CardTitle>
                </CardHeader>
              </Card>
              <Card className="dark:border-gray-700 dark:bg-gray-800">
                <CardHeader>
                  <CardDescription className="dark:text-gray-300">Dynamic Labels</CardDescription>
                  <CardTitle className="text-3xl dark:text-white">{profile?.dynamicLabelCount ?? 0}</CardTitle>
                </CardHeader>
              </Card>
              <Card className="dark:border-gray-700 dark:bg-gray-800">
                <CardHeader>
                  <CardDescription className="dark:text-gray-300">Adaptive Enabled</CardDescription>
                  <CardTitle className="text-3xl dark:text-white">{profile?.adaptiveConfig?.enabled ? "Yes" : "No"}</CardTitle>
                </CardHeader>
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="dark:border-gray-700 dark:bg-gray-800">
                <CardHeader>
                  <CardTitle className="dark:text-white">Score Means</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    {Object.entries(profile?.scoreMeans || {}).map(([dimension, value]) => (
                      <div key={dimension} className="flex items-center justify-between rounded border px-3 py-2 dark:border-gray-700">
                        <span className="capitalize dark:text-gray-200">{dimension}</span>
                        <span className="font-semibold dark:text-white">{value}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="dark:border-gray-700 dark:bg-gray-800">
                <CardHeader>
                  <CardTitle className="dark:text-white">Adaptive Config</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm dark:text-gray-200">
                    <div>Max Docs: {profile?.adaptiveConfig?.maxDocs ?? 0}</div>
                    <div>Cache TTL: {profile?.adaptiveConfig?.cacheTtlSeconds ?? 0}s</div>
                    <div>Max Dynamic Labels: {profile?.adaptiveConfig?.maxDynamicTagLabels ?? 0}</div>
                    <div>Max Suggestion Pool: {profile?.adaptiveConfig?.maxSuggestionPool ?? 0}</div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="dark:border-gray-700 dark:bg-gray-800">
                <CardHeader>
                  <CardTitle className="dark:text-white">Top Learned Tags</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    {(profile?.topLearnedTags || []).map((item) => (
                      <div key={item.tag} className="flex items-center justify-between rounded border px-3 py-2 dark:border-gray-700">
                        <span className="dark:text-gray-200">{item.tag}</span>
                        <span className="font-mono dark:text-white">{item.prior.toFixed(4)}</span>
                      </div>
                    ))}
                    {(profile?.topLearnedTags || []).length === 0 && (
                      <p className="text-gray-500 dark:text-gray-400">No learned tags available yet.</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card className="dark:border-gray-700 dark:bg-gray-800">
                <CardHeader>
                  <CardTitle className="dark:text-white">Top Suggestions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    {(profile?.topSuggestions || []).map((item, index) => (
                      <div key={`${item.text}-${index}`} className="rounded border px-3 py-2 dark:border-gray-700">
                        <div className="dark:text-gray-200">{item.text}</div>
                        <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">Frequency: {item.freq}</div>
                      </div>
                    ))}
                    {(profile?.topSuggestions || []).length === 0 && (
                      <p className="text-gray-500 dark:text-gray-400">No historical suggestions available yet.</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card className="dark:border-gray-700 dark:bg-gray-800">
              <CardHeader>
                <CardTitle className="dark:text-white">Score Quantiles</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="overflow-auto rounded bg-gray-100 p-4 text-xs text-gray-800 dark:bg-gray-900 dark:text-gray-100">
                  {JSON.stringify(profile?.scoreQuantiles || {}, null, 2)}
                </pre>
              </CardContent>
            </Card>

            <Card className="dark:border-gray-700 dark:bg-gray-800">
              <CardHeader>
                <CardTitle className="dark:text-white">Dynamic Label Preview</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {(profile?.dynamicLabelPreview || []).map((label) => (
                    <span
                      key={label}
                      className="rounded-full bg-purple-100 px-3 py-1 text-xs font-medium text-purple-800 dark:bg-purple-900 dark:text-purple-200"
                    >
                      {label}
                    </span>
                  ))}
                  {(profile?.dynamicLabelPreview || []).length === 0 && (
                    <p className="text-gray-500 dark:text-gray-400">No dynamic labels available yet.</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  )
}
