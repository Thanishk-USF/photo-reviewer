# PhotoReviewer

A photo analysis application that provides aesthetic scoring, content tagging, style analysis, and hashtag generation for your photos.

## Features

- Upload and analyze photos
- Get aesthetic scores and technical analysis
- Identify content tags and style
- Generate optimized hashtags for social media
- View analysis history in the dashboard

## Tech Stack

- **Frontend**: Next.js, React, TypeScript, Tailwind CSS
- **Backend**: Flask, Python
- **Database**: MongoDB

## Project Structure

\`\`\`
photo-reviewer/
├── app/ # Next.js app directory
│ ├── api/ # API routes
│ ├── dashboard/ # Dashboard page
│ ├── results/ # Results page
│ ├── globals.css # Global styles
│ ├── layout.tsx # Root layout
│ └── page.tsx # Home page
├── components/ # React components
├── lib/ # Utility functions and API client
├── backend/ # Flask backend
│ ├── app/ # Flask application
│ │ ├── models/ # ML models (mock)
│ │ ├── utils/ # Utility functions
│ │ ├── **init**.py # App factory
│ │ └── routes.py # API routes
│ ├── uploads/ # Uploaded images
│ └── run.py # Entry point
├── public/ # Static assets
├── .env.local # Environment variables
└── package.json # Dependencies
