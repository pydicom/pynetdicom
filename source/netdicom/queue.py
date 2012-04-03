#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

from threading import Lock
import time
import DULparameters
class Empty(Exception):
	pass


class Queue(object):
	def __init__(self):
		self.__items = []
		self.__lock = Lock()
	def Flush(self):
		self.__items = []
	def IsEmpty(self):
		self.__lock.acquire()
		isempty = (self.__items == [])
		self.__lock.release()
		return isempty
	def get(self, Wait=False, Leave=False):
		if Wait:
			while 1:
				try:
					self.__lock.acquire()
					if not Leave:
						item = self.__items.pop()
					else:
						item = self.__items[-1]
					self.__lock.release()
					break
				except IndexError:
					self.__lock.release()
					pass
			return item
				
		else:
			try:
				self.__lock.acquire()
				if not Leave:
					item = self.__items.pop()
				else:
					item = self.__items[-1]
				self.__lock.release()
			except IndexError:
				self.__lock.release()
				raise Empty
			return item

	def put(self, item):
		self.__lock.acquire()
		self.__items.insert(0,item)
		self.__lock.release()

	def __repr__(self):
		return str(self.__items)
