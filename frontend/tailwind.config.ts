import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          500: '#14b8a6',
          600: '#0d9488',
        },
        accent: {
          500: '#fb7185',
        },
        neutral: {
          50: '#fafafa',
          100: '#f5f5f5',
          200: '#e7e7e7',
          300: '#d4d4d4',
          500: '#737373',
          600: '#525252',
          900: '#171717',
        },
        success: { 500: '#10b981' },
        warning: { 500: '#f59e0b' },
        danger: { 500: '#ef4444' },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Arial', 'sans-serif'],
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
    },
  },
  plugins: [],
}
export default config
