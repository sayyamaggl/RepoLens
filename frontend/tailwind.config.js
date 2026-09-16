/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        neon: {
          cyan: '#00f5ff',
          violet: '#8b5cf6',
          emerald: '#10b981',
          pink: '#f472b6',
          amber: '#f59e0b',
        },
        dark: {
          900: '#0a0a0f',
          800: '#0f0f1a',
          700: '#1a1a2e',
          600: '#252540',
          500: '#2d2d4a',
          400: '#3a3a5c',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite alternate',
        'float': 'float 6s ease-in-out infinite',
        'slide-up': 'slide-up 0.5s ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
        'fade-in': 'fade-in 0.4s ease-out',
        'scan-line': 'scan-line 4s linear infinite',
        'border-glow': 'border-glow 3s ease-in-out infinite alternate',
      },
      keyframes: {
        'glow-pulse': {
          '0%': { boxShadow: '0 0 20px rgba(0, 245, 255, 0.15)' },
          '100%': { boxShadow: '0 0 40px rgba(0, 245, 255, 0.3)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%': { opacity: '0', transform: 'translateX(30px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        'border-glow': {
          '0%': { borderColor: 'rgba(0, 245, 255, 0.2)' },
          '100%': { borderColor: 'rgba(139, 92, 246, 0.4)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}