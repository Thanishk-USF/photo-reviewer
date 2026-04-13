"use client"

import type React from "react"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { UploadIcon, ImageIcon, Loader2, AlertCircle, CheckCircle2, XCircle, Clock3, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { analyzeImage, type AnalysisResult } from "@/lib/api-client"

type UploadStatus = "queued" | "uploading" | "success" | "error"

type UploadItem = {
  id: string
  file: File
  preview: string
  status: UploadStatus
  progress: number
  error?: string
  resultId?: string
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
const MAX_BATCH_FILES = 12
const MAX_CONCURRENCY = 2

function createUploadId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function validateImageFile(file: File): string | null {
  if (!file.type.startsWith("image/")) {
    return "not an image"
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "larger than 10MB"
  }

  return null
}

async function fileToDataUrl(file: File): Promise<string> {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ""))
    reader.onerror = () => reject(new Error("Failed to read image preview"))
    reader.readAsDataURL(file)
  })
}

export function Upload() {
  const router = useRouter()
  const [items, setItems] = useState<UploadItem[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const updateItem = (id: string, patch: Partial<UploadItem>) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)))
  }

  const handleFiles = async (incomingFiles: FileList | null) => {
    if (!incomingFiles || incomingFiles.length === 0) {
      return
    }

    const selectedFiles = Array.from(incomingFiles)
    const validationErrors: string[] = []
    const validFiles: File[] = []

    for (const candidate of selectedFiles) {
      const reason = validateImageFile(candidate)
      if (reason) {
        validationErrors.push(`${candidate.name}: ${reason}`)
      } else {
        validFiles.push(candidate)
      }
    }

    const remainingSlots = Math.max(0, MAX_BATCH_FILES - items.length)
    if (remainingSlots <= 0) {
      setError(`Queue limit reached (${MAX_BATCH_FILES} images). Remove some files first.`)
      return
    }

    const filesToAdd = validFiles.slice(0, remainingSlots)
    if (validFiles.length > filesToAdd.length) {
      validationErrors.push(`Only ${MAX_BATCH_FILES} images can be queued at once.`)
    }

    if (filesToAdd.length > 0) {
      const preparedItems: UploadItem[] = await Promise.all(
        filesToAdd.map(async (file) => ({
          id: createUploadId(),
          file,
          preview: await fileToDataUrl(file),
          status: "queued",
          progress: 0,
        })),
      )
      setItems((prev) => [...prev, ...preparedItems])
    }

    setError(validationErrors.length > 0 ? validationErrors.join(" | ") : null)
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    void handleFiles(event.target.files)
    event.target.value = ""
  }

  const handleUpload = async () => {
    if (uploading) {
      return
    }

    const queue = items.filter((item) => item.status === "queued" || item.status === "error")
    if (queue.length === 0) {
      setError("Select at least one valid image to analyze.")
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setError(null)
    const queuedIds = new Set(queue.map((item) => item.id))
    setItems((prev) =>
      prev.map((item) =>
        queuedIds.has(item.id)
          ? {
              ...item,
              status: "queued",
              progress: 0,
              error: undefined,
              resultId: undefined,
            }
          : item,
      ),
    )

    const successfulResults: AnalysisResult[] = []
    let cursor = 0
    let completed = 0

    const updateBatchProgress = () => {
      setUploadProgress(Math.round((completed / queue.length) * 100))
    }

    const worker = async () => {
      while (cursor < queue.length) {
        const item = queue[cursor]
        cursor += 1
        if (!item) {
          continue
        }

        updateItem(item.id, { status: "uploading", progress: 5, error: undefined })
        const progressInterval = setInterval(() => {
          setItems((prev) =>
            prev.map((entry) => {
              if (entry.id !== item.id || entry.status !== "uploading") {
                return entry
              }
              const nextProgress = Math.min(90, entry.progress + 7)
              return { ...entry, progress: nextProgress }
            }),
          )
        }, 180)

        try {
          const result = await analyzeImage(item.file)
          if (!result.success) {
            throw new Error(result.error || "Analysis failed")
          }

          successfulResults.push(result)
          updateItem(item.id, {
            status: "success",
            progress: 100,
            resultId: typeof result.id === "string" && result.id.trim() ? result.id.trim() : undefined,
          })
        } catch (err) {
          updateItem(item.id, {
            status: "error",
            progress: 0,
            error: err instanceof Error ? err.message : "Upload failed",
          })
        } finally {
          clearInterval(progressInterval)
          completed += 1
          updateBatchProgress()
        }
      }
    }

    const workers = Array.from({ length: Math.min(MAX_CONCURRENCY, queue.length) }, () => worker())
    await Promise.all(workers)

    setUploading(false)

    if (successfulResults.length === 0) {
      setUploadProgress(0)
      setError("All analyses failed. Fix file issues and try again.")
      return
    }

    setUploadProgress(100)

    // Keep latest single result compatibility and add a batch record for multi-upload runs.
    const latestResult = successfulResults[successfulResults.length - 1]
    sessionStorage.setItem("latestAnalysis", JSON.stringify(latestResult))
    sessionStorage.setItem("latestBatchAnalysis", JSON.stringify(successfulResults))

    const successfulIds = successfulResults
      .map((result) => (typeof result.id === "string" ? result.id.trim() : ""))
      .filter((id) => id.length > 0)

    setTimeout(() => {
      if (successfulIds.length > 1) {
        router.push(`/results?ids=${encodeURIComponent(successfulIds.join(","))}`)
        return
      }

      if (successfulIds.length === 1) {
        router.push(`/results?id=${encodeURIComponent(successfulIds[0])}`)
        return
      }

      router.push("/results")
    }, 400)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    void handleFiles(e.dataTransfer.files)
  }

  const handleSelectImage = () => {
    document.getElementById("file-upload")?.click()
  }

  const handleRemoveItem = (id: string) => {
    if (uploading) {
      return
    }
    setItems((prev) => prev.filter((item) => item.id !== id))
  }

  const handleClearAll = () => {
    if (uploading) {
      return
    }
    setItems([])
    setUploadProgress(0)
    setError(null)
  }

  const totalQueued = items.filter((item) => item.status === "queued" || item.status === "error").length
  const totalSuccess = items.filter((item) => item.status === "success").length

  const statusBadge = (status: UploadStatus) => {
    if (status === "success") {
      return (
        <Badge variant="outline" className="border-green-500 text-green-600 dark:text-green-400">
          <CheckCircle2 className="mr-1 h-3 w-3" /> Done
        </Badge>
      )
    }
    if (status === "error") {
      return (
        <Badge variant="outline" className="border-red-500 text-red-600 dark:text-red-400">
          <XCircle className="mr-1 h-3 w-3" /> Failed
        </Badge>
      )
    }
    if (status === "uploading") {
      return (
        <Badge variant="outline" className="border-purple-500 text-purple-600 dark:text-purple-400">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" /> Analyzing
        </Badge>
      )
    }
    return (
      <Badge variant="outline" className="border-gray-400 text-gray-600 dark:text-gray-300">
        <Clock3 className="mr-1 h-3 w-3" /> Queued
      </Badge>
    )
  }

  return (
    <div className="mx-auto max-w-xl">
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {items.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-300 bg-gray-50 p-12 text-center hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:hover:bg-gray-700"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="mb-4 rounded-full bg-purple-100 p-3 dark:bg-purple-900">
            <UploadIcon className="h-6 w-6 text-purple-600 dark:text-purple-400" />
          </div>
          <h3 className="mb-2 text-lg font-medium text-gray-900 dark:text-white">Upload your photo</h3>
          <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">Drag and drop images here, or click to browse</p>
          <input type="file" id="file-upload" className="hidden" accept="image/*" multiple onChange={handleFileChange} />
          <Button
            variant="outline"
            onClick={handleSelectImage}
            className="cursor-pointer bg-white text-gray-800 
            hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 
            dark:text-white dark:hover:bg-gray-600"
          >
            <ImageIcon className="mr-2 h-4 w-4" />
            Select Images
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <input type="file" id="file-upload" className="hidden" accept="image/*" multiple onChange={handleFileChange} />

          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">Upload Queue</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {items.length} image(s) selected, {totalSuccess} complete, {totalQueued} remaining
              </p>
            </div>
            {uploading ? (
              <div className="w-full max-w-[180px]">
                <Progress value={uploadProgress} className="h-2.5 w-full" />
              </div>
            ) : (
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSelectImage}
                  className="dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  Add More
                </Button>
                <Button variant="ghost" size="sm" onClick={handleClearAll} className="dark:text-gray-300 dark:hover:bg-gray-700">
                  Clear
                </Button>
                <Button size="sm" onClick={handleUpload} className="dark:bg-purple-700 dark:hover:bg-purple-600" disabled={totalQueued === 0}>
                  Analyze Queue
                </Button>
              </div>
            )}
          </div>

          <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
            {items.map((item) => (
              <div key={item.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                <div className="flex items-start gap-3">
                  <img src={item.preview || "/placeholder.svg"} alt={item.file.name} className="h-14 w-14 rounded-md object-cover" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{item.file.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{(item.file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {statusBadge(item.status)}
                        {!uploading && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 dark:text-gray-300 dark:hover:bg-gray-700"
                            onClick={() => handleRemoveItem(item.id)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>

                    {(item.status === "uploading" || item.status === "success") && (
                      <div className="mt-2">
                        <Progress value={item.progress} className="h-1.5" />
                      </div>
                    )}

                    {item.error && <p className="mt-2 text-xs text-red-500 dark:text-red-400">{item.error}</p>}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {uploading && (
            <div className="mt-4 flex items-center justify-center">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-purple-600 dark:text-purple-400" />
              <span className="text-sm text-gray-600 dark:text-gray-300">
                {uploadProgress < 100 ? "Analyzing selected photos..." : "Analysis complete!"}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
