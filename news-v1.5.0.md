# 🚀 OmenCtl v1.5.0 Release Notes — Re-branded & Re-engineered
### *⚡ More Modern. More Responsive. Simply Better.*

Welcome to the official release notes for **OmenCtl v1.5.0** (formerly known as *OMEN Command Center for Linux*). This release marks a massive milestone, bringing a complete re-branding, advanced low-level hardware optimizations, re-engineered fan safety algorithms, and complete legacy cleanup tools.

Below is an extensive breakdown of the major innovations, stability improvements, and features introduced in this release compared to the legacy versions.

---

## 🌌 1. Re-branding to OmenCtl
We have officially retired the lengthy name *OMEN Command Center for Linux* in favor of **OmenCtl**.
* **Clean Identity:** All GitHub clone URLs, package definitions (`PKGBUILD`), API release checks, and NixOS flake inputs are updated to use the new streamlined `OmenCtl` paths.
* **Update Continuity:** The built-in updater in the Settings page is fully wired to check `https://github.com/yunusemreyl/OmenCtl` for instant, seamless future updates.

---

## 🌪️ 2. Acoustic Fan Hysteresis & RPM Stability
Legacy fan controls would frequently "pulsate" or "rev" up and down as CPU temperatures hovered near a threshold. We have completely re-architected the fan daemon with a robust cooling safety system:
* **15-Sample Moving Average:** The temperature reader now calculates a rolling average across the last 15 seconds of CPU temperature queries, smoothing out quick, non-critical thermal spikes.
* **4.0°C Hysteresis Deadband:** Once the fans speed up to cool the laptop, they stay at that RPM until the CPU drops at least **4.0°C below** the trigger threshold. This keeps fan speeds smooth and prevents annoying pulsing noises.
* **400 RPM Jitter Filter:** Filters out micro-adjustments under 400 RPM, locking the fan speed to avoid unnecessary motor adjustments.

---

## ⚡ 3. ACPI/WMI Power Profiles & PolicyKit Bypass
Switching performance modes previously felt sluggish and often triggered annoying PolicyKit authentication popups or D-Bus access blocks. We redesigned this path from the ground up:
* **Dynamic WMI Capsules:** Instead of hardcoding power profile buttons, the UI now queries the ACPI/WMI bus dynamically at startup. It draws buttons representing the exact modes supported by your specific motherboard (e.g. `power-saver`, `balanced`, `performance`).
* **PolicyKit Bypass:** Integrated `powerprofilesctl` commands directly inside our root-level system microservice. You can now toggle power profiles instantly inside the GUI without ever seeing a PolicyKit password prompt.
* **Hardware-First Sync:** The ACPI platform profile register (`/sys/firmware/acpi/platform_profile`) is queried as the absolute source of truth, ensuring the GUI perfectly reflects physical motherboard registers.
* **cTGP & PPAB Rails:** Configurable TGP and Dynamic Boost limits are automatically set at the hardware level when performance mode is active.

---

## 🧹 4. Pristine Legacy Cleanup in `setup.sh`
To prevent system clashes between old and new packages, the installer (`setup.sh`) has been completely rewritten:
* **System Remnants Sweeper:** The update routine now systematically searches and recursively deletes all legacy directories, D-Bus configuration files, obsolete `omen-command-center` launchers, and services.
* **Clean Reloads:** Automatically reloads systemd, clears obsolete daemon socket locks, and cleanly starts the new optimized service suite.

---

## 🎨 5. Cyberpunk UI Refinements & Dynamic Theme Reactions
The interface has received a massive graphical update, yielding a sleek, high-fidelity experience:
* **Performance-Reactive Accents:** The global highlight colors react in real-time to your selected performance mode:
  * 🟢 **Power Saver:** Emerald Green highlight accents.
  * 🔴 **Balanced:** HP Omen Signature Crimson highlight accents.
  * 🟣 **Performance:** Glowing Amethyst Purple highlight accents.
* **Premium Telemetry Gauges:** High-contrast Dark and Light modes now feature beautiful, responsive mechanical radial speedometer gauges, displaying real-time telemetry like CPU/GPU loads, disk usage, fan speeds, and memory.
* **Visual Cards & badges:** The settings card borders are stylized with glowing left borders, and driver states are encapsulated in gorgeous status capsules.

---

## 🌈 6. Zero-overhead Keyboard RGB Animation
* **0% CPU Idle Mode:** Static colors are locked via an optimized signaling thread that consumes precisely **0% CPU**.
* **High-Efficiency Animations:** Wave, Cycle, Breathing, and Static animations are completely optimized with precise sleeping cycles to preserve system resources and thermal headroom.

---

## 🎮 7. Hardened MUX GPU Switching
* Graphics mode switching supporting `prime-select`, `supergfxctl`, and `envycontrol` backends has been hardened with intelligent fallback algorithms, preventing boot loops or missing graphic displays on mixed platforms.

---

## 📊 Summary Comparison

| Feature | Legacy Version | OmenCtl v1.5.0 (New) |
| :--- | :--- | :--- |
| **Acoustic Fan Sound** | Constant pulsing and speed revving | Perfectly smooth and silent hysteresis |
| **Power Profile Setup** | Hardcoded buttons (mismatches common) | Dynamically queried from ACPI WMI registers |
| **Authentication Flow** | Annoying PolicyKit popups on switches | Zero-auth instant switches via root microservice |
| **Old remnants** | Leftover folders caused conflicts | Automatic pristine legacy cleaner in setup.sh |
| **Interface Style** | Basic monochrome accents | High-fidelity performance-reactive accents |
| **RGB Performance** | Thread polling consumed CPU cycles | Zero-CPU idle locks for static color states |
| **GitHub updates** | Referenced old repo path | Fast, integrated OmenCtl release checking |

---

*Thank you to all our incredible issue openers and code contributors for making this release possible!*
