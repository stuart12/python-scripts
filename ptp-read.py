#!/usr/bin/python3

# Copyright (C) 2024, Stuart Pook https://www.pook.it
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import locale
import logging
import os
import sys
import argparse
import collections
import time
import uuid
import glob
import subprocess

import gphoto2 as gp

suffixes = { 'jpg': 3, 'cr2': 1, 'raf': 0 }

def list_camera_files(camera, path='/'):
    result = {}
    # get files
    gp_list = camera.folder_list_files(path)
    for name, value in gp_list:
        result[name] = os.path.join(path, name)
    # read folders
    folders = []
    gp_list = camera.folder_list_folders(path)
    for name, value in gp_list:
        folders.append(name)
    # recurse over subfolders
    for name in folders:
        result.update(list_camera_files(camera, os.path.join(path, name)))
    return result
        
def wanted(fn, jpeg):
    folder, base = os.path.split(fn)
    root, directory = os.path.split(folder)
    fields = base.split('.')
    if len(fields) != 2:
        return None
    suffix = fields[1].lower()
    if suffix == 'jpg' or not jpeg and suffix in suffixes:
        return directory[4].lower() + directory[0:3] + fields[0][4:8]
    return None
        
def regroup(camera_files, jpeg):
    # newlist = [[b, x] for x in camera_files if (b := wanted(x)) ]
    d = collections.defaultdict(list)
    for fn in camera_files:
        w = wanted(fn=fn, jpeg=jpeg)
        if w:
            d[w].append(fn)
    return d
    # newlist = [[os.path.basename(x), x] for x in camera_files if "a" in x]
    
class Seen:

    def __init__(self, directory, jpeg):
        self.directory = directory
        self.prefix = ('jpg' if jpeg else 'raw') + '.'
    
    def read_handled(self):
        seen = set()
        fn = os.path.join(self.directory, self.prefix + '*')
        logging.debug('glob file listing read photos: %s', fn)
        for path in glob.iglob(fn):
            with open(path) as f:
                for l in f.readlines():
                    seen.add(l.strip())
        logging.info("%d %s photos already seen", len(seen), self.prefix)
        return seen

    def new_handled(self):
        fn = os.path.join(self.directory, self.prefix + uuid.uuid4().hex)
        logging.debug('new handled list: %s', fn)
        return open(fn, mode='x')

def copy_photo(photo, path, dest_dir, camera):
    folder, name = os.path.split(path)
    dest = os.path.join(dest_dir, photo + '.' + name.split('.')[1].lower())
    tmp = dest + '~'
    logging.debug("%s: copy %s to %s", photo, path, tmp)
    camera_file = camera.file_get(folder, name, gp.GP_FILE_TYPE_NORMAL)
    camera_file.save(tmp)
    logging.debug('rename(%s, %s)', tmp, dest)
    os.rename(tmp, dest)
    return os.stat(dest).st_size


def check_space(minimum_disk_space, where):
        statvfs = os.statvfs(where)
        if statvfs.f_frsize * statvfs.f_bavail < minimum_disk_space:
            print(f"less than {minimum_disk_space} bytes free, stopping")
            return False
        return True

def copy_files(camera_files, camera, dest_dir, seen_fp, minimum_disk_space):
    bytes = 0
    for photo, files in camera_files.items():
        if not check_space(minimum_disk_space, where=dest_dir):
            return bytes

        def key(a):
            return suffixes.get(a.split('.')[1].lower())
        ordered = sorted(files, key=key)
        bytes = bytes + copy_photo(photo=photo, path=ordered[0], dest_dir=dest_dir, camera=camera)
        print(photo, file=seen_fp, flush=True)
    return bytes

def main(destination, jpeg, seen_directory, minimum_disk_space, dry_run):
    ret_code = subprocess.call(['gio', 'mount',  '--unmount-scheme=gphoto2'])
    logging.log(logging.DEBUG if ret_code == 0 else logging.WARNING, "gio unmount returned: %d", ret_code)
    locale.setlocale(locale.LC_ALL, 'C')
    seen_object = Seen(jpeg=jpeg, directory=seen_directory)
    seen = seen_object.read_handled()
    gp.check_result(gp.use_python_logging(mapping={
        gp.GP_LOG_ERROR   : logging.WARNING,
        gp.GP_LOG_DEBUG   : logging.DEBUG - 1,
        gp.GP_LOG_VERBOSE : logging.DEBUG - 3,
        gp.GP_LOG_DATA    : logging.DEBUG - 6}))
    # https://github.com/jim-easterbrook/python-gphoto2#object-oriented-interface
    camera = gp.Camera()
    logging.info("after gp_camera_new")
    camera.init()
    logging.info("after gp_camera_init")
    camera_files = regroup(list_camera_files(camera).values(), jpeg=jpeg)
    logging.info("%d photos on camera", len(camera_files))
    unseen = {k: v for k, v in camera_files.items() if k not in seen}
    logging.info("%d new photos on camera", len(unseen))
    if not dry_run and len(unseen) > 0:
        with seen_object.new_handled() as seen_fp:
            start_time = time.time()
            bytes = copy_files(camera_files=unseen, camera=camera, dest_dir=destination, seen_fp=seen_fp, minimum_disk_space=minimum_disk_space)
            duration = time.time() - start_time
            logging.info("%d bytes in %0.1fs, %0.1f MiB/s", bytes, duration, bytes / duration / 1024 / 1024)
    logging.info("exiftool -if 'not $gps:all' -geotag ~/Syncthing/bluejay-tracks/202\\* -overwrite_original *.???")
#    camera.exit()
    return 0

if __name__ == "__main__":
    umask = os.umask(0)
    os.umask(umask)
    parser = argparse.ArgumentParser(allow_abbrev=False,
            description="read photos from a PTP device with a record",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # parser.add_argument("--mode", default=0o666 & ~umask, type=int, help="mode for files")
    parser.set_defaults(loglevel='info')
    parser.add_argument("-v", "--verbose", dest='loglevel', action='store_const', const='debug', help='set log level to debug')
    parser.add_argument("--warn", dest='loglevel', action='store_const', const='warn', help='set log level to warn')
    parser.add_argument("-d", "--destination", default=".", help="directory to read into")
    parser.add_argument("--seen", default=os.path.expanduser("~/Syncthing/stuart/dynamic/seen-photos.d"), metavar="DIRECTORY", help="directory of read photos")
    parser.add_argument("--space", "-s", type=int, default=150, metavar='MEBIBYTES', help="minimum disk space to continue")
    parser.add_argument('-j', '--jpg', '--jpeg', action='store_true', help='retrieve jpg format')
    parser.add_argument('-n', '--dryrun', '--dry-run', action='store_true', help='do not read')

    args = parser.parse_args()
    loglevel = args.loglevel
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(format=os.path.basename(__file__) + ':%(levelname)s:%(name)s: %(message)s', level=numeric_level)

    minimum_disk_space = args.space * 1024 * 1024
    status = main(seen_directory=args.seen, destination=args.destination, jpeg=args.jpg, minimum_disk_space=minimum_disk_space, dry_run=args.dryrun)
    sys.exit(status)
# gio mount -s gphoto2
# gio mount  --unmount-scheme=gphoto2
