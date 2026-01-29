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
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        accent: {
          pink: '#ec4899',
          cyan: '#06b6d4',
          yellow: '#fbbf24',
        },
        success: { 500: '#10b981' },
        warning: { 500: '#f59e0b' },
        danger: { 500: '#ef4444' },
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%)',
        'gradient-accent': 'linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%)',
        'gradient-dark': 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%)',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
export default config
