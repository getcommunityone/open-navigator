import type {ReactNode} from 'react';
import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  // Get app URL from custom fields (safe for client-side code)
  const APP_URL = siteConfig.customFields?.appUrl as string || 'https://www.communityone.com';
  const logoUrl = useBaseUrl('/img/communityone_logo.svg');
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
          <img 
            src={logoUrl} 
            alt="CommunityOne Logo" 
            style={{ height: '80px', marginRight: '1rem' }}
          />
          <Heading as="h1" className="hero__title" style={{ margin: 0 }}>
            {siteConfig.title}
          </Heading>
        </div>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <p style={{ fontSize: '1.15rem', marginTop: '1rem', marginBottom: '0.5rem', maxWidth: '720px', margin: '1rem auto 0.5rem' }}>
          Every person deserves to find the help they need and have a voice in the decisions that shape their lives.
          But public resources are scattered, gaps go unseen, and communities are left navigating alone.
        </p>
        <p style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '2rem', maxWidth: '720px', margin: '0.5rem auto 2rem' }}>
          CommunityOne changes that — one platform connecting residents, leaders, and funders to what's really happening on the ground.
        </p>
      </div>
    </header>
  );
}

function AudiencePathways() {
  const {siteConfig} = useDocusaurusContext();
  const APP_URL = siteConfig.customFields?.appUrl as string || 'https://www.communityone.com';
  
  return (
    <section className="container margin-vert--xl">
      <div className="row">
        <div className="col text--center margin-bottom--lg">
          <Heading as="h2">Choose Your Path</Heading>
          <p style={{ fontSize: '1.1rem', color: '#666' }}>
            Select the documentation that matches your role
          </p>
        </div>
      </div>
      <div className="row">
        {/* Policy Makers & Advocates Path */}
        <div className="col col--6">
          <div style={{
            border: '3px solid #4CAF50',
            borderRadius: '12px',
            padding: '2rem',
            height: '100%',
            background: 'linear-gradient(135deg, #f1f8f4 0%, #ffffff 100%)',
            transition: 'transform 0.2s, box-shadow 0.2s',
            cursor: 'pointer'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-5px)';
            e.currentTarget.style.boxShadow = '0 8px 16px rgba(76, 175, 80, 0.3)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }}>
            <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '4rem' }}>📊</div>
              <Heading as="h3" style={{ color: '#2E7D32', marginTop: '1rem' }}>
                Policy Makers & Advocates
              </Heading>
            </div>
            
            <p style={{ fontSize: '1.1rem', marginBottom: '1.5rem', textAlign: 'center' }}>
              <strong>I want to:</strong>
            </p>
            
            <ul style={{ fontSize: '1rem', lineHeight: '1.8', marginBottom: '2rem' }}>
              <li>Hold governments accountable</li>
              <li>Analyze meeting minutes and budgets</li>
              <li>Track nonprofit spending vs. mission</li>
              <li>Find advocacy opportunities</li>
              <li>Generate campaign materials</li>
            </ul>
            
            <div style={{ textAlign: 'center' }}>
              <Link
                className="button button--success button--lg"
                to="for-advocates"
                style={{ marginBottom: '0.5rem', width: '80%' }}>
                Start Here: Advocacy Docs →
              </Link>
              <div style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#555' }}>
                <a href={APP_URL} style={{ fontWeight: 'bold' }}>
                  🚀 Or launch the app immediately
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Developers & Technical Users Path */}
        <div className="col col--6">
          <div style={{
            border: '3px solid #2196F3',
            borderRadius: '12px',
            padding: '2rem',
            height: '100%',
            background: 'linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%)',
            transition: 'transform 0.2s, box-shadow 0.2s',
            cursor: 'pointer'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-5px)';
            e.currentTarget.style.boxShadow = '0 8px 16px rgba(33, 150, 243, 0.3)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }}>
            <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '4rem' }}>🛠️</div>
              <Heading as="h3" style={{ color: '#1565C0', marginTop: '1rem' }}>
                Developers & Technical Users
              </Heading>
            </div>
            
            <p style={{ fontSize: '1.1rem', marginBottom: '1.5rem', textAlign: 'center' }}>
              <strong>I want to:</strong>
            </p>
            
            <ul style={{ fontSize: '1rem', lineHeight: '1.8', marginBottom: '2rem' }}>
              <li>Install and configure the platform</li>
              <li>Scrape meeting data at scale</li>
              <li>Integrate with data pipelines</li>
              <li>Deploy to production</li>
              <li>Contribute to development</li>
            </ul>
            
            <div style={{ textAlign: 'center' }}>
              <Link
                className="button button--primary button--lg"
                to="for-developers"
                style={{ marginBottom: '0.5rem', width: '80%' }}>
                Start Here: Developer Docs →
              </Link>
              <div style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#555' }}>
                <Link to="quickstart" style={{ fontWeight: 'bold' }}>
                  ⚡ Quick Start Guide
                </Link>
                {' | '}
                <Link to="architecture" style={{ fontWeight: 'bold' }}>
                  🏗️ Architecture
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Not sure section */}
      <div className="row margin-top--lg">
        <div className="col text--center">
          <p style={{ fontSize: '1rem', color: '#666' }}>
            Not sure which path to take?{' '}
            <Link to="intro" style={{ fontWeight: 'bold' }}>
              Start with the Introduction →
            </Link>
          </p>
        </div>
      </div>
    </section>
  );
}

