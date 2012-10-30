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
	
#create a new user and fill in their data here...
bot = Bot('auth+live+ea962b5a84c83d9c5334308f6574f7c6db01f930', '4fa9b6d6eb35c114b7000071', '4f94d6d1eb35c17511000418')

def checkIt(data):
	print "--checkit--", data['userid']
	if data['text'] == '3up':
		doit()
	elif data['text'] =='3down':
		dothat()
	elif data['text'] == '3vu':
		voteUp()
	elif data['text'] == '3vd':
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
