"""Layout polish over the upstream renderer (README, "Layout polish"), and the switch that
restores the upstream layout for the differential harness."""
import contextlib

from mermaid_unicode import mermaid as m
from mermaid_unicode import render_plain
from mermaid_unicode.unicode_width import str_width

README_FLOW = (
    "graph TD\n  Start[Request received] --> Auth{Authenticated?}\n  Auth -->|yes| Rate{Rate limit OK?}\n"
    "  Auth -->|no| R401[401 Unauthorized]\n  Rate -->|yes| H(Handle request)\n"
    "  Rate -->|no| R429[429 Too Many Requests]\n  H -.-> Log[Audit log]\n  H ==> Resp[200 OK]\n"
)

DEPLOY_FLOW = """flowchart TD
    S[/ds-deploy-stage2 skill/] -.->|2 dispatch Publish| B[Build repo CI: feature/x]
    B -->|Publish| A[Artifactory: dags X.Y.Z-branch.sha7]
    A -->|stage2.yml release_version| M[models-management CI: 2 gates]
    M -->|render + s3 sync| W[MWAA stage2]
    S -.->|3 read version| A
    S -.->|4 push pin, 5 dispatch, 6 approve| M
"""

DEPLOY_SEQ = """sequenceDiagram
    participant You
    participant Skill
    participant CI as Build CI
    participant Art as Artifactory
    participant MM as models-mgmt CI
    participant MWAA as MWAA stage2
    You->>Skill: deploy feature/x to stage2
    Skill->>Skill: 1 preflight
    Skill->>CI: 2 dispatch Publish
    CI->>Art: tarball X.Y.Z-branch.sha7
    CI-->>Skill: green (~4 min)
    Skill->>Art: 3 tarball version
    Art-->>Skill: X.Y.Z-branch.sha7
    Skill->>MM: 4 push pin release_version (main)
    Skill->>MM: 5 dispatch release-to-dev-stage2
    MM->>MM: preview + terraform plan
    MM-->>Skill: gate 1 pending
    alt plan = No changes
        Skill->>MM: approve gate 1
    else plan has changes
        Skill-->>You: show plan, ask
        You->>Skill: yes
        Skill->>MM: approve gate 1
    end
    MM-->>Skill: gate 2 pending
    Skill->>MM: approve gate 2
    MM->>MWAA: render + s3 sync
    MM-->>Skill: success (~5 min)
    Skill-->>You: old -> new, branch, run URL
"""


@contextlib.contextmanager
def upstream_layout():
    old = m.UPSTREAM_LAYOUT
    m.UPSTREAM_LAYOUT = True
    try:
        yield
    finally:
        m.UPSTREAM_LAYOUT = old


def _rows(src, width=None):
    art = render_plain(src, width)
    assert art is not None
    return art.split("\n")


def _is_fallback(rows):
    return rows[0].startswith("╭ mermaid")


# --- flowchart labels ----------------------------------------------------------------------------
def test_forward_edge_label_has_a_space_after_the_arrowhead():
    out = "\n".join(_rows(README_FLOW))
    assert "▼ yes" in out and "▼ no" in out, out
    assert "▼yes" not in out and "▼no" not in out, out
    with upstream_layout():
        up = "\n".join(_rows(README_FLOW))
    assert "▼yes" in up and "▼no" in up, up


def test_long_back_edge_label_is_drawn_in_full_beside_its_lane():
    rows = _rows(DEPLOY_FLOW)
    out = "\n".join(rows)
    assert "4 push pin, 5 dispatch, 6 approve" in out, out
    assert "3 read version" in out and "2 dispatch Publish" in out, out
    row = next(r for r in rows if "4 push pin" in r)
    # the label sits between the target box and the lane with a blank column on each side
    assert "│ 4 push pin, 5 dispatch, 6 approve ╎" in row, row
    with upstream_layout():
        up = "\n".join(_rows(DEPLOY_FLOW))
    assert "4 push pin" not in up, "upstream dropped this label; the test would not prove anything"


def test_two_lane_labels_into_one_target_take_different_rows():
    src = (
        "graph TD\n  A --> B --> C --> D\n  A -.->|from A| D\n  B -.->|from B| D\n"
    )
    rows = _rows(src)
    ra = next(i for i, r in enumerate(rows) if "from A" in r)
    rb = next(i for i, r in enumerate(rows) if "from B" in r)
    assert ra != rb, "\n".join(rows)
    assert all(str_width(r) == len(r.rstrip()) for r in rows)


def test_edge_labels_cap_is_wider_than_upstream():
    label = "a" * 35
    src = f"graph TD\n  A -->|{label}| B\n"
    assert label in "\n".join(_rows(src))
    with upstream_layout():
        up = "\n".join(_rows(src))
    assert label not in up and "…" in up


# --- sequence diagrams adapt to the width limit ---------------------------------------------------
def test_wide_sequence_fits_the_width_limit_by_wrapping_text():
    full = _rows(DEPLOY_SEQ)
    assert max(str_width(r) for r in full) > 100
    rows = _rows(DEPLOY_SEQ, 100)
    assert not _is_fallback(rows), "\n".join(rows)
    assert max(str_width(r) for r in rows) <= 100
    out = "\n".join(rows)
    for word in ("deploy", "stage2", "tarball", "release_version", "terraform", "gate 1 pending", "URL"):
        assert word in out, f"{word!r} missing:\n{out}"
    assert "…" not in out, out
    assert out.count("┌") == 12, "six participants, top and bottom"


def test_sequence_without_a_limit_or_that_already_fits_is_the_upstream_layout():
    with upstream_layout():
        up = render_plain(DEPLOY_SEQ)
        up_fit = render_plain(DEPLOY_SEQ, 200)
    assert render_plain(DEPLOY_SEQ) == up
    assert render_plain(DEPLOY_SEQ, 200) == up_fit
    with upstream_layout():
        assert _is_fallback(_rows(DEPLOY_SEQ, 100))


def test_sequence_wraps_progressively_and_still_falls_back_when_hopeless():
    widths = {w: max(str_width(r) for r in _rows(DEPLOY_SEQ, w)) for w in (120, 90, 70)}
    assert widths[120] <= 120 and widths[90] <= 90 and widths[70] <= 70, widths
    assert _is_fallback(_rows(DEPLOY_SEQ, 30))


def test_wrapped_self_message_and_note_keep_their_shape():
    src = (
        "sequenceDiagram\n  participant A as Alpha\n  participant B as Beta\n"
        "  A->>A: run the full validation suite locally first\n"
        "  Note over A,B: this note is long enough to need wrapping at narrow widths\n"
        "  A->>B: ship\n"
    )
    rows = _rows(src, 40)
    out = "\n".join(rows)
    assert not _is_fallback(rows) and max(str_width(r) for r in rows) <= 40, out
    assert "╮" in out and "╯" in out and "◄" in out, out
    assert "validation" in out and "wrapping" in out and "ship" in out, out


def test_participant_names_wrap_instead_of_truncating_when_squeezed():
    src = (
        "sequenceDiagram\n  participant A as Payment Gateway Service\n"
        "  participant B as Notification Dispatcher\n  A->>B: notify\n"
    )
    rows = _rows(src, 34)
    out = "\n".join(rows)
    assert not _is_fallback(rows) and max(str_width(r) for r in rows) <= 34, out
    assert "Payment" in out and "Dispatcher" in out and "…" not in out, out
