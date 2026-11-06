use std::{env, path::Path, process::{Command, ExitCode}};

fn run() -> Result<i32, Box<dyn std::error::Error>> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize()?;
    let toolchain = env::var("LADEN_DEBUG_TOOLCHAIN")
        .unwrap_or_else(|_| "nightly-2026-03-25".into());
    let target = root.join("targets/x86_64-unknown-uefi-gdb.json");
    if !target.is_file() {
        return Err("First run: python3 scripts/prepare_debug_target.py".into());
    }
    let help = Command::new("rustup")
        .args(["run", &toolchain, "cargo", "-Z", "help"])
        .output()?;
    if !help.status.success() {
        return Err(format!("Cannot run {toolchain}: {}", String::from_utf8_lossy(&help.stderr)).into());
    }
    let mut command = Command::new("rustup");
    command.current_dir(&root)
        .args(["run", &toolchain, "cargo", "-Z", "build-std=core,alloc"]);
    if String::from_utf8_lossy(&help.stdout).contains("json-target-spec") {
        command.args(["-Z", "json-target-spec"]);
    }
    let status = command.args(["run", "--target"]).arg(target)
        .args(env::args_os().skip(1))
        .env("QEMU_DEBUG", "1")
        .status()?;
    Ok(status.code().unwrap_or(1))
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(u8::try_from(code).unwrap_or(1)),
        Err(error) => {
            eprintln!("cargo debug: {error}");
            ExitCode::FAILURE
        }
    }
}
