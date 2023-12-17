#!/usr/bin/python3 -P
# mk-archive Copyright (c) 2013 Stuart Pook (http://www.pook.it/)
# make a squashfs on luks image of all my files to be archived
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

# don't put newlines at end of the passwords in the password files

# to mount use:
#        sudo mount -r /dev/sdd2 /mnt
# to umount:
#        sudo umount.crypt /mnt

# need to create archive.luks.md5 and archive.luks.sz (and perhaps archive.sqsh.sz) in options.output
# need to add these files to FAT partition (to make check.sh work)
# could also add a timestamp to options.output and copy it to the FAT partition

import os
import sys
import subprocess
import tempfile
import optparse
import shlex
import time
import datetime
import hashlib
import errno
import stat
import shutil
import math
import pwd
import argparse
import logging

class MyError(Exception):
    """Base class for exceptions in this module."""
    pass

def verbose(options, *args):
    if options.verbose:
        print(*args, file=sys.stderr)

def print_command(command, cwd=None, stdin=None):
    if cwd:
        print("(cd", cwd, '&& ', end='')
    print(" ".join([shlex.quote(c) for c in command]), end="")
    if stdin:
        print(" <", stdin, end="")
    if cwd:
        print(")")
    else:
        print()
    return command

def call(command,  **kwargs):
    logging.info("running: %s",  command)
    subprocess.check_call(args=command, **kwargs)
 
def sudo(command,  **kwargs):
    cmd = ['sudo'] + command
    call(cmd,  **kwargs)

def output(command, stdin=None):
    print_command(command, stdin=stdin)
    if stdin:
        r = subprocess.check_output(command, stdin=open(stdin))
    else:
        r = subprocess.check_output(command)
    return r.decode().strip()

def output_sudo(command, stdin=None):
    return output(["sudo"] + command, stdin=stdin)

    os.stat(mount_point)
    if os.path.ismount(mount_point):
        call_sudo(options, [command, mount_point])

    if os.path.exists(f):
        raise MyError(f + " must not exist")

    try:
        os.remove(name)
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
    image = open(name, "w")
    image.seek(size - 1)
    image.write("\0")
    image.flush()
    image.seek(0)
    assert os.fstat(image.fileno()).st_size == size
    return image

    image_size = int(output_sudo(["blockdev", "--getsize", loop]))
    crypt_size = int(output_sudo(["blockdev", "--getsize", crypt_device]))
    return image_size - crypt_size

    call_sudo(options, ["cp", squash_file, crypt_device])

    with make_sparse_file(image_filename, size) as image:
        loop =  output_sudo(["losetup", "--show", "-f", image_filename])
        try:
            call_sudo(options, ["sudo", "cryptsetup", "luksFormat", loop, "-"], stdin=passwords[0])
            for f in  passwords[1:]:
                call_sudo(options, ["cryptsetup", "luksAddKey", loop, "--key-file", passwords[0], f])
            call_sudo(options, ["cryptsetup", "luksOpen", "--key-file", passwords[-1], loop, options.crypt_device])
            try:
                crypt_device = os.path.join("/dev/mapper", options.crypt_device)
                return func(loop, crypt_device, arg, options)
            finally:
                call_sudo(options, ["cryptsetup", "remove", options.crypt_device])
        finally:
            call_sudo(options, ["losetup", "-d", loop])

    
def luks(usb,  passwords,  label,  root_device):
    password = os.path.join(passwords, 'password0')
    with open('/dev/null',  'w') as devnull:
        sudo(['cryptsetup',  'luksDump',  '--dump-volume-key',  '--batch-mode',  '--key-file',  password,  root_device], stdout=devnull)
    sudo(['cryptsetup',  'luksFormat',  '--label', label,'--type',  'luks2', '--integrity',  'hmac-sha256',  usb, password]) 
    sudo(['cryptsetup',  'luksOpen', '--key-file', password,  usb, label])
    sudo(['chown',  str(os.getuid()),  os.path.join('/dev/mapper',  label)])
    
def run_scripts(scripts,  directory,  home):
    return [os.path.relpath(subprocess.check_output([os.path.join(directory,  s),  '--cache_filename'],  text=True).strip(),  start=home) for s in scripts]
    
