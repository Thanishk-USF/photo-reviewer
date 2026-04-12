"use client"

import { Upload } from "@/components/upload"
import { Features } from "@/components/features"
import { HowItWorks } from "@/components/how-it-works"
import { ThemeToggle } from "@/components/theme-toggle"
import { useEffect } from 'react'
import Link from "next/link"

export default function Home() {
  useEffect(() => {
    // Check if we should open the upload dialog
    const params = new URLSearchParams(window.location.search)
    if (params.get('openUpload') === 'true') {
      // Increase the delay to ensure the component is fully mounted
      const timer = setTimeout(() => {
        const fileInput = document.getElementById('file-upload')
        if (fileInput) {
          fileInput.click()
        } else {
          console.error('File input element not found')
        }
      }, 1000) // Increased to 1000ms
      
      return () => clearTimeout(timer) // Clean up the timeout
    }
  }, [])
  
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800 dark:text-white">
      <header className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-purple-600 dark:bg-purple-700 p-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-white"
              >
                <path d="M15 2H9a1 1 0 0 0-1 1v2c0 .6.4 1 1 1h6c.6 0 1-.4 1-1V3c0-.6-.4-1-1-1Z" />
                <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
                <path d="M12 11v5" />
                <path d="m9 14 3 3 3-3" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">PhotoReviewer</h1>
          </div>
          <nav className="hidden md:block">
            <ul className="flex space-x-8">
              <li>
                {/* <a
                  href="#features"
                  className="relative overflow-hidden px-3 py-2 text-gray-600 transition-colors 
                  duration-300 hover:text-purple-600 dark:text-gray-300 dark:hover:text-purple-400 group"
                  onClick={(e) => {
                    // Create ripple effect
                    const button = e.currentTarget
                    const circle = document.createElement("span")
                    const diameter = Math.max(button.clientWidth, button.clientHeight)
                    const radius = diameter / 2

                    circle.style.width = circle.style.height = `${diameter}px`
                    circle.style.left = `${e.clientX - button.offsetLeft - radius}px`
                    circle.style.top = `${e.clientY - button.offsetTop - radius}px`
                    circle.classList.add("ripple")

                    const ripple = button.getElementsByClassName("ripple")[0]
                    if (ripple) {
                      ripple.remove()
                    }

                    button.appendChild(circle)
                  }}
                >
                  <span className="relative z-10">Features</span>
                  <span className="absolute inset-0 translate-y-full bg-gradient-to-r 
                  from-purple-400 to-pink-400 opacity-0 transition-all duration-300
                  group-hover:translate-y-0 group-hover:opacity-10dark:from-purple-500 dark:to-pink-500"></span>
                </a> */}
                 <a
    href="#features"
    className="relative overflow-hidden px-3 py-2 text-gray-600 transition-colors 
    duration-300 hover:text-purple-600 dark:text-gray-300 dark:hover:text-purple-400 group"
    onClick={(e) => {
      // Create ripple effect
      const button = e.currentTarget
      const circle = document.createElement("span")
      const diameter = Math.max(button.clientWidth, button.clientHeight)
      const radius = diameter / 2

      circle.style.width = circle.style.height = `${diameter}px`
      circle.style.left = `${e.clientX - button.offsetLeft - radius}px`
      circle.style.top = `${e.clientY - button.offsetTop - radius}px`
      circle.classList.add("ripple")

      const ripple = button.getElementsByClassName("ripple")[0]
      if (ripple) {
        ripple.remove()
      }

      button.appendChild(circle)
    }}
  >
    <span className="relative z-10">Features</span>
    <span className="absolute inset-0 translate-y-full bg-gradient-to-r 
    from-purple-400 to-pink-400 opacity-0 transition-all duration-300
    group-hover:translate-y-0 group-hover:opacity-10 dark:from-purple-500 dark:to-pink-500"></span>
  </a>
              </li>
              <li>
                <a
                  href="#how-it-works"
                  className="relative overflow-hidden px-3 py-2 text-gray-600 transition-colors 
                  duration-300 hover:text-purple-600 dark:text-gray-300 dark:hover:text-purple-400 group"
                  onClick={(e) => {
                    // Create ripple effect
                    const button = e.currentTarget
                    const circle = document.createElement("span")
                    const diameter = Math.max(button.clientWidth, button.clientHeight)
                    const radius = diameter / 2

                    circle.style.width = circle.style.height = `${diameter}px`
                    circle.style.left = `${e.clientX - button.offsetLeft - radius}px`
                    circle.style.top = `${e.clientY - button.offsetTop - radius}px`
                    circle.classList.add("ripple")

                    const ripple = button.getElementsByClassName("ripple")[0]
                    if (ripple) {
                      ripple.remove()
                    }

                    button.appendChild(circle)
                  }}
                >
                  <span className="relative z-10">How It Works</span>
                  <span className="absolute inset-0 translate-y-full bg-gradient-to-r 
                  from-blue-400 to-purple-400 opacity-0 transition-all duration-300
                  group-hover:translate-y-0 group-hover:opacity-10 dark:from-blue-500 dark:to-purple-500"></span>
                </a>
              </li>
            </ul>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/dashboard"
              className="rounded-lg bg-purple-600 px-4 py-2 text-white hover:bg-purple-700 
              dark:bg-purple-700 dark:text-black dark:hover:bg-purple-600"
            >
              Dashboard
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="container mx-auto px-4 py-16 text-center">
          <h2 className="mb-6 text-4xl font-bold text-gray-900 dark:text-white md:text-5xl">
            Photo Analysis
          </h2>
          <p className="mx-auto mb-10 max-w-2xl text-xl text-gray-600 dark:text-gray-300">
            Get instant feedback on your photos. Discover aesthetic scores, content tags, style
            analysis, and optimized hashtags for social media.
          </p>

          <Upload />
        </section>

        <Features />
        <HowItWorks />
      </main>

      <footer className="bg-gray-100 py-8 dark:bg-gray-800">
        <div className="container mx-auto px-4 text-center text-gray-600 dark:text-gray-300">
          <p>© 2026 PhotoReviewer. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
