# Diagrams

Every diagram below describes the system **as it is built**, not as it was
planned. Each is followed by the explanation the report needs beside it.

They are written in Mermaid so they live in version control as text, stay
readable in a diff, and can be exported to images for the report and slides
(mermaid.live, or the Mermaid extension in VS Code).

---

## Figure 2.1 — Conceptual framework

*Chapter 2.4. Inputs, processes, outputs.*

```mermaid
flowchart LR
    subgraph INPUT["INPUTS"]
        A1["Academic paper<br/>(PDF)"]
        A2["Researcher's<br/>account"]
        A3["Owner's provider<br/>configuration"]
    end

    subgraph PROCESS["PROCESSES"]
        B1["Text extraction<br/>(pypdf)"]
        B2["Normalisation +<br/>content hashing"]
        B3["Reuse check<br/>(analysis cache)"]
        B4["Grounded generation<br/>3 schema-constrained passes"]
        B5["Schema validation<br/>(Pydantic)"]
        B6["Ownership enforcement<br/>(Postgres RLS)"]
    end

    subgraph OUTPUT["OUTPUTS"]
        C1["Structured summary"]
        C2["Research gaps<br/>with evidence"]
        C3["Literature review"]
        C4["Private research<br/>library"]
        C5["Provenance record"]
    end

    A1 --> B1 --> B2 --> B3
    B3 -->|"already analysed"| B5
    B3 -->|"new document"| B4 --> B5
    A3 --> B4
    B5 --> C1 & C2 & C3
    A2 --> B6 --> C4
    B4 --> C5
```

**Reading it.** The single most important feature is the branch at `B3`. A
document that has been analysed before does not reach the model at all, which
is what makes the same paper cost one analysis rather than one per user. The
second is that `B6` sits on the path to the library and nothing else: the
analysis is shared, the library is not.

---

## Figure 3.1 — System architecture

*Chapter 3.2.*

```mermaid
flowchart TB
    subgraph CLIENT["Browser"]
        UI["Next.js 16 · React 19<br/>Landing · Dashboard · Library · Settings"]
        SBJS["supabase-js<br/>(authentication only)"]
    end

    subgraph VERCEL["Vercel — one project, two services"]
        FE["Next.js service<br/>/"]
        BE["FastAPI service<br/>/api/* and /health"]
    end

    subgraph SUPA["Supabase"]
        AUTH["GoTrue<br/>email+password, Google OAuth"]
        PG[("PostgreSQL<br/>+ Row Level Security")]
    end

    subgraph AI["AI providers"]
        ANT["Anthropic<br/>claude-opus-5"]
        GRQ["Groq<br/>qwen/qwen3.6-27b"]
    end

    UI --> FE
    SBJS -->|"sign in / out"| AUTH
    UI -->|"Bearer access token"| BE
    BE -->|"verify token"| AUTH
    BE -->|"PostgREST, as the USER"| PG
    BE -->|"primary"| ANT
    BE -.->|"fallback, once"| GRQ

    style GRQ stroke-dasharray: 5 5
```

**Reading it.** Two things are deliberate and worth stating in the report.

The browser talks to Supabase **only** to sign in; it never reads or writes
research data. Everything else goes through FastAPI, so validation, grounding
rules and the error vocabulary live in one place.

The backend reaches Postgres **as the signed-in user**, passing that user's own
access token rather than a service key. This is what makes ownership a property
of the database rather than of a `WHERE` clause the application has to
remember. The one exception is the analysis cache, which holds no user data and
is reachable only by the server (see Figure 4.3).

---

## Figure 3.2 — Analysis pipeline

*Chapter 3.5. What happens between an upload and a result.*

```mermaid
sequenceDiagram
    autonumber
    actor R as Researcher
    participant API as FastAPI
    participant C as Analysis cache
    participant P as Provider (primary)
    participant F as Provider (fallback)

    R->>API: POST /api/analyze (PDF + access token)
    API->>API: verify token, check size and PDF signature
    API->>API: extract text (pypdf)
    API->>API: normalise → SHA-256 content hash
    API->>C: entry for (hash, version)?

    alt already analysed
        C-->>API: stored analysis
        API-->>R: result, cache_hit = true, no model called
    else new document
        API->>P: pass 1 — summary
        API->>P: pass 2 — research gaps
        API->>P: pass 3 — literature review
        alt primary fails retryably
            P--xAPI: 429 or transient error
            API->>F: remaining passes (once, if enabled)
            F-->>API: structured output
        end
        API->>API: validate against schema
        API->>C: store (only a complete, valid result)
        API-->>R: result, cache_hit = false, provenance recorded
    end
```

