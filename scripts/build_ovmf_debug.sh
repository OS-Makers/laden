#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
src="$root/target/edk2-debug"
revision=d46aa46c8361194521391aa581593e556c707c6e

for tool in git python3 make gcc g++ nasm iasl; do
    command -v "$tool" >/dev/null || { printf 'Missing: %s\n' "$tool" >&2; exit 1; }
done
mkdir -p "$root/target"
if [[ ! -d "$src/.git" ]]; then
    git clone --depth 1 --branch edk2-stable202508 https://github.com/tianocore/edk2.git "$src"
fi
[[ "$(git -C "$src" rev-parse HEAD)" == "$revision" ]] || {
    printf 'Unexpected EDK2 revision in %s\n' "$src" >&2; exit 1;
}
# Do not recursively clone upstreams' tests, examples and optional providers.
# Existing checkouts are reused; new top-level submodules are shallow.
git -C "$src" submodule update --init --depth 1
python3 "$root/scripts/patch_ovmf.py" "$src"

cd "$src"
# New GCC versions diagnose an unused counter in this pinned BaseTools source.
# Keep all other -Werror checks, and leave the warning itself visible.
make -C BaseTools -j"$(nproc)" \
    CC="gcc -std=gnu11" \
    CXX="g++ -std=gnu++14" \
    EXTRA_OPTFLAGS="-Wno-error=unused-but-set-variable"
# EDK2's environment setup is not written for Bash nounset.
set +u
source edksetup.sh
set -u

python3 - <<'PY'
from pathlib import Path

path = Path("OvmfPkg/OvmfPkgX64.dsc")
data = path.read_bytes()

old = b"-mno-mmx -mno-sse"
new = old + b" -std=gnu11 -Wno-error=unused-but-set-variable"

if new not in data:
    if data.count(old) != 1:
        raise SystemExit("Nieoczekiwana zawartosc OvmfPkgX64.dsc")
    path.write_bytes(data.replace(old, new, 1))
PY

build -a X64 -b DEBUG -t GCC5 -p OvmfPkg/OvmfPkgX64.dsc \
    -D FD_SIZE_4MB -D SECURE_BOOT_ENABLE=FALSE -D SMM_REQUIRE=FALSE \
    -n "$(nproc)"

python3 "$root/scripts/package_ovmf.py" "$src" "$root/firmware/ovmf-laden-debug-v1"
printf 'Debug firmware ready: %s/firmware/ovmf-laden-debug-v1\n' "$root"
