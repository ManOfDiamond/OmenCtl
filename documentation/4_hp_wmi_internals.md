# Driver Internals: `hp-wmi.c`

The `hp-wmi.c` driver is the core bridge between the Linux kernel and the HP ACPI WMI firmware. Because HP uses various generations of embedded controllers (EC) and firmware interfaces across different laptop models, this file contains significant abstraction and compatibility mapping.

Below is a detailed breakdown of the file structure and where specific logic resides.

## 1. Constants, Enums & Structs (Lines 1 - 150)
- **Defines & GUIDs:** The WMI GUIDs (e.g., `HPWMI_BIOS_GUID`) are defined at the very beginning.
- **Thermal Enums:** Different generations of HP motherboards use different integer values for their thermal modes (Default, Performance, Quiet). You will find `enum hp_thermal_profile_omen_v0`, `_omen_v1`, `_victus`, and `_victus_s` mapped out here.
- **`struct thermal_profile_params`:** This struct defines the EC offset used for manipulating thermal profiles for a given generation.

## 2. Compatibility Matrix & Board Lists (Lines 160 - 250)
Because WMI methods can crash unsupported systems, the driver strictly checks the DMI Board ID (e.g., `8C77`) against hardcoded arrays.
- `omen_thermal_profile_boards`
- `victus_thermal_profile_boards`
- `victus_s_thermal_profile_boards`

*When adding a new device, its Board ID must be added to the appropriate array here.*

## 3. WMI Execution Core (Lines 600 - 650)
- **`hp_wmi_perform_query`:** This is the most critical function in the driver. It takes query commands, wraps them in the `bios_args` structure, safely allocates them using `kzalloc`, and invokes the kernel's `wmi_evaluate_method`.
- **Security Note:** This function is protected by the `hp_wmi_mutex` to prevent race conditions when the `hp-rgb-lighting` driver simultaneously attempts to write to the ACPI firmware.

## 4. Thermal Profile Logic (Lines 800 - 1000)
- **`omen_thermal_profile_set` / `_get`:** Functions that map the standard Linux sysfs integer (0, 1, 2) to the proprietary HP enum values based on the `active_thermal_profile_params` determined during initialization.

## 5. GPU Power Limits (TGP/PPAB) (Lines 1180 - 1400)
- Functions like `victus_s_gpu_thermal_profile_get` read and write to the GPU power target WMI variables.
- Sysfs interfaces like `gpu_tgp_store` and `gpu_ppab_store` allow user-space daemons (like `power_service.py`) to toggle these limits.
- **Visibility (`hp_wmi_is_visible`):** Prevents these sysfs nodes from appearing on laptops that do not support dynamic TGP adjustment.

## 6. WMI Notify Handler (Lines 1400 - 1600)
- **`hp_wmi_notify`:** Listens for asynchronous WMI events from the firmware, such as the user pressing the physical OMEN key (usually mapping it to `KEY_PROG2` or `XF86Launch2`).

## 7. Advanced Fan Control & EC Flags (Lines 1700 - 2000)
- **`omen_thermal_profile_ec_flags_set`:** Directly manipulates the Embedded Controller (EC) memory to override default BIOS fan curves. This is heavily used by the "Max Fan" toggles.

## 8. Hwmon & Sysfs Interfaces (Lines 2000 - 2500)
- Contains the `show` and `store` methods for standard `hwmon` interfaces (`pwm1`, `fan1_input`, `temp1_input`). This is what allows `fan_service.py` to read RPMs and set manual fan speeds.

## 9. Initialization (Lines 2500 - 3250)
- **`hp_wmi_hwmon_init` & `hp_wmi_bios_setup`:** Probes the system on boot, identifies the Board ID, sets up the compatibility flags (`is_victus_s_board`), and registers the sysfs and hwmon devices with the Linux kernel.
- **`hp_wmi_init`:** The standard Linux kernel module entry point.
