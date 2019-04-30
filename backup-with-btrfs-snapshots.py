#!/usr/bin/python3
# vim: set shiftwidth=4 tabstop=4
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

def verbose(options, *args):
	if options.verbosity:
		print(os.path.basename(sys.argv[0]) + ":", *args, file=sys.stderr)

def warn(*opts):
	print(os.path.basename(sys.argv[0]) + ": warn:", *opts, file=sys.stderr)

def error(*opts):
	print(os.path.basename(sys.argv[0]) + ": error:", *opts, file=sys.stderr)
	sys.exit(3)

def quote_command(command):
	return " ".join(shlex.quote(x) for x in command)

def check_pipe(command, p, errors):
	if p.wait() != 0:
		if errors is None:
			r = ""
		else:
			errors.seek(0)
			r = ": " + errors.read().strip()
		warn(quote_command(command), "failed (%d)%s" % (p.returncode, r))
		return 1
	return 0

def get_stdout(options):
	if options.verbosity > 0:
		return None
	return tempfile.TemporaryFile(mode='w+')

def check_call(command, options):
	verbose(options, quote_command(command))
	stdout = get_stdout(options)
	p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout)
	if check_pipe(command, p, stdout) > 0:
		sys.exit(10)

def get_snapshots(dirname, options):
	return os.listdir(dirname)

def get_backups(dirname, options):
	try:
		fns = os.listdir(dirname)
	except FileNotFoundError:
		if options.create_dest:
		    check_call([options.btrfs, "subvolume", "create", dirname], options)
		    fns = []
		else:
		    return None

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

	p1_stderr = get_stdout(options)
	p1 = subprocess.Popen(first, stdout=subprocess.PIPE, stderr=p1_stderr)
	p2_stdout = get_stdout(options)
	p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=p2_stdout, stderr=subprocess.STDOUT)
	p1.stdout.close()
	r = 0
	r += check_pipe(first, p1, p1_stderr)
	r += check_pipe(second, p2, p2_stdout)
	if r:
		sys.exit(r)

def copy(src, dst, options):
		src_snapshots = sorted(get_snapshots(src, options))
		if len(src_snapshots) == 0:
			warn("source directory %s is empty" % src)
			return options.missing
		dst_snapshots_list = get_backups(dst, options)
		if dst_snapshots_list is None:
			verbose(options, "destination directory %s is missing" % dst)
			return options.partial
		dst_snapshots = frozenset(dst_snapshots_list)

		target = src_snapshots[-1]
		old_snapshot = os.path.join(src, target)
		if target in dst_snapshots:
			warn("most recent snapshot %s is already in %s" % (old_snapshot, dst))
			return options.skip
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
		return True

def copy_with_config(options):
	config = configparser.ConfigParser()
	with open(options.config) as f:
		config.read_file(f)
	ok = True
	for section_name in config.sections():
		section = config[section_name]
		src = section.get("source")
		dst = section.get("destination")
		verbose(options, "Section: %s %s -> %s" % (section_name, src, dst))
		ok = copy(src, dst, options) and ok
	return ok

def copy_directories(src_dir, dst_dir, options):
	ok = True
	for subdir in os.listdir(src_dir):
		ok = copy(os.path.join(src_dir, subdir), os.path.join(dst_dir, subdir), options) and ok
	return ok

def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.add_argument("-v", "--verbosity", '--verbose', action="count", default=0, help="increase output verbosity")
	parser.add_argument('--config', default=None, help='config file')
	parser.add_argument('--good', default=".good", help='suffix for correctly transfered snapshots')
	parser.add_argument('--btrfs', default="btrfs", help='btrfs command')
	parser.add_argument('-c', '--compare', action='store_true', help='check that directories are the same')
	parser.add_argument('-s', '--skip', action='store_true', help='status ok if directories have already been copied')
	parser.add_argument('-p', '--partial', action='store_true', help='status ok if missing destination directory')
	parser.add_argument('--missing', action='store_true', help='status ok if missing directories')
	parser.add_argument('--no_create_dest', '--no-create-dest', default=True, dest="create_dest", action='store_false', help='do not create destination')
	parser.add_argument('--no_clean', '--no-clean', default=True, dest="clean", action='store_false', help='do not clean destination volumes')
	parser.add_argument('-D', '--directories', action='store_true', help='do subdirectories of arguments')

	parser.add_argument('args', nargs=argparse.REMAINDER, help='command to run')

	options = parser.parse_args()

	if not options.good:
		sys.exit("good suffix cannot be empty")

	if options.config:
		ok = copy_with_config(options)
	elif options.directories and len(options.args) >= 2:
		ok = True
		for src in options.args[0:-1]:
			ok = copy_directories(src, options.args[-1], options) and ok
	elif len(options.args) == 2:
		ok = copy(options.args[0], options.args[-1], options)
	else:
		parser.print_help()
		sys.exit("bad arguments")

	sys.exit(0 if ok else 8)
if __name__ == "__main__":
	main()
