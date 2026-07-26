//! Screen 2: animated playback of the 30-day trace with a moving cursor.

use ratatui::Frame;
use ratatui::layout::{Alignment, Constraint, Rect};
use ratatui::widgets::Paragraph;

use crate::app::App;
use crate::ui::components::forecast_chart::Series;
use crate::ui::components::{forecast_chart, now_tiles};
use crate::ui::layout::vertical;
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let Some(snapshot) = &app.snapshot else {
        let msg = Paragraph::new("waiting for data...")
            .alignment(Alignment::Center)
            .style(theme::label());
        frame.render_widget(msg, area);
        return;
    };
    let trace = &snapshot.trace;
    if trace.is_empty() {
        let msg = Paragraph::new("no trace in snapshot")
            .alignment(Alignment::Center)
            .style(theme::label());
        frame.render_widget(msg, area);
        return;
    }

    let n = trace.len();
    let cursor = app.anim_cursor.min(n - 1);

    let [tiles_area, chart_area] = vertical(area, [Constraint::Length(3), Constraint::Min(6)]);

    let learned_import = at(&trace.learned.grid_import_kw, cursor);
    let mpc_import = at(&trace.mpc.grid_import_kw, cursor);
    let soc = at(&trace.learned.soc, cursor);
    let peak = at(&trace.rolling_peak_learned, cursor);
    let progress = (cursor as f64 + 1.0) / n as f64 * 100.0;

    let tiles = vec![
        ("Grid (RL)".to_string(), format!("{learned_import:.1} kW")),
        ("Grid (MPC)".to_string(), format!("{mpc_import:.1} kW")),
        ("SOC".to_string(), format!("{:.0}%", soc * 100.0)),
        ("Peak".to_string(), format!("{peak:.1} kVA")),
        ("Play".to_string(), format!("{progress:.0}%")),
    ];
    now_tiles::render(frame, tiles_area, &tiles);

    let series = vec![
        Series {
            name: "MPC".to_string(),
            color: theme::GRID,
            points: index_series(&trace.mpc.grid_import_kw),
        },
        Series {
            name: "RL".to_string(),
            color: theme::LOAD,
            points: index_series(&trace.learned.grid_import_kw),
        },
        Series {
            name: "Peak".to_string(),
            color: theme::PEAK,
            points: index_series(&trace.rolling_peak_learned),
        },
    ];
    forecast_chart::render(
        frame,
        chart_area,
        "30-day dispatch (grid import kW)",
        &series,
        "month",
        Some(cursor as f64),
    );
}

fn index_series(values: &[f64]) -> Vec<(f64, f64)> {
    values
        .iter()
        .enumerate()
        .map(|(i, v)| (i as f64, *v))
        .collect()
}

fn at(values: &[f64], i: usize) -> f64 {
    values.get(i).copied().unwrap_or(0.0)
}
