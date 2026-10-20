/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        sidebar: {
          DEFAULT: '#0F172A',
          hover: '#1E293B',
          active: '#334155',
          border: '#1E293B',
          text: '#F8FAFC',
          muted: '#94A3B8',
        },
        brand: {
          primary: '#4F46E5',
          'primary-hover': '#4338CA',
          accent: '#0F766E',
          'accent-hover': '#0d655e',
        },
      },
      borderRadius: {
        'card': '14px',
      },
    },
  },
  plugins: [],
}
