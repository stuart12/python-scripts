#!/usr/bin/python3
# https://github.com/jim-easterbrook/python-gphoto2/blob/main/examples/copy-files.py

# python-gphoto2 - Python interface to libgphoto2
# http://github.com/jim-easterbrook/python-gphoto2
# Copyright (C) 2014-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime
import locale
import logging
import os
import sys

import gphoto2 as gp
import collections

PHOTO_DIR = os.path.expanduser('~/Pictures/from_camera')

def get_target_dir(timestamp):
    return os.path.join(PHOTO_DIR, timestamp.strftime('%Y/%Y_%m_%d/'))

def list_computer_files():
    result = []
    for root, dirs, files in os.walk(os.path.expanduser(PHOTO_DIR)):
        for name in files:
            if '.thumbs' in dirs:
                dirs.remove('.thumbs')
            if name in ('.directory',):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in ('.db',):
                continue
            result.append(os.path.join(root, name))
    return result

def list_camera_files(camera, path='/'):
    result = []
    # get files
    gp_list = gp.check_result(
        gp.gp_camera_folder_list_files(camera, path))
    for name, value in gp_list:
        result.append(os.path.join(path, name))
    # read folders
    folders = []
    gp_list = gp.check_result(
        gp.gp_camera_folder_list_folders(camera, path))
    for name, value in gp_list:
        folders.append(name)
    # recurse over subfolders
    for name in folders:
        result.extend(list_camera_files(camera, os.path.join(path, name)))
    return result

def get_camera_file_info(camera, path):
    folder, name = os.path.split(path)
    return gp.check_result(
        gp.gp_camera_file_get_info(camera, folder, name))
        
def wanted(fn):
    base = os.path.basename(fn)
    fields = base.split('.')
    if len(fields) == 2 and fields[1] in ['JPG', 'RAR']:
        return fields[0]
    return None
        
def regroup(camera_files):
    # newlist = [[b, x] for x in camera_files if (b := wanted(x)) ]
    d = collections.defaultdict(list)
    for fn in camera_files:
        w = wanted(fn)
        if w:
            d[w].append(fn)
    return d
    # newlist = [[os.path.basename(x), x] for x in camera_files if "a" in x]
    
def read_handled(path):
    seen = set()
    with open(path) as f:
        for l in f.readlines():
            seen.add(l.strip())
    return seen

def copy_files(camera_files, camera, seen):
    for photo, files in camera_files:
        if photo not in seen:
            ordered = sorted(files)
            print(photo, ordered)

def main():
    locale.setlocale(locale.LC_ALL, 'C')
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s', level=logging.INFO)
    seen = read_handled(os.path.expanduser('~/Syncthing/stuart/dynamic/seen-photos'))
    logging.info("%d seen", len(seen))
    print(seen)
    return 0
    callback_obj = gp.check_result(gp.use_python_logging())
    computer_files = list_computer_files()
    camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(camera))
    print('Getting list of files from camera...')
    camera_files = regroup(list_camera_files(camera))
    if not camera_files:
        print('No files found')
        return 1
    print(camera_files)
    print('Copying files...')
    copy_files(camera_files, camera, seen
        )
    return 0
    for path in camera_files:
        info = get_camera_file_info(camera, path)
        timestamp = datetime.fromtimestamp(info.file.mtime)
        folder, name = os.path.split(path)
        dest_dir = get_target_dir(timestamp)
        dest = os.path.join(dest_dir, name)
        if dest in computer_files:
            continue
        print('%s -> %s' % (path, dest_dir))
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)
        camera_file = gp.check_result(gp.gp_camera_file_get(
            camera, folder, name, gp.GP_FILE_TYPE_NORMAL))
        gp.check_result(gp.gp_file_save(camera_file, dest))
    gp.check_result(gp.gp_camera_exit(camera))
    return 0

if __name__ == "__main__":
    sys.exit(main())
