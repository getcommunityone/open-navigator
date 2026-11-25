/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      keyframes: {
        plateIn: {
          from: {
            opacity: '0',
            transform: 'translateY(-18px) rotate(-2deg) scale(0.9)',
          },
          to: {
            opacity: '1',
            transform: 'translateY(0) rotate(0deg) scale(1)',
          },
        },
      },
      animation: {
        plateIn: 'plateIn 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) both',
      },
      // One type system site-wide (#975): Playfair Display headings, Source Sans 3 body, IBM Plex Mono labels.
      fontFamily: {
        sans: ['"Source Sans 3"', 'system-ui', '-apple-system', 'Segoe UI', 'Helvetica', 'Arial', 'sans-serif'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // The brand teal of the logo, the home page and the data stories (#975); was a dark slate.
        primary: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          500: '#0d9488',
          600: '#0f766e',
          700: '#115e59',
        },
        sky: {
          50: '#e8eaeb',
          100: '#c5cace',
          500: '#354F52',
          600: '#2e4346',
          700: '#27383a',
        },
        neutral: {
          600: '#354F52',
          700: '#2e4346',
        },
        slate: {
          500: '#64748B',
          600: '#475569',
          700: '#334155',
        },
      },
    },
  },
  plugins: [],
}
