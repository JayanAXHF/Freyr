//! Screen 3: the Next-24h forecast chart on its own, full-screen — legible on a
//! small (3.5") display where the dashboard layout squeezes it.

use ratatui::Frame;
use ratatui::layout::{Alignment, Rect};
use ratatui::widgets::Paragraph;

use crate::app::App;
use crate::ui::components::forecast_chart;
use crate::ui::components::forecast_chart::Series;
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let Some(snapshot) = &app.snapshot else {
        let msg = Paragraph::new("waiting for data...")
            .alignment(Alignment::Center)
            .style(theme::label());
        frame.render_widget(msg, area);
        return;
    };

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
    forecast_chart::render(frame, area, "Next 24h (kW)", &series, "24h", None);
}

fn index_series(values: impl Iterator<Item = f64>) -> Vec<(f64, f64)> {
    values.enumerate().map(|(i, v)| (i as f64, v)).collect()
}
