#!/usr/bin/python
# -*- coding: utf-8 -*-
# now_playing.py, show the currently playing song in a X11 Window
# Copyright (C) 2012 Stuart Pook
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.  You should have received a copy of the GNU General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Written for Amarok 2.5 & VLC 2 which implement MPRIS 2.1

# http://www.mpris.org/2.1/spec/

# http://dbus.freedesktop.org/doc/dbus-python/doc/tutorial.html
# http://www.documentroot.net/en/linux/python-dbus-tutorial
# http://developer.pidgin.im/wiki/DbusHowto
# https://www.ibm.com/developerworks/linux/library/l-dbus/index.html
# http://www.riverbankcomputing.com/pipermail/pyqt/2008-March/018811.html
# http://www.zetcode.com/tutorials/pyqt4/widgets/

import sys, datetime, time, os, socket
import dbus
# import python-qt4-dbus
import dbus.mainloop.qt
import subprocess

from PyQt4 import QtGui, QtCore

def timestamp():
	return time.strftime("%H:%M:%S")
	
def seconds_to_string(s):
	try:
		itime = int(s)
	except ValueError:
		stime = ""
	else:
		if itime > 0:
			stime = datetime.time(itime / (60 * 60), itime / 60 % 60, itime % 60).strftime('%H:%M:%S')
		else:
			stime = ""
	return stime
	
def dpms(display, status):
	if status:
		c = "on"
	else:
		c = "off"
	subprocess.check_call(["xset", "-display", display, "dpms", "force", c])

class Example(QtGui.QWidget):
	
	def __init__(self, bus, display):
		super(Example, self).__init__()
		self.bus = bus
		self.screen_on = False
		self.display = display
		
		self.initUI()
		
	def switch_on(self):
		if not self.screen_on:
			dpms(self.display, 1)
			self.screen_on = True
		
	def switch_off(self):
		if self.screen_on:
			dpms(self.display, 0)
			self.screen_on = False
		
	def mktext(self, text, font, vbox):
		t = QtGui.QLabel (text, self)
		t.setFont(font)
		t.setWordWrap(True)
		vbox.addWidget(t)
		return t
		
	def initUI(self):
		font = QtGui.QFont();
		vbox = QtGui.QVBoxLayout()
		vbox.setContentsMargins(0, 0, 0, 0);
		vbox.setSpacing(0);

#		pal = self.palette();
#		pal.setColor(self.backgroundRole(), QtCore.Color.blue);
#		self.setPalette(pal);

		self.setStyleSheet("QWidget { background-color: black;  color: white}")  
		
		font.setPointSize(19);
		self.setLayout(vbox)

		inter_stretch = 10
		vbox.addStretch(3);
		self.line1 = self.mktext("Hello World!", font, vbox)
		vbox.addStretch(inter_stretch);
		self.line2 = self.mktext("This is a rather long second line", font, vbox)
		vbox.addStretch(inter_stretch);
		self.line3 = self.mktext("This is a rather long third line", font, vbox)
		vbox.addStretch(inter_stretch);
		font.setPointSize(14);
		self.line4 = self.mktext("This is a rather long fourth line", font, vbox)
		vbox.addStretch(0);

		self.setWindowTitle('Now Playing')
		self.showFullScreen();
		self.show()
		
	def get(self, dict, key):
		return  dict.get(key, key + " not in metadata")
		
	def show_text(self, l1, l2, l3, l4 = ""):
		self.line1.setText(l1)
		self.line2.setText(l2)
		self.line3.setText(l3)
		self.line4.setText(l4)
		
	def track(self, metadata):
		self.switch_on()
		try:
			itime = int(metadata.get("time", "bad"))
		except ValueError:
			stime = ""
		else:
			stime = datetime.time(itime / (60 * 60), itime / 60 % 60, itime % 60).strftime('%H:%M:%S')
		bitrate = metadata.get("audio-bitrate", None)
		info = stime
		if bitrate:
			info += ", %d kb/s" % bitrate
		track_number = metadata.get("tracknumber", None)
		if track_number:
			info += ", track %d" % track_number
			
		title = metadata.get("title", None)
		if not title:
			title = metadata.get("xesam:title", "")
		self.show_text(metadata.get("artist", ""), title, metadata.get("album", ""), info)
	
	def track_change(self, metadata):
		print timestamp(), "track_change", metadata.get("title", str(len(metadata)))
		self.track(metadata)
		
	def status_change(self, status):
		print timestamp(), "status_change", str(status)
		if len(status) < 1:
			self.show_text("", "amarok", "empty status")
		elif status[0] == 0:
			if not self.screen_on:
				dpms(self.display, 1)
				self.screen_on = True
