#!/usr/bin/python3
# vim: set shiftwidth=4 tabstop=4 noexpandtab copyindent preserveindent softtabstop=0 
# Use btrfs send and receive to backup a subvolume to a local disk.
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
import argparse
import re

def verbose(options, *args):
	if options.verbosity:
		print(os.path.basename(sys.argv[0]) + ":", *args, file=sys.stderr)

def warn(*opts):
	print(os.path.basename(sys.argv[0]) + ":", *opts, file=sys.stderr)

def fix(directory, options):
	mapping = {}
	slaves = []
	for fn in os.listdir(directory):
		if fn.endswith(options.master):
			match = re.fullmatch("(\d\d\d_\d\d\d\d)( .+)" + options.master, fn)
			if match:
				mapping[match.group(1)] = match.group(2)
		elif fn.endswith(options.slave):
			slave = re.fullmatch("(\d\d\d_\d\d\d\d).*" + options.slave, fn)
			if slave:
				slaves.append([slave.group(1), fn])
		elif options.recursive and os.path.isdir(fn):
			fix(os.path.join(directory, fn), options)
	for (key, fn) in slaves:
		text = mapping.get(key)
		if text:
			new_fn = key + text + options.slave
			if fn != new_fn:
				verbose(options, "mv %s %s" % (fn, new_fn))
				if not options.dryrun:
					os.rename(fn, new_fn)

def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
	parser.add_argument("-n", '--dryrun', default=False, action='store_true', help='dryrun')
	parser.add_argument("-r", '--recursive', default=False, action='store_true', help='recursive')
	parser.add_argument('--slave', default=".cr2.pp3", help='suffix to fix')
	parser.add_argument('--master', default=".cr2", help='master suffix')

	parser.add_argument('directories', default=["."], nargs=argparse.REMAINDER, help='directories to fix')

	options = parser.parse_args()

	if len(options.directories) == 0:
		parser.print_help()
		sys.exit("bad arguments")

	for d in options.directories:
		fix(d, options)

if __name__ == "__main__":
	main()
