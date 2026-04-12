"use client"

import type React from "react"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { UploadIcon, ImageIcon, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { analyzeImage } from "@/lib/api-client"

export function Upload() {
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [analysisId, setAnalysisId] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null)
    const selectedFile = e.target.files?.[0]

    if (!selectedFile) return

    // Check if file is an image
    if (!selectedFile.type.startsWith("image/")) {
      setError("Please select an image file")
      return
    }

    // Check file size (max 10MB)
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError("Image size should be less than 10MB")
      return
    }

    setFile(selectedFile)

    // Create preview
    const reader = new FileReader()
    reader.onload = () => {
      setPreview(reader.result as string)
    }
    reader.readAsDataURL(selectedFile)
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setUploadProgress(0)
    setError(null)

    // Simulate upload progress
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 95) {
          clearInterval(progressInterval)
          return 95
        }
        return prev + 5
      })
    }, 200)

    try {
      // Send the file to the Flask backend via our API client
      const result = await analyzeImage(file)

      clearInterval(progressInterval)
      setUploadProgress(100)

      if (!result.success) {
        throw new Error(result.error || "Analysis failed")
      }

      // Always store the result in sessionStorage
      console.log("Storing analysis result in sessionStorage:", result)
      sessionStorage.setItem("latestAnalysis", JSON.stringify(result))

      // Store the analysis ID if provided by the backend
      if (result.id) {
        setAnalysisId(result.id)
        // Redirect to results page with the analysis ID
        setTimeout(() => {
          router.push(`/results?id=${result.id}`)
        }, 500)
      } else {
        // If no ID is provided, redirect to results page without ID
        setTimeout(() => {
          router.push("/results")
        }, 500)
      }
    } catch (err) {
      clearInterval(progressInterval)
      setUploadProgress(0)
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.")
      setUploading(false)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setError(null)

    const droppedFile = e.dataTransfer.files?.[0]
    if (!droppedFile) return

    if (!droppedFile.type.startsWith("image/")) {
      setError("Please drop an image file")
      return
    }

    if (droppedFile.size > 10 * 1024 * 1024) {
      setError("Image size should be less than 10MB")
      return
    }

    setFile(droppedFile)

    const reader = new FileReader()
    reader.onload = () => {
      setPreview(reader.result as string)
    }
    reader.readAsDataURL(droppedFile)
  }

  const handleSelectImage = () => {
    // Directly trigger the file input click event
    document.getElementById("file-upload")?.click()
  }

  return (
    <div className="mx-auto max-w-xl">
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!preview ? (
        <div
          className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-300 bg-gray-50 p-12 text-center hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:hover:bg-gray-700"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="mb-4 rounded-full bg-purple-100 p-3 dark:bg-purple-900">
            <UploadIcon className="h-6 w-6 text-purple-600 dark:text-purple-400" />
          </div>
          <h3 className="mb-2 text-lg font-medium text-gray-900 dark:text-white">Upload your photo</h3>
          <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
            Drag and drop your image here, or click to browse
          </p>
          <input type="file" id="file-upload" className="hidden" accept="image/*" onChange={handleFileChange} />
          <Button
            variant="outline"
            onClick={handleSelectImage}
            className="cursor-pointer bg-white text-gray-800 
            hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 
            dark:text-white dark:hover:bg-gray-600"
          >
            <ImageIcon className="mr-2 h-4 w-4" />
            Select Image
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="relative mb-4 overflow-hidden rounded-lg">
            <img src={preview || "/placeholder.svg"} alt="Preview" className="h-64 w-full object-cover" />
          </div>
          <div className="flex items-center justify-between">
            <div className="flex-1 truncate pr-4">
              <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{file?.name}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {file?.size ? (file.size / 1024 / 1024).toFixed(2) : 0} MB
              </p>
            </div>
            {uploading ? (
              <div className="w-full max-w-[120px]">
                <Progress value={uploadProgress} className="h-2 w-full" />
              </div>
            ) : (
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setFile(null)
                    setPreview(null)
                  }}
                  className="dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  Change
                </Button>
                <Button size="sm" onClick={handleUpload} className="dark:bg-purple-700 dark:hover:bg-purple-600">
                  Analyze
                </Button>
              </div>
            )}
          </div>
          {uploading && (
            <div className="mt-4 flex items-center justify-center">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-purple-600 dark:text-purple-400" />
              <span className="text-sm text-gray-600 dark:text-gray-300">
                {uploadProgress < 100 ? "Analyzing your photo..." : "Analysis complete!"}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
