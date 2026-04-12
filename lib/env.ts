// Environment variable validation and access
export const env = {
  FLASK_API_URL: process.env.FLASK_API_URL || "http://localhost:5000",
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || "/api",
}
