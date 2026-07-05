#!/usr/bin/env python3
"""
OMEN Command Center for Linux — HwMon Controller.

Linux hwmon sensor interface for temperature monitoring.
Reads from /sys/class/hwmon/* to get CPU and GPU temperatures.
This is preferred over EC-based temperature reading when available.
"""

import os
import glob
import time
import logging
import threading

logger = logging.getLogger("hwmon_controller")

HWMON_PATH = "/sys/class/hwmon"
THERMAL_ZONE_PATH = "/sys/class/thermal"
MIN_TEMP_C = 1.0
MAX_TEMP_C = 125.0


class LinuxHwMonController:
    def __init__(self):
        self._lock = threading.Lock()
        self._cpu_sensor_paths = []
        self._gpu_sensor_paths = []
        self._sensor_failure_count = {}
        self._max_failures_before_skip = 5
        self._last_full_scan = 0.0
        self._rescan_interval = 300.0  # 5 minutes
        
        self.discover_sensors()

    @property
    def has_cpu_sensor(self):
        with self._lock:
            return len(self._cpu_sensor_paths) > 0

    @property
    def has_gpu_sensor(self):
        with self._lock:
            return len(self._gpu_sensor_paths) > 0

    @property
    def available_sensor_count(self):
        with self._lock:
            return len(self._cpu_sensor_paths) + len(self._gpu_sensor_paths)

    def discover_sensors(self):
        with self._lock:
            self._cpu_sensor_paths.clear()
            self._gpu_sensor_paths.clear()
            # Periodically clear failure count so skipped sensors get a retry
            self._sensor_failure_count.clear()
            self._last_full_scan = time.monotonic()
            
            self._discover_hwmon_sensors()
            self._discover_thermal_zones()
        
    def _discover_hwmon_sensors(self):
        if not os.path.exists(HWMON_PATH):
            return
            
        for hwmon_dir in glob.glob(os.path.join(HWMON_PATH, "hwmon*")):
            name_path = os.path.join(hwmon_dir, "name")
            if not os.path.exists(name_path):
                continue
                
            try:
                with open(name_path, "r") as f:
                    name = f.read().strip().lower()
                    
                # CPU sensors
                if any(x in name for x in ["coretemp", "k10temp", "zenpower", "amd_energy", "thinkpad", "hp", "acpitz"]):
                    self._add_cpu_sensor_paths(hwmon_dir)
                    
                # GPU sensors
                if any(x in name for x in ["nvidia", "nouveau", "amdgpu", "radeon"]):
                    self._add_gpu_sensor_paths(hwmon_dir)
            except Exception:
                pass
                
    def _discover_thermal_zones(self):
        if not os.path.exists(THERMAL_ZONE_PATH):
            return
            
        for zone_dir in glob.glob(os.path.join(THERMAL_ZONE_PATH, "thermal_zone*")):
            type_path = os.path.join(zone_dir, "type")
            temp_path = os.path.join(zone_dir, "temp")
            
            if not os.path.exists(type_path) or not os.path.exists(temp_path):
                continue
                
            try:
                with open(type_path, "r") as f:
                    zone_type = f.read().strip().lower()
                    
                # CPU-related thermal zones
                if any(x in zone_type for x in ["x86_pkg", "acpitz", "cpu", "soc"]):
                    if temp_path not in self._cpu_sensor_paths:
                        self._cpu_sensor_paths.append(temp_path)
                        
                # GPU thermal zones
                if any(x in zone_type for x in ["gpu", "nvidia"]):
                    if temp_path not in self._gpu_sensor_paths:
                        self._gpu_sensor_paths.append(temp_path)
            except Exception:
                pass

    def _add_cpu_sensor_paths(self, hwmon_dir):
        for suffix in ["temp1_input", "temp2_input", "temp3_input"]:
            path = os.path.join(hwmon_dir, suffix)
            if os.path.exists(path) and path not in self._cpu_sensor_paths:
                self._cpu_sensor_paths.append(path)

    def _add_gpu_sensor_paths(self, hwmon_dir):
        for suffix in ["temp1_input", "temp2_input"]:
            path = os.path.join(hwmon_dir, suffix)
            if os.path.exists(path) and path not in self._gpu_sensor_paths:
                self._gpu_sensor_paths.append(path)

    def get_cpu_temperature(self):
        with self._lock:
            paths = list(self._cpu_sensor_paths)
        return self._get_temperature_reading(paths)

    def get_gpu_temperature(self):
        with self._lock:
            paths = list(self._gpu_sensor_paths)
        return self._get_temperature_reading(paths)

    def _should_skip_sensor(self, path):
        with self._lock:
            return self._sensor_failure_count.get(path, 0) >= self._max_failures_before_skip

    def _get_temperature_reading(self, sensor_paths):
        # Auto-rediscover if interval passed
        with self._lock:
            should_rescan = (time.monotonic() - self._last_full_scan) > self._rescan_interval
        
        if should_rescan:
            self.discover_sensors()

        for path in sensor_paths:
            if self._should_skip_sensor(path):
                continue

            temp = self._read_temperature_file(path)
            if temp is not None:
                self._reset_sensor_failure(path)
                return temp

            self._record_sensor_failure(path)

        return None

    def _record_sensor_failure(self, path):
        with self._lock:
            self._sensor_failure_count[path] = self._sensor_failure_count.get(path, 0) + 1

    def _reset_sensor_failure(self, path):
        with self._lock:
            self._sensor_failure_count[path] = 0

    def _read_temperature_file(self, path):
        try:
            if not os.path.exists(path):
                return None
                
            with open(path, "r") as f:
                content = f.read().strip()
                if content.isdigit() or (content.startswith('-') and content[1:].isdigit()):
                    value = int(content)
                    temperature = value / 1000.0
                    if MIN_TEMP_C <= temperature <= MAX_TEMP_C:
                        return temperature
        except Exception:
            pass
        return None

    def get_all_sensors(self):
        results = []
        if not os.path.exists(HWMON_PATH):
            return results
            
        for hwmon_dir in glob.glob(os.path.join(HWMON_PATH, "hwmon*")):
            name = "unknown"
            try:
                name_path = os.path.join(hwmon_dir, "name")
                if os.path.exists(name_path):
                    with open(name_path, "r") as f:
                        name = f.read().strip()
            except Exception:
                pass
                
            for temp_file in glob.glob(os.path.join(hwmon_dir, "temp*_input")):
                try:
                    with open(temp_file, "r") as f:
                        content = f.read().strip()
                        if content.isdigit() or (content.startswith('-') and content[1:].isdigit()):
                            millidegrees = int(content)
                            label = os.path.basename(temp_file).replace("_input", "")
                            results.append({
                                "name": name,
                                "label": label,
                                "temp": millidegrees / 1000.0
                            })
                except Exception:
                    pass
                    
        return results
