#!/usr/bin/env python3
import sys
import json
from pydbus import SystemBus

def print_usage():
    print("OmenCtl CLI (Command Line Interface)")
    print("Usage: omenctl <command> [args]")
    print("\nCommands:")
    print("  fan <max|auto|performance>    - Sets fan mode")
    print("  performans <profile>          - Sets power profile (performance, balanced, quiet)")
    print("  power <profile>               - Alias for performans")
    print("  klavye <mode>                 - Sets RGB mode (static, breathing, wave, rainbow, etc.)")
    print("  rgb <mode>                    - Alias for klavye")
    print("  mux <hybrid|discrete>         - Sets GPU mode")
    print("  dump                          - Generates auto-calibration & hardware report")
    print("  uninstall                     - Uninstalls OmenCtl from the system")
    print("  help                          - Shows this help menu")
    print("\nExamples:")
    print("  omenctl fan max")
    print("  omenctl power performance")
    print("  omenctl klavye wave")
    print("  omenctl mux discrete")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "--help", "-h"):
        print_usage()
        sys.exit(0)

    bus = SystemBus()
    cmd = sys.argv[1].lower()

    try:
        if cmd == "fan":
            if len(sys.argv) < 3:
                print("Error: fan command requires a mode (max, auto, performance)")
                sys.exit(1)
            
            sub = sys.argv[2].lower()
            if sub not in ("max", "auto", "performance"):
                print(f"Error: invalid fan mode '{sub}'")
                sys.exit(1)
            
            fan_svc = bus.get("com.yyl.hpmanager.fan")
            res = fan_svc.SetFanMode(sub)
            print(f"Fan mode set to '{sub}': {res}")

        elif cmd in ("performans", "power", "mode"):
            if len(sys.argv) < 3:
                print("Error: power command requires a profile (performance, balanced, quiet)")
                sys.exit(1)
            
            profile = sys.argv[2].lower()
            mapping = {
                "performance": "performance",
                "balanced": "balanced",
                "quiet": "power-saver",
                "eco": "power-saver",
                "powersaver": "power-saver"
            }
            target = mapping.get(profile)
            if not target:
                print(f"Error: invalid power profile '{profile}'. Valid profiles: performance, balanced, quiet")
                sys.exit(1)
            
            power_svc = bus.get("com.yyl.hpmanager.power")
            res = power_svc.SetPowerProfile(target)
            print(f"Power profile set to '{profile}': {res}")

        elif cmd in ("klavye", "rgb"):
            if len(sys.argv) < 3:
                print("Error: rgb command requires a mode (static, breathing, wave, rainbow, pulse, etc.)")
                sys.exit(1)
            
            mode = sys.argv[2].lower()
            rgb_svc = bus.get("com.yyl.hpmanager.rgb")
            # Speed is defaulted to 50 for CLI
            res = rgb_svc.SetMode(mode, 50)
            if res == "FAIL":
                print(f"Error: Invalid or unsupported RGB mode '{mode}'.")
            else:
                print(f"RGB mode set to '{mode}': {res}")

        elif cmd == "mux":
            if len(sys.argv) < 3:
                print("Error: mux command requires a mode (hybrid, discrete)")
                sys.exit(1)
            
            mode = sys.argv[2].lower()
            if mode not in ("hybrid", "discrete"):
                print(f"Error: invalid mux mode '{mode}'")
                sys.exit(1)
            
            mux_svc = bus.get("com.yyl.hpmanager.mux")
            res = mux_svc.SetGpuMode(mode)
            print(f"GPU mode set to '{mode}': {res}")
            if "REBOOT_REQUIRED" in res:
                print("Warning: A system reboot or session restart is required for changes to take effect.")

        elif cmd == "dump":
            plat_svc = bus.get("com.yyl.hpmanager.platform")
            res = plat_svc.GenerateHardwareDump()
            print(res)
            
        elif cmd == "uninstall":
            print("Starting uninstallation process...")
            import subprocess
            subprocess.run(["sudo", "hp-manager-uninstall"])

        else:
            print(f"Error: unknown command '{cmd}'")
            print_usage()
            sys.exit(1)

    except Exception as e:
        print(f"Error (Could not connect to service): {e}")
        print("Ensure that the background services (hpm-fan, hpm-power, etc.) are running.")
        sys.exit(1)

if __name__ == "__main__":
    main()
