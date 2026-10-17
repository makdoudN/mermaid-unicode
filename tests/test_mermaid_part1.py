"""Port of the Rust unit tests in ``mermaid.rs`` (``mod tests``, first half).

Source: crates/codegen/xai-grok-markdown/src/mermaid.rs lines 4053-4704 of xai-org/grok-build.
One Python test function per Rust ``#[test]``, same name, same assertions and messages.
"""
from __future__ import annotations

from mermaid_unicode.mermaid import (
    CONT,
    LABEL_BREAK_CHARS,
    MAX_LINES,
    WRAP_WIDTH,
    ClassInfo,
    Dir,
    Edge,
    Graph,
    Head,
    MermaidStyles,
    Node,
    SeqDivider,
    SeqMessage,
    SeqNote,
    compute_ranks,
    count_crossings,
    decode_html_entities,
    order_ranks,
    parse_class,
    parse_graph,
    parse_sequence,
    parse_state,
    push_er_attribute,
    push_member,
    render,
    wrap_label,
)
from mermaid_unicode.unicode_width import str_width


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
    assert i < len(xs), f"index {i} out of bounds for {xs!r}"
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


# ---------------------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------------------
def test_parses_nodes_edges_and_direction():
    g = parse_graph("flowchart LR\n  A[Start] --> B[End]")
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert node(g, 0).label == "Start"
    assert node(g, 1).label == "End"
    assert g.dir == Dir.RIGHT


def test_non_flowchart_returns_none_from_parse():
    assert parse_graph("sequenceDiagram\n  A->>B: hi") is None


def test_html_tags_are_stripped_from_labels():
    g = parse_graph('flowchart TD\n  A["<b>Bold</b> and <i>italic</i>"] --> B')
    assert g is not None
    assert node(g, 0).label == "Bold and italic"


def test_br_tag_becomes_a_line_break():
    # Upstream turns <br> into a space; this port keeps it as a hard line break in node labels
    # (see README, "Line breaks in labels"). Edge labels and titles still get the upstream space.
    g = parse_graph('flowchart TD\n  A["Line1<br/>Line2<br>Line3"]')
    assert g is not None
    assert node(g, 0).label == "Line1\nLine2\nLine3"


def test_markdown_string_strips_bold_italic_and_code():
    g = parse_graph(
        'flowchart TD\n  A["`**Start** here`"] --> B["`Save to **database**`"]\n  B --> C["`**Done!**`"]',
    )
    assert g is not None
    assert node(g, 0).label == "Start here"
    assert node(g, 1).label == "Save to database"
    assert node(g, 2).label == "Done!"


def test_markdown_string_preserves_snake_case_and_strips_inline_code():
    g = parse_graph('flowchart TD\n  A["`_italic_ uses `vocab_size` with __all__`"]')
    assert g is not None
    assert node(g, 0).label == "italic uses vocab_size with all"


def test_markdown_string_edge_label_is_stripped():
    g = parse_graph('flowchart TD\n  A -->|"`**yes**`"| B\n  A -->|"`__no__`"| C')
    assert g is not None
    assert edge(g, 0).label == "yes"
    assert edge(g, 1).label == "no"


def test_plain_label_keeps_literal_text_and_underscores():
    # Not a markdown string (no backtick wrapper): Mermaid renders it literally, so brackets,
    # snake_case, and any `*`/`_` must survive
    g = parse_graph('flowchart TD\n  A["[ 464, 3797 ] seq_len d_model"]')
    assert g is not None
    assert node(g, 0).label == "[ 464, 3797 ] seq_len d_model"


def test_code_and_span_tags_are_stripped():
    g = parse_graph(
        'flowchart TD\n  A["<code>vocab_size</code> <span style=\\"color:red\\">x</span>"]',
    )
    assert g is not None
    assert node(g, 0).label == "vocab_size x"


def test_bare_angle_brackets_are_kept():
    g = parse_graph('flowchart TD\n  A["a < b and c > d"]')
    assert g is not None
    assert node(g, 0).label == "a < b and c > d"


def test_generic_types_are_not_stripped_as_html():
    # `<String>` / `<i32>` / `<id>` look like tags but are not HTML formatting tags, so they must
    # survive. Only b/i/code/span/… etc. and <br> are stripped.
    g = parse_graph(
        'flowchart TD\n  A["Returns Vec<String>"] --> B["Option<i32> for <id>"]',
    )
    assert g is not None
    assert node(g, 0).label == "Returns Vec<String>"
    assert node(g, 1).label == "Option<i32> for <id>"


