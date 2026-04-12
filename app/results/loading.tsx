"use client"

import { Loader2 } from "lucide-react"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

// NoSSR wrapper component
function NoSSR({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false)
  
  useEffect(() => {
    setMounted(true)
  }, [])
  
  if (!mounted) {
    return null
  }
  
  return <>{children}</>
}

export default function Loading() {
  // Force dark mode if that's what was active
  useEffect(() => {
    try {
      const theme = localStorage.getItem("theme") || "system"
      const isDark = theme === "dark" || 
        (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)
      
      if (isDark) {
        document.documentElement.classList.add("dark")
      }
    } catch (e) {
      // Handle localStorage access errors
    }
  }, [])

  return (
    <NoSSR>
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-purple-600 dark:text-purple-400" />
          <p className="mt-4 text-gray-600 dark:text-gray-300">Loading analysis results...</p>
        </div>
      </div>
    </NoSSR>
  )
}
