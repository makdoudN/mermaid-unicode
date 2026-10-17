/// Differential-test export (added locally, not upstream): render a mermaid block with
/// distinguishable styles and return `(plain_lines, styled_lines_tagged)`.
#[doc(hidden)]
pub mod mermaid_dump {
    use ratatui::style::{Color, Modifier, Style};
    pub fn dump(src: &str, max_width: Option<usize>) -> Option<(Vec<String>, Vec<String>)> {
        let styles = crate::mermaid::MermaidStyles {
            border: Style::default().fg(Color::Indexed(1)),
            node_text: Style::default().fg(Color::Indexed(2)),
            edge: Style::default().fg(Color::Indexed(3)),
            edge_label: Style::default().fg(Color::Indexed(4)),
            title: Style::default().fg(Color::Indexed(5)),
        };
        let art = crate::mermaid::render(src, &styles, max_width)?;
        let styled = art
            .styled_lines
            .iter()
            .map(|line| {
                let mut s = String::new();
                for span in &line.spans {
                    let tag = match span.style.fg {
                        Some(Color::Indexed(1)) => "B",
                        Some(Color::Indexed(2)) => "T",
                        Some(Color::Indexed(3)) => "E",
                        Some(Color::Indexed(4)) => "L",
                        Some(Color::Indexed(5)) => "I",
                        None => "_",
                        _ => "?",
                    };
                    let mut mods = String::new();
                    if span.style.add_modifier.contains(Modifier::BOLD) { mods.push('b'); }
                    if span.style.add_modifier.contains(Modifier::DIM) { mods.push('d'); }
                    if span.style.add_modifier.contains(Modifier::ITALIC) { mods.push('i'); }
                    if span.style.add_modifier.contains(Modifier::UNDERLINED) { mods.push('u'); }
                    s.push_str(&format!("<{}{}>{}</>", tag, mods, span.content));
                }
                s
            })
            .collect();
        Some((art.plain_lines, styled))
    }
}
