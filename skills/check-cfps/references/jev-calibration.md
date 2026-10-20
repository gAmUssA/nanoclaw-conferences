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

The selected route uses fit >=0.85 and combined `core`/`adjacent`
probability >=0.80 for automatic opens. Fit <=0.35 or combined
`off_topic`/`not_dev` probability >=0.80 permits automatic dismissal.
A tied maximum or an `unknown` maximum goes to Sonnet first. Provider
labels and confidence do not decide the route. Intermediate scores,
service failures and invalid distributions also go to Sonnet 5.5 or newer.

The final evaluation refreshed Sessionize metadata through the current
normalizer before fetching website descriptions and recorded each full
distribution. These rules automatically keep FOSDEM (fit 0.89, relevant
probability 0.89) and DevFest Berlin (fit 0.85, relevant probability 0.95),
dismiss Dev Days Students Madrid (off-topic probability 0.89), and route
fourteen to Sonnet. All three automatic decisions match the operator's
labels. Every response in this final pass supplied a usable distribution.

This small set selected conservative routing boundaries; it is not an
independent accuracy estimate. Retain the middle band until a larger
labelled evaluation supports narrowing it. Re-evaluate when the model,
questions, profile or metadata projection changes.
