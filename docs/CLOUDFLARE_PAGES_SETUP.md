# Cloudflare Pages setup

## Dashboard connection (easiest)

1. Open Cloudflare dashboard and click **Workers & Pages → Create → Pages → Connect to Git**.
2. Authorize GitHub and select this repository.
3. Set **Root directory** to `web`, **Build command** to `npm run build`, and
   **Build output directory** to `dist`.
4. For the first deployment, add only `VITE_SUPABASE_URL`,
   `VITE_SUPABASE_ANON_KEY`, and optionally `VITE_TELEGRAM_CHANNEL_URL`.
   Do **not** wait for `VITE_PUBLIC_WEBSITE_URL`; you do not have that URL yet.
5. Click **Save and Deploy**. Cloudflare will create and display a free address such as
   `https://your-project.pages.dev`. No custom domain is required.
6. Copy that new production URL.
7. In Cloudflare Pages open **Settings → Environment variables** and add
   `VITE_PUBLIC_WEBSITE_URL` with the copied URL.
8. In GitHub open **Settings → Secrets and variables → Actions → Variables** and add
   `PUBLIC_WEBSITE_URL` with the same copied URL.
9. Click **Deployments → Retry deployment**, or run the GitHub website workflow again.

This two-deployment bootstrap is normal: the first deployment creates the URL; the
second deployment uses it for canonical sitemap links and Telegram website buttons.

Never add `SUPABASE_SERVICE_ROLE_KEY` to Cloudflare Pages. The SPA uses Supabase anon
access plus RLS. For deep links, add a Cloudflare Pages SPA fallback if your Pages
project does not automatically serve `index.html` for routes.

The alternative `.github/workflows/web.yml` deployment needs a scoped Cloudflare API
token with Pages edit permission and the account ID. Tests and the build run before deploy.
