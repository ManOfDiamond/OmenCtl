# Architecture & Communication Flow

The project is strictly separated into three privilege tiers: **User Space (Frontend)**, **System Daemon (Backend)**, and **Kernel Space (Drivers)**. 

They communicate linearly: `GUI -> D-Bus -> Daemon -> Sysfs -> Kernel -> ACPI/Firmware`.

## 1. User Space: The GUI (GTK4 + libadwaita)
- **Role:** Presents the visual interface to the user.
- **Privilege:** Runs as a standard, unprivileged user.
- **Communication:** It cannot directly touch hardware or system files. It communicates entirely by sending D-Bus messages to the System Bus.

## 2. D-Bus Authorization Layer
- **Role:** The security gatekeeper (`/etc/dbus-1/system.d/*.conf`).
- **Policy:** 
  - **Read Operations** (e.g., `GetState`) are open to all users.
  - **Write Operations** (e.g., `SetFanTarget`, `SetGpuMode`) are strictly restricted to users in the `wheel`, `sudo`, or `adm` groups. If an unprivileged application tries to change the fan speed, D-Bus blocks it at the IPC level.

## 3. System Daemon: Microservices
- **Role:** Handles the actual business logic, config saving, and sysfs manipulation.
- **Architecture:** Runs as `root` via systemd (`/etc/systemd/system/hpm-*.service`). It is sandboxed using systemd directives (no network access, strict filesystem mounting, restricted capabilities).
- **Communication:** Listens for D-Bus messages. When a valid write request arrives, the daemon validates the input using a centralized `sysfs.py` path validator, and writes the required values to `/sys` or `/proc` files.

## 4. Kernel Space: `hp-wmi` & `hp-rgb-lighting`
- **Role:** Acts as the bridge between the Linux OS and the HP proprietary firmware.
- **Communication:** The daemons write to sysfs nodes (e.g., `/sys/devices/platform/hp-wmi/thermal_profile`). The kernel driver intercepts these writes, validates them, locks a global `hp_wmi_mutex` to prevent race conditions, and sends the payload to the motherboard's Embedded Controller (EC) via ACPI `wmi_evaluate_method`.
