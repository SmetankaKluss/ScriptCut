/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        editor: {
          bg: '#0b0d0c',
          panel: '#101311',
          surface: '#171a18',
          border: '#2b302d',
          accent: '#71d9b0',
          'accent-hover': '#8ee6c2',
          text: '#f3f5f3',
          'text-muted': '#a6aea8',
          paper: '#f4f4ef',
          'paper-soft': '#e9ebe6',
          ink: '#111411',
          'ink-muted': '#677069',
          danger: '#ff716d',
          success: '#71d9b0',
          warning: '#e7bd63',
          'word-hover': 'rgba(35, 128, 91, 0.10)',
          'word-selected': 'rgba(35, 128, 91, 0.22)',
          'word-deleted': 'rgba(193, 57, 54, 0.14)',
          'word-filler': 'rgba(174, 119, 24, 0.18)',
        },
      },
      fontFamily: {
        mono: ['SFMono-Regular', 'Cascadia Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
