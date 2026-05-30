import { RocketLaunchIcon, CalendarIcon, TrophyIcon, UserGroupIcon, CodeBracketIcon, LightBulbIcon } from '@heroicons/react/24/outline';

export default function Hackathons() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-3 bg-primary-50 rounded-lg">
            <RocketLaunchIcon className="h-8 w-8 text-primary-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Hackathons for Good</h1>
            <p className="text-gray-600 mt-1">Build civic tech solutions that empower communities and promote transparency</p>
          </div>
        </div>
      </div>

      {/* Coming Soon Notice */}
      <div className="bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl p-8 mb-8 text-white">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0">
            <RocketLaunchIcon className="h-12 w-12" />
          </div>
          <div>
            <h2 className="text-3xl font-bold mb-2">Quarterly Civic Tech Hackathons</h2>
            <p className="text-lg mb-4 text-purple-50">
              Join developers, designers, and civic advocates to build tools for social impact.
            </p>
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-white text-purple-700 rounded-lg font-semibold">
              <CalendarIcon className="h-5 w-5" />
              Next Event: Coming Soon!
            </div>
          </div>
        </div>
      </div>

      {/* Why Participate */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Why Participate?</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-blue-100 rounded-lg">
                <LightBulbIcon className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Real Impact</h3>
            </div>
            <p className="text-gray-600 text-sm">
              Build tools that help communities access services, hold government accountable, and participate in democracy.
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-green-100 rounded-lg">
                <UserGroupIcon className="h-6 w-6 text-green-600" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Collaboration</h3>
            </div>
            <p className="text-gray-600 text-sm">
              Work alongside civic advocates, policy experts, and fellow developers to solve real problems.
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-purple-100 rounded-lg">
                <TrophyIcon className="h-6 w-6 text-purple-600" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Recognition</h3>
            </div>
            <p className="text-gray-600 text-sm">
              Win prizes, get featured in our showcase, and add meaningful projects to your portfolio.
            </p>
          </div>
        </div>
      </div>

      {/* Challenge Tracks */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Challenge Tracks</h2>
        <div className="space-y-4">
          {/* Track 1 */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <CodeBracketIcon className="h-8 w-8 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-gray-900 mb-2">Data Visualization & Dashboards</h3>
                <p className="text-gray-600 mb-3">
                  Create interactive visualizations that make government data accessible to everyday citizens.
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full">
                    React
                  </span>
                  <span className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full">
                    D3.js
                  </span>
                  <span className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full">
                    Data Analysis
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Track 2 */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <RocketLaunchIcon className="h-8 w-8 text-green-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-gray-900 mb-2">AI for Civic Engagement</h3>
                <p className="text-gray-600 mb-3">
                  Use LLMs and AI agents to summarize meetings, extract policy insights, or answer citizen questions.
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="px-3 py-1 bg-green-50 text-green-700 text-xs font-semibold rounded-full">
                    LangChain
                  </span>
                  <span className="px-3 py-1 bg-green-50 text-green-700 text-xs font-semibold rounded-full">
                    RAG
                  </span>
                  <span className="px-3 py-1 bg-green-50 text-green-700 text-xs font-semibold rounded-full">
                    NLP
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Track 3 */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-purple-100 rounded-lg">
                <UserGroupIcon className="h-8 w-8 text-purple-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-gray-900 mb-2">Community Engagement Tools</h3>
                <p className="text-gray-600 mb-3">
                  Build mobile apps, notification systems, or tools that help people participate in local government.
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="px-3 py-1 bg-purple-50 text-purple-700 text-xs font-semibold rounded-full">
                    Mobile
                  </span>
                  <span className="px-3 py-1 bg-purple-50 text-purple-700 text-xs font-semibold rounded-full">
                    Notifications
                  </span>
                  <span className="px-3 py-1 bg-purple-50 text-purple-700 text-xs font-semibold rounded-full">
                    UX Design
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Track 4 */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-amber-100 rounded-lg">
                <LightBulbIcon className="h-8 w-8 text-amber-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-gray-900 mb-2">Voice, Face & Rhetoric Profiles</h3>
                <p className="text-gray-600 mb-3">
                  Link official headshots and contact data to diarized meeting audio and cited rhetoric traits—multimodal
                  accountability for elected officials (public record only).
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="px-3 py-1 bg-amber-50 text-amber-800 text-xs font-semibold rounded-full">
                    Diarization
                  </span>
                  <span className="px-3 py-1 bg-amber-50 text-amber-800 text-xs font-semibold rounded-full">
                    contacts.json
                  </span>
                  <span className="px-3 py-1 bg-amber-50 text-amber-800 text-xs font-semibold rounded-full">
                    Policy JSON
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <p className="text-sm text-gray-500 mt-4">
          More pitch ideas (TikTok summaries, accessibility checker, interactive annual reports, voice profiles):{' '}
          <a
            href="https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/web_docs/docs/guides/hackathon-video-submission-ideas.md"
            className="text-primary-600 hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            hackathon idea library (docs)
          </a>
        </p>
      </div>

      {/* Resources */}
      <div className="bg-gradient-to-r from-primary-50 to-primary-100 rounded-xl p-8 border border-primary-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Resources for Participants</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 mb-2">Data Access</h3>
            <ul className="space-y-1 text-gray-700">
              <li>• 925 jurisdiction records</li>
              <li>• 43,726 nonprofit organizations</li>
              <li>• 6,913 meeting pages with transcripts</li>
              <li>• API access and bulk downloads</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 mb-2">Support</h3>
            <ul className="space-y-1 text-gray-700">
              <li>• Mentors from civic tech community</li>
              <li>• Technical workshops and tutorials</li>
              <li>• GitHub repository with starter code</li>
              <li>• Discord community for collaboration</li>
            </ul>
          </div>
        </div>
      </div>

      {/* CTA */}
      <div className="mt-8 text-center">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-2xl mx-auto border border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900 mb-3">
            Join Our Community
          </h2>
          <p className="text-gray-600 mb-6">
            Get notified about upcoming hackathons, workshops, and civic tech events.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href="https://github.com/getcommunityone/open-navigator-for-engagement"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-semibold"
            >
              Star on GitHub
            </a>
            <a
              href="/opportunities"
              className="px-6 py-3 bg-white text-primary-600 rounded-lg hover:bg-primary-50 transition-colors font-semibold border-2 border-primary-600"
            >
              Browse All Opportunities
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
