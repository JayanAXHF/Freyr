//! Small high-contrast palette that reads well on a tiny TFT.

use ratatui::style::{Color, Modifier, Style};

pub const ACCENT: Color = Color::Cyan;
pub const GOOD: Color = Color::Green;
pub const WARN: Color = Color::Yellow;
pub const BAD: Color = Color::Red;
pub const MUTED: Color = Color::DarkGray;

// Series colors (shared by the static + live charts).
pub const LOAD: Color = Color::Yellow;
pub const SOLAR: Color = Color::Green;
pub const GRID: Color = Color::Magenta;
pub const PEAK: Color = Color::Red;
pub const CURSOR: Color = Color::White;

pub fn title() -> Style {
    Style::default()
        .fg(Color::Black)
        .bg(ACCENT)
        .add_modifier(Modifier::BOLD)
}

pub fn value() -> Style {
    Style::default().add_modifier(Modifier::BOLD)
}

pub fn label() -> Style {
    Style::default().fg(MUTED)
}

pub fn selected() -> Style {
    Style::default()
        .fg(Color::Black)
        .bg(ACCENT)
        .add_modifier(Modifier::BOLD)
}
