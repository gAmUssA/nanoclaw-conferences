# Conference follow-up callback protocol 1

This contract belongs to `jbaruch/nanoclaw-conferences` and the host's
`conference.followup.v1` registry consumer. It authorizes no script to send
mail directly. Use only the configured owner in the single main Telegram chat.

## Proposal and visible content

`skills/conference-followups/scripts/build-card.py` owns the schema-1 proposal and canonical card renderer.
Its docstring declares input/output. Preserve complete recipient, subject and
body on the same literal card as their Send/Cancel/Edit buttons. Do not
truncate a draft or substitute a summary. Paginate into independently approved
cards when the host's limits require it; All always means only that card.

Each payload has exactly `schema_version:1`, `batch_id`, `event_id`,
`event_name`, `source_message_id`, `kind` and `decision`. An item payload also
has `index` and `item`; item has exactly `name`, `to`, `subject`, `body`.
Kind is `item` or `batch`; effect decision is `send` or `cancel`.
`event_id` is the canonical actual conference start date displayed with its
name on the card. A changed batch/request id supplies no new occurrence.
Indices start at 1 and are contiguous. Each item has one effect row containing
Send N and Cancel N in that order. The next row contains Send all and
Cancel all. The final independent answer row contains Edit N for each item,
then Edit all, with two to four choices. Edit buttons use the actual `owner.answer.v1` action
with exactly `{"label":"<same visible label>"}`; this generic consumer returns
the validated owner's reply to the agent with its original question. Send and
Cancel use `conference.followup.v1`. Require the installed owner-answer
authority before enabling these cards. Reject other mixed effects,
missing/duplicate rows, changed labels or different copies of an item.

Validate `batch_id` and the byte-identical visible text against
`skills/conference-followups/scripts/build-card.py`'s `digest` and `card` functions, whose docstrings own
the computed-value and renderer contract. Keep the full digest; its shortened
visible prefix is a reference, never an identity or approval.
Require distinct case-insensitive ASCII
mailboxes (unquoted ASCII dot-atom local part and DNS-label domain), complete
bounded plain text and the builder's measured host limits.

## Private hold and decisions

The existing host-private callback store holds the proposal before delivery.
Arm choices only after actual Telegram delivery is bound to that card. A
proposal, source id, stored pending status or agent JSON field supplies no
approval. Before any effect, revalidate the private running claim, configured
owner, main group/chat, actual message id, original complete text, full callback
rows, payload and expiry. Reject unsupported schemas and mismatches.

The host owns a durable delivery gate keyed by exact conference occurrence
and canonical recipient across cards/batches. Its schema of record belongs
with the host-private callback database migrations; agent-writable files
cannot replace it. Preserve drafts privately and do not expose raw mail or
gateway credentials through its status or callback result.

Send releases only the selected pending items. Serialize each gate and commit
`sending` before the first Gmail POST. Bind a stable RFC Message-ID to its
exact event, recipient, subject and body. A crash, timeout, malformed response
or incomplete confirmation retains the attempt and blocks another POST.
Recover only by exact live Sent confirmation of account, Message-ID,
recipient, subject, body and provider ids. A Gmail receipt or HTTP 200 alone
cannot confirm different content. Record confirmed provider ids in the host
log for deduplication on the next round.

Cancel closes only unreleased items. A sending, sent or uncertain item cannot
be described as cancelled. Edit retires its native answer row and returns the
selected original item identities for new humanization and fresh approval.
Before releasing any item, inspect actual private row decisions: an Edit N
claim fences that original item and Edit all fences every original item,
including when another row's Send all is selected later. An Edit request
never changes approved bytes or sends. Already attempted or contacted
recipients remain gated across new cards. Expired cards never release mail.
Typed edits/cancellations use the ordinary owner workflow; never forge a tap
or write the private callback store from an agent.

## Host execution and gateway

`conference_followup_status` is a main-only read operation for the exact
`event_date`, `event_name` and selected `recipients`. Its schema-1 result
contains the matching occurrence, host `observed_at`, `source: host-log`,
and per-recipient status/confirmation time/provider ids. It returns no draft
or credential and performs no write or provider call. Unknown schemas and
mismatched identities are unusable history, never permission to clear a gate.
The effect handler always rechecks the private gate independently.

On an owner request to check an uncertain delivery, call the main-only native
`conference_followup_reconcile` with the same exact `event_date`, `event_name`
and at most three explicit recipients. It can inspect only existing durable
sending/uncertain attempts. Reuse their original persisted account, Message-ID,
recipient and complete content; never accept replacement bytes from this query.
It performs exact live Sent verification and records only a confirmed receipt.
It never creates a draft, gate or message and never calls POST. Its schema-1
status result adds `reconciliation` counts (`checked`, `confirmed`, `unconfirmed`)
and a nullable bounded `diagnostic` for unavailable live evidence. An absent,
ambiguous, unsupported or failed read remains unconfirmed, with its send gate
closed. Report that result honestly and retry only the readback on owner request.

Resolve `skills/conference-followups/scripts/conference-followup-callback-v1.py`
inside the same installed provider as this declared rule and skill. Require
regular contained realpaths and the provider manifest declaration. Register
only after that actual published provider is installed.

Run with the host-selected Python executable and exactly one argument matching
`^[A-Za-z0-9_-]{22}$`. Inject absolute `NANOCLAW_CALLBACK_HOST_ROOT` from the
trusted registry, absolute `NANOCLAW_CALLBACK_NODE` from the host's actual Node
executable, and fixed main group/chat; never take paths, credentials,
sender ids or executable names from payloads. The adapter selects that real
host cwd, invokes regular contained `dist/conference-followup-callback-cli.js`
once with the exact claim id through the selected Node executable, and validates
the result. The adapter caps child stdout at 2,048 bytes and stderr at 8,192 bytes
while reading, kills the child on excess output, and enforces a 240-second deadline.
That CLI calls `runConferenceFollowupCallbackV1(id)`.

Require stdout to be exactly `{status,text}` with status `applied`, `rejected`,
`stale` or `failed` and text at most 200 Unicode scalars. A handled failed
result remains failed even with exit 0. Invalid input/deployment exits nonzero
with empty stdout and a bounded diagnostic. Do not replay an uncertain claim.

The fixed Gmail first-contact sender runs only in the verified host callback
using the dedicated `nanoclaw-host-conference-followup` OneCLI identity.
Provision that identity through the real existing OneCLI role API with only
the account/profile, exact Sent verification and send operations the consumer
uses. A missing route or incompatible role refuses before POST; it never
falls back to a container identity or enables/weakens unrelated ASK policies.
The host holds this operation before the gateway; no new OneCLI paid service,
API key or upstream hold implementation is required.

Verify lookup and adapter I/O in this provider, and claim, content, expiry,
dedupe, cancellation, restart and provider-confirmation behavior in the host.
Synthetic fixtures grant no account access or live owner approval. Keep live
acceptance open until root verifies installed roles and real owner decisions.
