#!/usr/bin/python3
# vim: set shiftwidth=4,tabstop=4
# Use btrfs send and receive to backup a subvolume to a local disk.
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
import shutil
import shlex
import argparse
import configparser
import filecmp

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

def get_snapshots(dirname, suffix, options):
	fns = os.listdir(dirname)
	if len(suffix) == 0:
		return fns
	r = []
	for fn in fns:
		if fn.endswith(suffix):
			r.append(fn[:-len(suffix)])
	return r

def check_pipe(command, p, tmp):
	if p.wait() != 0:
		if tmp:
			tmp.seek(0)
			r = tmp.read()
		else:
			r = ""
		warn(quote_command(command), "failed (%d): %s" % (p.returncode, r))
		return 1
	return 0

def print_diff_files(dcmp):
	for name in dcmp.diff_files:
		error("diff_file %s found in %s and %s" % (name, dcmp.left, dcmp.right))
	for name in dcmp.left_only:
		error("left_only %s only found in %s" % (name, dcmp.left))
	for name in dcmp.right_only:
		error("right_only %s only found in %s" % (name, dcmp.right))
	#for name in dcmp.common_funny: # problem with symlinks
		#error("common_funny %s found in %s & %s" % (name, dcmp.left, dcmp.right))
	for name in dcmp.funny_files:
		error("funny_files %s found in %s & %s" % (name, dcmp.left, dcmp.right))

	for sub_dcmp in dcmp.subdirs.values():
		print_diff_files(sub_dcmp)

def pipe(first, second, options):
	verbose(options, "%s | %s" % (quote_command(first), quote_command(second)))

	if options.verbose:
		t1 = t2 = None
	else:
		t1 = tempfile.TemporaryFile(mode='w+')
		t2 = tempfile.TemporaryFile(mode='w+')
	p1 = subprocess.Popen(first, stdout=subprocess.PIPE, stderr=t1)
	p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=t2, stderr=t2)
	p1.stdout.close()
	r = 0
	r += check_pipe(first, p1, t1)
	r += check_pipe(second, p2, t2)
	if r:
		sys.exit(r)

def run(options):
	config = configparser.ConfigParser()
	with open(options.config) as f:
		config.read_file(f)
	for section_name in config.sections():
		section = config[section_name]
		src = section.get("source")
		dst = section.get("destination")
		print("Section: %s %s -> %s" % (section_name, src, dst))
		src_snapshots = sorted(get_snapshots(src, "", options))
		dst_snapshots = frozenset(get_snapshots(dst, options.good, options))
		if len(src_snapshots ) == 0:
			error("source directory %s in empty", src)

		target = src_snapshots[-1]
		old_snapshot = os.path.join(src, target)
		if target in dst_snapshots:
			error("most recent snapshot %s is already backuped in %s" % (old_snapshot, dst))
		cmd = [options.btrfs, "send" ]
		for common in dst_snapshots & frozenset(src_snapshots):
			cmd.extend(["-c", os.path.join(src, common)])
		cmd.append(old_snapshot)

		receive = [options.btrfs, "receive", dst]
		pipe(cmd, receive, options)

		new_snapshot = os.path.join(dst, target)
		if options.compare:
			verbose(options, "compare", old_snapshot, new_snapshot)
			print_diff_files(filecmp.dircmp(old_snapshot, new_snapshot))
		if options.good:
			os.rename(new_snapshot, new_snapshot + options.good)

def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
	parser.add_argument('-c', '--config', default="/etc/local/btrfs-snapshoter.ini", help='config file')
	parser.add_argument('--good', default=".good", help='suffix for correctly transfered snapshots')
	parser.add_argument('--btrfs', default="btrfs", help='btrfs command')
	parser.add_argument('--compare', action='store_true', help='check that directories are the same')
	parser.add_argument('command', nargs=argparse.REMAINDER, help='command to run')

	args = parser.parse_args()

	run(args)

if __name__ == "__main__":
	main()
