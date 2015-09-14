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
import collections
import podcastparser
import time
import tempfile
import datetime
import urllib.request

# http://zeromq.org/

def myname():
    return os.path.basename(sys.argv[0])

PlayAble = collections.namedtuple('PlayAble', ['date', 'guid', 'url', 'feed', 'channel', 'title'])

def wakeup(options):
    subprocess.call(["alsactl", "--file", os.path.join(options.config, options.on), "restore"])
    subprocess.call([options.player, os.path.join(options.config, options.music)])
    subprocess.call(["amixer", "set", options.volume_control, options.loud])
    subprocess.call([options.player, os.path.join(options.config, options.music)])
    subprocess.call(["alsactl", "--file", os.path.join(options.config, options.off), "restore"])

def queue(prog, options):
    subprocess.check_call(["alsactl", "--file", os.path.join(options.config, options.on), "restore"])
    subprocess.check_call([options.player, "--ss=60", "--endpos=5", os.path.join(options.config, options.music)])
    subprocess.check_call(["alsactl", "--file", os.path.join(options.config, options.off), "restore"])
    with tempfile.TemporaryFile("w+") as tmp:
        print(prog, "--wakeup", out=tmp)
        tmp.seek(0)
        subprocess.check_call(["at", "-M", options.when], stdin=tmp)

def stop(options):
    pass

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="control alarms")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--min_play_time", metavar="SECONDS", type=int, default=9,
            help="minimum to consider a podcast played")
    parser.add_argument("--player", metavar="COMMAND", default="mplayer", help="command to play music")
    parser.add_argument("--volume_control", metavar="SCONTROL", default="PCM", help="mixer control")
    parser.add_argument("--music", metavar="FILE", default="alarm.wav", help="music to play")
    parser.add_argument("--loud", metavar="VOLUME", default="255", help="volume for second play")
    parser.add_argument("--datefmt", metavar="STRFTIME", default="%d/%m/%Y", help="strftime format for dates")
    parser.add_argument("--on", metavar="FILE", default="on.state", help="alsa control file to switch sound on")
    parser.add_argument("--off", metavar="FILE", default="off.state", help="alsa control file to switch sound off")
    parser.add_argument("--config", metavar="DIRECTORY", default=os.path.expanduser("~/lib/alarm"),
            help="default directory for conf files")
    parser.add_argument('-w', "--when", metavar="TIMESPEC", help="queue wakeup")
    parser.add_argument("--wakeup", action="store_true", help="wakeup now")
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