def test_decode_html_entities_covers_named_numeric_and_double_escape():
    assert (
        decode_html_entities("&lt;a&gt; &amp; &quot;x&quot; &apos;y&apos;")
        == "<a> & \"x\" 'y'"
    )
    assert decode_html_entities("it&#39;s &#60;ok&#62;") == "it's <ok>"
    assert decode_html_entities("&#x3c;tag&#X3E; &#x27;q&#x27;") == "<tag> 'q'"
    # `&amp;lt;` must yield the literal `&lt;`, never `<`.
    assert decode_html_entities("&amp;lt;") == "&lt;"
    assert decode_html_entities("a &foo; b & c") == "a &foo; b & c"
    # Control chars (NUL collides with CONT, ESC injects ANSI) never decode.
    assert decode_html_entities("a&#27;b&#0;c") == "a&#27;b&#0;c"
    assert decode_html_entities("x&#x1b;y") == "x&#x1b;y"


def test_entity_escaped_flowchart_label_decodes_in_box_art():
    src = (
        'flowchart LR\n  YAML["models-config/&lt;model&gt;/&lt;env&gt;.yaml\\nenterprise_api_config:"]'
        '\n  PY["model_config_map.py\\nlanguage_model_dict_to_proto()"]\n  YAML --> PY'
    )
    g = parse_graph(src)
    assert g is not None
    assert "models-config/<model>/<env>.yaml" in node(g, 0).label, node(g, 0).label
    art = plain(src)
    assert "<model>" in art and "<env>" in art, art
    assert "&lt;" not in art and "&gt;" not in art, art


def test_direct_push_sinks_decode_entities():
    # Entities contain `;`, which split_statements treats as a separator, so they reach a sink
    # intact only inside quotes. Assert through the real parsers where such quoting works.
    g = parse_state(
        'stateDiagram-v2\n  state "work &lt;job&gt;" as J\n  Idle --> Run: "on &lt;go&gt;"\n  Run: "d &lt;e&gt;"',
    )
    assert g is not None

    def node_has(s: str) -> bool:
        return any(s in n.label for n in g.nodes)

    def edge_has(s: str) -> bool:
        return any(e.label is not None and s in e.label for e in g.edges)

    assert node_has("work <job>") and node_has("d <e>") and edge_has("on <go>")
    assert not node_has("&lt;") and not edge_has("&lt;")

    parsed = parse_class('classDiagram\n  A --> B : "uses &lt;X&gt;"')
    assert parsed is not None
    cg, _ = parsed
    assert any(
        e.label is not None and "uses <X>" in e.label and "&lt;" not in e.label
        for e in cg.edges
    )

    s = parse_sequence(
        'sequenceDiagram\n  A->>B: "call &lt;svc&gt;"\n  Note over A,B: "memo &lt;o&gt;"\n  alt "c &lt;x&gt;"\n    A->>B: ok\n  end',
    )
    assert s is not None
    assert any(
        isinstance(it, SeqMessage)
        and it.text is not None
        and "call <svc>" in it.text
        and "&lt;" not in it.text
        for it in s.items
    )
    assert any(
        isinstance(it, SeqNote) and "memo <o>" in it.text and "&lt;" not in it.text
        for it in s.items
    )
    assert any(
        isinstance(it, SeqDivider) and "c <x>" in it.text and "&lt;" not in it.text
        for it in s.items
    )

    # Class members and ER attributes have no clean quoted form (splitter fragments unquoted `;`;
    # ER drops quoted text as a comment). Exercise those decodes directly at push_member and
    # push_er_attribute.
    member = ClassInfo()
    push_member(member, "+run &lt;R&gt;")
    assert member.attrs == ["+run <R>"]
    attr = ClassInfo()
    push_er_attribute(attr, "string &lt;pk&gt;")
    assert attr.attrs == ["string <pk>"]


def test_quoted_label_with_inner_brackets_is_one_node():
    g = parse_graph(
        'flowchart TD\n  IDs["<b>Token IDs</b><br/>[ 464, 3797 ]<br/><i>indices</i>"]',
    )
    assert g is not None
    assert len(g.nodes) == 1, "inner brackets must not split the node"
    assert len(g.edges) == 0, "no phantom edges from <br/> + brackets"
    # <br/> is a hard line break here (upstream: a space), see test_br_tag_becomes_a_line_break
    assert node(g, 0).label == "Token IDs\n[ 464, 3797 ]\nindices"


def test_unquoted_label_with_embedded_quote_closes_at_bracket():
    g = parse_graph('flowchart TD\n  A[5" pipe] --> B[24" display]')
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert node(g, 0).label == '5" pipe'
    assert node(g, 1).label == '24" display'


