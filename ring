#!/usr/bin/python3 -P
# -*- coding: utf-8 -*-
# ring Copyright (C) 2011-2014, 2017,2020  Stuart Pook (http://www.pook.it/)
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# with no options just look for a contact as given in the arguments

# show all the fred's in the contact list on your owncloud server
#	ring fred

# print a short list of important contacts formatted using groff
#	ring -p | lp

# print a longer list of important and medium contacts
#	ring -P | lp

# The printed output is formated for A4 paper.

import sys;
import os;
import re;
import unicodedata;
import locale
import requests
import tempfile
import vobject
import subprocess
import optparse
import errno
import time
import stat
import getpass
import logging
import hashlib

class MyError(Exception):
	pass

def format_number(number, options):
	if number.find('p') >= 0:
		p = re.compile('^.*p')
		number = p.sub('', number)

	if number.startswith('00'):
		number = '+' + number[2:]
	if number.startswith('0'):
		number = options.home_prefix + number[1:]
	if not options.international and number.startswith(options.home_prefix):
		number = '0' + number[len(options.home_prefix):]
		if options.dots:
			p = re.compile(r'(\d\d)')
			number = p.sub(r'\1.', number)
			number = number[0:-1]
	return number

def insert(set, value):
	n = len(set)
	set.add(value)
	return n != len(set)
	
def icase(s, t):
	return s.lower() == t.lower()

def format_contact(contact, troff, min_pager, options):
	if troff:
		or_mark = r" \(or "
	else:
		or_mark = " | "
	if troff:
		nbsp = r'\ '
	else:
		nbsp = ' '
	try:
		nv = contact.n.value
	except AttributeError as x:
		logging.debug("AttributeError looking for n.value %s", x)
		return ''
	name = ''
	for k in (nv.prefix, nv.given, nv.family, nv.suffix, nv.additional):
		if k != '' and name != '':
			name = name + " "
		name = name + k
	if troff:
		out = r'\fB' + name + r'\fP'
	else:
		out = name + ','

	pager = 0

	numbers = set()
	for number in contact.contents.get('tel', []):
		tag = ''
		for ntype in number.params.get('TYPE', []):
			if icase(ntype, 'CELL'):
				tag += 'm'
			elif icase(ntype,'HOME'):
				tag += 'h'
			elif icase(ntype, 'FAX'):
				tag += options.fax_tag
			elif icase(ntype, 'WORK'):
				tag += 'w'
			elif icase(ntype, 'PAGER'):
				pager = int(number.value)
				break
		else:
			formated_number = format_number(number.value, options)
			if insert(numbers, formated_number):
				out += ' '
				if tag:
					out += tag + nbsp
				out += formated_number
	if pager < min_pager:
		return ''

	for number in contact.contents.get('x-sip', []):
		formated_number = format_number(number.value.partition('@')[0], options)
		if insert(numbers, formated_number):
			out += ' s' + nbsp + formated_number

	for address in contact.contents.get('adr', []):
		tag = ''
		try:
			for atype in address.params['TYPE']:
				if icase(atype, 'HOME'):
					tag += 'h'
				elif icase(atype,'WORK'):
					tag += 'w'
		except KeyError:
			pass
		v = address.value
		for v in (v.box, v.extended, v.street, v.code, v.city, v.region, v.country):
			if len(v) > 0:
				if len(tag):
					out += ' ' + tag + nbsp
					tag = ''
				else:
					out += ', '
				for vv in v:
					out += vv

	done1 = False
	for what in ('title', 'role', 'note'):
		if what in contact.contents:
			for note in contact.contents[what]:
				if len(note.value):
					if done1:
						logging.debug("%s has more than 1 %s %s %d", nv, what,  out, note.value)
						out += or_mark
					else:
						out += ' ('
						done1 = True
					out += note.value.rstrip('\n').replace('\n', or_mark)
	if done1:
		out += ')'

	for email in contact.contents.get('email', []):
		if troff:
			out += ' ' + email.value.replace('@', '\\:@').replace('.', '\\:.')
		else:
			out += ' ' + email.value

	return out

def strip_accents(uc):
	if uc == '':
		return ''

	c = unicodedata.normalize('NFD', uc)
	d = ""
	for i in c:
		if unicodedata.combining(i) == 0:
			d += i
	return d

def eclose(evolution, errors, cmd):
	if evolution.wait() != 0:
		errors.seek(0)
		sys.stderr.writelines(errors)
		raise MyError("%s failed (%d)" % (cmd[0], evolution.returncode))

def matcher(line, expressions, what):
	#print("matching", what, "=", repr(s))
	s = strip_accents(line)
	for e in expressions:
		if e.search(s):
			return True
	return False


def match(contact, expressions):
#	print(contact)
	for k in ("org", "title",  "role"):
		for l in contact.contents.get(k, []):
			m = l.value
			if isinstance(l.value, list):
				for m in l.value:
					if matcher(m, expressions, k):
						return True
			else:
				if matcher(l.value, expressions, k):
					return True

	for k in ("n",):
		for l in contact.contents.get(k, []):
			#print("n 1= ", dir(l))
