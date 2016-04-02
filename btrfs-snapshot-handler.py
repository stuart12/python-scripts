#!/usr/bin/python3
# btrfs-snapshot a set of btrfs filesystems.
# Copyright (C) 2015 Stuart Pook (http://www.pook.it)
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.  This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.  You should have received a copy of the GNU General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import tempfile
import subprocess
import shlex
import argparse
import configparser
try:
    import pytz
except ImportError:
    print(": on Debian do; sudo apt-get install python3-tz", file=sys.stderr)
    raise
import pytz.reference
import datetime
try:
    import dateutil.parser
except ImportError:
    print(": on Debian do; sudo apt-get install python3-dateutil", file=sys.stderr)
    raise

def timestamp():
    local_system_utc = pytz.utc.localize(datetime.datetime.utcnow())
    rounded = local_system_utc.astimezone(pytz.reference.LocalTimezone()).replace(microsecond=0)
    r = rounded.isoformat()
# parse using
    assert dateutil.parser.parse(r) == rounded
    return r

def verbose(args, *opts):
    if args.verbosity:
        print(os.path.basename(sys.argv[0]) + ":", *opts, file=sys.stderr)

def warn(*opts):
    print(os.path.basename(sys.argv[0]) + ":", *opts, file=sys.stderr)

def error(*opts):
    warn(*opts)
    sys.exit(3)

def quote_command(command):
    return " ".join(shlex.quote(x) for x in command)

def check_pipe(command, p, stdout, options):
    if p.wait() != 0:
        if stdout is None:
            r = ""
        else:
            stdout.seek(0)
            r = ": " + stdout.read().rstrip()
        warn(quote_command(command), "failed (%d)%s" % (p.returncode, r))
        return 1
    return 0

def get_stdout(options):
    if options.verbosity > 0:
        return None
    return tempfile.TemporaryFile(mode='w+')

def check_call(command, options):
    verbose(options, quote_command(command))
    if options.dryrun:
        return True
    stdout = get_stdout(options)
    p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout)
    return check_pipe(command, p, stdout, options) == 0

def clean_snapshots(directory, keep, options):
    if keep <= 0:
        return True
    snapshots = [fn for fn in os.listdir(directory) if all(c not in options.snapshot_saver for c in fn)]
    verbose(options, "have %d snapshots in %s" % (len(snapshots), directory))
    if len(snapshots) <= keep:
        return True
    to_delete = [os.path.join(directory, sn) for sn in sorted(snapshots)[:-keep]]
    verbose(options, "delete %d snapshots in %s" % (len(to_delete), directory))
    return check_call([options.btrfs, "subvolume", "delete", *to_delete], options)

def snapshot(src, dst_dir, keep, options):
    dst = os.path.join(dst_dir, options.timestamp)
    if not check_call([options.btrfs, "subvolume", "snapshot", "-r", src, dst], options):
        return False
    return clean_snapshots(dst_dir, keep, options)

def snapshot_with_config(keep, options):
    config = configparser.ConfigParser()
    with open(options.config) as f:
        config.read_file(f)
    ok = True
    for section_name in config.sections():
        section = config[section_name]
        src = section.get("source", None)
        if src == None:
            src = os.path.join(section.get("sourcedirectory", None), section_name)
        dst = section.get("destination", None)
        if dst == None:
            dst = os.path.join(section.get("destinationdirectory", None), section_name)
#        verbose(options, "Section: %s %s -> %s" % (section_name, src, dst))
        ok = snapshot(src, dst, section.getint("keep", options.keep), options) and ok
    return ok

def snapshot_directories(src_dir, dst_dir, options):
    ok = True
    for subdir in os.listdir(src_dir):
        ok = snapshot(os.path.join(src_dir, subdir), os.path.join(dst_dir, subdir), options) and ok
    return ok

def run(options, parser):
    keep = options.keep
    if options.config:
        if len(options.args) != 0:
            parser.print_help()
            sys.exit("no arguments when config file used")
        ok = snapshot_with_config(keep, options)
    elif options.directories and len(options.args) >= 2:
        ok = True
        for src in options.args[0:-1]:
            ok = snapshot_directories(src, options.args[-1], keep, options) and ok
    elif len(options.args) == 2:
        ok = snapshot(options.args[0], options.args[-1], keep, options)
    else:
        parser.print_help()
        sys.exit("bad arguments")
    return 0 if ok else 8

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument('--config', default="/etc/local/btrfs-snapshots", help='config file')
    parser.add_argument('--btrfs', default="btrfs", help='btrfs command')
    parser.add_argument('--timestamp', default=timestamp(), help='timestamp for new snapshots')
    parser.add_argument('-D', '--directories', action='store_true', help='do subdirectories of arguments')
    parser.add_argument('--snapshot_saver', default="~#@.", help='characters in snapshots not to be deleted')
    parser.add_argument('--keep', type=int, default=-1, help='number of snapshots to keep')
    parser.add_argument('-n', '--dryrun', action='store_true', help='do not execute')

    parser.add_argument('args', nargs=argparse.REMAINDER, help='directories')

    options = parser.parse_args()
    sys.exit(run(options, parser))

if __name__ == "__main__":
    main()
