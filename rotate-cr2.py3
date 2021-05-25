#!/usr/bin/python3 -u
# set noexpandtab copyindent preserveindent softtabstop=0 shiftwidth=4 tabstop=4
# rotated-cr2 Copyright (c) 2012, 2013, 2014 Stuart Pook (http://www.pook.it/)
# create jpg from cr2 accounting for screen size
#
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
import optparse
import sys
import subprocess
import tempfile
import shlex # python 3.3 or later
import configparser
try:
	import exifread
except ImportError:
	print("sudo apt install python3-exif", file=sys.stderr)
	raise

def myname():
	return os.path.basename(sys.argv[0])

def is_horizontal(cr2):
	with open(cr2, 'rb') as img:
		data = exifread.process_file(img, details=True)
		for field in ['Image Orientation', 'Camera Orientation', 'Orientation']:
			d = data.get(field)
			if d:
				return d.printable.lower().startswith("horizontal")
		return True

def main(argv):
	parser = optparse.OptionParser(usage="usage: %prog [--help] [options] source_dir target_dir")
	parser.set_defaults(check_children=False)
	parser.disable_interspersed_args()
	parser.add_option("-v", "--verbose", action="store_true", help="verbose messages")
	parser.add_option("-n", "--dryrun", action="store_true", help="dryrun")
	parser.add_option("--quality", type="int", default=40, help="JPEG quality [%default]")
	parser.add_option("--height", type="int", help="height [%default]")
	parser.add_option("--width", type="int", help="width [%default]")
	parser.add_option("--output", help="output JPEG file")
	parser.add_option("--pp3", default=None, help="rawtherapee PP3 file")
	parser.add_option("--resizing_pp3", default=None, help="resizing rawtherapee PP3 file")
	(options, args) = parser.parse_args()

	cr2 = args[0]

	width = options.width
	height = options.height
	if options.pp3:
		config = configparser.ConfigParser()
		with open(options.pp3) as f:
			config.read_file(f)
		try:
			crop = config['Crop']
		except KeyError as x:
			print("%s: no %s in %s" % (myname(), x, shlex.quote(options.pp3)), file=sys.stderr)
			raise
		if crop['Enabled']:
			w = int(crop['W']) - int(crop['X'])
			h = int(crop['H']) - int(crop['Y'])
			if w < h:
				width, height = height, width
	else:
		if not is_horizontal(cr2):
			width, height = height, width

	pp3 = tempfile.NamedTemporaryFile(mode='w+', suffix='.pp3', delete=True)
	print("[Resize]", file=pp3)
	if width and height:
		print("Enabled=true", file=pp3)
		print("Method=Lanczos", file=pp3)
		print("AppliesTo=Cropped area", file=pp3)
		print("Width=%d" % width, file=pp3)
		print("Height=%d" % height, file=pp3)
	else:
		print("Enabled=false", file=pp3)
	print("[LensProfile]",  file=pp3)
	print("LcMode=lfauto",  file=pp3)
	print("[Color Management]", file=pp3)
	print("OutputProfile=", file=pp3) # use sRGB colour profile
	pp3.flush()

	command = [ "rawtherapee-cli", "-Y"]
	command.append("-j%d" % options.quality)
	if options.pp3:
		command.extend(["-p", options.pp3])
	command.extend(["-p", pp3.name])
	command.extend(["-o", options.output])
	command.extend(["-c", args[0]])
	stderr = tempfile.TemporaryFile(mode='w+')
	if options.verbose:
		print(myname() + ": running", " ".join(map(shlex.quote, command)), file=sys.stderr)
	status = subprocess.call(command, stdout=open("/dev/null", "w"), stderr=stderr)
	if status:
		print(myname()+ ":", "command failed (%d):" % status, " ".join(shlex.quote(c) for c in command), file=sys.stderr)
		stderr.seek(0)
		for line in stderr:
			print(line, end='', file=sys.stderr)
		sys.exit(status)

if __name__ == "__main__":
	main(sys.argv)