def test_quoted_label_with_inner_parens_is_one_node():
    g = parse_graph('flowchart TD\n  A["Tokenizer (BPE / WordPiece)"] --> B[Done]')
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert node(g, 0).label == "Tokenizer (BPE / WordPiece)"


def test_diagram_with_html_labels_renders_without_tag_artifacts():
    src = 'flowchart TD\n  IDs["<b>3. Token IDs</b><br/>[ 464, 3797 ]<br/><i>indices</i>"] --> Out["<b>done</b>"]'
    out = plain(src)
    assert "<b>" not in out, f"raw HTML tag leaked:\n{out}"
    assert "</" not in out, f"raw closing tag leaked:\n{out}"
    assert "br/" not in out, f"phantom br artifact leaked:\n{out}"
    assert "Token IDs" in out, f"label text missing:\n{out}"


def test_ranks_ignore_back_edges():
    g = parse_graph("graph TD\n A-->B\n B-->C\n C-->A")
    assert g is not None
    r = compute_ranks(g)

    def idx(id: str) -> int:
        return index_of(g, id)

    assert at(r, idx("A")) == 0
    assert at(r, idx("B")) == 1
    assert at(r, idx("C")) == 2


def test_td_render_has_boxes_labels_and_arrow():
    out = plain("graph TD\n A[Start] --> B[End]")
    assert "Start" in out, out
    assert "End" in out, out
    assert "┌" in out or "╭" in out, out
    assert "▼" in out, out


def test_edge_label_is_rendered():
    out = plain("graph TD\n A-->|yes| B")
    assert "yes" in out, out


def test_lr_is_shorter_than_td_for_a_chain():
    chain = "A --> B --> C --> D"
    td_art = render(f"graph TD\n {chain}", styles(), 120)
    assert td_art is not None
    td = len(td_art.plain_lines)
    lr_art = render(f"flowchart LR\n {chain}", styles(), 120)
    assert lr_art is not None
    lr = len(lr_art.plain_lines)
    assert lr < td, f"expected LR ({lr}) shorter than TD ({td})"


def test_unsupported_diagram_uses_fallback_box():
    out = plain("gantt\n title Plan\n section A\n task :a1, 2024-01-01, 30d")
    assert "mermaid: gantt" in out, out
    assert "Plan" in out, out


def test_blank_source_returns_none():
    assert render("   \n  ", styles(), 80) is None


def test_inline_label_with_x_or_o_letters():
    g = parse_graph("graph TD\n A -- no exit --> B")
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert edge(g, 0).label == "no exit"


def test_wide_glyph_box_stays_aligned():
    art = render("graph TD\n A[日本語ab]", styles(), 120)
    assert art is not None
    lines = art.plain_lines
    widths = [str_width(l) for l in lines if l.strip() != ""]
    assert all(
        a == b for a, b in zip(widths, widths[1:])
    ), f"box rows must share one width: {widths!r}\n{lines!r}"
    assert not any(CONT in l for l in lines), "sentinel leaked"


def test_merge_has_single_arrowhead():
    out = plain("graph TD\n A[aaa] --> D[ddddddd]\n B[bb] --> D\n C[ccccc] --> D")
    arrows = sum(1 for c in out if c == "▼")
    assert arrows == 1, f"merge edges share one arrowhead:\n{out}"
    assert "▼▼" not in out, f"must not stack arrowheads:\n{out}"


def test_long_label_wraps_without_truncation():
    out = plain("graph TD\n A[Check if the user has permission to access resource] --> B[Done]")
    assert "permission" in out, out
    assert "resource" in out, out
    assert "…" not in out, f"should wrap, not truncate:\n{out}"


def test_very_long_label_truncates_after_max_lines():
    long = "alpha " * 40
    out = plain(f"graph TD\n A[{long.strip()}] --> B[x]")
    assert "…" in out, f"should truncate past max lines:\n{out}"


def test_wrap_label_breaks_long_identifier_on_boundary():
    lines = wrap_label("mark_filter_restore_context", WRAP_WIDTH, MAX_LINES)
    # The first line ends on an identifier boundary, not a mid-segment slice.
    assert len(lines) > 0 and lines[0].endswith("_"), (
        f"first line must end on a boundary: {lines!r}"
    )
    # Every break (all but the last line) lands on a boundary char.
    assert len(lines) >= 1, f"expected wrapped lines, got {lines!r}"
    prefix = lines[: len(lines) - 1]
    for line in prefix:
        assert line.endswith(LABEL_BREAK_CHARS), f"line must break on a boundary: {line!r}"
    # Nothing is lost: the wrapped lines reconstruct the original word.
    assert "".join(lines) == "mark_filter_restore_context"


