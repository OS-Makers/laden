#![no_std]
#![no_main]

use core::time::Duration;
use laden::{diagnostics::Diagnostics, emergency_serial::{EmergencySerial}};
use uefi::{Status, boot, entry, println};
use core::fmt::Write as _;

#[panic_handler]
fn panic(info: &core::panic::PanicInfo<'_>) -> ! {

    let mut emergency: EmergencySerial = laden::emergency_serial::EmergencySerial;
    let _ = write!(emergency, "[PANIC] {info}\r\n");
    
    loop {
        core::hint::spin_loop();
    }
}



#[entry]
fn main() -> Status {
    uefi::helpers::init().expect("UEFI initialization failed");

    println!("OSama bootloader started!");

    let port = match laden::serial::SerialPort::open() {
        Ok(p) => p,
        Err(e) => 
        {
            uefi::print!("[ERROR] Failed to initialize serial diagnostics: {e}\r\n");
            return e.status()
        }
    };

    let mut diagnostics: Diagnostics = Diagnostics::new(port);
    diagnostics.info(format_args!("Diagnostics initialized")).expect("Failed to write diagnostics message\r\n");

    diagnostics.info(format_args!("Bootloader initialization completed")).expect("Failed to write diagnostics message\r\n");

    boot::stall(Duration::from_secs(10));
    diagnostics.info(format_args!("Returning control to firmware")).expect("Failed to write diagnostics message\r\n");

    Status::SUCCESS
}