# MediDiet Mini-Program Prototype

This is a mobile-first browser prototype for the MediDiet three-role WeChat mini-program design.

Chinese usage guide: [README.zh.md](./README.zh.md)

## What It Demonstrates

- Patient role: profile confirmation, intake records, next-meal recommendation, refused result, and human-review wait state.
- Dietitian role: pending review queue, `RecommendationTrace` evidence, and approve/modify/reject actions.
- Catering role: `MenuItem` data quality, availability updates, nutrition values, and lightweight fulfillment status.

## Contract Alignment

The prototype mirrors the recommendation engine contract documented in:

- `../../docs/superpowers/specs/2026-05-15-hospital-diet-agent-recommendation-engine-design.zh.md`
- `../../docs/superpowers/specs/2026-05-17-medidiet-mini-program-frontend-design.zh.md`
- `../../docs/superpowers/plans/2026-05-17-medidiet-mini-program-prototype.zh.md`

Important mapped concepts:

- `PatientProfile`
- `IntakeRecord`
- `MenuItem`
- `MealLabel`
- `RecommendationResult`
- `RecommendationTrace`

## Commands

```bash
npm install
npm run test
npm run build
npm run dev -- --host 127.0.0.1
```

## Boundaries

This prototype does not implement real WeChat Mini Program runtime APIs, HTTP services, image recognition, payment, or production clinical rules. It is intentionally service-free and deterministic so the product flow can be reviewed before implementation hardens.
