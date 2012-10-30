"""Pleasurebot v0.4
by:pleasuretek based around the python ttapi by alainGilbert.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
 You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>."""

import sys
import re
import MySQLdb as mdb
from datetime import datetime as dt
from collections import deque
import random
from ttapi import Bot
from settings import DBHOST,DBUSER,DBPASS

#
#Global variables
#
DEBUG = True
respondTo = ""  #nested callbacks were not returning what I wanted, so set a tmp userid to address teh return to instead

class pleasureBot:
	def __init__(self):
		dbName = None
		auth   = None
	
		#get database name from command line and connect to db
	
		if (len(sys.argv) > 1):
			dbName = sys.argv[1]
		else :
			print "there was not a database name passed as arg."
			sys.exit(1)
		try:
			self.con = mdb.connect(DBHOST, DBUSER, DBPASS, dbName)

		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
			sys.exit(1)
		with self.con:
			cur = self.con.cursor()
			cur.execute("SELECT b.auth, b.userid, b.roomid, s.cmddelim FROM BotInfo b, Settings s")
			res = cur.fetchone()
			auth     = res[0]
			self.userid   = res[1]
			self.roomid   = res[2]
			self.CMDDELIM = res[3]
			cur.close()
			self.bot = Bot(auth, self.userid, self.roomid)
			if (DEBUG): print "turntable login:", auth, self.userid, self.roomid
		#keep track of shitty things going on
		self.usersList = {}    #keep a dictionary of current users  { userid : username }
		self.currentDj = {}    #keep a dictionary of current DJ ids and play count  { djid : playcount }
		self.djq = ('',)     #keep a tuple of people waiting to DJ
		self.qenforced = False  # a bool for is the djq enforced or not
		self.currentSongdbId = 0   #keep playid (primary key) of current playing song  song id can be grabbed with from bot
		
		self.plCount = 0
		self.userBootCount   = {}

		if (DEBUG): self.bot.debug = True     #sets debug flag on Bot object
		self.bot.on('speak', self.speak)
		self.bot.on('pmmed', self.pm)
		self.bot.on('roomChanged', self.roomChanged)    #user joined or left the room. log that to RoomUsers table
		self.bot.on('registered', self.registered)
		self.bot.on('deregistered', self.deregistered)
		self.bot.on('newsong', self.songStarted)
		self.bot.on('endsong', self.songEnded)
		self.bot.on('snagged', self.songSnagged)      
		#bot.on('updateVotes', updateVotes)
		self.bot.on('booted_user', self.booted)
		#bot.on('update_user', doShit)
		self.bot.on('new_moderator', self.newMod)
		self.bot.on('rem_moderator', self.remMod)
		self.bot.on('add_dj', self.djSteppedUp)    #dj stepped up to decks check if the queue is enforced and if so then is he supposed to dj.. if not remove him and ask the correct person to dj
		self.bot.on('rem_dj', self.djSteppedDown)   #keep currentDj in sync

		self.bot.start()


	#	
	#SECTION
	#START EVENTS FIRED BY TTAPI  -aka event handlers but not officially...
	#
	#

	def speak(self, data):
		"""something was said in chat... log everything and respond to commands depending on role of associated userid """
		timestamp = dt.now().strftime('%Y-%m-%d %H:%M:%S')

		if (DEBUG):
			print data
			print data['text'][0]   #print char at command delimiter
			print data['text'][1:]
	
		#if data['text'] begins with '/' it is a command
		#TODO: get len of CMDDELIM and see if the first X chars of data['text'] match the delim. not just first char, but can be multiple..
		dlmlen = len(self.CMDDELIM)
		if data['text'][:dlmlen] == self.CMDDELIM :
			text = data['text'][1:]
			self.checkCommands(data, "speak")
		try:
			cur = self.con.cursor()
			cur.execute("INSERT INTO ChatLog (userid, chat, time) VALUES(%s, %s , %s)", (data['userid'], data['text'], timestamp))
			self.con.commit()
			cur.close()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
			self.con.rollback()


	def pm(self, data):
		"""bot was pm'ed """
		if(DEBUG): print data
		timestamp = dt.now().strftime('%Y-%m-%d %H:%M:%S')
		#if data['text'] begins with '/' it is a command
		#remove the '/' and check for matches
		if data['text'][0] == self.CMDDELIM :
			text = data['text'][1:]
			self.checkCommands(data, "pm")    #NOTE: might need self.
		try:
			cur = self.con.cursor()
			cur.execute("INSERT INTO PmLog (senderid, message, time) VALUES(%s, %s , %s)", (data['senderid'], data['text'], timestamp))
			self.con.commit()
			cur.close()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
			self.con.rollback()

	def roomChanged(self, data):
		"""placeholder for roomChanged event, currently empty function"""
		#if (DEBUG):
		#	print "roomChanged : ", data

	def registered(self, data):
		""" user joined room, check blacklist and add them to userList """
		if DEBUG: print "---------------registered----- :", data['user'][0]['name'] #, q
		#insert or update RoomUsers table with new user
		user = data['user'][0]
		if not self.usersList.has_key(user['userid']):
			if DEBUG: print "---adding to usersList---"
			self.usersList[user['userid']] = user['name']
		else:
			#TODO: this gets called sometimes... double check the remove from usersList methods
			if DEBUG: print "user is already in the userslist... sync issue"
			
		ts = dt.now().strftime('%Y-%m-%d %H:%M:%S')
		if DEBUG: print ts
		try:
			cur = self.con.cursor()
			cur.execute("SELECT * FROM RoomUsers WHERE userid = %s", user['userid'])
			if (cur.rowcount == 0):
				cur.execute("INSERT INTO RoomUsers (userid, username, lastlogon, role) VALUES (%s, %s, %s, '0')", (user['userid'], user['name'], ts))
			elif (cur.rowcount == 1):
				#UPDATE user name and login to match the bot if so update that data
				cur.execute("UPDATE RoomUsers SET username = %s, lastlogon = %s WHERE userid = %s", ( user['name'], ts, user['userid']))
			self.con.commit()
		except mdb.Error,e:
			print "Error %d: %s" % (e.args[0], e.args [1])
			self.con.rollback()
		if DEBUG: print "---synced RoomUsers, see who it is now---"
		if user['userid'] != self.userid:  #user registered is a user (not the bot)
			#check if user is in blacklist and if so then give them the boot
			self.checkBlacklist(user['userid'])
			#check date and pull proper greeting
			cur.execute("SELECT greeting FROM Greetings WHERE datef LIKE CURDATE()")
			if cur.rowcount == 0 :   #nothing for today, pull up default greeting
				cur.execute("SELECT greeting FROM Greetings WHERE datef = '1983-08-11'")   #the magic date is 1983-08-11 for default greeting
			greet = cur.fetchone()
			self.bot.pm(greet[0], user['userid'])
			self.getRoomInfo(user['userid'])
		else:   #bot logged on so don't do as much
			#TODO:implement name changing stuff here (bot user name (did bot logoff and human logged on to change some account settings then bot came back?)
			if DEBUG : print "----- registered the bot, updtade room info-------------"
			self.getRoomInfo(self.setState)

		

	def deregistered(data):
		""" user left the room, remove them from theUsersList """
		user = data['user'][0]
	
		ts = dt.now().strftime('%Y-%m-%d %H:%M:%S')
		if DEBUG: print "deregistered :" , user
		try:
			cur = self.con.cursor()
			cur.execute("UPDATE RoomUsers SET lastlogoff = %s WHERE userid = %s", (ts, user['userid']))
			self.con.commit()
		except mdb.Error,e:
			print "Error %d: %s" % (e.args[0], e.args [1])
			self.con.rollback()
		self.usersList.remove(user['userid'])
		for dj in self.djq:
			if dj == user['userid']: #if user just left room check if user was on djq and if so, remove them from it
				tmpq = self.djq
				indx = tmpq.index(user['userid'])
				if indx == 0: #remove first user from tuple
					for boom in tmpq :
						if not boom == tmpq[indx]:
							if boom == tmpq[1]:
								self.djq = boom,
							else:
								self.djq += boom,
				else :   #remove from middle of tuple
					i = 0
					for boom in tmpq:
						if not boom == tmpq[indx] and i == 0:
							self.djq = boom,
						elif not boom == tmpq[indx] : #not the user to remove from list
							self.djq += boom,
						i += 1
				

		if DEBUG: print "userslist: " , self.usersList
	
	


	def songStarted(self, data):
		""" the newsong event was fired, do stuff to the new song..."""
		if DEBUG : print "---sStarted----", data['room']['metadata']['current_song']
		if self.checkSongBan(data['room']['metadata']['current_song']['_id']) :
			self.bot.speak("%s that song has been banned." % data['room']['metadata']['djid'])
			self.bot.stopSong()
		else :		
			try:
				cur = self.con.cursor()
				cur.execute("INSERT INTO SongList (songid, artist, song, djid, starttime) VALUES (%s, %s, %s, %s, %s)", (data['room']['metadata']['current_song']['_id'], data['room']['metadata']['current_song']['metadata']['artist'], data['room']['metadata']['current_song']['metadata']['song'], data['room']['metadata']['current_song']['djid'], data['room']['metadata']['current_song']['starttime']))
				self.currentSongdbId = cur.lastrowid
				self.con.commit()
				cur.close()
			except mdb.Error, e:
				print "Error %d: %s" % (e.args[0], e.args [1])
				self.con.rollback()


	def songEnded(self, data):
		""" a song just ended, update its stats, and test the parameters to see if bot should play that song.."""

		if DEBUG : print "---sEnded----", data['room']['metadata']['current_dj']
		djid = data['room']['metadata']['current_dj']
	
		if DEBUG: print "songEnded data:"#, data['room']['metadata']['current_song'] #wow that is alot of info this returns if uncommented
		try:
			cur = self.con.cursor()
			cur.execute("UPDATE SongList SET upvotes = %s, downvotes = %s, listeners = %s WHERE playid = %s", (data['room']['metadata']['upvotes'], data['room']['metadata']['downvotes'], data['room']['metadata']['listeners'], self.currentSongdbId))
			self.con.commit()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args[1])
			self.con.rollback()
		self.isItGoodEnough(data['room']['metadata']['current_song']['_id'])
	
		self.currentDj[djid] +=1 #increment the count of how many tracks dj has played since been on decks
		#TODO: make role > 'xXx' where xXx == set from database
		try:
			cur.execute("SELECT userid FROM RoomUsers WHERE role > '0' AND userid = %s", djid)
		except mdb.Error,e:
			print  "Error %d: %s" % (e.args[0], e.args[1])
	
		if cur.rowcount == 0: #role is 0 so enforce playlimit
			self.checkDjSongLimit(djid)
		try:
			cur.close()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args[1])


	def songSnagged(self, data):
		""" a user just snagged the current playing song """
		if DEBUG : print "---songSnagged--"
		if not self.userid == data['userid']:
			try:
				cur = self.con.cursor()
				cur.execute("SELECT songid FROM SongList WHERE playid = %s", self.currentSongdbId)
				res = cur.fetchone()
				songID = res[0]
				cur.execute("INSERT INTO SNAGLOG (songid, userid) VALUES (%s, %s)", (songID, data['userid']))
				self.con.commit()
				cur.close()
			except mdb.Error, e:
				print "Error %d: %s" % (e.args[0], e.args [1])
				self.con.rollback()


	def booted(self, data):
		""" user was just booted from the room by a mod, add them to ban list """
		if DEBUG : print "-----BOOTED--------- : ", data
		#TODO: configure from web interface, 1st time warning boot (make warninglist), 2nd time ban or instaban on boot... make it hyperconfigurable thru admin interface..
		ts = dt.now().strftime('%Y-%m-%d %H:%M:%S')
		try:
			cur = self.con.cursor()
			cur.execute("INSERT INTO BanList (userid, time, reason, modid) VALUES (%s, %s, %s, %s)", (data['userid'], ts, data['reason'], data['modid']))
			self.con.commit()
			cur.close()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
			self.con.rollback()


	def djSteppedUp(self, data):
		"""dj just got up on decks... check if user is next in queue, if not escort him offstage->tell him hist spot number or add user to queue"""
		if DEBUG: print "--check the DJ yo-- count:", len(self.currentDj), data['user'][0]['userid']
		if not self.userid == data['user'][0]['userid']:  #if the user that stepped up is not the bot 
			if self.qenforced :		
				if data['user'][0]['userid'] in self.djq:
					if data['user'][0]['userid'] == self.djq[0]:  #userid is the next in line in the djq
						self.currentDj[data['user'][0]['userid']] = 0
						if DEBUG: print "---was first in line..abt to del from djq --"
						tmpq = self.djq
						if len(tmpq) == 1:
							self.djq = '',
						else :
							for boom in tmpq:
								if not boom == tmpq[0]:
									if boom == tmpq[1]:   #then clear djq and put second in line as first in line of new tuple
										self.djq = boom,
									else :      #refill the djq
										self.djq += boom,
					else : #user is not next in line to DJ...
						pos     = 0
						linePos = None
						for boom in self.djq:
							if boom == data['user'][0]['userid']:
								linePos = pos
							pos += 1
						pmStr = "You are %s in line to DJ currently" % linePos
						self.bot.pm(pmStr, data['user'][0]['userid'])
						if DEBUG: print "is now in q removing ", data['user'][0]['userid'], " from decks"
						self.escort(data['user'][0]['userid'])
				else :  #user is not in djq...
					pmStr = "You were not in line to DJ, There are %s DJs in front of you in line" % len(self.djq)		
					self.bot.pm(pmStr,data['user'][0]['userid'])
					if self.djq[0] == '':
						self.djq = data['user'][0]['userid'],
					else:
						self.djq += data['user'][0]['userid'],
				
					remStr = data['user'][0]['userid']
					if DEBUG: print "not in q. removing -", remStr , "- from decks"
					self.escort(data['user'][0]['userid'])
			else:    #djq is not enforced
				self.currentDj[data['user'][0]['userid']] = 0  #main thing is this - add the user and blank count to currentDj{}
				#check if we need to start enforcing the djq - never or always should have been setup during program start
				cur = self.con.cursor()
				cur.execute("SELECT qenforcement FROM Settings")
				res = cur.fetchone()
				if res[0] == 1 : #enforce djq if decks are full
					if len(self.currentDj) == 5 :
						self.qenforced = True
					else:
						self.qenforced = False
				elif res[0] == 2:  #tricky stuff.. 
					cur.execute("SELECT qcrowdvariable FROM Settings")
					crowded = cur.fetchone()
					if len(self.usersList) >= crowded[0] or len(self.currentDj) == 5:
						self.qenforced = True
					else:
						self.qenforced = False
				cur.close()
			if DEBUG : print "-- end stepup- length-", len(self.currentDj), "enforced:", str(self.qenforced)
			self.checkBotDj()
		else:
			self.currentDj[data['user'][0]['userid']] = 0
			if DEBUG: print "the bot is DJing bitch", self.currentDj

	def djSteppedDown(self, data):
		"""Dj stepped down from decks, update the currentDj dic"""
		#remove dj from currentDj dictionary
		if DEBUG: print "---stepped down -- count: ", len(self.currentDj), self.currentDj, "-----", data['user'][0]['userid']
		if self.currentDj.has_key(data['user'][0]['userid']):
			del self.currentDj[data['user'][0]['userid']]
		print " after removal ---" ,self.currentDj
		#check if there are DJs in the queue and notify the next dj in line to stepup..
		cur = self.con.cursor()
		cur.execute("SELECT qenforcement FROM Settings")
		res = cur.fetchone()
		if res[0] > 0: #the q is either low medium or high - might be enforced
			if res[0] == 1:  #enforce only when decks are full...
				if len(self.currentDj) == 4:
					if not self.djq[0] == '':
						self.qenforced = True
						self.bot.pm("Alright, the open deck is yours. Go Get It",self.djq[0])
					else:
						self.qenforced = False
			elif res[0] == 2: #enforce by settings
				cur.execute("SELECT qcrowdvariable FROM Settings")
				crowded = cur.fetchone()
				if len(self.usersList) >= crowded[0] or (len(self.currentDj) == 4 and len(self.djq) > 0):
					self.qenforced = True
					if len(self.djq) > 0:
						self.bot.pm("Alright, the open deck is yours. Go Get It",self.djq[0])
				else: #the room is not crowded, the decks are not full, and the djq is empty
					self.qenforced = False
			elif res[0] == 3: #enforce always
				if len(self.djq) > 0:
					self.bot.pm("Alright, the open deck is yours. Go Get It",self.djq[0])
		if DEBUG: print "--end stepped down - enforced-", str(self.qenforced)
		self.checkBotDj()


	def newMod(self, data):
		if DEBUG : print "--new mod--", data
		self.checkModRole(data['userid'],True)

	def remMod(self, data):
		if DEBUG: print "--rem mod--", data
		self.doModRem(data['userid'])

	#----------------------------------------------------------
	#
	#SECTION
	#actions and callbacks...
	# actions and args to action commands (callbacks (functions passed as params to other functions to execute))
	#
	#----------------------------------------------------------

	def setState(self, data):
		""" (only runs when bot logs on) sets the current room moderators (checks role assigned in RoomUsers(correct (promote) role if needed)), room users, and current DJ deck status"""
		if DEBUG : print "---------setState---------"#,data['room']['metadata']
		self.currentDj = {}  #clear out list of DJs is easier than checking if the list contains an index for the id of DJ 
		self.usersList = {}  #same thing as line above
		cur = self.con.cursor()
		#dj stuff
		for dj in data['room']['metadata']['djs'] :
			self.currentDj[dj] = 1
		if DEBUG: print self.currentDj
		#user stuff
	
		for u in data['users'] :
			curId = u['userid']
			if self.checkBlacklist(u['userid']):
				self.usersList[curId] = u['name']
	
		subsql = "', '".join(['%s'] * len(self.usersList)) % tuple(self.usersList.keys())
		if DEBUG: print "--subsql-- ", subsql
		try:
			cur.execute("SELECT userid FROM RoomUsers WHERE userid IN (%s)", subsql)
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		if DEBUG : print cur.rowcount
		if cur.rowcount < len(self.usersList):
			if DEBUG: print " we have a new user.."
			rows = cur.fetchall()
			pastUserList = []
			for row in rows:
				pastUserList.append(row[0])
		
			usersToRegister = set(self.usersList.keys()) -  set(pastUserList)
			ts = dt.now().strftime('%Y-%m-%d %H:%M:%S')
			usersToRegister = list(usersToRegister)
			if DEBUG: print usersToRegister
			for dood in usersToRegister:
				try:
					#TODO: following SQL might be broken in self.usersList[dood] -dubeg thit shat
					cur.execute("INSERT INTO RoomUsers (userid, username, lastlogon, role) VALUES (%s, %s, %s, '0') ", (dood, self.usersList[dood], ts ))
				except mdb.Error, e:
					print "Error %d: %s" % (e.args[0], e.args [1])
		

		#moderator stuff
		if DEBUG : print "--moderators--", data['room']['metadata']['moderator_id']
		for modId in data['room']['metadata']['moderator_id'] :
			self.checkModRole(modId,True)
		#current song stuff
		if DEBUG : print "--song stuff--", len(data['room']['metadata']), data['room']['metadata']
		if data['room']['metadata']['current_dj'] == 'None' or len(data['room']['metadata']) > 20:
			cur.execute("SELECT playid, songid FROM SongList WHERE songid = %s AND starttime = %s", (data['room']['metadata']['current_song']['_id'], data['room']['metadata']['current_song']['starttime']))
			if DEBUG : print cur.rowcount
			if cur.rowcount == 0: 
				try:
					cur.execute("INSERT INTO SongList (songid, artist, song, djid, starttime) VALUES (%s, %s, %s, %s, %s)", (data['room']['metadata']['current_song']['_id'], data['room']['metadata']['current_song']['metadata']['artist'], data['room']['metadata']['current_song']['metadata']['song'], data['room']['metadata']['current_song']['djid'], data['room']['metadata']['current_song']['starttime']))
					self.currentSongdbId = cur.lastrowid
					self.con.commit()
				except mdb.Error, e:
					print "Error %d: %s" % (e.args[0], e.args [1])
					self.con.rollback()
			else :
				res = cur.fetchone()
				self.currentSongdbId = res[0]
		#djq setup
		if DEBUG: print "----djq-----"
		try:
			cur.execute("SELECT qenforcement FROM Settings")
			res = cur.fetchone()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		if DEBUG: print res[0]
		if res[0] == 0:   #q is off
			self.qenforced = False
		elif res[0] == 1:     #q is low
			if len(self.currentDj) == 5:
				self.qenforced = True
			else:
				self.qenforced = False
		elif res[0] == 2:     #q is medium
			cur.execute("SELECT qcrowdvariable FROM Settings")
			crowded = cur.fetchone()
			if len(self.usersList) >= crowded[0]:
				self.qenforced = True
			elif len(self.currentDj) == 5:
				self.qenforced = True
			else:
				self.qenforced = False
		elif res[0] == 3:     #q is high
			self.qenforced = True
		self.checkBotDj()
		self.countPList()
		try:
			cur.close()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])

	def printInfo(self, data):
		"""debugging function to print callback response to terminal"""
		print  "-----print info -----", data

	def getRoomInfo(self, *args):
		"""get the room info, usefull when entering room first time."""
		global respondTo
		if DEBUG: print "---getRoomInfo----", type(args[0])
		uid = ""
		callback=None
		if len(args) == 1:
			if callable(args[0]):
				if DEBUG : print "---getRoomInfo got callback---"
				callback = args[0]
				self.bot.roomInfo(False, callback)
			elif isinstance(args[0], unicode):
				if DEBUG : print "---getRoomInfo got uid---"
				uid = args[0]
				respondTo = uid
				self.bot.roomInfo(False, self.printRoomInfo)
		elif len(args) ==2:
			if DEBUG : print "---getRoomInfo got both---"
			uid = args[0]
			callback = args[1]
			self.bot.roomInfo(False, callback)
			respondTo = uid  #just in case a function that needs a userID and this info

	def printRoomInfo(self, data):  #need to get user from before callback is fired
		"""pm the room info to the user who requested it"""
		global respondTo
		if DEBUG: print "----room info to add to pm---", data
		#current number of users in room
		#count of djs in queue if its enabled
		#link to rules page
		cur = self.con.cursor()
		cur.execute("SELECT rulesurl FROM BotInfo")
		res = cur.fetchone()
		pmStr = "-="
		pmStr += data['room']['name']
		pmStr += "=- Please read the rules at "
		pmStr += res[0]
		pmStr += " . "
		pmStr += data['room']['description']
		pmStr += " "
		pmStr += self.CMDDELIM
		pmStr += "commands for a list of commands "
		pmStr += self.CMDDELIM
		pmStr += "help for help "
		self.bot.pm(pmStr,respondTo)
		respondTo = ""
		cur.close()


	def getPList(self, data):
		"""request bots playlist"""
		global respondTo
		#parse data from tags and print the important bits..
		playStr = ""
		count = 0
		thelist = data['list']
		if DEBUG : print "-----getPLlist -----"#,data['list']
		for theSong in data['list']:
			thisStr = "-="
			thisStr += str(count)
			thisStr += "="
			thisStr += "--Song: "
			thisStr += theSong['metadata']['song']
			thisStr += " --Artist: "
			thisStr += theSong['metadata']['artist']
			print thisStr
			playStr += thisStr
			count +=1
		if DEBUG : print "roar", respondTo #, playStr
		self.bot.pm(playStr,respondTo)
		respondTo = ""

	def printPList(self, uid):
		"""print the bots playlist to the user who requested it"""
		global respondTo
		respondTo = uid #this global var will be read by requestPlaylist()
		if DEBUG: print "--printPList--", respondTo
		self.bot.playlistAll(self.getPList)

	def getPListCount(self, data):
		if DEBUG: print "--plist count --", len(data['list'])
		self.plCount = len(data['list']) - 1

	def countPList(self):
		"""return a count of songs in playlist"""
		self.bot.playlistAll(self.getPListCount)

	#---------------------------------------------------------------------
	#
	#SECTION
	#Program Functions...
	#
	#---------------------------------------------------------------------
	def checkCommands(self, data, avenue):
		""" stuff was entered with a command delimiter... see if cmd exists and user has access, fire as needed 
			The only permanent command is 'help' which only responds to PMs and lists the commands that user has access to"""
		cmd = data['text'][len(self.CMDDELIM):]   #remove cmd delimiter
		uid = None
		#check userid role
		if avenue == 'speak':
			uid = data['userid']
		elif avenue == 'pm':
			uid =  data['senderid']
		try:
			cur = self.con.cursor()
			cur.execute("SELECT role FROM RoomUsers WHERE userid = %s", uid)
			res = cur.fetchone()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		if res[0] !=None :
			role = res[0]
		if (DEBUG):print "role  ", role
		#load results for command table where role of userid is >= role of command
		try:
			cur.execute("SELECT id, cmd FROM Commands WHERE role <= %s AND ((avenue = %s) OR (avenue = 'both')) ", (role, avenue))
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		rows = cur.fetchall()
		for row in rows:
			if (DEBUG):print row[0], row[1]
			if cmd == row[1]:
				#it is an actual command, it is ok to load methods now..
				try:			
					cur.execute("SELECT method, target, parameter FROM Commands WHERE id = %s ", row[0])
					mthdrow = cur.fetchone()
				except mdb.Error, e:
					print "Error %d: %s" % (e.args[0], e.args [1])
				if (DEBUG): print mthdrow[0],mthdrow[1], mthdrow[2]
				methodToCall = None
				if mthdrow[1] == 'self':
					methodToCall = getattr(self, mthdrow[0])
				elif mthdrow[1] == 'bot':
					tmpBotMem = self.bot
					methodToCall = getattr(tmpBotMem, mthdrow[0])
				
				if not mthdrow[2] == '' and not mthdrow[2] == 'Null' :
					if mthdrow[2] == 'uid':
						if DEBUG: print "-about to send uid"
						methodToCall(uid)
					elif mthdrow[2] == 'uid,rows': #for print commands
						if DEBUG: print "-about to send uid,rows"
						methodToCall(uid, rows)
					elif mthdrow[2] == 'uid,pm' : #for pm a new PM window specific
						if DEBUG: print "-about to send uid,pm"
						fuuaaagggghhh = "hey"
						methodToCall(fuuaaagggghhh,uid)
					#if you need more paramaters to catch ie.callbacks write those in here...
					else : #has param but not defined -usually a message
						if DEBUG: print "-about to send crap-"
						methodToCall(mthdrow[2])
				else:
					if DEBUG: print "-about to send empty-"
					methodToCall()
		cur.close()
		if DEBUG : print "Leaving checkCommands()"

	def checkBlacklist(self, uid):
		"""check if user is in the blacklist and if so do the appropriate action """
		#TODO: change blacklist check to pull interval based on 1-how many times been banned (recently) 2- variable length of ban from database(webapp config)
		cur = self.con.cursor()
		if DEBUG: print "-----checkBL----"
		try:
			#make the above mentioned TODO on the line below
			cur.execute("SELECT date_add((SELECT time FROM BanList WHERE userid =%s), INTERVAL 1 DAY), reason FROM BanList WHERE userid = %s", (uid,uid))
			retval = True
			if cur.rowcount != 0 :
				rows = cur.fetchall()
				for row in rows:
					oktime = row[0]
					if oktime < timestamp:
						self.bot.bootUser(uid, row[1])
						retval = False
				if retval :
					welcomeBack = "Welcome back %s Please review the rules of this room"
					self.bot.pm(welcomeBack, uid)
			cur.close()
		except mdb.Error,e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		if DEBUG: print retval
		return retval

	def isItGoodEnough(self, songid):
		""" check if the song is good enough for bot to add it to bot playlist """
		""" logic: calculate up to down ratio against how many listeners... for each time song was played and last time song was played (most recent time has more weight than previous plays). if song is over 65% upvotes AND under 10% downs"""
		totalup     = 0
		totaldown   = 0
		totallisten = 0
		if DEBUG: print "is It Good Enough()? : " , songid
		try:
			cur = self.con.cursor()
			cur.execute("SELECT upvotes, downvotes, listeners, starttime FROM SongList WHERE songid = %s ORDER BY starttime LIMIT 3", (songid))
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		rows = cur.fetchall()
		isFirst = 0
		if DEBUG: print cur.rowcount
		for row in rows:
			if DEBUG : print "---ups, downs, listeners---", row[0], row[1], row[2]
			if not row[0] == None:
				totalup     += int(row[0])
				totaldown   += int(row[1])
				totallisten += int(row[2])
		
				if isFirst == 0:	#make the most recent play count 50% and the 2 before that count as 25% each for simplicity sake... can complicate further later when basic bot is finished
					totalup     += int(row[0])
					totaldown   += int(row[1])
					totallisten += int(row[2])
				isFirst += 1
			#come back to this here... go do the ban list first, then manage playlist, then manage DJs..
		up2listen = float(totalup) / float(totallisten)
		up2listen -=  float(totaldown) /  float(totallisten)  #subtract the haters from the up2listen crowd
		#TODO:debug this section of code in depth.. 
		cur.execute("SELECT addtoplaylistthresh, addtosongbanthresh FROM Settings")
		thresh = cur.fetchone()  #threshold value is in thresh[0]
		upthresh = 0.0
		upthresh += float(thresh[0]) / 100.0
		downthresh = 0.0
		downthresh += float(thresh[1]) / 100.0
		if DEBUG: print "--iiGE values---", up2listen, totalup, totaldown, totallisten, upthresh, downthresh, songid
	
		if up2listen > upthresh: 
			self.addToPlaylist(songid)
		elif up2listen > downthresh:
			self.banSong(songid)
		cur.close()

	def banSong(self, songid):
		try:
			cur = self.con.cursor()
			cur.execute("INSERT INTO SongBan (songid) VALUES (%s)", songid)
			self.con.commit()	
			cur.close()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
			self.con.rollback()

	def checkSongBan(self, songid):
		try:
			cur = self.con.cursor()
			cur.execute("SELECT songid FROM SongBan WHERE songid = %s", songid)
			if not cur.rowcount == 0:
				return True
			else:
				return False
			cur.close()
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])

	def checkModRole(self, *args):
		"""check that each mod has at least a role of mod or higher in RoomUsers table"""
		"""modId is the id of the moderator to be checked, doUpdate is a bool, true and it will update teh users privledges, false, and it only checks"""
		modId = ""
		doUpdate = False
		if len(args) == 1:
			modId = args[0]
		elif len(args) == 2:
			modId    = args[0]
			doUpdate = args[1]
		try:
			cur = self.con.cursor()
			cur.execute("SELECT userid FROM RoomUsers WHERE role <= '2' AND userid =%s", modId )
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		if not cur.rowcount == 0:   #if we got a result then we need to escalate the users privledges at least to moderator
			if doUpdate :
				try:
					cur.execute("UPDATE RoomUsers SET role = '2' WHERE userid = %s", modId )
					self.con.commit()
				except mdb.Error, e:
					print "Error %d: %s" % (e.args[0], e.args[1])
					self.con.rollback()
			cur.close()
			return True
		else : #ID in question is not a mod
			cur.close()
			return False	

	def doModRem(self, uid):
		try:
			cur = self.con.cursor()
			cur.execute("SELECT userid FROM RoomUsers WHERE role = '2' AND userid = %s", uid)
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0], e.args [1])
		if not cur.rowcount == 0:
			try:
				cur.execute("UPDATE RoomUsers SET role = '0' WHERE userid = %s", uid)
				self.con.commit()
				cur.close()
			except mdb.Error, e:
				print "Error %d: %s" % (e.args[0], e.args[1])
				self.con.rollback()

	def checkSpin(self, uid):
		"""manage dj queue"""
		#TODO: check for is user is DJing alread and if user is already on the djqueue...
		cur = self.con.cursor()
		cur.execute("SELECT (SELECT qenforcement FROM Settings), username  FROM RoomUsers WHERE userid = %s", uid)
		res = cur.fetchone()
		if res[0] == 0:  #enforcement is off
			self.bot.speak("the decks are open, or fastest finger to get up on the decks when one opens up")
		elif res[0] == 1:  #enforcemnet is low - only enforce when full
			if len(self.currentDj) == 5: #only enforce when decks are full
				if self.djq[0] == '':
					self.djq = uid,
				else :
					self.djq += uid,
				self.qenforced = True
				pmStr = "%s is %sst in line to DJ" % (res[1], len(self.djq))
				self.bot.pm(pmStr, uid)
			else :
				self.qenforced = False
				self.bot.pm("The decks are open to grab a spot",uid)
		elif res[0] == 2:  #enforcemnet is medium - variable by config
			cur.execute("SELECT listeners, (SELECT qcrowdvariable FROM Settings) FROM SongList ORDER BY starttime DESC LIMIT 1")
			lc = cur.fetchone()
			if (len(self.currentDj) == 5) or (lc[0]>=lc[1]):
				self.qenforced = True
				self.djq += uid,
				pmStr = "%s is %sst in line to DJ"  % (res[1], len(self.djq))
				self.bot.pm(pmStr,uid)
			else:
				self.qenforced = False
				self.bot.pm("grab an open deck", uid)
		elif res[0] == 3:  #enforcement is high - always on
			self.djq += uid,
			if (len(self.djq) == 1) and (len(self.currentDj) < 5):  #there is an open deck currently
				self.bot.pm("grab an open deck", uid)
			else :
				pmStr = "%s is %sst in line to DJ" % (res[1], len(self.djq))
				self.bot.pm(pmStr, uid)
		cur.close()

	def checkBotDj(self):
		"""check if the bot should get up and dj"""
		if DEBUG: print "----checkBotDj----", len(self.currentDj)
		cur = self.con.cursor()
		cur.execute("SELECT djlowthresh, djhighthresh FROM Settings")
		thresh = cur.fetchone()
		if (thresh[0] -1) >= len(self.currentDj):
			if not self.currentDj.has_key(self.userid):
				if DEBUG: print "--bot is not a dj-", thresh[0]-1 , "is GTorEQ than ", len(self.currentDj)
				self.bot.addDj()
				#currentDj[userid] = 0
		if self.currentDj.has_key(self.userid):
			if DEBUG: print "---bot is already djing, about to test if remove---"
			if len(self.currentDj) > thresh[1]:  #if there are more than X djs have the bot step down
				self.bot.remDj()
				if DEBUG: print "--bot is stepping down because-",len(self.currentDj), " is greater than ",thresh[1]
				#del currentDj[userid] # should be handled like every other dj stepping down

	def checkDjSongLimit(self, uid):
		"""check to see if bot needs to escort a DJ offstage after playing amount of songs"""
		if not uid == self.userid:
			try:
				cur = self.con.cursor()
				cur.execute("SELECT djplaylimit FROM Settings")
				res = cur.fetchone()
			except mdb.Error, e:
				print "Error %d: %s" % (e.args[0], e.args [1])
			if not res[0] == 0 :  #0 is unlimited play for all
				if DEBUG: print "--check song limit--", self.currentDj[uid], " >= ", res[0]
				if self.currentDj[uid] >= res[0] :
					#TODO: set a timer to give them a few seconds before you escort them
					pmStr = "That was an awesome set, you have played your limit of songs, Plese step down and give other DJ's a chance to play"
					self.bot.pm(pmStr,uid)
					self.bot.remDj(uid)
					cur.execute("SELECT username FROM RoomUsers WHERE userid == %s", uid)
					name = cur.fetchone()
					self.bot.speak("Give it up for %s, That was an awesome DJ set" % name[0])
			try:
				cur.close()
			except mdb.Error, e:
				print "Error %d: %s" % (e.args[0], e.args [1])

	def addToPlaylist(self, songId = None):
		if DEBUG: print "--adding to playlist-- at-", self.plCount
		if songId == None:
			cur = self.con.cursor()
			cur.execute("SELECT songid FROM SongList WHERE playid = %s", self.currentSongdbId)
			if not cur.rowcount == 0 :
				res = cur.fetchone()
				if DEBUG: print "nothing passed", res[0]
				self.bot.playlistAdd(str(res[0]) ,int(self.plCount))
				self.plCount += self.plCount
			cur.close()
		else:
			if DEBUG: "passed songId-", songId
			self.bot.playlistAdd(str(songId), int(self.plCount))

	def escort(self, uid):
		if DEBUG: print "--escort -", uid
		remStr = str(uid)
		self.bot.remDj(remStr)

