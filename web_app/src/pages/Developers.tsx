import { CodeBracketIcon, RocketLaunchIcon, BookOpenIcon, CubeIcon, ServerIcon, CircleStackIcon } from '@heroicons/react/24/outline';

export default function Developers() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-3 bg-primary-50 rounded-lg">
            <CodeBracketIcon className="h-8 w-8 text-primary-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Developers & Civic Tech</h1>
            <p className="text-gray-600 mt-1">Build civic tech solutions with open data and open source tools</p>
          </div>
        </div>
      </div>

      {/* Hero Section */}
      <div className="bg-gradient-to-r from-primary-600 to-primary-700 rounded-xl p-8 mb-8 text-white">
        <h2 className="text-3xl font-bold mb-4">Build the Future of Civic Engagement</h2>
        <p className="text-xl mb-6 text-primary-50">
          Open Navigator is 100% open source. Join developers worldwide building tools for transparency, 
          accountability, and community empowerment.
        </p>
        <div className="flex flex-wrap gap-4">
          <a
            href="https://github.com/getcommunityone/open-navigator-for-engagement"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 bg-white text-primary-700 rounded-lg hover:bg-primary-50 transition-colors font-semibold flex items-center gap-2"
          >
            <CodeBracketIcon className="h-5 w-5" />
            View on GitHub
          </a>
          <a
            href="/hackathons"
            className="px-6 py-3 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors font-semibold border-2 border-white flex items-center gap-2"
          >
            <RocketLaunchIcon className="h-5 w-5" />
            Join Hackathons
          </a>
        </div>
      </div>

      {/* Tech Stack */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Tech Stack</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Frontend */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-blue-100 rounded-lg">
                <CubeIcon className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Frontend</h3>
            </div>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>• React 18 + TypeScript</li>
              <li>• Vite + Tailwind CSS</li>
              <li>• TanStack Query</li>
              <li>• Recharts for visualizations</li>
            </ul>
          </div>

          {/* Backend */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-green-100 rounded-lg">
                <ServerIcon className="h-6 w-6 text-green-600" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Backend</h3>
            </div>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>• Python FastAPI</li>
              <li>• LangChain + LangGraph</li>
              <li>• OpenAI, Anthropic APIs</li>
              <li>• Supabase Auth</li>
            </ul>
          </div>

          {/* Data */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-purple-100 rounded-lg">
                <CircleStackIcon className="h-6 w-6 text-purple-600" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Data</h3>
            </div>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>• 925 jurisdictions</li>
              <li>• 43,726 nonprofits</li>
              <li>• 6,913 meeting pages</li>
              <li>• Medallion architecture</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Get Started</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href="https://github.com/getcommunityone/open-navigator-for-engagement#readme"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-4 p-6 bg-white rounded-xl shadow-md border border-gray-200 hover:border-primary-300 transition-colors group"
          >
            <BookOpenIcon className="h-8 w-8 text-primary-600 flex-shrink-0" />
            <div>
              <h3 className="text-lg font-bold text-gray-900 mb-1 group-hover:text-primary-600">
                Documentation
              </h3>
              <p className="text-sm text-gray-600">
                Setup guides, API docs, and architecture overview
              </p>
            </div>
          </a>

          <a
            href="https://huggingface.co/datasets/CommunityOne/open-navigator-data"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-4 p-6 bg-white rounded-xl shadow-md border border-gray-200 hover:border-primary-300 transition-colors group"
          >
            <CircleStackIcon className="h-8 w-8 text-primary-600 flex-shrink-0" />
            <div>
              <h3 className="text-lg font-bold text-gray-900 mb-1 group-hover:text-primary-600">
                Open Datasets
              </h3>
              <p className="text-sm text-gray-600">
                Download CSV/Parquet files from HuggingFace
              </p>
            </div>
          </a>

          <a
            href="https://github.com/getcommunityone/open-navigator-for-engagement/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-4 p-6 bg-white rounded-xl shadow-md border border-gray-200 hover:border-primary-300 transition-colors group"
          >
            <CodeBracketIcon className="h-8 w-8 text-primary-600 flex-shrink-0" />
            <div>
              <h3 className="text-lg font-bold text-gray-900 mb-1 group-hover:text-primary-600">
                Contribute Code
              </h3>
              <p className="text-sm text-gray-600">
                Pick an issue, submit a PR, or propose new features
              </p>
            </div>
          </a>

          <a
            href="/hackathons"
            className="flex items-start gap-4 p-6 bg-white rounded-xl shadow-md border border-gray-200 hover:border-primary-300 transition-colors group"
          >
            <RocketLaunchIcon className="h-8 w-8 text-primary-600 flex-shrink-0" />
            <div>
              <h3 className="text-lg font-bold text-gray-900 mb-1 group-hover:text-primary-600">
                Join Hackathons
              </h3>
              <p className="text-sm text-gray-600">
                Build solutions at our quarterly civic tech hackathons
              </p>
            </div>
          </a>
        </div>
      </div>

      {/* API Example */}
      <div className="bg-gray-900 rounded-xl p-6 text-white">
        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
          <CodeBracketIcon className="h-6 w-6" />
          API Example
        </h2>
        <pre className="bg-gray-800 rounded-lg p-4 overflow-x-auto text-sm">
          <code>{`# Search meeting transcripts
import requests

response = requests.get(
  '/api/search/',
  params={
    'q': 'dental health',
    'state': 'AL',
    'limit': 10
  }
)

for result in response.json()['results']:
  print(f"{result['title']} - {result['date']}")
  print(f"Score: {result['score']}")
  print(result['snippet'])
  print()`}</code>
        </pre>
      </div>
    </div>
  );
}
