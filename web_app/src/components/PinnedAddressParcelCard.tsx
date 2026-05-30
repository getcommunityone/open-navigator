import { MapPinIcon } from '@heroicons/react/24/outline'

interface PinnedAddressParcelCardProps {
  label: string
  lat: number
  lng: number
  onBack: () => void
}

/**
 * Right-rail panel shown in the local satellite view. Stubbed for now — the
 * real parcel record (owner, parcel number, appraised value, tax class) comes
 * from a future /api/parcels/lookup endpoint backed by bronze.bronze_addresses.
 */
export default function PinnedAddressParcelCard({
  label,
  lat,
  lng,
  onBack,
}: PinnedAddressParcelCardProps) {
  return (
    <div className="rounded-lg border border-rose-200 bg-white p-3 shadow-sm">
      <div className="flex items-start gap-2">
        <div className="rounded-full bg-rose-50 p-1.5 text-rose-700">
          <MapPinIcon className="h-4 w-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-rose-700">
            Pinned address
          </div>
          <div className="mt-0.5 text-sm font-semibold leading-snug text-slate-900">{label}</div>
          <div className="mt-1 font-mono text-[11px] text-slate-500 tabular-nums">
            {lat.toFixed(5)}, {lng.toFixed(5)}
          </div>
        </div>
      </div>

      <dl className="mt-3 space-y-1.5 border-t border-slate-100 pt-2.5 text-[12px]">
        <ParcelFieldStub label="Owner" />
        <ParcelFieldStub label="Parcel #" />
        <ParcelFieldStub label="Appraised value" />
        <ParcelFieldStub label="Tax class" />
        <ParcelFieldStub label="Source" />
      </dl>
      <p className="mt-2 text-[11px] leading-snug text-slate-500">
        Parcel lookup against <code className="rounded bg-slate-100 px-1 py-px font-mono text-[10px] text-slate-700">bronze.bronze_addresses</code> not yet wired
        up. Fields will populate once the staging model and API route land.
      </p>

      <div className="mt-3 border-t border-slate-100 pt-2">
        <button
          type="button"
          onClick={onBack}
          className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-700 hover:bg-slate-50"
        >
          Clear pin
        </button>
      </div>
    </div>
  )
}

function ParcelFieldStub({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-slate-400">—</dd>
    </div>
  )
}