#------------------------------------------------
#
#COMMAND handlers
#
#------------------------------------------------

	def printCommands(self, uid, rows):
		cmdTxt = ""
		for row in rows:
			cmdTxt += self.CMDDELIM
			cmdTxt += row[1]
			cmdTxt += ",  "
		self.bot.pm(cmdTxt, uid)

	def printHelp(self, uid):
		"""print help for bot, like how many songs can dj play before asked to step down, how the q is enforced, and how to execute commands"""
		if DEBUG: print "------printHelp-----"
		cur = self.con.cursor()
		cur.execute("SELECT djplaylimit, stepdowntime, qenforcement, cmddelim FROM Settings")
		res = cur.fetchone()
		helpTxt = "When you get on the decks you can play "
		helpTxt += str(res[0])
		helpTxt += " songs before you need to step down for "
		helpTxt += str(res[1])
		helpTxt += " songs.  "
		if DEBUG: print "------printHelp-----"
		if res[2] == 0: #qenforcement is off
			helpTxt += "The DJ Queue is not being enforced, fastest finger gets the spot. "
		elif res[2] == 1: #qenforcement is low
			helpTxt += "The DJ Queue is enforced if the decks are full. "
		elif res[2] == 2: #qenforcement is med
			cur.execute("SELECT qcrowdvariable FROM Settings")
			crowd = cur.fetchone()
			helpTxt += "The DJ Queue is enforced is the decks are full or if the room is crowded (with %s people in the room). " % crowd[0]
		elif res[2] == 3: #qenforcement is high
			helpTxt += "The DJ Queue is always enforced, You must ask before you can DJ. "
		helpTxt += "type "
		helpTxt += str(res[3])
		helpTxt += "commands  for a list of commands you can use."
		cur.close()   #clean up cursor
		if DEBUG: print "------printHelp-----"
		self.bot.pm(helpTxt, uid)

	def printDjq(self, uid):
		"""print the dj queue to pm the user the requested it"""
		cur = self.con.cursor()
		cnt = 1
		pmStr = ""
		if DEBUG: print "--about to print djlist--- to:", uid, "----", self.djq
		for dj in self.djq:
			if dj == '':
				pmStr = "The Dj Queue is empty"
			else :
				cur.execute("SELECT username FROM RoomUsers WHERE userid = %s", dj)
				if not cur.rowcount == 0:
					res = cur.fetchone()
					if DEBUG: print "--name--", res[0]
					tmpStr = str(cnt)
					tmpStr += "-"
					tmpStr += res[0]
					tmpStr += "  ; "
					if DEBUG: print tmpStr
					pmStr += tmpStr
					cnt += 1
					if DEBUG: print pmStr
		if DEBUG: print "--the dj list --" , pmStr
		self.bot.pm(pmStr , uid)

	def rollin(self, uid):
		"""prng roll x and set limits from database"""
		#dummy implement currently : need to pull a random number with limits pulled from database. then form responce from database
		cur = self.con.cursor()
		#cache user name
		cur.execute("SELECT username FROM RoomUsers WHERE userid = %s", uid)
		r = cur.fetchone()
		name = r[0]
		cur.execute("SELECT rollwhat, low, high FROM Rollin")
		res = cur.fetchone()
		number = random.randint(res[1],res[2])
		stuffToSay = ""
		if DEBUG : print "--- roll number ------", number
		if res[0] == 'dice':
			stuffToSay = "%s rolled a %s" % (name, number)
		else :
			stuffToSay = "%s rolled %s %s" % (name, number, res[0]) #'username' 'rolled' 'six' rollwhat
		self.bot.speak(stuffToSay)
		cur.close()

	def stagedive(self, uid):
		"""if there is an open deck or user is already djing have user do a stagedive"""
		if DEBUG: print "---stagedive---", uid, type(uid)
		if self.currentDj.has_key(uid):
			print "its in there somewhere..."
			cur = self.con.cursor()
			cur.execute("SELECT username FROM RoomUsers WHERE userid = %s", uid)
			res = cur.fetchone()
			diveline = "%s just did a stagedive... The crowd gets hyped and loves it" % res[0]
			print diveline
			self.bot.speak(diveline)
			self.bot.vote("up")
			self.bot.remDj(str(uid))
			cur.close()

	def shufflePList(self):
		"""shuffles the bots playlist"""
		i = 0
		filled = []
		number = 0
		cutOn = self.plCount / 2
		while i < cutOn:
			if i == 0: number = random.randint(cutOn, self.plCount)
			while number in filled:
				if DEBUG: print "--num in fill--", number, filled
				number = random.randint(cutOn, self.plCount)
			filled.append(number)
			self.bot.playlistReorder(i,number)
			if DEBUG: print "----unique ----", i, " to ", number, " cut the deck on ", cutOn
			i += 1

	def topDjs(self, uid):
		"""print top djs from last 24hrs and all time"""
		if DEBUG: print "------in top djs--------"
		cur = self.con.cursor()
		cur.execute("SELECT r.username, count(s.upvotes) FROM SongList s LEFT JOIN RoomUsers r ON (s.djid = r.userid) GROUP BY s.djid ORDER BY count(s.upvotes) DESC LIMIT 5")
		res = cur.fetchall()
		pmStr = 'Top DJs : '
		count = 1
		for result in res:
			pmStr += str(count)
			pmStr += ") "
			if DEBUG: print result[1]
			pmStr += result[0]
			pmStr += " "
			pmStr += str(result[1])
			pmStr += "; "
			count += 1
		if DEBUG: print pmStr
		self.bot.pm(pmStr, uid)
		cur.close()

	def djSongCount(self, uid):
		"""show the count of current DJs"""
		cur = self.con.cursor()
		pmStr = ""
		if DEBUG: print "------djSongCount-------"
		for dj in self.currentDj:
			cur.execute("SELECT username FROM RoomUsers WHERE userid = %s",dj)
			res = cur.fetchone()
			pmStr += res[0]
			pmStr += " - "
			pmStr += str(self.currentDj[dj])
			pmStr += "; "
		self.bot.pm(pmStr,uid)

#------------------------------------------------
#
#instantiate and launch bot 
#
#------------------------------------------------

pb = pleasureBot()    #instantiate this whole thung
