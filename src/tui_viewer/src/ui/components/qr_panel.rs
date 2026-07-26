//! Render one QR code for a config slot.
//!
//! Uses 2x2 Unicode quadrant blocks so one character encodes four QR modules —
//! halving both width and height versus the crate's `Dense1x2` half-blocks — and
//! the lowest error-correction level to keep the module count (and size) down so
//! it fits a 3.5" screen.

use qrcode::types::Color as QrColor;
use qrcode::{EcLevel, QrCode};
use ratatui::Frame;
use ratatui::layout::{Alignment, Rect};
use ratatui::widgets::Paragraph;

use crate::config::QrEntry;
use crate::ui::theme;

/// Quadrant glyphs indexed by which of the four sub-cells are "filled"
/// (bit 0 = top-left, 1 = top-right, 2 = bottom-left, 3 = bottom-right).
const QUADRANTS: [char; 16] = [
    ' ', '▘', '▝', '▀', '▖', '▌', '▞', '▛', '▗', '▚', '▐', '▜', '▄', '▙', '▟', '█',
];

/// Render the QR as text using quadrant blocks. A filled sub-cell corresponds to
/// a *light* module so that, on a dark terminal, dark modules stay dark and the
/// code reads as the standard dark-on-light — the same inversion the previous
/// half-block renderer used.
fn quadrant_art(code: &QrCode) -> String {
    let width = code.width();
    let colors = code.to_colors();
    let is_light = |r: usize, c: usize| -> bool {
        r < width && c < width && colors[r * width + c] == QrColor::Light
    };
    let mut out = String::new();
    let mut row = 0;
    while row < width {
        let mut col = 0;
        while col < width {
            let idx = (is_light(row, col) as usize)
                | (is_light(row, col + 1) as usize) << 1
                | (is_light(row + 1, col) as usize) << 2
                | (is_light(row + 1, col + 1) as usize) << 3;
            out.push(QUADRANTS[idx]);
            col += 2;
        }
        out.push('\n');
        row += 2;
    }
    out
}

pub fn render(frame: &mut Frame, area: Rect, entry: &QrEntry) {
    if entry.url.trim().is_empty() {
        let placeholder = Paragraph::new("empty slot\nset label + url in config.toml")
            .alignment(Alignment::Center)
            .style(theme::label());
        frame.render_widget(placeholder, area);
        return;
    }

    let body = match QrCode::with_error_correction_level(entry.url.as_bytes(), EcLevel::L) {
        Ok(code) => quadrant_art(&code),
        Err(_) => format!("URL too long for a QR code\n{}", entry.url),
    };

    let paragraph = Paragraph::new(body).alignment(Alignment::Center);
    frame.render_widget(paragraph, area);
}
