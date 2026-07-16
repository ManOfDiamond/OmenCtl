#!/usr/bin/env python3
"""OMEN Command Center for Linux — RGB Microservice.

Owns RGB LED zone control and all lighting animation modes.
Exposes its functionality over D-Bus as ``com.yyl.hpmanager.rgb``.
"""

import json
import os
import re
import sys
import threading
import time
import typing

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.dbus_helpers import run_service

logger = setup_logging("rgb")

DRIVER_PATH_NEW = "/sys/devices/platform/omen-rgb-keyboard/rgb_zones"
DRIVER_PATH_CUSTOM = "/sys/devices/platform/hp-rgb-lighting"
HEX_COLOR_RE = re.compile(r"^[0-9A-F]{6}$")

# Driver capability notes:
#
# omen-rgb-keyboard (new driver)
#   sysfs: /sys/devices/platform/omen-rgb-keyboard/rgb_zones/zone00 … zone07
#   brightness: 0-100  animation_mode / animation_speed supported
#   is_new_driver = True
#
# hp-rgb-lighting (custom driver by yunusemreyl)
#   sysfs: /sys/devices/platform/hp-rgb-lighting/zone0 … zone7
#   brightness: "1" (on, writes 0xE4 to WMI) / "0" (off, writes 0x64)
#   no animation_mode; static zone colours only
#   supports up to 8 zones (zone0-zone7)
#   is_new_driver = False
#
# hp-omen (hp-omen-linux-module, old community driver)
#   sysfs: /sys/devices/platform/hp-wmi/rgb_zones/zone00 … zone03
#   brightness: not present; only 4 zones; no animation
#   is_new_driver = False (treated same as hp-rgb-lighting fallback)

VALID_LIGHT_MODES = {"static", "breathing", "wave", "cycle", "rainbow", "pulse", "chase", "sparkle", "candle", "aurora", "disco", "gradient"}
VALID_DIRECTIONS = {"ltr", "rtl"}

