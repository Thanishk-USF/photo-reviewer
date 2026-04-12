import { type NextRequest, NextResponse } from "next/server"

const FLASK_API_URL = process.env.FLASK_API_URL || "http://localhost:5000"

function toFlaskApiPath(path: string): string {
  if (!path) {
    return "api"
  }
  return path.startsWith("api/") || path === "api" ? path : `api/${path}`
}

function upstreamUnavailableResponse() {
  return NextResponse.json(
    {
      success: false,
      error: "Failed to reach analysis service. Start the Flask backend (python backend/main.py) and retry.",
    },
    { status: 502 },
  )
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  try {
    const params = await context.params
    const path = params.path.join('/')
    const flaskPath = toFlaskApiPath(path)

    const url = new URL(request.url)
    const queryString = url.search

    const response = await fetch(`${FLASK_API_URL}/${flaskPath}${queryString}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    })

    // Check if response is JSON before parsing
    const contentType = response.headers.get('content-type')
    if (contentType?.includes('application/json')) {
      const data = await response.json()
      return NextResponse.json(data, { status: response.status })
    }

    // For non-JSON responses (like images), return the response directly
    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    })
  } catch (error) {
    console.error("Proxy GET error:", error)
    return upstreamUnavailableResponse()
  }
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  try {
    const params = await context.params
    const path = params.path.join("/")
    const flaskPath = toFlaskApiPath(path)

    const contentType = request.headers.get("content-type") || ""

    if (contentType.includes("multipart/form-data")) {
      const formData = await request.formData()
      const response = await fetch(`${FLASK_API_URL}/${flaskPath}`, {
        method: "POST",
        body: formData,
      })
      const responseType = response.headers.get("content-type") || ""
      if (responseType.includes("application/json")) {
        const data = await response.json()
        return NextResponse.json(data, { status: response.status })
      }
      return new Response(response.body, {
        status: response.status,
        headers: response.headers,
      })
    }

    const body = await request.json()
    const response = await fetch(`${FLASK_API_URL}/${flaskPath}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    const responseType = response.headers.get("content-type") || ""
    if (responseType.includes("application/json")) {
      const data = await response.json()
      return NextResponse.json(data, { status: response.status })
    }
    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    })
  } catch (error) {
    console.error("Proxy POST error:", error)
    return upstreamUnavailableResponse()
  }
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  try {
    const params = await context.params
    const path = params.path.join("/")
    const flaskPath = toFlaskApiPath(path)

    const response = await fetch(`${FLASK_API_URL}/${flaskPath}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    })

    const contentType = response.headers.get("content-type") || ""
    if (contentType.includes("application/json")) {
      const data = await response.json()
      return NextResponse.json(data, { status: response.status })
    }

    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    })
  } catch (error) {
    console.error("Proxy DELETE error:", error)
    return upstreamUnavailableResponse()
  }
}