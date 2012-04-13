#!/usr/bin/python
# -*- coding: utf-8 -*-
# now_playing.py, show the currently playing song in a X11 Window
# Copyright (C) 2012 Stuart Pook
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.  This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.  You should have received a copy of the GNU General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.

# http://dbus.freedesktop.org/doc/dbus-python/doc/tutorial.html
# http://www.documentroot.net/en/linux/python-dbus-tutorial
# http://developer.pidgin.im/wiki/DbusHowto
# https://www.ibm.com/developerworks/linux/library/l-dbus/index.html
# http://www.riverbankcomputing.com/pipermail/pyqt/2008-March/018811.html
# http://www.zetcode.com/tutorials/pyqt4/widgets/

import sys, datetime
import dbus
# import python-qt4-dbus
import dbus.mainloop.qt
import subprocess

from PyQt4 import QtGui, QtCore

class Example(QtGui.QWidget):
	
	def __init__(self, bus):
		super(Example, self).__init__()
		self.bus = bus
		self.screen_on = False
		
		self.initUI()
		
	def mktext(self, text, font, vbox):
		t = QtGui.QLabel (text, self)
		t.setFont(font)
		t.setWordWrap(True)
		vbox.addWidget(t)
		return t
		
	def initUI(self):
		font = QtGui.QFont();
		vbox = QtGui.QGridLayout()
		
#		pal = self.palette();
#		pal.setColor(self.backgroundRole(), QtCore.Color.blue);
#		self.setPalette(pal);

		self.setStyleSheet("QWidget { background-color: black;  color: white}")  
		
		font.setPointSize(17);
		
		vbox.setSpacing(26)
		self.setLayout(vbox)

		self.line1 = self.mktext("Hello World!", font, vbox)
		self.line2 = self.mktext("This is a rather long second line", font, vbox)
		self.line3 = self.mktext("This is a rather long third line", font, vbox)
		self.line4 = self.mktext("This is a rather long fourth line", font, vbox)

		self.setGeometry(300, 600, 250, 150)
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
		try:
			itime = int(metadata.get("time", "bad"))
		except ValueError:
			stime = ""
		else:
			stime = datetime.time(itime / (60 * 60), itime / 60 %60, itime % 60).strftime('%H:%M:%S')
		bitrate = metadata.get("audio-bitrate", None)
		info = stime
		if bitrate:
			info += " %d kb/s" % bitrate
		self.show_text(self.get(metadata, "artist"), self.get(metadata, "title"), self.get(metadata, "album"), info)
	
	def track_change(self, metadata):
		print "track_change", metadata
		self.track(metadata)
		
	def status_change(self, status):
		print "status_change", str(status)
		if len(status) < 1:
			self.show_text("", "amarok", "empty status")
		elif status[0] == 0:
			if not self.screen_on:
				subprocess.check_call(["xset", "dpms", "force", "on"])
				self.screen_on = True
#			amarok = self.bus.get_object('org.mpris.amarok', '/Player')
#			metadata = amarok.GetMetadata()
#			self.track(metadata)
		else:
			if self.screen_on:
				subprocess.check_call(["xset", "dpms", "force", "off"])
				self.screen_on = False
			self.show_text("", "not playing", "")

#		self.line1.setText(kargs[2])
		
	def my_func(self, account, sender, message, conversation, flags):
		print sender, "said:", message
		self.line1.setText(sender)
		self.line2.setText(message)
		self.line3.setText(str(account) + " " + str(conversation) + " " + str(flags))
		
	def signal_print(self, *all):
		print "signal_print", all

	def changeTitle(self, state):
		if state == QtCore.Qt.Checked:
			self.setWindowTitle('QtGui.QCheckBox')
		else:
			self.setWindowTitle('')
		
def main():
	app = QtGui.QApplication(sys.argv)
	dbus_loop = dbus.mainloop.qt.DBusQtMainLoop(set_as_default=True)
	bus = dbus.SessionBus(mainloop=dbus_loop)
	ex = Example(bus)
#	bus.add_signal_receiver(ex.my_func , dbus_interface="im.pidgin.purple.PurpleInterface",signal_name="ReceivedImMsg")
# http://xmms2.org/wiki/MPRIS#The_signals
	bus.add_signal_receiver(ex.status_change, dbus_interface="org.freedesktop.MediaPlayer", signal_name="StatusChange")
	bus.add_signal_receiver(ex.track_change, dbus_interface="org.freedesktop.MediaPlayer",signal_name="TrackChange" )
	sys.exit(app.exec_())

if __name__ == '__main__':
	main()