def mkdir(path,  dryrun):
    logging.debug("mkdir %s",  path)
    os.mkdir(path, mode=0o700)
    
def decrypt_passwords(home,  subdir,  tmpdir,  dryrun):
    start = os.path.join(home,  subdir)
    logging.info("tmpdir %s",  tmpdir)
    out = os.path.join(tmpdir,  subdir)
    mkdir(path=out,  dryrun=dryrun)
    for root,  dirs,  files in os.walk(start):
        target = os.path.join(out, os.path.relpath(root,  start=start))
        logging.info("root %s start %s -> current %s",  root,  start,  target)
        skip = set()
        for index,  name in enumerate(dirs):
            if name == '.git':
                skip.add(index)
            else:
                ndir = os.path.join(target,  name)
                mkdir(path=ndir,  dryrun=dryrun)
        for index in skip:
            del dirs[index]
        for name in files:
            suffix = '.gpg'
            if name.endswith(suffix):
                encrypted = os.path.join(root,  name)
                cleartext = os.path.join(target,  name[:-len(suffix)] + '.txt')
                command = ['gpg', '--decrypt',  '--output',  cleartext,   '--quiet',  encrypted]
                logging.debug("running: %s",  command)
                subprocess.check_call(args=command)
    return out
    
def download_email():
    pass

def main():
    parser = argparse.ArgumentParser(description="do full backup",  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.set_defaults(loglevel='info')
    parser.set_defaults(dryrun=False)
    parser.add_argument("-v", "--verbose", dest='loglevel', action="store_const", const='debug', help="debug loglevel")
    parser.add_argument("-n", "--dryrun", action="store_true", help="dryrun")
    parser.add_argument("--luks", action="store_true", help="setup luks")
 #   parser.add_argument("--width", type=int, help="width")
    parser.add_argument("--passwords", default="/tmp/passwords", help="directory of passwords")
    parser.add_argument("--usb", default="/dev/disk/by-id/usb-_USB_DISK_3.2_6198CC39-0:0-part1", help="USB device")
    parser.add_argument("--root_device", default="/dev/disk/by-diskseq/1-part6", help="USB device")
    parser.add_argument("--label", default="backup-2023", help="luks label")
    parser.add_argument("--home", default=os.path.expanduser('~') ,  help="root directory")
    parser.add_argument('--mkfs_options', default=['-all-root',  '-root-mode',  '-keep-as-directory',  '-no-recovery',  '-no-strip', '-root-mode',  '0700'],  help='options to mksquashfs')
    parser.add_argument('--script_directory', default=os.path.dirname(sys.argv[0]),  help='directory of scripts')
    parser.add_argument('--scripts', default=['ring',  'calendar.py'],  help='scripts to run')
    parser.add_argument('--mount_point', default='/mnt',  help='where to mount')
    parser.add_argument('--password_store', default='.password-store',  help='directory of passwords')
    parser.add_argument('--extras',  default=['archive'],  help='extra directories to backup')

    parser.add_argument('directories', nargs='*', default=['Syncthing/stuart',  'photos',  'Books'],  help='directories to backup')
    options = parser.parse_args()

    numeric_level = getattr(logging, options.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        sys.exit('Invalid log level: %s' % options.loglevel)
    logging.basicConfig(level=numeric_level)

    mapped =  os.path.join('/dev/mapper',  options.label)
    if options.luks:
        luks(passwords=options.passwords,  usb=options.usb, label=options.label,  root_device=options.root_device)
    else:
        caches = run_scripts(scripts=options.scripts, home=options.home, directory=options.script_directory)
        tmpdir = tempfile.mkdtemp(prefix='full-backup')
        try:
            passwds = decrypt_passwords(home=options.home,  subdir=options.password_store, tmpdir=tmpdir,  dryrun=options.dryrun)
            backup(directories=caches + options.directories + [passwds],  device=mapped,  home=options.home,
                mount_point=options.mount_point, label=options.label,  dryrun=options.dryrun,
                mkfs_options=options.mkfs_options)
        finally:
            shutil.rmtree(tmpdir)
    return 0

if __name__ == "__main__":
    sys.exit(main())
