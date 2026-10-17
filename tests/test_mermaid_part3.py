"""Port of ``mod tests`` from grok-build's ``mermaid.rs`` (part 3: lines 5304-5699).

One Python test function per Rust ``#[test]``, same name, same assertions. The shared helpers
(``styles``/``node``/``edge``/``index_of``/``at``/``plain``/``ordered_ranks``) mirror the Rust
ones at the top of the Rust test module.
"""
from __future__ import annotations

from mermaid_unicode import rstr
from mermaid_unicode.mermaid import (
    CONT,
    Edge,
    Graph,
    MermaidStyles,
    Node,
    Shape,
    compute_ranks,
    order_ranks,
    parse_graph,
    parse_state,
    render,
)


# ---------------------------------------------------------------------------------------------
# Helpers (Rust: styles / node / edge / index_of / at / plain / ordered_ranks)
# ---------------------------------------------------------------------------------------------
def styles() -> MermaidStyles:
    """All `Style::default()`, like the Rust `styles()` helper."""
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


def _position(lines: list[str], needle: str) -> int:
    """`lines.iter().position(|l| l.contains(needle)).unwrap()`."""
    for i, l in enumerate(lines):
        if needle in l:
            return i
    raise AssertionError(f"no line contains {needle!r}")


def _rposition(lines: list[str], needle: str) -> int:
    """`lines.iter().rposition(|l| l.contains(needle)).unwrap()`."""
    for i in range(len(lines) - 1, -1, -1):
        if needle in lines[i]:
            return i
    raise AssertionError(f"no line contains {needle!r}")


# ---------------------------------------------------------------------------------------------
# State diagrams
# ---------------------------------------------------------------------------------------------
def test_state_diagram_renders_states_and_transitions():
    out = plain("stateDiagram-v2\n [*] --> Idle\n Idle --> Running: start\n Running --> [*]")
    assert "Idle" in out, out
    assert "Running" in out, out
    assert "start" in out, out
    assert "▼" in out, out
    assert out.count("●") == 2, f"distinct start and end markers:\n{out}"
    lines = rstr.lines(out)
    first_dot = _position(lines, "●")
    last_dot = _rposition(lines, "●")
    idle = _position(lines, "Idle")
    assert first_dot < idle and idle < last_dot, out


def test_state_v1_header_renders():
    out = plain("stateDiagram\n A --> B")
    assert "▼" in out, out


def test_state_boxes_are_rounded():
    out = plain("stateDiagram-v2\n A --> B")
    assert "╭" in out, out
    assert "┌" not in out, f"states render rounded:\n{out}"


def test_state_alias_label_renders():
    out = plain('stateDiagram-v2\n state "Waiting for input" as W\n W --> Done')
    assert "Waiting for input" in out, out


def test_state_choice_parses_as_diamond():
    g = parse_state("stateDiagram-v2\n state c <<choice>>\n A --> c\n c --> B: yes\n c --> D: no")
    assert g is not None
    assert node(g, index_of(g, "c")).shape == Shape.DIAMOND
    assert len(g.edges) == 3


def test_state_description_sets_label():
    out = plain("stateDiagram-v2\n s2 : waits patiently\n A --> s2")
    assert "waits patiently" in out, out


def test_state_direction_lr():
    out = plain("stateDiagram-v2\n direction LR\n A --> B --> C")
    td = plain("stateDiagram-v2\n A --> B")
    assert len(rstr.lines(out)) <= len(rstr.lines(td)) + 2, f"LR stays flat:\n{out}"
    line = next((l for l in rstr.lines(out) if "A" in l), None)
    assert line is not None
    assert "B" in line, f"A and B share a row in LR:\n{out}"


def test_state_composite_contents_render_flat():
    out = plain("stateDiagram-v2\n state Active {\n A --> B\n }\n Active --> Done")
    assert "Active" in out, out
    assert "A" in out and "B" in out, out
    assert "Done" in out, out


def test_state_notes_are_skipped():
    out = plain(
        "stateDiagram-v2\n A --> B\n note right of A: inline note\n note left of B\n block text\n end note"
    )
    assert "▼" in out, out
    assert "note" not in out, out
    assert "block text" not in out, out


def test_state_back_transition_uses_lane():
    out = plain("stateDiagram-v2\n A --> B\n B --> C\n C --> B: retry")
    assert "◄" in out, out
    assert "retry" in out, out


def test_state_unknown_statement_falls_back():
    out = plain("stateDiagram-v2\n A --> B\n some garbage line")
    assert "mermaid: stateDiagram-v2" in out, out


def test_state_over_cap_falls_back():
    src = "stateDiagram-v2\n"
    for i in range(600):
        src += f" S{i} --> S{i + 1}\n"
    out = plain(src)
    assert "mermaid: stateDiagram-v2" in out, out


