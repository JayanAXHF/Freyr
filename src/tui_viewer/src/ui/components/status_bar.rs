//! Footer: screen tabs + context-sensitive key hints.

use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;

use crate::app::{App, Screen};
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let mut spans = vec![
        tab("1 Dashboard", app.screen == Screen::DashboardStatic),
        tab("2 Live", app.screen == Screen::DashboardLive),
        tab("3 QR", app.screen == Screen::Qr),
        Span::raw("  "),
    ];

    match app.screen {
        Screen::DashboardLive => {
            let state = if app.paused { "paused" } else { "playing" };
            spans.push(Span::styled(
                format!("space:{state}  r:restart  "),
                theme::label(),
            ));
        }
        Screen::Qr => spans.push(Span::styled("j/k:select  ", theme::label())),
        Screen::DashboardStatic => {}
    }
    spans.push(Span::styled("q:quit", theme::label()));

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn tab(text: &str, active: bool) -> Span<'_> {
    let style = if active {
        theme::selected()
    } else {
        theme::label()
    };
    Span::styled(format!(" {text} "), style)
}
