# Open Navigator - Frontend

React + TypeScript web interface for the Open Navigator application.

## Projects

### Main Application
React + TypeScript web interface with maps, charts, and data visualization.

**Location:** `frontend/` (this directory)

### Policy Accountability Dashboards
Evidence-based accountability dashboards for policy advocacy.

**Location:** `frontend/policy-dashboards/`  
**Documentation:** [Policy Dashboards README](policy-dashboards/README.md)

## Tech Stack

- **React 18.2** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **React Router** - Navigation
- **TanStack Query** - Data fetching
- **Recharts** - Charts
- **Leaflet** - Interactive maps

## Development

```bash
# Install dependencies
npm install

# Run dev server (hot reload)
npm run dev
# Opens http://localhost:3000

# Build for production
npm run build
# Outputs to ../api/static/

# Type check
npm run type-check

# Lint
npm run lint
```

### Console noise

**`🔍 [FETCH]` logs** — Off by default. To enable per-request logging in dev, add to `frontend/.env.local`:

```bash
VITE_DEBUG_API=true
```

**`[Home] Preview state` / location / stats logs** — Off by default. Set `VITE_DEBUG_HOME=true` in `.env.local` to re-enable.

**`background.js` / `addEventListener` on null** and **“message channel closed”** on `batch-jobs:1` — From a **browser extension** (`chrome-extension://…`), not this app. Use an external browser or Incognito with extensions disabled; see `chrome://extensions` to find the extension ID from the Sources panel.

## Project Structure

```
src/
├── components/
│   └── Layout.tsx          # Main layout with sidebar
├── pages/
│   ├── Dashboard.tsx       # Statistics and charts
│   ├── Heatmap.tsx         # Interactive map
│   ├── Documents.tsx       # Document browser
│   ├── Opportunities.tsx   # Opportunity manager
│   └── Settings.tsx        # Configuration
├── App.tsx                 # Root component with routing
├── main.tsx                # Entry point
└── index.css               # Global styles
```

## Pages

### Dashboard (`/`)
- Total documents, opportunities, states monitored
- Topic distribution charts (bar and pie)
- Recent opportunities table

### Heatmap (`/heatmap`)
- Interactive Leaflet map
- Color-coded urgency markers
- State and topic filters
- Popup details

### Documents (`/documents`)
- Searchable document list
- Pagination
- Topic tags
- Source links

### Opportunities (`/opportunities`)
- Filterable by urgency
- Generate advocacy emails
- Talking points display
- Confidence scores

### Settings (`/settings`)
- Target state selection
- Policy topic configuration
- Notification preferences
- Agent status monitoring

## Environment

The frontend proxies API requests to the backend:

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

## Building

Production builds are output to `../api/static/` so the FastAPI backend can serve them:

```typescript
// vite.config.ts
build: {
  outDir: '../api/static',
  emptyOutDir: true,
}
```

## Styling

Uses Tailwind CSS with custom utility classes:

```css
/* index.css */
.card { @apply bg-white rounded-lg shadow-md p-6; }
.btn-primary { @apply bg-primary-600 hover:bg-primary-700 text-white ... }
.btn-secondary { @apply bg-gray-200 hover:bg-gray-300 text-gray-800 ... }
```

## Data Fetching

Uses TanStack Query for server state management:

```typescript
const { data, isLoading } = useQuery({
  queryKey: ['opportunities', state, topic],
  queryFn: async () => {
    const response = await axios.get('/api/opportunities', { params: { state, topic } })
    return response.data
  },
})
```

## Deployment

The built frontend is automatically included when deploying to Databricks Apps:

```bash
# Build frontend
npm run build

# Deploy entire app
cd ..
./scripts/deploy-databricks-app.sh
```

## License

Apache License 2.0 - See LICENSE file for details
