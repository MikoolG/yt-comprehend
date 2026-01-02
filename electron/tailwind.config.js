/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './src/renderer/index.html',
    './src/renderer/**/*.{js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        'editor-bg': '#1e1e1e',
        'sidebar-bg': '#252526',
        'header-bg': '#323233',
        'border': '#3c3c3c',
        'text-primary': '#cccccc',
        'text-secondary': '#858585',
        'accent': '#0e639c',
        'accent-hover': '#1177bb'
      }
    }
  },
  plugins: []
}
