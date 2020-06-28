#!/usr/bin/python3 -B
# radioinfo Copyright (c) 2017,2019 Stuart Pook (http://www.pook.it/)
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
import logging
import os
import sys
import re
import radioinfo
import argparse
try:
    import mpd
except ImportError:
    print("sudo apt install python3-mpd", file=sys.stderr)
    raise

def myname():
    return os.path.basename(sys.argv[0])

def lookup(url):
    logging.info("lookup: %s", url)
    return radioinfo.geturl(url)

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="Play RadioInfo station in MPD")

    parser.set_defaults(loglevel='warn')
    parser.add_argument("-v", "--verbose", dest='loglevel', action="store_const", const='debug', help="debug loglevel")

    parser.add_argument("--mpd", metavar="hostname", default="localhost", help="MPD host to contact")
    parser.add_argument("--port", metavar="TCP PORT", type=int, default=6600, help="port number of mpd host")

    parser.add_argument('station', nargs=argparse.REMAINDER, help='stations to lookup')

    options = parser.parse_args()

    numeric_level = getattr(logging, options.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        sys.exit('Invalid log level: %s' % options.loglevel)
    logging.basicConfig(level=numeric_level)

    player = mpd.MPDClient()
    player.connect(options.mpd, options.port)
    urls = [lookup(name) for name in options.station]
    logging.debug("have %d url", len(urls))
    urls = [re.sub(r'^[-A-Za-z0-9+.]*:', lambda pat: pat.group(0).lower(), url) for url in urls]

    player.clear()
    for url in urls:
        logging.debug("add %s", url)
        player.add(url)
    logging.debug("play")
    player.play()
    player.close()

if __name__ == "__main__":
    main()
