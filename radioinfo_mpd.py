#!/usr/bin/python3 -B
# radioinfo Copyright (c) 2017 Stuart Pook (http://www.pook.it/)
# Get the URL from the name of a station in http://www.radio-browser.info/webservice
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
import sys
import subprocess
import radioinfo
import mpd_playurl

def myname():
    return os.path.basename(sys.argv[0])

import argparse
import urllib.request
import json

def verbose(verbosity, level, *message):
    if verbosity >= level:
        print(myname() + ":", *message, file=sys.stderr)

def verbose1(verbosity, *message):
    verbose(verbosity, 1, *message)

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="Play RadioInfo station in MPD")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--mpc", metavar="command", default="mpc", help="command to run")
    parser.add_argument("--option", metavar="option", default="--quiet", help="an option for the command to run")

    parser.add_argument('station', nargs=argparse.REMAINDER, help='stations to lookup')

    options = parser.parse_args()
    urls = [radioinfo.geturl(name) for name in options.station]
    mpd_playurl.playurls(urls, verbosity=options.verbosity)

if __name__ == "__main__":
    main()
