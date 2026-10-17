#![allow(dead_code)]
mod tables;
use std::io::Read;
fn dump_pred(name: &str, pred: impl Fn(char) -> bool) {
    let mut ranges: Vec<(u32, u32)> = Vec::new();
    let mut start: Option<u32> = None;
    for cp in 0u32..=0x10FFFF {
        let hit = char::from_u32(cp).map(&pred).unwrap_or(false);
        match (hit, start) {
            (true, None) => start = Some(cp),
            (false, Some(s)) => { ranges.push((s, cp - 1)); start = None; }
            _ => {}
        }
    }
    if let Some(s) = start { ranges.push((s, 0x10FFFF)); }
    print!("{name} ");
    for (a, b) in ranges { print!("{a:x}-{b:x} "); }
    println!();
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("strs") {
        // each stdin line: hex codepoints separated by spaces → print str_width
        let mut input = String::new();
        std::io::stdin().read_to_string(&mut input).unwrap();
        for line in input.lines() {
            let s: String = line.split_whitespace().filter_map(|h| u32::from_str_radix(h, 16).ok()).filter_map(char::from_u32).collect();
            println!("{}", tables::str_width(&s));
        }
        return;
    }
    // lookup_width run-length table: start end width info
    println!("@lookup_width");
    let mut prev: Option<(u8, u16)> = None;
    let mut start = 0u32;
    for cp in 0u32..=0x110000 {
        let cur = if cp == 0x110000 { None } else { char::from_u32(cp).map(|c| { let (w, i) = tables::lookup_width(c); (w, i.0) }) };
        if cur != prev {
            if let Some(p) = prev { println!("{start:x} {:x} {} {}", cp - 1, p.0, p.1); }
            prev = cur;
            start = cp;
        }
    }
    dump_pred("is_transparent_zero_width", tables::is_transparent_zero_width);
    dump_pred("is_ligature_transparent", tables::is_ligature_transparent);
    dump_pred("starts_emoji_presentation_seq", tables::starts_emoji_presentation_seq);
    dump_pred("starts_non_ideographic_text_presentation_seq", tables::starts_non_ideographic_text_presentation_seq);
    dump_pred("is_emoji_modifier_base", tables::is_emoji_modifier_base);
    dump_pred("single_char_width_none", |c| tables::single_char_width(c).is_none());
}
