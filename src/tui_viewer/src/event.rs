//! Input + tick event loop. Emits key/resize events and a periodic tick used to
//! drive the animation and drain the data channel.

use std::sync::mpsc::{self, Receiver};
use std::thread;
use std::time::Duration;

use ratatui::crossterm::event::{self, Event as CtEvent, KeyEvent};

pub enum Event {
    Key(KeyEvent),
    Tick,
    /// Terminal resize; the payload is unused today but a resize still forces a
    /// redraw via the main loop.
    Resize(#[allow(dead_code)] u16, #[allow(dead_code)] u16),
}

/// Spawn the event thread. `tick_ms` is the animation/refresh cadence.
pub fn spawn(tick_ms: u64) -> Receiver<Event> {
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        let tick = Duration::from_millis(tick_ms);
        loop {
            let ready = event::poll(tick).unwrap_or(false);
            if ready {
                match event::read() {
                    Ok(CtEvent::Key(key)) => {
                        if tx.send(Event::Key(key)).is_err() {
                            break;
                        }
                    }
                    Ok(CtEvent::Resize(w, h)) => {
                        if tx.send(Event::Resize(w, h)).is_err() {
                            break;
                        }
                    }
                    Ok(_) => {}
                    Err(_) => break,
                }
            } else if tx.send(Event::Tick).is_err() {
                break;
            }
        }
    });
    rx
}
