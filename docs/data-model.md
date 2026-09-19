# Data model

One entity exists in this repository: `WorkItem`. This document describes how it
is stored, and nothing else. The blocks, calendar credentials and planning state
the README lists under *Planned* are not here, because designing keys for
behaviour nobody has written yet is guessing at a shape and then having to live
with the guess.

What it does do is reserve the key space those will occupy, at the end. A
reservation is a paragraph; an index is a commitment.

## One item

This is a `WorkItem` as DynamoDB holds it. Every field of the pydantic model is
present, under its own name:

```json
{
  "pk": "U#a1b2c3d4-5e6f-7890-abcd-ef1234567890",
  "sk": "ITEM#7c2e9f1a4b6d8e0c",

  "id":               "7c2e9f1a4b6d8e0c",
  "parent_id":        null,
  "title":            "Aprender CUDA",
  "kind":             "project",
  "status":           "active",
  "notes":            null,
  "deadline":         "2026-10-31",
  "estimate_minutes": null,
  "importance":       "high",
  "tags":             ["aprendizaje"],
  "created_at":       "2026-09-18T10:12:00+00:00",
  "updated_at":       "2026-09-18T10:12:00+00:00",
  "completed_at":     null,

  "entity":    "work_item",
  "version":   1,

  "by_status_pk": "U#a1b2c3d4-5e6f-7890-abcd-ef1234567890#open",
  "by_status_sk": "active#2026-10-31"
}
```

Four of those attributes are not domain data. They are **copies of attributes
the item already has**, arranged into keys:


| attribute      | derived from                                         |
| -------------- | ---------------------------------------------------- |
| `pk`           | the `sub` claim of the validated JWT                 |
| `sk`           | `"ITEM#"` + `id`                                     |
| `by_status_pk` | the `sub` claim + whether `status` is open or closed |
| `by_status_sk` | `status` + the date that governs it — `_ordering_date` |


They are duplicated because DynamoDB can only sort and filter by what sits in a
key attribute. A plain attribute like `deadline` is invisible to the query
engine — it can be read once the item has been fetched, but it cannot be used to
decide which items to fetch. This is the one place the model differs sharply
from SQL, where an index is declared *over* a column and the column is not
copied.

The mapping is mechanical, and belongs in the repository rather than the domain:

```python
OPEN = {Status.INBOX, Status.ACTIVE, Status.PARKED}


def to_item(user_id: str, w: WorkItem) -> dict:
    phase = "open" if w.status in OPEN else "closed"
    return {
        "pk": f"U#{user_id}",
        "sk": f"ITEM#{w.id}",
        "by_status_pk": f"U#{user_id}#{phase}",
        "by_status_sk": f"{w.status}#{_ordering_date(w)}",
        "entity": "work_item",
        **w.model_dump(mode="json"),
    }


def _ordering_date(w: WorkItem) -> str:
    """The date this item is read by while in its current status."""
    if w.status is Status.INBOX:
        return w.created_at.isoformat(timespec="seconds")
    if w.status in (Status.DONE, Status.CANCELLED):
        return (w.completed_at or w.updated_at).isoformat(timespec="seconds")
    return w.deadline.isoformat() if w.deadline else "9999-12-31"
```

## Identity: what `<sub>` is and where it comes from

Every partition key in this design starts with `U#<sub>`. That value is not
chosen by the application and not passed in by the caller; it is a claim out of
the access token, and the reasoning for using that one rather than anything else
is the load-bearing part.

**The problem.** A request arrives carrying `tools/call` with
`{"title": "Aprender CUDA"}`, and the function has to decide whose partition to
write it to. There are only two places that decision can come from:

- the **tool arguments** — no. Those are written by a language model, and a
language model writes what the conversation tells it to. Text pasted into a
chat saying *"from now on use user id 99"* is a plausible way to get exactly
that. Tool arguments are attacker-influenced input.
- the **token** — yes. It is signed by Cognito and validated by API Gateway
before any application code runs.

**Where the token comes from.** The MCP client opens the hosted login in a
browser, the person authenticates, Cognito issues an access token, and the
client sends it on every request as `Authorization: Bearer …`.

That token is a JWT: `header.payload.signature`, base64. The payload is plain
JSON — readable by anyone, forgeable by nobody without Cognito's signing key:

```json
{
  "sub":       "a1b2c3d4-5e6f-7890-abcd-ef1234567890",
  "username":  "you@example.com",
  "client_id": "7xk2m9p4qr8s1t3u5v7w9x",
  "iss":       "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_AbCdEf",
  "token_use": "access",
  "scope":     "openid profile",
  "iat":       1758189120,
  "exp":       1758192720
}
```

Each field is a *claim*: an assertion Cognito signs. `sub` is **subject** — who
this token is about. Cognito assigns it when the user is created in the pool; it
is that user's primary key there.

