# TAKELEY — Architecture

**TAKELEY** (테이클리): *Take a look. Take a side.*

Product unit for users: **Issue** (+ Take / follow / update).  
Persistence: table **`issues`** (renamed from `signals`). Legacy `/api/v1/signals*` and internal `Signal*` type aliases may remain for compatibility.

```text
Sources → Worker ingest → Pipeline → DB → API personalization → App
```

## Principles

1. **Common Intelligence First** — never call external APIs or LLMs on each user request.
2. **Issue-centric** — users see Issues, not raw post dumps.
3. **Fact vs interpretation** — Confirmed Fact, Market Interpretation, Opinion, and Rumor stay separated.
4. **Provider isolation** — X is one `SourceProvider`; TAKELEY is not an X product.
5. **Admin publish gate** — pipeline writes **draft**; home shows **published** only after review.

## MVP focus

High-quality daily Issues (~5–10), multi-source when possible.  
Loop: **Discover → Understand → Take → Return**.

## Ingestion / Issue Pipeline pack

Detailed redesign notes (still valid; brand = TAKELEY):

→ **[docs/architecture/README.md](architecture/README.md)**
