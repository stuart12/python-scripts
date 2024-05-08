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

import logging
import os
import argparse
import sys
import subprocess
import tempfile
import shlex # python 3.3 or later
import configparser
import re
try:
	import exifread
except ImportError:
	print("sudo apt install python3-exif", file=sys.stderr)
	raise
from PIL import Image
from PIL.ExifTags import TAGS
import piexif
from datetime import datetime

def myname():
	return os.path.basename(sys.argv[0])

def is_horizontal(cr2):
	with open(cr2, 'rb') as img:
		logging.debug(f"is_horizontal({shlex.quote(cr2)})")
		data = exifread.process_file(img, details=True)
		for field in ['Image Orientation', 'Camera Orientation', 'Orientation']:
			d = data.get(field)
			if d:
				return d.printable.lower().startswith("horizontal")
		return True

def getDateTime(fn):
	base = os.path.basename(fn)
	m = re.match(r".* \((\d\d\d\d)[-/:](\d\d)[-/:](\d\d) (\d\d)[-:/](\d\d)\)\.[a-z.]*", base)
	if m:
		r = f"{m.group(1)}:{m.group(2)}:{m.group(3)} {m.group(4)}:{m.group(5)}:00";
		logging.debug(f"date/time from {fn} is {r}")
		return r
	m = re.match(r".* \((\d\d\d\d)[-/:](\d\d)[-/:](\d\d)\)\.[a-z.]*", base)
	if m:
		r = f"{m.group(1)}:{m.group(2)}:{m.group(3)} 12:00:00";
		logging.debug(f"date from {fn} is {r}")
		return r
	logging.debug(f"no date from {fn} -> {base}")
	return None

def setDateTime(cr2name, output):
	#subprocess.check_call(["exiftool", "-tagsFromFile", cr2name, output])

	date = getDateTime(cr2name)
	if date:
		im = Image.open(output)
		#exif_dict = piexif.load(im.info["exif"])
		zeroth_ifd = {piexif.ImageIFD.Make: "Canon",  # ASCII, count any
				  piexif.ImageIFD.XResolution: (96, 1),  # RATIONAL, count 1
				  piexif.ImageIFD.YResolution: (96, 1),  # RATIONAL, count 1
				  piexif.ImageIFD.Software: "piexif"  # ASCII, count any
				  }
		exif_ifd = {piexif.ExifIFD.ExifVersion: b"\x02\x00\x00\x00",  # UNDEFINED, count 4
				piexif.ExifIFD.DateTimeOriginal: date,
				}
		gps_ifd = {piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),  # BYTE, count 4
			   piexif.GPSIFD.GPSAltitudeRef: 1,  # BYTE, count 1 ... also be accepted '(1,)'
			   }
		#exif_dict = {"0th":zeroth_ifd, "Exif":exif_ifd, "GPS":gps_ifd}
		exif_dict = {"Exif":exif_ifd}
		#exif_dict["0th"][piexif.ImageIFD.DateTime] = date

		exif_bytes = piexif.dump(exif_dict)
		im.save(output, "jpeg", exif=exif_bytes, quality="keep", optimize=True)

def main(argv):
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="Format image with rawtherapee")
	parser.set_defaults(check_children=False)
	parser.set_defaults(loglevel='warning')
	parser.add_argument("-v", "--verbose", dest='loglevel', action="store_const", const='debug', help="debug loglevel")
	parser.add_argument("--icc", default=None, metavar="ICC filename", help="ICC colour profile for image [%default]")
	parser.add_argument("-n", "--dryrun", action="store_true", help="dryrun")
	parser.add_argument("--quality", type=int, default=40, help="JPEG quality [%default]")
	parser.add_argument("--height", type=int, help="height [%default]")
	parser.add_argument("--width", type=int, help="width [%default]")
	parser.add_argument("--output", help="output JPEG file")
	parser.add_argument("--pp3", default=None, help="rawtherapee PP3 file")
	parser.add_argument("--resizing_pp3", default=None, help="resizing rawtherapee PP3 file")
	parser.add_argument('image', nargs=1, help='image to process')
	options = parser.parse_args()

	numeric_level = getattr(logging, options.loglevel.upper(), None)
	if not isinstance(numeric_level, int):
		sys.exit('Invalid log level: %s' % options.loglevel)
	logging.basicConfig(level=numeric_level)

	cr2 = options.image[0]

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
			w = int(crop['W'])
			h = int(crop['H'])
			if w > h:
				width, height = height, width
				logging.debug("width %d height %d swap from %d %d", width, height, w, h)
			else:
				logging.debug("width %d height %d from %d %d", width, height, w, h)
		else:
			logging.debug("width %d height %d without crop", width, height)
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
	if options.icc:
		print("InputProfile=file:" + options.icc, file=pp3)
	pp3.flush()

	command = [ "rawtherapee-cli", "-Y"]
	command.append("-j%d" % options.quality)
	command.append("-d")
	if options.pp3:
		command.extend(["-p", options.pp3])
	command.extend(["-p", pp3.name])
	command.extend(["-o", options.output])
	command.extend(["-c", cr2])
	stderr = tempfile.TemporaryFile(mode='w+')
	logging.debug("running %s" % " ".join(map(shlex.quote, command)))
	status = subprocess.call(command, stdout=open("/dev/null", "w"), stderr=stderr)
	if status:
		print(myname()+ ":", "command failed (%d):" % status, " ".join(shlex.quote(c) for c in command), file=sys.stderr)
		stderr.seek(0)
		for line in stderr:
			print(line, end='', file=sys.stderr)
		sys.exit(status)
	setDateTime(cr2, options.output)
	subprocess.check_call(['exiftool', '-overwrite_original', '-tagsFromFile', cr2, '-n', '-Orientation=1', '-quiet', options.output])

if __name__ == "__main__":
	main(sys.argv)
