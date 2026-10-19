# The plain-copy rule

Everything written into Basecamp is read by the client: to-do titles and
descriptions, comments, both Docs, questions on their list, and anything an agent
writes on Joe's behalf. Read this before writing a line there, and run the sweep
below before the line lands.

The reader runs their own business, not software. Assume they read on a phone,
between jobs, on the first pass, with no one to ask.

## The rule

> **Write plainly what happens.** Every title, sentence and bullet is a **complete
> sentence** or the **literal name of a thing on the screen**. Say what the client
> can now do, or what is broken and what will change. No metaphors, idioms, slang,
> analogies, coined labels, clipped fragments, rhythmic pairs, or any word they
> have not seen on the screen or said themselves.
>
> **The test:** read the line aloud to the client on the phone, with no screen in
> front of them. If they would ask "what does that mean?", rewrite it as the plain
> statement of what happens.

## Whose words to use

Two kinds of words are safe: the client's own business words, and the names on
the screens they use (menu items, page titles, button labels, status names).
Everything else is ours and needs replacing with what happens.

**Project word list.** If the repo has `docs/plain-copy-rule.md`, read it too. It
is the project's own version of this rule: the client's business words, the screen
names they know, and the words of ours they have tripped on. Where it is more
specific than this page, it wins. Add to it when the client asks what a word means.

## The faults

**1. An idiom, metaphor or figure of speech.**
- "The warning was hit and miss" → "The warning showed only some of the time."
- "The button needs a new home" → "The button needs a new service behind it."
- "This page is the rules of the road" → "This page explains how the project works."
- "came along for the ride" → "were fixed at the same time."

**2. Our words, not theirs.**
- "The delta works as expected" → "The download of only the new items works."
- "breakdown by channel" → "the same numbers for each place you sell."
- "the sandbox copy" → "the practice copy" (or the name they already use for it).
- "proven end to end" → "tested from start to finish."
- "recomputes" → "works out again."

**3. A fragment with no verb, so they rebuild the sentence.**
- "The plan: the app emails a sign-in link instead." → "The app will email a sign-in link instead."
- "Nothing to open, nothing to drill into." → "You do not have to open anything."

**4. A name we made up that they have not been taught.**
- "the Monday-morning price drops" → "lowering prices on items that have not sold."
- "per-report totals" → "a total for each report."
- Repo ticket ids appear only on the italic `_Ref:_` line at the bottom, never in a sentence.

**5. Pairs, triplets and cadence over precision.**
- "Sort, edit, change status, clearer colours" → "You can sort the items, edit the
  record, change its status, and the colours are clearer."

## How an item is written

- **Title:** one sentence saying what they can now do or what is fixed. "You choose
  which statements a family sees." Not a label.
- **First line:** the outcome. Then how to find it, in the screen's own words. Then
  anything they have to do.
- **Status line** (only while partly done): "Live:" what works today. "Still to do:"
  what is left. Both as sentences.
- **Tense:** Shipped items say what the app does now. Backlog items say what it will do.
- **Length:** as short as it can be. One idea per sentence. Three sentences is usually enough.
  Technical detail stays in the repo.
- **Their words:** when quoting a request, quote it exactly. Never rewrite New requests.
- **Questions:** one plain question with the choices spelled out. "Do you want X: yes or no?"

## The sweep, before anything lands in Basecamp

1. Read the title and every sentence aloud. Any line without a verb gets one, unless
   it is the name of a thing on the screen.
2. Search for our words and replace each with what happens: sandbox, export, delta,
   CSV, sync, API, cluster, backfill, recompute, migration, deploy, lane, gate,
   platform, channel, variant, end to end, tenant, roll out, surface, flag, trigger,
   pass, plus any the project word list names.
3. Search for figures of speech and replace each with the plain statement: door,
   window, land, home, road, ride, wins, hit and miss, heads-up, on the fly, out of
   your way, quietly, finally, straight from, right there.
4. Search for "X, not Y" and lists of three with no verb. Make each a sentence or delete it.
5. Check the tense against the list the item sits on.
6. The client's own words are theirs. Fix nothing in a New request; quote them exactly elsewhere.