**Reading it.** The three passes are deliberately separate calls rather than
one. Each is constrained to its own schema, so a malformed summary cannot
corrupt the gap analysis, and a failure is attributable to one section.

The `alt` branch is the fallback rule: it fires only for *retryable* failures,
at most once per analysis, and the router stays switched afterwards so one
analysis is never written by two different models.

---

## Figure 3.3 — Provider routing and fallback

*Chapter 3.5.*

```mermaid
stateDiagram-v2
    [*] --> ReadConfig
    ReadConfig: Read owner configuration<br/>primary + enabled set

    ReadConfig --> Refuse: primary is disabled
    Refuse: Configuration error<br/>nothing is called
    Refuse --> [*]

    ReadConfig --> UsePrimary: primary is enabled
    UsePrimary: Call primary provider

    UsePrimary --> Done: success
    UsePrimary --> Fail: NON-retryable failure<br/>(bad key, invalid output)
    UsePrimary --> CheckFallback: RETRYABLE failure<br/>(429, timeout, 5xx)

    CheckFallback --> Fail: other provider disabled<br/>or has no key
    CheckFallback --> UseFallback: other provider available

    UseFallback: Call fallback<br/>(sticky for the rest of the analysis)
    UseFallback --> Done: success
    UseFallback --> Fail: also failed

    Done: Record ACTUAL provider,<br/>model and fallback_used
    Fail: Report the real error<br/>no invented provenance

    Done --> [*]
    Fail --> [*]
```

**Reading it.** Two rules stop this being merely convenient. Falling back only
on retryable failures means a bad API key or an unusable response is not
retried on a second vendor to produce the same error at twice the cost. Staying
switched means the analysis is finished by one model, so the recorded
provenance is true.

---

## Figure 4.1 — Use case diagram

*Chapter 4.2.*

```mermaid
flowchart LR
    V(("Visitor"))
    U(("Researcher<br/>authenticated"))
    O(("Owner"))
    AI["AI provider<br/>(external)"]

    V --- UC1["View landing page"]
    V --- UC2["Create account"]
    V --- UC3["Sign in<br/>email or Google"]

    U --- UC4["Upload a paper"]
    U --- UC5["Read summary,<br/>gaps, review"]
    U --- UC6["Save to library"]
    U --- UC7["Browse My Papers"]
    U --- UC8["Cross-paper<br/>literature review"]
    U --- UC9["Manage account<br/>name, password"]

    O --- UC10["Choose primary<br/>AI provider"]
    O --- UC11["Enable / disable<br/>a provider"]

    O -.->|"is also a"| U

    UC4 --> AI
    UC8 --> AI

    style O fill:#e8f0fd
```

**Reading it.** The owner is a researcher with two extra capabilities, not a
separate kind of user — which is why there is no separate owner login. UC10 and
UC11 are the only actions any other account is refused.

---

## Figure 4.2 — Activity diagram: upload to saved analysis

*Chapter 4.3.*

```mermaid
flowchart TD
    S([Start]) --> A["Researcher selects a PDF"]
    A --> B{"Signed in?"}
    B -->|no| B1["Redirect to sign in"] --> A
    B -->|yes| C{"Under 25 MB<br/>and a real PDF?"}
    C -->|no| C1["Reject with a reason<br/>413 or 422"] --> E([End])
    C -->|yes| D["Extract text"]
    D --> D1{"Text layer<br/>present?"}
    D1 -->|no| D2["Refuse: scanned PDF,<br/>no OCR"] --> E
    D1 -->|yes| F["Normalise and hash"]
    F --> G{"Seen this<br/>document before?"}
    G -->|yes| H["Reuse stored analysis<br/>no model call"]
    G -->|no| I["Three grounded passes"]
    I --> J{"Valid against<br/>the schema?"}
    J -->|no| J1["Discard and report<br/>never partially used"] --> E
    J -->|yes| K["Store in cache"]
    H --> L["Show summary, gaps, review"]
    K --> L
    L --> M{"Save to<br/>library?"}
    M -->|no| E
    M -->|yes| N["Write paper + analysis<br/>owned by this user"]
    N --> E
```

