# Open Navigator - Documentation Site

This directory contains the **Docusaurus documentation website** for the Open Navigator project.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm start

# Open http://localhost:3000
```

## Available Commands

```bash
npm start              # Start development server (localhost:3000)
npm run build          # Build static site for production
npm run serve          # Serve production build locally
npm run deploy         # Deploy to GitHub Pages
npm run clear          # Clear Docusaurus cache
```

## Documentation Structure

- `docs/` - All documentation markdown files
- `blog/` - Blog posts (optional)
- `src/pages/` - Custom React pages (home, redirect to app)
- `static/` - Static assets (images, files)
- `docusaurus.config.ts` - Site configuration
- `sidebars.ts` - Documentation sidebar structure

## Integration with Main Project

The documentation site is part of the larger Open Navigator project:

- **Documentation**: `http://localhost:3000` (this site)
- **Open Navigator**: React app at `frontend/` (separate Vite app)
- **API**: FastAPI backend at `api/`

The `/dashboard` page in this site redirects users to the React application.

## Deployment

### Local Testing

```bash
npm run build
npm run serve
```

### GitHub Pages

```bash
GIT_USER=<username> npm run deploy
```

### Integration with Main App

The built static site can be served alongside the FastAPI backend for production.

## Resources

- [Docusaurus Docs](https://docusaurus.io/docs)
- [Main Project README](../README.md)
- [GitHub Repository](https://github.com/getcommunityone/open-navigator-for-engagement)

---

Built with [Docusaurus](https://docusaurus.io/) 🦖
