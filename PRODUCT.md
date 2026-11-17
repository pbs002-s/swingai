# PRODUCT.md

Inferred from `docs/PRD.md` and the conversation on 2026-11-17. Lines marked *(assumed)* were not stated by the user.

## Product
StitchSense (working name): sewing-floor monitoring and analytics for garment factories. Self-hosted per client, hybrid edge + central server. Tracks working time, output vs target (SMV efficiency), machine downtime, needle breaks traced to supplier batch, quality events, and fair performance ranking with human review.

## Users and use scene
- **Supervisors** on the sewing floor, standing, on 10" tablets under bright factory lighting, glancing between work. Need state at a glance and one-tap review.
- **Factory admins / management** at a desk in the floor office, on laptops, scanning many lines and alerts.
- **Quality and maintenance** teams moving between floor and office.
- Bangladesh-style garment floors are the first market *(assumed from the Bangla requirement)*; UI in English and Bangla.

## Surfaces and modes
- Public landing page: **Persuade**. The buyer is a factory owner or operations head deciding whether to run a pilot.
- App (overview, live floor, review queue, needles, performance): **Operate**.

## Tone
Plain, factual, fair to workers. No surveillance language, no hype. Uncertain results are labelled as uncertain.

## Constraints
- Light theme first (bright floor, daytime office); dark theme supported.
- Status must not rely on colour alone (shape or label too).
- Touch targets 44px on supervisor screens.
- No invented customer names, logos, testimonials or statistics on the landing page.
