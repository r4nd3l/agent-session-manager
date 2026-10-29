import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: 'Agent Session Manager',
  description: 'A native Linux terminal workspace for your AI coding agents.',
  lang: 'en-US',
  base: '/agent-session-manager/',
  lastUpdated: true,
  cleanUrls: true,

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/agent-session-manager/favicon.svg' }],
    ['meta', { name: 'theme-color', content: '#cba6f7' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'Agent Session Manager' }],
    ['meta', {
      property: 'og:image',
      content: 'https://raw.githubusercontent.com/r4nd3l/agent-session-manager/main/data/banner.png',
    }],
  ],

  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Guide', link: '/guide/introduction' },
      { text: 'Releases & Roadmap', link: '/releases' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Introduction',
          items: [
            { text: 'What is Agent Session Manager?', link: '/guide/introduction' },
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
      { icon: 'github', link: 'https://github.com/r4nd3l/agent-session-manager' },
    ],

    editLink: {
      pattern: 'https://github.com/r4nd3l/agent-session-manager/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Unofficial community tool — not affiliated with or endorsed by Anthropic. Released under GPL-3.0.',
      copyright: 'Copyright © 2026 Máté Molnár',
    },

    search: { provider: 'local' },
  },
})
