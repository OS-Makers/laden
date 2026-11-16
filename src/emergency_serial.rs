use core::{arch::asm};

pub struct EmergencySerial;

impl core::fmt::Write for EmergencySerial {
    fn write_str(&mut self, s: &str) -> core::fmt::Result {
        for byte in s.bytes() {
            if !try_write_byte(byte) {
                return Err(core::fmt::Error)
            }
        }   
        Ok(())
    }
}




const COM1_BASE: u16 = 0x3F8;

/// # Safety
/// The caller must ensure that port I/O is permitted and that reading
/// this device register is valid in the current device state
unsafe fn read_port(port: u16) -> u8 {
    let value: u8;
    unsafe {
        asm!(
            "in al, dx",
            in("dx") port,
            out("al") value,
            options(nostack, preserves_flags),
        );
    }

    value
}

/// # Safety
/// The caller must ensure that port I/O is permitted and that writing
/// to this device is valid in the current device state
unsafe fn write_port(port: u16, value: u8) 
{
    unsafe {
        asm!(
            "out dx, al",
            in("dx") port,
            in("al") value,
            options(nostack, preserves_flags),
        );
    }
}

pub fn try_write_byte(byte: u8) -> bool {
    let mut i: u32 = 0;
    loop {
        let status;
        // SAFETY: In our x86_64/QEMU setup, COM1 uses I/O base 0x3F8.
        // Offset 5 is the UART Line Status Register; port I/O is permitted
        // in this UEFI execution context.
        unsafe {
            status = read_port(COM1_BASE + 5);
        }
        if status & 0x20 != 0
        {
            // SAFETY: COM1 is provided by our QEMU configuration.
            // We rely on firmware having configured the UART with DLAB cleared,
            // so offset 0 accesses the transmit register. THRE was checked above.
            unsafe {
                write_port(COM1_BASE, byte);
            }
            return true;
        }
        if i == 100_000
        {
            return false;
        }
        i+=1;
        core::hint::spin_loop();
    }
}