def test_wrap_label_token_without_break_char_falls_back_per_char():
    token = "a" * 40
    lines = wrap_label(token, WRAP_WIDTH, MAX_LINES)
    # The token has no boundary char, so the wrap hard-breaks per char across multiple lines
    assert len(lines) >= 2, f"must hard-break: {lines!r}"
    # 40 narrow chars fit in MAX_LINES or fewer lines, so nothing is truncated or lost
    assert "".join(lines) == token


def test_flowchart_long_identifier_breaks_on_boundary_not_mid_segment():
    out = plain("graph TD\n A[mark_filter_restore_context] --> B[Done]")
    # The boundary-respecting pieces are present in the rendered art.
    # `wrap_label_breaks_long_identifier_on_boundary` proves the break is on a boundary and
    # lossless, so no exact-offset check here.
    assert "mark_filter_restore_" in out, out
    assert "context" in out, out


def test_wrap_label_mixed_boundary_then_no_boundary_tail():
    token = "ab_" + "c" * 40
    lines = wrap_label(token, WRAP_WIDTH, MAX_LINES)
    # The boundary is taken first ...
    assert len(lines) > 0 and lines[0].endswith("_"), f"first break on boundary: {lines!r}"
    # ... then the long no-boundary tail falls back to a per-char break.
    assert any(
        not any(c in l for c in LABEL_BREAK_CHARS) for l in lines[1:]
    ), f"a later line must be a per-char break: {lines!r}"
    # 43 cols is less than MAX_LINES*WRAP_WIDTH, so it must not truncate; fully lossless
    assert "".join(lines) == token


def test_wrap_label_boundary_breaking_still_truncates_at_max_lines():
    id = "_".join(["segment"] * 20)
    lines = wrap_label(id, WRAP_WIDTH, MAX_LINES)
    # The identifier far exceeds MAX_LINES*WRAP_WIDTH, so it truncates ...
    assert len(lines) == MAX_LINES
    # ... with the ellipsis still on the final line.
    assert lines[-1].endswith("…"), f"truncation must keep the ellipsis: {lines!r}"


def test_bt_flips_orientation():
    out = plain("flowchart BT\n A[first] --> B[second] --> C[third]")
    lines = out.split("\n")

    def row(needle: str) -> int:
        hits = [i for i, l in enumerate(lines) if needle in l]
        assert hits, f"{needle!r} not found in:\n{out}"
        return hits[0]

    assert row("third") < row("first"), f"BT: 'third' should sit above 'first':\n{out}"


def test_rl_flips_orientation():
    out = plain("flowchart RL\n A[first] --> B[second] --> C[third]")
    matches = [l for l in out.split("\n") if "first" in l]
    assert matches, out
    line = matches[0]
    # Rust compares `Option<usize>` (None < Some); Python's -1 for "not found" orders the same way
    assert line.find("third") < line.find("first"), (
        f"RL: 'third' should sit left of 'first':\n{out}"
    )


def test_undirected_piped_label_has_no_arrowhead():
    out = plain("graph TD\n A ---|maybe| B")
    assert "maybe" in out, out
    assert "▼" not in out, f"undirected link should not draw an arrow:\n{out}"


def test_chain_edges_are_straight():
    out = plain("graph TD\n A[aaaa] --> B[b] --> C[cccccccc]")
    for line in out.split("\n"):
        assert "└" not in line or "┐" not in line, f"chain should not jog: {line!r}"


def test_adversarial_chain_falls_back():
    src = "graph TD\n"
    for i in range(10_000):
        src += f" N{i} --> N{i + 1}\n"
    out = plain(src)
    assert "mermaid: graph" in out, f"expected fallback:\n{out}"


def test_single_statement_chain_over_cap_falls_back():
    src = "graph LR\n "
    for i in range(10_000):
        src += f"N{i}-->"
    src += "N10000"
    out = plain(src)
    assert "mermaid: graph" in out, "expected fallback"


def test_deep_chain_within_caps_renders():
    src = "graph TD\n"
    for i in range(100):
        src += f" N{i} --> N{i + 1}\n"
    art = render(src, styles(), 200)
    assert art is not None
    out = art.plain_lines
    joined = "\n".join(out)
    assert "N0" in joined, joined
    assert "N100" in joined, joined
    assert "▼" in joined, joined


