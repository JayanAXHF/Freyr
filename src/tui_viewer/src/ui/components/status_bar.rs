//! Footer: screen tabs + context-sensitive key hints.

use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::Style;
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;

use crate::app::{App, Screen};
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let mut spans = vec![
        tab("1 Dash", app.screen == Screen::DashboardStatic),
        tab("2 Live", app.screen == Screen::DashboardLive),
        tab("3 Graph", app.screen == Screen::Graph),
        tab("4 QR", app.screen == Screen::Qr),
        Span::raw(" "),
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
        Screen::DashboardStatic | Screen::Graph => {}
    }
    spans.push(Span::styled("q:quit", theme::label()));

    // GPIO status indicator (only when buttons are configured): green when the
    // watcher thread is live, red when it failed to start (see the gpio log).
    if app.gpio_configured() {
        let (text, color) = if app.gpio_is_active() {
            ("  gpio\u{25CF}", theme::GOOD)
        } else {
            ("  gpio\u{2717}", theme::BAD)
        };
        spans.push(Span::styled(text, Style::default().fg(color)));
    }

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
