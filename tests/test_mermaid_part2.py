"""Port of `mod tests` from grok-build's ``mermaid.rs`` (part 2: lines 4705-5303).

One Python test per Rust ``#[test]``, same name. Runs under pytest or ``tests/run_tests.py``.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mermaid_unicode import rstr  # noqa: E402
from mermaid_unicode.mermaid import (  # noqa: E402
    Edge,
    Graph,
    Head,
    LineKind,
    MermaidStyles,
    Node,
    compute_ranks,
    count_crossings,
    order_ranks,
    parse_class,
    parse_er,
    parse_er_op,
    parse_graph,
    render,
)
from mermaid_unicode.unicode_width import str_width  # noqa: E402


# ---------------------------------------------------------------------------------------------
# Helpers (Rust: styles / node / edge / index_of / at / plain / ordered_ranks)
# ---------------------------------------------------------------------------------------------
def styles() -> MermaidStyles:
    return MermaidStyles()


def node(g: Graph, i: int) -> Node:
    assert i < len(g.nodes), f"expected node {i}, have {len(g.nodes)}"
    return g.nodes[i]


def edge(g: Graph, i: int) -> Edge:
    assert i < len(g.edges), f"expected edge {i}, have {len(g.edges)}"
    return g.edges[i]


def index_of(g: Graph, id: str) -> int:
    assert id in g.index, f"missing node id {id!r}"
    return g.index[id]


def at(xs, i: int):
    assert 0 <= i < len(xs), f"index {i} out of bounds for {xs!r}"
    return xs[i]


def plain(src: str) -> str:
    art = render(src, styles(), 120)
    assert art is not None
    return "\n".join(art.plain_lines)


def ordered_ranks(src: str) -> tuple[Graph, list[int], list[list[int]]]:
    g = parse_graph(src)
    assert g is not None
    ranks = compute_ranks(g)
    max_rank = max(ranks)
    by_rank: list[list[int]] = [[] for _ in range(max_rank + 1)]
    for idx, r in enumerate(ranks):
        if r < len(by_rank):
            by_rank[r].append(idx)
    order_ranks(by_rank, g.edges, ranks)
    return g, ranks, by_rank


def _lines(s: str) -> list[str]:
    return s.split("\n")


def _position(lines: list[str], pred) -> int:
    """`lines.iter().position(pred).unwrap()`."""
    for i, l in enumerate(lines):
        if pred(l):
            return i
    raise AssertionError("no matching line in:\n" + "\n".join(lines))


def _rposition(lines: list[str], pred) -> int:
    """`lines.iter().rposition(pred).unwrap()`."""
    for i in range(len(lines) - 1, -1, -1):
        if pred(lines[i]):
            return i
    raise AssertionError("no matching line in:\n" + "\n".join(lines))


def _find_line(s: str, pred) -> str:
    """`s.lines().find(pred).unwrap()`."""
    for l in _lines(s):
        if pred(l):
            return l
    raise AssertionError("no matching line in:\n" + s)


def _positions(by_rank: list[list[int]], n: int) -> list[int]:
    pos = [0] * n
    for row in by_rank:
        for i, v in enumerate(row):
            if v < len(pos):
                pos[v] = i
    return pos


# ---------------------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------------------
def test_order_ranks_removes_avoidable_crossing():
    g, ranks, by_rank = ordered_ranks("graph TD\n C[ccc]\n D[ddd]\n A --> D\n B --> C")
    pos = _positions(by_rank, len(g.nodes))
    assert count_crossings(g.edges, ranks, pos) == 0
    idx = lambda id: index_of(g, id)  # noqa: E731
    assert at(pos, idx("D")) < at(pos, idx("C")), "D follows parent A leftward"


def test_order_ranks_keeps_crossing_free_order():
    g, ranks, by_rank = ordered_ranks("graph TD\n A --> C\n B --> D")
    idx = lambda id: index_of(g, id)  # noqa: E731
    assert (by_rank[0] if len(by_rank) > 0 else None) == [idx("A"), idx("B")]
    assert (by_rank[1] if len(by_rank) > 1 else None) == [idx("C"), idx("D")]
    pos = _positions(by_rank, len(g.nodes))
    assert count_crossings(g.edges, ranks, pos) == 0


def test_crossing_edges_render_untangled():
    out = plain("graph TD\n C[ccc]\n D[ddd]\n A --> D\n B --> C")
    row = _find_line(out, lambda l: "ccc" in l and "ddd" in l)
    assert row.find("ddd") < row.find("ccc"), f"children reorder under their parents:\n{out}"
    assert "┼" not in out, out


def test_three_layer_weave_untangles():
    g, ranks, by_rank = ordered_ranks(
        "graph TD\n X[x]\n Y[y]\n A --> Y\n B --> X\n X --> Q\n Y --> P\n P[p]\n Q[q]"
    )
    pos = _positions(by_rank, len(g.nodes))
    assert count_crossings(g.edges, ranks, pos) == 0, "both layers untangle"


def test_unavoidable_crossing_gets_separate_bus_rows():
    crossing = plain("graph TD\n A --> D[ddd]\n A --> C[ccc]\n B --> C\n B --> D")
    parallel = plain("graph TD\n A --> C[ccc]\n B --> D[ddd]")
    assert "┼" in crossing, f"wire crossing renders:\n{crossing}"
    assert len(_lines(crossing)) == len(_lines(parallel)) + 1, (
        f"crossing pair claims one extra bus row:\n{crossing}"
    )
    assert crossing.count("▼") == 2, crossing


def test_fan_out_keeps_single_bus_row():
    out = plain("graph TD\n A --> C[ccc]\n A --> D[ddd]")
    baseline = plain("graph TD\n A --> C[ccc]")
    assert len(_lines(out)) == len(_lines(baseline)), (
        f"shared-source jogs share one bus row:\n{out}"
    )
    assert "┼" not in out, out


def test_shared_target_back_edges_share_one_lane():
    two = plain("graph TD\n A --> B\n B --> C\n B --> A\n C --> A")
    one = plain("graph TD\n A --> B\n B --> C\n C --> A")
    assert max(str_width(l) for l in _lines(two)) == max(str_width(l) for l in _lines(one)), (
        f"shared-target back edges merge into one lane:\n{two}"
    )
    assert two.count("◄") == 1, two


def test_distinct_back_edges_get_separate_lanes():
    split = plain("graph TD\n A --> B\n B --> C\n B --> A\n C --> B")
    single = plain("graph TD\n A --> B\n B --> C\n C --> B")
    assert split.count("◄") == 2, split
    assert max(str_width(l) for l in _lines(split)) > max(
        str_width(l) for l in _lines(single)
    ), f"overlapping unrelated back edges claim a second lane:\n{split}"


def test_fallback_wraps_long_lines_to_max_width():
    art = render(
        "gantt\n title a very long line that should wrap inside the fallback box nicely",
        styles(),
        40,
    )
    assert art is not None
    out = art.plain_lines
    assert all(str_width(l) <= 40 for l in out), "\n".join(out)
    assert len(out) >= 2, f"expected boxed output, got {out!r}"
    mid = out[1 : len(out) - 1]
    for line in mid:
        assert line.startswith("│") and line.endswith("│"), (
            f"body rows keep both borders: {line!r}"
        )
    assert "nicely" in "\n".join(out), "\n".join(out)


def test_class_renders_compartments():
    out = plain(
        "classDiagram\n class Animal {\n +int age\n +isMammal() bool\n }\n Animal <|-- Duck"
    )
    assert "Animal" in out, out
    assert "+int age" in out, out
    assert "+isMammal() bool" in out, out
    assert "├" in out and "┤" in out, f"section rules:\n{out}"
    lines = _lines(out)
    name = _position(lines, lambda l: "Animal" in l)
    attr = _position(lines, lambda l: "+int age" in l)
    method = _position(lines, lambda l: "+isMammal() bool" in l)
    assert name < attr and attr < method, out


def test_class_inheritance_triangle_at_parent():
    out = plain("classDiagram\n Animal <|-- Duck\n Animal <|-- Fish")
    assert "△" in out, f"hollow triangle:\n{out}"
    lines = _lines(out)
    animal = _position(lines, lambda l: "Animal" in l)
    duck = _position(lines, lambda l: "Duck" in l)
    assert animal < duck, f"parent above child:\n{out}"
    tri = _position(lines, lambda l: "△" in l)
    assert tri >= animal and tri < duck, f"triangle at parent end:\n{out}"


def test_class_realization_is_dotted_triangle():
    parsed = parse_class("classDiagram\n IShape <|.. Circle")
    assert parsed is not None
    g = parsed[0]
    assert edge(g, 0).head_from == Head.TRIANGLE
    assert edge(g, 0).line == LineKind.DOTTED
    out = plain("classDiagram\n IShape <|.. Circle")
    assert "╎" in out or "╌" in out, out


def test_class_composition_and_aggregation_diamonds():
    out = plain("classDiagram\n Car *-- Engine\n Pond o-- Duck")
    assert "◆" in out, f"filled diamond:\n{out}"
    assert "◇" in out, f"open diamond:\n{out}"


def test_class_dependency_dotted_arrow():
    parsed = parse_class("classDiagram\n A ..> B")
    assert parsed is not None
    g = parsed[0]
    assert edge(g, 0).head_to == Head.ARROW
    assert edge(g, 0).line == LineKind.DOTTED


def test_class_colon_members_merge_with_block():
    out = plain(
        "classDiagram\n class Duck {\n +swim()\n }\n Duck : +String beakColor\n S --> Duck"
    )
    assert "+swim()" in out, out
    assert "+String beakColor" in out, out


def test_class_annotation_renders_guillemets():
    out = plain("classDiagram\n <<interface>> Shape\n Shape <|.. Circle")
    assert "«interface»" in out, out


def test_class_generics_display_as_angle_brackets():
    out = plain("classDiagram\n Shape~T~ : +area() T\n S --> Shape~T~")
    assert "Shape<T>" in out, out
    assert "~" not in out, out


def test_class_cardinalities_fold_into_label():
    out = plain('classDiagram\n Student "many" --> "1" School : attends')
    assert "many attends 1" in out, out


def test_class_from_end_head_survives_fan_out_jog():
    out = plain("classDiagram\n Animal <|-- Duck\n Animal <|-- Fish\n Animal <|-- Cow")
    assert out.count("△") + out.count("▽") == 1, (
        f"merged from-end glyph on the parent border:\n{out}"
    )


def test_class_empty_class_is_plain_titled_box():
    out = plain("classDiagram\n class Loner\n A --> Loner")
    assert "Loner" in out, out


def test_class_unknown_statement_falls_back():
    out = plain("classDiagram\n A --> B\n total garbage here")
    assert "mermaid: classDiagram" in out, out


def test_class_member_cap_ellipsis():
    src = "classDiagram\n class Big {\n"
    for i in range(12):
        src += f" +field{i}\n"
    src += " }\n A --> Big"
    out = plain(src)
    assert "+field7" in out, out
    assert "+field9" not in out, out
    assert "…" in out, out


def test_class_direction_lr():
    out = plain("classDiagram\n direction LR\n A --> B")
    line = _find_line(out, lambda l: "A" in l)
    assert "B" in line, out


def test_er_renders_entities_and_relationship_labels():
    out = plain(
        'erDiagram\n CUSTOMER ||--o{ ORDER : places\n CUSTOMER {\n string name PK "full name"\n int custNumber\n }'
    )
    assert "CUSTOMER" in out, out
    assert "ORDER" in out, out
    assert "string name PK" in out, out
    assert "full name" not in out, f"attribute comments dropped:\n{out}"
    assert "1 places 0..*" in out, out
    assert "├" in out, f"attribute compartment rule:\n{out}"


def test_er_cardinality_map():
    cases = [
        ("||--||", "1", "1"),
        ("|o--o|", "0..1", "0..1"),
        ("}o--o{", "0..*", "0..*"),
        ("}|--|{", "1..*", "1..*"),
        ("||--o{", "1", "0..*"),
    ]
    for op, l, r in cases:
        parsed = parse_er_op(op)
        assert parsed is not None, op
        cl, cr, line = parsed
        assert (cl, cr) == (l, r), op
        assert line == LineKind.SOLID
    dotted = parse_er_op("||..o{")
    assert dotted is not None
    assert dotted[2] == LineKind.DOTTED
    assert parse_er_op("||==o{") is None
    assert parse_er_op("garbage") is None


def test_er_non_identifying_renders_dotted():
    out = plain("erDiagram\n A ||..o{ B : uses")
    assert "╎" in out or "╌" in out, out


def test_er_relationships_have_no_arrowheads():
    out = plain("erDiagram\n A ||--o{ B : has")
    for head in ["▼", "▲", "◄", "▶", "△", "◆", "◇"]:
        assert head not in out, f"{head} in:\n{out}"


def test_er_entity_alias_label():
    out = plain('erDiagram\n p[Person] ||--o{ a["Bank Account"] : owns')
    assert "Person" in out, out
    assert "Bank Account" in out, out


def test_er_unquoted_label_and_bare_entity_decl():
    parsed = parse_er("erDiagram\n LONER\n A ||--|| B : linked")
    assert parsed is not None
    g = parsed[0]
    assert len(g.nodes) == 3
    out = plain("erDiagram\n LONER\n A ||--|| B : linked")
    assert "LONER" in out, out
    assert "1 linked 1" in out, out


def test_er_attribute_cap_ellipsis():
    src = "erDiagram\n BIG {\n"
    for i in range(12):
        src += f" int f{i}\n"
    src += " }\n BIG ||--|| OTHER : x"
    out = plain(src)
    assert "int f7" in out, out
    assert "int f9" not in out, out
    assert "…" in out, out


def test_er_unknown_statement_falls_back():
    out = plain("erDiagram\n A ||--|| B : ok\n utter nonsense statement")
    assert "mermaid: erDiagram" in out, out


def test_subgraph_renders_titled_frame():
    out = plain(
        "graph TD\n S[Start] --> one\n subgraph one [Group One]\n A --> B\n end\n one --> E[End]"
    )
    assert " Group One " in out, out
    lines = _lines(out)
    title = _position(lines, lambda l: "Group One" in l)
    a = _position(lines, lambda l: "│ A │" in l)
    b = _position(lines, lambda l: "│ B │" in l)
    frame_close = _rposition(lines, lambda l: rstr.trim_start(l).startswith("└"))
    assert title < a and a < b and b <= frame_close, out
    assert "Start" in out and "End" in out, out
    assert out.count("▼") == 3, out


def test_subgraph_edge_between_groups():
    out = plain(
        "graph TD\n subgraph api [API]\n A1 --> A2\n end\n subgraph db [Storage]\n B1\n end\n api --> db"
    )
    assert " API " in out, out
    assert " Storage " in out, out
    lines = _lines(out)
    api = _position(lines, lambda l: "API" in l)
    db = _position(lines, lambda l: "Storage" in l)
    assert api < db, f"API frame ranks above Storage:\n{out}"


def test_subgraph_nested_frames():
    out = plain(
        "graph TD\n subgraph outer [Outer]\n subgraph inner [Inner]\n X --> Y\n end\n W --> X\n end\n S --> outer"
    )
    assert " Outer " in out, out
    assert " Inner " in out, out
    lines = _lines(out)
    outer = _position(lines, lambda l: "Outer" in l)
    inner = _position(lines, lambda l: "Inner" in l)
    assert outer < inner, out


def test_subgraph_cross_member_edge_attaches_to_frame():
    out = plain("graph LR\n S --> A\n subgraph g [Workers]\n A --> B\n end\n B --> T")
    assert " Workers " in out, out
    assert "S" in out and "T" in out, out
    assert out.count("▶") == 3, out
    row = _find_line(out, lambda l: "│ A ├" in l)
    assert row.find("S") < row.find("A"), (
        f"A stays outside the group (first definition wins):\n{out}"
    )


def test_subgraph_id_referenced_before_declaration():
    g = parse_graph("graph TD\n X --> two\n subgraph two\n C --> D\n end")
    assert g is not None
    assert len(g.groups) == 1
    out = plain("graph TD\n X --> two\n subgraph two\n C --> D\n end")
    assert " two " in out, f"frame titled by id:\n{out}"
    assert "│ C │" in out, out


def test_subgraph_quoted_and_plain_titles():
    out = plain('graph TD\n subgraph "My Stuff"\n A\n end\n S --> A')
    assert " My Stuff " in out, out
    out2 = plain("graph TD\n subgraph batch jobs\n B\n end\n S --> B")
    assert " batch jobs " in out2, out2
    out3 = plain('graph TD\n subgraph "a &lt;b&gt;"\n C\n end\n S --> C')
    assert "a <b>" in out3 and "&lt;" not in out3, out3


def test_subgraph_empty_is_dropped():
    out = plain("graph TD\n subgraph ghost\n end\n A --> B")
    assert "ghost" not in out, out
    assert "▼" in out, out


def test_subgraph_bt_flips_frame_and_contents():
    out = plain("flowchart BT\n S --> one\n subgraph one [Up]\n A --> B\n end")
    assert " Up " in out, out
    lines = _lines(out)
    row = lambda needle: _position(lines, lambda l: needle in l)  # noqa: E731
    assert row("│ B │") < row("│ A │"), f"contents flip with BT:\n{out}"
    assert row(" Up ") < row("S"), f"frame above source in BT:\n{out}"
    assert "▲" in out, out


def test_subgraph_depth_over_cap_falls_back():
    src = "graph TD\n"
    for i in range(8):
        src += f" subgraph g{i}\n"
    src += " A --> B\n"
    for _ in range(8):
        src += " end\n"
    out = plain(src)
    assert "mermaid: graph" in out, out


def test_subgraph_groupless_path_unchanged():
    g = parse_graph("graph TD\n A --> B")
    assert g is not None
    assert not g.groups


def test_fan_out_creates_cross_product_edges():
    g = parse_graph("graph TD\n A & B --> C & D")
    assert g is not None
    assert len(g.nodes) == 4
    assert len(g.edges) == 4
    idx = lambda id: index_of(g, id)  # noqa: E731
    has = lambda f, t: any(e.from_ == idx(f) and e.to == idx(t) for e in g.edges)  # noqa: E731
    assert has("A", "C") and has("A", "D") and has("B", "C") and has("B", "D")
    out = plain("graph TD\n A & B --> C & D")
    assert out.count("▼") == 2, out


def test_fan_out_in_chain():
    g = parse_graph("graph LR\n A & B --> C --> D")
    assert g is not None
    assert len(g.edges) == 3


def test_fan_out_with_reversed_arrow():
    g = parse_graph("graph TD\n A & B <-- C")
    assert g is not None
    idx = lambda id: index_of(g, id)  # noqa: E731
    assert len(g.edges) == 2
    assert all(e.from_ == idx("C") for e in g.edges)
    assert all(e.head_to == Head.ARROW for e in g.edges)


def test_circle_and_cross_endings_create_no_phantom_nodes():
    g = parse_graph("graph TD\n A --o B\n C --x D")
    assert g is not None
    assert len(g.nodes) == 4, "no phantom o/x nodes"
    assert "o" not in g.index
    assert "x" not in g.index
    assert edge(g, 0).head_to == Head.CIRCLE
    assert edge(g, 1).head_to == Head.CROSS
    out = plain("graph TD\n A --o B")
    assert "o" in out, f"circle head rendered:\n{out}"


def test_left_endings_decorate_without_reversing():
    g = parse_graph("graph TD\n A o-- B\n C x-- D")
    assert g is not None
    idx = lambda id: index_of(g, id)  # noqa: E731
    assert edge(g, 0).from_ == idx("A")
    assert edge(g, 0).to == idx("B")
    assert edge(g, 0).head_from == Head.CIRCLE
    assert edge(g, 1).head_from == Head.CROSS
    assert edge(g, 0).head_to == Head.NONE


def test_reversed_arrow_with_end_marker_swaps_direction():
    g = parse_graph("graph TD\n A <--o B\n C <--x D")
    assert g is not None
    idx = lambda id: index_of(g, id)  # noqa: E731
    assert edge(g, 0).from_ == idx("B")
    assert edge(g, 0).to == idx("A")
    assert edge(g, 0).head_to == Head.ARROW
    assert edge(g, 0).head_from == Head.CIRCLE
    assert edge(g, 1).from_ == idx("D")
    assert edge(g, 1).to == idx("C")
    assert edge(g, 1).head_from == Head.CROSS
    plain_rev = plain("graph TD\n A <--o B")
    lines = _lines(plain_rev)
    row = lambda needle: _position(lines, lambda l: needle in l)  # noqa: E731
    assert row("B") < row("A"), f"ranks match plain <-- reversal:\n{plain_rev}"


def test_both_end_markers_parse():
    g = parse_graph("graph TD\n A o--o B\n C x--x D")
    assert g is not None
    assert edge(g, 0).head_from == Head.CIRCLE
    assert edge(g, 0).head_to == Head.CIRCLE
    assert edge(g, 1).head_from == Head.CROSS
    assert edge(g, 1).head_to == Head.CROSS
    assert len(g.nodes) == 4


def test_dotted_and_thick_lines_render_distinctly():
    dotted = plain("graph TD\n A -.-> B")
    assert "╎" in dotted, f"dotted vertical:\n{dotted}"
    thick = plain("graph TD\n A ==> B")
    assert "┃" in thick, f"thick vertical:\n{thick}"
    solid = plain("graph TD\n A --> B")
    assert "╎" not in solid and "┃" not in solid, f"solid unchanged:\n{solid}"


def test_dotted_label_form_renders_dashed():
    out = plain("graph LR\n A -. maybe .-> B")
    assert "╌" in out, out
    assert "maybe" in out, out


def test_thick_jog_uses_thick_corners():
    out = plain("graph TD\n A[aaaaaaa] ==> B\n A ==> C[ccccccc]")
    assert "┏" in out or "┓" in out or "┳" in out, f"thick corners on jog:\n{out}"
