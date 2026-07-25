//! Screen 1: static point-in-time dashboard (mirrors the Streamlit page).

use ratatui::Frame;
use ratatui::layout::{Alignment, Constraint, Rect};
use ratatui::widgets::Paragraph;

use crate::app::App;
use crate::ui::components::forecast_chart::Series;
use crate::ui::components::{benchmark_table, forecast_chart, now_tiles};
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

    let [tiles_area, chart_area, table_area] = vertical(
        area,
        [
            Constraint::Length(3),
            Constraint::Min(6),
            Constraint::Length(8),
        ],
    );

    let tiles = now_tiles::now_tiles(
        snapshot.now.load_kw,
        snapshot.now.solar_kw,
        snapshot.now.soc,
        snapshot.now.tariff_block,
        snapshot.now.billing_peak_kva,
    );
    now_tiles::render(frame, tiles_area, &tiles);

    let series = vec![
        Series {
            name: "Load".to_string(),
            color: theme::LOAD,
            points: index_series(snapshot.forecast.iter().map(|p| p.load_kw)),
        },
        Series {
            name: "Solar".to_string(),
            color: theme::SOLAR,
            points: index_series(snapshot.forecast.iter().map(|p| p.solar_kw)),
        },
        Series {
            name: "Grid".to_string(),
            color: theme::GRID,
            points: index_series(snapshot.forecast.iter().map(|p| p.grid_import_kw)),
        },
    ];
    forecast_chart::render(frame, chart_area, "Next 24h (kW)", &series, "24h", None);

    benchmark_table::render(frame, table_area, &snapshot.benchmark);
}

fn index_series(values: impl Iterator<Item = f64>) -> Vec<(f64, f64)> {
    values.enumerate().map(|(i, v)| (i as f64, v)).collect()
}
