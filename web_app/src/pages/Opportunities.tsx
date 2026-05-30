import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

interface Opportunity {
  id: string
  state: string
  municipality: string
  topic: string
  urgency: string
  confidence: number
  meeting_date: string
  next_meeting: string
  talking_points: string[]
  contact_info: {
    email?: string
    phone?: string
  }
}

export default function Opportunities() {
  const [urgencyFilter, setUrgencyFilter] = useState<string | null>(null)

  const { data: opportunities, isLoading } = useQuery<Opportunity[]>({
    queryKey: ['opportunities-list', urgencyFilter],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (urgencyFilter) params.append('urgency', urgencyFilter)
      
      const response = await api.get(`/opportunities?${params}`)
      return response.data.opportunities || []
    },
  })

  const handleGenerateEmail = async (oppId: string) => {
    try {
      const response = await api.post(`/advocacy/email/${oppId}`)
      // Download the generated email
      const blob = new Blob([response.data.content], { type: 'text/plain' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `advocacy-email-${oppId}.txt`
      a.click()
    } catch (error) {
      console.error('Failed to generate email:', error)
    }
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="card">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Filter by Urgency
        </label>
        <div className="flex gap-2">
          {['critical', 'high', 'medium', 'low'].map((level) => (
            <button
              key={level}
              onClick={() => setUrgencyFilter(urgencyFilter === level ? null : level)}
              className={`px-4 py-2 rounded-lg capitalize ${
                urgencyFilter === level
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {/* Opportunities List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="card">Loading causes...</div>
        ) : (
          opportunities?.map((opp) => (
            <div key={opp.id} className="card">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">
                    {opp.municipality}, {opp.state}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {opp.topic.replace(/_/g, ' ')} • Meeting: {new Date(opp.meeting_date).toLocaleDateString()}
                  </p>
                </div>
                
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    opp.urgency === 'critical'
                      ? 'bg-red-100 text-red-800'
                      : opp.urgency === 'high'
                      ? 'bg-orange-100 text-orange-800'
                      : opp.urgency === 'medium'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-green-100 text-green-800'
                  }`}
                >
                  {opp.urgency}
                </span>
              </div>

              {/* Talking Points */}
              {opp.talking_points && opp.talking_points.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-medium text-gray-900 mb-2">Key Talking Points:</h4>
                  <ul className="list-disc list-inside space-y-1">
                    {opp.talking_points.map((point, idx) => (
                      <li key={idx} className="text-sm text-gray-700">{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3">
                <button
                  onClick={() => handleGenerateEmail(opp.id)}
                  className="btn-primary"
                >
                  Generate Email
                </button>
                
                {opp.contact_info?.email && (
                  <a
                    href={`mailto:${opp.contact_info.email}`}
                    className="btn-secondary"
                  >
                    Contact via Email
                  </a>
                )}
                
                {opp.next_meeting && (
                  <button className="btn-secondary">
                    📅 Add to Calendar
                  </button>
                )}
              </div>

              {/* Confidence Score */}
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Confidence Score:</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-primary-600 h-2 rounded-full"
                        style={{ width: `${opp.confidence * 100}%` }}
                      />
                    </div>
                    <span className="font-medium">{(opp.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
