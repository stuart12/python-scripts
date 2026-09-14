#!/usr/bin/python3 -BP
# -*- coding: utf-8 -*-
# publish_mdns Copyright (C) 2026  Stuart Pook (http://www.pook.it/)
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Requires, on Debian/Ubuntu: apt install python3-dbus python3-gi avahi-utils
# (python3-dbus and python3-gi are C-library bindings, not installable via pip;
# avahi-utils provides the avahi-publish binary this script shells out to)

import sys
import signal
import socket
import subprocess
import argparse
import logging as do_not_use
import pathlib

import dbus
import dbus.mainloop.glib
from gi.repository import GLib

logger = do_not_use.getLogger(__name__)


def set_logging_level(loglevel: int) -> None:
    script_name = pathlib.Path(sys.argv[0]).name
    do_not_use.basicConfig(
        level=do_not_use.WARNING,
        format=f"{script_name}:%(levelname)s:%(name)s:%(message)s",
        force=True,
    )
    logger.setLevel(loglevel)


def error(message: str) -> None:
    logger.critical(message)
    sys.exit(8)


def get_local_ip() -> str | None:
    """Ask the kernel which local address it would use to reach the
    internet, without sending any packets (UDP connect() only resolves
    routing — same trick as `ip route get 1.1.1.1`)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
        logger.info("current local IP is %s", ip)
        return ip
    except OSError as e:
        logger.info("could not determine local IP: %s", e)
        return None
    finally:
        s.close()


class MdnsPublisher:
    def __init__(self, hostname: str):
        self.hostname = hostname
        self.current_ip: str | None = None
        self.proc: subprocess.Popen | None = None

    def stop_publish(self) -> None:
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.proc = None

    def start_publish(self, ip: str) -> None:
        try:
            self.proc = subprocess.Popen(
                ["avahi-publish", "--no-reverse", "--address", f"{self.hostname}.local", ip]
            )
        except FileNotFoundError:
            error("avahi-publish not found: is avahi-utils installed?")

    def reconcile(self) -> None:
        ip = get_local_ip()
        if ip == self.current_ip:
            return
        logger.warning("IP changed: %s -> %s, restarting avahi-publish", self.current_ip, ip)
        self.stop_publish()
        self.current_ip = ip
        if ip is not None:
            self.start_publish(ip)

    def on_state_changed(self, *args, **kwargs) -> None:
        self.reconcile()

    def shutdown(self, *_):
        logger.warning("shutting down, stopping avahi-publish")
        self.stop_publish()
        sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="publish an mDNS hostname pointing at this machine's current IP, "
                    "restarting the publish whenever the IP changes",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.set_defaults(loglevel='warning')
    parser.add_argument("--hostname", required=True, help="mDNS hostname to publish with an appended .local suffix")
    parser.add_argument(
        "-v", "--verbose", "--debug", dest='loglevel', action="store_const", const='debug', help="debug loglevel")
    parser.add_argument("-l", "--loglevel", metavar="LEVEL", help="set logging level")

    options = parser.parse_args()

    set_logging_level(getattr(do_not_use, options.loglevel.upper(), None))
    
    if "." in options.hostname:
        error(f"--hostname must be a single label, without any dots (the .local suffix is appended automatically): {options.hostname}")

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    publisher = MdnsPublisher(options.hostname)

    bus.add_signal_receiver(
        publisher.on_state_changed,
        signal_name="StateChanged",
        dbus_interface="org.freedesktop.NetworkManager",
        path="/org/freedesktop/NetworkManager",
    )

    signal.signal(signal.SIGTERM, publisher.shutdown)
    signal.signal(signal.SIGINT, publisher.shutdown)

    publisher.reconcile()  # establish initial state without waiting for a signal
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