#			print "n a= ", l.prettyPrint()
			#print("n 2= ", `l.value`)
#			print "n 3= ", dir(l.value)
#			print "n 3 given = ", `l.value.given`
#			print "n5=", strip_accents(l.value.given)
#			print "n6=", strip_accents(l.value.family)
			if matcher(l.value.suffix, expressions, k + " suffix"):
				return True
			if matcher(l.value.additional, expressions, k + " additional"):
				return True
			if matcher(l.value.prefix, expressions, k + " prefix"):
				return True
			if matcher(l.value.given, expressions, k + " given"):
				return True
			if matcher(l.value.family, expressions, k + " family"):
				return True

	for k in ("fn", 'tel'):
		for l in contact.contents.get(k, []):
			if matcher(l.value, expressions, k):
				return True

	for number in contact.contents.get('x-sip', []):
		if matcher(number.value.partition('@')[0], expressions, "x-sip"):
			return True

	return False

def show_contacts(vcal, args, options):
	expressions = []
	for a in args:
		expressions.append(re.compile(strip_accents(a), re.IGNORECASE))
	for contact in vobject.readComponents(vcal):
		if (match(contact, expressions)):
#			print dir(contact), contact.n.value.__doc__, `contact.n.value.given`, dir(contact.n.value)
			#print(contact)
			print(format_contact(contact, False, 0, options))
#		express: for e in expressions:
#			for k in ("fn", "n", "org"):
#				if k in contact.contents:
#			for k in contact.contents:
#					print k, "is", contact.contents[k]
#					if e.search(strip_accents(contact.contents[k])):
#						print dir(contact)
#				for z in contact.getChildren():
#					print z
#					print format_contact(contact, False, 0).encode('utf-8')
#					break express
#	eclose(evolution, errors)

def build_url(options):
	url = options.url if options.url else options.server + '/' + options.user + "/" + options.addressbook + '/'
	logging.debug("url %s", url)
	return url

def get_credentials(options):
	logging.debug("reading credentials from %s", options.credentials)
	with open(options.credentials) as f:
		fields = f.readline().strip().split(':')
		user = fields[0]
		passwd = fields[1]
		logging.debug("credentials user=%s hash(passwd)=%s", user, hashlib.blake2b(passwd.encode(), digest_size=10).hexdigest())
		return (user, passwd)

def get_cache_file(options):

	if options.cache:
		try:
			old = open(options.cache, "r")
		except IOError as e:
			if e.errno != errno.ENOENT:
				raise e
			logging.debug("no cache %s", options.cache)
		else:
			stat_buf = os.fstat(old.fileno())
			age = time.time() -  stat_buf.st_mtime
			if age <= options.cache_lifetime:
				logging.debug("reusing cache %s (age %.2f s)", options.cache, age)
				return old
			old.close()
			mode = stat.S_IMODE(stat_buf.st_mode)
			logging.debug("cache %s too old (new mode %#o, age %.2f s)", options.cache, mode, age)

		tmp = options.cache + ".tmp"
		os.umask(0o77)
		contacts = open(tmp, "w+")
	else:
		contacts = tempfile.TemporaryFile('w+')
		tmp = None

	url = build_url(options)
	r = requests.get(url, auth=get_credentials(options))
	if r.status_code != 200:
		logging.fatal("download from %s failed with %d", url, r.status_code)
		sys.exit(7)

	contacts.write(r.text)
	contacts.seek(0)
	if tmp:
		os.rename(tmp, options.cache)
	return contacts

