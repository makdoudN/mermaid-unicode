"""Hand-written and generated Mermaid sources for differential testing against the Rust reference."""
from __future__ import annotations

import random

HANDWRITTEN = [
    # the user's example
    "graph TD\n  Start[Request received] --> Auth{Authenticated?}\n  Auth -->|yes| Rate{Rate limit OK?}\n  Auth -->|no| R401[401 Unauthorized]\n  Rate -->|yes| H(Handle request)\n  Rate -->|no| R429[429 Too Many Requests]\n  H -.-> Log[Audit log]\n  H ==> Resp[200 OK]",
    # md_mermaid_test.rs SAMPLES
    "flowchart TD\n    A[Start] --> B{Is it working?}\n    B -->|Yes| C[Ship it]\n    B -->|No| D[Debug]\n    D --> B\n",
    "graph TD\n    A[Client] --> B[Load Balancer]\n    B --> C[Server 1]\n    B --> D[Server 2]\n    C --> E[(Database)]\n    D --> E\n",
    "flowchart LR\n    A --> B --> C --> D\n",
    "sequenceDiagram\n    Alice->>Bob: Hello Bob\n    Bob-->>Alice: Hi Alice\n",
    "sequenceDiagram\n    autonumber\n    participant C as Client\n    participant S as Server\n    participant D as Database\n    C->>S: GET /api/items\n    S->>D: SELECT * FROM items\n    D-->>S: rows\n    S-->>C: 200 OK\n    C->>C: render list\n    Note over C,S: happy path\n    loop retry x3\n        C-x S: timeout\n    end\n",
    "graph TD\n  Start --> Stop\n",
    "stateDiagram-v2\n    [*] --> Idle\n    Idle --> Loading: fetch\n    Loading --> Ready: ok\n    Loading --> Error: fail\n    Error --> Idle: retry\n    Ready --> [*]\n",
    "flowchart TD\n    A[Read config] & B[Load cache] --> C{Valid?}\n    C -.->|no| D[Rebuild]\n    C ==>|yes| E[Serve]\n    D --o E\n    E -->|poll| E\n",
    "graph TD\n    C[ccc]\n    D[ddd]\n    A --> D\n    B --> C\n    D --> P[pp]\n    C --> Q[qq]\n",
    "graph TD\n    A --> D[ddd]\n    A --> C[ccc]\n    B --> C\n    B --> D\n",
    "graph TD\n    U[User] --> gw\n    subgraph gw [Gateway]\n        LB[load balancer] --> RL[rate limiter]\n    end\n    subgraph core [Services]\n        API[api] --> W[worker]\n        W --> Q[(queue)]\n    end\n    gw --> core\n    core --> DB[(postgres)]\n",
    "classDiagram\n    class Animal {\n        <<abstract>>\n        +int age\n        +isMammal() bool\n        +mate()\n    }\n    class Duck {\n        +String beakColor\n        +swim()\n    }\n    Animal <|-- Duck\n    Animal <|-- Fish\n    Duck *-- Bill\n    Duck ..> Pond : swims in\n",
    "erDiagram\n    CUSTOMER ||--o{ ORDER : places\n    ORDER ||--|{ LINE_ITEM : contains\n    PRODUCT }o..o{ LINE_ITEM : \"is in\"\n    CUSTOMER {\n        string name PK\n        int custNumber\n    }\n    ORDER {\n        int orderNumber\n        date placed\n    }\n",
    # sources from the Rust unit tests
    "flowchart LR\n  A[Start] --> B[End]",
    "flowchart TD\n  A[\"<b>Bold</b> and <i>italic</i>\"] --> B",
    "flowchart TD\n  A[\"Line1<br/>Line2<br>Line3\"]",
    "flowchart TD\n  A[\"`**Start** here`\"] --> B[\"`Save to **database**`\"]\n  B --> C[\"`**Done!**`\"]",
    "flowchart TD\n  A[\"`_italic_ uses `vocab_size` with __all__`\"]",
    "flowchart TD\n  A -->|\"`**yes**`\"| B\n  A -->|\"`__no__`\"| C",
    "flowchart TD\n  A[\"[ 464, 3797 ] seq_len d_model\"]",
    "flowchart TD\n  A[\"<code>vocab_size</code> <span style=\\\"color:red\\\">x</span>\"]",
    "flowchart TD\n  A[\"a < b and c > d\"]",
    "flowchart TD\n  A[\"Returns Vec<String>\"] --> B[\"Option<i32> for <id>\"]",
    "flowchart LR\n  YAML[\"models-config/&lt;model&gt;/&lt;env&gt;.yaml\\nenterprise_api_config:\"]\n  PY[\"model_config_map.py\\nlanguage_model_dict_to_proto()\"]\n  YAML --> PY",
    "stateDiagram-v2\n  state \"work &lt;job&gt;\" as J\n  Idle --> Run: \"on &lt;go&gt;\"\n  Run: \"d &lt;e&gt;\"",
    "classDiagram\n  A --> B : \"uses &lt;X&gt;\"",
    "sequenceDiagram\n  A->>B: \"call &lt;svc&gt;\"\n  Note over A,B: \"memo &lt;o&gt;\"\n  alt \"c &lt;x&gt;\"\n    A->>B: ok\n  end",
    "flowchart TD\n  IDs[\"<b>Token IDs</b><br/>[ 464, 3797 ]<br/><i>indices</i>\"]",
    "flowchart TD\n  A[5\" pipe] --> B[24\" display]",
    "flowchart TD\n  A[\"Tokenizer (BPE / WordPiece)\"] --> B[Done]",
    "flowchart TD\n  IDs[\"<b>3. Token IDs</b><br/>[ 464, 3797 ]<br/><i>indices</i>\"] --> Out[\"<b>done</b>\"]",
    "graph TD\n A-->B\n B-->C\n C-->A",
    "graph TD\n A[Start] --> B[End]",
    "graph TD\n A-->|yes| B",
    "graph TD\n A --> B --> C --> D",
    "flowchart LR\n A --> B --> C --> D",
    "gantt\n title Plan\n section A\n task :a1, 2024-01-01, 30d",
    "   \n  ",
    "graph TD\n A -- no exit --> B",
    "graph TD\n A[日本語ab]",
    "graph TD\n A[aaa] --> D[ddddddd]\n B[bb] --> D\n C[ccccc] --> D",
    "graph TD\n A[Check if the user has permission to access resource] --> B[Done]",
    "graph TD\n A[" + ("alpha " * 40).strip() + "] --> B[x]",
    "graph TD\n A[mark_filter_restore_context] --> B[Done]",
    "flowchart BT\n A[first] --> B[second] --> C[third]",
    "flowchart RL\n A[first] --> B[second] --> C[third]",
    "graph TD\n A ---|maybe| B",
    "graph TD\n A[aaaa] --> B[b] --> C[cccccccc]",
    "graph TD\n" + "".join(f" N{i} --> N{i + 1}\n" for i in range(100)),
    "graph LR\n " + "".join(f"N{i}-->" for i in range(200)) + "N200",
    "gantt\n title Plan\n a\n",
    "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]",
    "flowchart LR\n A <--> B",
    "graph TD\n A <--> B",
    "graph TD\n A <-- B",
    "graph TD\n A[\"wait; 50%% done\"] --> B",
    "graph TD %% main flow\n A --> B %% trailing\n %% full line\n",
    "graph TD\n A --> B\n B --> C\n A --> C",
    "graph TD\n C[ccc]\n D[ddd]\n A --> D\n B --> C",
    "graph TD\n A --> C\n B --> D",
    "graph TD\n X[x]\n Y[y]\n A --> Y\n B --> X\n X --> Q\n Y --> P\n P[p]\n Q[q]",
    "graph TD\n A --> C[ccc]\n B --> D[ddd]",
    "graph TD\n A --> C[ccc]\n A --> D[ddd]",
    "graph TD\n A --> C[ccc]",
    "graph TD\n A --> B\n B --> C\n B --> A\n C --> A",
    "graph TD\n A --> B\n B --> C\n C --> A",
    "graph TD\n A --> B\n B --> C\n B --> A\n C --> B",
    "graph TD\n A --> B\n B --> C\n C --> B",
    "gantt\n title a very long line that should wrap inside the fallback box nicely",
    "classDiagram\n class Animal {\n +int age\n +isMammal() bool\n }\n Animal <|-- Duck",
    "classDiagram\n Animal <|-- Duck\n Animal <|-- Fish",
    "classDiagram\n IShape <|.. Circle",
    "classDiagram\n Car *-- Engine\n Pond o-- Duck",
    "classDiagram\n A ..> B",
    "classDiagram\n class Duck {\n +swim()\n }\n Duck : +String beakColor\n S --> Duck",
    "classDiagram\n <<interface>> Shape\n Shape <|.. Circle",
    "classDiagram\n Shape~T~ : +area() T\n S --> Shape~T~",
    "classDiagram\n Student \"many\" --> \"1\" School : attends",
    "classDiagram\n Animal <|-- Duck\n Animal <|-- Fish\n Animal <|-- Cow",
    "classDiagram\n class Loner\n A --> Loner",
    "classDiagram\n A --> B\n total garbage here",
    "classDiagram\n class Big {\n" + "".join(f" +field{i}\n" for i in range(12)) + " }\n A --> Big",
    "classDiagram\n direction LR\n A --> B",
    "erDiagram\n CUSTOMER ||--o{ ORDER : places\n CUSTOMER {\n string name PK \"full name\"\n int custNumber\n }",
    "erDiagram\n A ||..o{ B : uses",
    "erDiagram\n A ||--o{ B : has",
    "erDiagram\n p[Person] ||--o{ a[\"Bank Account\"] : owns",
    "erDiagram\n LONER\n A ||--|| B : linked",
    "erDiagram\n BIG {\n" + "".join(f" int f{i}\n" for i in range(12)) + " }\n BIG ||--|| OTHER : x",
    "erDiagram\n A ||--|| B : ok\n utter nonsense statement",
    "graph TD\n S[Start] --> one\n subgraph one [Group One]\n A --> B\n end\n one --> E[End]",
    "graph TD\n subgraph api [API]\n A1 --> A2\n end\n subgraph db [Storage]\n B1\n end\n api --> db",
    "graph TD\n subgraph outer [Outer]\n subgraph inner [Inner]\n X --> Y\n end\n W --> X\n end\n S --> outer",
    "graph LR\n S --> A\n subgraph g [Workers]\n A --> B\n end\n B --> T",
    "graph TD\n X --> two\n subgraph two\n C --> D\n end",
    "graph TD\n subgraph \"My Stuff\"\n A\n end\n S --> A",
    "graph TD\n subgraph batch jobs\n B\n end\n S --> B",
    "graph TD\n subgraph \"a &lt;b&gt;\"\n C\n end\n S --> C",
    "graph TD\n subgraph ghost\n end\n A --> B",
    "flowchart BT\n S --> one\n subgraph one [Up]\n A --> B\n end",
    "graph TD\n" + "".join(f" subgraph g{i}\n" for i in range(8)) + " A --> B\n" + " end\n" * 8,
    "graph TD\n A & B --> C & D",
    "graph LR\n A & B --> C --> D",
    "graph TD\n A & B <-- C",
    "graph TD\n A --o B\n C --x D",
    "graph TD\n A --o B",
    "graph TD\n A o-- B\n C x-- D",
    "graph TD\n A <--o B\n C <--x D",
    "graph TD\n A <--o B",
    "graph TD\n A o--o B\n C x--x D",
    "graph TD\n A -.-> B",
    "graph TD\n A ==> B",
    "graph TD\n A --> B",
    "graph LR\n A -. maybe .-> B",
    "graph TD\n A[aaaaaaa] ==> B\n A ==> C[ccccccc]",
    "stateDiagram-v2\n [*] --> Idle\n Idle --> Running: start\n Running --> [*]",
    "stateDiagram\n A --> B",
    "stateDiagram-v2\n A --> B",
    "stateDiagram-v2\n state \"Waiting for input\" as W\n W --> Done",
    "stateDiagram-v2\n state c <<choice>>\n A --> c\n c --> B: yes\n c --> D: no",
    "stateDiagram-v2\n s2 : waits patiently\n A --> s2",
    "stateDiagram-v2\n direction LR\n A --> B --> C",
    "stateDiagram-v2\n state Active {\n A --> B\n }\n Active --> Done",
    "stateDiagram-v2\n A --> B\n note right of A: inline note\n note left of B\n block text\n end note",
    "stateDiagram-v2\n A --> B\n B --> C\n C --> B: retry",
    "stateDiagram-v2\n A --> B\n some garbage line",
    "stateDiagram-v2\n" + "".join(f" S{i} --> S{i + 1}\n" for i in range(600)),
    "stateDiagram-v2\n A ---> B",
    "stateDiagram-v2\n state c <<choice>>\n c : pick a path\n A --> c\n c --> B",
    "stateDiagram-v2\n state c <<choice>>\n state \"pick\" as c\n A --> c",
    "stateDiagram-v2\n A --> B --> C",
    "stateDiagram-v2\n [*] --> A --> B: done",
    "stateDiagram-v2\n A --> B -->",
    "sequenceDiagram\n Alice->>Bob: Hello Bob\n Bob-->>Alice: Hi Alice",
    "sequenceDiagram\n participant C as Client\n participant S as Server\n C->>S: GET /",
    "sequenceDiagram\n participant B\n participant A\n A->>B: hi",
    "sequenceDiagram\n A->>A: think",
    "sequenceDiagram\n A-x B: lost",
    "sequenceDiagram\n A->>B: hi\n Note over A,B: happy path",
    "sequenceDiagram\n autonumber\n A->>B: one\n B->>A: two",
    "sequenceDiagram\n A->>B: hi\n loop retry x3\n A->>B: again\n end",
    "sequenceDiagram\n rect rgb(0,0,0)\n A->>B: hi\n end",
    "sequenceDiagram\n loop l1\n box g\n participant A\n end\n A->>B: hi\n A->>B: bye\n end",
    "sequenceDiagram\n critical connect\n A->>B: try\n option timeout\n A->>A: log\n end",
    "sequenceDiagram\n A->>B: a very long message label that needs room\n B-->>A: ok",
    "graph TD\n A --> C\n B -.-> C",
    "graph TD\n A --> A",
    "graph TD\n A -->|again| A",
    "graph TD\n A --> A\n A --> B",
    "flowchart BT\n A --> A\n A --> B",
    "flowchart LR\n A --> A\n A --> B",
    "graph TD\n A -- or else --> B",
    "sequenceDiagram\n ->>B: orphan",
    "sequenceDiagram\n A->>B: hi\n garbage statement here",
    "sequenceDiagram\n A->>B: this label is far wider than the available pane width",
    "sequenceDiagram\n" + "".join(f" A->>B: msg {i}\n" for i in range(600)),
    "sequenceDiagram\n A->>+B: call\n B-->>-A: return",
    "sequenceDiagram\n Alice->>Bob: hi\n Note over Alice: solo note",
    "sequenceDiagram\n Note left of A: left note\n Note right of B: right note\n A-)B: async\n B--)A: reply\n A->B: plain\n B-->A: dashed plain",
    # extra hand-written edge cases
    "graph TD\n A[😀 emoji] --> B[日本語 wide] --> C[é combining]",
    "graph TD\n  A[\"Line with \\\"quotes\\\" inside\"] --> B",
    "graph LR\n  a[[Subroutine]] --> b[(Cylinder)] --> c((Circle)) --> d>Flag] --> e{{Hexagon}} --> f([Stadium])",
    "graph TD\n  A -->|a very very very very long edge label that exceeds MAX_LABEL| B",
    "graph LR\n  A -->|label| B\n  B --> A\n  A --> C\n  C -->|back| A",
    "graph BT\n  A --> B\n  A --> C\n  B --> D\n  C --> D\n  D --> A",
    "graph RL\n  A[alpha] -->|x| B[beta]\n  B -.-> C[gamma]\n  C ==> A",
    "flowchart TD\n  subgraph one\n    subgraph two\n      subgraph three\n        A --> B\n      end\n      B --> C\n    end\n    C --> D\n  end\n  D --> E\n  E --> A",
    "flowchart LR\n  subgraph g1 [Group 1]\n    A --> B\n  end\n  subgraph g2 [Group 2]\n    C --> D\n  end\n  B --> C\n  g1 --> g2\n  D --> A",
    "classDiagram\n  direction RL\n  class A~T~ {\n    <<interface>>\n    +List~int~ ids\n    +get() T\n  }\n  A <|-- B\n  B o-- C : has\n  C --* D\n  D <.. E\n  E ..|> A",
    "classDiagram\n  direction BT\n  A --> B\n  B --> C",
    "erDiagram\n  A }|..|| B : \"many to one\"\n  B ||--o| C\n  C {\n    int id PK\n    string name \"desc\"\n  }",
    "stateDiagram-v2\n  direction RL\n  [*] --> A\n  A --> B: go\n  B --> A: back\n  B --> [*]",
    "stateDiagram-v2\n  direction BT\n  [*] --> A\n  A --> B\n  B --> [*]",
    "sequenceDiagram\n  participant A as Alice 日本\n  participant B as Bob\n  A->>B: 日本語 メッセージ\n  B-->>A: ok\n  Note left of A: 左\n  Note right of B: 右\n  alt case 1\n    A->>B: x\n  else case 2\n    B->>A: y\n  end\n  par p\n    A->>A: self\n  and q\n    B->>B: self2\n  end",
    "flowchart TD\n  A[\"&#x1F600; &#128512; &amp; &lt;b&gt;\"] --> B[\"&#0; &#27; &bogus;\"]",
    "graph TD\n  A(( )) --> B[ ]",
    "graph TD\n  A\n  B\n  C",
    "graph LR\n  A\n  B\n  C",
    "graph TD\n  A -->|yes| B -->|no| C -->|maybe| A",
    "flowchart TD\n  A ==>|thick label| B\n  A -.->|dotted label| C\n  B & C --> D",
    "graph TD\n  A --> B\n  A --> C\n  A --> D\n  A --> E\n  B --> F\n  C --> F\n  D --> F\n  E --> F\n  F --> A",
    "graph LR\n  A --> B\n  A --> C\n  A --> D\n  B --> E\n  C --> E\n  D --> E\n  E --> B\n  E --> C",
    "graph TD;A-->B;B-->C;C-->D;",
    "graph TD\r\n  A --> B\r\n  B --> C\r\n",
    "graph TD\n\tA --> B\n\tB --> C",
    "flowchart TD\n  A -- text --- B\n  B -- more text -.- C\n  C -- thick === D",
    "flowchart TD\n  A ---> B\n  B ----> C\n  C -...-> D\n  D ====> E",
    "graph TD\n  A -->|line one<br/>line two| B",
    "graph LR\n  A[very_long_identifier_with_many_segments_that_wraps] --> B[another/path/like/identifier/here]",
    "graph TD\n  A[\"x\"] --> B[\"y\"]\n  click A callback\n  style A fill:#f9f\n  classDef c fill:#fff\n  class A c\n  linkStyle 0 stroke:red\n  direction LR",
]

