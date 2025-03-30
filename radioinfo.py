#!/usr/bin/python3
# radioinfo Copyright (c) 2017,2021 Stuart Pook (http://www.pook.it/)
# Get the URL from the name of a station in http://www.radio-browser.info
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
import random
import dns.resolver

def verbose(verbosity, level, *message):
    if verbosity >= level:
        print(myname() + ":", *message, file=sys.stderr)

def verbose1(verbosity, *message):
    verbose(verbosity, 1, *message)

default_search = "json/stations/bynameexact"
default_srv_record = "_api._tcp.radio-browser.info"
default_key = "url_resolved"
default_bytes = 32000


def get_servers(srv_record, verbosity):
    srv_records = list(dns.resolver.resolve(srv_record, 'SRV'))
    verbose1(verbosity, "srv_records count", len(srv_records))
    random.shuffle(srv_records)
    return [f"{str(record.target).rstrip('.')}:{record.port}" for record in srv_records]


def geturl(name, srv_record = default_srv_record, search = default_search, read_bytes=default_bytes, verbosity=0, key=default_key):
    servers = get_servers(srv_record, verbosity)
    error = f"no servers from {srv_record}"
    for server in servers:
        url = f"https://{server}/{search}/{urllib.parse.quote(name)}"
        verbose1(verbosity, url)
        try:
            response = urllib.request.urlopen(url)
        except urllib.error.HTTPError as ex:
            error = f"HTTPError {url}: {ex}"
        except urllib.error.URLError as ex:
            error = f"URLError {url}: {ex}"
        with response as f:
            answer = json.loads(f.read(read_bytes).decode('utf8'))
            verbose1(verbosity, answer)
            try:
                return answer[0][key]
            except KeyError as ex:
                error = f"for \"{name}\" no {key} in {answer}"
    verbosity1(verbosity, "for", server, "failed", error)
    sys.exit(f"{myname()}: {error}")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="Get URL from station name in www.radio-browser.info")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--search", metavar="REQUEST", default=default_search, help="search request")
    parser.add_argument("--srv", metavar="SRV_RECORD", default=default_srv_record, help="SRV for api hosts")
    parser.add_argument("--key", default=default_key, help="key in Struct Station")
    parser.add_argument("--read", metavar="BYTES", default=default_bytes, type=int, help="size of read for result")

    parser.add_argument('names', nargs=argparse.REMAINDER, help='stations to lookup')

    options = parser.parse_args()
    for name in options.names:
        verbose1(options.verbosity, "name:", name)
        print(geturl(name, options.srv, options.search, options.read, options.verbosity, key=options.key))

if __name__ == "__main__":
    main()
