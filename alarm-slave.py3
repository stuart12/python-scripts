#!/usr/bin/python3
# playnewestpod Copyright (c) 2015 Stuart Pook (http://www.pook.it/)
# program and ring an alarm on a remote machine
# set expandtab copyindent preserveindent softtabstop=0 shiftwidth=4 tabstop=4
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import argparse
import sys
import subprocess
import tempfile
import time
import shlex
import syslog

# http://zeromq.org/
# https://stackoverflow.com/questions/22390064/use-dbus-to-just-send-a-message-in-python

# apt-get install gir1.2-gtksource-3.0
#from gi.repository import Gtk

# sudo apt-get install python3-dbus
#import dbus

#import dbus.service
#from dbus.mainloop.glib import DBusGMainLoop

def myname():
    return os.path.basename(sys.argv[0])

def error(options, *args):
    if options.syslog:
        syslog.syslog("error: " + " ".join(args))
    else:
        print(myname() + ": error:", *args, file=sys.stderr)
    sys.exit(9)

def verbose(options, *args):
    if options.verbosity > 0:
        if options.syslog:
            syslog.syslog(" ".join(args))
        else:
            print(myname() + ":", *args, file=sys.stderr)

def format_cmd(cmd):
    return ' '.join(shlex.quote(c) for c in cmd)

def print_cmd(options, cmd):
    verbose(options, "run", format_cmd(cmd))
    return cmd

def do_sleep(options):
    dbus_interface= options.dbus_interface

    class MyDBUSService(dbus.service.Object):
        def __init__(self, options):
            bus_name = dbus.service.BusName(options.bus_name, bus=dbus.SystemBus())
            dbus.service.Object.__init__(self, bus_name, options.object_path)
            self.options = options

        @dbus.service.method(dbus_interface)
        def hello(self):
            """returns the string 'Hello, World!'"""
            return "Hello, World!"

        @dbus.service.method(dbus_interface)
        def string_echo(self, s):
            """returns whatever is passed to it"""
            return s

        @dbus.service.method(dbus_interface)
        def Quit(self):
            """removes this object from the DBUS connection and exits"""
            self.remove_from_connection()
            #Gtk.main_quit()
            return
    DBusGMainLoop(set_as_default=True)
    myservice = MyDBUSService(options)
    #Gtk.main()
    import gobject

    loop = gobject.MainLoop()
    loop.run()

def sleeper(options):
    pid = os.fork()
    if pid != 0:
        return pid
    do_sleep(options)
    sys.exit(0)

def run_mplayer(stopper, options):
    moptions = ['--quiet', '--no-consolecontrols']
    mplayer = [options.player] + moptions + [os.path.join(options.config, options.music)]
    mp = subprocess.Popen(print_cmd(options, mplayer))
    pid, status = os.wait()
    if os.wait() == stopper:
        if status == 0:
            os.kill(mp.pid, signal.SIGTERM)
            subprocess.call([options.alsactl, "--file", os.path.join(options.config, options.off), "restore"])
            os.kill(mp.pid, signal.SIGKILL)
            mp.wait()
            return -1
        mp.wait()
        return 0
    return stopper

def check_call(options, cmd, **kw):
    if options.verbosity > 0:
        print_cmd(options, cmd)
    r = subprocess.call(cmd, **kw)
    if r:
        error(options, "failed (%d):" % r, format_cmd(cmd))

def call(options, cmd, **kw):
    print_cmd(options, cmd)
    r = subprocess.call(cmd, **kw)
    if r:
        verbose(options, "failed (%d):" % r, format_cmd(cmd))
    return r

def set_brightness(options, brightness):
    fn = os.path.join(options.led_directory, options.led_control)
    verbose(options, "brightness %s in %s" % (brightness, fn))
    with open(fn, "w") as f:
        f.write(brightness + "\n")

def get_contents(fn, options):
    with open(fn) as f:
        return f.readline().strip()

class ShowLed:
    def __init__(self, options):
        self.options = options
    def __enter__(self):
        options = self.options
        try:
            set_brightness(options, get_contents(os.path.join(options.led_directory, options.led_max), options))
        except OSError:
            self.ok = False
        else:
            self.ok = True
    def __exit__(self, type, value, traceback):
        if self.ok:
            try:
                set_brightness(self.options, "0")
            except OSError:
                pass

def get_trigger(options):
    return os.path.join(options.config, options.trigger)

