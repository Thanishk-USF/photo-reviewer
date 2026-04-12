"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Calendar, ImageIcon, Upload, Grid, List, Star, Filter, AlertCircle, Loader2, Trash2 } from "lucide-react"
import Link from "next/link"
import { deletePhoto, getUserPhotos, type PhotoData } from "@/lib/api-client"
import { ThemeToggle } from "@/components/theme-toggle"

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [photos, setPhotos] = useState<PhotoData[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [nextOffset, setNextOffset] = useState(0)
  const [deletingPhotoId, setDeletingPhotoId] = useState<string | null>(null)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [photoToDelete, setPhotoToDelete] = useState<PhotoData | null>(null)
  const PAGE_SIZE = 24
  const [stats, setStats] = useState({
    totalPhotos: 0,
    averageScore: 0,
    thisMonth: 0,
    topCategory: "",
  })
  // Add mounted state to prevent hydration mismatch
  const [mounted, setMounted] = useState(false)


  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (photos.length === 0) {
      setStats({
        totalPhotos: 0,
        averageScore: 0,
        thisMonth: 0,
        topCategory: "",
      })
      return
    }

    const avgScore = photos.reduce((sum, photo) => sum + photo.score, 0) / photos.length

    const now = new Date()
    const thisMonth = now.getMonth()
    const thisYear = now.getFullYear()
    const monthPhotos = photos.filter((photo) => {
      try {
        const photoDate = new Date(photo.date)
        return photoDate.getMonth() === thisMonth && photoDate.getFullYear() === thisYear
      } catch {
        return false
      }
    })

    const tagCounts: Record<string, number> = {}
    photos.forEach((photo) => {
      if (photo.tags) {
        photo.tags.forEach((tag) => {
          tagCounts[tag] = (tagCounts[tag] || 0) + 1
        })
      }
    })

    let topCategory = ""
    let maxCount = 0
    Object.entries(tagCounts).forEach(([tag, count]) => {
      if (count > maxCount) {
        maxCount = count
        topCategory = tag
      }
    })

    setStats({
      totalPhotos: photos.length,
      averageScore: Number.parseFloat(avgScore.toFixed(1)) || 0,
      thisMonth: monthPhotos.length,
      topCategory: topCategory || "N/A",
    })
  }, [photos])

  useEffect(() => {
    async function loadPhotos() {
      try {
        setLoading(true)
        setError(null)

        const response = await getUserPhotos(PAGE_SIZE, 0)

        if (!response.success) {
          throw new Error(response.error || "Failed to load photos")
        }

        // Make sure photos exists before accessing it
        const photosList = response.photos || []
        setPhotos(photosList)
        setHasMore(Boolean(response.hasMore))
        setNextOffset(response.nextOffset ?? photosList.length)

      } catch (err) {
        console.error("Error loading photos:", err)
        setError(err instanceof Error ? err.message : "Failed to load photos")
      } finally {
        setLoading(false)
      }
    }

    loadPhotos()
  }, [])

  const handleLoadMore = async () => {
    if (loadingMore || !hasMore) return

    try {
      setLoadingMore(true)
      const response = await getUserPhotos(PAGE_SIZE, nextOffset)

      if (!response.success) {
        throw new Error(response.error || "Failed to load more photos")
      }

      const incoming = response.photos || []
      setPhotos((prev) => [...prev, ...incoming])
      setHasMore(Boolean(response.hasMore))
      setNextOffset(response.nextOffset ?? (nextOffset + incoming.length))
    } catch (err) {
      console.error("Error loading more photos:", err)
      setError(err instanceof Error ? err.message : "Failed to load more photos")
    } finally {
      setLoadingMore(false)
    }
  }

  const handleDeleteClick = (photo: PhotoData) => {
    setPhotoToDelete(photo)
    setIsDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!photoToDelete) return

    try {
      setDeletingPhotoId(photoToDelete.id)
      setError(null)

      const result = await deletePhoto(photoToDelete.id)
      if (!result.success) {
        throw new Error("Failed to delete photo")
      }

      setPhotos((prev) => prev.filter((item) => item.id !== photoToDelete.id))
      setIsDeleteDialogOpen(false)
      setPhotoToDelete(null)
    } catch (err) {
      console.error("Error deleting photo:", err)
      setError(err instanceof Error ? err.message : "Failed to delete photo")
    } finally {
      setDeletingPhotoId(null)
    }
  }

  const handleDeleteDialogOpenChange = (open: boolean) => {
    if (deletingPhotoId) return
    setIsDeleteDialogOpen(open)
    if (!open) {
      setPhotoToDelete(null)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-purple-600 dark:text-purple-400" />
          <p className="mt-4 text-gray-600 dark:text-gray-300">Loading dashboard data...</p>
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
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-white"
              >
                <path d="M15 2H9a1 1 0 0 0-1 1v2c0 .6.4 1 1 1h6c.6 0 1-.4 1-1V3c0-.6-.4-1-1-1Z" />
                <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
                <path d="M12 11v5" />
                <path d="m9 14 3 3 3-3" />
              </svg>
            </div>
            <Link href="/">
              <h1 className="text-lg font-bold text-gray-900 dark:text-white">PhotoReviewer</h1>
            </Link>
          </div>
          <div className="flex items-center gap-4">
            {mounted && <ThemeToggle />}
            <Button variant="ghost" size="sm" className="dark:text-gray-300 dark:hover:bg-gray-700" asChild>
              <Link href="/">Home</Link>
            </Button>
            <Button size="sm" className="dark:bg-purple-700 dark:hover:bg-purple-600" asChild>
              <Link href="/?openUpload=true">
                <Upload className="mr-2 h-4 w-4" />
                Upload New
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <AlertDialog open={isDeleteDialogOpen} onOpenChange={handleDeleteDialogOpenChange}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete photo?</AlertDialogTitle>
              <AlertDialogDescription>
                {`This will permanently remove ${photoToDelete?.name || "this photo"} from your dashboard.`}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={Boolean(deletingPhotoId)}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault()
                  void handleConfirmDelete()
                }}
                disabled={Boolean(deletingPhotoId)}
                className="bg-red-600 hover:bg-red-700"
              >
                {deletingPhotoId ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  "Delete"
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
            <p className="text-gray-600 dark:text-gray-300">Manage and analyze your photo collection</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
            >
              <Filter className="mr-2 h-4 w-4" />
              Filter
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
            >
              <Calendar className="mr-2 h-4 w-4" />
              Date Range
            </Button>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <Card className="dark:border-gray-700 dark:bg-gray-800">
            <CardContent className="flex items-center justify-between p-6">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Photos</p>
                <p className="text-2xl font-bold dark:text-white">{stats.totalPhotos}</p>
              </div>
              <div className="rounded-full bg-purple-100 p-2 dark:bg-purple-900">
                <ImageIcon className="h-4 w-4 text-purple-600 dark:text-purple-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="dark:border-gray-700 dark:bg-gray-800">
            <CardContent className="flex items-center justify-between p-6">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Average Score</p>
                <p className="text-2xl font-bold dark:text-white">{stats.averageScore}</p>
              </div>
              <div className="rounded-full bg-purple-100 p-2 dark:bg-purple-900">
                <Star className="h-4 w-4 text-purple-600 dark:text-purple-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="dark:border-gray-700 dark:bg-gray-800">
            <CardContent className="flex items-center justify-between p-6">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">This Month</p>
                <p className="text-2xl font-bold dark:text-white">{stats.thisMonth}</p>
              </div>
              <div className="rounded-full bg-purple-100 p-2 dark:bg-purple-900">
                <Calendar className="h-4 w-4 text-purple-600 dark:text-purple-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="dark:border-gray-700 dark:bg-gray-800">
            <CardContent className="flex items-center justify-between p-6">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Top Category</p>
                <p className="text-2xl font-bold dark:text-white">{stats.topCategory}</p>
              </div>
              <div className="rounded-full bg-purple-100 p-2 dark:bg-purple-900">
                <ImageIcon className="h-4 w-4 text-purple-600 dark:text-purple-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-8">
          <Tabs defaultValue="recent">
            <div className="flex items-center justify-between">
              <TabsList className="dark:bg-gray-700">
                <TabsTrigger
                  value="recent"
                  className="dark:data-[state=active]:bg-gray-800 dark:data-[state=active]:text-white"
                >
                  Recent Photos
                </TabsTrigger>
                <TabsTrigger
                  value="top"
                  className="dark:data-[state=active]:bg-gray-800 dark:data-[state=active]:text-white"
                >
                  Top Rated
                </TabsTrigger>
                <TabsTrigger
                  value="collections"
                  className="dark:data-[state=active]:bg-gray-800 dark:data-[state=active]:text-white"
                >
                  Collections
                </TabsTrigger>
              </TabsList>
              <div className="flex gap-2">
                <Button variant="ghost" size="icon" className="dark:text-gray-300 dark:hover:bg-gray-700">
                  <Grid className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" className="dark:text-gray-300 dark:hover:bg-gray-700">
                  <List className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <TabsContent value="recent" className="mt-6">
              {!photos || photos.length === 0 ? (
                <div className="rounded-lg border bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
                  <p className="text-gray-600 dark:text-gray-300">
                    No photos found. Upload your first photo to get started!
                  </p>
                  <Button className="mt-4 dark:bg-purple-700 dark:hover:bg-purple-600" asChild>
                    <Link href="/">Upload Photo</Link>
                  </Button>
                </div>
              ) : (
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                  {photos.map((photo) => (
                    <Card key={photo.id} className="overflow-hidden dark:border-gray-700 dark:bg-gray-800">
                      <Link href={`/results?id=${photo.id}`}>
                        <div className="aspect-video w-full overflow-hidden">
                          <img
                            src={photo.thumbnail || "/placeholder.svg"}
                            alt={photo.name}
                            className="h-full w-full object-cover transition-transform hover:scale-105"
                            onError={(e) => {
                              const target = e.currentTarget
                              if (!target.src.endsWith('/placeholder.svg')) {
                                target.src = '/placeholder.svg'
                              }
                            }}
                          />
                        </div>
                      </Link>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div className="min-w-0 flex-1 pr-2">
                            <h3 className="truncate font-medium dark:text-white" title={photo.name}>{photo.name}</h3>
                            <p className="truncate text-xs text-gray-500 dark:text-gray-400" title={photo.date}>{photo.date}</p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-purple-100 text-sm font-semibold text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                              {photo.score}
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-red-500 hover:bg-red-500/10 hover:text-red-600"
                              onClick={() => handleDeleteClick(photo)}
                              disabled={deletingPhotoId === photo.id}
                              aria-label={`Delete ${photo.name}`}
                            >
                              {deletingPhotoId === photo.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {hasMore && (
                <div className="mt-6 flex justify-center">
                  <Button
                    variant="outline"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
                  >
                    {loadingMore ? "Loading..." : "Show More"}
                  </Button>
                </div>
              )}
            </TabsContent>

            <TabsContent value="top">
              <div className="mt-6 rounded-lg border bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
                <p className="text-gray-600 dark:text-gray-300">Top rated photos will appear here</p>
              </div>
            </TabsContent>

            <TabsContent value="collections">
              <div className="mt-6 rounded-lg border bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
                <p className="text-gray-600 dark:text-gray-300">Your collections will appear here</p>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  )
}
