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
          400: '#667eea',
          500: '#764ba2',
          600: '#a855f7',
        },
        accent: {
          400: '#ec4899',
          500: '#a855f7',
        },
        success: {
          500: '#10b981',
          600: '#34d399',
        },
        warning: {
          500: '#f59e0b',
          600: '#fbbf24',
        },
        danger: {
          500: '#ef4444',
          600: '#f87171',
        },
      },
      backgroundImage: {
        'glass-gradient': 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)',
        'purple-gradient': 'linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)',
      },
      backdropBlur: {
        xs: '2px',
        sm: '4px',
        md: '12px',
        lg: '24px',
        xl: '40px',
      },
      fontFamily: {
        sans: ['"SF Pro Display"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
export default config