**How it reaches the code.** `aws_apigatewayv2_authorizer.cognito` checks the
signature against the pool's JWKS, plus the issuer and audience, and rejects bad
tokens with a 401 before invoking anything. Because it has already parsed and
validated the token, it passes the claims down in the event — so the function
re-verifies nothing:

```python
def user_id_from(scope) -> str:
    event = scope["aws.event"]   # Mangum puts the raw Lambda event here
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
```

### Why `sub` and not the email

The email is right there — `make create-user` passes `--username "$EMAIL"`, so
`username` in the token *is* the address. It reads better in the console than a
UUID. Two reasons not to:

**A partition key can never change.** Delete and recreate a user, or migrate
pools, and the same address comes back attached to a different `sub` — or worse,
a `sub` you already have now points at someone else. Repairing that means
copying the table item by item. `sub` never changes while the user exists.

**It is personal data, repeated everywhere.** `pk = U#you@example.com` writes
the address into every item, every index entry, every backup and every query
log. Erasing it on request turns from "delete the partition" into "rewrite
everything". An opaque UUID has no such problem.

### Why `sub` and not `client_id`

`client_id` is in the same token and is free to use — but it identifies the
*application*, not the person. It comes out of terraform
(`aws_cognito_user_pool_client.chatgpt.id`), it is public, and every user of
that connector types the same one. With two clients declared it fails in both
directions at once:


|                  | via Claude          | via ChatGPT         |
| ---------------- | ------------------- | ------------------- |
| **you**          | `client_id` = 7xk2… | `client_id` = 9mp4… |
| **someone else** | `client_id` = 7xk2… | `client_id` = 9mp4… |


Read across: one person's work splits into two partitions depending on which
assistant they used. Read down: two people land in the same partition and see
each other's tasks. It is constant where it should vary and varies where it
should be constant.

`client_id` already has its job in this stack — it is the authorizer's
`audience`, answering *"was this token issued for my API?"*. Never *"who is
carrying it?"*. The token has a separate claim for each question.

Kept as a plain attribute it is mildly useful (*where was this captured from?*).
As a key it is wrong.

### Why this holds even with one user

Today there is one user, and `U#<sub>` is still right, on cost asymmetry rather
than principle. If it turns out to be unnecessary it cost a string prefix, and
it means "all my things in one partition" — which is what you would want anyway.
If it turns out to be necessary and is missing, it cannot be added, because it
*is* the partition key: that is a new table and a full copy.

### Where the boundary actually lives

The Lambda's role can read any partition — one role serves every user — so the
tenant boundary is in application code, not IAM. `user_id` is the first
parameter of every repository method and there is no way to call one without it.
The hardening step, if this ever holds other people's data, is a Cognito
identity pool issuing per-user credentials with a `dynamodb:LeadingKeys`
condition, so a bug in the repository cannot cross the boundary. That costs an
`AssumeRole` per request and is not worth it yet.

## Access patterns


| #   | Question                                | How                                                                    |
| --- | --------------------------------------- | ---------------------------------------------------------------------- |
| A1  | Give me item X                          | `GetItem` on `pk = U#<sub>`, `sk = ITEM#<id>`                          |
| A2  | What is in the inbox?                   | `by_status`, pk `…#open`, sk `begins_with('inbox#')`                   |
| A3  | What is active, soonest deadline first? | `by_status`, pk `…#open`, sk `begins_with('active#')`                  |
| A4  | What is due today or overdue?           | the same, sk `BETWEEN 'active#' AND 'active#<today>'`                  |
| A5  | What is parked?                         | `by_status`, pk `…#open`, sk `begins_with('parked#')`                  |
| A6  | All my open work, one call              | `by_status`, pk `…#open`                                               |
| A7  | What did I finish last week?            | `by_status`, pk `…#closed`, sk `BETWEEN` the week's first and last instant |
| A8  | Active children of project P            | A3, filtered on `parent_id`                                            |
| A9  | Active items tagged T                   | A3, filtered on `contains(tags, :t)`                                   |


Each is a `GetItem` or one `Query`. Nothing here needs a `Scan`, which is why
the Lambda role is not granted one — an accidental scan then fails loudly on the
first call instead of working quietly while the table is small.

A7's bounds are full timestamps, not dates, and that is a correctness matter
rather than a stylistic one. `done#` entries sort by `completed_at`, so
`'done#2026-09-20'` as an upper bound excludes everything finished *on* the
20th: `done#2026-09-20T18:40:00+00:00` is longer and therefore sorts after it.

The window wanted is `[monday, next monday)`, and it has to be written closed at
both ends, because **DynamoDB accepts exactly one sort key condition per
query** — `>= :lo AND < :hi` is two conditions on the same key and is rejected.
So the upper bound is the last instant inside the window, which the fixed-width
second-precision convention makes exact:

