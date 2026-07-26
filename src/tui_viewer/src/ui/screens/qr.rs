//! Screen 3: three QR slots — a chip row selector on top, the selected QR below.

use ratatui::Frame;
use ratatui::layout::{Alignment, Constraint, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;

use crate::app::App;
use crate::ui::components::qr_panel;
use crate::ui::layout::vertical;
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    // Single-line selector keeps as many rows as possible for the QR itself.
    let [selector_area, panel_area] = vertical(area, [Constraint::Length(1), Constraint::Min(0)]);

    let mut spans = Vec::new();
    for (i, entry) in app.config.qr.iter().enumerate() {
        let label = if entry.label.is_empty() {
            format!("slot {}", i + 1)
        } else {
            entry.label.clone()
        };
        let style = if i == app.qr_selected {
            theme::selected()
        } else {
            theme::label()
        };
        spans.push(Span::styled(format!(" {} {label} ", i + 1), style));
        spans.push(Span::raw(" "));
    }
    frame.render_widget(
        Paragraph::new(Line::from(spans)).alignment(Alignment::Center),
        selector_area,
    );

    let entry = &app.config.qr[app.qr_selected];
    qr_panel::render(frame, panel_area, entry);
}
