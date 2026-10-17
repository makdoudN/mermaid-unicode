"""Line breaks inside labels: the port's one extension over the upstream Rust renderer.

A literal ``\\n`` (two characters), a ``<br>`` tag or a quoted label spanning several source lines
is a hard line break in a flowchart node label. Single-line text (edge labels, subgraph titles)
collapses the break to a space. See README, "Line breaks in labels".
"""
from mermaid_unicode import render_plain
from mermaid_unicode.mermaid import (
    MAX_LINES,
    WRAP_WIDTH,
    fit_label,
    join_quoted_lines,
    parse_graph,
    wrap_label,
)

PLAYER_DAY = '''    flowchart TD
        A["🎯 Player-day row\\n(BETTING.GOLD view, PT, settled bet)"]
        A --> B{"IS_UAP_REAL_MONEY\\n= TRUE ?"}

        B -- "No" --> C{"IS_UAP_FREE_MONEY\\n= TRUE ?"}
        C -- "No"  --> X["⚠️ Impossible row\\n(no settled bet → no row)"]
        C -- "Yes" --> FM["💸 GGR_FREE_MONEY\\nOnly freebets settled\\nSUM(GGR_AMOUNT_EURO)\\nwhere RM=F ∧ FM=T"]

        B -- "Yes" --> D{"IS_UAP_FREE_MONEY\\n= TRUE ?"}
        D -- "No"  --> RM["💰 GGR_REAL_MONEY\\nOnly cash bets settled\\nSUM(GGR_AMOUNT_EURO)\\nwhere RM=T ∧ FM=F"]
        D -- "Yes" --> MX["🔀 GGR_MIX_MONEY\\nCash + freebet same day\\nSUM(GGR_AMOUNT_EURO)\\nwhere RM=T ∧ FM=T\\n(cannot split
  further at this grain)"]

        RM --> S["Σ Total SBK GGR\\n= REAL + FREE + MIX\\n≈ GGR_EURO (FACT_PRODUCT, ID=1)"]
        FM --> S
        MX --> S

        style FM fill:#f0c040,color:#000
        style RM fill:#4caf50,color:#fff
        style MX fill:#2196f3,color:#fff
        style S  fill:#333,color:#fff
        style X  fill:#f44336,color:#fff'''


def _labels(g):
    assert g is not None
    return [n.label for n in g.nodes]


def _rows(src):
    art = render_plain(src)
    assert art is not None
    return [r for r in art.split("\n") if r.strip()]


# --- parsing ---------------------------------------------------------------------------------
def test_literal_backslash_n_in_quoted_node_label_is_a_hard_break():
    g = parse_graph('flowchart TD\n  A["first line\\nsecond line"]')
    assert _labels(g) == ["first line\nsecond line"]


def test_literal_backslash_n_in_unquoted_label_and_every_shape():
    g = parse_graph("flowchart TD\n  A[one\\ntwo] --> B(three\\nfour) --> C{five\\nsix} --> D((seven\\neight))")
    assert _labels(g) == ["one\ntwo", "three\nfour", "five\nsix", "seven\neight"]


def test_br_tag_in_node_label_is_a_hard_break():
    g = parse_graph('flowchart TD\n  A["Line1<br/>Line2<br>Line3<BR />Line4"]')
    assert _labels(g) == ["Line1\nLine2\nLine3\nLine4"]


def test_leading_and_trailing_breaks_are_trimmed():
    g = parse_graph('flowchart TD\n  A["\\nfoo\\n"] --> B["<br/>bar<br/>"]')
    assert _labels(g) == ["foo", "bar"]


def test_escaped_br_entity_stays_literal():
    g = parse_graph('flowchart TD\n  A["a &lt;br&gt; b"]')
    assert _labels(g) == ["a <br> b"]


def test_edge_label_breaks_collapse_to_spaces():
    # (`<br/>` inside an unpiped `-- text -->` label is not parseable upstream either: `<` and
    # `>` are link characters, so only the `|…|` form is exercised with a tag.)
    g = parse_graph('flowchart TD\n  A -->|"yes\\nplease"| B\n  B -->|no<br/>way| C\n  C -- one\\ntwo --> D')
    assert g is not None
    assert [e.label for e in g.edges] == ["yes please", "no way", "one two"]