#			amarok = self.bus.get_object('org.mpris.amarok', '/Player')
#			metadata = amarok.GetMetadata()
#			self.track(metadata)
		else:
			if self.screen_on:
				dpms(self.display, 0)
				self.screen_on = False
			self.show_text("", "not playing", "")

#		self.line1.setText(kargs[2])
		
	def my_func(self, account, sender, message, conversation, flags):
		print timestamp(), sender, "said:", message
		self.line1.setText(sender)
		self.line2.setText(message)
		self.line3.setText(str(account) + " " + str(conversation) + " " + str(flags))
		
	def signal_print(self, *all):
		print timestamp(), "signal_print", all

	def properties_changed(self, who, dict, signature):
		print timestamp(), "properties_changed", who, dict
		for i in dict:
			print "     ", i, dict[i]
		metadata = dict.get('Metadata', None)
		if metadata:
			for i in metadata:
				print "           ", i, metadata[i]
			title = metadata.get("xesam:title", "")
			xartist = metadata.get("xesam:artist", "")
			if isinstance(xartist, dbus.Array):
				artist = str(xartist[0])
			else:
				artist = str(xartist)
			album = metadata.get("xesam:album", "")
			time = seconds_to_string(metadata.get("mpris:length", 0) / 1000000)
			track =  metadata.get("xesam:trackNumber", None)
			info = time
			if track:
				info += " track %d" % track
			self.show_text(artist, title, album, info)
			
		status = dict.get('PlaybackStatus', None)
		if status == 'Stopped' or status == 'Paused':
			self.switch_off()
		elif status == 'Playing':
			self.switch_on()

	def changeTitle(self, state):
		if state == QtCore.Qt.Checked:
			self.setWindowTitle('QtGui.QCheckBox')
		else:
			self.setWindowTitle('')
			
def get_my_address_for_connection(machine):
	s = socket.create_connection((machine, "ssh"))
	a = str(s.getsockname()[0])
	s.close()
	return a
	
def main():
	machine = sys.argv[1]
	print timestamp(), "initialising", machine
	my_address = get_my_address_for_connection(machine)
	subprocess.check_call(["ssh", "-nax", machine, "env", "DISPLAY=:0", "xhost", my_address])
	display = machine + ":0"
	subprocess.check_call(["xrandr",  "-display", display, "--orientation", "right"])
	print timestamp(), "initialising Qt on", display, "from", my_address
	extraargs = sys.argv + ["-display", display]
	os.environ["DISPLAY"] = display # I don't know why this is necessary
	app = QtGui.QApplication(extraargs)
	dbus_loop = dbus.mainloop.qt.DBusQtMainLoop(set_as_default=True)
	bus = dbus.SessionBus(mainloop=dbus_loop)
	ex = Example(bus, display)
#	bus.add_signal_receiver(ex.my_func , dbus_interface="im.pidgin.purple.PurpleInterface",signal_name="ReceivedImMsg")
# http://xmms2.org/wiki/MPRIS#The_signals
#	bus.add_signal_receiver(ex.status_change, dbus_interface="org.freedesktop.MediaPlayer", signal_name="StatusChange")
#	bus.add_signal_receiver(ex.track_change, dbus_interface="org.freedesktop.MediaPlayer",signal_name="TrackChange" )
	bus.add_signal_receiver(ex.properties_changed, dbus_interface="org.freedesktop.DBus.Properties",signal_name="PropertiesChanged" )
	print timestamp(), "starting"
	sys.exit(app.exec_())

if __name__ == '__main__':
	main()
