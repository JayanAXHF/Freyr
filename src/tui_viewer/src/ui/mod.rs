//! Top-level rendering: title bar, the active screen, and the status bar.

pub mod components;
pub mod layout;
pub mod screens;
pub mod theme;

use ratatui::Frame;
use ratatui::layout::{Alignment, Constraint};
use ratatui::widgets::Paragraph;

use crate::app::{App, Screen};

pub fn draw(frame: &mut Frame, app: &App) {
    let area = frame.area();
    if layout::too_small(area) {
        let notice = Paragraph::new("Terminal too small\nResize to at least 50x16")
            .alignment(Alignment::Center)
            .style(theme::label());
        frame.render_widget(notice, area);
        return;
    }

    let [top, body, bottom] = layout::vertical(
        area,
        [
            Constraint::Length(1),
            Constraint::Min(0),
            Constraint::Length(1),
        ],
    );

    components::title_bar::render(frame, top, app);
    match app.screen {
        Screen::DashboardStatic => screens::dashboard_static::render(frame, body, app),
        Screen::DashboardLive => screens::dashboard_live::render(frame, body, app),
        Screen::Qr => screens::qr::render(frame, body, app),
    }
    components::status_bar::render(frame, bottom, app);
}
