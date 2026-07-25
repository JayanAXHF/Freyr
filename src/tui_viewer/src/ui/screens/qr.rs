//! Screen 3: three QR slots — a chip row selector on top, the selected QR below.

use ratatui::Frame;
use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::widgets::{Block, Borders, Paragraph};

use crate::app::App;
use crate::ui::components::qr_panel;
use crate::ui::layout::vertical;
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let [chips_area, panel_area] = vertical(area, [Constraint::Length(3), Constraint::Min(0)]);

    let slots = app.config.qr.len().max(1);
    let constraints: Vec<Constraint> = (0..slots)
        .map(|_| Constraint::Ratio(1, slots as u32))
        .collect();
    let cells = Layout::default()
        .direction(Direction::Horizontal)
        .constraints(constraints)
        .split(chips_area);

    for (i, cell) in cells.iter().enumerate() {
        let entry = &app.config.qr[i];
        let label = if entry.label.is_empty() {
            format!("slot {}", i + 1)
        } else {
            entry.label.clone()
        };
        let selected = i == app.qr_selected;
        let border = if selected {
            theme::selected()
        } else {
            theme::label()
        };
        let text_style = if selected {
            theme::value()
        } else {
            theme::label()
        };
        let chip = Paragraph::new(label)
            .alignment(Alignment::Center)
            .style(text_style)
            .block(Block::default().borders(Borders::ALL).border_style(border));
        frame.render_widget(chip, *cell);
    }

    let entry = &app.config.qr[app.qr_selected];
    qr_panel::render(frame, panel_area, entry);
}
