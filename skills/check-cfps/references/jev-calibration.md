# Initial calibration — 2026-10-20

The operator's `cfp-labeling-2026-10-16.json` supplies 17 non-geographic
yes/no labels: ten yes and seven no. Geo-excluded, unlabelled and
`unknown_to_baruch` rows were excluded. Jev 1.13.0 evaluated the current
speaker profile, relevance criteria and conference metadata. Website
descriptions came from the bounded fetcher; two pages required the 256 KiB
preview limit. No state decisions were changed during calibration.

The initial 0.80 open threshold admitted a labelled negative, DevFest
Nantes. Its fit overlapped labelled positives: 0.83 in the initial run,
0.81 after enabling descriptions from large-page previews. That overlap
does not support automatic decisions near 0.80.

The selected route uses fit >=0.85 for `core`/`adjacent` automatic opens,
fit <=0.35 for automatic dismissals, and Choice confidence >=0.80 for
`off_topic`/`not_dev` automatic dismissals. `unknown`, intermediate scores,
service failures and invalid answers go to Sonnet 5.5 or newer.

The final evaluation refreshed Sessionize metadata through the current
normalizer before fetching website descriptions. These rules automatically
keep FOSDEM (fit 0.90), dismiss NDC Security (fit 0.25), and route fifteen
to Sonnet. Both automatic decisions match the operator's labels. One
fallback was an off-contract Choice distribution rejected by the vendored
client. In an earlier pass, Dev Days Students Madrid was also correctly
dismissed; the final pass routed its invalid answer to Sonnet.

This small set selected conservative routing boundaries; it is not an
independent accuracy estimate. Retain the middle band until a larger
labelled evaluation supports narrowing it. Re-evaluate when the model,
questions, profile or metadata projection changes.
