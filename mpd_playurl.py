#!/usr/bin/python3 -B
# mpd_playurl Copyright (c) 2017 Stuart Pook (http://www.pook.it/)
# Play URL in mpd using mpc
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
import argparse
import re

def myname():
    return os.path.basename(sys.argv[0])

def verbose(verbosity, level, *message):
    if verbosity >= level:
        print(myname() + ":", *message, file=sys.stderr)

def verbose1(verbosity, *message):
    verbose(verbosity, 1, *message)

def check_call(cmd, env=None, verbosity=0):
    verbose1(verbosity, "run:", " ".join(cmd))
    subprocess.check_call(cmd, env=env)

def get_host(mpd_config, verbosity):
    host = "localhost"
    password = None
    with open(mpd_config) as f:
        password_prog = re.compile('password\s+"([^@"]*)[@"].*')
        host_prog = re.compile('bind_to_address\s+"(/[^"]*)".*')
        for line in f:
            m = re.match(password_prog, line)
            if m:
                password = m.group(1)
            else:
                m = re.match(host_prog, line)
                if m:
                    host = m.group(1)
    r = (password + '@' if password else "") + host
    verbose1(verbosity, "host", host, "password", password, "MPD_HOST", r)
    return r


default_mpc = "mpc"
default_option = "--quiet"
default_mpd_config = "/etc/mpd.conf"

def playurls(urls, mpc=default_mpc, option=default_option, verbosity=0, mpd_config=default_mpd_config):
    mpd_host = get_host(mpd_config, verbosity)
    env = os.environ.copy()
    env['MPD_HOST'] = mpd_host
    check_call([mpc, option, "clear"], env=env, verbosity=verbosity)
    for u in urls:
        check_call([mpc, option, "add", u], env=env, verbosity=verbosity)
    check_call([mpc, option, "play"], env=env, verbosity=verbosity)

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="Play URLs in mpd using mpc")

    parser.add_argument("-v", "--verbosity", "--verbose", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--mpc", metavar="command", default=default_mpc, help="command to run")
    parser.add_argument("--mpd_config", metavar="FILE", default=default_mpd_config, help="file to read password and port")
    parser.add_argument("--option", metavar="option", default=default_option, help="an option for the command to run")

    parser.add_argument('urls', nargs=argparse.REMAINDER, help='urls to queue and play')

    options = parser.parse_args()
    playurls(options.urls, options.mpc, options.option, options.verbosity, options.mpd_config)

if __name__ == "__main__":
    main()
