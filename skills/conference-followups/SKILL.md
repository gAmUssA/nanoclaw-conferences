---
name: conference-followups
description: >
  Prepare post-conference follow-ups from an owner's free-text people list or
  voice transcript. Resolve contacts, humanize one email per person, show
  complete drafts with Send/Cancel/Edit choices, and offer explicitly requested
  calendar holds. Use for "follow up with people I met", "conference contacts",
  or a post-event list of names and conversation notes.
---

# Conference Follow-ups

Process steps in order. Do not skip ahead.

## Step 1 — Ground the intake

- Use the actual owner's main-chat text or supplied voice transcript.
- Resolve one exact conference occurrence from that intake and owner context; preserve message identities and exact source quotes.
- Extract people and conversation notes by meaning.
- Do not infer an unheard transcript, invented email, conversation or meeting agreement.
- Clarify missing event or ambiguous people.
- Read `references/intake.md`, then validate the extracted schema-1 input:

```bash
python3 /home/node/.claude/skills/tessl__conference-followups/scripts/prepare-intake.py < /tmp/conference-intake.json
```

- Require successful output before drafting.
- Proceed immediately to Step 2.

## Step 2 — Resolve the contacts

- Use an explicitly provided address first.
- For a missing address, invoke `Skill(skill: "tessl__ask-my-data")` for sanitized earlier mail evidence, or read the event's actual Sessionize speaker profile.
- Preserve source ids/links and explain ambiguous matches to the owner.
- Never derive an address from a name, employer domain or another person's profile.
- Unresolved people remain unsent; continue resolved people without fabricating missing contacts.
- Proceed immediately to Step 3.

## Step 3 — Humanize the drafts

- Draft one concise plain-text email per resolved person naming the event and their actual conversation.
- Include no promised meeting, attachment or other effect absent from intake.
- Invoke `Skill(skill: "tessl__blog-writer")` on its scoped humanization route before presenting any draft.
- Preserve language and the complete draft.
- Write the schema-1 builder input described in `scripts/build-card.py` to `/tmp/conference-drafts.json`, then invoke:

```bash
python3 /home/node/.claude/skills/tessl__conference-followups/scripts/build-card.py < /tmp/conference-drafts.json
```

- Remove both temporary inputs after use, including on failure.
- They contain private contact and conversation text.
- Proceed immediately to Step 4.

## Step 4 — Present the held choices

- Read `references/callback-contract.md` in full.
- Send each builder-produced literal `text` with its complete `buttons` through `mcp__nanoclaw__send_message` in main, without sender override.
- Preserve each actual delivery receipt.
- All refers only to that card; never imply approval of unseen pages.
- The host privately holds these drafts and alone releases the selected mail after an actual configured-owner claim.
- Do not invoke a direct Gmail writer, manufacture an approval field, remove refused buttons or weaken ASK policies.

- An explicit pre-send refusal leaves the batch unsent: report the missing published consumer or dedicated gateway route.
- An uncertain card delivery requires inspection of its original message before any resend.
- Proceed immediately to Step 5 when a real owner decision arrives; otherwise finish here with the drafts held.

## Step 5 — Resolve the outcome

- Use the actual host-bound decision and mirrored card result.
- Send/Cancel are handled by the private host consumer; do not repeat a send from chat text.
- For Edit, use the exact selected original draft and owner's correction, then return to Step 3 for new complete content and fresh approval.
- For an ordinary typed edit/cancel, establish its exact original card/items and actual owner identity; do not simulate a callback or promise cancellation before the host confirms it.
- Report unsupported typed effect routing and leave it held.

- Describe success only from confirmed host/provider state.
- A pending, interrupted or uncertain send is not resent, even under a new batch id.
- Consult the host's contacted log before claiming a new round; never replace that authority with an agent-written contact ledger.
- Proceed immediately to Step 6.

## Step 6 — Offer calendar holds

- If the intake actually agreed a meeting, offer a separate finite owner choice using `owner.answer.v1`, under the installed owner-answer contract.
- Resolve timezone, exact time, duration and attendees before proposing a hold.
- Only an explicit actual owner request permits `google-calendar-write.py insert` under `Skill(skill: "tessl__admin-contracts")` and its Google main-write workflow.
- Preserve its stable request id and confirmed event receipt; `sendUpdates=none` does not prove an invitation.
- No agreement or no exact requested time means no calendar write.
- Finish here.
