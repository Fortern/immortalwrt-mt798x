#!/usr/bin/env python3
"""Fail integration builds when defconfig silently drops required selections."""
import pathlib
import sys

values = {}
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    if line.startswith("CONFIG_") and "=" in line:
        key, value = line.split("=", 1)
        values[key] = value

required = {
    "TARGET_mediatek_filogic_DEVICE_cudy_tr3000-256mb-v1": "y",
    "PACKAGE_kmod-mt_wifi": "y",
    "PACKAGE_kmod-conninfra": "y",
    "PACKAGE_kmod-warp": "y",
    "PACKAGE_kmod-mediatek_hnat": "y",
    "PACKAGE_mtwifi-cfg": "y",
    "PACKAGE_wifi-dats": "y",
    "PACKAGE_lua": "y",
    "PACKAGE_luci-lib-nixio": "y",
    "PACKAGE_luci-app-mtwifi-cfg": "y",
    "MTK_CHIP_MT7981": "y",
    "MTK_APCLI_SUPPORT": "y",
    "MTK_DBDC_MODE": "y",
    "MTK_RT_FIRST_IF_RF_OFFSET": "0x0",
    "MTK_MT7981_NEW_FW": "y",
    "WARP_CHIPSET": '"mt7981"',
    "WARP_NEW_FW": "y",
}
forbidden = (
    "PACKAGE_kmod-mt7915e", "PACKAGE_kmod-mt7981-firmware",
    "PACKAGE_mt7981-wo-firmware", "PACKAGE_wifi-profile",
    "PACKAGE_mtwifi-wapp", "WIFI_SCRIPTS_UCODE",
    "MTK_MAP_SUPPORT", "MTK_MBO_SUPPORT", "MTK_BAND_STEERING",
    "MTK_QOS_R1_SUPPORT",
)
errors = []
for key, expected in required.items():
    if values.get("CONFIG_" + key) != expected:
        errors.append(f"{key}: expected {expected}, got {values.get('CONFIG_' + key, 'n')}")
for key in forbidden:
    if values.get("CONFIG_" + key, "n") != "n":
        errors.append(f"Conflicting or unwanted selection: {key}")
if errors:
    sys.exit("\n".join(errors))
print("TR3000 vendor device, AP/STA, firmware and conflict selections verified.")
