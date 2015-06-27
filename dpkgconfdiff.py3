#!/usr/bin/python3
# vim: set shiftwidth=4 tabstop=4 noexpandtab copyindent preserveindent softtabstop=0 
# Compare dpkg (Debian apt) configuration files with the original version
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

# inspired by
# https://gitorious.org/mybin/mybin/source/d0602b99dd4ff840a6d3ffdfb017c6ca8b574fe4:debdiffconf

import os
import sys
import argparse
import time
import difflib
import subprocess
import tempfile

def myname():
	return os.path.basename(sys.argv[0])

def verbose(options, *args):
	if options.verbosity:
		print(os.path.basename(sys.argv[0]) + ":", *args, file=sys.stderr)

def warn(*opts):
	print(os.path.basename(sys.argv[0]) + ":", *opts, file=sys.stderr)

def error(*opts):
	warn(*opts)
	sys.exit(67)

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

def pkgs_for_files(files, options):
	command = [ "dpkg", "-S", ]
	for f in files:
		command.append(os.path.abspath(f))
	pipe = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)
	pkg2files = {}
	for line in pipe.stdout:
		fields = line.rstrip().split(": ")
		pkg2files.setdefault(fields[0], []).append(fields[1])
	if pipe.wait() != 0:
		error("command failed:", " ".join(command[0:2]))

	return pkg2files

def diff_files_in_package(pkg, files, options):
	n = options.lines
	with tempfile.TemporaryDirectory(prefix=myname()) as tdir:
		subprocess.check_call(["apt-get", "--quiet=3", "download", pkg], cwd=tdir)
		pkg_file = os.listdir(tdir)[0]
		contents = "contents"
		os.mkdir(os.path.join(tdir, contents))
		subprocess.check_call(["dpkg-deb", "--extract", pkg_file, contents], cwd=tdir)
		for tofile in files:
			tobase = tofile[1:]
			fromfile = os.path.join(tdir, contents, tobase)
			fromheader = tobase
			fromdate = time.ctime(os.stat(fromfile).st_mtime)
			todate = time.ctime(os.stat(tofile).st_mtime)

			# we're passing these as arguments to the diff function
			with open(fromfile) as fromf, open(tofile) as tof:
				fromlines, tolines = list(fromf), list(tof)

			if options.context:
				diff = difflib.context_diff(fromlines, tolines, fromheader, tofile, fromdate, todate, n=n)
			elif options.ndiff:
				diff = difflib.ndiff(fromlines, tolines)
			elif options.html:
				diff = difflib.HtmlDiff().make_file(fromlines, tolines, fromheader, tofile, context=options.c, numlines=n)
			else:
				diff = difflib.unified_diff(fromlines, tolines, fromheader, tofile, fromdate, todate, n=n)

			# we're using writelines because diff is a generator
			sys.stdout.writelines(diff)


def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, description="compare configuration files")

	#parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
	parser.add_argument('--slave', default=".cr2.pp3", help='suffix to fix')
	parser.add_argument('--master', default=".cr2", help='master suffix')
	parser.add_argument("--context", "-c", action="store_true", default=False, help='Produce a context format diff')
	parser.add_argument("--unified", "-u", action="store_true", default=False, help='Produce a unified format diff (default)')
	hlp = 'Produce HTML side by side diff (can use -c and -l in conjunction)'
	parser.add_argument("--html", "-m", action="store_true", default=False, help=hlp)
	parser.add_argument("--ndiff", "-n", action="store_true", default=False, help='Produce a ndiff format diff')
	parser.add_argument("-l", "--lines", type=int, default=3, help='Set number of context lines (default 3)')

	parser.add_argument('files', nargs=argparse.REMAINDER, help='files to compare')

	options = parser.parse_args()

	if len(options.files) == 0:
		parser.print_help()
		sys.exit("bad arguments")

	for f in options.files:
		with open(f) as dummy:
			pass
	pkg2files = pkgs_for_files(options.files, options)
	for pkg, files in pkg2files.items():
		diff_files_in_package(pkg, files, options)

if __name__ == "__main__":
	main()
