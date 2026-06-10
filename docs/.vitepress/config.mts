import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: 'Claude Session Manager',
  description: 'A native Linux home for your Claude Code sessions.',
  lang: 'en-US',
  base: '/claude-session-manager/',
  lastUpdated: true,
  cleanUrls: true,

  head: [
    ['meta', { name: 'theme-color', content: '#D97757' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'Claude Session Manager' }],
    ['meta', {
      property: 'og:image',
      content: 'https://raw.githubusercontent.com/r4nd3l/claude-session-manager/main/data/banner.png',
    }],
  ],

  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Guide', link: '/guide/introduction' },
      { text: 'Releases', link: 'https://github.com/r4nd3l/claude-session-manager/releases' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Introduction',
          items: [
            { text: 'What is Claude Session Manager?', link: '/guide/introduction' },
            { text: 'Getting Started', link: '/guide/getting-started' },
          ],
        },
        {
          text: 'Usage',
          items: [
            { text: 'Features', link: '/guide/features' },
            { text: 'Keyboard Shortcuts', link: '/guide/keyboard-shortcuts' },
            { text: 'How It Works', link: '/guide/how-it-works' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/r4nd3l/claude-session-manager' },
    ],

    editLink: {
      pattern: 'https://github.com/r4nd3l/claude-session-manager/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Unofficial community tool — not affiliated with or endorsed by Anthropic. Released under GPL-3.0.',
      copyright: 'Copyright © 2026 Máté Molnár',
    },

    search: { provider: 'local' },
  },
})