def test_subgraph_title_breaks_collapse_to_spaces():
    g = parse_graph('flowchart TD\n  subgraph "one\\ntwo"\n    A\n  end\n  subgraph s [three\\nfour]\n    B\n  end')
    assert g is not None
    assert [grp.label for grp in g.groups] == ["one two", "three four"]


# --- quoted labels spanning source lines -----------------------------------------------------
def test_quoted_label_spanning_source_lines_is_one_node():
    g = parse_graph('flowchart TD\n  A["first\n  second"] --> B\n  B --> C')
    assert _labels(g) == ["first\n  second", "B", "C"]
    assert len(g.edges) == 2


def test_join_quoted_lines_needs_a_label_opener_and_a_closing_quote():
    # never closed: every line stays separate, exactly as upstream parses it
    lines = ["graph TD", '  A["oops', "  B --> C"]
    assert join_quoted_lines(lines) == lines
    # a stray quote inside an unquoted label is not a label opener
    lines = ["graph TD", '  A[5" pipe]', "  B --> C"]
    assert join_quoted_lines(lines) == lines
    # quotes inside a %% comment do not count
    lines = ["graph TD", '  A --> B %% see ["the', "  B --> C"]
    assert join_quoted_lines(lines) == lines
    # closes two lines later; the rest of the source is untouched
    lines = ["graph TD", '  A["one', "two", 'three"] --> B', "  B --> C"]
    assert join_quoted_lines(lines) == ["graph TD", '  A["one\ntwo\nthree"] --> B', "  B --> C"]
    # edge labels and every shape opener join too
    lines = ['  A -->|"yes', 'really"| B(("round', 'one"))']
    assert join_quoted_lines(lines) == ['  A -->|"yes\nreally"| B(("round\none"))']


def test_unterminated_quote_keeps_upstream_parsing():
    g = parse_graph('flowchart TD\n  A["oops\n  B --> C')
    assert g is not None
    assert len(g.nodes) == 3 and len(g.edges) == 1


def test_stray_quote_line_is_not_joined_with_the_next():
    g = parse_graph('flowchart TD\n  A[5" pipe]\n  B[24" display] --> C')
    assert _labels(g) == ['5" pipe', '24" display', "C"]


# --- wrapping and drawing ----------------------------------------------------------------------
def test_wrap_label_keeps_every_explicit_line():
    six = wrap_label("\n".join(f"line {i}" for i in range(6)), WRAP_WIDTH, MAX_LINES)
    assert six == [f"line {i}" for i in range(6)], "explicit breaks are not capped at MAX_LINES"
    assert wrap_label("a\n\nb", WRAP_WIDTH, MAX_LINES) == ["a", "", "b"]
    assert wrap_label("  padded  \n  words  ", WRAP_WIDTH, MAX_LINES) == ["padded", "words"]


def test_wrap_label_still_wraps_and_truncates_each_segment():
    lines = wrap_label("short\n" + " ".join(["word"] * 40), WRAP_WIDTH, MAX_LINES)
    assert lines[0] == "short"
    assert len(lines) == 1 + MAX_LINES and lines[-1].endswith("…")
    assert all(len(line) <= WRAP_WIDTH for line in lines)


def test_wrap_label_without_breaks_is_unchanged():
    assert wrap_label("Check if the user has permission", WRAP_WIDTH, MAX_LINES) == [
        "Check if the user has",
        "permission",
    ]


def test_fit_label_never_emits_a_raw_newline():
    assert fit_label("a\nb", 10) == "a b"
    assert fit_label("abc\ndef", 4) == "abc…"


def test_rendered_box_has_one_row_per_break():
    rows = _rows('flowchart TD\n  A["alpha\\nbeta\\ngamma"]')
    assert len(rows) == 5, rows  # top border, three text rows, bottom border
    assert "alpha" in rows[1] and "beta" in rows[2] and "gamma" in rows[3]
    assert "\\n" not in "\n".join(rows)


def test_player_day_diagram_renders_every_break():
    g = parse_graph(PLAYER_DAY)
    assert len(_labels(g)) == 9, "the two-line MX label must not spawn a `further` node"
    assert "further" not in _labels(g)
    art = render_plain(PLAYER_DAY)
    assert "\\n" not in art, art
    rows = art.split("\n")
    split_row = next(i for i, r in enumerate(rows) if "(cannot split" in r)
    assert "further at this grain)" in rows[split_row + 1], art
    assert "Only freebets settled" in art and "where RM=F ∧ FM=T" in art
