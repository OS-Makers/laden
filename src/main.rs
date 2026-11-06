#![no_std]
#![no_main]

use core::time::Duration;
use uefi::{Status, boot, entry, println};

#[entry]
fn main() -> Status {
    uefi::helpers::init().expect("UEFI initialization failed");

    println!("OSama bootloader started!");
    println!("Hello from UEFI!");

    boot::stall(Duration::from_secs(10));

    Status::SUCCESS
}