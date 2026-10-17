# Fidelity to the upstream renderer

`mermaid-unicode` is a **1:1 port** of grok-build's terminal Mermaid renderer
(`crates/codegen/xai-grok-markdown/src/mermaid.rs`, Apache-2.0, upstream commit `a28ee2b`).
Same parsers, same layout algorithms, same glyphs, same fallbacks. The port is verified
**byte-for-byte against the Rust reference**: every `(source, width)` case in the differential
corpus produces identical plain lines and identical styled spans.

Two deliberate departures are on by default. Both are described below, and both are turned off
(or excluded) when the port is compared with the Rust binary.

Verification so far: the 145 upstream unit tests pass, and roughly 96,000 `(source, width)`
cases (fuzz corpus plus about 640 hand-written probes at widths from 0 to 200) match the Rust
output exactly on Python 3.11 through 3.14.

## Departure 1: line breaks in labels

Inside a flowchart node label, each of these is a hard line break, and the box gets one row per
line (each line still wraps at the wrap width):

* the two-character sequence `\n`, as commonly written inside quoted Mermaid labels;
* a `<br>` / `<br/>` tag (upstream turns it into a space);
* a real newline, when a `"quoted"` label continues on the next source line.

```text
$ mermaid-unicode examples flowchart-multiline
flowchart TD
    A["Player-day row\n(settled bets only)"] --> B{"Real money\n= TRUE ?"}
    B -- "No" --> F["GGR_FREE_MONEY<br/>freebets only"]
    B -- "Yes" --> R["GGR_REAL_MONEY
    cash bets only"]

         ┌─────────────────────┐
         │   Player-day row    │
         │ (settled bets only) │
         └──────────┬──────────┘
                    │
                    ▼
             ╭────────────╮
             │ Real money │
             │  = TRUE ?  │
             ╰──────┬─────╯
         ┌──────────┴─────────┐
         ▼ No                 ▼ Yes
┌────────────────┐   ┌────────────────┐
│ GGR_FREE_MONEY │   │ GGR_REAL_MONEY │
│ freebets only  │   │ cash bets only │
└────────────────┘   └────────────────┘
```

Text that is drawn on a single line (edge labels, subgraph titles, class/ER/sequence labels)
collapses the break into a space instead. A quoted label is only joined across lines when the
quote opens right after `[`, `(`, `{`, `|` or `>` and a later line closes it, so stray quotes
(`A[5" pipe]`) and unterminated ones parse exactly as upstream. Sources that use any of this are
excluded from the differential comparison (`tools/py_ref.py: deviates_from_upstream`).

## Departure 2: layout polish

Small departures from the upstream layout, on by default.
`mermaid_unicode.mermaid.UPSTREAM_LAYOUT = True` restores the exact upstream output (the
differential harness does this).

* **A blank column between an arrowhead and its label**: `▼ yes` instead of `▼yes`.
* **Edge labels routed through a side lane are never dropped.** Upstream right-aligned the
  uncapped label to the lane, so a long label started inside the target box and was silently
  skipped. The label now uses its capped width, sits on the row above the arrow, and moves to
  the row below (then one further out) when that row is already taken.
* **Edge labels may be 40 columns wide** before the `…` truncation (upstream: 28).
* **Sequence diagrams adapt to the width limit.** When the single-line layout is wider than
  `-w`, message, note and participant text wraps to 40, 32, 24, 20, 16, 12, 10 and finally 8
  columns until the diagram fits; a message that crosses several lifelines keeps using its
  whole span. Only when even that fails does the framed-source fallback appear. Without a
  limit, or when the diagram already fits, the layout is exactly upstream's.

```text
$ mermaid-unicode examples sequence-full -w 44
┌────────┐      ┌────────┐  ┌──────────┐
│ Client │      │ Server │  │ Database │
└────┬───┘      └────┬───┘  └─────┬────┘
     │               │            │
     │    1. GET     │            │
     │  /api/items   │            │
     ├──────────────▶│            │
     │               │            │
     │               │2. SELECT * │
     │               │ FROM items │
     │               ├───────────▶│
     │               │            │
     │               │  3. rows   │
     │               │◄╌╌╌╌╌╌╌╌╌╌╌┤
     │               │            │
     │   4. 200 OK   │            │
     │◄╌╌╌╌╌╌╌╌╌╌╌╌╌╌┤            │
     │               │            │
     ├──╮            │            │
     │  │ 5. render  │            │
     │  │ list       │            │
     │◄─╯            │            │
     │               │            │
   ┌───────────────────┐          │
   │    happy path     │          │
   └───────────────────┘          │
     │               │            │
── loop retry x3 ────────────────────────
     │               │            │
     │  6. timeout   │            │
     ├──────────────×│            │
     │               │            │
── end ──────────────────────────────────
     │               │            │
┌────┴───┐      ┌────┴───┐  ┌─────┴────┐
│ Client │      │ Server │  │ Database │
└────────┘      └────────┘  └──────────┘
```

`mermaid-unicode inspect FILE -w N` reports `fits by wrapping text (W × H)` when this kicks in.

## Render options

`RenderOptions(wrap_width=24, max_lines=4, align="center")` (the CLI's `-W` and `--align`)
are knobs on top of the upstream defaults. With the defaults the output is upstream's; the
differential harness never changes them.

## Why the port carries its own Unicode and Rust helpers

The Rust code depends on behaviour that Python's standard library does not reproduce exactly,
so the port carries its own helpers instead of the obvious Python equivalents:

* `mermaid_unicode/unicode_width.py`: a port of the `unicode-width` 0.2.0 crate (Unicode
  15.1.0), including the string-level state machine for `\r\n`, emoji ZWJ / modifier /
  presentation sequences and the script ligatures. `wcwidth`-style libraries differ from it.
* `mermaid_unicode/rstr.py`: Rust `str`/`char` semantics: `trim` on Unicode White_Space
  (not `str.isspace`), `split_whitespace`, `str::lines`, ASCII-only case folding,
  `parse::<u32>`, `char::from_u32`, `f64::round` (half away from zero), saturating `as usize`.
* `mermaid_unicode/_uw_tables.py`: generated from the Rust crate and from Rust `std`'s
  `char::is_alphanumeric` / `is_whitespace` tables (`tools/gen_tables.py`, dumped with
  `tools/rust_ref_src/*.rs`), so identifier and whitespace classification match Rust rather
  than Python's `unicodedata`.
* Floating-point relaxation in `assign_positions` / `relax_rank` keeps Rust's operation order
  (Python's `sum()` is compensated since 3.12 and is deliberately not used).

## Small CLI-only differences

* The CLI trims blank leading and trailing canvas rows. The Python API returns them, as
  upstream does.
* The CLI's default color theme (`mermaid_unicode.ansi.DEFAULT_STYLES`: dim borders and edges,
  italic edge labels, bold titles) is this project's choice; upstream takes its styles from
  the host TUI theme.
