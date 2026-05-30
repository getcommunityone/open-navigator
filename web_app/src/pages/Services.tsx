import { useEffect } from 'react';
import { HeartIcon, HomeIcon, AcademicCapIcon, PhoneIcon, MapIcon } from '@heroicons/react/24/outline';

export default function Services() {
  // Scroll to top with smooth behavior when page loads
  useEffect(() => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-3 bg-primary-50 rounded-lg">
            <HeartIcon className="h-8 w-8 text-primary-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Services & Resources</h1>
            <p className="text-gray-600 mt-1">Find family services, social programs, and community support resources</p>
          </div>
        </div>
      </div>

      {/* Coming Soon Notice */}
      <div className="bg-purple-50 border border-purple-200 rounded-xl p-8 mb-8">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0">
            <HeartIcon className="h-12 w-12 text-purple-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-purple-900 mb-2">Coming Soon!</h2>
            <p className="text-purple-800 mb-4">
              We're creating a comprehensive directory of family services and community resources.
            </p>
            <div className="space-y-2 text-purple-700">
              <h3 className="font-semibold">What you'll find here:</h3>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Healthcare services including dental clinics and mental health support</li>
                <li>Educational programs, tutoring, and after-school activities</li>
                <li>Food assistance, housing support, and financial aid programs</li>
                <li>Legal aid, translation services, and crisis hotlines</li>
                <li>Parks & recreation programs, dog parks, and community facilities</li>
                <li>Senior services, youth activities, and family programs</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Preview Service Categories */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Health Services */}
        <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 opacity-60">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-red-100 rounded-lg">
              <HeartIcon className="h-6 w-6 text-red-600" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">Health Services</h3>
          </div>
          <ul className="space-y-2 text-sm text-gray-600">
            <li>• Free dental clinics</li>
            <li>• Community health centers</li>
            <li>• Mental health counseling</li>
            <li>• Vision screening programs</li>
          </ul>
        </div>

        {/* Education */}
        <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 opacity-60">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-100 rounded-lg">
              <AcademicCapIcon className="h-6 w-6 text-blue-600" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">Education</h3>
          </div>
          <ul className="space-y-2 text-sm text-gray-600">
            <li>• After-school programs</li>
            <li>• Tutoring services</li>
            <li>• Adult education</li>
            <li>• STEM workshops</li>
          </ul>
        </div>

        {/* Housing & Basic Needs */}
        <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 opacity-60">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-green-100 rounded-lg">
              <HomeIcon className="h-6 w-6 text-green-600" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">Basic Needs</h3>
          </div>
          <ul className="space-y-2 text-sm text-gray-600">
            <li>• Food pantries</li>
            <li>• Housing assistance</li>
            <li>• Utility support</li>
            <li>• Emergency shelters</li>
          </ul>
        </div>

        {/* Parks & Recreation */}
        <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 opacity-60">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-emerald-100 rounded-lg">
              <MapIcon className="h-6 w-6 text-emerald-600" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">Parks & Recreation</h3>
          </div>
          <ul className="space-y-2 text-sm text-gray-600">
            <li>• Community parks</li>
            <li>• Dog parks & pet areas</li>
            <li>• Sports facilities</li>
            <li>• Recreation programs</li>
          </ul>
        </div>
      </div>

      {/* Emergency Contacts Card */}
      <div className="mt-8 bg-gradient-to-r from-red-500 to-red-600 rounded-xl p-6 text-white">
        <div className="flex items-center gap-3 mb-3">
          <PhoneIcon className="h-8 w-8" />
          <h2 className="text-2xl font-bold">Emergency Resources</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="font-semibold mb-1">Crisis Hotline</div>
            <div>988 - Suicide & Crisis Lifeline</div>
          </div>
          <div>
            <div className="font-semibold mb-1">Domestic Violence</div>
            <div>1-800-799-7233 (SAFE)</div>
          </div>
          <div>
            <div className="font-semibold mb-1">Child Abuse</div>
            <div>1-800-422-4453</div>
          </div>
        </div>
      </div>

      {/* Temporary Link */}
      <div className="mt-8 text-center">
        <p className="text-gray-600 mb-4">Browse nonprofit organizations offering services:</p>
        <a
          href="/nonprofits?category=family-services"
          className="inline-flex items-center px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-semibold"
        >
          Explore Nonprofits →
        </a>
      </div>
    </div>
  );
}
