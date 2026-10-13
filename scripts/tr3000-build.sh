#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C.UTF-8
# Bash reads a running script incrementally. Freeze the entry before long builds
# so source maintenance cannot change the remainder of an in-flight run.
if [[ ${TR3000_FROZEN_ENTRY:-0} != 1 ]]; then
    TR3000_FROZEN_SCRIPT=$(mktemp)
    cp -- "${BASH_SOURCE[0]}" "$TR3000_FROZEN_SCRIPT"
    export TR3000_FROZEN_ENTRY=1 TR3000_FROZEN_SCRIPT
    exec bash "$TR3000_FROZEN_SCRIPT" "$@"
fi
trap 'rm -f -- "$TR3000_FROZEN_SCRIPT"' EXIT
source_repo=${TR3000_SOURCE:-/mnt/f/CLionProjects/immortalwrt-mt798x}
build_dir=${TR3000_BUILD:-/home/fortern/build/immortalwrt-tr3000-v25.12.2}
# Trust only this explicitly configured source path on the Windows mount.
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$source_repo"
mode=${1:-vendor}
case "$mode" in
    baseline) ref=v25.12.2; config=baseline.config ;;
    vendor) ref=${2:-tr3000-v25.12.2-mtk}; config=vendor.config ;;
    *) echo 'Usage: tr3000-build.sh baseline | vendor [commit]' >&2; exit 2 ;;
esac
[[ $(id -u) != 0 ]] || { echo 'Build as an ordinary user.' >&2; exit 1; }
source_sha=$(git -C "$source_repo" rev-parse "$ref^{commit}")
recipe_sha=$(git -C "$source_repo" rev-parse HEAD)
if [[ $mode == vendor ]]; then
    [[ -z $(git -C "$source_repo" status --porcelain) ]] || {
        echo 'Source changes must be committed before building.' >&2; exit 1;
    }
    recipe_sha=$source_sha
fi
recipe_dir=$(mktemp -d)
trap 'rm -rf -- "$recipe_dir"; rm -f -- "$TR3000_FROZEN_SCRIPT"' EXIT
git -C "$source_repo" archive "$recipe_sha" \
    "configs/tr3000-v25.12.2/$config" scripts/tr3000-feeds.py scripts/tr3000-check-config.py \
    scripts/tr3000-check-image.py | tar -x -C "$recipe_dir"
config_path="$recipe_dir/configs/tr3000-v25.12.2/$config"
mkdir -p "$(dirname "$build_dir")"
# Lock outside the checkout, including clone and configuration steps.
exec 9>"${build_dir}.lock"
flock -n 9 || { echo "Another build owns $build_dir" >&2; exit 1; }
if [[ ! -d "$build_dir/.git" ]]; then
    git clone --no-hardlinks "$source_repo" "$build_dir"
fi
[[ -z $(git -C "$build_dir" status --porcelain --untracked-files=no) ]] || {
    echo 'Build checkout has tracked changes; refusing to overwrite.' >&2; exit 1;
}
git -C "$build_dir" fetch "$source_repo" "$ref"
git -C "$build_dir" -c advice.detachedHead=false checkout --detach "$source_sha"
git -C "$build_dir" config core.autocrlf false
git -C "$build_dir" config core.eol lf
cd "$build_dir"
# Target module metadata is cached separately and can survive a branch switch.
rm -f tmp/info/.packageinfo-kernel_linux tmp/.packageinfo tmp/.config-package.in
run_id=$(date -u +%Y%m%dT%H%M%SZ)
output="$source_repo/artifacts/$source_sha/$mode-$run_id"
mkdir -p "$output"
exec > >(tee "$output/build.log") 2>&1
finish() {
    local result=$?
    printf '%s\n' "$result" > "$output/exit-code"
    if [[ -d logs ]]; then
        rsync -a logs/ "$output/package-logs/" || true
    fi
    rm -rf -- "$recipe_dir"
    rm -f -- "$TR3000_FROZEN_SCRIPT"
    exit "$result"
}
trap finish EXIT
printf '%s\n' "$source_sha" > "$output/source-commit"
printf '%s\n' "$recipe_sha" > "$output/build-recipe-commit"
cp "$recipe_dir/scripts/tr3000-feeds.py" "$output/feeds-recipe.py"
cp -- "$TR3000_FROZEN_SCRIPT" "$output/build-entry.sh"
cp feeds.conf.default "$output/feeds.conf.default"
cp "$config_path" "$output/input.config"
sha256sum "$config_path" > "$output/input-config.sha256"
{
    cat /etc/os-release
    uname -a
    gcc --version | head -n 1
    /usr/lib/llvm-19/bin/clang --version | head -n 1
    git --version
    make --version | head -n 1
    df -h .
    free -h
} > "$output/environment.txt"
python3 "$recipe_dir/scripts/tr3000-feeds.py"
./scripts/feeds update -i -a
./scripts/feeds install -a
for feed in feeds/*/.git; do
    dir=${feed%/.git}
    printf '%s %s\n' "${dir##*/}" "$(git -C "$dir" rev-parse HEAD)"
done > "$output/feeds-commits"
cp "$config_path" .config
make defconfig
if [[ $mode == vendor ]]; then
    python3 "$recipe_dir/scripts/tr3000-check-config.py" .config
fi
cp .config "$output/expanded.config"
./scripts/diffconfig.sh > "$output/diffconfig"
jobs=$(nproc)
(( jobs <= 8 )) || jobs=8
if ! make -j"$jobs" download; then make -j1 download V=s; fi
if ! make -j"$jobs" BUILD_LOG=1; then make -j1 V=s BUILD_LOG=1; fi
if [[ $mode == vendor ]]; then
    python3 "$recipe_dir/scripts/tr3000-check-image.py" "$build_dir" "$output/image-validation.json"
    cp "$recipe_dir/scripts/tr3000-check-image.py" "$output/image-check-recipe.py"
fi
mkdir -p "$output/bin"
rsync -a bin/ "$output/bin/"
(cd "$output"; find bin -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "Build completed: $output"
