#!/usr/bin/python3
# vim: set shiftwidth=4 tabstop=4
# Delete btrfs snapshots by date until enough free space
# Copyright (C) 2022 Stuart Pook (http://www.pook.it)
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
import fnmatch
import filecmp
import time
import logging
import datetime
import shutil
import pytz
import dateutil
import dateutil.parser
import itertools

def clean_old_transient(directory, options):
	try:
		subdirs = os.listdir(directory)
	except FileNotFoundError:
		if options.skip:
			logging.info("skipping missing %s" % directory)
			return False
		logging.fatal("%s: not found" % directory)
		sys.exit(5)

	now = datetime.datetime.now(pytz.utc)
	deleted = 0
	for subdir in subdirs:
		where = os.path.join(directory, subdir)
		for snapshot in os.listdir(where):
			if not snapshot.endswith(options.good):
				dt = dateutil.parser.parse(snapshot)
				age = (now - dt).days
				if age > options.transient_age:
					logging.info("deleteing %s/%s (%s) as age %d days is greater than limit %d" % (where, snapshot, dt, age, options.transient_age))
					check_call([options.btrfs, "subvolume", "delete", options.commit, snapshot], cwd=where, options=options)
					deleted = deleted + 1
				else:
					logging.debug("keeping %s/%s (%s) as age %d days is not greater than limit %d" % (where, snapshot, dt, age, options.transient_age))
	time.sleep(options.delete_delay * deleted)
	return True

def space_limited(directory, options, check=True):
	stat = shutil.disk_usage(directory)
	if check:
		time.sleep(options.stat_delay)
		stat2 = shutil.disk_usage(directory)
		if stat.free != stat2.free:
			logging.fatal("free space changed from %d to %d on %s" % (stat.free, stat2.free, directory))
			sys.exit(6)
	free = stat.free * 100.0 / stat.total
	result = free < options.free
	logging.debug("%.1f%% free in %s %slimited" % (free, directory, "" if result else "not "))
	return result

def directory_snapshots(directory, options):
	good = sorted(fnmatch.filter(os.listdir(directory), "*%s" % options.good))[:-options.keep]
	def prefix(fn):
		return (fn, directory)
	return map(prefix, good)

def clean_old(directory, options):
	if not clean_old_transient(directory, options):
		return

	if not space_limited(directory, options, check=False):
		return

	def scan(d):
		return directory_snapshots(os.path.join(directory, d), options)
	snapshots = sorted(list(itertools.chain(*map(scan, os.listdir(directory)))))

	for (snapshot, where) in snapshots:
		if not space_limited(directory, options):
			return
		check_call([options.btrfs, "subvolume", "delete", options.commit, snapshot], cwd=where, options=options)
		time.select(options.delete_delay)

def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.set_defaults(loglevel='warn')
	parser.add_argument("-v", "--verbose", dest='loglevel', action='store_const', const='info', help='set log level to info')
	parser.add_argument("--debug", dest='loglevel', action='store_const', const='debug', help='set log level to debug')
	parser.add_argument('--good', default=".good", help='suffix for correctly transfered snapshots')
	parser.add_argument('--commit', default="--commit-each", help='option for btrfs-subvolume delete to wait for stable space')
	parser.add_argument('--btrfs', default="btrfs", help='btrfs command')
	parser.add_argument('-n', '--dryrun', action='store_true', help='dryrun')
	parser.add_argument('--stdout', action='store_true', help='dump command output')
	parser.add_argument('--skip', action='store_true', help='silently skip missing directories')
	parser.add_argument('--transient_age', type=int, default=1, metavar="days", help='age of oldest transient to keep')
	parser.add_argument('--keep', type=int, default=1, metavar="COUNT", help='minimum number of snapshots per directory to keep')
	parser.add_argument('--free', type=float, default=10.0, metavar="PERCENT", help='minumum percent disk free')
	parser.add_argument('--delete_delay', type=float, default=60.0, metavar="SECONDS", help='delay after each delete')
	parser.add_argument('--stat_delay', type=float, default=2.0, metavar="SECONDS", help='delay to check no change in free space')

	parser.add_argument('args', nargs=argparse.REMAINDER, help='command to run')

	options = parser.parse_args()

	loglevel = options.loglevel
	numeric_level = getattr(logging, loglevel.upper(), None)
	if not isinstance(numeric_level, int):
		raise ValueError('Invalid log level: %s' % loglevel)
	logging.basicConfig(level=numeric_level)

	if len(options.good) < 2 or options.good[0] != '.':
		sys.exit("bad good suffix")

	for dest in options.args:
		clean_old(dest, options)

	sys.exit(0)
if __name__ == "__main__":
	main()