function HomepageFeatures() {
  const features = [
    {
      title: '📄 Meeting Minutes & Financial Documents',
      description: 'Tracks what happens in local meetings and budgets. Covers 90,000+ cities, counties, and school districts.',
    },
    {
      title: '🤖 Automated Analysis',
      description: 'Finds documents. Reads them. Identifies topics. Spots opportunities. Drafts emails.',
    },
    {
      title: '💰 Words vs Money',
      description: 'Compare what they say in meetings with what they actually spend. Find the gaps.',
    },
    {
      title: '🔍 Free Public Data',
      description: 'Census, school district, and nonprofit data. All free. All public.',
    },
    {
      title: '🗺️ Visual Map',
      description: 'See opportunities on a map. Filter by topic and urgency. Click for details.',
    },
    {
      title: '📧 Draft Materials',
      description: 'Auto-generate emails, talking points, and social posts for each opportunity.',
    },
  ];

  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {features.map((feature, idx) => (
            <div key={idx} className={clsx('col col--4')}>
              <div className="text--center padding-horiz--md padding-vert--md">
                <Heading as="h3">{feature.title}</Heading>
                <p>{feature.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function HomepageStats() {
  return (
    <section style={{ background: '#f8f9fa', padding: '3rem 0' }}>
      <div className="container">
        <div className="row">
          <div className="col text--center">
            <Heading as="h2">Data Coverage Nationwide</Heading>
            <p className="margin-bottom--lg" style={{ fontSize: '1.1rem', color: '#666' }}>
              100% free, public data from official sources
            </p>
          </div>
        </div>
        <div className="row">
          <div className="col col--3 text--center">
            <div className="padding--md">
              <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#2196F3' }}>90,000+</div>
              <p style={{ fontSize: '1rem', fontWeight: '500' }}>Government Jurisdictions</p>
              <p style={{ fontSize: '0.9rem', color: '#666' }}>Counties, cities, townships</p>
            </div>
          </div>
          <div className="col col--3 text--center">
            <div className="padding--md">
              <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#4CAF50' }}>3M+</div>
              <p style={{ fontSize: '1rem', fontWeight: '500' }}>Nonprofit Organizations</p>
              <p style={{ fontSize: '0.9rem', color: '#666' }}>IRS Form 990 data</p>
            </div>
          </div>
          <div className="col col--3 text--center">
            <div className="padding--md">
              <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#FF9800' }}>13,000+</div>
              <p style={{ fontSize: '1rem', fontWeight: '500' }}>School Districts</p>
              <p style={{ fontSize: '0.9rem', color: '#666' }}>Financial & meeting data</p>
            </div>
          </div>
          <div className="col col--3 text--center">
            <div className="padding--md">
              <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#9C27B0' }}>1,000+</div>
              <p style={{ fontSize: '1rem', fontWeight: '500' }}>Meeting Videos</p>
              <p style={{ fontSize: '0.9rem', color: '#666' }}>Full transcripts available</p>
            </div>
          </div>
        </div>
        <div className="row margin-top--md">
          <div className="col text--center">
            <p style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#2E7D32' }}>
              💰 Total Cost: $0 — All data is free and public
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function WhyItMatters() {
  return (
    <section className="container margin-vert--xl">
      <div className="text--center margin-bottom--lg">
        <Heading as="h2">Why This Matters</Heading>
        <p style={{ fontSize: '1.1rem', color: '#666', marginTop: '1rem' }}>
          Turn public data into accountability and action
        </p>
      </div>
      <div className="row margin-top--lg">
        <div className="col col--4 padding--md">
          <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
            <span style={{ fontSize: '3rem' }}>🎯</span>
          </div>
          <Heading as="h4" style={{ textAlign: 'center' }}>Direct Community Impact</Heading>
          <p style={{ textAlign: 'center' }}>
            Find nonprofits and organizations already providing services, connect citizens to care, and identify partnership opportunities.
          </p>
        </div>
        <div className="col col--4 padding--md">
          <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
            <span style={{ fontSize: '3rem' }}>⚖️</span>
          </div>
          <Heading as="h4" style={{ textAlign: 'center' }}>Government Accountability</Heading>
          <p style={{ textAlign: 'center' }}>
            Challenge "impossibility" claims, expose resource gaps, and compare spending priorities with service provision.
          </p>
        </div>
        <div className="col col--4 padding--md">
          <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
            <span style={{ fontSize: '3rem' }}>🚀</span>
          </div>
          <Heading as="h4" style={{ textAlign: 'center' }}>Strategic Advocacy</Heading>
          <p style={{ textAlign: 'center' }}>
            Ground campaigns in real data, build coalitions, and mobilize communities with evidence-based messaging.
          </p>
        </div>
      </div>
    </section>
  );
}

function GetStartedCTA() {
  const {siteConfig} = useDocusaurusContext();
  const APP_URL = siteConfig.customFields?.appUrl as string || 'https://www.communityone.com';
  
  return (
    <section style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', padding: '4rem 0', color: 'white' }}>
      <div className="container text--center">
        <Heading as="h2" style={{ color: 'white', marginBottom: '1rem' }}>
          Ready to Get Started?
        </Heading>
        <p style={{ fontSize: '1.2rem', marginBottom: '2rem', opacity: 0.9 }}>
          Choose your path and start exploring the data
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link
            className="button button--success button--lg"
            to="for-advocates"
            style={{ minWidth: '200px' }}>
            📊 For Advocates
          </Link>
          <Link
            className="button button--info button--lg"
            to="for-developers"
            style={{ minWidth: '200px' }}>
            🛠️ For Developers
          </Link>
          <Link
            className="button button--secondary button--lg"
            href={APP_URL}
            style={{ minWidth: '200px' }}>
            🚀 Launch App
          </Link>
        </div>
        <p style={{ marginTop: '2rem', fontSize: '0.9rem', opacity: 0.8 }}>
          All data is free and public • No subscriptions • Open source
        </p>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  
  return (
    <Layout
      title={`${siteConfig.title}`}
      description="One platform connecting residents, leaders, and funders to what's really happening on the ground — so no community has to fight just to be seen.">
      
      <HomepageHeader />
      <main>
        <AudiencePathways />
        <HomepageFeatures />
        <HomepageStats />
        <WhyItMatters />
        <GetStartedCTA />
      </main>
    </Layout>
  );
}