def test_state_extra_dash_arrow_tolerated():
    g = parse_state("stateDiagram-v2\n A ---> B")
    assert g is not None
    assert len(g.edges) == 1
    assert len(g.nodes) == 2


def test_state_description_preserves_choice_shape():
    g = parse_state("stateDiagram-v2\n state c <<choice>>\n c : pick a path\n A --> c\n c --> B")
    assert g is not None
    assert node(g, index_of(g, "c")).shape == Shape.DIAMOND
    assert node(g, index_of(g, "c")).label == "pick a path"
    g2 = parse_state('stateDiagram-v2\n state c <<choice>>\n state "pick" as c\n A --> c')
    assert g2 is not None
    assert node(g2, index_of(g2, "c")).shape == Shape.DIAMOND
    assert node(g2, index_of(g2, "c")).label == "pick"


def test_state_chained_transitions_parse_as_separate_edges():
    g = parse_state("stateDiagram-v2\n A --> B --> C")
    assert g is not None
    assert len(g.nodes) == 3, "three distinct states"
    assert len(g.edges) == 2, "two edges"
    assert "B" in g.index
    assert "C" in g.index
    assert not any("-->" in n.label for n in g.nodes), "no node swallows the arrow"

    def idx(id: str) -> int:
        return index_of(g, id)

    assert any(e.from_ == idx("A") and e.to == idx("B") for e in g.edges)
    assert any(e.from_ == idx("B") and e.to == idx("C") for e in g.edges)


def test_state_chain_with_markers_and_label():
    g = parse_state("stateDiagram-v2\n [*] --> A --> B: done")
    assert g is not None
    assert len(g.edges) == 2
    assert any(e.label == "done" for e in g.edges)
    out = plain("stateDiagram-v2\n [*] --> A --> B: done")
    assert "●" in out, out
    assert "done" in out, out


def test_state_dangling_chain_falls_back():
    out = plain("stateDiagram-v2\n A --> B -->")
    assert "mermaid: stateDiagram-v2" in out, out


# ---------------------------------------------------------------------------------------------
# Sequence diagrams
# ---------------------------------------------------------------------------------------------
def test_sequence_renders_actors_and_messages():
    out = plain("sequenceDiagram\n Alice->>Bob: Hello Bob\n Bob-->>Alice: Hi Alice")
    assert "Alice" in out, out
    assert "Bob" in out, out
    assert "Hello Bob" in out, out
    assert "▶" in out, f"solid call arrow:\n{out}"
    assert "◄" in out, f"reply arrow:\n{out}"
    assert "╌" in out, f"reply line is dashed:\n{out}"
    assert out.count("│ Alice │") == 2, f"actor boxes repeat at bottom:\n{out}"


def test_sequence_participant_as_label():
    out = plain("sequenceDiagram\n participant C as Client\n participant S as Server\n C->>S: GET /")
    assert "Client" in out, out
    assert "Server" in out, out


def test_sequence_declared_order_wins():
    out = plain("sequenceDiagram\n participant B\n participant A\n A->>B: hi")
    lines = rstr.lines(out)
    assert len(lines) > 1
    line = lines[1]
    assert line.find("B") < line.find("A"), f"B declared first sits left:\n{out}"


def test_sequence_self_message_loops():
    out = plain("sequenceDiagram\n A->>A: think")
    assert "╮" in out, out
    assert "╯" in out, out
    assert "think" in out, out


def test_sequence_cross_head():
    out = plain("sequenceDiagram\n A-x B: lost")
    assert "×" in out, out


def test_sequence_note_over_renders_box():
    out = plain("sequenceDiagram\n A->>B: hi\n Note over A,B: happy path")
    assert "happy path" in out, out


def test_sequence_autonumber_prefixes_messages():
    out = plain("sequenceDiagram\n autonumber\n A->>B: one\n B->>A: two")
    assert "1. one" in out, out
    assert "2. two" in out, out


def test_sequence_loop_renders_divider_and_end():
    out = plain("sequenceDiagram\n A->>B: hi\n loop retry x3\n A->>B: again\n end")
    assert "loop retry x3" in out, out
    assert " end " in out, out


def test_sequence_rect_block_is_invisible():
    out = plain("sequenceDiagram\n rect rgb(0,0,0)\n A->>B: hi\n end")
    assert "rect" not in out, out
    assert " end " not in out, f"rect end is silent:\n{out}"


def test_sequence_box_end_does_not_close_enclosing_block():
    out = plain(
        "sequenceDiagram\n loop l1\n box g\n participant A\n end\n A->>B: hi\n A->>B: bye\n end"
    )
    assert out.count(" end ") == 1, f"box end is silent, loop end renders:\n{out}"
    lines = rstr.lines(out)

    def row(needle: str) -> int:
        return _position(lines, needle)

    assert row("loop l1") < row("hi") and row("bye") < row(" end "), (
        f"messages stay inside the loop:\n{out}"
    )
    assert "box" not in out, out


