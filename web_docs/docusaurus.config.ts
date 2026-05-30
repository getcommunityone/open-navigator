import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** Ensures `window.gtag` exists before @docusaurus/plugin-google-gtag client code runs. */
function ensureGtagHeadStubPlugin() {
  return {
    name: 'ensure-gtag-fn-head-stub',
    injectHtmlTags(_args: { content: unknown }): { headTags: { tagName: 'script'; innerHTML: string }[] } {
      return {
        headTags: [
          {
            tagName: 'script',
            innerHTML: `window.dataLayer=window.dataLayer||[];if(typeof window.gtag!=="function"){window.gtag=function(){window.dataLayer.push(arguments)};}`,
          },
        ],
      }
    },
  }
}

const config: Config = {
  title: 'Open Navigator',
  tagline: 'One Map for Every Community',
  favicon: 'img/favicon.ico',

  /** Runs before plugin client modules so `window.gtag` is always callable. */
  clientModules: ['./src/clientModules/gtagSafeShim.ts'],

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://www.communityone.com',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  // For HuggingFace Spaces, docs are served from /docs/ subdirectory
  baseUrl: process.env.DOCUSAURUS_BASE_URL || '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'getcommunityone', // Usually your GitHub org/user name.
  projectName: 'open-navigator', // Usually your repo name.

  onBrokenLinks: 'warn',

  // Custom fields to make environment variables available in client-side code
  customFields: {
    appUrl: process.env.APP_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:5173' : 'https://www.communityone.com'),
  },

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          // If baseUrl already includes /docs/, serve at root. Otherwise add /docs/.
          // Production (HF): baseUrl=/docs/ + routeBasePath=/ = /docs/intro ✓
          // Development: baseUrl=/ + routeBasePath=docs = /docs/intro ✓
          routeBasePath: process.env.DOCUSAURUS_BASE_URL ? '/' : 'docs',
          sidebarPath: './sidebars.ts',
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/getcommunityone/open-navigator-for-engagement/tree/main/web_docs/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/getcommunityone/open-navigator-for-engagement/tree/main/web_docs/',
          // Useful options to enforce blogging best practices
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
        // Google Analytics for tracking and SEO
        gtag: {
          trackingID: 'G-5EQV815915',
          anonymizeIP: true,
        },
        // Sitemap configuration for better SEO
        sitemap: {
          changefreq: 'weekly',
          priority: 0.5,
          ignorePatterns: ['/tags/**'],
          filename: 'sitemap.xml',
        },
      } satisfies Preset.Options,
    ],
  ],

  themes: ['@docusaurus/theme-mermaid'],

  plugins: [() => ensureGtagHeadStubPlugin()],

  markdown: {
    mermaid: true,
  },

  themeConfig: {
    // SEO metadata
    metadata: [
      {name: 'keywords', content: 'civic engagement, policy tracking, meeting minutes, nonprofit tracking, municipal government, advocacy, open data, local government'},
      {name: 'description', content: 'Open Navigator - Track 90,000+ jurisdictions, 1.8M nonprofits, and analyze meeting minutes with AI. The open path to everything local.'},
      {property: 'og:type', content: 'website'},
      {property: 'og:site_name', content: 'Open Navigator'},
      {name: 'twitter:card', content: 'summary_large_image'},
    ],
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 4, // Show h2-h4 headings for better navigation
    },
    mermaid: {
      theme: { light: 'default', dark: 'dark' },
      options: {
        fontSize: 18,
        fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        entityPadding: 20,
        minEntityHeight: 120,
        minEntityWidth: 180,
      },
    },
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Open Navigator Home',
      logo: {
        alt: 'CommunityOne Logo',
        src: 'img/communityone_logo.svg',
        href: process.env.APP_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:5173' : 'https://www.communityone.com'),
        target: '_self',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'gettingStartedSidebar',
          position: 'left',
          label: 'Getting Started',
        },
        {
          type: 'docSidebar',
          sidebarId: 'handbookSidebar',
          position: 'left',
          label: 'Handbook',
        },
        {
          type: 'docSidebar',
          sidebarId: 'catalogSidebar',
          position: 'left',
          label: 'Catalog',
        },
        {
          type: 'docSidebar',
          sidebarId: 'familiesSidebar',
          position: 'left',
          label: 'Families & Individuals',
        },
        {
          type: 'docSidebar',
          sidebarId: 'policyMakersSidebar',
          position: 'left',
          label: 'Policy Makers',
        },
        {
          type: 'docSidebar',
          sidebarId: 'developersSidebar',
          position: 'left',
          label: 'Developers',
        },
        {
          to: 'docs/data-sources/citations',
          label: 'Data and Terms',
          position: 'left',
        },
        {to: 'blog', label: 'Blog', position: 'left'},
        {
          href: 'https://github.com/getcommunityone/open-navigator-for-engagement',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Getting Started',
              to: 'docs/intro',
            },
            {
              label: 'Citations & Data Sources',
              to: 'docs/data-sources/citations',
            },
            {
              label: 'Data Sources',
              to: 'docs/data-sources/overview',
            },
            {
              label: 'For Developers',
              to: 'docs/for-developers',
            },
          ],
        },
        {
          title: 'Resources',
          items: [
            {
              label: 'Launch Open Navigator',
              href: process.env.APP_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:5173' : 'https://www.communityone.com'),
            },
            {
              label: 'GitHub',
              href: 'https://github.com/getcommunityone/open-navigator-for-engagement',
            },
            {
              label: 'CommunityOne',
              href: 'https://www.communityone.com/',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'Instagram',
              href: 'https://www.instagram.com/getcommunityone/',
            },
            {
              label: 'Facebook',
              href: 'https://www.facebook.com/getcommunityone',
            },
            {
              label: 'X (Twitter)',
              href: 'https://x.com/getcommunityone/',
            },
            {
              label: 'LinkedIn',
              href: 'https://www.linkedin.com/company/getcommunityone',
            },
            {
              label: 'YouTube',
              href: 'https://www.youtube.com/@getcommunityone',
            },
            {
              label: 'Discord',
              href: 'https://discord.gg/uH6Dytek',
            },
          ],
        },
        {
          title: 'Legal',
          items: [
            {
              label: 'Privacy Policy',
              to: 'docs/legal/privacy-policy',
            },
            {
              label: 'Terms of Service',
              to: 'docs/legal/terms-of-service',
            },
            {
              label: 'Data Provider Terms',
              to: 'docs/legal/data-provider-terms',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'Blog',
              to: 'blog',
            },
            {
              label: 'License (MIT)',
              href: 'https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/LICENSE',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Community One. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
  