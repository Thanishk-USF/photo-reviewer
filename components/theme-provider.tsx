/*"use client"

import { ThemeProvider as NextThemesProvider } from "next-themes"
import { useEffect, useState } from "react"

export function ThemeProvider({ children, ...props }: { children: React.ReactNode } & Record<string, unknown>) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    // Add initializing class to body
   // document.body.classList.add('theme-initializing')
    //setMounted(true)
    // Add class to prevent transitions
  document.documentElement.classList.add('no-transitions')
  
  // Remove class after a short delay
  const timer = setTimeout(() => {
    document.documentElement.classList.remove('no-transitions')
  }, 100)
  
    
    // Remove initializing class after a short delay
   const timer2 = setTimeout(() => {
      document.body.classList.remove('theme-initializing')
    }, 50)

    
    return () => clearTimeout(timer)
  }, [])

  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
}
*/

"use client"

import { ThemeProvider as NextThemesProvider } from "next-themes"
import { useEffect } from "react"
import Cookies from 'js-cookie'

export function ThemeProvider({ children, ...props }: { children: React.ReactNode } & Record<string, unknown>) {
  useEffect(() => {
    const savedTheme = Cookies.get('theme')
  if (savedTheme) {
    // Apply the saved theme
    document.documentElement.classList.toggle('dark', savedTheme === 'dark')
  }
    // Sync theme with cookies for SSR
    const handleThemeChange = () => {
      const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light'
      //document.cookie = `theme=${theme}; max-age=${60 * 60 * 24 * 365}; path=/`
      Cookies.set('theme', theme, { expires: 365, path: '/' })
    }
    
    window.addEventListener('themechange', handleThemeChange)
    return () => window.removeEventListener('themechange', handleThemeChange)
  }, [])

  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
}