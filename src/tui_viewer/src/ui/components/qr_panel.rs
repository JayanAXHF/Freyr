//! Render one QR code (unicode half-blocks) for a config slot.

use qrcode::QrCode;
use qrcode::render::unicode;
use ratatui::Frame;
use ratatui::layout::{Alignment, Rect};
use ratatui::widgets::{Block, Borders, Paragraph};

use crate::config::QrEntry;
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, entry: &QrEntry) {
    let title = if entry.label.is_empty() {
        "QR".to_string()
    } else {
        entry.label.clone()
    };
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(theme::label())
        .title(title)
        .title_style(theme::value());

    if entry.url.trim().is_empty() {
        let placeholder = Paragraph::new("empty slot\nset label + url in config.toml")
            .alignment(Alignment::Center)
            .style(theme::label())
            .block(block);
        frame.render_widget(placeholder, area);
        return;
    }

    let body = match QrCode::new(entry.url.as_bytes()) {
        Ok(code) => {
            let art = code
                .render::<unicode::Dense1x2>()
                .dark_color(unicode::Dense1x2::Light)
                .light_color(unicode::Dense1x2::Dark)
                .quiet_zone(true)
                .build();
            format!("{art}\n{}", entry.url)
        }
        Err(_) => format!("URL too long for a QR code\n{}", entry.url),
    };

    let paragraph = Paragraph::new(body)
        .alignment(Alignment::Center)
        .block(block);
    frame.render_widget(paragraph, area);
}