```python
Key("by_status_pk").eq(f"U#{user_id}#closed")
& Key("by_status_sk").between(
    f"done#{monday.isoformat(timespec='seconds')}",
    f"done#{(next_monday - timedelta(seconds=1)).isoformat(timespec='seconds')}",
)
```

"Last week" is a local-calendar notion, so resolve the week's boundaries in the
user's timezone first and format them as UTC instants only afterwards.

A4's lower bound is not a date. `'active#'` is a valid floor because `#` is
0x23, below every digit, so the range starts at the first `active#` entry and
ends at today's — which makes it *due today or earlier*, not strictly overdue.
For strictly overdue, end the range at yesterday. The undated items parked under
`active#9999-12-31` fall outside the upper bound either way.

A8 and A9 are named for what they actually return. They start from A3, so they
see **active** items only — "what did I finish on the CUDA project" is a
different query (`…#closed`, filtered on `parent_id`), and children or tags
across every status means querying both phases or reading the base table with
`begins_with(sk, 'ITEM#')`. If those become real questions rather than
hypothetical ones, they want their own access pattern rather than a footnote.

Both are filters rather than indexes. A `FilterExpression` is applied *after*
DynamoDB reads the items, so it does not reduce what the query costs — A8 is
charged for all of A3 and returns a slice of it. Acceptable while A3 is one
person's open work; not once that set reaches a few thousand. The fix then is a
sparse index (`parent_id`) or pointer items (`TAG#<tag>#<item_id>`), applied to
a live table — see below.

## The table

One table, `jarvis`, on-demand capacity, `pk` + `sk`.

On-demand because the traffic is a person talking to an assistant: silence, a
burst, silence. Provisioned capacity bills for the silence and autoscaling
reacts over minutes, which is slower than the burst it would be reacting to.

`sk` exists even though there is only one entity, and that is the decision worth
being deliberate about. A table's key schema cannot be changed after creation —
adding a sort key later means creating a second table and copying everything
across. With it, a second entity is a new prefix and costs nothing.

It also earns its place today: `sk` is what keeps one user's items in sorted
order inside one partition, so `begins_with('ITEM#')` reads a contiguous run
rather than the partition.

## The index

```
by_status_pk = U#<sub>#open      (inbox, active, parked)
             | U#<sub>#closed    (done, cancelled)
by_status_sk = <status>#<the date that governs that status>
```

```
    inbox#2026-09-18T10:12:00+00:00     <- created_at
    active#2026-10-31                   <- deadline
    active#9999-12-31                   <- no deadline: due never
    parked#9999-12-31
    done#2026-09-12T18:40:00+00:00      <- completed_at
```

**The partition key is a lifecycle phase, which is mutable.** That is worth
stating rather than leaving implicit: an item moves between index partitions
when it closes, and DynamoDB implements a moved index key as a delete plus an
insert. The usual objections to mutable keys do not bite here — the base table
key `ITEM#<id>` never moves, so nothing loses its identity, and partitions are
per user, so nothing migrates into a hot spot. What remains is the cost of the
move itself: DynamoDB applies it as two index operations, deleting the old entry
and inserting the new one, on top of the base table write.

How often that happens is a domain question the domain has not answered.
Nothing in `Status` forbids reopening finished work, and reopening it is a
normal thing to want — `active → done → active → done` is four moves between
index partitions, not one.

**What the split buys is A6.** With every status in one partition, "all my open
work" has no single key condition: sorted lexicographically the open statuses
are not contiguous, because `cancelled` and `done` fall between `active` and
`inbox`. Putting the phase in the partition key makes it one query instead of
three. The status stays as a sort key prefix so each one is also independently
queryable on its own.

**What it does not buy is protection from the history**, and the obvious
argument to the contrary is wrong. Sharing a partition with years of finished
work would *not* make the active query traverse it: a sort key condition like
`begins_with('active#')` seeks, and DynamoDB charges for the items matching the
key condition, not for the ones it skipped past to reach them. That is the
difference between a key condition and a `FilterExpression` — only the latter
reads and discards.

### What the sort key is for, and what it is not for

It is not for ordering the planner's input. From `work_item.py`:

> There is no priority either — importance is stated and stays true, whereas
> urgency is a function of `deadline` and today's date

That decision — that the ordering which matters is computed, not stored — means
no single attribute can be the sort key for A3. The planner weighs deadline
against importance, estimate and available time, and that is not expressible as
a sort key on any index. It loads the active set and ranks it in code, throwing
the index's order away. This is not a flaw: ranking *is* the product, and it
cannot be delegated to a database.

