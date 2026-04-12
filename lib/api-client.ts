// API client for communicating with the Flask backend
import { env } from "@/lib/env"

// Define the response types for better type safety
export interface AnalysisResult {
  success: boolean
  id?: string
  imageUrl: string
  thumbnailUrl?: string
  aestheticScore: number
  technicalScore: number
  composition: number
  lighting: number
  color: number
  style: string
  mood: string
  tags: string[]
  hashtags: string[]
  suggestions: string[]
  error?: string
}

export interface PhotoData {
  id: string
  name: string
  score: number
  date: string
  thumbnail: string
  tags?: string[]
}

export interface UserPhotosResponse {
  success: boolean
  photos: PhotoData[]
  hasMore?: boolean
  nextOffset?: number
  error?: string
}

// Base URL for the Flask API
const API_BASE_URL = env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")
const REQUEST_TIMEOUT_MS = 30000

async function fetchWithTimeout(url: string, options: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timed out. Please try again.")
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

async function getErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  const contentType = response.headers.get("content-type") || ""

  if (contentType.includes("application/json")) {
    const errorData = await response.json()
    return errorData.error || fallbackMessage
  }

  const text = await response.text()
  return text || fallbackMessage
}

/**
 * Analyzes an image using the Flask backend
 * @param file The image file to analyze
 * @returns Analysis results
 */
export async function analyzeImage(file: File): Promise<AnalysisResult> {
  try {
    const formData = new FormData();
    formData.append('image', file);
    console.log("Sending image for analysis to:", `${API_BASE_URL}/analyze`)
    // Send to Flask backend
    const response = await fetchWithTimeout(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header when using FormData
      // The browser will set it with the correct boundary
    })

    if (!response.ok) {
      throw new Error(await getErrorMessage(response, "Failed to analyze image"))
    }

    const result = await response.json()
    console.log("Analysis result:", result)
    return result
  } catch (error) {
    console.error("Error analyzing image:", error)
    throw error
  }
}

/**
 * Fetches the user's previously analyzed photos
 * @param limit Optional limit on the number of photos to return
 * @returns List of user photos
 */
export async function getUserPhotos(limit?: number, offset?: number): Promise<UserPhotosResponse> {
  try {
    // Handle both absolute and relative URLs
    const searchParams = new URLSearchParams()

    // Add limit parameter if provided
    if (limit) {
      searchParams.set("limit", String(limit))
    }

    if (offset && offset > 0) {
      searchParams.set("offset", String(offset))
    }

    const requestUrl = searchParams.size
      ? `${API_BASE_URL}/photos?${searchParams.toString()}`
      : `${API_BASE_URL}/photos`

    console.log("Fetching photos from:", requestUrl)

    const response = await fetchWithTimeout(requestUrl, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      throw new Error(await getErrorMessage(response, "Failed to fetch photos"))
    }

    const data = await response.json()
    console.log("Fetched photos:", data)

    // Ensure the response has the expected structure
    return {
      success: data.success || false,
      photos: Array.isArray(data.photos) ? data.photos : [],
      hasMore: Boolean(data.hasMore),
      nextOffset: typeof data.nextOffset === "number" ? data.nextOffset : undefined,
      error: data.error,
    }
  } catch (error) {
    console.error("Error fetching photos:", error)
    // Return a valid response structure even on error
    return {
      success: false,
      photos: [],
      hasMore: false,
      error: error instanceof Error ? error.message : "Failed to fetch photos",
    }
  }
}

/**
 * Fetches a specific photo analysis by ID
 * @param photoId The ID of the photo to fetch
 * @returns Analysis results for the specified photo
 */
export async function getPhotoById(photoId: string): Promise<AnalysisResult> {
  try {
    console.log("Fetching photo by ID:", photoId)
    const response = await fetchWithTimeout(`${API_BASE_URL}/photos/${photoId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      throw new Error(await getErrorMessage(response, "Failed to fetch photo"))
    }

    const result = await response.json()
    console.log("Fetched photo:", result)
    return result
  } catch (error) {
    console.error("Error fetching photo:", error)
    throw error
  }
}

/**
 * Deletes a photo analysis by ID
 * @param photoId The ID of the photo to delete
 * @returns Success status
 */
export async function deletePhoto(photoId: string): Promise<{ success: boolean }> {
  try {
    console.log("Deleting photo:", photoId)
    const response = await fetchWithTimeout(`${API_BASE_URL}/photos/${photoId}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      throw new Error(await getErrorMessage(response, "Failed to delete photo"))
    }

    const result = await response.json()
    console.log("Delete result:", result)
    return result
  } catch (error) {
    console.error("Error deleting photo:", error)
    throw error
  }
}
