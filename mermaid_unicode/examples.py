"""Built-in example diagrams (the upstream playground samples, the README example and one for line breaks)."""
from __future__ import annotations

EXAMPLES: dict[str, tuple[str, str]] = {
    "flowchart-request": (
        "Request pipeline with decisions, dotted and thick edges",
        "graph TD\n  Start[Request received] --> Auth{Authenticated?}\n  Auth -->|yes| Rate{Rate limit OK?}\n"
        "  Auth -->|no| R401[401 Unauthorized]\n  Rate -->|yes| H(Handle request)\n"
        "  Rate -->|no| R429[429 Too Many Requests]\n  H -.-> Log[Audit log]\n  H ==> Resp[200 OK]\n",
    ),
    "flowchart-decision": (
        "Decision loop (TD)",
        "flowchart TD\n    A[Start] --> B{Is it working?}\n    B -->|Yes| C[Ship it]\n    B -->|No| D[Debug]\n    D --> B\n",
    ),
    "flowchart-loadbalancer": (
        "Fan-out / fan-in with a database cylinder",
        "graph TD\n    A[Client] --> B[Load Balancer]\n    B --> C[Server 1]\n    B --> D[Server 2]\n"
        "    C --> E[(Database)]\n    D --> E\n",
    ),
    "flowchart-chain-lr": ("Left-to-right chain", "flowchart LR\n    A --> B --> C --> D\n"),
    "flowchart-styles": (
        "Fan-in with `&`, dotted/thick edges, circle ending and a self loop",
        "flowchart TD\n    A[Read config] & B[Load cache] --> C{Valid?}\n    C -.->|no| D[Rebuild]\n"
        "    C ==>|yes| E[Serve]\n    D --o E\n    E -->|poll| E\n",
    ),
    "flowchart-subgraphs": (
        "Nested services in titled subgraph frames",
        "graph TD\n    U[User] --> gw\n    subgraph gw [Gateway]\n        LB[load balancer] --> RL[rate limiter]\n    end\n"
        "    subgraph core [Services]\n        API[api] --> W[worker]\n        W --> Q[(queue)]\n    end\n"
        "    gw --> core\n    core --> DB[(postgres)]\n",
    ),
    "flowchart-multiline": (
        "Hard line breaks in labels: \\n, <br> and a quoted label spanning source lines",
        'flowchart TD\n    A["Player-day row\\n(settled bets only)"] --> B{"Real money\\n= TRUE ?"}\n'
        '    B -- "No" --> F["GGR_FREE_MONEY<br/>freebets only"]\n'
        '    B -- "Yes" --> R["GGR_REAL_MONEY\n    cash bets only"]\n',
    ),
    "flowchart-pipeline": (
        "Step chart with a title and a detail line per box; try -W 44 --align left",
        'flowchart TD\n    A["Raw events\\nJSON per player × day, ~250 columns"]\n'
        '    A --> B["Unpivot\\n1 row = player, feature, value"]\n'
        '    B --> C["Join the mapping\\nfeature → risk factor"]\n'
        '    C --> D["1 · Raw score per factor\\nΣ value of the group"]\n'
        '    C --> E["2 · Positive mass\\nΣ max(value, 0)"]\n'
        '    D --> F["3 · Contribution\\nraw score ÷ positive mass × 100"]\n    E --> F\n'
        '    F --> G{"contribution ≥ 10 % ?"}\n    G -->|yes| H["Keep\\n3 risk factors max"]\n'
        '    G -->|no| I[Discard]\n    H --> J["Output\\nplayer × risk factor · score · % · rank"]\n',
    ),
    "graph-crossing": (
        "Crossing edges that the layout untangles",
        "graph TD\n    C[ccc]\n    D[ddd]\n    A --> D\n    B --> C\n    D --> P[pp]\n    C --> Q[qq]\n",
    ),
    "graph-unavoidable-crossing": (
        "A crossing that cannot be removed (extra bus row)",
        "graph TD\n    A --> D[ddd]\n    A --> C[ccc]\n    B --> C\n    B --> D\n",
    ),
    "graph-minimal": ("Two nodes", "graph TD\n  Start --> Stop\n"),
    "sequence-basic": (
        "Two participants, solid and dashed arrows",
        "sequenceDiagram\n    Alice->>Bob: Hello Bob\n    Bob-->>Alice: Hi Alice\n",
    ),
    "sequence-full": (
        "Aliases, autonumber, self message, note and loop block",
        "sequenceDiagram\n    autonumber\n    participant C as Client\n    participant S as Server\n    participant D as Database\n"
        "    C->>S: GET /api/items\n    S->>D: SELECT * FROM items\n    D-->>S: rows\n    S-->>C: 200 OK\n"
        "    C->>C: render list\n    Note over C,S: happy path\n    loop retry x3\n        C-x S: timeout\n    end\n",
    ),
    "state-lifecycle": (
        "Start/end markers and labelled transitions",
        "stateDiagram-v2\n    [*] --> Idle\n    Idle --> Loading: fetch\n    Loading --> Ready: ok\n"
        "    Loading --> Error: fail\n    Error --> Idle: retry\n    Ready --> [*]\n",
    ),
    "class-animals": (
        "Compartments, annotation, inheritance, composition and dependency",
        "classDiagram\n    class Animal {\n        <<abstract>>\n        +int age\n        +isMammal() bool\n        +mate()\n    }\n"
        "    class Duck {\n        +String beakColor\n        +swim()\n    }\n    Animal <|-- Duck\n    Animal <|-- Fish\n"
        "    Duck *-- Bill\n    Duck ..> Pond : swims in\n",
    ),
    "er-orders": (
        "Entities with attributes and cardinalities",
        "erDiagram\n    CUSTOMER ||--o{ ORDER : places\n    ORDER ||--|{ LINE_ITEM : contains\n"
        "    PRODUCT }o..o{ LINE_ITEM : \"is in\"\n    CUSTOMER {\n        string name PK\n        int custNumber\n    }\n"
        "    ORDER {\n        int orderNumber\n        date placed\n    }\n",
    ),
}
