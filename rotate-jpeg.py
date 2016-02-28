#!/usr/bin/python
# rotate-jpeg Copyright (c) 2015 Stuart Pook (http://www.pook.it/)
# rotate & resize a jpeg file
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function

import os
import subprocess
import sys
import Image
import string
import optparse
import pyexiv2

def update_size(dest, image):
	# http://stackoverflow.com/questions/400788/resize-image-in-python-without-losing-exif-data
	dest["Exif.Photo.PixelXDimension"] = image.size[0]
	dest["Exif.Photo.PixelYDimension"] = image.size[1]

def copy_exif_data(image, source_path, dest_path, options):
	if pyexiv2.version_info >= (0, 3, 2):
		source = pyexiv2.ImageMetadata(source_path)
		source.read()
		dest = pyexiv2.ImageMetadata(dest_path)
		dest.read()
		source.copy(dest)
		update_size(dest, image)
		dest.write()
	else:
		source = pyexiv2.Image(source_path)
		source.readMetadata()
		dest = pyexiv2.Image(dest_path)
		dest.readMetadata()
		for k in source.exifKeys():
			v = source[k]
			try:
				dest[k] = source[k]
			except ValueError as e:
				if options.verbose:
					print("skipping Exif tag", k, v, e.args[0])
				pass
		update_size(dest, image)
	#	source.copyMetadataTo(dest)
		dest.writeMetadata()

def shrink(inputfile, options):
	im = Image.open(inputfile)
	iw = im.size[0]
	ih = im.size[1]
	width = options.width
	height = options.height
	if ih and iw and ih > iw:
		width, height = height, width
	if not (width and height) or iw <= width * options.size_margin and ih <= height * options.size_margin:
		if options.no_dimensions_symlink:
			shutil.copyfile(inputfile, options.output)
		else:
			os.symlink(inputfile, options.output)
	else:
		im.thumbnail((width, height), Image.ANTIALIAS)
		im.save(options.output, "JPEG", quality=options.quality)
		copy_exif_data(im, inputfile, options.output, options)
		if os.path.getsize(options.output) > os.path.getsize(inputfile) * 1.2:
		    os.remove(options.output)
		    os.symlink(inputfile, options.output)

def main():
	parser = optparse.OptionParser(usage="usage: %prog [--help] [options] inputfile")
	parser.add_option("-o", "--output", help="output file name [%default]")
	parser.add_option("-v", "--verbose", action="store_true", help="verbose")
	parser.add_option("--resizing_pp3", metavar="DUMMY", help="ignored [%default]")
	parser.add_option("--no_dimensions_symlink", action="store_true", help="don't make any symlinks even if the dimensions seem ok")
	parser.add_option("-m", "--size_margin", type='float', default=1.1, help="margin for files almost the same size [%default]")
	parser.add_option("-w", "--width", type='int', default=None, help="output width [%default]")
	parser.add_option("--height", type='int', default=None, help="output height [%default]")
	parser.add_option("-q", "--quality", type='int', default=40, help="output JPEG quality [%default]")
	(options, args) = parser.parse_args()
	if len(args) != 1:
		parser.error("must supply 1 argument (found %d %s)" % (len(args), args))
	inputfile = args[0]
	if not options.output:
		parser.error("--output option is compulsory")
		
	shrink(inputfile, options)
	return 0

if __name__ == "__main__":
	sys.exit(main())