**Reading it.** Three separate refusal paths — oversized file, no text layer,
invalid model output — are shown deliberately. Each fails with its own message
rather than a generic error, and none produces a partial result.

---

## Figure 4.3 — Entity relationship diagram

*Chapter 4.4.*

```mermaid
erDiagram
    AUTH_USERS ||--o{ PAPERS : owns
    AUTH_USERS ||--o{ ANALYSES : owns
    AUTH_USERS ||--o{ LITERATURE_REVIEWS : owns
    AUTH_USERS ||--o| APP_OWNERS : "may be"
    PAPERS ||--o{ ANALYSES : "is analysed by"
    PAPERS ||--o{ CHUNKS : "is split into"
    LITERATURE_REVIEWS ||--|{ LITERATURE_REVIEW_PAPERS : "is built from"
    PAPERS ||--o{ LITERATURE_REVIEW_PAPERS : "contributes to"

    AUTH_USERS {
        uuid id PK
        text email
        jsonb user_metadata
    }
    PAPERS {
        uuid id PK
        uuid user_id FK "DEFAULT auth.uid()"
        text title
        text filename
        int page_count
        int extracted_characters
        text status
    }
    ANALYSES {
        uuid id PK
        uuid paper_id FK
        uuid user_id FK "denormalised owner"
        jsonb summary
        jsonb research_gaps
        jsonb literature_review
        text model_used
        text model_provider
        bool fallback_used
        int processing_time_ms
        bool cache_hit
    }
    LITERATURE_REVIEWS {
        uuid id PK
        uuid user_id FK
        text title
        jsonb content
        int paper_count
    }
    LITERATURE_REVIEW_PAPERS {
        uuid review_id PK_FK
        uuid paper_id PK_FK
        int position
    }
    CHUNKS {
        uuid id PK
        uuid paper_id FK
        vector embedding "scaffolding, unused"
    }
    APP_OWNERS {
        uuid user_id PK_FK
        timestamptz granted_at
    }
    SYSTEM_SETTINGS {
        text key PK
        text value
        uuid updated_by FK
    }
    ANALYSIS_CACHE {
        uuid id PK
        text content_hash UK
        text analysis_version UK
        jsonb summary
        jsonb research_gaps
        jsonb literature_review
        text model_used
        int hit_count
    }
```

**Reading it.** Two features of this diagram carry most of the design.

`ANALYSIS_CACHE` has **no relationship to any user table**, and that is the
privacy guarantee rather than an omission. It is keyed by document content, so
two researchers uploading the same paper share one analysis while their library
records stay entirely separate. Adding a `user_id` here would turn the table
into an answer to "who has read what".

`CHUNKS` exists but is **unused**. It was built for a retrieval pipeline that
was not implemented; the production path reads whole documents. It is shown
here because it is in the schema, and labelled so the report does not imply a
capability the system lacks.

---

## Figure 4.4 — Authorisation layers

*Chapter 4.1, non-functional requirements: security.*

```mermaid
flowchart TB
    REQ["Request from a browser"]

    L1{"Layer 1 — API<br/>valid access token?"}
    L2{"Layer 2 — API<br/>owner-only route?"}
    L3{"Layer 3 — Postgres RLS<br/>user_id = auth.uid()"}

    REQ --> L1
    L1 -->|no| R1["401 — not signed in"]
    L1 -->|yes| L2
    L2 -->|"not the owner"| R2["403 — not yours to change"]
    L2 -->|"allowed"| L3
    L3 -->|"row belongs to<br/>someone else"| R3["404 — indistinguishable<br/>from 'does not exist'"]
    L3 -->|"row is yours"| OK["200 — data returned"]

    style L3 fill:#e8f0fd
```

**Reading it.** Layer 3 is the one that matters, and it is highlighted for that
reason. Layers 1 and 2 are application code and could contain a bug; layer 3 is
enforced by the database on every query, so a forgotten filter returns *nothing*
rather than everything.

The 404 at layer 3 is deliberate. Answering 403 for "exists but is not yours"
would turn the identifier in a URL into a way to confirm which papers other
people hold.
