#!/usr/bin/python3
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

def import_failed(pkg):
	print(f"import failed, do: sudo apt-get install {pkg}", file=sys.stderr)
	sys.exit(87)

try:
    from PIL import Image
except ImportError:
	import_failed("python3-pil")
import string
import optparse
import collections
try:
    import piexif
except ImportError:
    import_failed("python3-piexif")
try:
    import cv2
except ImportError:
    import_failed("python3-opencv")
try:
    import lensfun
except ImportError:
    import_failed("python3-lensfun")

import gi.repository
gi.require_version('GExiv2', '0.10')
try:
	from gi.repository import GExiv2
except ImportError:
    print("sudo apt-get install gir1.2-gexiv2-0.10 python3-gi", file=sys.stderr)
    raise

def error(*message):
	print(*message, file=sys.stderr)
	sys.exit(6)

def verbose(options, *message):
	if options.verbose:
		print(*message, file=sys.stderr)

def update_size(dest, image):
	# http://stackoverflow.com/questions/400788/resize-image-in-python-without-losing-exif-data
	dest.set_metadata_pixel_width(image.size[0])
	dest.set_metadata_pixel_height(image.size[1])

def read_exif_data(image, source_path, options):
	source = GExiv2.Metadata(source_path)
	return source

def copy_exif_data(image, source_path, dest_path, options):
	source = read_exif_data(image, source_path, options)
	dest = GExiv2.Metadata(dest_path)
	for tag in source.get_exif_tags():
		try:
			dest[tag] = source[tag]
		except UnicodeDecodeError:
			pass
	update_size(dest, image)
	try:
		dest.save_file(dest_path)
	except gi.repository.GLib.Error:
		dest.clear_exif() # old img* files
		dest.save_file(dest_path)

def shrink(inputfile, options):
	verbose(options, "shrink", inputfile)
	im = Image.open(inputfile)
	iw = im.size[0]
	ih = im.size[1]
	width = options.width
	height = options.height
	if ih and iw and ih > iw:
		width, height = height, width
	if not (width and height) or iw <= width * options.size_margin and ih <= height * options.size_margin:
		if options.reflink:
			subprocess.check_call(["cp", "--reflink=" + options.reflink, inputfile, options.output])
		else:
			if options.no_dimensions_symlink:
				shutil.copyfile(inputfile, options.output)
			else:
				os.symlink(inputfile, options.output)
	else:
		im.thumbnail((width, height), Image.Resampling.LANCZOS)
		im = im.convert('RGB')
		im.save(options.output, "JPEG", quality=options.quality)
		copy_exif_data(im, inputfile, options.output, options)
		if os.path.getsize(options.output) > os.path.getsize(inputfile) * 1.2:
			os.remove(options.output)
			if options.reflink:
				subprocess.check_call(["cp", "--reflink=" + options.reflink, inputfile, options.output])
			else:
				os.symlink(inputfile, options.output)

def get_required_exif_data(options, exif):
	# https://git.gnome.org/browse/gexiv2/tree/GExiv2.py
	cam_maker = exif.get('Exif.Image.Make')
	if cam_maker is None:
		return None
	camera_model = exif.get('Exif.Image.Model')
	if camera_model is None:
		return None

	focallength = exif.get_exif_tag_rational('Exif.Photo.FocalLength')
	if focallength is None:
		return None

	aperture = exif.get_exif_tag_rational('Exif.Photo.ApertureValue')
	if aperture is None:
		return None

	distance = exif.get_exif_tag_rational('Exif.Photo.SubjectDistance')
	if distance is None:
		return None

	PhotoData = collections.namedtuple('PhotoData', ['camera_maker', 'camera_model', 'focal_length', 'aperture', 'subject_distance'])
	verbose(options, "have exif data")
	return PhotoData(
		camera_maker=cam_maker,#.encode('ascii','ignore'),
		camera_model=camera_model,#.encode('ascii','ignore'),
		focal_length=focallength,
		aperture=aperture,
		subject_distance=distance
		)