def test_sequence_critical_option_renders_dividers():
    out = plain("sequenceDiagram\n critical connect\n A->>B: try\n option timeout\n A->>A: log\n end")
    assert "critical connect" in out, f"valid critical diagram renders:\n{out}"
    assert "option timeout" in out, out
    assert " end " in out, out


def test_sequence_long_label_widens_gap():
    out = plain("sequenceDiagram\n A->>B: a very long message label that needs room\n B-->>A: ok")
    assert "a very long message label that needs room" in out, out


# ---------------------------------------------------------------------------------------------
# Flowchart edge styling / self loops
# ---------------------------------------------------------------------------------------------
def test_mixed_solid_and_dotted_bus_stays_light():
    out = plain("graph TD\n A --> C\n B -.-> C")
    assert "╌" in out, f"dotted branch survives:\n{out}"
    assert "─" in out, f"solid branch survives:\n{out}"
    assert "┬" in out, f"shared merge cell stays light:\n{out}"


def test_box_borders_stay_light_next_to_styled_edges():
    out = plain("graph TD\n A ==> B")
    assert "┌" in out and "└" in out, out
    assert "┏" not in out, f"borders not restyled:\n{out}"


def test_self_loop_renders_below_box():
    out = plain("graph TD\n A --> A")
    assert "╰" in out and "╯" in out, out
    assert "▲" in out, f"loop returns into the box:\n{out}"


def test_self_loop_label_renders():
    out = plain("graph TD\n A -->|again| A")
    assert "again" in out, out


def test_self_loop_coexists_with_forward_edge():
    out = plain("graph TD\n A --> A\n A --> B")
    assert "▲" in out, out
    assert "▼" in out, out
    assert "B" in out, out
    assert "┼" not in out, out


def test_self_loop_flips_with_bt():
    out = plain("flowchart BT\n A --> A\n A --> B")
    assert "▼" in out, f"flipped loop head points down:\n{out}"
    assert "╭" in out or "╮" in out, out


def test_self_loop_in_lr():
    out = plain("flowchart LR\n A --> A\n A --> B")
    assert "▲" in out, out
    assert "▶" in out, out


def test_inline_o_word_label_still_parses_as_label():
    g = parse_graph("graph TD\n A -- or else --> B")
    assert g is not None
    assert len(g.nodes) == 2
    assert edge(g, 0).label == "or else"


# ---------------------------------------------------------------------------------------------
# Sequence fallbacks and edge cases
# ---------------------------------------------------------------------------------------------
def test_sequence_unparseable_arrow_falls_back():
    out = plain("sequenceDiagram\n ->>B: orphan")
    assert "mermaid: sequenceDiagram" in out, out


def test_sequence_unknown_statement_falls_back():
    out = plain("sequenceDiagram\n A->>B: hi\n garbage statement here")
    assert "mermaid: sequenceDiagram" in out, out


def test_sequence_over_wide_falls_back():
    # Upstream falls back to the framed source here. The polished layout (README, "Layout
    # polish") wraps the message text to fit instead; the upstream behaviour is kept behind
    # `UPSTREAM_LAYOUT`, which is what this port of the upstream test checks.
    from mermaid_unicode import mermaid as m
    from mermaid_unicode.unicode_width import str_width

    src = "sequenceDiagram\n A->>B: this label is far wider than the available pane width"
    saved = m.UPSTREAM_LAYOUT
    m.UPSTREAM_LAYOUT = True
    try:
        art = render(src, styles(), 30)
    finally:
        m.UPSTREAM_LAYOUT = saved
    assert art is not None
    out = "\n".join(art.plain_lines)
    assert "mermaid: sequenceDiagram" in out, out

    polished = render(src, styles(), 30)
    assert polished is not None
    out = "\n".join(polished.plain_lines)
    assert "mermaid: sequenceDiagram" not in out and "▶" in out, out
    assert all(str_width(l) <= 30 for l in polished.plain_lines), out


def test_sequence_over_cap_falls_back():
    src = "sequenceDiagram\n"
    for i in range(600):
        src += f" A->>B: msg {i}\n"
    out = plain(src)
    assert "mermaid: sequenceDiagram" in out, out


def test_sequence_activation_markers_are_stripped():
    out = plain("sequenceDiagram\n A->>+B: call\n B-->>-A: return")
    assert "call" in out, out
    assert "return" in out, out
    assert "+" not in out, out


def test_sequence_rows_are_rectangular_and_sentinel_free():
    out = plain("sequenceDiagram\n Alice->>Bob: hi\n Note over Alice: solo note")
    assert CONT not in out, f"sentinel leaked:\n{out}"
    assert "solo note" in out, out
