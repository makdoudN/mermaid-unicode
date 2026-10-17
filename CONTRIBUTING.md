# Contributing

## Set up

```sh
git clone https://github.com/makdoudN/mermaid-unicode.git && cd mermaid-unicode
uv sync --group dev
uv run python -m pytest tests -q          # or: python3 tests/run_tests.py (no pytest needed)
uv tool install --reinstall .             # refresh the installed CLI after editing the source
```

Behind a corporate proxy that re-signs TLS, add `--native-tls` to the `uv` commands.

## Repository layout

| Path | Contents |
| --- | --- |
| `mermaid_unicode/mermaid.py` | the renderer: parsers, layout and painting, ported line by line from `mermaid.rs` |
| `mermaid_unicode/unicode_width.py`, `_uw_tables.py` | display-width rules (port of the `unicode-width` crate) and generated tables |
| `mermaid_unicode/rstr.py` | Rust `str` / `char` semantics the renderer relies on |
| `mermaid_unicode/ansi.py` | ANSI SGR output and the CLI's default color theme |
| `mermaid_unicode/cli.py` | the Typer command line (`render`, `markdown`, `inspect`, `examples`) |
| `mermaid_unicode/examples.py` | the built-in example diagrams |
| `tests/` | unit tests (see below) |
| `tools/` | differential harness, fuzz corpus, probes, table generator, screenshot generator |
| `docs/` | [FIDELITY.md](docs/FIDELITY.md) and the README screenshots |

## Tests

`tests/test_mermaid_part*.py` are the upstream Rust unit tests ported one-to-one (two `<br>`
assertions now expect a line break, and one over-wide sequence now wraps instead of falling
back; see [docs/FIDELITY.md](docs/FIDELITY.md)). `tests/test_line_breaks.py` and
`tests/test_layout_polish.py` cover the departures from upstream, `tests/test_options.py` the
`RenderOptions` knobs, `tests/test_cli.py` the command line and `tests/test_unicode_width.py`
the width tables.

Keep the rule that made the port trustworthy: anything that changes the output of an existing
case needs either a matching upstream change or an entry in `docs/FIDELITY.md` plus a test
under `tests/test_layout_polish.py` or `tests/test_line_breaks.py`.

## Differential harness against the Rust reference

`tests/test_differential.py` diffs the port against the Rust reference binary and is skipped
unless `MERMAID_DUMP_BIN` points at a build of `tools/rust_ref_src/mermaid_dump.rs`. To build
it:

1. Check out [grok-build](https://github.com/xai-org/grok-build) at commit `a28ee2b`.
2. Copy `tools/rust_ref_src/mermaid_dump.rs` into `crates/codegen/xai-grok-markdown/src/bin/`.
3. Append `tools/rust_ref_src/lib_rs_append.rs` to that crate's `src/lib.rs`.
4. `cargo build --release -p xai-grok-markdown --bin mermaid_dump`.
5. `MERMAID_DUMP_BIN=/path/to/mermaid_dump uv run python -m pytest tests -q`.

The harness renders with `UPSTREAM_LAYOUT = True` and skips sources that use the line-break
extension (`tools/py_ref.py: deviates_from_upstream`).

* `tools/diff_against_rust.py --seed N --count M` runs the fuzz corpus (`tools/corpus.py`)
  against the reference.
* `tools/check_case.py` checks a single source.
* `tools/probes.py` and `tools/critic_probes.json.gz` hold about 640 hand-written edge-case
  sources (cap boundaries, Unicode whitespace, entities, ZWJ emoji, ligatures, degenerate
  syntax) that the differential test also runs at widths from 0 to 200.

## Regenerating generated files

* **Unicode tables**: `tools/gen_tables.py`, fed by the dumps produced with
  `tools/rust_ref_src/charprops_main.rs` and `uwdump_main.rs`. `tools/uw_difftest.py` compares
  the Python width function with the Rust crate.
* **README screenshots** (`docs/img/*.png`): `uv run --with pillow python tools/readme_assets.py`.
  The images are drawn glyph by glyph on a fixed cell grid with a monospace font that has
  box-drawing glyphs (macOS Menlo by default, `--font PATH` for another). Regenerate them
  whenever an example diagram or the layout changes.

## Releasing a new version

1. Bump `version` in `pyproject.toml` and `__version__` in `mermaid_unicode/__init__.py`.
2. Run the tests.
3. Commit, tag `vX.Y.Z` and push the tag. `uv tool install git+https://github.com/makdoudN/mermaid-unicode.git@vX.Y.Z` then installs that exact version.