def get_size(iw, ih, width, height):
	if width >= iw and height >= ih:
		return None
	rw = width / float(iw)
	rh = height / float(ih)
	if rw > rh:
		return (int(iw * rh), height)
	return (width, int(ih * rw))

def undistort(inputfile, options):
	exif = GExiv2.Metadata(inputfile)
	required_info = get_required_exif_data(options, exif)
	if required_info is None:
		return shrink(inputfile, options)

	db = lensfun.get_core_database()
	cam = db.find_cameras(required_info.camera_maker, required_info.camera_model)[0]
	lens = db.find_lenses(cam)[0]

	im = cv2.imread(inputfile)
	ih, iw = im.shape[0], im.shape[1]

	owidth = options.width
	oheight = options.height
	if ih > iw:
		verbose(options, "swap", owidth, oheight)
		owidth, oheight = oheight, owidth
	width = owidth if owidth else iw
	height = oheight if oheight else ih

	mod = lensfun.Modifier(lens, cam.crop_factor, iw, ih)
	mod.initialize(required_info.focal_length, required_info.aperture, required_info.subject_distance)

	undistCoords = mod.apply_geometry_distortion()
	imUndistorted = cv2.remap(im, undistCoords, None, cv2.INTER_NEAREST)
	#http://docs.opencv.org/2.4/modules/imgproc/doc/geometric_transformations.html
	sz = get_size(iw, ih, width, height)
	if sz:
		shrunk = cv2.resize(imUndistorted, sz, interpolation=cv2.INTER_AREA)
		verbose(options, "ratio is (%d %d) != (%d %d)" % (shrunk.shape[1], shrunk.shape[0], iw, ih))
		if shrunk.shape[0] != height and shrunk.shape[1] != height and shrunk.shape[0] != width and  shrunk.shape[1] != width:
			error("new size is wrong (%d %d) != (%d %d)" % (shrunk.shape[1], shrunk.shape[0], iw, ih))
		if abs(shrunk.shape[0] / float(shrunk.shape[1]) - im.shape[0] / float(im.shape[1])) > options.ratio_change:
			error("ratio changed (%d %d) != (%d %d)" % (shrunk.shape[1], shrunk.shape[0], im.shape[1], im.shape[0]))
	else:
		shrunk = imUndistorted
		verbose(options, "using imUndistorted")
	cv2.imwrite(options.output, shrunk, (cv2.IMWRITE_JPEG_QUALITY, options.quality))

	exif['Exif.Photo.PixelXDimension'] = str(width)
	exif['Exif.Photo.PixelYDimension'] = str(height)
	exif.save_file(options.output)

def main():
	parser = optparse.OptionParser(usage="usage: %prog [--help] [options] inputfile")
	parser.add_option("-o", "--output", help="output file name [%default]")
	parser.add_option("-v", "--verbose", action="store_true", help="verbose")
	parser.add_option("--resizing_pp3", metavar="DUMMY", help="ignored [%default]")
	parser.add_option("-R", "--reflink", default="always", help="cp reflink option [%default]")
	parser.add_option("--no_dimensions_symlink", action="store_true", help="don't make any symlinks even if the dimensions seem ok")
	parser.add_option("-m", "--size_margin", type='float', default=1.1, help="margin for files almost the same size [%default]")
	parser.add_option("--ratio_change", type='float', default=0.002, help="maximum accepted ratio change after resize [%default]")
	parser.add_option("-w", "--width", type='int', default=None, help="output width [%default]")
	parser.add_option("--height", type='int', default=None, help="output height [%default]")
	parser.add_option("-q", "--quality", type='int', default=20, help="output JPEG quality [%default]")
	(options, args) = parser.parse_args()
	if len(args) != 1:
		parser.error("must supply 1 argument (found %d %s)" % (len(args), args))
	inputfile = args[0]
	if not options.output:
		parser.error("--output option is compulsory")
		
	undistort(inputfile, options)
	return 0

if __name__ == "__main__":
	sys.exit(main())
