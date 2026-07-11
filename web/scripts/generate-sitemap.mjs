import {writeFileSync} from 'node:fs'
// Cloudflare supplies CF_PAGES_URL during the first build, before the owner has
// a canonical pages.dev URL to place in VITE_PUBLIC_WEBSITE_URL.
const origin=(process.env.VITE_PUBLIC_WEBSITE_URL||process.env.CF_PAGES_URL||'https://example.invalid').replace(/\/$/,'')
const routes=['/','/notices','/deadlines','/search','/verification-policy','/about','/disclaimer','/privacy','/telegram']
const urls=routes.map(path=>`<url><loc>${origin}${path}</loc></url>`).join('')
writeFileSync(new URL('../public/sitemap.xml',import.meta.url),`<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>\n`)
