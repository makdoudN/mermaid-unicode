"""Generate mermaid_unicode/_uw_tables.py from the Rust dumps (unicode-width 0.2.0 + Rust std char props)."""
import sys
uw_path, props_path, out_path = sys.argv[1:4]

starts, ends, widths, infos = [], [], [], []
preds = {}
with open(uw_path) as f:
    for line in f:
        line = line.rstrip("\n")
        if not line or line.startswith("@"):
            continue
        parts = line.split(" ")
        if len(parts) == 4 and all(p.strip() for p in parts) and not parts[0].startswith(("is_", "starts_", "single_")):
            s, e, w, i = parts
            starts.append(int(s, 16)); ends.append(int(e, 16)); widths.append(int(w)); infos.append(int(i))
        else:
            name = parts[0]
            rngs = []
            for tok in parts[1:]:
                if not tok:
                    continue
                a, b = tok.split("-")
                rngs.append((int(a, 16), int(b, 16)))
            preds[name] = rngs
with open(props_path) as f:
    for line in f:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        preds["std_" + name] = [tuple(int(x, 16) for x in tok.split("-")) for tok in parts[1:]]

def fmt_list(name, vals, per_line=16):
    out = [f"{name} = ("]
    for i in range(0, len(vals), per_line):
        out.append("    " + ", ".join(str(v) for v in vals[i:i + per_line]) + ",")
    out.append(")")
    return "\n".join(out)

lines = [
    '"""Generated tables: DO NOT EDIT.',
    "",
    "Derived from unicode-width 0.2.0 (Unicode 15.1.0) `lookup_width`/predicates and from",
    "Rust std `char` property methods, dumped with a Rust toolchain so the Python port",
    "matches the Rust reference bit-for-bit.",
    '"""',
    "",
    "UNICODE_VERSION = (15, 1, 0)",
    "",
    "# Run-length encoded `lookup_width(c) -> (width, WidthInfo)`. LW_STARTS is sorted; entry i",
    "# covers codepoints LW_STARTS[i]..=LW_ENDS[i].",
    fmt_list("LW_STARTS", starts),
    fmt_list("LW_ENDS", ends),
    fmt_list("LW_WIDTH", widths),
    fmt_list("LW_INFO", infos),
    "",
]
for name, rngs in preds.items():
    flat_s = [a for a, _ in rngs]
    flat_e = [b for _, b in rngs]
    lines.append(f"# predicate `{name}`: inclusive ranges")
    lines.append(fmt_list(name.upper() + "_STARTS", flat_s))
    lines.append(fmt_list(name.upper() + "_ENDS", flat_e))
    lines.append("")
with open(out_path, "w") as f:
    f.write("\n".join(lines))
print("entries", len(starts), "preds", {k: len(v) for k, v in preds.items()})
