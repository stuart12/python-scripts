#!/usr/bin/python3
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


def getid(name, base, verbosity):
    url = base + urllib.parse.quote(name)
    verbose1(verbosity, url)
    with urllib.request.urlopen(url) as f:
        id = int(json.loads(f.read(3000).decode('utf8'))[0]['id'])
        verbose1(verbosity, "id", id)
        return id

default_search = "http://www.radio-browser.info/webservice/json/stations/bynameexact/"
default_lookup = "http://www.radio-browser.info/webservice/v2/json/url/"

def geturl(name, base = default_search, lookup = default_lookup, verbosity = 0):
    url = "%s%d" % (lookup, getid(name, base, verbosity))
    verbose1(verbosity, url)
    with urllib.request.urlopen(url) as f:
        return json.loads(f.read(3000).decode('utf8'))['url']

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="Get URL from station name in www.radio-browser.info")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--search", metavar="URL", default=default_search, help="search URL")
    parser.add_argument("--lookup", metavar="URL", default=default_lookup, help="lookup URL")

    parser.add_argument('names', nargs=argparse.REMAINDER, help='stations to lookup')

    options = parser.parse_args()
    for name in options.names:
        verbose1(options.verbosity, "name:", name)
        print(geturl(name, options.search, options.lookup, options.verbosity))

if __name__ == "__main__":
    main()
