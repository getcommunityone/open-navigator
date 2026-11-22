/**
 * Minimal site footer: legal links (YouTube API audit expects these on the
 * public homepage) + CommunityOne social icons (same URLs as docs).
 */
import type { ReactNode } from 'react'
import { docsUrl } from '../utils/docsLinks'

const MUTED = '#78716c'
const ICON = '#57534e'

type Social = {
  label: string
  href: string
  icon: ReactNode
}

function IconWrap({ children }: { children: ReactNode }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

const SOCIAL: Social[] = [
  {
    label: 'Instagram',
    href: 'https://www.instagram.com/getcommunityone/',
    icon: (
      <IconWrap>
        <path d="M7.8 2h8.4C19.4 2 22 4.6 22 7.8v8.4a5.8 5.8 0 0 1-5.8 5.8H7.8C4.6 22 2 19.4 2 16.2V7.8A5.8 5.8 0 0 1 7.8 2m-.2 2A3.6 3.6 0 0 0 4 7.6v8.8A3.6 3.6 0 0 0 7.6 20h8.8a3.6 3.6 0 0 0 3.6-3.6V7.6A3.6 3.6 0 0 0 16.4 4H7.6m9.65 1.5a1.25 1.25 0 1 1 0 2.5 1.25 1.25 0 0 1 0-2.5M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10m0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" />
      </IconWrap>
    ),
  },
  {
    label: 'Facebook',
    href: 'https://www.facebook.com/getcommunityone',
    icon: (
      <IconWrap>
        <path d="M14 13.5h2.5l1-4H14v-2c0-1.03 0-2 2-2h1.5V2.14c-.326-.043-1.557-.14-2.857-.14C11.928 2 10 3.657 10 6.7v2.8H7v4h3V22h4v-8.5z" />
      </IconWrap>
    ),
  },
  {
    label: 'X (Twitter)',
    href: 'https://x.com/getcommunityone/',
    icon: (
      <IconWrap>
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.74l7.727-8.835L1.254 2.25H8.08l4.253 5.622L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z" />
      </IconWrap>
    ),
  },
  {
    label: 'LinkedIn',
    href: 'https://www.linkedin.com/company/getcommunityone',
    icon: (
      <IconWrap>
        <path d="M6.94 5a2 2 0 1 1-4-.002 2 2 0 0 1 4 .002zM7 8.48H3V21h4V8.48zm6.32 0H9.34V21h3.94v-6.57c0-3.66 4.77-4 4.77 0V21H22v-7.93c0-6.17-7.06-5.94-8.72-2.91l.04-1.68z" />
      </IconWrap>
    ),
  },
  {
    label: 'YouTube',
    href: 'https://www.youtube.com/@getcommunityone',
    icon: (
      <IconWrap>
        <path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2 31.5 31.5 0 0 0 0 12a31.5 31.5 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31.5 31.5 0 0 0 24 12a31.5 31.5 0 0 0-.5-5.8zM9.75 15.5v-7l6.5 3.5-6.5 3.5z" />
      </IconWrap>
    ),
  },
  {
    label: 'Discord',
    href: 'https://discord.gg/uH6Dytek',
    icon: (
      <IconWrap>
        <path d="M20.317 4.37a19.8 19.8 0 0 0-4.885-1.515.07.07 0 0 0-.074.035c-.21.375-.444.864-.608 1.25a18.3 18.3 0 0 0-5.487 0 12.6 12.6 0 0 0-.617-1.25.07.07 0 0 0-.074-.035A19.7 19.7 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.08.08 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.07.07 0 0 0 .084-.027 14 14 0 0 0 1.226-1.994.07.07 0 0 0-.041-.098 13.1 13.1 0 0 1-1.872-.892.07.07 0 0 1-.007-.117c.126-.094.252-.192.372-.291a.07.07 0 0 1 .076-.01 14.1 14.1 0 0 0 12.076 0 .07.07 0 0 1 .077.01c.12.099.246.198.373.292a.07.07 0 0 1-.006.117 12.3 12.3 0 0 1-1.873.891.07.07 0 0 0-.041.099 14.2 14.2 0 0 0 1.226 1.993.07.07 0 0 0 .084.028 19.8 19.8 0 0 0 6.002-3.03.07.07 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.06.06 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
      </IconWrap>
    ),
  },
]

const LEGAL = [
  { label: 'Privacy Policy', href: docsUrl('/legal/privacy-policy') },
  { label: 'Terms of Service', href: docsUrl('/legal/terms-of-service') },
  { label: 'Data Provider Terms', href: docsUrl('/legal/data-provider-terms') },
] as const

export default function SiteFooter() {
  return (
    <footer
      style={{
        background: '#fff',
        borderTop: '1px solid #e7e5e4',
      }}
    >
      <div
        className="v9-footer-inner"
        style={{
          maxWidth: 1180,
          margin: '0 auto',
          padding: '20px 24px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <nav aria-label="Legal" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 16px' }}>
            {LEGAL.map((item) => (
              <a
                key={item.href}
                href={item.href}
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: ICON,
                  textDecoration: 'underline',
                  textUnderlineOffset: 3,
                }}
              >
                {item.label}
              </a>
            ))}
          </nav>

          <nav aria-label="CommunityOne on social media" style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {SOCIAL.map((item) => (
              <a
                key={item.href}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={item.label}
                title={item.label}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  color: ICON,
                }}
              >
                {item.icon}
              </a>
            ))}
          </nav>
        </div>

        <span style={{ fontSize: 12.5, color: MUTED }}>
          CommunityOne · a 501(c)(3) nonprofit · Tuscaloosa, Alabama
        </span>
      </div>
    </footer>
  )
}
