#!/usr/bin/env python3
"""OMEN Command Center for Linux — Standalone Tray Icon Process.

Runs in a separate process to prevent GTK3 (AppIndicator) and GTK4 mainloop conflicts.
"""

import os
import sys
import subprocess
import time
import json
import threading

try:
    from PIL import Image
    import pystray
    from pydbus import SystemBus
except ImportError as e:
    print(f"Required dependency missing ({e}). Tray icon unavailable.")
    sys.exit(0)

# Local state cache to avoid freezing the tray on slow DBus calls
state_cache = {
    "power": "balanced",
    "fan": "auto",
    "mux": "hybrid",
    "color": "off"
}

bus = None

def get_bus():
    global bus
    if not bus:
        try:
            bus = SystemBus()
        except Exception:
            pass
    return bus

def update_state_from_dbus():
    b = get_bus()
    if not b: return
    try:
        power_svc = b.get("com.yyl.hpmanager.power")
        state_cache["power"] = power_svc.GetPowerProfile().lower()
    except Exception: pass
    
    try:
        fan_svc = b.get("com.yyl.hpmanager.fan")
        fm = fan_svc.GetFanMode()
        if isinstance(fm, str):
            state_cache["fan"] = fm.lower()
    except Exception: pass
    
    try:
        mux_svc = b.get("com.yyl.hpmanager.mux")
        state_cache["mux"] = mux_svc.GetGpuMode().lower()
    except Exception: pass

    try:
        rgb_svc = b.get("com.yyl.hpmanager.rgb")
        rgb_state = json.loads(rgb_svc.GetState())
        if not rgb_state.get("power", True):
            state_cache["color"] = "off"
        else:
            colors = rgb_state.get("colors", [])
            if colors and colors[0]:
                c = colors[0].upper()
                if c == "FF0000": state_cache["color"] = "red"
                elif c == "00FF00": state_cache["color"] = "green"
                elif c == "0000FF": state_cache["color"] = "blue"
                elif c == "FFFFFF": state_cache["color"] = "white"
                else: state_cache["color"] = "custom"
    except Exception: pass

def run_dbus_call(svc_name, method_name, *args):
    def _call():
        b = get_bus()
        if b:
            try:
                svc = b.get(svc_name)
                getattr(svc, method_name)(*args)
                update_state_from_dbus() # Refresh state after call
            except Exception as e:
                print(f"DBus error {svc_name}.{method_name}: {e}")
    threading.Thread(target=_call, daemon=True).start()

def set_power(icon, item):
    val = item.text.lower().replace("power saver", "power-saver")
    state_cache["power"] = val
    run_dbus_call("com.yyl.hpmanager.power", "SetPowerProfile", val)

def is_power(item):
    val = item.text.lower().replace("power saver", "power-saver")
    return state_cache["power"] == val

def set_fan(icon, item):
    val = item.text.lower()
    state_cache["fan"] = val
    run_dbus_call("com.yyl.hpmanager.fan", "SetFanMode", val)

def is_fan(item):
    return state_cache["fan"] == item.text.lower()

def set_mux(icon, item):
    val = item.text.lower()
    state_cache["mux"] = val
    run_dbus_call("com.yyl.hpmanager.mux", "SetGpuMode", val)

def is_mux(item):
    return state_cache["mux"] == item.text.lower()

def set_color(icon, item):
    val = item.text.lower()
    state_cache["color"] = val
    
    if val == "off":
        def _off():
            b = get_bus()
            if b:
                try:
                    rgb_svc = b.get("com.yyl.hpmanager.rgb")
                    st = json.loads(rgb_svc.GetState())
                    rgb_svc.SetGlobal(False, st.get("brightness", 100), st.get("direction", "ltr"))
                except Exception as e: print(e)
        threading.Thread(target=_off, daemon=True).start()
    else:
        colors = {
            "red": "FF0000",
            "green": "00FF00",
            "blue": "0000FF",
            "white": "FFFFFF"
        }
        c = colors.get(val, "FFFFFF")
        run_dbus_call("com.yyl.hpmanager.rgb", "SetColor", 8, c)

def is_color(item):
    return state_cache["color"] == item.text.lower()

def on_open(icon, item):
    subprocess.Popen(["omenctl"])

def on_quit(icon, item):
    icon.stop()

def bg_updater():
    while True:
        update_state_from_dbus()
        time.sleep(5)

def main():
    icon_path = "/usr/share/icons/hicolor/48x48/apps/omenctl.png"
    if not os.path.exists(icon_path):
        icon_path = "/usr/share/hp-manager/images/omenctl.png"
    if not os.path.exists(icon_path) and os.path.exists("images/omenctl.png"):
        icon_path = "images/omenctl.png"
        
    if os.path.exists(icon_path):
        image = Image.open(icon_path)
    else:
        image = Image.new('RGB', (64, 64), color=(15, 15, 15))

    update_state_from_dbus()
    threading.Thread(target=bg_updater, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem("Open OmenCtl", on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Power Mode", pystray.Menu(
            pystray.MenuItem("Performance", set_power, checked=is_power, radio=True),
            pystray.MenuItem("Balanced", set_power, checked=is_power, radio=True),
            pystray.MenuItem("Power Saver", set_power, checked=is_power, radio=True)
        )),
        pystray.MenuItem("Fan Mode", pystray.Menu(
            pystray.MenuItem("Max", set_fan, checked=is_fan, radio=True),
            pystray.MenuItem("Auto", set_fan, checked=is_fan, radio=True),
            pystray.MenuItem("Custom", set_fan, checked=is_fan, radio=True)
        )),
        pystray.MenuItem("GPU Mode", pystray.Menu(
            pystray.MenuItem("Hybrid", set_mux, checked=is_mux, radio=True),
            pystray.MenuItem("Discrete", set_mux, checked=is_mux, radio=True)
        )),
        pystray.MenuItem("Keyboard Lighting", pystray.Menu(
            pystray.MenuItem("Off", set_color, checked=is_color, radio=True),
            pystray.MenuItem("Red", set_color, checked=is_color, radio=True),
            pystray.MenuItem("Green", set_color, checked=is_color, radio=True),
            pystray.MenuItem("Blue", set_color, checked=is_color, radio=True),
            pystray.MenuItem("White", set_color, checked=is_color, radio=True)
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit)
    )

    icon = pystray.Icon("omenctl", image, "OmenCtl", menu)
    
    for attempt in range(12):
        try:
            icon.run()
            break
        except Exception as e:
            print(f"pystray run failed (attempt {attempt+1}): {e}. Retrying in 3 seconds...")
            time.sleep(3)

if __name__ == "__main__":
    main()
