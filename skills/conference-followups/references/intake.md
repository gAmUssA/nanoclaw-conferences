# Intake and contact evidence

The owner supplies free text or a voice transcript; the model extracts its
meaning. `prepare-intake.py` validates exact quotes and structural bounds,
not a natural-language grammar. Its JSON contains no approval or send flag.

Use the actual conference start date as canonical `event.id` / `event_id`
in `YYYY-MM-DD` form, with its actual conference name. Keep both stable across
later contact rounds. Resolve the date from actual owner context or event
records; a name reused annually is insufficient. Date interpretation stays
with the model and cited evidence; ask when it is unknown. The event
evidence and each person's quote come from the source text. If needed,
combine the explicitly identified owner context with the new intake before
validation while retaining all original message identities in the working
record. Ask about unknown event/name/conversation evidence instead of filling
it in. A voice transcript's uncertain or spelled address needs confirmation.

Keep unresolved people separate from resolved drafts. Contact lookup does not
authorize sending: earlier mail must come from sanitized `ask-my-data`
evidence, and a Sessionize match requires its actual speaker profile. Reading
a CFP endpoint alone does not prove it exposes a person's email. Never scrape
or guess a private address. Surface multiple plausible matches to the owner
with `owner.answer.v1` choices and a typed-reply alternative.

Builder input is a transient proposal; its batch digest identifies exact
content, not owner identity or permission. The host-private callback database
owns pending choices and its delivery gate owns attempted/contacted dedupe.
Neither parser nor builder reads/writes that private store or calls Google.
