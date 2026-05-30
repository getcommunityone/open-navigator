import { 
  MicrophoneIcon,
  CheckCircleIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
  ShieldCheckIcon,
  DocumentMagnifyingGlassIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'

export default function FactChecking() {
  const factCheckSources = [
    {
      name: 'PolitiFact',
      description: 'Fact-checking political claims with the Truth-O-Meter rating system.',
      url: 'https://www.politifact.com',
      logo: '🔍',
      focus: 'National & State Politics',
    },
    {
      name: 'FactCheck.org',
      description: 'Nonpartisan fact-checking by the Annenberg Public Policy Center.',
      url: 'https://www.factcheck.org',
      logo: '✓',
      focus: 'Political Claims',
    },
    {
      name: 'Google Fact Check Explorer',
      description: 'Search fact checks from publishers worldwide using Google\'s Fact Check Tools.',
      url: 'https://toolbox.google.com/factcheck/explorer',
      logo: '🔎',
      focus: 'Global Claims',
    },
    {
      name: 'Snopes',
      description: 'Fact-checking urban legends, internet rumors, and misinformation.',
      url: 'https://www.snopes.com',
      logo: '📰',
      focus: 'Internet & Media',
    },
  ]

  const howToFactCheck = [
    {
      icon: DocumentMagnifyingGlassIcon,
      title: 'Find the Claim',
      description: 'Identify specific statements made in government meetings or public discourse.',
    },
    {
      icon: ShieldCheckIcon,
      title: 'Check Credible Sources',
      description: 'Use fact-checking organizations and official data sources to verify claims.',
    },
    {
      icon: CheckCircleIcon,
      title: 'Evaluate Evidence',
      description: 'Look for primary sources, statistics, and expert analysis to support or refute claims.',
    },
    {
      icon: MicrophoneIcon,
      title: 'Share Findings',
      description: 'Report misinformation and share accurate information with your community.',
    },
  ]

  const claimCategories = [
    {
      type: 'True',
      icon: CheckCircleIcon,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      description: 'Claim is accurate and supported by evidence',
    },
    {
      type: 'Mostly True',
      icon: CheckCircleIcon,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      description: 'Claim is mostly accurate with minor omissions',
    },
    {
      type: 'Half True',
      icon: QuestionMarkCircleIcon,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
      description: 'Claim contains elements of truth but lacks context',
    },
    {
      type: 'Mostly False',
      icon: XCircleIcon,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      description: 'Claim contains significant inaccuracies',
    },
    {
      type: 'False',
      icon: XCircleIcon,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      description: 'Claim is not supported by evidence',
    },
  ]

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <MicrophoneIcon className="h-8 w-8" style={{ color: '#CAD2C5' }} />
            <h1 className="text-3xl font-bold" style={{ color: '#354F52' }}>
              Fact-Checking Tools
            </h1>
          </div>
          <p className="text-gray-600">
            Verify claims from meetings and legislation with trusted fact-checking sources and tools.
          </p>
        </div>

        {/* Debate Grader Tool */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8 border-l-4" style={{ borderColor: '#CAD2C5' }}>
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Debate Framework Analyzer
              </h2>
              <p className="text-gray-600 mb-4">
                Evaluate government decisions using a debate framework that analyzes Harms, Solvency, and Topicality.
              </p>
            </div>
            <Link
              to="/debate-grader"
              className="px-6 py-3 rounded-lg text-white font-semibold hover:shadow-lg transition-all whitespace-nowrap"
              style={{ backgroundColor: '#52796F' }}
            >
              Try Debate Grader →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-gray-50">
              <h3 className="font-semibold text-gray-900 mb-1">Harms Analysis</h3>
              <p className="text-sm text-gray-600">
                Evaluates whether the decision addresses a real problem and its severity.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-gray-50">
              <h3 className="font-semibold text-gray-900 mb-1">Solvency Check</h3>
              <p className="text-sm text-gray-600">
                Assesses if the proposed solution will actually solve the identified problem.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-gray-50">
              <h3 className="font-semibold text-gray-900 mb-1">Topicality Review</h3>
              <p className="text-sm text-gray-600">
                Determines if the decision is within the authority and scope of the body making it.
              </p>
            </div>
          </div>
        </div>

        {/* Truth Rating Scale */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Understanding Truth Ratings</h2>
          <div className="space-y-3">
            {claimCategories.map((category) => {
              const Icon = category.icon
              return (
                <div
                  key={category.type}
                  className={`flex items-start gap-4 p-4 rounded-lg ${category.bgColor}`}
                >
                  <Icon className={`h-6 w-6 flex-shrink-0 ${category.color}`} />
                  <div>
                    <h3 className={`font-semibold ${category.color}`}>{category.type}</h3>
                    <p className="text-sm text-gray-700">{category.description}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Fact-Checking Sources */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Trusted Fact-Checking Resources</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {factCheckSources.map((source) => (
              <a
                key={source.name}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-all group"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="text-4xl">{source.logo}</div>
                  <ArrowTopRightOnSquareIcon className="h-5 w-5 text-gray-400 group-hover:text-gray-600" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2 group-hover:text-primary-600 transition-colors">
                  {source.name}
                </h3>
                <p className="text-sm text-gray-600 mb-3">
                  {source.description}
                </p>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-3 py-1 rounded-full bg-gray-100 text-gray-700 font-medium">
                    {source.focus}
                  </span>
                </div>
              </a>
            ))}
          </div>
        </div>

        {/* How to Fact Check */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">How to Fact-Check Claims</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {howToFactCheck.map((step) => {
              const Icon = step.icon
              return (
                <div key={step.title} className="text-center">
                  <div
                    className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                    style={{ backgroundColor: '#CAD2C5' }}
                  >
                    <Icon className="h-8 w-8" style={{ color: '#354F52' }} />
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-2">{step.title}</h3>
                  <p className="text-sm text-gray-600">{step.description}</p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Tips for Critical Thinking */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Tips for Critical Thinking</h2>
          <div className="space-y-3 text-gray-700">
            <div className="flex items-start gap-3">
              <span className="text-xl flex-shrink-0">💡</span>
              <p><strong>Question the Source:</strong> Who is making the claim? Do they have expertise or potential bias?</p>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-xl flex-shrink-0">📊</span>
              <p><strong>Look for Data:</strong> Are there statistics or studies backing up the claim? Are they from credible sources?</p>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-xl flex-shrink-0">🔍</span>
              <p><strong>Check Multiple Sources:</strong> Does the claim appear in multiple independent, reliable sources?</p>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-xl flex-shrink-0">⏰</span>
              <p><strong>Consider Context:</strong> Is the claim taken out of context? When was it made, and is it still relevant?</p>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-xl flex-shrink-0">🤔</span>
              <p><strong>Beware of Bias:</strong> Does the source have a political or financial incentive to make this claim?</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