WIDE_CHARS = ["日", "本", "語", "字", "😀", "🚀", "한", "글", "中", "文"]
ASCII_WORDS = ["alpha", "beta", "gamma", "delta", "request", "response", "db", "cache", "user", "svc", "queue", "worker", "api", "ok", "fail", "retry", "x", "yy", "zzz"]
SPECIAL_WORDS = ["a<b", "&lt;x&gt;", "&amp;", "50%", "it's", "\"q\"", "a_b_c", "path/to/file", "very-long-hyphenated-identifier-name", "é", "<b>bold</b>", "<br/>", "<code>c</code>", "**md**", "`code`"]


def rand_word(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.6:
        return rng.choice(ASCII_WORDS)
    if r < 0.8:
        return rng.choice(SPECIAL_WORDS)
    return "".join(rng.choice(WIDE_CHARS) for _ in range(rng.randint(1, 4)))


def rand_label(rng: random.Random) -> str:
    n = rng.choice([1, 1, 1, 2, 2, 3, 5, 8])
    return " ".join(rand_word(rng) for _ in range(n))


def rand_node(rng: random.Random, ids: list[str]) -> str:
    id_ = rng.choice(ids)
    r = rng.random()
    if r < 0.4:
        return id_
    label = rand_label(rng)
    if rng.random() < 0.3:
        label = f'"{label}"'
    shape = rng.choice(["[{}]", "({})", "{{{}}}", "[[{}]]", "[({})]", "(({}))", "([{}])", ">{}]", "{{{{{}}}}}"])
    return id_ + shape.format(label)


def rand_link(rng: random.Random) -> str:
    ops = ["-->", "---", "-.->", "-.-", "==>", "===", "<-->", "<--", "--o", "--x", "o--", "x--", "o--o", "x--x", "<--o", "---->", "-..->"]
    op = rng.choice(ops)
    r = rng.random()
    if r < 0.4:
        return f" {op} "
    if r < 0.7:
        return f" {op}|{rand_label(rng)}| "
    if r < 0.85 and op in ("---", "-.-", "==="):
        base = op[0]
        return f" {base}{base} {rand_label(rng)} {op}> "
    return f" {op} "


def gen_flowchart(rng: random.Random) -> str:
    dir_ = rng.choice(["TD", "TB", "LR", "RL", "BT", "", "lr", "td"])
    header = rng.choice(["graph", "flowchart", "Graph", "FLOWCHART"]) + (f" {dir_}" if dir_ else "")
    n_ids = rng.randint(1, 10)
    ids = [f"N{i}" for i in range(n_ids)] + ["A", "B", "C", "Start", "End_1", "日本"]
    lines = [header]
    n_stmts = rng.randint(0, 12)
    depth = 0
    n_groups = 0
    for _ in range(n_stmts):
        r = rng.random()
        if r < 0.12 and depth < 3 and n_groups < 6:
            gid = f"g{n_groups}"
            n_groups += 1
            form = rng.choice([gid, f"{gid} [{rand_label(rng)}]", f'"{rand_label(rng)}"', f"{gid} [ ]"])
            lines.append(f"  subgraph {form}")
            depth += 1
            continue
        if r < 0.2 and depth > 0:
            lines.append("  end")
            depth -= 1
            continue
        if r < 0.28:
            lines.append("  " + rand_node(rng, ids))
            continue
        if r < 0.33:
            lines.append("  " + rng.choice(["classDef x fill:#fff", "style A fill:#f9f", "click A cb", "linkStyle 0 stroke:red", "direction LR", "%% comment"]))
            continue
        chain_len = rng.choice([1, 1, 1, 2, 2, 3])
        parts = [rand_node(rng, ids)]
        if rng.random() < 0.15:
            parts[0] += " & " + rand_node(rng, ids)
        for _ in range(chain_len):
            nxt = rand_node(rng, ids)
            if rng.random() < 0.1:
                nxt += " & " + rand_node(rng, ids)
            parts.append(rand_link(rng) + nxt)
        stmt = "".join(parts)
        if rng.random() < 0.1:
            stmt += "; " + rand_node(rng, ids) + " --> " + rand_node(rng, ids)
        if rng.random() < 0.05:
            stmt += " %% trailing comment"
        lines.append("  " + stmt)
    while depth > 0:
        lines.append("  end")
        depth -= 1
    sep = rng.choice(["\n", "\n", "\r\n"])
    return sep.join(lines) + (sep if rng.random() < 0.5 else "")


def gen_state(rng: random.Random) -> str:
    lines = [rng.choice(["stateDiagram-v2", "stateDiagram", "StateDiagram-v2"])]
    ids = ["A", "B", "C", "Idle", "Run", "S1", "S2", "[*]"]
    if rng.random() < 0.3:
        lines.append("  direction " + rng.choice(["LR", "RL", "BT", "TB"]))
    for _ in range(rng.randint(1, 10)):
        r = rng.random()
        if r < 0.5:
            chain = rng.choice(ids)
            for _ in range(rng.choice([1, 1, 2])):
                chain += " --> " + rng.choice(ids)
            if rng.random() < 0.5:
                chain += ": " + rand_label(rng)
            lines.append("  " + chain)
        elif r < 0.65:
            lines.append(f'  state "{rand_label(rng)}" as {rng.choice(ids[:-1])}')
        elif r < 0.75:
            lines.append(f"  state {rng.choice(ids[:-1])} <<choice>>")
        elif r < 0.85:
            lines.append(f"  {rng.choice(ids[:-1])} : {rand_label(rng)}")
        elif r < 0.92:
            lines.append(f"  note right of {rng.choice(ids[:-1])}: {rand_label(rng)}")
        else:
            lines.append("  " + rng.choice(["hide empty description", "classDef x", "state Comp {", "}", "--"]))
    return "\n".join(lines)


def gen_class(rng: random.Random) -> str:
    lines = ["classDiagram"]
    ids = ["A", "B", "C", "Animal", "Duck", "Shape~T~", "List~int~"]
    if rng.random() < 0.3:
        lines.append("  direction " + rng.choice(["LR", "RL", "BT", "TB"]))
    ops = ["<|--", "--|>", "<|..", "..|>", "*--", "--*", "o--", "--o", "<--", "-->", "<..", "..>", "--", ".."]
    for _ in range(rng.randint(1, 10)):
        r = rng.random()
        if r < 0.5:
            a, b = rng.choice(ids), rng.choice(ids)
            op = rng.choice(ops)
            card = rng.random() < 0.3
            lhs = f'{a} "{rng.choice(["1", "many", "0..*"])}"' if card else a
            rhs = f'"{rng.choice(["1", "*"])}" {b}' if card else b
            stmt = f"  {lhs} {op} {rhs}"
            if rng.random() < 0.5:
                stmt += " : " + rand_label(rng)
            lines.append(stmt)
        elif r < 0.7:
            cls = rng.choice(ids)
            lines.append(f"  class {cls} {{")
            if rng.random() < 0.3:
                lines.append("    <<interface>>")
            for _ in range(rng.randint(0, 10)):
                lines.append("    " + rng.choice(["+int age", "-String name", "+run()", "#calc(int x) bool", "~List~int~ ids", "+get() T"]))
            lines.append("  }")
        elif r < 0.8:
            lines.append(f"  {rng.choice(ids)} : {rng.choice(['+int x', '+go()', 'field'])}")
        elif r < 0.9:
            lines.append(f"  <<{rng.choice(['interface', 'abstract', 'enumeration'])}>> {rng.choice(ids)}")
        else:
            lines.append(f"  class {rng.choice(ids)}")
    return "\n".join(lines)


def gen_er(rng: random.Random) -> str:
    lines = ["erDiagram"]
    ids = ["CUSTOMER", "ORDER", "LINE_ITEM", "PRODUCT", "p[Person]", 'a["Bank Account"]']
    cards = ["||", "|o", "o|", "}o", "o{", "}|", "|{"]
    for _ in range(rng.randint(1, 8)):
        r = rng.random()
        if r < 0.6:
            op = rng.choice(cards) + rng.choice(["--", ".."]) + rng.choice(cards)
            stmt = f"  {rng.choice(ids)} {op} {rng.choice(ids)}"
            if rng.random() < 0.7:
                lab = rand_label(rng)
                stmt += " : " + (f'"{lab}"' if rng.random() < 0.5 else lab.split(" ")[0])
            lines.append(stmt)
        elif r < 0.9:
            ent = rng.choice(ids[:4])
            lines.append(f"  {ent} {{")
            for _ in range(rng.randint(0, 10)):
                lines.append("    " + rng.choice(["string name PK", "int id", 'date placed "when"', "float amount FK"]))
            lines.append("  }")
        else:
            lines.append("  " + rng.choice(ids[:4]))
    return "\n".join(lines)


def gen_sequence(rng: random.Random) -> str:
    lines = [rng.choice(["sequenceDiagram", "SequenceDiagram"])]
    ids = ["A", "B", "C", "Alice", "Bob", "Client", "Server"]
    ops = ["->>", "-->>", "->", "-->", "-x", "--x", "-)", "--)"]
    if rng.random() < 0.3:
        lines.append("  autonumber")
    for _ in range(rng.randint(0, 3)):
        p = rng.choice(ids)
        lines.append(f"  participant {p}" + (f" as {rand_label(rng)}" if rng.random() < 0.5 else ""))
    depth = 0
    for _ in range(rng.randint(1, 12)):
        r = rng.random()
        if r < 0.5:
            a, b = rng.choice(ids), rng.choice(ids)
            act = rng.choice(["", "", "+", "-"])
            msg = f"  {a}{rng.choice(ops)}{act}{b}"
            if rng.random() < 0.8:
                msg += ": " + rand_label(rng)
            lines.append(msg)
        elif r < 0.65:
            kind = rng.choice(["over", "left of", "right of", "Over"])
            who = rng.choice(ids)
            if kind.lower() == "over" and rng.random() < 0.5:
                who += "," + rng.choice(ids)
            lines.append(f"  Note {kind} {who}: {rand_label(rng)}")
        elif r < 0.78:
            lines.append(f"  {rng.choice(['loop', 'alt', 'opt', 'par', 'critical', 'break', 'rect rgb(0,0,0)', 'box'])} {rand_label(rng)}")
            depth += 1
        elif r < 0.85 and depth > 0:
            lines.append(f"  {rng.choice(['else', 'and', 'option'])} {rand_label(rng)}")
        elif r < 0.95 and depth > 0:
            lines.append("  end")
            depth -= 1
        else:
            lines.append("  " + rng.choice(["activate A", "deactivate A", "title T", "create participant X"]))
    while depth > 0:
        lines.append("  end")
        depth -= 1
    return "\n".join(lines)


def gen_other(rng: random.Random) -> str:
    return rng.choice([
        "gantt\n  title " + rand_label(rng) + "\n  section S\n  task :a1, 2024-01-01, 30d",
        "pie title Pets\n  \"Dogs\" : 386\n  \"Cats\" : 85",
        "mindmap\n  root((mindmap))\n    Origins\n      Long history",
        "  \n\n" + rand_label(rng),
        "gitGraph\n  commit\n  branch develop",
        rand_label(rng) * 10,
    ])


def generate(seed: int, count: int) -> list[str]:
    rng = random.Random(seed)
    out = []
    gens = [gen_flowchart] * 6 + [gen_state, gen_class, gen_er, gen_sequence, gen_sequence, gen_other]
    for _ in range(count):
        out.append(rng.choice(gens)(rng))
    return out


WIDTHS = [None, 24, 40, 60, 80, 120, 200]
