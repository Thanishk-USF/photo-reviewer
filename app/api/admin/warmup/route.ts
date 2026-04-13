import { type NextRequest, NextResponse } from "next/server"

import { ADMIN_SESSION_COOKIE_NAME, isValidAdminSessionToken } from "@/lib/admin-auth"

const FLASK_API_URL = process.env.FLASK_API_URL || "http://localhost:5000"

function unauthorized() {
  return NextResponse.json(
    {
      success: false,
      error: "Admin authentication required",
    },
    { status: 401 },
  )
}

export async function POST(request: NextRequest) {
  const sessionToken = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)?.value
  if (!isValidAdminSessionToken(sessionToken)) {
    return unauthorized()
  }

  const adminDebugKey = (process.env.ADMIN_DEBUG_KEY || process.env.ADMIN_DEBUG_PASSWORD || "").trim()
  if (!adminDebugKey) {
    return NextResponse.json(
      {
        success: false,
        error: "ADMIN_DEBUG_PASSWORD is not configured",
      },
      { status: 500 },
    )
  }

  let payload: { runInference?: boolean } = {}
  try {
    payload = (await request.json()) as { runInference?: boolean }
  } catch {
    payload = {}
  }

  try {
    const response = await fetch(`${FLASK_API_URL}/api/admin/warmup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Debug-Key": adminDebugKey,
      },
      body: JSON.stringify({ runInference: Boolean(payload.runInference) }),
      cache: "no-store",
    })

    const contentType = response.headers.get("content-type") || ""
    if (contentType.includes("application/json")) {
      const data = await response.json()
      return NextResponse.json(data, { status: response.status })
    }

    const text = await response.text()
    return NextResponse.json(
      {
        success: false,
        error: text || "Unexpected response from analysis service",
      },
      { status: 502 },
    )
  } catch (error) {
    console.error("Admin warmup proxy error:", error)
    return NextResponse.json(
      {
        success: false,
        error: "Failed to reach analysis service",
      },
      { status: 502 },
    )
  }
}