def mplayer_cmd(options, extra=[]):
    moptions = ['--no-consolecontrols']
    if options.verbosity == 0:
        moptions.append('--really-quiet')
    elif options.verbosity == 1:
        moptions.append('--quiet')
    return [options.player] + moptions + extra + [os.path.join(options.config, options.music)]

def wakeup(options):
    try:
        stat = os.stat(get_trigger(options))
    except FileNotFoundError:
        verbose(options, "no trigger, skipping", get_trigger(options))
        pass
    else:
        if stat.st_mtime < time.time() - options.age * 60 * 60:
            verbose(options, "trigger old, skipping", get_trigger(options))
        else:
            with ShowLed(options) as dummy:
                mplayer = mplayer_cmd(options)
                call(options, [options.alsactl, "--file", os.path.join(options.config, options.on), "restore"])
                if call(options, mplayer) == 0:
                    call(options, ["amixer", "-q", "set", options.volume_control, options.loud])
                    call(options, mplayer)
                call(options, [options.alsactl, "--file", os.path.join(options.config, options.off), "restore"])

def queue(options):
    with ShowLed(options) as dummy:
        with open(get_trigger(options), "w") as trig:
            os.utime(trig.fileno(), None)
        verbose(options, "queue", get_trigger(options))
        check_call(options, [options.alsactl, "--file", os.path.join(options.config, options.on), "restore"])
        mplayer = mplayer_cmd(options, ["--ss=" + options.test_start, "--endpos=" + options.test_play_time])
        check_call(options, mplayer)
        check_call(options, [options.alsactl, "--file", os.path.join(options.config, options.off), "restore"])

def stop(options):
    call(options, ["pkill", "-u", str(os.getuid()), options.player])

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="control alarms")

    parser.add_argument("--bus_name", default="pook.it.test")
    parser.add_argument("--object_path", default = "/org/my/test")
    parser.add_argument("--dbus_interface", default="org.my.test")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--test_start", metavar="TIMESPEC", default='43.8',
            help="start position during test")
    parser.add_argument("--test_play_time", metavar="TIMESPEC", default='3.1',
            help="time to play during test")
    parser.add_argument("--player", metavar="COMMAND", default="mplayer", help="command to play music")
    parser.add_argument("--alsactl", metavar="COMMAND", default="/usr/sbin/alsactl", help="command to load alsa config")
    parser.add_argument("--volume_control", metavar="SCONTROL", default="PCM", help="mixer control")
    parser.add_argument("--music", metavar="FILE", default="alarm", help="music file to play")
    parser.add_argument("--trigger", metavar="FILE", default="trigger", help="file to touch to play")
    parser.add_argument("--loud", metavar="VOLUME", default="255", help="volume for second play")
    parser.add_argument("--age", metavar="HOURS", type=float, default=12, help="maximum age for trigger file")
    parser.add_argument("--datefmt", metavar="STRFTIME", default="%d/%m/%Y", help="strftime format for dates")
    parser.add_argument("--on", metavar="FILE", default="on.state", help="alsa control file to switch sound on")
    parser.add_argument("--off", metavar="FILE", default="off.state", help="alsa control file to switch sound off")
    parser.add_argument("--config", metavar="DIRECTORY", default=os.path.expanduser("~/lib/alarm"),
            help="default directory for configuration files")
    parser.add_argument("--led_directory", metavar="DIRECTORY",
            default="/sys/bus/platform/devices/leds-gpio/leds/gta02:red:aux", help="LED control directory")
    parser.add_argument("--led_control", metavar="FILE", default="brightness", help="file controlling LED brightness")
    parser.add_argument("--led_max", metavar="FILE", default="max_brightness",
            help="file containing maximum LED brightness value")
    parser.add_argument("--activate", '-a', action="store_true", help="program alarm")
    parser.add_argument("--stop", "-s", action="store_true", help="stop alarm")
    parser.add_argument("--syslog", action="store_true", help="syslog messages")

    options = parser.parse_args()
    if options.syslog:
        syslog.openlog(myname())
        verbose(options, "start: " + format_cmd(sys.argv[1:]))
    try:
        if options.activate:
            queue(options)
        elif options.stop:
            stop(options)
        else:
            wakeup(options)
    except Exception as x:
        if options.syslog:
            error(options, "Exception %s" % x)
        else:
            raise
    else:
        if options.syslog:
            verbose(options, "end")

if __name__ == "__main__":
    main()
