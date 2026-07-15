#!/usr/bin/env python3
"""OMEN Command Center for Linux — Platform Microservice.

System info (CPU/GPU temp, battery, VRAM), keyboard fixes (hwdb),
and memory cache cleaning. D-Bus: ``com.yyl.hpmanager.platform``.
"""

import glob, json, os, platform, shutil, subprocess, sys, threading, time, typing

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.dbus_helpers import run_service, system_sleeping
from common.ec_controller import LinuxEcController
import common.acpi_mapper as acpi_mapper
from common.capabilities import get_cpu_model

logger = setup_logging("platform")


class PlatformService:
    """
    <node>
      <interface name="com.yyl.hpmanager.platform">
        <method name="GetSystemInfo"><arg type="s" name="j" direction="out"/></method>
        <method name="GetState"><arg type="s" name="j" direction="out"/></method>
        <method name="SetKeyboardFixes"><arg type="b" name="prtsc" direction="in"/><arg type="b" name="f1" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="CleanMemory"><arg type="s" name="result" direction="out"/></method>
        <method name="GenerateHardwareDump"><arg type="s" name="dump" direction="out"/></method>
        <method name="GetHardwareDumpJson"><arg type="s" name="dump" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """

    def __init__(self):
        self._config = ServiceConfig("platform", {"prtsc_fix": False, "f1_fix": False})
        self._config.load()
        self.ec = LinuxEcController()

        self._static_info = {
            "hostname": platform.node(),
            "kernel": platform.release(),
            "os_name": "Linux",
            "product_name": self.ec.product_name,
            "board_id": self.ec.board_id,
            "cpu_name": get_cpu_model(),
            "capabilities": self.ec.capabilities.to_dict(),
            "ec_access": self.ec.has_ec_access,
            "is_unsafe_ec": self.ec.is_unsafe_ec_model,
        }

        self._has_nvidia_smi = shutil.which("nvidia-smi") is not None
        self._cpu_temp_path: typing.Optional[str] = None
        self._gpu_temp_path: typing.Optional[str] = None
        self._find_temp_paths()

        self._last_nv_time = 0.0
        self._nv_temp_cache = 0.0
        self._nv_vram_cache = 0.0
        self._nv_fail_cooldown = 0.0
        self._nv_runtime_path = None
        self._find_nvidia_runtime_path()
        self._nv_unchanged_count = 0
        self._nv_poll_interval = 5.0

        self._cache_lock = threading.Lock()
        self._info_cache: typing.Dict[str, typing.Any] = {}
        self._last_dbus_call_time = 0.0

        # Restore keyboard fixes
        if self._config.get("prtsc_fix") or self._config.get("f1_fix"):
            self._write_hwdb_rules(self._config.get("prtsc_fix"), self._config.get("f1_fix"))

        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _find_nvidia_runtime_path(self):
        for path in glob.glob("/sys/bus/pci/devices/*/vendor"):
            try:
                with open(path) as f:
                    if "0x10de" in f.read():
                        d_path = os.path.dirname(path)
                        with open(os.path.join(d_path, "class")) as f_cls:
                            if f_cls.read().strip().startswith("0x03"):
                                self._nv_runtime_path = os.path.join(d_path, "power/runtime_status")
                                break
            except Exception:
                pass

    def _find_temp_paths(self):
        best_score = -1000
        RANK_DRV = {"zenpower":100,"coretemp":90,"k10temp":90,"cpu_thermal":80,"hp_wmi":60,"acpitz":30}
        RANK_LBL = {"tdie":100,"package id 0":95,"tctl":90,"core":80,"composite":50}
        try:
            for d in os.listdir("/sys/class/hwmon"):
                path = os.path.join("/sys/class/hwmon", d)
                try:
                    with open(os.path.join(path, "name")) as f:
                        drv = f.read().strip().lower()
                except Exception:
                    continue
                d_score = RANK_DRV.get(drv, 10)
                for tf in glob.glob(os.path.join(path, "temp*_input")):
                    try:
                        with open(tf) as f_test:
                            if int(f_test.read().strip()) <= 0:
                                continue
                    except Exception:
                        continue
                    label = ""
                    lp = tf.replace("_input", "_label")
                    if os.path.exists(lp):
                        try:
                            with open(lp) as f: label = f.read().strip().lower()
                        except Exception: pass
                    l_score = max((v for k,v in RANK_LBL.items() if k in label), default=0)
                    score = d_score + l_score - (500 if "75" in str(tf) else 0)
                    if score > best_score:
                        best_score = score
                        self._cpu_temp_path = tf
        except Exception:
            pass
        try:
            for d in os.listdir("/sys/class/hwmon"):
                path = os.path.join("/sys/class/hwmon", d)
                try:
                    with open(os.path.join(path, "name")) as f:
                        name = f.read().strip().lower()
                    if name in ("amdgpu", "i915", "nouveau"):
                        self._gpu_temp_path = os.path.join(path, "temp1_input")
                except Exception:
                    continue
        except Exception:
            pass

    def _monitor_loop(self):
        while True:
            if system_sleeping.is_set():
                time.sleep(0.5); continue
            info = self._static_info.copy()
            info["cpu_temp"] = self._get_cpu_temp()
            gpu = self._get_gpu_stats()
            info["gpu_temp"] = gpu["temp"]
            info["gpu_vram"] = gpu["vram_used"]
            info["battery"] = self._get_battery_info()
            with self._cache_lock:
                self._info_cache = info
            time.sleep(2.0)

    def _get_cpu_temp(self):
        if self._cpu_temp_path and os.path.exists(self._cpu_temp_path):
            try:
                with open(self._cpu_temp_path) as f:
                    t = int(f.read().strip()) / 1000.0
                    if t > -100.0:
                        return t
            except Exception: pass
        if self.ec.has_ec_access and not self.ec.is_unsafe_ec_model:
            t = self.ec.get_cpu_temp()
            if t > 0:
                return t
        return 0.0

    def _get_gpu_stats(self):
        stats = {"temp": 0.0, "vram_used": 0.0, "status": "Active"}
        if self._gpu_temp_path and os.path.exists(self._gpu_temp_path):
            try:
                with open(self._gpu_temp_path) as f:
                    t = int(f.read().strip()) / 1000.0
                    if t > -100.0:
                        stats["temp"] = t
            except Exception: pass
        if stats["temp"] == 0.0 and self.ec.has_ec_access and not self.ec.is_unsafe_ec_model:
            t = self.ec.get_gpu_temp()
            if t > 0:
                stats["temp"] = t

        if self._has_nvidia_smi:
            if self._nv_runtime_path and os.path.exists(self._nv_runtime_path):
                try:
                    with open(self._nv_runtime_path) as f:
                        if f.read().strip() == "suspended":
                            return {"temp": 0.0, "vram_used": 0.0, "status": "Suspended"}
                except Exception: pass

            now = time.time()
            if now - getattr(self, "_last_dbus_call_time", 0.0) > 15.0:
                stats["temp"] = max(stats["temp"], self._nv_temp_cache)
                stats["vram_used"] = self._nv_vram_cache
                return stats

            if now < self._nv_fail_cooldown:
                stats["temp"] = max(stats["temp"], self._nv_temp_cache)
                stats["vram_used"] = self._nv_vram_cache
                return stats

            if now - self._last_nv_time >= self._nv_poll_interval:
                self._last_nv_time = now
                try:
                    out = subprocess.check_output(
                        ["nvidia-smi","--query-gpu=temperature.gpu,memory.used","--format=csv,noheader,nounits"],
                        stderr=subprocess.DEVNULL, timeout=1.0
                    ).decode().strip()
                    parts = out.split(",")
                    if len(parts) >= 2:
                        new_temp = float(parts[0].strip())
                        new_vram = float(parts[1].strip())
                        if new_vram == self._nv_vram_cache:
                            self._nv_unchanged_count += 1
                            if self._nv_unchanged_count >= 3:
                                self._nv_poll_interval = 10.0
                        else:
                            self._nv_unchanged_count = 0
                            self._nv_poll_interval = 5.0
                        self._nv_temp_cache = new_temp
                        self._nv_vram_cache = new_vram
                except Exception:
                    self._nv_fail_cooldown = now + 15.0
            stats["temp"] = max(stats["temp"], self._nv_temp_cache)
            stats["vram_used"] = self._nv_vram_cache
        return stats

    def _get_battery_info(self):
        bat = {}
        path = "/sys/class/power_supply/BAT0"
        if not os.path.exists(path): return bat
        try:
            with open(os.path.join(path, "status")) as f: bat["status"] = f.read().strip()
            with open(os.path.join(path, "capacity")) as f: bat["capacity"] = int(f.read().strip())
        except Exception: pass
        try:
            with open(os.path.join(path, "cycle_count")) as f: bat["cycle_count"] = int(f.read().strip())
        except Exception: pass
        try:
            with open(os.path.join(path, "charge_full")) as f: cf = int(f.read().strip())
            with open(os.path.join(path, "charge_full_design")) as f: cfd = int(f.read().strip())
            if cfd > 0: bat["health"] = min(100, int((cf / cfd) * 100))
        except Exception: pass
        try:
            with open(os.path.join(path, "power_now")) as f:
                bat["power_now"] = int(f.read().strip()) / 1000000.0
        except Exception: pass
        return bat

    # ── D-Bus methods ─────────────────────────────────────────────────

    def GetSystemInfo(self):
        self._last_dbus_call_time = time.time()
        with self._cache_lock:
            return json.dumps(self._info_cache)

    def GetHardwareDumpJson(self):
        """Returns hardware dump data (ACPI, System, EC) as pure JSON."""
        logger.info("Generating hardware dump (JSON)...")
        data = {
            "system": {},
            "ec": {},
            "acpi": {}
        }
        
        # Basic Info
        with self._cache_lock:
            info = self._info_cache.copy()
            data["system"] = {
                "product_name": info.get('product_name', 'Unknown'),
                "board_id": info.get('board_id', 'Unknown'),
                "cpu_name": info.get('cpu_name', 'Unknown'),
                "kernel": info.get('kernel', 'Unknown')
            }

        # EC Data
        data["ec"]["supported"] = self.ec.has_ec_access
        if self.ec.has_ec_access:
            data["ec"]["capabilities"] = self.ec.capabilities.to_dict()

        # ACPI Data
        data["acpi"] = acpi_mapper.dump_and_analyze_acpi()

        return json.dumps(data)

    def GenerateHardwareDump(self):
        logger.info("Generating hardware dump...")
        lines = [
            "# OmenCtl Auto-Calibration & Hardware Report",
            "",
            "Paste this into a new GitHub issue at https://github.com/yunusemreyl/OmenCtl/issues to add your board to the model database.",
            ""
        ]

        # Basic Info
        with self._cache_lock:
            info = self._info_cache.copy()
            lines.append("## System")
            lines.append(f"- **Product Name:** {info.get('product_name', 'Unknown')}")
            lines.append(f"- **Board ID:** {info.get('board_id', 'Unknown')}")
            lines.append(f"- **CPU:** {info.get('cpu_name', 'Unknown')}")
            lines.append(f"- **Kernel:** {info.get('kernel', 'Unknown')}")
            lines.append("")

        # EC Data
        lines.append("## EC Access")
        lines.append(f"- **Supported:** {self.ec.has_ec_access}")
        if self.ec.has_ec_access:
            lines.append("### Capabilities")
            caps = self.ec.capabilities.to_dict()
            for k, v in caps.items():
                lines.append(f"  - **{k}**: {v}")
        lines.append("")

        # ACPI DSDT Data
        lines.append("## ACPI & DSDT Analysis")
        acpi_data = acpi_mapper.dump_and_analyze_acpi()
        
        if acpi_data.get("status") == "error":
            lines.append("⚠️ **ACPI Analysis Failed:**")
            for err in acpi_data.get("errors", []):
                lines.append(f"- {err}")
            lines.append("\n*Note: Install `acpica` or `acpica-tools` to enable DSDT decompilation.*")
        else:
            lines.append("### Discovered Methods")
            methods = acpi_data.get("methods_found", {})
            if not methods:
                lines.append("- *No known OMEN ACPI methods found.*")
            else:
                for m, desc in methods.items():
                    lines.append(f"- **{m}**: {desc}")
            
            lines.append("")
            lines.append("### WMI GUIDs Found")
            guids = acpi_data.get("wmi_guids", [])
            if not guids:
                lines.append("- *No UUIDs found.*")
            else:
                for g in sorted(guids):
                    lines.append(f"- `{g}`")

        return "\n".join(lines)

    def GetState(self):
        return json.dumps(self._config.snapshot())

    def SetKeyboardFixes(self, prtsc, f1):
        logger.info("SetKeyboardFixes: prtsc=%s, f1=%s", prtsc, f1)
        self._config.set("prtsc_fix", bool(prtsc))
        self._config.set("f1_fix", bool(f1))
        self._write_hwdb_rules(prtsc, f1)
        self._config.save()
        return "OK"

    def _write_hwdb_rules(self, prtsc, f1):
        logger.info("Writing hwdb rules: prtsc=%s, f1=%s", prtsc, f1)
        if os.path.exists("/etc/NIXOS") or os.path.exists("/run/current-system/sw/bin/nixos-version"):
            logger.info("NixOS detected, skipping immutable /etc/udev/hwdb.d write")
            return
        hwdb_path = "/etc/udev/hwdb.d/90-hp-keyboard-fixes.hwdb"
        if not prtsc and not f1:
            if os.path.exists(hwdb_path):
                try:
                    os.remove(hwdb_path)
                    subprocess.run(["systemd-hwdb", "update"], capture_output=True, check=True, timeout=10)
                    subprocess.run(["udevadm", "trigger", "-s", "input"], capture_output=True, check=True, timeout=10)
                except Exception: pass
            return
        content = [
            "# HP Keyboard Fixes - Generated by OMEN Command Center for Linux",
            "evdev:atkbd:dmi:bvn*:bvr*:bd*:svnHP*:pn*:*",
        ]
        if prtsc: content.append(" KEYBOARD_KEY_b7=sysrq")
        if f1: content.append(" KEYBOARD_KEY_ab=f1")
        new_content = "\n".join(content) + "\n"
        if os.path.exists(hwdb_path):
            try:
                with open(hwdb_path) as f:
                    if f.read() == new_content: return
            except Exception: pass
        try:
            os.makedirs(os.path.dirname(hwdb_path), exist_ok=True)
            with open(hwdb_path, "w") as f: f.write(new_content)
            def _apply():
                try:
                    subprocess.run(["systemd-hwdb", "update"], check=True, timeout=10)
                    subprocess.run(["udevadm", "trigger", "-s", "input"], check=True, timeout=10)
                    logger.info("Keyboard fixes applied via hwdb")
                except Exception as e:
                    logger.error("Failed to apply hwdb: %s", e)
            threading.Thread(target=_apply, daemon=True).start()
        except Exception as e:
            logger.error("Failed to write hwdb rules: %s", e)

    def CleanMemory(self):
        logger.info("CleanMemory called")
        try:
            subprocess.run(["sync"], check=True, timeout=5)
            with open("/proc/sys/vm/drop_caches", "w") as f: f.write("3\n")
            logger.info("Memory cache cleared successfully")
            return "OK"
        except Exception as e:
            logger.error("CleanMemory failed: %s", e)
            return f"Error: {e}"

    def Ping(self):
        return "OK"


def main():
    svc = PlatformService()
    run_service("com.yyl.hpmanager.platform", svc, service_name="platform")

if __name__ == "__main__":
    main()
