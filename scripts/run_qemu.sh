#!/usr/bin/env bash
set -euo pipefail

die() { printf 'Błąd: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 1 ]] || die "Użycie: $0 <plik.efi>"
[[ -f "$1" ]] || die "Plik nie istnieje: $1"

efi_binary="$(realpath -- "$1")"
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
qemu="${QEMU_BIN:-qemu-system-x86_64}"
debug="${QEMU_DEBUG:-0}"

if [[ "$debug" == "1" ]]; then
    # Always use the matching pair from our private debug firmware build.
    firmware_dir="$project_root/firmware/ovmf-laden-debug-v1"

    ovmf_code="${LADEN_OVMF_DEBUG_CODE:-$firmware_dir/OVMF_CODE.fd}"
    ovmf_vars_template="${LADEN_OVMF_DEBUG_VARS:-$firmware_dir/OVMF_VARS.fd}"
else
    ovmf_code="${OVMF_CODE:-/usr/share/edk2/x64/OVMF_CODE.4m.fd}"
    ovmf_vars_template="${OVMF_VARS:-/usr/share/edk2/x64/OVMF_VARS.4m.fd}"
fi

command -v "$qemu" >/dev/null 2>&1 || die "Nie znaleziono: $qemu"
[[ -r "$ovmf_code" ]] || die "Nie można odczytać: $ovmf_code (debug: uruchom scripts/build_ovmf_debug.sh)"
[[ -r "$ovmf_vars_template" ]] || die "Nie można odczytać: $ovmf_vars_template"

mkdir -p -- "$project_root/target"
run_dir="$(mktemp -d "$project_root/target/qemu.XXXXXX")"
trap 'rm -rf -- "$run_dir"' EXIT
esp_dir="$run_dir/esp"
vars_file="$run_dir/OVMF_VARS.fd"
mkdir -p -- "$esp_dir/EFI/BOOT"
cp -- "$efi_binary" "$esp_dir/EFI/BOOT/BOOTX64.EFI"
cp -- "$ovmf_vars_template" "$vars_file"
chmod u+w -- "$vars_file"

accel="${QEMU_ACCEL:-kvm}"
case "$accel" in
    kvm) cpu="host" ;;
    tcg) cpu="qemu64" ;;
    *) die "Nieobsługiwany akcelerator: $accel" ;;
esac

# QEMU -drive uses commas as option separators even inside shell quotes.
# Escape literal commas in paths for QEMU's option parser.
qemu_code="${ovmf_code//,/,,}"
qemu_vars="${vars_file//,/,,}"
qemu_esp="${esp_dir//,/,,}"
args=(
    -machine q35
    -accel "$accel"
    -cpu "$cpu"
    -m 256M
    -smp 1
    -drive "if=pflash,unit=0,format=raw,readonly=on,file=$qemu_code"
    -drive "if=pflash,unit=1,format=raw,file=$qemu_vars"
    -drive "if=virtio,format=raw,readonly=on,file=fat:ro:$qemu_esp"
    -nic none
    -serial stdio
    -monitor none
    -no-reboot
)

if [[ "${QEMU_HEADLESS:-0}" == "1" ]]; then
    args+=(-display none)
fi

if [[ "$debug" == "1" ]]; then
    command -v python3 >/dev/null || die "Nie znaleziono python3"
    # A unique log directory permits concurrent debug sessions.
    python3 "$project_root/scripts/debug_session.py" \
        --efi "$efi_binary" --logs "$project_root/target/debug-$(basename -- "$run_dir")" \
        -- "$qemu" "${args[@]}"
else
    "$qemu" "${args[@]}"
fi
