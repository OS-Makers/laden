use uefi::{boot::ScopedProtocol, proto::console::serial::Serial};

pub struct SerialPort {
    protocol: ScopedProtocol<Serial>
}

impl SerialPort {
    pub fn new(protocol: ScopedProtocol<Serial>) -> Self {
        Self { protocol }
    }
    
    pub fn open() -> uefi::Result<Self> {
        let handle = uefi::boot::get_handle_for_protocol::<Serial>()?;

        let protocol = uefi::boot::open_protocol_exclusive::<Serial>(handle)?;

        let mut port = Self::new(protocol);

        port.write("Serial device initialized\r\n".as_bytes())?;

        Ok(port)
    }

    pub fn write(&mut self, data: &[u8]) -> uefi::Result<()> {
        self.protocol.write_exact(data)
    }
}

impl core::fmt::Write for SerialPort {
    fn write_str(&mut self, s: &str) -> core::fmt::Result {
        let bytes = s.as_bytes();
        let res = self.write(bytes);
        
        res.map_err(|_error| core::fmt::Error)
    }
}

