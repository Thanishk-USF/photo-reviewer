"use client"

import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ArrowLeft, Download, Share2, AlertCircle, Loader2 } from "lucide-react"
import Link from "next/link"
import { type AnalysisResult, getPhotoById } from "@/lib/api-client"
import { ThemeToggle } from "@/components/theme-toggle"
import { useTheme } from "next-themes"

export default function Results() {
  const searchParams = useSearchParams()
  const photoId = searchParams.get("id")
  const { theme, resolvedTheme } = useTheme()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mounted, setMounted] = useState(false)

  // Prevent hydration mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  // Add a class to the document element to prevent theme flash
  useEffect(() => {
    if (mounted && theme) {
      document.documentElement.classList.add('no-theme-transition')
      document.documentElement.classList.remove('no-theme-transition')
    }
  }, [mounted, theme])

  const [results, setResults] = useState<AnalysisResult | null>(null)

  useEffect(() => {
    async function loadResults() {
      try {
        setLoading(true)
        setError(null)

        if (photoId) {
          // If we have an ID, fetch the results from the API
          const data = await getPhotoById(photoId)
          setResults(data)
        } else {
          // Otherwise, try to get the results from sessionStorage
          const storedResults = sessionStorage.getItem("latestAnalysis")
          if (storedResults) {
            setResults(JSON.parse(storedResults))
          } else {
            throw new Error("No analysis results found")
          }
        }
      } catch (err) {
        console.error("Error loading results:", err)
        setError(err instanceof Error ? err.message : "Failed to load analysis results")
      } finally {
        setLoading(false)
      }
    }

    loadResults()
  }, [photoId])

  const scoreToColor = (score: number) => {
    if (score >= 8) return "bg-green-500"
    if (score >= 6) return "bg-yellow-500"
    return "bg-red-500"
  }

  const handleCopyHashtags = () => {
    if (!results?.hashtags) return

    navigator.clipboard
      .writeText(results.hashtags.join(" "))
      .then(() => {
        alert("Hashtags copied to clipboard!")
      })
      .catch((err) => {
        console.error("Failed to copy hashtags:", err)
      })
  }

  const handleDownloadReport = () => {
    if (!results) return

    // Create a simple text report
    const report = `
      Photo Analysis Report
      ---------------------
      Aesthetic Score: ${results.aestheticScore}/10
      Technical Score: ${results.technicalScore}/10
      
      Composition: ${results.composition}/10
      Lighting: ${results.lighting}/10
      Color: ${results.color}/10
      
      Style: ${results.style}
      Mood: ${results.mood}
      
      Tags: ${results.tags.join(", ")}
      
      Hashtags:
      ${results.hashtags.join(" ")}
      
      Improvement Suggestions:
      ${results.suggestions.map((s) => `- ${s}`).join("\n")}
    `.trim()

    // Create a blob and download it
    const blob = new Blob([report], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "photo-analysis-report.txt"
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-purple-600 dark:text-purple-400" />
          <p className="mt-4 text-gray-600 dark:text-gray-300">Loading analysis results...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-4">
        <Alert variant="destructive" className="mb-4 max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button asChild>
          <Link href="/">Return to Home</Link>
        </Button>
      </div>
    )
  }

  if (!results) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-4">
        <Alert className="mb-4 max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>No analysis results found</AlertDescription>
        </Alert>
        <Button asChild>
          <Link href="/">Return to Home</Link>
        </Button>
      </div>
    )
  }

   return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-8">
      <div className="container mx-auto px-4">
        <div className="mb-8 flex items-center justify-between">
          <Button variant="ghost" className="gap-2" asChild>
            <Link href="/dashboard">
              <ArrowLeft className="h-4 w-4" />
              Back to Dashboard
            </Link>
          </Button>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Photo Analysis Results</h1>
          <div className="flex gap-2 items-center">
            <ThemeToggle />
            <Button variant="ghost" size="sm" className="dark:text-gray-300 dark:hover:bg-gray-700" asChild>
              <Link href="/">Home</Link>
            </Button>
            <Button size="sm" onClick={handleDownloadReport}>
              <Download className="mr-2 h-4 w-4" />
              Download Report
            </Button>
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <Card>
              <CardContent className="p-4">
                <div className="overflow-hidden rounded-lg">
                  <img
                    src={results.imageUrl || "/placeholder.svg"}
                    alt="Analyzed photo"
                    className="h-auto w-full object-cover"
                  />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Style</p>
                    <p className="font-medium">{results.style}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Mood</p>
                    <p className="font-medium">{results.mood}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="mt-6">
              <CardContent className="p-4">
                <h3 className="mb-4 text-lg font-semibold">Improvement Suggestions</h3>
                <ul className="space-y-2">
                  {results.suggestions.map((suggestion, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-purple-500"></span>
                      <span>{suggestion}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-2">
            <Card className="mb-6">
              <CardContent className="p-6">
                <h3 className="mb-4 text-lg font-semibold">Aesthetic Analysis</h3>

                <div className="mb-6">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium">Overall Aesthetic Score</span>
                    <span className="text-lg font-bold">{results.aestheticScore}/10</span>
                  </div>
                  <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={`h-full ${scoreToColor(results.aestheticScore)}`}
                      style={{ width: `${results.aestheticScore * 10}%` }}
                    ></div>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-sm">Composition</span>
                      <span className="text-sm font-medium">{results.composition}</span>
                    </div>
                    <Progress value={results.composition * 10} className="h-2" />
                  </div>
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-sm">Lighting</span>
                      <span className="text-sm font-medium">{results.lighting}</span>
                    </div>
                    <Progress value={results.lighting * 10} className="h-2" />
                  </div>
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-sm">Color</span>
                      <span className="text-sm font-medium">{results.color}</span>
                    </div>
                    <Progress value={results.color * 10} className="h-2" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="mb-6">
              <CardContent className="p-6">
                <h3 className="mb-4 text-lg font-semibold">Content Tags</h3>
                <div className="flex flex-wrap gap-2">
                  {results.tags.map((tag, index) => (
                    <Badge
                      key={index}
                      variant="outline"
                      className="bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6">
                <h3 className="mb-4 text-lg font-semibold">Social Media Hashtags</h3>
                <div className="flex flex-wrap gap-2">
                  {results.hashtags.map((hashtag, index) => (
                    <Badge
                      key={index}
                      variant="outline"
                      className="bg-gradient-to-r from-purple-400 to-pink-400 text-white 
                      border-0 dark:from-purple-600 dark:to-pink-500"
                    >
                      {hashtag}
                    </Badge>
                  ))}
                </div>
                <div className="mt-4">
                  <Button variant="outline" className="w-full text-sm" onClick={handleCopyHashtags}>
                    Copy All Hashtags
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