class RGBController:
    """Low-level RGB LED zone access via sysfs."""

    def __init__(self):
        self.driver_path = self._find_rgb_path()
        self.available = self.driver_path is not None
        self.is_new_driver = self.available and "omen-rgb-keyboard" in self.driver_path
        self.unsupported = not self.available
        # Determine actual zone count supported by the driver
        self.zone_count = self._detect_zone_count()

    def _detect_zone_count(self):
        """Return the number of writable zones this driver exposes."""
        if not self.available:
            return 0
        if self.is_new_driver:
            # omen-rgb-keyboard always exposes zone00..zone07
            return 8
        # hp-rgb-lighting: probe for zone4 to distinguish 8-zone from 4-zone
        zone4 = os.path.join(self.driver_path, "zone4")
        zone4_new = os.path.join(self.driver_path, "zone04")
        if os.path.exists(zone4) or os.path.exists(zone4_new):
            return 8
        return 4

    def _find_rgb_path(self):
        if os.path.exists(DRIVER_PATH_NEW):
            logger.info("RGB: Using new driver path %s", DRIVER_PATH_NEW)
            return DRIVER_PATH_NEW
        if os.path.exists(DRIVER_PATH_CUSTOM):
            logger.info("RGB: Using custom driver path %s", DRIVER_PATH_CUSTOM)
            return DRIVER_PATH_CUSTOM

        for candidate in (
            "/sys/devices/platform/hp-rgb-lighting",
            "/sys/devices/platform/hp_rgb_lighting",
        ):
            if os.path.exists(candidate):
                logger.info("RGB: Found loaded module at %s", candidate)
                return candidate

        # Neither driver path exists — try loading the modules.
        self._try_load_rgb_drivers()

        # Re-check after modprobe
        for check in (DRIVER_PATH_NEW, DRIVER_PATH_CUSTOM,
                      "/sys/devices/platform/hp-rgb-lighting",
                      "/sys/devices/platform/hp_rgb_lighting"):
            if os.path.exists(check):
                logger.info("RGB: Driver path available after modprobe: %s", check)
                return check

        logger.info("RGB: No RGB control path found (hp_rgb_lighting / omen-rgb-keyboard not loaded)")
        return None

    @staticmethod
    def _try_load_rgb_drivers():
        """Attempt to load known HP/OMEN RGB kernel modules."""
        import subprocess as _sp
        for mod in ("omen-rgb-keyboard", "hp_rgb_lighting", "hp-rgb-lighting"):
            try:
                result = _sp.run(["modprobe", mod], capture_output=True, timeout=5)
                if result.returncode == 0:
                    logger.info("RGB: Loaded kernel module '%s'", mod)
                    return  # One driver is enough
            except Exception as e:
                logger.debug("RGB: modprobe %s failed: %s", mod, e)

    def is_available(self):
        return self.available

    def write_zone(self, zone, hex_color):
        if not self.available or not (0 <= zone <= 7):
            return
        
        # New driver uses zone00, zone01, etc.
        # Old driver uses zone0, zone1, etc.
        filename = f"zone{zone:02d}" if self.is_new_driver else f"zone{zone}"
        path = f"{self.driver_path}/{filename}"
        
        try:
            with open(path, "w") as f:
                f.write(hex_color)
        except Exception as e:
            logger.error(f"Failed to write zone {zone}: {e}")

    def write_all(self, hex_color):
        """Write hex_color to all available zones."""
        if not self.available:
            return

        if self.is_new_driver:
            try:
                with open(f"{self.driver_path}/all", "w") as f:
                    f.write(hex_color)
            except Exception as e:
                logger.error(f"Failed to write all zones: {e}")
        else:
            # hp-rgb-lighting supports zone_count zones (4 or 8)
            for i in range(self.zone_count):
                self.write_zone(i, hex_color)

    def write_brightness(self, value_or_bool):
        if not self.available:
            return
            
        try:
            with open(f"{self.driver_path}/brightness", "w") as f:
                if self.is_new_driver:
                    # New driver takes 0-100
                    if isinstance(value_or_bool, bool):
                        val = "100" if value_or_bool else "0"
                    else:
                        val = str(int(value_or_bool))
                    f.write(val)
                else:
                    # Old driver takes 1 or 0
                    val = "1" if value_or_bool else "0"
                    f.write(val)
        except Exception as e:
            logger.error(f"Failed to write brightness: {e}")

    def read_brightness(self):
        if not self.available:
            return None
        try:
            with open(f"{self.driver_path}/brightness", "r") as f:
                val = f.read().strip()
                if self.is_new_driver:
                    return int(val) > 0
                return val == "1"
        except Exception:
            return None

    def write_win_lock(self, locked):
        # Mute LED is automatic in new driver, but win_lock might not exist in new driver, just ignore if fails
        if not self.available:
            return
        try:
            path = f"{self.driver_path}/win_lock"
            if os.path.exists(path):
                with open(path, "w") as f:
                    f.write("1" if locked else "0")
        except Exception:
            pass
            
    def write_mode(self, mode, speed=50):
        if not self.is_new_driver:
            return # Old driver does not support hardware animations
            
        if mode == "cycle":
            mode = "rainbow"
            
        try:
            with open(f"{self.driver_path}/animation_mode", "w") as f:
                f.write(mode)
                
            # Speed is 1-10 in new driver, GUI gives 1-100
            mapped_speed = max(1, min(10, int(speed / 10)))
            with open(f"{self.driver_path}/animation_speed", "w") as f:
                f.write(str(mapped_speed))
        except Exception as e:
            logger.error(f"Failed to write mode/speed: {e}")


