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
        black: '#0a0a0a',
        primary: {
          400: '#22d3ee',
          500: '#00d4ff',
          600: '#00ffff',
        },
        accent: {
          400: '#f472b6',
          500: '#ff00ff',
          600: '#ff00ff',
        },
        success: {
          500: '#00ff88',
          600: '#00ff88',
        },
        warning: {
          500: '#ffaa00',
          600: '#ffaa00',
        },
        danger: {
          500: '#ff0055',
          600: '#ff0055',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Arial', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', '"SF Mono"', 'Monaco', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 10px rgba(0, 212, 255, 0.5)',
        'glow-magenta': '0 0 10px rgba(255, 0, 255, 0.5)',
        'glow-green': '0 0 8px rgba(0, 255, 136, 0.4)',
        'glow-red': '0 0 8px rgba(255, 0, 85, 0.4)',
      },
    },
  },
  plugins: [],
}
export default config
