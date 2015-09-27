#!/usr/bin/python3
# playnewestpod Copyright (c) 2015 Stuart Pook (http://www.pook.it/)
# make a shadow copy respecting the EXIF time order
# Used to make the sorting order by name of this files in a directory
# equal the sorting order by Exif Date.
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
import collections
import time
import tempfile
import datetime
import exifread
import time
import itertools
import math
import string
import errno

def myname():
    return os.path.basename(sys.argv[0])

def verbose(options, *args):
    if options.verbosity:
        print(*args, file=sys.stderr)

def verbose1(options, *args):
    if options.verbosity > 1:
        print(*args, file=sys.stderr)

def verbose2(options, *args):
    if options.verbosity > 2:
        print(*args, file=sys.stderr)

def same_prefix(filenames, options):
    if len(filenames[0]) <= options.same_camera:
        return False
    prefix = filenames[0][:options.same_camera]
    for fn in filenames:
        if not fn.startswith(prefix):
            return False
    return True

def photo_time(fn, options):
    try:
        with open(fn, 'rb') as img:
            data = exifread.process_file(img, stop_tag=options.tag, details=False)
            try:
                timestr = data[options.tag].printable
            except KeyError:
                verbose2(options, "no",  options.tag, "in", fn)
                return None
            verbose2(options, fn, options.tag, "=", timestr)
            try:
                ntime = time.strptime(timestr, "%Y:%m:%d %H:%M:%S")
            except ValueError as ex:
                verbose2(options, fn, ex)
                return None
            return ntime
    except IsADirectoryError:
        verbose(options, "found directory", fn)
        return None

def dates_if_required(path, filenames, options):
    if len(filenames) < 2:
        return None
    if same_prefix(filenames, options):
        return None

    dates = []
    for fn in filenames:
        date = photo_time(os.path.join(path, fn), options)
        if date is None:
            return None
        dates.append(date)

    return dates

def rmdir(src, options):
    verbose(options, "rmdir", src)
    os.rmdir(src)

def unlink(src, options):
    verbose(options, "unlink", src)
    os.unlink(src)

def mkdir(src, options):
    verbose(options, "mkdir", src)
    os.mkdir(src)

def symlink(src, dst, options):
    verbose(options, "ln -s", src, dst)
    os.symlink(src, dst)
    os.stat(dst)

def read_destination(dst, options):
    try:
        os.remove(dst)
        verbose(options, "rm", dst)
    except FileNotFoundError:
        pass
    except IsADirectoryError:
        return sorted(os.listdir(dst))
    mkdir(dst, options)
    return []

class Letters:
    base = len(string.ascii_uppercase)
    def int2base(self, v, ndigits):
        x = v
        digits = []
        for i in range(0, ndigits):
            digits.append(string.ascii_uppercase[x % Letters.base])
            x //= Letters.base
        assert x == 0, "%d != 0 for %d digits" % (x, ndigits)
        digits.reverse()
        res = ''.join(digits)
        verbose1(self.options, v, "in base", Letters.base, "with", ndigits, "digits", "is", res)
        return res
    def __init__(self, options):
        self.i = 0;
        self.count = True
        self.options = options
    def calibrate(self):
        assert self.i > 0, "%d" % self.i
        self.counted = self.i
        self.digits = math.floor(math.log(self.i, Letters.base) + 1)
        assert self.digits > 0, "%d for %d" % (self.digits, self.i)
        self.count = False
        self.i = 0
    def current(self):
        if self.count:
            return "%010d" % self.i
        return self.int2base(self.i, self.digits)
    def advance(self, path):
        self.i += 1
        r = self.current() + path
        verbose1(self.options, "advancing", r)
        return r
    def iszero(self):
        return self.i == 0
    def check(self):
        assert self.i == self.counted, "%d != %d for %d" % (self.i,  self.counted, self.digits)

def greater2(a, b, options): # if a > b
    for x, y in itertools.zip_longest(a, b, fillvalue=None):
        if x != y:
            if x is None:
                return False
            if y is None:
                return True
            if x.isdigit() and y.isdigit() or x.islower() and y.islower() or x.isupper() and y.isupper():
                return x > y
            return False
    return False

def greater(a, b, options): # if a > b
    r = greater2(a, b, options)
    verbose1(options, "greater", a, b, r)
    return r

def find_links(sorted_paths, dates, links, letter, options):
    prev = None
    odate = sorted_paths[0][0]
    for date, path in sorted_paths:
        new = letter.current() + path
        if date != odate and prev and not greater(new, prev, options):
            new = letter.advance(path)
        if links is not None:
            links.append([path, new])
        prev = new
        odate = date

def calculate_links(paths, dates, options):
    sorted_paths = sorted(zip(dates, paths))
    letter = Letters(options=options)
    find_links(sorted_paths, dates, None, letter, options)
    if letter.iszero():
        return None

    letter.calibrate()
    links = []
    find_links(sorted_paths, dates, links, letter, options)
    letter.check()
    return links

def do_shadow(src, paths, dst, dates, options):
    verbose(options, "do_shadow", src, dst)
    links = calculate_links(paths, dates, options)
    if links is None:
        return False
    existing = set(read_destination(dst, options))
    for image, renamed in links:
        if renamed in existing:
            existing.remove(renamed)
        else:
            symlink(os.path.join(src, image), os.path.join(dst, renamed), options)

    for bad in existing:
        unlink(os.path.join(dst, bad), options)
    return True

# return True iff dst is symlink
def delete_directory(dst, options):
    try:
        fd = os.open(dst, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    except OSError as ex:
        if ex.errno != errno.ELOOP:
            raise
        return True
    try:
        files = os.listdir(fd)
        for f in files:
            path = os.path.join(dst, f)
            os.readlink(path)
            unlink(path, options)
        rmdir(dst, options)
        return False
    finally:
        os.close(fd)

def shadow(src_dir, dst_dir, options):
    verbose(options, "shadow", src_dir, dst_dir)
    for fn in os.listdir(src_dir):
        src = os.path.join(src_dir, fn)
        dst = os.path.join(dst_dir, fn)
        paths = sorted(os.listdir(src))
        dates = dates_if_required(src, paths, options)
        need_symlink = not dates or not do_shadow(src, paths, dst, dates, options)
        if need_symlink and not delete_directory(dst, options):
            symlink(src, dst, options)

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="make a shadow copy respecting the EXIF time order")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--tag", default="EXIF DateTimeOriginal", help="EXIF tag for the date")
    parser.add_argument("--same_camera", type=int, default=4, help="same camera if all filenames are the same in this many characters")

    parser.add_argument('source', help='directory to shadow')
    parser.add_argument('destination', help='destination directory')

    options = parser.parse_args()
    shadow(options.source, options.destination, options)

if __name__ == "__main__":
    main()
