#!/usr/bin/python3
# name-shadow Copyright (c) 2021 Stuart Pook (http://www.pook.it/)
# make hard link copy transforming every filename
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
import shlex
import logging
import re

def empty_if_none(s):
    if s:
        return s
    return ''

def transform_name(fn):
    fname,  suffix = os.path.splitext(fn)
    if not suffix:
        return None

    m = re.match(r"^(?P<fn>[^ ]+)(?:(?P<space> )(?P<text>[^:]+))?(?: \(\d\d\d\d[:-]\d\d[:-]\d\d( \d\d:\d\d)?\))?(?P<suffix>\.[a-z0-9][a-z0-9][a-z0-9])$", fn)

    if not m:
        logging.fatal("match failed on: %s", fn)

    name = empty_if_none(m.group('text')) + empty_if_none(m.group('space')) + m.group('fn') + m.group('suffix')

    logging.debug("%s mapped to %s", fn, name)
    return name

def check_and_update(src, dst_dir,  new_name):
    dst = os.path.join(dst_dir,  new_name)
    try:
        if os.path.samefile(src,  dst):
            return
    except FileNotFoundError:
            pass
    else:
        logging.info("rm %s", shlex.quote(dst))
        os.unlink(dst)
    logging.info("ln %s %s",  shlex.quote(src),  shlex.quote(dst))
    os.link(src,  dst)
    
def rm_extra(dst_dir,  wanted):
    for fn in frozenset(os.listdir(dst_dir)) -  wanted:
        fname = os.path.join(dst_dir,  fn)
        logging.debug("rm %s",  shlex.quote(fname))
        os.unlink(fname)

def check_and_update_directory(src_dir, dst_dir):
    wanted = set()
    for fn in os.listdir(src_dir):
        new_name =  transform_name(fn)
        if new_name:
            check_and_update(os.path.join(src_dir,  fn),  dst_dir,  new_name)
            wanted.add(new_name)
    return wanted

def shadow_dir(src_dir, dst_dir):
    wanted = check_and_update_directory(src_dir, dst_dir)
    rm_extra(dst_dir,  wanted)
    
def delete_directory(dst):
    count = 0
    for f in os.listdir(dst):
        os.unlink(os.path.join(dst, f))
        count = count + 1
    logging.info("rmdir %s (%d)",  shlex.quote(dst),  count)
    os.rmdir(dst)
    
def mkdir_missing(src_dirs,  dst_dirs,  dst_dir):
     for dir in src_dirs - dst_dirs:
        dst = os.path.join(dst_dir,  dir)
        logging.info("mkdir %s",  shlex.quote(dst))
        os.mkdir(dst)

def rmdir_extra(src_dirs,  dst_dirs,  dst_dir):
    for fn in dst_dirs - src_dirs:
        delete_directory(os.path.join(dst_dir, fn))

def shadow(src_dir, dst_dir):
    logging.debug("shadow %s %s",  shlex.quote(src_dir),  shlex.quote(dst_dir))
    src_dirs = frozenset(os.listdir(src_dir))
    dst_dirs = frozenset(os.listdir(dst_dir))
    
    mkdir_missing(src_dirs,  dst_dirs,  dst_dir)  

    for fn in src_dirs:
         shadow_dir(os.path.join(src_dir, fn), os.path.join(dst_dir, fn))

    rmdir_extra(src_dirs,  dst_dirs,  dst_dir)     
 
def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="make a shadow copy inversing the filename")
    parser.set_defaults(loglevel='warning')
    parser.add_argument("-v", "--verbose", dest='loglevel', action="store_const", const='debug', help="debug loglevel")
    parser.add_argument("-i", "--info", dest='loglevel', action="store_const", const='info', help="info loglevel")
    parser.add_argument("-l", "--loglevel", metavar="LEVEL", help="set logging level")

    parser.add_argument('source', help='directory to shadow')
    parser.add_argument('destination', help='destination directory')

    options = parser.parse_args()
    numeric_level = getattr(logging, options.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        sys.exit('Invalid log level: %s' % options.loglevel)
    logging.basicConfig(level=numeric_level)
    shadow(options.source, options.destination)

if __name__ == "__main__":
    main()
