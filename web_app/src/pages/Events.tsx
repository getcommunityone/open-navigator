import { CalendarIcon, MapPinIcon, UserGroupIcon, ClockIcon } from '@heroicons/react/24/outline';

export default function Events() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-3 bg-primary-50 rounded-lg">
            <CalendarIcon className="h-8 w-8 text-primary-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Community Events</h1>
            <p className="text-gray-600 mt-1">Discover upcoming public meetings, community gatherings, and civic events</p>
          </div>
        </div>
      </div>

      {/* Coming Soon Notice */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-8 mb-8">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0">
            <CalendarIcon className="h-12 w-12 text-blue-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-blue-900 mb-2">Coming Soon!</h2>
            <p className="text-blue-800 mb-4">
              We're building a comprehensive events calendar to help you stay engaged with your community.
            </p>
            <div className="space-y-2 text-blue-700">
              <h3 className="font-semibold">What you'll find here:</h3>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>City council meetings, school board sessions, and public hearings</li>
                <li>Community forums, town halls, and neighborhood gatherings</li>
                <li>Voter registration drives and civic engagement events</li>
                <li>Training workshops and educational programs</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Preview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Example Event 1 */}
        <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 opacity-60">
          <div className="flex items-start justify-between mb-4">
            <h3 className="text-xl font-bold text-gray-900">City Council Meeting</h3>
            <span className="px-3 py-1 bg-green-100 text-green-800 text-xs font-semibold rounded-full">
              Upcoming
            </span>
          </div>
          <div className="space-y-3 text-gray-600">
            <div className="flex items-center gap-2">
              <ClockIcon className="h-5 w-5 text-gray-400" />
              <span>Tuesday, May 5, 2026 at 6:00 PM</span>
            </div>
            <div className="flex items-center gap-2">
              <MapPinIcon className="h-5 w-5 text-gray-400" />
              <span>City Hall, Main Chamber</span>
            </div>
            <div className="flex items-center gap-2">
              <UserGroupIcon className="h-5 w-5 text-gray-400" />
              <span>Open to the public</span>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-600">
              Budget discussions, zoning changes, and community feedback session
            </p>
          </div>
        </div>

        {/* Example Event 2 */}
        <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 opacity-60">
          <div className="flex items-start justify-between mb-4">
            <h3 className="text-xl font-bold text-gray-900">Community Health Fair</h3>
            <span className="px-3 py-1 bg-purple-100 text-purple-800 text-xs font-semibold rounded-full">
              Registration Open
            </span>
          </div>
          <div className="space-y-3 text-gray-600">
            <div className="flex items-center gap-2">
              <ClockIcon className="h-5 w-5 text-gray-400" />
              <span>Saturday, May 10, 2026 at 10:00 AM</span>
            </div>
            <div className="flex items-center gap-2">
              <MapPinIcon className="h-5 w-5 text-gray-400" />
              <span>Community Center, 123 Main St</span>
            </div>
            <div className="flex items-center gap-2">
              <UserGroupIcon className="h-5 w-5 text-gray-400" />
              <span>Free for families</span>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-600">
              Free dental screenings, health resources, and family activities
            </p>
          </div>
        </div>
      </div>

      {/* Temporary Link */}
      <div className="mt-8 text-center">
        <p className="text-gray-600 mb-4">In the meantime, browse upcoming meetings:</p>
        <a
          href="/documents?filter=upcoming"
          className="inline-flex items-center px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-semibold"
        >
          View Meeting Calendar →
        </a>
      </div>
    </div>
  );
}
