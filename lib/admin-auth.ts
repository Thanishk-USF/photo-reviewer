import { createHash, createHmac, randomBytes, timingSafeEqual } from "crypto"

export const ADMIN_SESSION_COOKIE_NAME = "admin_debug_session"
const DEFAULT_SESSION_TTL_SECONDS = 8 * 60 * 60

function getAdminPassword(): string {
  return (process.env.ADMIN_DEBUG_PASSWORD || "").trim()
}

function hashValue(value: string): Buffer {
  return createHash("sha256").update(value).digest()
}

function signPayload(payload: string): string {
  const secret = getAdminPassword()
  return createHmac("sha256", secret).update(payload).digest("hex")
}

export function isAdminPasswordConfigured(): boolean {
  return getAdminPassword().length > 0
}

export function verifyAdminPassword(password: string): boolean {
  const configured = getAdminPassword()
  if (!configured) {
    return false
  }

  const passwordHash = hashValue(typeof password === "string" ? password : "")
  const configuredHash = hashValue(configured)
  return timingSafeEqual(passwordHash, configuredHash)
}

export function createAdminSessionToken(ttlSeconds = DEFAULT_SESSION_TTL_SECONDS): string {
  const boundedTtl = Math.max(300, ttlSeconds)
  const expiresAt = Date.now() + boundedTtl * 1000
  const nonce = randomBytes(12).toString("hex")
  const payload = `${expiresAt}.${nonce}`
  const signature = signPayload(payload)
  return `${payload}.${signature}`
}

export function isValidAdminSessionToken(token: string | undefined): boolean {
  if (!token) {
    return false
  }
  if (!isAdminPasswordConfigured()) {
    return false
  }

  const parts = token.split(".")
  if (parts.length !== 3) {
    return false
  }

  const [expiresAtRaw, nonce, signature] = parts
  const expiresAt = Number(expiresAtRaw)
  if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
    return false
  }

  const payload = `${expiresAtRaw}.${nonce}`
  const expectedSignature = signPayload(payload)
  const expectedBuffer = Buffer.from(expectedSignature)
  const actualBuffer = Buffer.from(signature)
  if (expectedBuffer.length !== actualBuffer.length) {
    return false
  }

  return timingSafeEqual(expectedBuffer, actualBuffer)
}

export function adminSessionCookieOptions(ttlSeconds = DEFAULT_SESSION_TTL_SECONDS) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: Math.max(300, ttlSeconds),
  }
}
