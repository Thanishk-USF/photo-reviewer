import { type NextRequest, NextResponse } from "next/server"

import {
  ADMIN_SESSION_COOKIE_NAME,
  adminSessionCookieOptions,
  createAdminSessionToken,
  isAdminPasswordConfigured,
  verifyAdminPassword,
} from "@/lib/admin-auth"

type LoginPayload = {
  password?: string
}

export async function POST(request: NextRequest) {
  if (!isAdminPasswordConfigured()) {
    return NextResponse.json(
      {
        success: false,
        error: "ADMIN_DEBUG_PASSWORD is not configured",
      },
      { status: 500 },
    )
  }

  let payload: LoginPayload = {}
  try {
    payload = (await request.json()) as LoginPayload
  } catch {
    payload = {}
  }

  const password = typeof payload.password === "string" ? payload.password : ""
  if (!verifyAdminPassword(password)) {
    return NextResponse.json(
      {
        success: false,
        error: "Invalid admin credentials",
      },
      { status: 401 },
    )
  }

  const response = NextResponse.json({ success: true })
  response.cookies.set({
    name: ADMIN_SESSION_COOKIE_NAME,
    value: createAdminSessionToken(),
    ...adminSessionCookieOptions(),
  })
  return response
}
