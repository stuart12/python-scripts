#!/usr/bin/python3
# rotate-pcd.py3 Copyright (c) 2013 Stuart Pook (http://www.pook.it/)
# convert a pcd image to jpeg using ImageMagik
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
import argparse
import sys
import subprocess

def myname():
	return os.path.basename(sys.argv[0])

def main():
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, description="compare configuration files")

	parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
	parser.add_argument("--quality", type=int, default=40, help="JPEG quality")
	parser.add_argument("--height", type=int, default=0, help="height")
	parser.add_argument("--width", type=int, default=0, help="width")
	parser.add_argument("--output", help="output JPEG file")
	parser.add_argument("--resizing_pp3", metavar="DUMMY", default=None, help="ignored")

	parser.add_argument('files', nargs=argparse.REMAINDER, help='file to convert')

	options = parser.parse_args()

	if len(options.files) != 1:
		parser.print_help()
		sys.exit("bad arguments")

	input = options.files[0]

	command = ["convert" , "-quality", str(options.quality)]
	if options.height and options.width:
		sz = min(options.width, options.height)
		command.extend(["-resize", "%dx%d^" % (sz, sz)])
	if input.endswith(".pcd"):
		command.append(input + "[5]")
	else:
		command.append(input)
	command.append(options.output)

	if options.verbosity > 0:
		print(" ".join(command))

	subprocess.check_call(command)

if __name__ == "__main__":
	main()
