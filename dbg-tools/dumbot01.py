import sys
import re
import MySQLdb as mdb
from datetime import datetime as dt
from collections import deque
import random
from ttapi import Bot
#from settings import DBHOST,DBUSER,DBPASS

def init():
	global bot
	global con
	global roomid
	global adminid
	global userid
	dbName = None
	auth   = None
	
bot = Bot('auth+live+3ff1fdf4426da214708693e7fb9bd151ac7ff2e6', '4fa8283daaa5cd337c0000c9', '4f94d6d1eb35c17511000418')

def checkIt(data):
	print "--checkit--", data['userid']
	if data['text'] == '1up':
		doit()
	elif data['text'] =='1down':
		dothat()
	elif data['text'] == '1vu':
		voteUp()
	elif data['text'] == '1vd':
		voteDown()

def dothat():
	bot.remDj()

def doit():
	bot.addDj()

def voteUp():
	bot.vote()

def voteDown():
	bot.vote('down')

print "--init-- "
init()
bot.on('speak', checkIt)
bot.start()
