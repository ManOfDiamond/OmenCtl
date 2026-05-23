# Adding Support for New Devices

If a new HP OMEN or Victus laptop model is released, it may require specific mappings to enable fan control, thermal profiles, or GPU power limits. Here is how to add support for a new device.

## Step 1: Identify the Board ID
First, determine the laptop's HP Board ID. This is a 4-character hex string (e.g., `8C77`, `8A25`).
You can find it by running:
```bash
cat /sys/class/dmi/id/board_name
```

## Step 2: Update the Kernel Thermal Profile Map
HP uses different Embedded Controller (EC) offsets and flags depending on the motherboard generation (Omen V0, Omen V1, Victus S, etc.).
1. Open `driver/hp-wmi.c`.
2. Locate the `board_thermal_profile_map` array.
3. Add a new entry for your Board ID, assigning it to the known thermal profile family that matches the hardware.
   ```c
   { "8C77", &omen_v1_thermal_params },
   { "8A25", &victus_s_thermal_params },
   ```
4. If the laptop introduces an entirely new thermal flag system, you must define a new `struct thermal_profile_params` with the correct `ec_tp_offset` and enum values, and add it to the map.

## Step 3: Enable GPU Power Limits (TGP/PPAB)
Newer OMEN and Victus laptops support dynamic GPU power target manipulation.
1. In `driver/hp-wmi.c`, locate the `is_victus_s_board` variable or the initialization logic inside `hp_wmi_bios_setup()`.
2. Ensure that your Board ID successfully sets the necessary boolean flags so that the `gpu_tgp` and `gpu_ppab` sysfs interfaces are exposed in `hp_wmi_is_visible()`.
3. Be careful: only expose these interfaces for boards that explicitly support them to avoid ACPI errors or system crashes.

## Step 4: Daemon and GUI Compatibility
In most cases, **no changes are needed** to the Python Daemons or GUI.
- The daemon (`fan_service.py` and `power_service.py`) dynamically detects features based on what `/sys` files the kernel driver exposes.
- If the new laptop has a different RGB layout (e.g., per-key RGB instead of 4-zone), you will need to update `driver/hp-rgb-lighting.c` to handle the new ACPI payload structure, and then update `src/gui/pages/rgb_page.py` to display the appropriate UI elements.

## Step 5: Test and Verify
Run the compilation to ensure no syntax errors were introduced:
```bash
cd driver
make -C /lib/modules/$(uname -r)/build M=$PWD modules
```
After installation, test changing fan modes and reading `dmesg` to verify that `hp_wmi_perform_query` completes successfully without error codes (e.g., `0x05` or `0x06`).
