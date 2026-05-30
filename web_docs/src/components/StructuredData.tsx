/**
 * Structured Data (JSON-LD) for SEO
 * Helps Google understand your organization and content
 */
import React from 'react';

export default function StructuredData(): JSX.Element {
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "CommunityOne",
    "legalName": "CommunityOne",
    "url": "https://www.communityone.com",
    "logo": "https://www.communityone.com/img/communityone_logo.svg",
    "description": "Track 90,000+ jurisdictions, 1.8M nonprofits, and analyze meeting minutes with AI. The open path to everything local.",
    "email": "johnbowyer@communityone.com",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "5617 Lakeridge Court",
      "addressLocality": "Tuscaloosa",
      "addressRegion": "AL",
      "postalCode": "35406",
      "addressCountry": "US"
    },
    "sameAs": [
      "https://www.facebook.com/communityone",
      "https://www.instagram.com/communityone",
      "https://twitter.com/communityone",
      "https://www.linkedin.com/company/communityone",
      "https://www.youtube.com/@communityone",
      "https://discord.gg/communityone",
      "https://github.com/getcommunityone/open-navigator"
    ],
    "contactPoint": {
      "@type": "ContactPoint",
      "email": "johnbowyer@communityone.com",
      "contactType": "Customer Service",
      "availableLanguage": ["English"]
    }
  };

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Open Navigator",
    "alternateName": "CommunityOne Open Navigator",
    "url": "https://www.communityone.com",
    "description": "AI-powered civic engagement platform tracking jurisdictions, nonprofits, and government meetings",
    "potentialAction": {
      "@type": "SearchAction",
      "target": {
        "@type": "EntryPoint",
        "urlTemplate": "https://www.communityone.com/search?q={search_term_string}"
      },
      "query-input": "required name=search_term_string"
    }
  };

  const softwareSchema = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "Open Navigator",
    "applicationCategory": "BusinessApplication",
    "operatingSystem": "Web",
    "offers": {
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD"
    },
    "description": "Track 90,000+ jurisdictions, 1.8M nonprofits, and analyze meeting minutes with AI",
    "screenshot": "https://www.communityone.com/img/docusaurus-social-card.jpg",
    "featureList": [
      "Track 90,000+ jurisdictions",
      "Monitor 1.8M nonprofits",
      "Analyze meeting minutes",
      "Legislative bill tracking",
      "Campaign finance data"
    ],
    "softwareVersion": "1.0.0",
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": "5",
      "ratingCount": "1"
    }
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(organizationSchema),
        }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(websiteSchema),
        }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(softwareSchema),
        }}
      />
    </>
  );
}