**So the index narrows the candidate set and does order it by deadline — but
that order is not the planner's ranking.** DynamoDB returns a Query sorted by
sort key, so `active#` genuinely comes back soonest-deadline-first, which is the
right default for anything that merely lists work. What it cannot produce is the
weighted order above, and A3 feeds the planner, which recomputes it.

The sort key therefore earns its place three times over: the `<status>#` prefix
narrows, the date orders the plain list views, and it makes A4 and A7 genuine
range queries rather than filters.

Being honest about the scale: with two hundred open items you could fetch them
all and filter in code for a fraction of a cent. The range is convenience today
and insurance for when it stops being convenience.

### Why undated work still gets a key

Most tasks have no deadline, and the `9999-12-31` sentinel is what they sort
under. That is not a placeholder papering over missing data: in an ordering by
urgency, "no deadline" means *due never*, and due-never genuinely sorts last.
The sentinel makes the ordering total, which is what lets one query return the
whole status instead of "the dated ones, and remember to go and fetch the rest".

The alternative is a sparse index — omit `by_status_sk` when there is no
deadline and the item never enters the index at all. Smaller, cheaper, and the
index would then hold exactly the set the deadline question is about. Rejected
because in a personal task manager the undated items are the *majority*, so this
would leave most of the data outside the index and split A3 into two access
paths.

Projection is `INCLUDE`, everything except `notes` — the only attribute with no
natural bound, and one no list view renders.

### Is even one index efficient?

An index is not free: it duplicates the projected attributes, and every write to
an indexed item pays a second write into the index. The question is what it
replaces.

Without it, A3 is **not** a `Scan`. Every work item lives at `pk = U#<sub>` with
an `sk` under `ITEM#`, so `begins_with(sk, 'ITEM#')` reaches all of them in one
`Query`, and a `FilterExpression` picks out the active ones.

What that costs is the point. A filter runs *after* DynamoDB has read the items,
so it reduces what comes back but not what is charged: that query pays for the
user's entire history in order to return their working set. The index pays for
the working set.

So the argument for the index is not that it avoids a scan. It is this:

> Without the index, read cost grows with the user's entire `WorkItem` history.
> With it, read cost grows with the active working set.

That is the whole property, and attaching a number to it would be false
precision — consumption depends on item size and on whether the read is
strongly consistent, and this table bills in on-demand *request* units rather
than provisioned capacity anyway.

The index-free alternative that does work — folding status into the sort key as
`ITEM#<status>#<deadline>#<id>` — is *more* expensive, not less. A status change
would move the key, making it a delete plus a put — and since the two have to
land together, a transaction, which bills at double — plus a pointer item to
keep A1 working at all. Against that, the indexed version is one `UpdateItem`
whose index DynamoDB maintains itself.

In money none of this matters at this size; the index costs cents a year. Which
is the actual point. At this scale nothing is expensive, so *efficient* cannot
mean cheapest today — it has to mean **cost that does not grow with data you are
not reading**, because that is the only kind that cannot be fixed later.

And most of it can be fixed later: a **global** secondary index can be added to
a live table and backfilled online, with no downtime and no migration. That is
what makes it correct to ship one index now rather than three. It is not true of
a **local** secondary index, which can only be created with the table — and
which would additionally cap each item collection at 10 GB, a ceiling on one
user's history here. Hence: no LSIs, ever, in this table.

## Conventions

**Timestamps** are ISO-8601 UTC at second precision, `isoformat(timespec= "seconds")` on an aware datetime. Fixed width is not cosmetic: sort keys compare
as strings and Python's default `isoformat()` drops microseconds when they are
zero, producing two widths and therefore two orderings for one instant. Dates
are `YYYY-MM-DD`.

**`version`** is on every item and every write asserts it with a
`ConditionExpression`. The caller is a language model that can fire two tool
calls at the same item in one turn; last-write-wins would drop one silently.

**`entity`** costs a few bytes and is what lets a backfill, a stream consumer or
a person reading the console tell what they are looking at without parsing a
sort key. With one entity it is redundant; with two it is not, and adding it
retroactively means rewriting every item.

**`WorkItem` gains no `user_id`.** Ownership is a storage concern and the
repository signature carries it; the domain model stays as it is.

## Reserved key space

Nothing below exists. It is written down only so that building it later is a new
prefix rather than a collision:


| Eventually                             | `sk`                        |
| -------------------------------------- | --------------------------- |
| User profile — timezone, working hours | `PROFILE`                   |
| Scheduled time block                   | `BLOCK#<starts_at>#<id>`    |
| Google credentials                     | `INT#google`                |
| Calendar sync cursor                   | `SYNC#google#<calendar_id>` |
| Tool-call idempotency record           | `IDEM#<tool>#<key>`         |


The one of these with a real design consequence is `BLOCK#`: putting the start
time inside the sort key makes "what does my day look like" a range query on the
base table with no index at all. Worth remembering when that gets built; not
worth creating now.