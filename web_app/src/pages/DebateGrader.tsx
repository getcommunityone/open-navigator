import { useState } from 'react'
import { CheckCircleIcon, XCircleIcon, QuestionMarkCircleIcon } from '@heroicons/react/24/outline'

interface DebateGrade {
  dimensions: {
    harms: DimensionScore
    solvency: DimensionScore
    topicality: DimensionScore
  }
  overall: {
    score: number
    grade: string
    summary: string
  }
  timestamp: string
}

interface DimensionScore {
  score: number
  grade: string
  explanation: string
  layperson_label: string
  layperson_question: string
}

export default function DebateFinder() {
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [grade, setGrade] = useState<DebateGrade | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const gradeDecision = async () => {
    if (!text) {
      setError('Please enter some text to grade')
      return
    }

    setLoading(true)
    setError('')

    try {
      const params = new URLSearchParams()
      params.set('text', text)
      if (title) params.set('title', title)

      const response = await fetch(`/api/debate-grade?${params.toString()}`, {
        method: 'POST'
      })

      if (!response.ok) {
        throw new Error('Failed to grade decision')
      }

      const data = await response.json()
      setGrade(data.debate_grade)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'excellent':
        return 'text-green-600'
      case 'good':
        return 'text-blue-600'
      case 'fair':
        return 'text-yellow-600'
      case 'weak':
        return 'text-orange-600'
      case 'missing':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  const getGradeIcon = (grade: string) => {
    switch (grade) {
      case 'excellent':
      case 'good':
        return <CheckCircleIcon className="h-6 w-6 text-green-600" />
      case 'fair':
        return <QuestionMarkCircleIcon className="h-6 w-6 text-yellow-600" />
      case 'weak':
      case 'missing':
        return <XCircleIcon className="h-6 w-6 text-red-600" />
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>
            Debate Finder
          </h1>
          <p className="text-gray-600">
            Evaluate government decisions using debate framework: Harms, Solvency, and Topicality
          </p>
        </div>

        {/* Input Form */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Decision Title (optional)
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g., City Council approves dental screening program"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Decision Text
              </label>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                rows={8}
                placeholder="Paste the government decision, meeting minutes, or policy text here..."
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            <button
              onClick={gradeDecision}
              disabled={loading}
              className="px-6 py-2 text-white rounded-md transition-colors"
              style={{ backgroundColor: '#354F52' }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2e4346'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#354F52'}
            >
              {loading ? 'Grading...' : 'Grade This Decision'}
            </button>
          </div>
        </div>

        {/* Results */}
        {grade && (
          <div className="space-y-6">
            {/* Overall Score */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-2xl font-bold mb-4" style={{ color: '#354F52' }}>
                Overall Grade: <span className={getGradeColor(grade.overall.grade)}>
                  {grade.overall.grade.toUpperCase()}
                </span>
              </h2>
              <p className="text-gray-700 mb-2">
                Score: {grade.overall.score}/5
              </p>
              <p className="text-gray-600">
                {grade.overall.summary}
              </p>
            </div>

            {/* Dimension Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Harms */}
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-semibold" style={{ color: '#354F52' }}>
                    {grade.dimensions.harms.layperson_label}
                  </h3>
                  {getGradeIcon(grade.dimensions.harms.grade)}
                </div>
                <p className="text-sm text-gray-600 mb-3 italic">
                  "{grade.dimensions.harms.layperson_question}"
                </p>
                <div className="mb-3">
                  <span className={`text-lg font-bold ${getGradeColor(grade.dimensions.harms.grade)}`}>
                    {grade.dimensions.harms.grade.toUpperCase()}
                  </span>
                  <span className="text-gray-500 ml-2">
                    ({grade.dimensions.harms.score}/5)
                  </span>
                </div>
                <p className="text-sm text-gray-700">
                  {grade.dimensions.harms.explanation}
                </p>
              </div>

              {/* Solvency */}
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-semibold" style={{ color: '#354F52' }}>
                    {grade.dimensions.solvency.layperson_label}
                  </h3>
                  {getGradeIcon(grade.dimensions.solvency.grade)}
                </div>
                <p className="text-sm text-gray-600 mb-3 italic">
                  "{grade.dimensions.solvency.layperson_question}"
                </p>
                <div className="mb-3">
                  <span className={`text-lg font-bold ${getGradeColor(grade.dimensions.solvency.grade)}`}>
                    {grade.dimensions.solvency.grade.toUpperCase()}
                  </span>
                  <span className="text-gray-500 ml-2">
                    ({grade.dimensions.solvency.score}/5)
                  </span>
                </div>
                <p className="text-sm text-gray-700">
                  {grade.dimensions.solvency.explanation}
                </p>
              </div>

              {/* Topicality */}
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-semibold" style={{ color: '#354F52' }}>
                    {grade.dimensions.topicality.layperson_label}
                  </h3>
                  {getGradeIcon(grade.dimensions.topicality.grade)}
                </div>
                <p className="text-sm text-gray-600 mb-3 italic">
                  "{grade.dimensions.topicality.layperson_question}"
                </p>
                <div className="mb-3">
                  <span className={`text-lg font-bold ${getGradeColor(grade.dimensions.topicality.grade)}`}>
                    {grade.dimensions.topicality.grade.toUpperCase()}
                  </span>
                  <span className="text-gray-500 ml-2">
                    ({grade.dimensions.topicality.score}/5)
                  </span>
                </div>
                <p className="text-sm text-gray-700">
                  {grade.dimensions.topicality.explanation}
                </p>
              </div>
            </div>

            {/* Explanation */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-blue-900 mb-3">
                Understanding the Debate Framework
              </h3>
              <div className="space-y-2 text-sm text-blue-800">
                <p>
                  <strong>The Problem (Harms):</strong> Does the decision clearly explain the crisis or problem? 
                  Is there data to back it up? Who is affected?
                </p>
                <p>
                  <strong>The Fix (Solvency):</strong> Does the solution actually work? Is there a clear plan? 
                  Has it worked elsewhere?
                </p>
                <p>
                  <strong>The Scope (Topicality):</strong> Does the government body have the legal authority to do this? 
                  Is it within their jurisdiction?
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