def format_contacts(cache, options, args):

	full = options.full_postscript or options.full

	if options.groff:
		output = sys.stdout
	else:
		output = tempfile.TemporaryFile("w+")
	mess = """.\\"
.af minutes 00
.kern
.fam HN
.nh
.na
.nr topmargin 1.5c
.po 0.7c
.ll 19.8c
.pl 29.7c
.sp \\n[topmargin]u
"""
	output.write(mess)

	if full:
		sz = 11
		if options.text_size:
			sz = options.text_size
		output.write('.ps %f\n' % sz)

		mess = """.\\"
.vs \\n[.s]+0.9
.de NP
'bp
'sp \\n[topmargin]u
..
.wh -0.8c NP
"""
	else:
		sz = 8.9
		if options.text_size:
			sz = options.text_size
		output.write('.ps %f\n' % sz)
		mess = """.\\"
.vs \\n[.s]+0.4
.ll 15c
.de NP
' bp
' sp \\n[topmargin]u
' po +4.4c
..
.wh 7.2c NP
"""
	output.write(mess)
	if options.utf8:
			output.write('.ll 26c\n')
			output.write('.po 0\n')
			output.write('.wh 7.2c\n')

	output.write(r'\n[hours]:\n[minutes] \n[dy]/\n[mo]/\n[year]' + '\n')
	if full:
		output.write('.sp 0.3\n')

	contacts = []
	for contact in vobject.readComponents(cache):
		line = format_contact(contact, True, 0 if options.full else (full and 1 or 2), options)
		if line:
			contacts.append(line)

	cache.close()

	contacts.sort(key=locale.strxfrm)

	for line in contacts:
		euro = u'\u20ac'
		line = line.replace(euro, r'\[eu]')
		output.write(line)
		output.write('\n')
		if full:
			output.write('.br\n')

	output.write('\n')

	if options.groff:
		return

	output.flush()
	output.seek(0)

	postscript = tempfile.TemporaryFile()
	child = os.fork()
	if child == 0:
		os.dup2(output.fileno(), 0)
		if options.print_list:
			os.dup2(postscript.fileno(), 1)
		cmd = ["groff", '-k']
		if options.utf8:
			cmd.extend(["-T", "utf8"])
		else:
			cmd.extend(["-P", "-pA4"])
		os.execvp(cmd[0], cmd)
	pid, status = os.waitpid(child, 0)
	if status:
		raise MyError('groff failed: %d' % status)

	if not options.print_list:
		return

	printer = "lp"

	turn_over = not "Duplex=Duplex" in subprocess.Popen(["lpoptions"], stdout=subprocess.PIPE).communicate()[0]

	postscript.seek(0)
	child = os.fork()
	if child == 0:
		os.dup2(postscript.fileno(), 0)
		if turn_over:
			os.execlp(printer, printer, "-P1")
		else:
			os.execlp(printer, printer)
	pid, status = os.waitpid(child, 0)
	if status:
		raise MyError('%s failed (%d)' % (printer, status))

	if turn_over:
		print("turn the paper over and hit return ", end="")
		sys.stdin.readline()

		postscript.seek(0)
		child = os.fork()
		if child == 0:
			os.dup2(postscript.fileno(), 0)
			os.execlp(printer, printer, "-P2")
		pid, status = os.waitpid(child, 0)
		if status:
			raise MyError('%s failed (%d)' % (printer, status))

def main():
	parser = optparse.OptionParser("%prog [options] pattern ...")
	parser.add_option("-C", "--cache_lifetime", metavar="seconds", type='float', default=60 * 60 * 24, help="cache life time [%default]")
	parser.add_option("-r", "--retrieve", "-n", "--oldcache", action="store_const", const=0, dest='cache_lifetime',
			help="consider cache is too old")
	parser.add_option("-q", "--usecache", "--quick", action="store_const", const=sys.maxsize, dest='cache_lifetime',
			help="consider cache is up todate")
	parser.add_option("-g", "--groff", action="store_true", help="produce groff output")
	parser.add_option("-p", "--short_postscript", action="store_true", help="produce PostScript list")
	parser.add_option("-P", "--full_postscript", action="store_true", help="produce full PostScript list")
	parser.add_option("-i", "--international", action="store_true", help="use international format for all numbers")
	parser.add_option("-f", "--full", action="store_true", help="produce full list")
	parser.add_option("-d", "--dots", action="store_true", help="add dots to numbers")
	parser.add_option("-u", "--utf8", action="store_true", help="produce a full UTF-8 list")
	parser.add_option("--dump", action="store_true", help="dump the raw contact list")
	parser.add_option("--print", dest="print_list", action="store_true", help="print")
	parser.add_option("--text_size", type='float', metavar="points", help="text size")
	parser.add_option("--user", default=getpass.getuser(), help="username on server")
	parser.add_option("--server", default="http://localhost:37358", help="url etesync server [%default]")
	parser.add_option("--url", default=None, help="full url to download [%default]")
	parser.add_option("--addressbook", default=os.environ['ETESYNC'], help="address name [%default]")
	parser.add_option("--fax_tag", default="f", help="tag for fax numbers [%default]")
	parser.add_option("--home_prefix", default="+33", help="home prefix [%default]")
	parser.add_option("--credentials", metavar="FILE",
			default=os.path.expanduser('~/.local/share/etesync-dav/htpaswd'), help="etesync credentials [%default]")
	parser.add_option("--cache", default=os.path.expanduser('~/.ring-cache'), metavar="FILE", help="file to cache contacts [%default]")
	parser.set_defaults(loglevel='warn')
	parser.add_option("-v", "--verbose", "--debug", dest='loglevel', action="store_const", const='debug', help="debug loglevel")
	parser.add_option("-l", "--loglevel", metavar="LEVEL", help="set logging level")
	parser.add_option("--cache_filename", action="store_true", help="update and return cache file")

	(options, args) = parser.parse_args()

	#locale.setlocale(locale.LC_COLLATE, 'fr_FR.iso885915@euro')
	locale.setlocale(locale.LC_ALL, '')
	locale.setlocale(locale.LC_COLLATE, 'fr_FR.UTF-8')

	numeric_level = getattr(logging, options.loglevel.upper(), None)
	if not isinstance(numeric_level, int):
		sys.exit('Invalid log level: %s' % options.loglevel)
	logging.basicConfig(level=numeric_level)

	with get_cache_file(options) as cache:
		if options.cache_filename:
		    print(options.cache)
		elif options.dump:
			for line in cache:
				print(line, end="")
		elif not options.short_postscript and not options.full_postscript and not options.utf8 and not options.groff:
			show_contacts(cache, args, options)
		else:
			format_contacts(cache, options, args)

if __name__ == "__main__":
	main()
