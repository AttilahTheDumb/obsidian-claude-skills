# /remember — Capture a Durable Fact Right Now

Pin a single fact to the memory store immediately, mid-session, rather than waiting for
`/compress` to batch-capture at session end. Use this when the user explicitly says
something worth remembering ("remember that...", "from now on...") or when you notice a
clearly durable fact and want to check it in without losing the thread of the conversation.

## Engine
`VAULT_PATH/System/Scripts/memory.py` — run via Bash as
`python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" <subcommand> ...`

If `Memory/` doesn't exist yet in this vault, run the `init` subcommand first.

## Input
`$ARGUMENTS` — the fact, if given inline (e.g. `/remember prefers terse code reviews`).
If empty, ask the user what to remember.

## Steps

1. **Apply the durability test:** would this still be true and useful in three months?
   - If it's disposable (true only in this session — "I'm stuck on this bug right now"),
     tell the user it doesn't look durable enough to remember, and don't write anything.
     Suggest `/compress` will still log the session itself.
   - If it's true only until a known date/event (a deadline, a trip, a temporary
     constraint), it's `class: expiring` — get or infer the date for `--expires-at`.
   - Otherwise it's `class: durable`.

2. **Classify it:**
   - `subject`: a short kebab-case key for what this fact is *about* (e.g.
     `code-review-style`, `package-manager`, `client-x-compliance`). Facts sharing a
     subject are compared against each other later, so keep this specific enough to be
     meaningful but general enough that restatements of the same fact land on the same
     subject.
   - `scope`: `work`, `personal`, or omit if it's not context-dependent.
   - `confidence`: 0.6–0.9 — lower if this is inferred rather than stated outright, higher
     if the user said it directly and emphatically.

3. **Check for existing related memories** before writing anything new:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" candidates --subject <subject>
   ```
   Read the returned records and decide, using judgment (this step is exactly what
   Consolidate/Reconcile do in `/memory-gc` and `/memory-conflicts` — you're doing it
   inline here for a single fact):
   - **No candidates, or none genuinely related** → insert as new.
   - **A candidate says essentially the same thing** → don't write a duplicate. Tell the
     user it's already remembered (mention the existing content).
   - **A candidate is related but adds new information** (e.g. it's the same subject but
     covers a different aspect) → still insert as new; both stand.
   - **A candidate contradicts the new fact, and which one is current is unambiguous**
     (the new one is clearly a correction, an explicit reversal, or a stated update) →
     supersede the old one.
   - **A candidate contradicts the new fact and it's genuinely unclear which is current**
     → don't guess. File a conflict instead of writing either as authoritative.

4. **Write the outcome:**
   - Insert:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" new \
       --content "<fact text>" --subject <subject> --class <durable|expiring> \
       [--scope <scope>] --confidence <0.0-1.0> [--expires-at <ISO8601>] \
       --source "remember command, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
     ```
   - Supersede:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" supersede \
       --old-id <candidate id> --content "<new fact text>" [--scope <scope>] \
       [--confidence <0.0-1.0>]
     ```
   - Flag conflict:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" flag-conflict \
       --old-id <candidate id> --new-content "<new fact text>" --subject <subject> \
       --reason "<why this is ambiguous>"
     ```
     Tell the user it's queued in `Memory/Conflicts/` for `/memory-conflicts` to resolve,
     and ask if they want to resolve it right now instead.

5. Confirm in one line what happened (inserted / already remembered / superseded old
   memory X / flagged as a conflict) — don't narrate the whole classification process back
   to the user.
