//! Differential-test driver (added locally): reads cases from stdin, prints results.
//! Input format: repeated `@@CASE <width|none>\n<src...>\n@@END\n`.
//! Output format: `@@CASE\n@@NONE` or `@@CASE\n<plain>\n@@STYLED\n<styled>\n@@END`.
use std::io::Read;

fn main() {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("stdin");
    let mut out = String::new();
    let mut lines = input.split('\n');
    while let Some(line) = lines.next() {
        let Some(hdr) = line.strip_prefix("@@CASE ") else { continue };
        let width: Option<usize> = hdr.trim().parse().ok();
        let mut src = String::new();
        let mut first = true;
        for l in lines.by_ref() {
            if l == "@@END" { break; }
            if !first { src.push('\n'); }
            first = false;
            src.push_str(l);
        }
        out.push_str("@@CASE\n");
        match xai_grok_markdown::mermaid_dump::dump(&src, width) {
            None => out.push_str("@@NONE\n"),
            Some((plain, styled)) => {
                for p in &plain { out.push_str(p); out.push('\n'); }
                out.push_str("@@STYLED\n");
                for s in &styled { out.push_str(s); out.push('\n'); }
            }
        }
        out.push_str("@@END\n");
    }
    print!("{out}");
}
