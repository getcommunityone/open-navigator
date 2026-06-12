import { EnvelopeIcon } from '@heroicons/react/24/outline'

/**
 * Contact page — the simple "Get in Touch" card.
 *
 * Mirrors the legacy home-page contact CTA (a single mailto button) rather than
 * the previous full ticket form. The Contact nav link (SiteHeader) points here.
 */
export default function Support() {
  return (
    <section
      id="contact"
      className="py-20 px-4 bg-gradient-to-br from-gray-50 to-blue-50"
    >
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-12 text-center">
          <EnvelopeIcon className="h-16 w-16 mx-auto mb-6" style={{ color: '#354F52' }} />
          <h2 className="text-4xl md:text-5xl font-bold mb-4" style={{ color: '#354F52' }}>
            Get in Touch
          </h2>
          <p className="text-xl text-gray-600 mb-8">
            Questions, feedback, or ideas? We'd love to hear from you.
            Report bugs, request features, or ask questions about jurisdiction coverage.
          </p>
          <div className="flex justify-center">
            <a
              href="mailto:johnbowyer@communityone.com"
              className="inline-flex items-center justify-center px-8 py-4 rounded-lg text-white font-semibold transition-all hover:shadow-lg"
              style={{ backgroundColor: '#354F52' }}
            >
              <EnvelopeIcon className="h-5 w-5 mr-2" />
              Email Us
            </a>
          </div>
          <p className="text-sm text-gray-500 mt-6">
            Your feedback helps us improve the platform for everyone.
          </p>
        </div>
      </div>
    </section>
  )
}
