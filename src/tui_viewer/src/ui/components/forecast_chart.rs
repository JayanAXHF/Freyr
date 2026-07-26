//! Line chart shared by the static forecast and the live playback. Accepts a
//! set of named series plus an optional vertical sweep cursor.

use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::symbols::Marker;
use ratatui::text::Span;
use ratatui::widgets::{Axis, Block, Borders, Chart, Dataset, GraphType};

use crate::ui::theme;

pub struct Series {
    pub name: String,
    pub color: Color,
    pub points: Vec<(f64, f64)>,
}

pub fn render(
    frame: &mut Frame,
    area: Rect,
    title: &str,
    series: &[Series],
    x_label: &str,
    cursor_x: Option<f64>,
) {
    let x_max = series
        .iter()
        .flat_map(|s| s.points.iter())
        .map(|(x, _)| *x)
        .fold(0.0_f64, f64::max)
        .max(1.0);
    let y_max = series
        .iter()
        .flat_map(|s| s.points.iter())
        .map(|(_, y)| *y)
        .fold(0.0_f64, f64::max)
        .max(1.0)
        * 1.1;

    // A vertical cursor is just a two-point line dataset; declared here so it
    // outlives the borrow held by the Chart below.
    let cursor_pts: Vec<(f64, f64)> = match cursor_x {
        Some(cx) => vec![(cx, 0.0), (cx, y_max)],
        None => Vec::new(),
    };

    let mut datasets: Vec<Dataset> = series
        .iter()
        .map(|s| {
            Dataset::default()
                .name(s.name.clone())
                .marker(Marker::Braille)
                .graph_type(GraphType::Line)
                .style(Style::default().fg(s.color))
                .data(&s.points)
        })
        .collect();

    if !cursor_pts.is_empty() {
        datasets.push(
            Dataset::default()
                .name("now")
                .marker(Marker::Braille)
                .graph_type(GraphType::Line)
                .style(Style::default().fg(theme::CURSOR))
                .data(&cursor_pts),
        );
    }

    let chart = Chart::new(datasets)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(theme::label())
                .title(title)
                .title_style(theme::label()),
        )
        .x_axis(
            Axis::default()
                .style(theme::label())
                .bounds([0.0, x_max])
                .labels(vec![Span::raw("0"), Span::raw(x_label.to_string())]),
        )
        .y_axis(
            Axis::default()
                .style(theme::label())
                .bounds([0.0, y_max])
                .labels(vec![Span::raw("0"), Span::raw(format!("{y_max:.0}"))]),
        );
    frame.render_widget(chart, area);
}
