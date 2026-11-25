# C4 Model Architecture Diagrams Reference

Use the **C4 Model** (Simon Brown) to visualize software architecture at progressive zoom levels inside `.aidlc/inception/design.md` or `docs/architecture.md`.

By default, render C4 levels using portable **Mermaid `flowchart` and `classDiagram`** blocks (which render natively in Antigravity, GitHub, Cursor, and Obsidian without external plugins). When the user explicitly requests **Structurizr DSL** or **PlantUML C4**, emit that format alongside or instead.

## Which C4 Levels to Generate

| AI-DLC Depth / Scenario | Required C4 Levels |
| :--- | :--- |
| `fast-track` | None (unless explicitly requested) |
| `standard` (feature / module change) | **Level 3 (Component)** — plus **Level 2 (Container)** if crossing service/storage/process boundaries |
| `deep` (greenfield / cross-system / security boundary) | **Level 1 (System Context)** + **Level 2 (Container)** + **Level 3 (Component)** (+ **Level 4 (Code/Domain)** for complex aggregates) |

Every node label MUST state: **Name**, **[Type / Technology]**, and a **1-line responsibility**. Every edge MUST label the **action and protocol/contract**. Quote any label containing parentheses or brackets (`id["Label [Tech]"]`).

---

## Level 1: System Context Diagram (People & External Systems)

Shows the system as a single black box surrounded by user personas and external systems.

```mermaid
flowchart TB
    User["Persona: Customer\n[Person]\nPlaces and tracks orders"]
    Admin["Persona: Backoffice Admin\n[Person]\nManages catalog and refunds"]

    subgraph Boundary["System Scope"]
        Sys["Order Platform\n[Software System]\nEnforces order lifecycle and BR-* policies"]
    end

    Pay["Payment Gateway\n[External System]\nProcesses card charges"]
    Mail["Email Provider\n[External System]\nSends transactional notifications"]

    User -- "Submits orders [HTTPS/JSON]" --> Sys
    Admin -- "Approves refunds [HTTPS]" --> Sys
    Sys -- "Charges payment token [HTTPS/REST]" --> Pay
    Sys -- "Dispatches receipts [SMTP/API]" --> Mail
```

---

## Level 2: Container Diagram (Deployable Units & Data Stores)

Zooms into the software system to show runtime containers (apps, APIs, workers, databases, queues).

```mermaid
flowchart TB
    User["Customer\n[Person]"]

    subgraph SystemBoundary["Order Platform [Software System]"]
        Web["Web / SPA\n[Container: TypeScript]\nDelivers customer checkout UI"]
        Api["Core API Service\n[Container: Python / FastAPI]\nEnforces domain rules BR-1..BR-5"]
        Worker["Async Fulfillment Worker\n[Container: Python Worker]\nHandles retries and webhooks"]
        Db[("Primary Database\n[Container: PostgreSQL]\nStores orders, line items, audit ledger")]
        Queue["Event Bus\n[Container: Redis Streams]\nDecouples order events"]
    end

    User -- "Uses [HTTPS]" --> Web
    Web -- "Calls API [JSON/HTTPS]" --> Api
    Api -- "Reads/Writes [SQL/TLS]" --> Db
    Api -- "Publishes OrderPlaced [Stream]" --> Queue
    Queue -- "Consumes events" --> Worker
    Worker -- "Updates state [SQL/TLS]" --> Db
```

---

## Level 3: Component Diagram (Internal Modules & Seams)

Zooms into a single container to show deep modules, domain aggregates, ports, and adapters.

```mermaid
flowchart LR
    subgraph ApiContainer["Core API Service [Container]"]
        Ctrl["OrderController\n[Component: HTTP Adapter]\nValidates request schema & auth"]
        Svc["OrderApplicationService\n[Component: Use Case]\nCoordinates transactions & events"]
        Agg["OrderAggregate\n[Component: Domain Model]\nEnforces BR-1 (cancel rules) & BR-2 (totals)"]
        RepoPort["OrderRepository\n[Component: Port Interface]\nAbstract persistence seam"]
        PgRepo["PostgresOrderRepository\n[Component: SQL Adapter]\nMaps aggregate to relational tables"]

        Ctrl -- "Invokes command" --> Svc
        Svc -- "Executes domain logic" --> Agg
        Svc -- "Persists via" --> RepoPort
        PgRepo -. "Implements" .-> RepoPort
    end

    Db[("PostgreSQL\n[Container]")]
    PgRepo -- "Queries [SQL]" --> Db
```

---

## Level 4: Code / Domain Class Diagram (Optional — Complex Aggregates)

Use `classDiagram` only when an aggregate or state machine has non-trivial business rules (`BR-*`) and invariants worth showing at type level.

```mermaid
classDiagram
    class Order {
        +OrderId id
        +OrderStatus status
        +Money total
        +place(items) Result
        +cancel(actor, reason) Result
    }
    class OrderLine {
        +SkuId sku
        +int quantity
        +Money unitPrice
    }
    class Money {
        +int amountMinor
        +CurrencyCode currency
        +add(Money other) Money
    }
    Order "1" *-- "1..*" OrderLine : contains
    OrderLine --> Money : priced in
```
