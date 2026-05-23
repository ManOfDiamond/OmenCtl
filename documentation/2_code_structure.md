# Code Structure & File Locations

The repository is organized by component layer to ensure maintainability.

## 1. Graphical User Interface (`src/gui/`)
The frontend is written in Python using GTK4.
- `main_window.py`: The entry point that sets up the main application window and navigation.
- `pages/`: Contains the logic and layout for individual tabs.
  - `fan_page.py`: Fan curves and modes.
  - `rgb_page.py`: Keyboard lighting controls.
  - `power_page.py`: Power profiles and GPU limits.
- `widgets/`: Reusable UI components (e.g., custom toggles, graphs).

## 2. Daemon Microservices (`src/daemon/`)
The backend is split into 5 distinct D-Bus microservices, running independently.
- `common/`:
  - `sysfs.py`: The critical centralized sysfs path validator (`_validate_path`) to prevent path traversal attacks.
  - `dbus_helpers.py`: Boilerplate for publishing D-Bus services.
  - `config.py`: Secure JSON config reader/writer.
- `services/`:
  - `fan_service.py`: Controls PWM fan speeds and detects fallback hwmon paths.
  - `power_service.py`: Orchestrates NVIDIA `nvidia-smi` limits and kernel TGP/PPAB limits.
  - `rgb_service.py`: Sends color arrays to the RGB kernel driver.
  - `mux_service.py`: Integrates with `supergfxctl` or `envycontrol` via secure subprocesses.
  - `platform_service.py`: Handles system monitoring (temperatures, battery, keyboard fixes).

## 3. Kernel Drivers (`driver/`)
Written in C, these DKMS modules are loaded into the Linux Kernel.
- `hp-wmi.c`: The primary driver. Handles WMI queries, exposes thermal profiles, GPU targets, and shortcuts. Uses `hp_wmi_mutex` to prevent ACPI clobbering.
- `hp-rgb-lighting.c`: A specialized driver for the 4-zone OMEN keyboard backlighting.

## 4. System Integration (`data/` & `scripts/`)
- `data/*.conf`: D-Bus XML policy files defining group-based access control.
- `data/*.service`: Systemd service definitions with sandbox configurations (`ProtectHome`, `CapabilityBoundingSet`).
- `scripts/`: Diagnostic and fix scripts (e.g., securely using `mktemp` for logs).
- `setup.sh`: The master installation script that orchestrates dependencies, DKMS builds, and systemd integration.
