/*import { type NextRequest, NextResponse } from "next/server"

// This is a mock implementation of the image analysis API
// In a real implementation, this would connect to your Flask backend

export async function POST(request: NextRequest) {
  try {
    console.log("Received analyze request")

    // In a real implementation, you would:
    // 1. Parse the multipart form data to get the image
    // const formData = await request.formData();
    // const image = formData.get('image') as File;

    // 2. Send the image to your Flask backend
    // const flaskResponse = await fetch('http://your-flask-backend/analyze', {
    //   method: 'POST',
    //   body: formData,
    // });
    // const data = await flaskResponse.json();

    // For now, we'll return mock data
    await new Promise((resolve) => setTimeout(resolve, 2000)) // Simulate processing time

    const mockResult = {
      success: true,
      id: "mock-" + Date.now(),
      imageUrl: "/placeholder.svg?height=600&width=800",
      thumbnailUrl: "/placeholder.svg?height=100&width=150",
      aestheticScore: 7.8,
      technicalScore: 8.2,
      composition: 7.5,
      lighting: 8.0,
      color: 8.5,
      style: "Minimalist",
      mood: "Calm",
      tags: [
        "nature",
        "landscape",
        "mountains",
        "sunset",
        "trees",
        "silhouette",
        "outdoor",
        "peaceful",
        "scenic",
        "dusk",
      ],
      hashtags: [
        "#naturephotography",
        "#landscapephotography",
        "#sunset",
        "#mountainview",
        "#outdooradventures",
        "#naturelover",
        "#peacefulmoments",
        "#scenicview",
        "#goldenhour",
        "#silhouettes",
      ],
      suggestions: [
        "The horizon line could be straighter for better composition",
        "Consider increasing contrast slightly to make the silhouettes pop more",
        "The image has a slight color cast that could be corrected",
      ],
    }

    console.log("Returning mock analysis result:", mockResult)
    return NextResponse.json(mockResult)
  } catch (error) {
    console.error("Error processing image:", error)
    return NextResponse.json({ success: false, error: "Failed to process image" }, { status: 500 })
  }
}
*/

import { type NextRequest, NextResponse } from "next/server"

const FLASK_API_URL = process.env.FLASK_API_URL || "http://localhost:5000"

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const flaskResponse = await fetch(`${FLASK_API_URL}/api/analyze`, {
      method: "POST",
      body: formData,
    })

    const contentType = flaskResponse.headers.get("content-type") || ""
    if (contentType.includes("application/json")) {
      const data = await flaskResponse.json()
      return NextResponse.json(data, { status: flaskResponse.status })
    }

    const bodyText = await flaskResponse.text()
    if (!flaskResponse.ok) {
      return NextResponse.json(
        {
          success: false,
          error: bodyText || "Failed to analyze image",
        },
        { status: flaskResponse.status },
      )
    }

    return NextResponse.json(
      {
        success: false,
        error: "Unexpected response from analysis service",
      },
      { status: 502 },
    )
  } catch (error) {
    console.error("Analyze route error:", error)
    return NextResponse.json(
      {
        success: false,
        error: "Failed to reach analysis service",
      },
      { status: 502 },
    )
  }
}