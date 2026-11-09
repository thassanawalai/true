# Phase C — implementation-based diagrams

Scope: React/Vite → FastAPI → PostgreSQL, local JSON KB and optional Gemini. Based on main.py,
routers/{demo_auth,customer_data,customer_chat,chat_rooms,tickets}.py and services/{support_answers,knowledge_base,gemini_support,temporary_chat}.py.
No vector/semantic search, live SIEM ingestion, automated response or production authentication is claimed.

## System Architecture

```mermaid
flowchart LR
    C[Customer browser] --> V[Vite /api proxy]
    S[SOC browser] --> V
    V --> F[FastAPI signed demo session]
    F --> A[Company and room-owner authorization]
    A --> P[(PostgreSQL: users / tenant telemetry / tickets / linked chat)]
    A --> K[Local JSON: authorize before keyword ranking]
    A --> R[Temporary chat RAM: one worker]
    P --> E[Local evidence]
    K --> E
    K --> W[Exact public-content digest allowlist]
    P --> T[Verified synthetic telemetry whitelist]
    W --> G[Optional Gemini: bounded request / no tools]
    T --> G
    G --> O[Text validation / fallback]
    E --> O
    O --> F
```

Question text is processed locally; only fixed topic enums, bounded history topic projections,
approved public KB text and whitelisted synthetic telemetry go to Gemini. In the browser evaluation,
Gemini is disabled and Thai deterministic fallback is displayed. Private KB is local-only.

## Use Case Diagram

```mermaid
flowchart LR
    Customer([CUSTOMER]) --> Login([Select mock identity])
    Staff([SUPPORT / ADMIN]) --> Login
    Customer --> Ask([Ask in own private chat])
    Customer --> Data([Read own-company telemetry])
    Customer --> Cite([Read authorized KB and citations])
    Customer --> Confirm([Confirm ticket creation])
    Customer --> Tickets([Read own-company ticket metadata])
    Customer --> History([Read own linked chat])
    Staff --> Select([Select customer company for Q&A])
    Staff --> Reply([Read / reply to customer chat])
    Staff --> Manage([Assign / update ticket])
    Ask -. includes .-> Cite
    Confirm -. saves .-> History
```

Mock user selection is not identity assurance. Internal staff may see all chat rooms or filter them;
company Q&A requires explicit selection. Same-company customers share ticket metadata, not transcripts.

## Sequence Diagram — customer chat

```mermaid
sequenceDiagram
    actor C as Customer
    participant UI as React
    participant API as FastAPI
    participant DB as PostgreSQL
    participant KB as JSON KB
    participant AI as Optional Gemini
    C->>UI: Send question
    UI->>API: Bearer session + room ID + content
    API->>DB: Resolve signed user; check owner/company
    alt Unauthorized
        API-->>UI: 401 / 403 / 404
    else Authorized
        API->>DB: Company-filtered assets/collectors/logs
        API->>KB: Filter scope before ranking; top 2 keyword matches
        KB-->>API: Authorized documents and sources
        alt AI enabled and configured
            API->>AI: Approved public KB + fixed topics + verified mock data
            AI-->>API: Plain Thai advice or failure
        end
        API->>API: Validate output; local citations; Thai fallback if needed
        API->>API: Append to temporary RAM or existing linked room
        API-->>UI: Messages including source links
    end
    C->>UI: Explicitly confirm ticket
    UI->>API: Subject + room ID
    API->>DB: Atomic ticket / room / messages transaction
    API-->>UI: Durable ticket-linked history
```

## Activity Diagram

```mermaid
flowchart TD
    Start([Question]) --> Auth{Session / owner / company allowed?}
    Auth -- No --> Deny[Reject before retrieval or provider]
    Auth -- Yes --> Filter[Filter JSON scope and tenant SQL]
    Filter --> Rank[Score authorized keyword/tag matches]
    Rank --> Match{Positive matches?}
    Match -- Yes --> KB[Render top 2 documents and real sources]
    Match -- No --> Missing[State insufficient evidence; empty citations]
    KB --> Config{Gemini configured and enabled?}
    Missing --> Config
    Config -- No --> Fallback[Thai local answer]
    Config -- Yes --> Project[Project allowed public and synthetic context]
    Project --> Valid{Provider output valid?}
    Valid -- No --> Fallback
    Valid -- Yes --> Advice[Label general Gemini advice separately]
    Advice --> Store{Already ticket-linked?}
    Fallback --> Store
    Store -- No --> RAM[Temporary RAM; idle TTL 30 minutes]
    Store -- Yes --> Durable[Persist messages in PostgreSQL]
    RAM --> End([Display answer])
    Durable --> End
```

No-match can still receive general advice if the provider is enabled; the local no-match disclaimer
remains and no KB citation is invented. Validation is structural, not proof of factual accuracy.
