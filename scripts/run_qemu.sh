#!/usr/bin/env bash

set -euo pipefail

die () {
    printf 'Blad: %s\n' "$*" >&2
    exit 1
}

# Cargo przekazuje ścieżkę do pliku wykonywalnego jako pierwszy argument, więc sprawdzamy, czy został on podany.
[[ $# -eq 1 ]] || die "Użycie: $0 <plik.efi>"
[[ -f "$1" ]] || die "Plik nie istnieje: $1"

efi_binary="$(realpath "$1")"
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd )"

qemu="${QEMU_BIN:-qemu-system-x86_64}"
ovfm_code="${OVMF_CODE:-/usr/share/edk2/x64/OVMF_CODE.4m.fd}"
ovfm_vars_template="${OVMF_VARS:-/usr/share/edk2/x64/OVMF_VARS.4m.fd}"

command -v "$qemu" >/dev/null 2>&1 || die "Nie znaleziono: $qemu"
[[ -r "$ovfm_code" ]] || die "Nie można odczytać: $ovfm_code"
[[ -r "$ovfm_vars_template" ]] || die "Nie można odczytać: $ovfm_vars_template"

mkdir -p -- "$project_root/target"
run_dir="$(mktemp -d "$project_root/target/qemu.XXXXXX")"
trap 'rm -rf -- "$run_dir"' EXIT

esp_dir="$run_dir/esp"
vars_file="$run_dir/OVFM_VARS.fd"

mkdir -p -- "$esp_dir/EFI/BOOT"
cp -- "$efi_binary" "$esp_dir/EFI/BOOT/BOOTX64.EFI"
cp -- "$ovfm_vars_template" "$vars_file"
chmod u+w -- "$vars_file"

accel="${QEMU_ACCEL:-kvm}"

case "$accel" in
    kvm) cpu="host" ;;
    tcg) cpu="qemu64" ;;
    *) die "Nieobsługiwany akcelerator: $accel" ;;
esac

args=(
    -machine q35
    -accel "$accel"
    -cpu "$cpu"
    -m 256M
    -smp 1

    -drive if=pflash,format=raw,readonly=on,file="$ovfm_code"
    -drive if=pflash,format=raw,file="$vars_file"

    -drive if=virtio,format=raw,readonly=on,file=fat:ro:"$esp_dir"

    -nic none
    -serial stdio
    -monitor none
    -no-reboot
)

if [[ "${QEMU_DEBUG:-0}" == "1" ]]; then
    args+=(-s -S)
    printf 'QEMU czeka na GDB: target remote localhost:1234\n'
fi

"$qemu" "${args[@]}"
