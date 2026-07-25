//! Header: app name + connection state.

use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::Style;
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;

use crate::app::App;
use crate::data::ConnState;
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let conn = match &app.conn {
        ConnState::Connecting => Span::styled(" connecting ", Style::default().fg(theme::WARN)),
        ConnState::Ok => Span::styled(" live ", Style::default().fg(theme::GOOD)),
        ConnState::Error(msg) => Span::styled(
            format!(" offline: {} ", truncate(msg, 40)),
            Style::default().fg(theme::BAD),
        ),
    };
    let line = Line::from(vec![
        Span::styled(" Freyr ", theme::title()),
        Span::raw(" "),
        Span::styled("\u{25CF}", conn_dot(&app.conn)),
        conn,
    ]);
    frame.render_widget(Paragraph::new(line), area);
}

fn conn_dot(conn: &ConnState) -> Style {
    let color = match conn {
        ConnState::Connecting => theme::WARN,
        ConnState::Ok => theme::GOOD,
        ConnState::Error(_) => theme::BAD,
    };
    Style::default().fg(color)
}

fn truncate(text: &str, max: usize) -> String {
    if text.chars().count() <= max {
        text.to_string()
    } else {
        let kept: String = text.chars().take(max.saturating_sub(1)).collect();
        format!("{kept}\u{2026}")
    }
}
