//! Central application state and event handling.

use std::sync::mpsc::Receiver;

use ratatui::crossterm::event::{KeyCode, KeyEvent, KeyEventKind};

use crate::config::{Config, QR_SLOTS};
use crate::data::model::Snapshot;
use crate::data::{ConnState, DataMsg};
use crate::event::Event;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Screen {
    DashboardStatic,
    DashboardLive,
    Graph,
    Qr,
}

pub struct App {
    pub config: Config,
    pub screen: Screen,
    pub snapshot: Option<Snapshot>,
    pub conn: ConnState,
    pub qr_selected: usize,
    pub anim_cursor: usize,
    pub paused: bool,
    pub should_quit: bool,
    data_rx: Receiver<DataMsg>,
}

impl App {
    pub fn new(config: Config, data_rx: Receiver<DataMsg>) -> Self {
        App {
            config,
            screen: Screen::DashboardStatic,
            snapshot: None,
            conn: ConnState::Connecting,
            qr_selected: 0,
            anim_cursor: 0,
            paused: false,
            should_quit: false,
            data_rx,
        }
    }

    pub fn on_event(&mut self, event: Event) {
        match event {
            Event::Key(key) => self.on_key(key),
            Event::Tick => self.on_tick(),
            Event::Resize(_, _) => {}
        }
    }

    fn on_tick(&mut self) {
        self.drain_data();
        if self.screen == Screen::DashboardLive
            && !self.paused
            && let Some(len) = self.trace_len().filter(|&len| len > 0)
        {
            self.anim_cursor = (self.anim_cursor + 1) % len;
        }
    }

    fn drain_data(&mut self) {
        while let Ok(msg) = self.data_rx.try_recv() {
            match msg {
                DataMsg::Snapshot(snapshot) => {
                    let len = snapshot.trace.len();
                    if len > 0 {
                        self.anim_cursor %= len;
                    } else {
                        self.anim_cursor = 0;
                    }
                    self.snapshot = Some(*snapshot);
                    self.conn = ConnState::Ok;
                }
                DataMsg::Error(err) => self.conn = ConnState::Error(err),
            }
        }
    }

    fn trace_len(&self) -> Option<usize> {
        self.snapshot.as_ref().map(|s| s.trace.len())
    }

    fn on_key(&mut self, key: KeyEvent) {
        if key.kind != KeyEventKind::Press {
            return;
        }
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => self.should_quit = true,
            KeyCode::Char('1') => self.screen = Screen::DashboardStatic,
            KeyCode::Char('2') => self.screen = Screen::DashboardLive,
            KeyCode::Char('3') => self.screen = Screen::Graph,
            KeyCode::Char('4') => self.screen = Screen::Qr,
            code => match self.screen {
                Screen::Qr => self.on_qr_key(code),
                Screen::DashboardLive => self.on_live_key(code),
                Screen::DashboardStatic | Screen::Graph => {}
            },
        }
    }

    fn on_qr_key(&mut self, code: KeyCode) {
        match code {
            KeyCode::Char('j') | KeyCode::Down => {
                self.qr_selected = (self.qr_selected + 1) % QR_SLOTS;
            }
            KeyCode::Char('k') | KeyCode::Up => {
                self.qr_selected = (self.qr_selected + QR_SLOTS - 1) % QR_SLOTS;
            }
            _ => {}
        }
    }

    fn on_live_key(&mut self, code: KeyCode) {
        match code {
            KeyCode::Char(' ') => self.paused = !self.paused,
            KeyCode::Char('r') => self.anim_cursor = 0,
            _ => {}
        }
    }
}
