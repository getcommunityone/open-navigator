import { Link } from 'react-router-dom';
import { HomeIcon, MagnifyingGlassIcon, DocumentTextIcon, MapIcon } from '@heroicons/react/24/outline';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4">
      <div className="max-w-2xl w-full text-center">
        {/* 404 Graphic */}
        <div className="mb-8">
          <h1 className="text-9xl font-bold text-blue-600 mb-4">404</h1>
          <div className="flex justify-center mb-6">
            <svg
              className="w-64 h-64 text-blue-200"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
        </div>

        {/* Message */}
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          Page Not Found
        </h2>
        <p className="text-lg text-gray-600 mb-8">
          Sorry, we couldn't find the page you're looking for. The page may have been moved, deleted, or never existed.
        </p>

        {/* Quick Links */}
        <div className="bg-white rounded-lg shadow-md p-8 mb-8">
          <h3 className="text-xl font-semibold text-gray-900 mb-6">
            Try one of these popular pages:
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              to="/"
              className="flex items-center p-4 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
            >
              <HomeIcon className="h-6 w-6 text-gray-400 group-hover:text-blue-600 mr-3" />
              <div className="text-left">
                <div className="font-semibold text-gray-900 group-hover:text-blue-600">Home</div>
                <div className="text-sm text-gray-500">Return to homepage</div>
              </div>
            </Link>

            <Link
              to="/search"
              className="flex items-center p-4 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
            >
              <MagnifyingGlassIcon className="h-6 w-6 text-gray-400 group-hover:text-blue-600 mr-3" />
              <div className="text-left">
                <div className="font-semibold text-gray-900 group-hover:text-blue-600">Search</div>
                <div className="text-sm text-gray-500">Find what you need</div>
              </div>
            </Link>

            <Link
              to="/explore"
              className="flex items-center p-4 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
            >
              <MapIcon className="h-6 w-6 text-gray-400 group-hover:text-blue-600 mr-3" />
              <div className="text-left">
                <div className="font-semibold text-gray-900 group-hover:text-blue-600">Take action</div>
                <div className="text-sm text-gray-500">Learn, decide, and act</div>
              </div>
            </Link>

            <Link
              to="/dashboard"
              className="flex items-center p-4 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
            >
              <DocumentTextIcon className="h-6 w-6 text-gray-400 group-hover:text-blue-600 mr-3" />
              <div className="text-left">
                <div className="font-semibold text-gray-900 group-hover:text-blue-600">Dashboard</div>
                <div className="text-sm text-gray-500">View your data</div>
              </div>
            </Link>
          </div>
        </div>

        {/* Additional Help */}
        <div className="text-gray-600">
          <p className="mb-4">
            Need help? Check out our{' '}
            <a
              href="https://www.communityone.com/docs"
              className="text-blue-600 hover:text-blue-800 font-semibold"
            >
              documentation
            </a>{' '}
            or{' '}
            <Link
              to="/support"
              className="text-blue-600 hover:text-blue-800 font-semibold"
            >
              contact support
            </Link>
            .
          </p>
          
          <p className="text-sm text-gray-500">
            Error Code: 404 • Page Not Found
          </p>
        </div>
      </div>
    </div>
  );
}
