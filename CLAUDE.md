# Closer AI Website — Project Context for Claude

## What This Is

Static marketing/legal site for [getcloserai.com](https://getcloserai.com), deployed to Vercel. Waitlist landing page, legal docs, and the SB 243 safety page for the [closer-ai-mobile](../closer-ai-mobile) app (a separate repo — see that repo's `CLAUDE.md` for the app itself). No build step: plain HTML/CSS/JS served directly.

## Key Files

- `index.html` — landing page + waitlist form (Formspree)
- `privacy.html`, `terms.html` — legal docs served at root
- `safety.html` — SB 243 crisis-response protocol page. **Content here is gated on the crisis-referral counter shipping in the mobile app** (mobile `docs/legal/crisis-response-protocol.md`) — every claim on this page must stay factually true against what the app actually does. Don't edit without checking the mobile repo's current state.
- `support.html` — support contact page
- `legal/data-usage-policy.html` — data usage policy (note: the app links to `/legal/privacy-policy` and `/legal/terms-of-service`, which do not exist as files — `vercel.json` redirects those paths to `/privacy` and `/terms` at root. This split is **intentional** — see "Legal URL Convention" below — don't "fix" the app's `/legal/` links or add real files at those paths.)
- `.well-known/apple-app-site-association` — iOS universal links config
- `auth/callback.html` — deep-link landing page for auth redirects back into the app
- `analytics.js` — PostHog site analytics, reverse-proxied via `/ingest` (see `vercel.json` rewrites) so requests survive ad-blockers. Cookie-based persistence (changed 2026-09-16 from `memory` — this is a multi-page static site, so `memory` persistence minted a new visitor identity on every navigation). Waitlist email input is masked (`ph-no-capture`) so session replays never contain an email address.
- `vercel.json` — headers (CSP, HSTS, etc.), the `/legal/*` → root redirects, and the PostHog `/ingest` proxy rewrites
- `scripts/check-links.py` — link checker, two passes: `internal` (filesystem + vercel.json redirects, no network, blocking) and `external` (network, advisory). Run after moving/renaming any page or anchor. Exists because of a shipped CTA that 404'd (PR #8).
- `.github/workflows/links.yml` — runs the link checker in CI

## Legal URL Convention

The app advertises all three legal docs under `/legal/` paths (e.g. `/legal/privacy-policy`), but this site serves the actual content at root (`/privacy`, `/terms`). `vercel.json`'s `redirects` bridge the two on purpose (web PR #7). **Do not "fix" the app's `/legal/` URLs to match the site's root paths** — the redirect is the intended fix; changing either side without the other breaks the link.

## Analytics

PostHog, same project as the mobile app (distinguishable by `$lib`), US cloud. Reverse-proxied through `/ingest` — if analytics events stop landing, check the `vercel.json` rewrite targets before assuming a PostHog outage.

## Safety Page — Handle With Care

`safety.html` publishes the SB 243 crisis-response protocol and is a regulatory-facing page. Its claims (referral routing, crisis hotline numbers, what counts as a reportable figure) must match what the mobile app's `ai-chat` safety classifier and referral counter actually do — see mobile `docs/legal/crisis-response-protocol.md` and mobile memory on the SB 243 referral counter. If you're touching this page, verify against the mobile repo's current state rather than assuming past claims still hold.

## Deploy

Vercel, deployed from this repo directly (no separate build). No `package.json` — nothing to install.

## Maintaining This File

Keep this short — it's a static site, not the mobile app. Inline what an agent needs to avoid breaking the `/legal/` redirect bridge, the safety-page accuracy requirement, or the analytics proxy. Anything longer than a few lines of rationale belongs in `docs/` (create it if a doc doesn't yet exist) with a link here, following the same convention as `closer-ai-mobile/CLAUDE.md`.

`AGENTS.md` in this repo is a stub pointing here — do not re-fork it.
