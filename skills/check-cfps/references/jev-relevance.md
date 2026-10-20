# Tier 3 relevance gate

After the geo gate and Tiers 1–2, pipe the remaining candidate objects to:

```bash
TYPESAFE_API_KEY=onecli-managed python3 /home/node/.claude/skills/tessl__check-cfps/scripts/relevance-gate.py
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
The initial evaluation is recorded in `skills/check-cfps/references/jev-calibration.md`.

The command supplies a non-secret OneCLI placeholder through the environment;
the gateway injects the vaulted key. Outside NanoClaw, supply the real key
through the process environment. Do not put it in the NAS project `.env`.
Request and routing contracts live in `skills/check-cfps/scripts/relevance-gate.py`
(docstring, `route` and named constants);
website retrieval bounds live in the `skills/check-cfps/scripts/website_meta.py`
docstring and constants.

Scores and metadata stay in the run artifact. Persist only the existing
`status` and `bot_notes` fields. The CFP record schema remains version 1;
the morning brief continues consuming that schema. The helper preserves
user actions and geo-dismissed rows without network requests. It never
changes Tier 1 approval or Tier 2 blocking.

Before changing the pinned model, questions or routing thresholds, rerun
the helper on candidates from the operator's labelled cohort. Retain the
result artifact with the evaluated model and metadata projection. Summarize
it through the co-shipped evaluator:

```bash
python3 /home/node/.claude/skills/tessl__check-cfps/scripts/summarize-calibration.py
```

Supply a stdin JSON object with `labels` (the labelling artifact's `items`
array) and `scores` (the gate's result array), joined by `slug`. The JSON summary
reports the evaluated and excluded cohort, automatic errors, model fallbacks,
preserved rows and missing metadata. Exit 0 emits a JSON summary; exit 2 means
invalid or incomplete inputs, with a diagnostic on stderr and no summary.
Its complete input/output contract is in
`skills/check-cfps/scripts/summarize-calibration.py`. Record the summary with
the run artifact. A small calibration set does not establish accuracy on
future conferences.
