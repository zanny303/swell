# SWELL — NASA Space Apps submission brief (draft)

**Working title:** SWELL — From Radar Signals to Ground Decisions  
**Core idea:** An evidence-to-action Earth decision twin for moisture-driven ground movement and local environmental interventions.  
**Submission status:** Product prototype and workflow improvements implemented; a real NISAR site proof is still required before claiming validated NASA observations. The [official 2026 Space Apps portal](https://www.spaceappschallenge.org/2026/) states that project submissions close on 15 November at 11:59 PM local time. The supplied project documentation uses the challenge label “Dancing with the SARs”; confirm the exact official challenge title/statement in your registered team page.

## 1. The problem

Satellite radar can reveal subtle surface change, but a displacement or backscatter map does not tell a city, engineer, utility or community what the signal means, how reliable it is, what could happen next, or which action is worth investigating. Radar phase can be influenced by surface moisture, atmosphere/ionosphere, coherence loss, reference choices and viewing geometry. Treating every color on a map as ground movement can create false confidence.

## 2. The SWELL approach

SWELL connects five parts of the decision process:

1. **Observe:** discover NISAR and supporting Earth-observation products for a real location.
2. **Interpret:** separate observed radar products from derived measurements and model inference; inspect quality, coherence, acquisition geometry and moisture context.
3. **Manipulate:** edit physical assumptions and map-based interventions without changing the observation record.
4. **Compare:** run and save alternative scenarios against a common baseline, exposing assumptions and uncertainty.
5. **Decide and verify:** create stakeholder-specific actions and identify the next observation or field measurement needed to test the result.

The product is not a static map dashboard. It is an interactive workspace where evidence, model state, possible futures and human decisions stay connected.

## 3. What is distinctive

- The scientific question is specific: distinguish moisture-driven radar phase effects from actual clay-related surface movement.
- NISAR GUNW phase/coherence and GCOV backscatter are treated as different measurements, not merged into a generic radar layer.
- The existing SWELL shrink–swell model and moisture-artifact correction are retained rather than replaced by a generic AI classifier.
- The user can select a cell, inspect its source values, change scenario assumptions, save alternative branches and compare consequences.
- The copilot uses the active site/role/selected-cell context and can propose model changes, but requires explicit human approval before running them.
- Stakeholder views turn analysis into an investigation/action plan with a verification step.

## 4. NASA/NISAR connection

NISAR's L-band radar provides repeat observations of Earth's changing surface. The mission's exact repeat cycle is 12 days; ascending and descending observations average about six days between looks. Product resolution and posting must be stated correctly for each dataset.

For a ground-motion use case, SWELL should use NISAR GUNW as the primary interferometric product and preserve its phase, coherence, connected components, ionospheric screen and correction metadata. GCOV is useful for backscatter/soil-moisture/inundation context, not displacement. Phase must be converted to LOS displacement with the correct wavelength, sign convention and viewing geometry; vertical movement is an additional assumption. Independent GNSS/leveling or field validation is strongly preferred.

**Evidence status:** the uploaded project archives contain a synthetic test fixture, not a real processed NISAR site. The code includes NISAR discovery and processing paths, but a real granule pair and independent validation have not yet been demonstrated in these archives. Replace this section with the exact site, granule IDs, acquisition dates, product maturity, quality metrics and reference measurements before submitting a claim of real-world results.

## 5. What users can do in the current build

- Open Earth Decision Studio as the main application.
- Connect/discover real data through the Connections workflow.
- Use the existing Local Physical Twin for terrain, water-balance screening and intervention workflows.
- Ask SWELL for evidence explanations and selected-cell interpretation.
- Preview a natural-language scenario and explicitly apply it to the active twin.
- Save and compare scenario branches locally in the browser.
- Export a scenario/decision record for review.

The copilot is evidence-first and deterministic by default; optional local Ollama generation requires separate local configuration. The scenario shelf is browser-local, not shared multi-user approval.

## 6. What is not claimed

- No global real-time digital twin.
- No operational NISAR-derived flood/water product where NASA/JPL marks it under development.
- No calibrated predictive interval until independent validation supports it.
- No building-level engineering assessment from a coarse raster cell.
- No structural safety certificate or geotechnical design.
- No authenticated multi-stakeholder approval in the local scenario shelf.
- No photorealistic 3D coverage where a provider/asset is not actually available.

## 7. Demo story (2–3 minutes)

1. Start on the Earth globe and choose a real study site.
2. Show available NISAR product coverage and the exact product metadata.
3. Open GUNW phase, coherence and quality; explain what is measured and what remains uncertain.
4. Compare the radar signal with moisture/rainfall/soil context and independent reference evidence.
5. Select a zone/cell and ask SWELL to explain the result.
6. Propose a drainage/land-cover/rainfall scenario; review assumptions; explicitly apply it.
7. Save two or three alternatives and compare the outputs against the same baseline.
8. Switch stakeholder role, create an investigation/action note and identify the next measurement.
9. Close by showing how a later NISAR pass or field measurement will verify the earlier forecast.

## 8. Final pre-submission checklist

- [ ] Confirm the exact assigned challenge statement and local event deadline.
- [ ] Process one real NISAR GUNW/GCOV study site; retain granule IDs, HDF5, hashes and metadata.
- [ ] Display product maturity, posting, CRS, orbit/direction, polarization, dates and quality masks.
- [ ] Validate the target signal against GNSS/leveling/field evidence or state the limitation.
- [ ] Ensure synthetic fixtures are never shown as real data.
- [ ] Capture a real browser walkthrough with all live-provider statuses visible.
- [ ] Test the full demo from a clean environment.
- [ ] Include model limitations and no-go cases in the submission.

## 9. Judging strategy

The 2026 local-event pages list Impact, Creativity, Validity, Relevance and Presentation. Make each one visible: a real stakeholder problem, the novel radar-artifact/ground-motion distinction, actual NISAR evidence and QA, direct response to the assigned challenge, and a short demonstration that ends with a human decision and verification step.

## 10. Short pitch

**SWELL turns satellite change detection into a testable human decision.** It connects NISAR radar evidence with soil and weather context, helps people understand which signals are real and which remain uncertain, lets stakeholders manipulate possible interventions, compares alternative futures and records what must be measured next. Instead of ending at a map, SWELL closes the loop from observation to action to verification.

---

**Submission integrity note:** this draft is intentionally conservative. Do not remove the evidence-status warning or replace it with a real-data claim until a real NISAR product and validation record have been processed and checked.
