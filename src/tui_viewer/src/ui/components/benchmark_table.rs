//! Compact MPC-vs-learned comparison table with the savings highlight.

use ratatui::Frame;
use ratatui::layout::{Constraint, Rect};
use ratatui::style::Style;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Cell, Row, Table};

use crate::data::model::{Benchmark, BenchmarkRow};
use crate::ui::theme;

pub fn render(frame: &mut Frame, area: Rect, bench: &Benchmark) {
    let header = Row::new(vec![
        Cell::from("Metric"),
        Cell::from("MPC"),
        Cell::from("Learned"),
    ])
    .style(theme::label());

    let rows = vec![
        metric_row(
            "Total bill",
            bench.mpc.total_bill,
            bench.learned.total_bill,
            0,
        ),
        metric_row(
            "Energy cost",
            bench.mpc.total_energy_cost,
            bench.learned.total_energy_cost,
            0,
        ),
        metric_row(
            "Demand chg",
            bench.mpc.demand_charge_incurred,
            bench.learned.demand_charge_incurred,
            0,
        ),
        metric_row("Peak kVA", bench.mpc.peak_kva, bench.learned.peak_kva, 1),
        metric_row(
            "Solar self-use",
            bench.mpc.solar_self_consumption,
            bench.learned.solar_self_consumption,
            2,
        ),
        savings_row(&bench.learned),
    ];

    let table = Table::new(
        rows,
        [
            Constraint::Length(15),
            Constraint::Min(8),
            Constraint::Min(8),
        ],
    )
    .header(header)
    .block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(theme::label())
            .title("Benchmark (30-day)")
            .title_style(theme::label()),
    );

    frame.render_widget(table, area);
}

fn metric_row<'a>(label: &'a str, mpc: f64, learned: f64, decimals: usize) -> Row<'a> {
    Row::new(vec![
        Cell::from(label),
        Cell::from(format!("{mpc:.*}", decimals)),
        Cell::from(Span::styled(
            format!("{learned:.*}", decimals),
            theme::value(),
        )),
    ])
}

fn savings_row<'a>(learned: &BenchmarkRow) -> Row<'a> {
    let (text, style) = match learned.savings_pct {
        Some(pct) => (
            format!("{pct:.1}% vs MPC"),
            Style::default().fg(theme::GOOD),
        ),
        None => (
            "n/a (service)".to_string(),
            Style::default().fg(theme::WARN),
        ),
    };
    Row::new(vec![
        Cell::from("Savings"),
        Cell::from(Line::from("")),
        Cell::from(Span::styled(text, style)),
    ])
}
