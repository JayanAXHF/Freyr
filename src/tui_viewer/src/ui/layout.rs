//! Layout helpers for small-screen (3.5") composition.

use ratatui::layout::{Constraint, Direction, Layout, Rect};

pub const MIN_W: u16 = 50;
pub const MIN_H: u16 = 16;

pub fn too_small(area: Rect) -> bool {
    area.width < MIN_W || area.height < MIN_H
}

pub fn vertical<const N: usize>(area: Rect, constraints: [Constraint; N]) -> [Rect; N] {
    Layout::default()
        .direction(Direction::Vertical)
        .constraints(constraints)
        .areas(area)
}
