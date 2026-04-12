"use client"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { useEffect, useState, useRef } from "react"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const toggleRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  const toggleTheme = () => {
    setTheme(theme === "light" ? "dark" : "light")
    
    // Add smooth scrolling to center the button
    if (toggleRef.current) {
      toggleRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "center"
      })
    }
  }

  if (!mounted) {
    return <div className="w-[106px] h-[24px]"></div> 
  }

  return (
    <div 
      ref={toggleRef}
      className="flex items-center space-x-2 transition-transform duration-300 scroll-mt-8"
    >
      <Sun
        className={`h-[1.2rem] w-[1.2rem] transition-transform duration-300 ${
          theme === "dark" ? "text-[#A1A1AA] scale-75 rotate-12" : "text-foreground scale-100 rotate-0"
        }`}
      />
      <Switch
        checked={theme === "dark"}
        onCheckedChange={toggleTheme}
        aria-label="Toggle theme"
        className="transition-all duration-500 ease-in-out hover:scale-110"
      />
      <style jsx global>{`
        .peer .rounded-full {
          transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        }
      `}</style>
      <Moon
        className={`h-[1.2rem] w-[1.2rem] transition-transform duration-300 ${
          theme === "light" ? "text-[#A1A1AA] scale-75 rotate-12" : "text-foreground scale-100 rotate-0"
        }`}
      />
    </div>
  )
}
