#!/usr/bin/env python3
"""Inspect the built sysupgrade payload; this is not a hardware acceptance test."""
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

from elftools.elf.elffile import ELFFile

build = pathlib.Path(sys.argv[1]).resolve()
report_path = pathlib.Path(sys.argv[2]).resolve()
target = build / "bin/targets/mediatek/filogic"
prefix = "immortalwrt-mediatek-filogic-cudy_tr3000-256mb-v1"
image = target / (prefix + "-squashfs-sysupgrade.bin")
manifest = target / (prefix + ".manifest")
hostbin = build / "staging_dir/host/bin"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


require(image.is_file(), "Missing target sysupgrade image")
require(0 < image.stat().st_size <= 235520 * 1024, "Image exceeds device size limit")
packages = dict(line.split(" - ", 1) for line in manifest.read_text().splitlines())
for name in ("kernel", "kmod-mt_wifi", "kmod-conninfra", "kmod-warp",
             "kmod-mediatek_hnat", "mtwifi-cfg", "wifi-dats",
             "iwinfo", "lua", "luci-lib-nixio", "luci-app-mtwifi-cfg"):
    require(name in packages, f"Required package missing: {name}")
require(any(re.fullmatch(r"libiwinfo\d+", name) for name in packages),
        "Missing ABI-versioned iwinfo library")
for name in ("kmod-mt7915e", "kmod-mt7981-firmware", "mt7981-wo-firmware",
             "wifi-profile", "mtwifi-wapp"):
    require(name not in packages, f"Conflicting package installed: {name}")

with tempfile.TemporaryDirectory(prefix="tr3000-image-") as tmp_name:
    tmp = pathlib.Path(tmp_name)
    metadata_file = tmp / "metadata.json"
    subprocess.run([str(hostbin / "fwtool"), "-i", str(metadata_file), str(image)], check=True)
    metadata = json.loads(metadata_file.read_text())
    require("cudy,tr3000-256mb-v1" in metadata["supported_devices"], "Wrong device metadata")
    require("R103" in metadata["supported_devices"], "Missing release compatibility alias")
    require(metadata["version"]["version"] == "25.12.2", "Unexpected release version")
    require(metadata["version"]["target"] == "mediatek/filogic", "Unexpected target")
    with tarfile.open(image) as archive:
        for part in ("kernel", "root", "CONTROL"):
            member = archive.getmember("sysupgrade-cudy_tr3000-256mb-v1/" + part)
            require(member.isfile() and member.size > 0, f"Missing image payload: {part}")
            with archive.extractfile(member) as source, (tmp / part).open("wb") as dest:
                shutil.copyfileobj(source, dest)
    root = tmp / "rootfs"
    # Device nodes are not needed for file/module inspection and require root
    # to recreate. Keep verification under the same ordinary build user.
    subprocess.run([str(hostbin / "unsquashfs4"), "-no-progress", "-processors", "2",
                    "-excludes", "-d", str(root), str(tmp / "root"), "dev"], check=True,
                   stdout=subprocess.DEVNULL)
    for name in ("sbin/mtwifi_cfg", "sbin/l1util", "lib/netifd/wireless/mtwifi.sh",
                 "lib/wifi/mtwifi.sh", "etc/wireless/l1profile.dat",
                 "www/luci-static/resources/view/network/mtwifi.js"):
        require((root / name).is_file(), f"Missing integration file: {name}")
    for name in ("sbin/mtwifi_cfg", "sbin/l1util", "lib/netifd/wireless/mtwifi.sh"):
        require((root / name).stat().st_mode & 0o111, f"Executable bit missing: {name}")
    module_paths = list((root / "lib/modules").glob("*/*.ko"))
    modules = {}
    for path in module_paths:
        with path.open("rb") as stream:
            elf = ELFFile(stream)
            require(elf["e_machine"] == "EM_AARCH64", f"Wrong module architecture: {path.name}")
            section = elf.get_section_by_name(".modinfo")
            require(section is not None, f"Missing module metadata: {path.name}")
            values = dict(item.decode().split("=", 1) for item in section.data().split(b"\0")
                          if b"=" in item)
        modules[path.stem] = values
    required_modules = ("mt_wifi", "conninfra", "mtk_warp", "mtk_warp_proxy", "mtkhnat")
    for name in required_modules:
        require(name in modules, f"Missing kernel module: {name}")
    vermagics = {values.get("vermagic") for values in modules.values()}
    require(len(vermagics) == 1 and None not in vermagics, "Kernel module vermagic mismatch")
    vermagic = next(iter(vermagics))
    require(vermagic.startswith("6.12."), "Kernel series changed")
    require(packages["kernel"].startswith(vermagic.split()[0]), "Kernel package/module version mismatch")
    require(not {"mt7915e", "mt76", "mt76_connac_lib"}.intersection(modules), "Board driver conflict")
    firmware = {}
    source_fw = build / "package/mtk/drivers/mt_wifi/files/mt7981-fw-20240613"
    for name in ("WIFI_RAM_CODE_MT7981.bin", "7981_WACPU_RAM_CODE_release.bin",
                 "mt7981_patch_e1_hdr.bin"):
        path = root / "lib/firmware" / name
        require(path.is_file(), f"Missing wireless firmware: {name}")
        require(digest(path) == digest(source_fw / name), f"Wireless firmware mismatch: {name}")
        firmware[name] = digest(path)
    wo_sources = list((build / "package/mtk/drivers/warp/files/mt7981-fw-20231228").glob("7981*WOCPU*_RAM_CODE_release.bin"))
    require(wo_sources, "No fixed WO firmware source")
    for source in wo_sources:
        path = root / "lib/firmware" / source.name
        require(path.is_file() and digest(path) == digest(source), f"WO firmware mismatch: {source.name}")
        firmware[source.name] = digest(path)
    kernel_configs = list((build / "build_dir").glob("target-*/linux-mediatek_filogic/linux-6.12.*/.config"))
    require(len(kernel_configs) == 1, "Ambiguous kernel configuration")
    kernel_config = kernel_configs[0].read_text().splitlines()
    for option in ("CONFIG_WIRELESS_EXT=y", "CONFIG_WEXT_CORE=y", "CONFIG_WEXT_PRIV=y",
                   "CONFIG_NET_MEDIATEK_HNAT=m", "CONFIG_MTK_VENDOR_WIFI_UTILITY=y"):
        require(option in kernel_config, f"Kernel option missing: {option}")
    require("CONFIG_NET_MEDIATEK_SOC_WED=y" not in kernel_config, "Upstream WED ownership conflict")
    report = {"status": "image-static-checks-passed", "hardware_validation": "pending",
              "source_commit": subprocess.check_output(["git", "-C", str(build), "rev-parse", "HEAD"], text=True).strip(),
              "image": image.name, "size": image.stat().st_size, "sha256": digest(image),
              "metadata": metadata, "module_vermagic": vermagic,
              "vendor_modules": {name: modules[name] for name in required_modules},
              "firmware_sha256": firmware, "package_count": len(packages)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Image checks passed; hardware acceptance pending. Report: {report_path}")
