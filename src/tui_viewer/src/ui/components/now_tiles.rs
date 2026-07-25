//! A single row of compact metric tiles (label as border title, bold centered
//! value). Reused by both dashboard screens with different tile sets.

use ratatui::Frame;
use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::widgets::{Block, Borders, Paragraph};

use crate::ui::theme;

/// Render `tiles` (label, value) as equal-width bordered cells across `area`.
pub fn render(frame: &mut Frame, area: Rect, tiles: &[(String, String)]) {
    if tiles.is_empty() {
        return;
    }
    let n = tiles.len();
    let constraints: Vec<Constraint> = (0..n).map(|_| Constraint::Ratio(1, n as u32)).collect();
    let cells = Layout::default()
        .direction(Direction::Horizontal)
        .constraints(constraints)
        .split(area);

    for (cell, (label, value)) in cells.iter().zip(tiles.iter()) {
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(theme::label())
            .title(label.as_str())
            .title_style(theme::label());
        let paragraph = Paragraph::new(value.as_str())
            .style(theme::value())
            .alignment(Alignment::Center)
            .block(block);
        frame.render_widget(paragraph, *cell);
    }
}

/// Convenience used by the static screen to build the standard "Now" tiles.
pub fn now_tiles(
    load_kw: f64,
    solar_kw: f64,
    soc: f64,
    tariff_block: i64,
    billing_peak_kva: f64,
) -> Vec<(String, String)> {
    vec![
        ("Load".to_string(), format!("{load_kw:.1} kW")),
        ("Solar".to_string(), format!("{solar_kw:.1} kW")),
        ("SOC".to_string(), format!("{:.0}%", soc * 100.0)),
        ("Tariff".to_string(), format!("blk {tariff_block}")),
        ("Peak".to_string(), format!("{billing_peak_kva:.1} kVA")),
    ]
}
