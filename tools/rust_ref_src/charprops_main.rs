// Dump Rust std char property ranges for exact Python emulation.
fn dump(name: &str, pred: impl Fn(char) -> bool) {
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
    dump("is_alphanumeric", |c| c.is_alphanumeric());
    dump("is_whitespace", |c| c.is_whitespace());
    dump("is_control", |c| c.is_control());
    dump("is_alphabetic", |c| c.is_alphabetic());
    dump("is_numeric", |c| c.is_numeric());
}
