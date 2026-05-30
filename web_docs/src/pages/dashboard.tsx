import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import BrowserOnly from '@docusaurus/BrowserOnly';

export default function DashboardRedirect(): JSX.Element {
  return (
    <Layout title="Dashboard" description="Access the Open Navigator Dashboard">
      <BrowserOnly fallback={<div>Loading...</div>}>
        {() => {
          // This code only runs in the browser
          const dashboardUrl = window.location.hostname === 'localhost'
            ? 'http://localhost:5173'
            : 'https://www.communityone.com';

          // Auto-redirect after 3 seconds
          React.useEffect(() => {
            const timer = setTimeout(() => {
              window.location.href = dashboardUrl;
            }, 3000);
            return () => clearTimeout(timer);
          }, []);

          return (
            <div className="container margin-vert--lg">
              <Heading as="h1">📊 Redirecting to Dashboard...</Heading>
              
              <div className="alert alert--success margin-vert--md">
                <p>
                  <strong>You will be redirected in 3 seconds...</strong>
                </p>
                <p>
                  Or click here to go immediately: <a href={dashboardUrl} target="_blank" rel="noopener noreferrer">
                    <strong>Open Dashboard →</strong>
                  </a>
                </p>
              </div>

              <div className="alert alert--info margin-vert--md">
                <p>
                  <strong>Note:</strong> The interactive dashboard is a separate React application (port 5173) 
                  that provides real-time access to advocacy opportunities, meeting minutes, and nonprofit data.
                  This documentation site (port 3000) provides guides and reference materials.
                </p>
              </div>

              <div className="card margin-vert--lg">
                <div className="card__header">
                  <Heading as="h3">Development Access</Heading>
                </div>
                <div className="card__body">
                  <p>To access the dashboard in development mode:</p>
                  <ol>
                    <li>
                      <strong>Start the API backend:</strong>
                      <pre><code>python -m uvicorn api.app:app --reload --port 8000</code></pre>
                    </li>
                    <li>
                      <strong>Start the React dashboard:</strong>
                      <pre><code>cd frontend && npm run dev</code></pre>
                    </li>
                    <li>
                      <strong>Access at:</strong> <a href="http://localhost:5173" target="_blank" rel="noopener noreferrer">http://localhost:5173</a>
                    </li>
                  </ol>
                </div>
              </div>

              <div className="margin-vert--lg">
                <Link to="/" className="button button--secondary button--lg">
                  ← Back to Documentation Home
                </Link>
              </div>
            </div>
          );
        }}
      </BrowserOnly>
    </Layout>
  );
}
