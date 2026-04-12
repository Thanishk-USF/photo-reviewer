export function HowItWorks() {
  const steps = [
    {
      number: "01",
      title: "Upload Your Photo",
      description: "Drag and drop or select a photo from your device to upload.",
    },
    {
      number: "02",
      title: "Analysis Phase",
      description: "The model analyzes your photo for aesthetics, content, and style.",
    },
    {
      number: "03",
      title: "Review Results",
      description: "Get detailed feedback including scores, tags, and improvement suggestions.",
    },
    {
      number: "04",
      title: "Apply Insights",
      description: "Use the recommended feedback to improve your photography skills and social media strategy.",
    },
  ]

  return (
    <section id="how-it-works" className="py-16 dark:bg-gray-800">
      <div className="container mx-auto px-4">
        <h2 className="mb-12 text-center text-3xl font-bold text-gray-900 dark:text-white">How It Works</h2>
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, index) => (
            <div key={index} className="relative">
              <div className="mb-4 text-4xl font-bold text-purple-200 dark:text-purple-800">{step.number}</div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">{step.title}</h3>
              <p className="text-gray-600 dark:text-gray-300">{step.description}</p>
              {index < steps.length - 1 && (
                <div className="absolute right-0 top-8 hidden h-0.5 w-1/2 bg-purple-100 lg:block dark:bg-purple-800"></div>
              )}
              {index > 0 && (
                <div className="absolute left-0 top-8 hidden h-0.5 w-1/2 bg-purple-100 lg:block dark:bg-purple-800"></div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
