import { 
  CodeBracketIcon,
  RocketLaunchIcon,
  UserGroupIcon,
  DocumentTextIcon,
  StarIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'

export default function OpenSource() {
  const features = [
    {
      icon: CodeBracketIcon,
      title: 'Open Source Codebase',
      description: 'All code is publicly available on GitHub under an open source license. Fork, contribute, or learn from our implementation.',
      link: 'https://github.com/getcommunityone/open-navigator-for-engagement',
    },
    {
      icon: DocumentTextIcon,
      title: 'Comprehensive Documentation',
      description: 'Detailed documentation for developers, including API docs, data models, deployment guides, and contribution guidelines.',
      link: import.meta.env.PROD ? 'https://www.communityone.com/docs/intro' : 'http://localhost:3000/docs/intro',
    },
    {
      icon: UserGroupIcon,
      title: 'Community Contributions',
      description: 'Join our community of civic tech developers. Submit issues, create pull requests, or participate in discussions.',
      link: 'https://github.com/getcommunityone/open-navigator-for-engagement/issues',
    },
    {
      icon: RocketLaunchIcon,
      title: 'Hackathons & Events',
      description: 'Participate in quarterly hackathons focused on civic engagement, government transparency, and community empowerment.',
      link: '/hackathons',
    },
  ]

  const techStack = [
    { category: 'Frontend', tech: 'React, TypeScript, Vite, TailwindCSS' },
    { category: 'Backend', tech: 'FastAPI, Python, PostgreSQL' },
    { category: 'Data', tech: 'Pandas, Parquet, HuggingFace Datasets' },
    { category: 'Deployment', tech: 'Docker, HuggingFace Spaces, Databricks' },
    { category: 'Documentation', tech: 'Docusaurus, Markdown' },
  ]

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <CodeBracketIcon className="h-8 w-8" style={{ color: '#354F52' }} />
            <h1 className="text-3xl font-bold" style={{ color: '#354F52' }}>
              Open Source Projects
            </h1>
          </div>
          <p className="text-gray-600">
            Build with us. Contribute to civic tech. Make government data accessible to everyone.
          </p>
        </div>

        {/* Main Project Card */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8 border-l-4" style={{ borderColor: '#354F52' }}>
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Open Navigator
              </h2>
              <p className="text-gray-600 mb-4">
                A comprehensive platform for civic engagement, government transparency, and community empowerment.
              </p>
            </div>
            <a
              href="https://github.com/getcommunityone/open-navigator-for-engagement"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-white hover:shadow-lg transition-all"
              style={{ backgroundColor: '#354F52' }}
            >
              <StarIcon className="h-5 w-5" />
              <span>Star on GitHub</span>
              <ArrowTopRightOnSquareIcon className="h-4 w-4" />
            </a>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">
                Key Features
              </h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start gap-2">
                  <span className="text-green-600 font-bold">✓</span>
                  Track 925 cities, counties, and school districts
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 font-bold">✓</span>
                  Monitor 43,726 nonprofits and community organizations
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 font-bold">✓</span>
                  Analyze government meeting transcripts with AI
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 font-bold">✓</span>
                  Open datasets on HuggingFace
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">
                Languages & Tools
              </h3>
              <div className="flex flex-wrap gap-2">
                {['TypeScript', 'Python', 'React', 'FastAPI', 'PostgreSQL', 'Docker'].map((tech) => (
                  <span
                    key={tech}
                    className="px-3 py-1 rounded-full text-xs font-medium"
                    style={{ backgroundColor: '#CAD2C5', color: '#354F52' }}
                  >
                    {tech}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-4">
            <a
              href="https://github.com/getcommunityone/open-navigator-for-engagement"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-lg font-semibold hover:shadow-lg transition-all border-2"
              style={{ borderColor: '#354F52', color: '#354F52' }}
            >
              View Repository →
            </a>
            <a
              href="https://github.com/getcommunityone/open-navigator-for-engagement/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-lg font-semibold hover:shadow-lg transition-all border-2 border-gray-300 text-gray-700"
            >
              Report Issue
            </a>
            <a
              href="https://github.com/getcommunityone/open-navigator-for-engagement/fork"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-lg font-semibold hover:shadow-lg transition-all border-2 border-gray-300 text-gray-700"
            >
              Fork Project
            </a>
          </div>
        </div>

        {/* Features Grid */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">How to Get Involved</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {features.map((feature) => {
              const Icon = feature.icon
              const isExternal = feature.link.startsWith('http')
              
              return (
                <a
                  key={feature.title}
                  href={feature.link}
                  target={isExternal ? '_blank' : undefined}
                  rel={isExternal ? 'noopener noreferrer' : undefined}
                  className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start gap-4">
                    <div
                      className="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: '#354F5215' }}
                    >
                      <Icon className="h-6 w-6" style={{ color: '#354F52' }} />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
                        {feature.title}
                        {isExternal && <ArrowTopRightOnSquareIcon className="h-4 w-4" />}
                      </h3>
                      <p className="text-sm text-gray-600">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </a>
              )
            })}
          </div>
        </div>

        {/* Tech Stack */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Technology Stack</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {techStack.map((item) => (
              <div key={item.category}>
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-2" style={{ color: '#52796F' }}>
                  {item.category}
                </h3>
                <p className="text-gray-700">{item.tech}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Contribution Guidelines */}
        <div className="bg-white rounded-lg shadow-sm p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Contribution Guidelines</h2>
          <div className="space-y-4 text-gray-600">
            <p>
              We welcome contributions from developers of all skill levels! Here's how to get started:
            </p>
            <ol className="list-decimal list-inside space-y-2 ml-4">
              <li>
                <strong>Fork the repository</strong> and clone it to your local machine
              </li>
              <li>
                <strong>Create a new branch</strong> for your feature or bug fix
              </li>
              <li>
                <strong>Make your changes</strong> following our coding standards
              </li>
              <li>
                <strong>Write tests</strong> for new functionality
              </li>
              <li>
                <strong>Submit a pull request</strong> with a clear description of your changes
              </li>
            </ol>
            <p className="mt-4">
              See our{' '}
              <a
                href="https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/CONTRIBUTING.md"
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold hover:underline"
                style={{ color: '#354F52' }}
              >
                CONTRIBUTING.md
              </a>{' '}
              for detailed guidelines.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
