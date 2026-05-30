import { 
  BellAlertIcon,
  MegaphoneIcon,
  HeartIcon,
  AcademicCapIcon,
  ShieldCheckIcon,
  HomeModernIcon,
  SparklesIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'

export default function AdvocacyTopics() {
  const topics = [
    {
      icon: HeartIcon,
      title: 'Oral Health',
      description: 'Track dental programs, fluoridation policies, and oral health initiatives in your community.',
      count: '5,200+ related meetings',
      color: '#DC143C',
      keywords: ['dental', 'fluoride', 'oral health', 'teeth'],
    },
    {
      icon: AcademicCapIcon,
      title: 'Education',
      description: 'Monitor school budgets, curriculum changes, and educational programs across districts.',
      count: '15,000+ related meetings',
      color: '#354F52',
      keywords: ['schools', 'education', 'curriculum', 'budget'],
    },
    {
      icon: HomeModernIcon,
      title: 'Housing & Development',
      description: 'Follow zoning decisions, affordable housing initiatives, and development projects.',
      count: '8,500+ related meetings',
      color: '#52796F',
      keywords: ['housing', 'zoning', 'development', 'affordable'],
    },
    {
      icon: ShieldCheckIcon,
      title: 'Public Safety',
      description: 'Stay informed on police budgets, fire department resources, and emergency services.',
      count: '12,000+ related meetings',
      color: '#84A98C',
      keywords: ['police', 'fire', 'safety', 'emergency'],
    },
    {
      icon: UserGroupIcon,
      title: 'Social Services',
      description: 'Track programs for seniors, families, mental health, and community support.',
      count: '7,800+ related meetings',
      color: '#CAD2C5',
      keywords: ['social services', 'mental health', 'seniors', 'families'],
    },
    {
      icon: SparklesIcon,
      title: 'Environment & Sustainability',
      description: 'Monitor climate initiatives, recycling programs, and environmental policies.',
      count: '6,400+ related meetings',
      color: '#52796F',
      keywords: ['environment', 'climate', 'sustainability', 'recycling'],
    },
  ]

  const howToAdvocate = [
    {
      step: '1',
      title: 'Find Your Topic',
      description: 'Browse advocacy topics or search for specific issues affecting your community.',
    },
    {
      step: '2',
      title: 'Track Meetings',
      description: 'Monitor upcoming government meetings where your topic will be discussed.',
    },
    {
      step: '3',
      title: 'Prepare Your Message',
      description: 'Use our talking points and data to craft compelling testimony.',
    },
    {
      step: '4',
      title: 'Make Your Voice Heard',
      description: 'Attend meetings, submit comments, or contact officials directly.',
    },
  ]

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <BellAlertIcon className="h-8 w-8" style={{ color: '#52796F' }} />
            <h1 className="text-3xl font-bold" style={{ color: '#354F52' }}>
              Advocacy Topics
            </h1>
          </div>
          <p className="text-gray-600">
            Track what your community is discussing. Find advocacy opportunities and get involved in local decision-making.
          </p>
        </div>

        {/* Search Banner */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8 text-center border-l-4" style={{ borderColor: '#52796F' }}>
          <MegaphoneIcon className="h-12 w-12 mx-auto mb-4" style={{ color: '#52796F' }} />
          <h2 className="text-2xl font-bold text-gray-900 mb-3">
            Find Advocacy Opportunities in Your Area
          </h2>
          <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
            Search meeting minutes for topics that matter to you. Get alerts when your issues are being discussed.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              to="/documents"
              className="px-6 py-3 rounded-lg text-white font-semibold hover:shadow-lg transition-all"
              style={{ backgroundColor: '#52796F' }}
            >
              Search Meeting Minutes
            </Link>
            <Link
              to="/opportunities"
              className="px-6 py-3 rounded-lg font-semibold hover:shadow-lg transition-all border-2"
              style={{ borderColor: '#52796F', color: '#52796F' }}
            >
              View All Opportunities
            </Link>
          </div>
        </div>

        {/* Topics Grid */}
        <div className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Popular Advocacy Topics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {topics.map((topic) => {
              const Icon = topic.icon
              return (
                <Link
                  key={topic.title}
                  to={`/documents?search=${encodeURIComponent(topic.keywords[0])}`}
                  className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-all group"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div
                      className="w-12 h-12 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform"
                      style={{ backgroundColor: `${topic.color}15` }}
                    >
                      <Icon className="h-6 w-6" style={{ color: topic.color }} />
                    </div>
                    <span
                      className="text-xs font-medium px-2 py-1 rounded-full"
                      style={{ backgroundColor: `${topic.color}15`, color: topic.color }}
                    >
                      {topic.count}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-primary-600 transition-colors">
                    {topic.title}
                  </h3>
                  <p className="text-sm text-gray-600 mb-3">
                    {topic.description}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {topic.keywords.slice(0, 3).map((keyword) => (
                      <span
                        key={keyword}
                        className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-700"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 text-sm font-medium group-hover:translate-x-1 transition-transform" style={{ color: topic.color }}>
                    Search meetings →
                  </div>
                </Link>
              )
            })}
          </div>
        </div>

        {/* How to Advocate */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">How to Advocate Effectively</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {howToAdvocate.map((item) => (
              <div key={item.step} className="text-center">
                <div
                  className="w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center text-white text-xl font-bold"
                  style={{ backgroundColor: '#52796F' }}
                >
                  {item.step}
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{item.title}</h3>
                <p className="text-sm text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Get Started CTA */}
        <div className="bg-gradient-to-r from-primary-50 to-primary-100 rounded-lg p-8 text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-3">
            Ready to Make a Difference?
          </h2>
          <p className="text-gray-700 mb-6 max-w-2xl mx-auto">
            Start by searching for your community and exploring what local government is discussing.
            Your voice matters in local decision-making.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              to="/heatmap"
              className="px-6 py-3 rounded-lg text-white font-semibold hover:shadow-lg transition-all"
              style={{ backgroundColor: '#354F52' }}
            >
              Find Your Community
            </Link>
            <Link
              to="/events"
              className="px-6 py-3 rounded-lg font-semibold hover:shadow-lg transition-all bg-white border-2 border-gray-300 text-gray-700"
            >
              View Upcoming Meetings
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
