import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import api from '../lib/api'

const COLORS = ['#0ea5e9', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6']

interface DashboardStats {
  total_documents: number
  total_opportunities: number
  states_monitored: number
  topics: Record<string, number>
  recent_opportunities: Array<{
    state: string
    municipality: string
    topic: string
    urgency: string
    date: string
  }>
}

export default function Dashboard() {
  const { data, isLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const response = await api.get('/dashboard')
      return response.data
    },
  })

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-xl text-gray-600">Loading analytics...</div>
      </div>
    )
  }

  const topicData = Object.entries(data?.topics || {}).map(([name, value]) => ({
    name: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
    value,
  }))

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>Data & Trends</h1>
          <p className="text-gray-600">
            Statistics and insights across communities - see what's happening in local government
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-primary-500">
            <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">Total Documents</h3>
            <p className="mt-2 text-4xl font-bold text-primary-600">
              {data?.total_documents?.toLocaleString() || '0'}
            </p>
            <p className="mt-1 text-sm text-gray-500">Meeting minutes & budgets</p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-amber-500">
            <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">Opportunities Found</h3>
            <p className="mt-2 text-4xl font-bold text-amber-600">
              {data?.total_opportunities?.toLocaleString() || '0'}
            </p>
            <p className="mt-1 text-sm text-gray-500">Advocacy windows identified</p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-emerald-500">
            <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">States Monitored</h3>
            <p className="mt-2 text-4xl font-bold text-emerald-600">
              {data?.states_monitored || '0'}
            </p>
            <p className="mt-1 text-sm text-gray-500">Across the nation</p>
          </div>
        </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Topics Bar Chart */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-xl font-semibold mb-4 text-gray-900">Policy Topics</h3>
          {topicData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topicData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#0ea5e9" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-400">
              No topic data available
            </div>
          )}
        </div>

        {/* Topics Pie Chart */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-xl font-semibold mb-4 text-gray-900">Topic Distribution</h3>
          {topicData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={topicData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => entry.name}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {topicData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-400">
              No topic data available
            </div>
          )}
        </div>
      </div>

      {/* Recent Opportunities */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-xl font-semibold mb-4 text-gray-900">Recent Causes</h3>
        {data?.recent_opportunities && data.recent_opportunities.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Location
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Topic
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Urgency
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.recent_opportunities.map((opp, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{opp.municipality}</div>
                      <div className="text-sm text-gray-500">{opp.state}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {opp.topic.replace(/_/g, ' ')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
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
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(opp.date).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-gray-400 text-lg mb-4">No opportunities found yet</p>
            <p className="text-gray-500 text-sm">
              Run the data ingestion pipeline to analyze meetings and identify advocacy opportunities
            </p>
          </div>
        )}
      </div>
    </div>
    </div>
  )
}
