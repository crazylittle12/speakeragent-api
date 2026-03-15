"use client"

import { useState, useEffect } from "react"
import { Check } from "lucide-react"

const steps = [
  { id: 1, emoji: "🔍", text: "Scanning conferences and events..." },
  { id: 2, emoji: "🎯", text: "Matching your expertise to opportunities..." },
  { id: 3, emoji: "🔬", text: "Researching decision makers..." },
  { id: 4, emoji: "✍️", text: "Generating personalized pitches..." },
  { id: 5, emoji: "✅", text: "Almost done — finalizing your leads..." },
]

// Total duration: 3 minutes (180 seconds)
const TOTAL_DURATION = 180000
const STEP_DURATION = TOTAL_DURATION / steps.length

export default function LeadsProcessingPage() {
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [visibleSteps, setVisibleSteps] = useState<number[]>([0])

  useEffect(() => {
    // Progress bar animation - updates every 100ms over 3 minutes
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(progressInterval)
          return 100
        }
        return prev + 100 / (TOTAL_DURATION / 100)
      })
    }, 100)

    return () => clearInterval(progressInterval)
  }, [])

  useEffect(() => {
    // Step progression - each step takes ~36 seconds
    const stepInterval = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev >= steps.length - 1) {
          clearInterval(stepInterval)
          return prev
        }
        
        // Mark current step as completed
        setCompletedSteps((completed) => [...completed, prev])
        
        // Show next step after a brief delay
        const nextStep = prev + 1
        setTimeout(() => {
          setVisibleSteps((visible) => [...visible, nextStep])
        }, 300)
        
        return nextStep
      })
    }, STEP_DURATION)

    return () => clearInterval(stepInterval)
  }, [])

  return (
    <main className="min-h-screen bg-[#0f172a] flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl mx-auto text-center">
        {/* Brand Logo */}
        <div className="mb-12">
          <h1 className="text-2xl font-bold text-white tracking-tight">
            <span className="text-cyan-400">Speaker</span>
            <span className="text-white">Agent</span>
            <span className="text-cyan-400">.AI</span>
          </h1>
        </div>

        {/* AI Working Indicator */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="relative flex items-center justify-center">
            <div className="absolute w-10 h-10 rounded-full bg-cyan-500/20 animate-ping" />
            <div className="relative w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center">
              <div className="w-3 h-3 rounded-full bg-white animate-pulse" />
            </div>
          </div>
          <span className="text-cyan-400 text-sm font-medium tracking-wide uppercase">
            AI is working
          </span>
        </div>

        {/* Main Heading */}
        <h2 className="text-4xl md:text-5xl font-bold text-white mb-4 leading-tight text-balance">
          Your leads are being prepared
        </h2>

        {/* Subheading */}
        <p className="text-slate-400 text-lg mb-12">
          Estimated time: 2–5 minutes
        </p>

        {/* Progress Bar */}
        <div className="w-full mb-12">
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-3 flex justify-between text-sm text-slate-500">
            <span>Processing...</span>
            <span>{Math.round(progress)}%</span>
          </div>
        </div>

        {/* Status Steps */}
        <div className="bg-slate-900/50 rounded-2xl p-6 md:p-8 border border-slate-800 mb-12">
          <div className="space-y-4">
            {steps.map((step, index) => {
              const isVisible = visibleSteps.includes(index)
              const isCompleted = completedSteps.includes(index)
              const isCurrent = currentStep === index && !isCompleted

              return (
                <div
                  key={step.id}
                  className={`
                    flex items-center gap-4 p-4 rounded-xl transition-all duration-500 ease-out
                    ${!isVisible ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0"}
                    ${isCompleted ? "bg-slate-800/50" : isCurrent ? "bg-cyan-500/10 border border-cyan-500/30" : "bg-slate-800/30"}
                  `}
                  style={{
                    transitionDelay: isVisible ? "0ms" : "0ms",
                  }}
                >
                  {/* Status Icon */}
                  <div className="flex-shrink-0">
                    {isCompleted ? (
                      <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                        <Check className="w-5 h-5 text-emerald-400" />
                      </div>
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-slate-700/50 flex items-center justify-center text-lg">
                        {isCurrent ? (
                          <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
                        ) : (
                          <span className="opacity-50">{step.emoji}</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Step Content */}
                  <div className="flex-1 text-left">
                    <p
                      className={`
                        text-base font-medium transition-colors duration-300
                        ${isCompleted ? "text-slate-400" : isCurrent ? "text-white" : "text-slate-500"}
                      `}
                    >
                      <span className="mr-2">{step.emoji}</span>
                      {step.text}
                    </p>
                  </div>

                  {/* Completed Badge */}
                  {isCompleted && (
                    <span className="text-xs text-emerald-400 font-medium uppercase tracking-wide">
                      Done
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Footer Text */}
        <p className="text-slate-500 text-sm">
          {"You'll receive an email when your leads are ready"}
        </p>
      </div>

      {/* Decorative Background Elements */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-1/4 -left-1/4 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 -right-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl" />
      </div>
    </main>
  )
}
