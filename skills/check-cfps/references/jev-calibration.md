# Initial calibration — 2026-10-20

The operator's `cfp-labeling-2026-10-16.json` supplies 17 non-geographic
yes/no labels: ten yes and seven no. Geo-excluded, unlabelled and
`unknown_to_baruch` rows were excluded. The evaluation used the current
speaker profile, relevance criteria and conference metadata, including
bounded website descriptions. No state decisions changed during calibration.

The final evaluation refreshed Sessionize metadata through the current
normalizer before fetching website descriptions and recorded each full
distribution. It automatically kept FOSDEM and DevFest Berlin, dismissed
Dev Days Students Madrid, and routed fourteen to Sonnet. All three automatic
decisions matched the operator's
labels. Every response in this final pass supplied a usable distribution.

The executable routing contract and calibration accounting procedure are
referenced in `skills/check-cfps/references/jev-relevance.md`.

This small set selected conservative routing boundaries; it is not an
independent accuracy estimate. Retain the middle band until a larger
labelled evaluation supports narrowing it. Re-evaluate when the model,
questions, profile or metadata projection changes.
