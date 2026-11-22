# 11. AdMob & Monetization Specification

> [!WARNING]
> **NOT YET BUILT**. Archipelago is currently a free institutional tool. This specification exists for future consideration.

## 1. Current Status
**NOT IMPLEMENTED**. Archipelago operates entirely as a free institutional tool at present.

## 2. Potential Monetization Strategies
For future consideration:
- **Institutional Licensing**: Per-university subscription models.
- **Freemium Model**: Basic queries remain free, with advanced personalization available on premium tiers.
- **API Access Tiers**: Providing structured data access for third-party integrations.
- **AdMob Integration**: For non-institutional, public access modes (if applicable).

## 3. AdMob Integration Points (If Pursued)
- **Landing Page**: Banner ads below the hero section.
- **Chat UI**: Sponsored resource recommendations, ensuring they are clearly labeled as sponsored.
- **Library Page**: Publisher-sponsored book highlights.
- **Strictly Prohibited Placements**: NEVER place ads in the diagnostic quiz flow, personalized learning paths, or citation results.

## 4. Constraints
- Must **NOT** interfere with academic integrity.
- Must **NOT** negatively impact page load speeds for students.
- Sponsored content must be clearly distinguished from academic recommendations.
- Must comply with institutional advertising policies.
- Must **NOT** track individual student learning data for targeted advertising.

## 5. Technical Requirements (When Built)
- Integration with the Google AdMob SDK.
- Ad placement configurations managed via environment variables.
- A/B testing framework support for diverse ad placements.
- A revenue tracking dashboard.
- Ad blocking detection paired with graceful degradation.

## 6. Privacy Compliance
- Strict GDPR and local data protection compliance for ad tracking.
- Student data is **NEVER** to be shared with ad networks.
- A straightforward opt-out mechanism for personalized ads.
- An institutional override capability to globally disable all advertising for a tenant.

## 7. Decision
This specification exists solely for completeness. Implementation priority is **LOW**. The core focus remains on delivering and refining primary product functionality.
