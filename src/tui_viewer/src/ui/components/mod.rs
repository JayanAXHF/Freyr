//! UI components — one file per widget. Each exposes a free `render(frame,
//! area, ...)` function; the app owns all state and key handling centrally, so
//! components stay stateless and composable across screens.

pub mod benchmark_table;
pub mod forecast_chart;
pub mod now_tiles;
pub mod qr_panel;
pub mod status_bar;
pub mod title_bar;
