#!/usr/bin/python3
# vim: sw=4:ts=4
# disk-keeper: run a command and then syslog its disk status.
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
import subprocess
import shlex
import argparse
import re
import time
import syslog

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

def start_pipe(command, options):
	verbose(options, quote_command(command))
	return subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)

def get_filesystem_partition(fs, options):
	# https://stackoverflow.com/questions/7718411/determine-device-of-filesystem-in-python
	res = None
	dev = os.lstat(fs).st_dev
	with open('/proc/mounts', "rb") as mounts:
		for line in mounts:
			# lines are device, mountpoint, filesystem, <rest>
			# later entries override earlier ones
			line = [s.decode('unicode_escape') for s in line.split()[:2]]
			try:
				if dev == os.lstat(line[1]).st_dev:
					res = line[0]
			except PermissionError:
				pass
	verbose(options, "filesystem %s is on disk %s" % (fs, res))
	return res

def get_state(disk, options):
	cmd = [options.hdparm, "-C", disk]
	p = start_pipe(cmd, options)
	result = None
	for line in p.stdout:
		match = re.match("\s*drive state is:\s*(\S+)", line)
		if match:
			result = match.group(1)
	p.stdout.close()
	if p.wait() != 0:
		error("%s failed (%d)" % (cmd[0], p.returncode))
	if result is None:
		error("no device status for %s" % (disk))
	return result

def get_temperature2(disk, options):
	cmd = [options.smartctl, "--attributes"]
	if options.device_type:
		cmd.extend(["-d", options.device_type])
	cmd.append(disk)
	p = start_pipe(cmd, options)
	temperature = None
	for line in p.stdout:
		fields = line.split()
		temperature_position = options.raw_value

		if len(fields) > temperature_position:
			try:
				id = int(fields[0])
			except ValueError:
				continue
			if id == options.temperature_id:
				temperature = int(fields[temperature_position])
	p.stdout.close()
	if p.wait() != 0:
		error("%s failed (%d)" % (cmd[0], p.returncode))
	if temperature is None:
		error("no temperature (id %d) for %s" % (options.temperature_id, disk))
	return temperature

def get_temperature(disk, options):
	temp = get_temperature2(disk, options)
	if temp is None:
		time.sleep(options.smartctl_sleep)
		temp = get_temperature2(disk, options)
		if temp is None:
			error("no temperature (id %d) for %s" % (options.temperature_id, disk))
	return temp

def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
	parser.add_argument("-s", "--stdout", action="store_true", help="messages to stdout")
	parser.add_argument('--device_type', default=None, help='device type for smartctl')
	parser.add_argument('--hdparm', default="hdparm", help='hdparm command')
	parser.add_argument('--smartctl', default="smartctl", help='smartctl command')
	parser.add_argument('--temperature_id', default=194, type=int, help='ID for smartctl Temperature_Celsius attribute')
	parser.add_argument('--raw_value', default=9, type=int, help='column number for RAW_VALUE in smartctl attributes')
	parser.add_argument('--smartctl_sleep', default=2.2, type=float, help='sleep before retrying if smartctl fails')
	parser.add_argument('--replace_string', default="{}", help='replace this string with the filesystem in command')

	parser.add_argument('filesystem', help='a filesystem on the disk to be supervised')
	parser.add_argument('command', help='command to run')
	parser.add_argument('args', nargs=argparse.REMAINDER, help='arguments ...')

	options = parser.parse_args()
	disk = get_filesystem_partition(options.filesystem, options)
	verbose(options, "disk for %s is %s"  % (options.filesystem, disk))

	start_temp = get_temperature(disk, options)
	start_state = get_state(disk, options)
	now = time.time()
	cmd = [c.replace(options.replace_string, options.filesystem) for c in [options.command] + options.args]
	r = subprocess.call(cmd)
	duration = time.time() - now
	end_temp = get_temperature(disk, options)
#	end_state = get_state(disk, options)

	message = "filesystem=%s disk=%s start_temperature=%d start_state=%s duration=%0.2f end_temperature=%s temperature_gain=%d command=%s exit_code=%d" % (
		options.filesystem, disk, start_temp, start_state, duration, end_temp, end_temp - start_temp, shlex.quote(options.command), r
	)
	if options.stdout:
		print(message)
	else:
		syslog.syslog(syslog.LOG_INFO, message)
	sys.exit(r)

if __name__ == "__main__":
	main()
