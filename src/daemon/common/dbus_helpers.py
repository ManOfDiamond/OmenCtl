"""OMEN Command Center for Linux — D-Bus service bootstrap helpers.

Provides ``run_service()`` which handles the repetitive boilerplate that
every microservice needs:

1. Root privilege check
2. D-Bus bus-name ownership + object publishing
3. GLib main-loop
4. Graceful shutdown via SIGTERM / SIGINT
5. Optional sleep/wake event handling via logind
"""

import logging
import os
import re
import signal
import sys
import threading
import time

from gi.repository import GLib
from pydbus import SystemBus

logger = logging.getLogger("hp-manager.dbus")

# Shared flag — services can check this to pause work during sleep
system_sleeping = threading.Event()

# Idle auto-exit — when >0, a D-Bus-activated service quits after this many
# seconds without an incoming method call, so it consumes no resources while
# the GUI is closed.  systemd/D-Bus re-activate it on demand on the next call.
# Override with the HPM_IDLE_TIMEOUT environment variable (0 disables).
DEFAULT_IDLE_TIMEOUT = int(os.environ.get("HPM_IDLE_TIMEOUT", "45"))


def _setup_sleep_handler(service_name: str):
    """Subscribe to logind PrepareForSleep signals."""
    try:
        bus = SystemBus()

        def _on_prepare_for_sleep(sender, obj, iface, signal, params):
            if params:
                sleeping = params[0]
                if sleeping:
                    logger.info("[%s] System preparing for sleep", service_name)
                    system_sleeping.set()
                else:
                    logger.info("[%s] System waking up", service_name)
                    system_sleeping.clear()

        bus.subscribe(
            sender="org.freedesktop.login1",
            iface="org.freedesktop.login1.Manager",
            signal="PrepareForSleep",
            object="/org/freedesktop/login1",
            signal_fired=_on_prepare_for_sleep
        )
        logger.info("[%s] Sleep/wake handler registered", service_name)
    except Exception as exc:
        logger.warning(
            "[%s] Failed to register sleep handler: %s", service_name, exc
        )


def _install_idle_exit(loop, service_instance, service_name, timeout):
    """Quit *loop* after *timeout* seconds without any D-Bus method call.

    Only the methods declared in the service's introspection docstring
    (``<method name="…">``) are wrapped, so internal helpers and background
    threads never reset the idle timer.
    """
    last_activity = [time.monotonic()]

    doc = getattr(type(service_instance), "__doc__", "") or ""
    method_names = set(re.findall(r'<method name="([^"]+)"', doc))

    for name in method_names:
        original = getattr(service_instance, name, None)
        if not callable(original):
            continue

        def _make_wrapper(fn):
            def _wrapper(*args, **kwargs):
                last_activity[0] = time.monotonic()
                return fn(*args, **kwargs)

            return _wrapper

        try:
            setattr(service_instance, name, _make_wrapper(original))
        except Exception:
            pass

    def _tick():
        if time.monotonic() - last_activity[0] >= timeout:
            logger.info(
                "[%s] Idle for %ss — exiting (will re-activate on demand)",
                service_name,
                timeout,
            )
            loop.quit()
            return False
        return True

    # Check periodically; keep the interval well below the timeout.
    GLib.timeout_add_seconds(max(5, min(timeout, 15)), _tick)


def run_service(
    bus_name: str,
    service_instance,
    service_name: str = "unknown",
    handle_sleep: bool = True,
    idle_timeout: int = DEFAULT_IDLE_TIMEOUT,
):
    """Publish *service_instance* on the system D-Bus and run the main-loop.

    Parameters
    ----------
    bus_name : str
        The well-known D-Bus bus name, e.g. ``"com.yyl.hpmanager.fan"``.
    service_instance : object
        A pydbus-compatible service object with an introspection docstring.
    service_name : str
        Human-readable name used in log messages.
    handle_sleep : bool
        If True, register logind sleep/wake handler.
    idle_timeout : int
        Seconds of D-Bus inactivity after which the service exits so it stops
        consuming resources while the GUI is closed.  0 keeps it running
        forever (legacy always-on behaviour).
    """
    if os.geteuid() != 0:
        print(f"[{service_name}] Root privileges required.")
        sys.exit(1)

    loop = GLib.MainLoop()

    def _shutdown(*_args):
        logger.info("[%s] Shutting down…", service_name)
        loop.quit()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    if handle_sleep:
        _setup_sleep_handler(service_name)

    try:
        bus = SystemBus()
        # Keep a reference so the registration is not garbage-collected.
        _published = bus.publish(bus_name, service_instance)
        logger.info("[%s] Ready on D-Bus (%s)", service_name, bus_name)
        if idle_timeout and idle_timeout > 0:
            _install_idle_exit(loop, service_instance, service_name, idle_timeout)
        loop.run()
    except Exception as exc:
        logger.critical("[%s] Service error: %s", service_name, exc)
        sys.exit(1)
