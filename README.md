# Technical Writing Portfolio

Docs live in `docs/` and publish automatically to GitHub Pages. A daily bot finds new remote writing leads and drafts a pitch for each.

## One-time setup (about 10 minutes)

1. Create a GitHub repo and push this folder to the `main` branch.
2. Copy your IPsec guide into `docs/ipsec-site-to-site-vpn.md`, then add it to `nav` in `mkdocs.yml` and link it from `docs/index.md`.
3. Repo > Settings > Actions > General > Workflow permissions: choose **Read and write permissions**.
4. Repo > Settings > Secrets and variables > Actions > **Variables**: add `PORTFOLIO_URL`, `YOUR_NAME`, `SAMPLE_TITLE`.
5. Push to `main`. After the first deploy, go to Settings > Pages and set the source to the `gh-pages` branch.
6. Actions tab > "Daily job leads" > Run workflow once to test.

## What runs without you

- **Every push to `docs/`:** rebuilds and publishes the site.
- **Every day at 03:00 UTC:** pulls leads from Remotive and We Work Remotely, filters to writing roles, skips ones already seen, and opens a GitHub issue with a drafted pitch per lead. GitHub emails you the issue.

## What stays manual (on purpose)

Sending the pitch. LinkedIn and Upwork prohibit automated messaging and applying, and bots get accounts restricted. The pitch is ready to paste, so each one takes under a minute.
