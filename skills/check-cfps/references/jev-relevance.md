# Tier 3 relevance gate

After the geo gate and Tiers 1–2, pipe the remaining candidate objects to:

```bash
python3 /home/node/.claude/skills/tessl__check-cfps/scripts/relevance-gate.py
```

Each object needs `slug`. Include available `name`, `description`, `tags`,
`city`, `country`, `is_online`, `website`, `cfp_url`, `organizer`,
`is_user_group`, `source`, `status`, `bot_notes`, and `user_actioned`.
Attach Sessionize's verified event metadata from Step 5 in memory; do not
invent descriptions or tags. The helper reads the speaker profile from
`/workspace/trusted/user_professional.md` and the operator's criteria from
`/workspace/group/RELEVANCE-CRITERIA.md`.

Use each parallel result's `slug`, `verdict`, and `reason` as Step 6 directs.
For a model case, pass its `evidence` to Sonnet, including the fetched description.
`metadata_warning` names missing website evidence; it is not evidence that
a conference is irrelevant. A `model` result goes to Sonnet 5.5 or newer.
Service errors, malformed answers and unknown audiences take that route.
Read the helper docstring for the exit and probability contracts.
The initial threshold evaluation and limits are in `jev-calibration.md`.

The helper uses Jev 1.13.0 and asks an independent fit Noul and audience
Choice in one request per candidate. Four workers process the full cohort.
Website requests use only public HTTP(S), pin public DNS results, follow
at most three redirects, read a 256 KiB preview, and have a 15-second wall
deadline. Only description and Open Graph description meta tags enter the
state. A page failure leaves the other metadata available.

Scores and metadata stay in the run artifact. Persist only the existing
`status` and `bot_notes` fields. The CFP record schema remains version 1;
the morning brief continues consuming that schema. The helper preserves
user actions and geo-dismissed rows without network requests. It never
changes Tier 1 approval or Tier 2 blocking.

Before changing the pinned model, questions or routing thresholds, rerun
calibration on the operator's yes/no labels. Exclude `geo_excluded` and
`unknown_to_baruch` rows. Record the evaluated model, metadata availability,
automatic errors and model fallback count; a small calibration set does
not establish accuracy on future conferences.
