# Phase 118B - Landing Page Link Routing and Footer Navigation Fix

## Outcome

Atlas landing-page navigation now routes visibly and honestly. Existing product sections scroll to real targets, informational footer destinations serve Atlas-branded pages, and unconfigured social destinations show a clear coming-soon toast instead of navigating home or using fake external URLs.

## Routing Contract

| Visible link | Destination |
| --- | --- |
| Product | `#product` |
| Repositories | `#repositories` |
| Features | `#features` |
| Beta | `#beta` |
| FAQ | `#faq` |
| Join Waitlist | `#waitlist` |
| Documentation | `docs.html` |
| Changelog | `changelog.html` |
| Roadmap | `roadmap.html` |
| About | `about.html` |
| Contact | `contact.html` |
| Privacy | `privacy.html` |
| Terms | `terms.html` |
| Security | `security.html` |

The shared marketing script initializes same-page smooth scrolling and updates the URL hash without sending the visitor to the top of the document.

## Social Links

`marketing.js` now defines:

```js
const ATLAS_LINKS = Object.freeze({
  github: "",
  x: "",
  discord: "",
});
```

The landing footer renders GitHub, X, and Discord as explicit buttons. While a URL remains empty, the button shows:

`Coming soon — official Atlas link not configured yet.`

No fake GitHub, X, or Discord URL was introduced.

## Informational Pages

Added:

- `privacy.html`
- `terms.html`
- `security.html`
- `about.html`
- `contact.html`
- `roadmap.html`
- `changelog.html`
- `docs.html`

Each page uses Atlas branding, includes home navigation, and keeps beta/local-first claims narrow. Privacy, Terms, and Security explicitly state that their beta notices are not final legal or certification documents.

## Automated Verification

Passed:

```text
py -3 -m pytest jarvis_desktop/tests/test_phase118b_landing_link_routing.py -q -p no:cacheprovider
8 passed
```

Passed with the sandbox-blocked temp fixture deselected:

```text
py -3 -m pytest jarvis_desktop/tests/test_phase113_marketing.py -q -p no:cacheprovider -k "not static_server_can_serve_marketing"
16 passed, 1 deselected
```

The remaining legacy fixture was separately covered by live HTTP checks because pytest could not inspect its own temporary directory under the restricted Windows sandbox.

Passed:

```text
node --check jarvis_desktop/static/marketing.js
```

Live server sweep:

```text
landing.html   200
privacy.html   200
terms.html     200
security.html  200
about.html     200
contact.html   200
roadmap.html   200
changelog.html 200
docs.html      200
```

## Manual Verification Checklist

The in-app browser route and local Playwright fallback were unavailable in this session. The audit test and live HTTP sweep verified the route contract, but a final physical click pass remains:

- [ ] Click Product
- [ ] Click Repositories
- [ ] Click Features
- [ ] Click Beta
- [ ] Click FAQ
- [ ] Click Join Waitlist
- [ ] Click Privacy
- [ ] Click Terms
- [ ] Click Security
- [ ] Click GitHub, X, and Discord and confirm the coming-soon toast
- [ ] Confirm no visible link incorrectly routes to home

## Scope

This phase touched only Atlas marketing static files, its targeted audit test, and this report. It did not modify desktop repository analysis, Builder Core, browser runtime, voice runtime, trading, or unrelated work in progress.
