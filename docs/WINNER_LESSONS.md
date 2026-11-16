# NASA Space Apps winner lessons applied to SWELL

This is a product-design synthesis, not a claim that winning projects used identical implementations.

## Patterns worth learning from

- **2plant / NVS-knot (2024 Galactic Impact):** connect remote sensing and environmental models to a sharply defined decision (field access / planting readiness), and carry uncertainty into the recommendation. SWELL adopts the narrow physical use case and decision-to-verification loop.
- **Resonant Exoplanets (2025 Best Use of Data):** combine detection, machine learning and physics-based validation rather than asking a language model to decide scientific truth. SWELL adopts competing hypotheses and independent validation.
- **SkySense (2025 Best Use of Technology):** turn multi-source environmental data into a user-facing decision and conversational interface. SWELL adopts the guided explanation layer, while keeping measurements and scenario calculations deterministic.
- **QUEÑARIS (2025 Local Impact):** connect environmental observations to a physical intervention pathway. SWELL adopts human-approved stakeholder action contracts and later outcome checks.
- **SpaceGenes+ (2025 Best Science):** a focused, testable scientific question can be more compelling than an over-generalized AI platform. SWELL keeps its central hypothesis narrow: separate moisture-driven radar phase effects from actual clay-related deformation.

## What SWELL should demonstrate to judges

1. NASA data are essential to the scientific result, not decorative context.
2. A real NISAR study region is processed end-to-end with product provenance and quality metadata.
3. The moisture-artifact hypothesis is compared against competing explanations.
4. A physical baseline and independent GNSS measurements are used to validate inference.
5. Predictions are evaluated on dates and regions not used for fitting.
6. The application shows when it cannot reach a conclusion.
7. Stakeholder outputs are actionable drafts, tied to a location, evidence, reviewer and later verification.

## Official references

- NASA Space Apps: https://www.spaceappschallenge.org/
- NASA Space Apps 2025 winners: https://www.spaceappschallenge.org/2025/awards/
- NASA Space Apps 2024 winners: https://www.spaceappschallenge.org/2024/awards/
- NISAR GUNW documentation: https://nisar-docs.asf.alaska.edu/gunw/
- ASF Search: https://search.asf.alaska.edu/

## Important limitations

Public GitHub repositories and project websites do not necessarily expose the complete code or evaluation data used by winning teams. Descriptions of their architectures should not be treated as independently reproduced performance evidence. The lessons above are architectural observations, not claims of causal reasons for winning.
