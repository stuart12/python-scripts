#!/usr/bin/python3
# playnewestpod Copyright (c) 2015 Stuart Pook (http://www.pook.it/)
# program and ring an alarm on a remote machine
# set noexpandtab copyindent preserveindent softtabstop=0 shiftwidth=4 tabstop=4
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

# http://zeromq.org/
# https://stackoverflow.com/questions/22390064/use-dbus-to-just-send-a-message-in-python
from gi.repository import Gtk
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

def myname():
    return os.path.basename(sys.argv[0])

def do_sleep(options):
    dbus_interface= options.dbus_interface

    class MyDBUSService(dbus.service.Object):
        def __init__(self, options):
            bus_name = dbus.service.BusName(options.bus_name, bus=dbus.SessionBus())
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
            Gtk.main_quit()
            return
    DBusGMainLoop(set_as_default=True)
    myservice = MyDBUSService(options)
    Gtk.main()

def sleeper(options):
    pid = os.fork()
    if pid != 0:
        return pid
    do_sleep(options)
    sys.exit(0)

def run_mplayer(stopper, options):
    moptions = ['--quiet', '--no-consolecontrols']
    mplayer = [options.player] + moptions + [os.path.join(options.config, options.music)]
    mp = subprocess.Popen(mplayer)
    pid, status = os.wait()
    if os.wait() == stopper:
        if status == 0:
            os.kill(mp.pid, signal.SIGTERM)
            subprocess.call(["alsactl", "--file", os.path.join(options.config, options.off), "restore"])
            os.kill(mp.pid, signal.SIGKILL)
            mp.wait()
            return -1
        mp.wait()
        return 0
    return stopper

def wakeup(options):
    stopper = do_sleep(options)
    subprocess.call(["alsactl", "--file", os.path.join(options.config, options.on), "restore"])
    stopper = run_mplayer(stopper, options)
    if stopper >= 0:
        subprocess.call(["amixer", "set", options.volume_control, options.loud])
        stopper = run_mplayer(stopper, options)
        if stopper >= 0:
            subprocess.call(["alsactl", "--file", os.path.join(options.config, options.off), "restore"])
        if stopper > 0:
            os.kill(stopper, signal.SIGKILL)
            os.waitpid(stopper, 0)

def queue(prog, options):
    subprocess.check_call(["alsactl", "--file", os.path.join(options.config, options.on), "restore"])
    subprocess.check_call([options.player, "--ss=60", "--endpos=%d" % options.test_play_time] + moptions + [os.path.join(options.config, options.music)])
    subprocess.check_call(["alsactl", "--file", os.path.join(options.config, options.off), "restore"])
    with tempfile.TemporaryFile("w+") as tmp:
        print(prog, "--wakeup", file=tmp)
        tmp.seek(0)
        subprocess.check_call(["at", "-M", options.when], stdin=tmp)

def stop(options):
    #get the session bus
    bus = dbus.SessionBus()
    #get the object
    bus_name = "org.my.test"
    object_path = "/org/my/test"
    # http://dbus.freedesktop.org/doc/dbus-python/api/dbus.bus.BusConnection-class.html
    the_object = bus.get_object(options.bus_name, options.object_path)
    #get the interface
    dbus_interface= "org.my.test" 
    the_interface = dbus.Interface(the_object, options.dbus_interface)

    #call the methods and print the results
    reply = the_interface.hello()
    print(reply)

    reply = the_interface.string_echo("test 123")
    print(reply)

    the_interface.Quit()

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="control alarms")

    parser.add_argument("--bus_name", default="pook.it.test")
    parser.add_argument("--object_path", default = "/org/my/test")
    parser.add_argument("--dbus_interface", default="org.my.test")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--test_play_time", metavar="SECONDS", type=int, default=4,
            help="time to play during test")
    parser.add_argument("--player", metavar="COMMAND", default="mplayer", help="command to play music")
    parser.add_argument("--volume_control", metavar="SCONTROL", default="PCM", help="mixer control")
    parser.add_argument("--music", metavar="FILE", default="alarm.mp3", help="music to play")
    parser.add_argument("--loud", metavar="VOLUME", default="255", help="volume for second play")
    parser.add_argument("--datefmt", metavar="STRFTIME", default="%d/%m/%Y", help="strftime format for dates")
    parser.add_argument("--on", metavar="FILE", default="on.state", help="alsa control file to switch sound on")
    parser.add_argument("--off", metavar="FILE", default="off.state", help="alsa control file to switch sound off")
    parser.add_argument("--config", metavar="DIRECTORY", default=os.path.expanduser("~/lib/alarm"),
            help="default directory for conf files")
    parser.add_argument('-w', "--when", metavar="TIMESPEC", help="queue wakeup")
    parser.add_argument('-W', "--wakeup", action="store_true", help="wakeup now")
    parser.add_argument("--stop", action="store_true", help="stop alarm")

    parser.add_argument('urls', nargs=argparse.REMAINDER, help='file to convert')

    options = parser.parse_args()
    if options.when:
        queue(sys.argv[0], options)
    elif options.stop:
        stop(options)
    else:
        wakeup(options)

if __name__ == "__main__":
    main()
