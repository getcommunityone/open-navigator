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
      colors: {
        primary: {
          50: '#e8eaeb',
          100: '#c5cace',
          500: '#354F52',
          600: '#2e4346',
          700: '#27383a',
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
