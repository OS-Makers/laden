use core::fmt::Write as _;

use crate::serial::SerialPort;

pub struct Diagnostics {
    serial: SerialPort,
}

pub enum Level {
    Info,
    Warn,
    Error
}

impl Diagnostics {
    pub fn new(serial: SerialPort) -> Self {
        Self { serial }
    }

    fn log(&mut self, level: Level, args: core::fmt::Arguments<'_>) -> core::fmt::Result {
        let prefix: &str = match level {
            Level::Info => "INFO",
            Level::Warn => "WARN",
            Level::Error => "ERROR"
        };

        uefi::println!("[{prefix}] {args}");
        write!(self.serial, "[{prefix}] {args}\r\n")
    }

    pub fn info(&mut self, args: core::fmt::Arguments<'_>) -> core::fmt::Result {
        self.log(Level::Info, args)
    }

    pub fn warn(&mut self, args: core::fmt::Arguments<'_>) -> core::fmt::Result {
        self.log(Level::Warn, args)
    }

    pub fn error(&mut self, args: core::fmt::Arguments<'_>) -> core::fmt::Result {
        self.log(Level::Error, args)
    }

}