def test_fallback_styled_and_plain_widths_match():
    art = render("gantt\n title Plan\n a\n", styles(), 120)
    assert art is not None
    assert len(art.styled_lines) == len(art.plain_lines)
    assert len(art.plain_lines) > 0, "expected framed lines"
    first = art.plain_lines[0]
    frame_w = str_width(first)
    for styled, plain_line in zip(art.styled_lines, art.plain_lines):
        styled_w = sum(str_width(s.content) for s in styled.spans)
        assert styled_w == str_width(plain_line), "styled/plain widths diverge"
        assert str_width(plain_line) == frame_w, "fallback box must be rectangular"


def test_over_wide_diagram_falls_back():
    src = "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]"
    art = render(src, styles(), 40)
    assert art is not None
    out = art.plain_lines
    joined = "\n".join(out)
    assert "mermaid: flowchart" in joined, f"expected fallback for over-wide diagram:\n{joined}"
    max_w = max((str_width(l) for l in out), default=0)
    fits_art = render(src, styles(), 120)
    assert fits_art is not None
    fits = fits_art.plain_lines
    assert any("▶" in l for l in fits), "same diagram should render when it fits"
    assert max_w <= len(src.encode("utf-8")), "fallback width bounded by source"


def test_too_wide_fallback_appends_hint_below_box():
    src = "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]"
    art = render(src, styles(), 40)
    assert art is not None
    out = art.plain_lines
    joined = "\n".join(out)

    assert "mermaid: flowchart" in joined, f"plain header:\n{joined}"
    assert "(too wide)" not in joined, f"header stays plain:\n{joined}"
    assert "flowchart LR" in joined, f"raw source kept:\n{joined}"

    bottoms = [i for i, l in enumerate(out) if "╰" in l]
    assert bottoms, "box bottom"
    bottom = bottoms[0]
    notes = [i for i, l in enumerate(out) if "too wide" in l]
    assert notes, "note row"
    note = notes[0]
    assert note > bottom, f"note must be below the box:\n{joined}"
    assert "open the image" in joined, f"note points at the image:\n{joined}"

    assert all(str_width(l) <= 40 for l in out), f"fits 40 cols:\n{joined}"


def test_unsupported_diagram_fallback_not_flagged_too_wide():
    out = plain("gantt\n title Plan\n section A\n task :a1, 2024-01-01, 30d")
    assert "mermaid: gantt" in out, out
    assert "too wide" not in out, f"unsupported type is not a width problem:\n{out}"


def test_fitting_diagram_has_no_width_warning():
    out = plain("flowchart LR\n A[Start] --> B[End]")
    assert "too wide" not in out, f"fitting diagram must not warn:\n{out}"
    assert "mermaid: flowchart" not in out, f"should draw art, not box:\n{out}"
    assert "▶" in out, f"should draw edges:\n{out}"


def test_bidirectional_link_draws_both_arrowheads():
    lr = plain("flowchart LR\n A <--> B")
    assert "◄" in lr and "▶" in lr, lr
    td = plain("graph TD\n A <--> B")
    assert "▲" in td and "▼" in td, td


def test_reversed_arrow_swaps_edge_direction():
    g = parse_graph("graph TD\n A <-- B")
    assert g is not None

    def idx(id: str) -> int:
        return index_of(g, id)

    assert len(g.edges) == 1
    assert edge(g, 0).from_ == idx("B")
    assert edge(g, 0).to == idx("A")
    assert edge(g, 0).head_to == Head.ARROW
    assert edge(g, 0).head_from == Head.NONE
    out = plain("graph TD\n A <-- B")
    lines = out.split("\n")

    def row(needle: str) -> int:
        hits = [i for i, l in enumerate(lines) if needle in l]
        assert hits, f"{needle!r} not found in:\n{out}"
        return hits[0]

    assert row("B") < row("A"), f"B should rank above A:\n{out}"


def test_semicolon_and_comment_survive_inside_quoted_label():
    g = parse_graph('graph TD\n A["wait; 50%% done"] --> B')
    assert g is not None
    assert len(g.nodes) == 2
    assert node(g, 0).label == "wait; 50%% done"


def test_comment_outside_quotes_is_stripped():
    g = parse_graph("graph TD %% main flow\n A --> B %% trailing\n %% full line\n")
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1


def test_skip_edge_routes_around_intermediate_boxes():
    out = plain("graph TD\n A --> B\n B --> C\n A --> C")
    assert "┼" not in out, f"no border corruption:\n{out}"
    assert "◄" in out, f"skip edge enters target from lane:\n{out}"
