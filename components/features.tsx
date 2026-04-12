import { Camera, Star, Tag, Palette, Hash } from "lucide-react"

export function Features() {
  const features = [
    {
      icon: <Star className="h-6 w-6 text-purple-600" />,
      title: "Aesthetic Scoring",
      description:
        "Get an objective score of your photo's aesthetic quality based on composition, lighting, and visual appeal.",
    },
    {
      icon: <Tag className="h-6 w-6 text-purple-600" />,
      title: "Content Tagging",
      description: "Application automatically identifies objects, scenes, and subjects in your photos with high accuracy.",
    },
    {
      icon: <Palette className="h-6 w-6 text-purple-600" />,
      title: "Style Analysis",
      description: "Discover the visual style and mood of your photos, from minimalist to vibrant, moody to cheerful.",
    },
    {
      icon: <Hash className="h-6 w-6 text-purple-600" />,
      title: "Hashtag Generation",
      description: "Get optimized hashtags for Instagram, Twitter, and other social platforms to maximize engagement.",
    },
    {
      icon: <Camera className="h-6 w-6 text-purple-600" />,
      title: "Technical Analysis",
      description: "Receive feedback on technical aspects like sharpness, noise levels, and exposure quality.",
    },
  ]

  return (
    <section id="features" className="bg-gray-50 py-16 dark:bg-gray-900">
      <div className="container mx-auto px-4">
        <h2 className="mb-12 text-center text-3xl font-bold text-gray-900 dark:text-white">Key Features</h2>
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, index) => (
            <div key={index} className="rounded-xl bg-white p-6 shadow-sm dark:bg-gray-800 dark:text-white">
              <div className="mb-4 rounded-full bg-purple-100 p-3 inline-flex dark:bg-purple-900">{feature.icon}</div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">{feature.title}</h3>
              <p className="text-gray-600 dark:text-gray-300">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
