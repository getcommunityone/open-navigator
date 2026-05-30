import { Fragment, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { XMarkIcon, MapPinIcon } from '@heroicons/react/24/outline'

interface RegistrationModalProps {
  isOpen: boolean
  onClose: () => void
  onComplete: (data: LocationData) => void
  initialData?: {
    state?: string
    county?: string
    city?: string
    school_board?: string
  }
}

interface LocationData {
  state: string
  county: string
  city: string
  school_board: string
}

export default function RegistrationModal({ isOpen, onClose, onComplete, initialData }: RegistrationModalProps) {
  const [formData, setFormData] = useState<LocationData>({
    state: initialData?.state || '',
    county: initialData?.county || '',
    city: initialData?.city || '',
    school_board: initialData?.school_board || '',
  })

  const [errors, setErrors] = useState<Record<string, string>>({})

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate required fields
    const newErrors: Record<string, string> = {}
    if (!formData.state.trim()) newErrors.state = 'State is required'
    if (!formData.county.trim()) newErrors.county = 'County is required'
    if (!formData.city.trim()) newErrors.city = 'City is required'
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }
    
    onComplete(formData)
  }

  const handleChange = (field: keyof LocationData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    // Clear error for this field
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
  }

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-25" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <MapPinIcon className="h-6 w-6 text-primary-600" />
                    <Dialog.Title
                      as="h3"
                      className="text-lg font-medium leading-6 text-gray-900"
                    >
                      Complete Your Profile
                    </Dialog.Title>
                  </div>
                  <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-gray-500 transition-colors"
                  >
                    <XMarkIcon className="h-6 w-6" />
                  </button>
                </div>

                <p className="text-sm text-gray-500 mb-6">
                  Help us personalize your experience by telling us where you're located.
                  You can update this information anytime in Settings.
                </p>

                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* State */}
                  <div>
                    <label htmlFor="state" className="block text-sm font-medium text-gray-700 mb-1">
                      State <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="state"
                      value={formData.state}
                      onChange={(e) => handleChange('state', e.target.value)}
                      placeholder="e.g., California, Texas, New York"
                      className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                        errors.state ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    {errors.state && (
                      <p className="mt-1 text-sm text-red-600">{errors.state}</p>
                    )}
                  </div>

                  {/* County */}
                  <div>
                    <label htmlFor="county" className="block text-sm font-medium text-gray-700 mb-1">
                      County <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="county"
                      value={formData.county}
                      onChange={(e) => handleChange('county', e.target.value)}
                      placeholder="e.g., Los Angeles County, Harris County"
                      className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                        errors.county ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    {errors.county && (
                      <p className="mt-1 text-sm text-red-600">{errors.county}</p>
                    )}
                  </div>

                  {/* City */}
                  <div>
                    <label htmlFor="city" className="block text-sm font-medium text-gray-700 mb-1">
                      City <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="city"
                      value={formData.city}
                      onChange={(e) => handleChange('city', e.target.value)}
                      placeholder="e.g., Los Angeles, Houston, New York"
                      className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                        errors.city ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    {errors.city && (
                      <p className="mt-1 text-sm text-red-600">{errors.city}</p>
                    )}
                  </div>

                  {/* School Board */}
                  <div>
                    <label htmlFor="school_board" className="block text-sm font-medium text-gray-700 mb-1">
                      School Board / District <span className="text-gray-400 text-xs">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      id="school_board"
                      value={formData.school_board}
                      onChange={(e) => handleChange('school_board', e.target.value)}
                      placeholder="e.g., LAUSD, Houston ISD"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>

                  {/* Submit Button */}
                  <div className="flex gap-3 pt-4">
                    <button
                      type="button"
                      onClick={onClose}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors font-medium"
                    >
                      Skip for Now
                    </button>
                    <button
                      type="submit"
                      className="flex-1 px-4 py-2 text-white rounded-lg transition-colors font-medium"
                      style={{ backgroundColor: '#354F52' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2e4346'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#354F52'}
                    >
                      Complete Profile
                    </button>
                  </div>
                </form>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