class RGBService:
    """
    <node>
      <interface name="com.yyl.hpmanager.rgb">
        <method name="SetColor"><arg type="i" name="z" direction="in"/><arg type="s" name="h" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetMode"><arg type="s" name="m" direction="in"/><arg type="i" name="s" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetGlobal"><arg type="b" name="p" direction="in"/><arg type="i" name="b" direction="in"/><arg type="s" name="d" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetState"><arg type="s" name="j" direction="out"/></method>
        <method name="SetWinLock"><arg type="b" name="locked" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """

    def __init__(self):
        self._rgb = RGBController()
        self._config = ServiceConfig(
            "rgb",
            {
                "mode": "static",
                "colors": ["FF0000"] * 8,
                "speed": 50,
                "brightness": 100,
                "direction": "ltr",
                "power": True,
                "win_lock": False,
            },
        )
        self._config.load()

        # Validate loaded colors
        colors = self._config.get("colors", [])
        if isinstance(colors, list):
            cleaned = []
            for c in colors[:8]:
                cs = str(c).lstrip("#").upper()
                if HEX_COLOR_RE.match(cs):
                    cleaned.append(cs)
            if cleaned:
                c0 = cleaned[0]
                self._config.set("colors", (cleaned + [c0] * 8)[:8])

        # Validate mode
        if self._config.get("mode") not in VALID_LIGHT_MODES:
            self._config.set("mode", "static")

        self._apply_current_state()
        
        # Restore win lock
        if self._rgb.is_available():
            self._rgb.write_win_lock(self._config.get("win_lock", False))

        # Restore saved power state (delayed)
        if self._rgb.is_available():
            def _delayed_apply():
                self._apply_current_state()
            threading.Timer(3.0, _delayed_apply).start()
            
    def _apply_current_state(self):
        if not self._rgb.is_available():
            return

        power = self._config.get("power", True)
        if not power:
            self._rgb.write_brightness(0)
            return

        mode = self._config.get("mode", "static")
        speed = self._config.get("speed", 50)
        brightness = self._config.get("brightness", 100)
        colors = self._config.get("colors", ["FF0000"] * 8)

        if self._rgb.is_new_driver:
            self._rgb.write_brightness(brightness)
            # Always set the mode first — the driver may reset zone colours
            # when the mode changes, so writing colours *after* mode commit
            # ensures they are not overwritten by the driver's defaults.
            self._rgb.write_mode(mode, speed)
            if mode == "static":
                for i in range(self._rgb.zone_count):
                    color = colors[i] if i < len(colors) else colors[0]
                    self._rgb.write_zone(i, color)
        else:
            # hp-rgb-lighting (custom driver): supports zone_count zones (4 or 8).
            # No animation modes — static colour only; brightness is binary on/off.
            self._rgb.write_brightness(True)
            zone_count = self._rgb.zone_count
            for i in range(zone_count):
                # Extend colors list if fewer colors than zones are stored
                color = colors[i] if i < len(colors) else colors[0]
                self._rgb.write_zone(i, color)


    # ── D-Bus methods ─────────────────────────────────────────────────

    def SetColor(self, z, h):
        c = str(h).lstrip("#").upper()
        if not HEX_COLOR_RE.match(c):
            return "FAIL"

        self._config.set("mode", "static")
        self._config.set("power", True)
        if z == 8:
            self._config.set("colors", [c] * 8)
        elif 0 <= z < 8:
            colors = self._config.get("colors", ["FF0000"] * 8)
            colors[z] = c
            self._config.set("colors", colors)
        else:
            return "FAIL"
            
        self._config.save()
        self._apply_current_state()
        return "OK"

    def SetMode(self, m, s):
        if m not in VALID_LIGHT_MODES:
            return "FAIL"
        self._config.set("mode", m)
        self._config.set("speed", max(1, min(int(s), 100)))
        self._config.set("power", True)
        self._config.save()
        self._apply_current_state()
        return "OK"

    def SetGlobal(self, p, b, d):
        if d not in VALID_DIRECTIONS:
            return "FAIL"
        self._config.set("power", bool(p))
        self._config.set("brightness", max(0, min(int(b), 100)))
        self._config.set("direction", d)
        self._config.save()
        self._apply_current_state()
        return "OK"

    def GetState(self):
        snap = self._config.snapshot()
        snap["unsupported"] = getattr(self._rgb, "unsupported", False)
        snap["driver_active"] = self._rgb.available
        snap["driver_path"] = self._rgb.driver_path or ""
        snap["is_new_driver"] = getattr(self._rgb, "is_new_driver", False)
        if not self._rgb.available:
            snap["unavailable_reason"] = (
                "RGB kernel module not loaded. Install 'hp_rgb_lighting' or "
                "'omen-rgb-keyboard' and ensure it loads at boot "
                "(e.g. add to /etc/modules-load.d/)."
            )
        return json.dumps(snap)

    def SetWinLock(self, locked):
        logger.info("SetWinLock: %s", "LOCKED" if locked else "UNLOCKED")
        self._config.set("win_lock", bool(locked))
        self._rgb.write_win_lock(bool(locked))
        self._config.save()
        return "OK"

    def Ping(self):
        return "OK"


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    service = RGBService()
    run_service("com.yyl.hpmanager.rgb", service, service_name="rgb")

if __name__ == "__main__":
    main()
