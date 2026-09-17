# Commons / Human Network design

A new standalone public landing page, September 2026.

## Direction

Near-black space, ice-blue light, oversized editorial typography and a procedural 3D-projected network. The visual is a concept, not a claim about live nodes. Native Canvas, CSS and inline SVG; no front-end framework, external font request, analytics or rendering CDN.

## Interaction

The network can be rotated with a mouse, expanded, and paused. Animation respects prefers-reduced-motion and stops when hidden or outside the viewport. A clearly labeled local simulation demonstrates participant permission followed by an organizer action; it never invokes a training API. Download tabs expose actual release assets with keyboard controls. EN/RU copy, semantic disclosures and a no-JavaScript download fallback are included.

## Content and operational boundaries

The v0.2.0 CPU pilot is still 65 parameters, 32 participants per round and 256 registrations. No change to training, private keys, enrollment or operator policy. Current release assets were not rebuilt. Coordinator telemetry remains read-only and same-origin; the GitHub Pages website displays no invented live counts.

## Source and checks

Canonical page: src/web/landing.html. Copies: docs/index.html and site/index.html, synchronized with scripts/sync_site.py. The social preview is a screenshot of the rendered design, not an AI-model result. scripts/site_acceptance.py tests layouts in English and Russian at 320, 375, 390, 768, 1024, 1440 and 1920 pixels, animation controls, consent simulation, six download links, keyboard navigation, no-JavaScript fallback and mocked coordinator states. API fixtures are not evidence of a live distributed training test.
