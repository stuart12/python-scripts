#!/usr/bin/python3
# vim: set shiftwidth=4,tabstop=4
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
import tempfile
import subprocess
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

def check_pipe(command, p):
	if p.wait() != 0:
		tmp = p.stderr
		if tmp:
			tmp.seek(0)
			r = tmp.read()
		else:
			r = ""
		warn(quote_command(command), "failed (%d): %s" % (p.returncode, r))
		return 1
	return 0

def get_stdout(options):
	if options.verbosity > 0:
		return None
	return tempfile.TemporaryFile(mode='w+')

def check_call(command, options):
	verbose(options, quote_command(command))
	p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=get_stdout(options))
	if check_pipe(command, p) > 0:
		sys.exit(10)

def get_snapshots(dirname, options):
	return os.listdir(dirname)

def get_backups(dirname, options):
	try:
		fns = os.listdir(dirname)
	except FileNotFoundError:
		check_call([options.btrfs, "subvolume", "create", dirname], options)
		fns = []

	r = []
	for fn in fns:
		if fn.endswith(options.good):
			r.append(fn[:-len(options.good)])
		elif options.clean:
			check_call([options.btrfs, "subvolume", "delete", os.path.join(dirname, fn)], options)
	return r

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

	p1 = subprocess.Popen(first, stdout=subprocess.PIPE, stderr=get_stdout(options))
	p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=get_stdout(options), stderr=subprocess.STDOUT)
	p1.stdout.close()
	r = 0
	r += check_pipe(first, p1)
	r += check_pipe(second, p2)
	if r:
		sys.exit(r)

def copy(src, dst, options):
		src_snapshots = sorted(get_snapshots(src, options))
		if len(src_snapshots) == 0:
			if options.skip:
				return
			error("source directory %s is empty" % src)
		dst_snapshots = frozenset(get_backups(dst, options))

		target = src_snapshots[-1]
		old_snapshot = os.path.join(src, target)
		if target in dst_snapshots:
			if options.skip:
				return
			error("most recent snapshot %s is already in %s" % (old_snapshot, dst))
		sender = [options.btrfs, "send"]
		for common in dst_snapshots & frozenset(src_snapshots):
			sender.extend(["-c", os.path.join(src, common)])
		sender.append(old_snapshot)

		pipe(sender, [options.btrfs, "receive", dst], options)

		new_snapshot = os.path.join(dst, target)
		if options.compare:
			verbose(options, "compare", old_snapshot, new_snapshot)
			print_diff_files(filecmp.dircmp(old_snapshot, new_snapshot))

		os.rename(new_snapshot, new_snapshot + options.good)

def copy_with_config(options):
	config = configparser.ConfigParser()
	with open(options.config) as f:
		config.read_file(f)
	for section_name in config.sections():
		section = config[section_name]
		src = section.get("source")
		dst = section.get("destination")
		verbose(options, "Section: %s %s -> %s" % (section_name, src, dst))
		copy(src, dst, options)

def copy_directories(src_dir, dst_dir, options):
	for subdir in os.listdir(src_dir):
		copy(os.path.join(src_dir, subdir), os.path.join(dst_dir, subdir), options)

def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
	parser.add_argument('--config', default=None, help='config file')
	parser.add_argument('--good', default=".good", help='suffix for correctly transfered snapshots')
	parser.add_argument('--btrfs', default="btrfs", help='btrfs command')
	parser.add_argument('-c', '--compare', action='store_true', help='check that directories are the same')
	parser.add_argument('-s', '--skip', action='store_true', help='skip directories that have already been copied')
	parser.add_argument('--no_create_dest', default=True, dest="create_dest", action='store_false', help='do not create destination')
	parser.add_argument('--no_clean', default=True, dest="clean", action='store_false', help='do not clean destination volumes')
	parser.add_argument('-D', '--directories', action='store_true', help='do subdirectories of arguments')

	parser.add_argument('args', nargs=argparse.REMAINDER, help='command to run')

	options = parser.parse_args()

	if not options.good:
		sys.exit("good suffix cannot be empty")

	if options.config:
		copy_with_config(options.config)
	elif options.directories and len(options.args) >= 2:
		for src in options.args[0:-1]:
			copy_directories(src, options.args[-1], options)
	elif len(options.args) == 2:
		copy(options.args[0], options.args[-1], options)
	else:
		parser.print_help()
		sys.exit("bad arguments")

if __name__ == "__main__":
	main()
