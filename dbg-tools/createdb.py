#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#initdb.py
#python script to setup database for use with yattbot.py 
#needs database named passed as parameter
#example usage:  'python initdb.py bbotTestdb'  bbotTestdb is the name of the db to be created
#the mysql admin account should already be created (run initdb.py once before you start running this script to setup databases)
#to fill the new database with dummy data run "mysql -u yattbotAdmin -p DATABASENAME < docs/dummydata.sql "

import MySQLdb
import sys


#db info
#TODO: will be updated to new host (new all info in this section...)
dbAdmin = 'yattbotAdmin'
dbApass = 'yattbotSuperSecret'
dbUser  = 'yattbot'
dbPass  = 'yattbotSecret'
dbHost  = 'localhost'

if (len(sys.argv) > 1):
	dbName = sys.argv[1]
else :
	print "there was not a database name passed as arg."
	sys.exit(1)	

try:
	con = MySQLdb.connect(dbHost, dbAdmin, dbApass)

except MySQLdb.Error, e:
	print "Error %d: %s" % (e.args[0], e.args [1])
	sys.exit(1)

with con:
	try:
		cur = con.cursor()
		st = 'CREATE DATABASE '
		st += dbName
		print st
		cur.execute(st)

		st = "GRANT SELECT, INSERT, UPDATE ON "
		st += dbName
		st += ".* TO '"
		st += dbUser
		st += "'@'localhost' IDENTIFIED BY '"
		st += dbPass
		st += "'"
		print st

		cur.execute(st)
		st = 'USE '
		st += dbName
		cur.execute(st)

		#create the tables needed
		#BOTINFO
		cur.execute("CREATE TABLE IF NOT EXISTS BotInfo (auth VARCHAR(255) PRIMARY KEY NOT NULL, userid VARCHAR(255) NOT NULL, roomid VARCHAR(255) NOT NULL, botname VARCHAR(255) NOT NULL, rulesurl VARCHAR(128))")
		#Settings
		cur.execute("CREATE TABLE IF NOT EXISTS Settings (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, addtoplaylistthresh REAL, addtosongbanthresh REAL, cmddelim VARCHAR(128) NOT NULL, djplaylimit INT, stepdowntime INT, qenforcement INT, qcrowdvariable INT, djlowthresh INT, djhighthresh INT)")
		#ROOMUSERS
		cur.execute("CREATE TABLE IF NOT EXISTS RoomUsers (userid VARCHAR(255) PRIMARY KEY NOT NULL, username VARCHAR(255) NOT NULL, lastlogon DATETIME, lastlogoff DATETIME, role INT(2))")
		#COMMANDS
		cur.execute("CREATE TABLE IF NOT EXISTS Commands (id INT(11) PRIMARY KEY AUTO_INCREMENT NOT NULL, cmd VARCHAR(128) NOT NULL, method VARCHAR(255) NOT NULL, role INT(2) NOT NULL, avenue VARCHAR(64) NOT NULL, target VARCHAR(128) NOT NULL, parameter VARCHAR(255))")
		#CHATLOG
		cur.execute("CREATE TABLE IF NOT EXISTS ChatLog (id INT(11) PRIMARY KEY AUTO_INCREMENT NOT NULL, userid VARCHAR(255) NOT NULL, chat VARCHAR(255) NOT NULL, time DATETIME NOT NULL)")
		#PMLOG
		cur.execute("CREATE TABLE IF NOT EXISTS PmLog (id INT(11) PRIMARY KEY AUTO_INCREMENT NOT NULL, senderid VARCHAR(255) NOT NULL, message VARCHAR(255) NOT NULL, time DATETIME NOT NULL)")
		#BANLIST
		cur.execute("CREATE TABLE IF NOT EXISTS BanList (banid INT(11) PRIMARY KEY AUTO_INCREMENT NOT NULL, userID VARCHAR(255) NOT NULL, time DATETIME NOT NULL, reason VARCHAR(255))")
		#SONGLIST
		cur.execute("CREATE TABLE IF NOT EXISTS SongList (playid INT(11) PRIMARY KEY AUTO_INCREMENT NOT NULL, songid VARCHAR(255) NOT NULL, artist VARCHAR(255), song VARCHAR(255), djid VARCHAR(255), upvotes INT(8), downvotes INT(8), listeners INT(8), starttime VARCHAR(127))")
		#SONGBAN
		cur.execute("CREATE TABLE IF NOT EXISTS SongBan (banid INT AUTO_INCREMENT PRIMARY KEY NOT NULL, songid VARCHAR(127))")
		#GREETINGS
		#NOTE the default greeting is set by a specific date of 08-11-1983
		cur.execute("CREATE TABLE IF NOT EXISTS Greetings (greetid INT PRIMARY KEY AUTO_INCREMENT NOT NULL, greeting VARCHAR(255) NOT NULL, datef DATE)")
		#rollin
		cur.execute("CREATE TABLE IF NOT EXISTS Rollin (rollid INT PRIMARY KEY AUTO_INCREMENT NOT NULL, rollwhat VARCHAR(255) NOT NULL, low INT NOT NULL, high INT NOT NULL)")		
		
		#INSERT into tables default data set
		cur.execute("INSERT INTO BotInfo (auth, userid, roomid, botname, rulesurl) VALUES ('auth+live+583320f7e5a458eb161c2a88930556307fd544e7', '4f316824a3f75176aa014dfc', '4f94d6d1eb35c17511000418', 'Cascadia Bot', 'www.github.com')")

		cur.execute ("INSERT INTO Settings (addtoplaylistthresh, addtosongbanthresh, cmddelim, djplaylimit, stepdowntime, qenforcement, qcrowdvariable, djlowthresh, djhighthresh) VALUES ('23', '-50', '/', '2', '2', '1', '10', '4', '4')")

		cur.execute("INSERT INTO Commands (cmd, method, role, avenue, target, parameter) VALUES ('hello', 'speak','0','both', 'bot', 'hello'), ('pm me', 'pm','0','speak', 'bot', 'uid,pm'), ('roll', 'rollin', '0', 'speak','self', 'uid'), ('up','addDj', '3', 'both', 'bot', ''), ('down','remDj', '3', 'both', 'bot', ''), ('snag','snag', '3', 'both', 'bot', ''), ('skip', 'stopSong', '3', 'both', 'bot', ''), ('bop','vote', '2', 'both', 'bot', ''), ('playlist','printPList', '0', 'both', 'self', 'uid'), ('info','getRoomInfo', '0', 'both', 'self', 'uid'), ('can I spin', 'checkSpin', '0', 'both', 'self', 'uid'), ('djlist', 'printDjq', '0', 'both', 'self', 'uid'), ('stats', 'printStats', '0', 'both', 'self', 'uid'), ('help', 'printHelp', '0', 'both', 'self', 'uid'), ('commands', 'printCommands', '0', 'both', 'self', 'uid,rows'), ('dive', 'stagedive', '0', 'both', 'self', 'uid'), ('shuffle', 'shufflePList', '2', 'both', 'self', ''), ('topdj', 'topDjs', '0', 'both', 'self', 'uid'), ('count', 'djSongCount', '0', 'both', 'self', 'uid')")
		cur.execute("INSERT INTO Rollin (rollwhat, low, high) VALUES ('dice','1','12')")
		cur.execute("INSERT INTO Greetings (datef, greeting) VALUES ('1983-08-11', 'Welcome to the room, this is the standard greeting'), ('2012-01-02', 'Happy New Year'), ('2012-01-01', 'Happy New Year'), ('2012-01-16', 'Happy Martin Luther King, Jr. Day'), ('2012-02-20', 'Happy President''s Day'), ('2012-05-28', 'Happy Memorial Day'), ('2012-07-04', 'Happy Independence Day'), ('2012-09-03', 'Happy Labor Day'), ('2012-10-08', 'Happy Columbus Day'), ('2012-11-11', 'Happy Veterans Day'), ('2012-11-22', 'Happy Thanksgiving'), ('2012-12-24', 'Merry Christmas'), ('2012-12-25', 'Merry Christmas'), ('2012-02-21', 'Happy Mardi Gras'), ('2012-02-02', 'Happy Groundhog Day'), ('2012-02-14', 'Happy Valentine''s Day'), ('2012-03-17', 'Happy St. Patrick''s Day'), ('2012-04-08', 'Happy Easter'), ('2012-04-22', 'Happy Earth Day'), ('2012-04-27', 'Happy Arbor Day'), ('2012-05-01', 'Happy May Day'), ('2012-05-05', 'Feliz Cinco de Mayo'), ('2012-05-13', 'Happy Mother''s Day'), ('2012-05-24', 'Happy Slavic National Holiday'), ('2012-06-14', 'Happy Flag Day'), ('2012-06-17', 'Happy Father''s Day'), ('2012-06-21', 'Happy Solstice'), ('2012-06-28', 'Happy Stonewall Day'), ('2012-08-26', 'Happy Women''s Equality Day'), ('2012-09-17', 'Happy Constitution Day'), ('2012-09-19', 'Ahoy'), ('2012-10-09', 'Happy Leif Erikson Day'), ('2012-10-31', 'Happy Halloween'), ('2012-11-06', 'Go vote'), ('2012-12-21', 'Happy Solstice and begining of yet another great cycle'), ('2012-01-23', 'Happy Chinese New Year'), ('2012-02-01', 'Happy National Freedom Day'), ('2012-03-08', 'Happy International Women''s Day'), ('2012-03-11', 'Happy 3/11 Day'), ('2012-03-20', 'Happy Vernal Equinox'), ('2012-03-21', 'Happy World Poetry Day'), ('2012-03-22', 'Happy World Water Day'), ('2012-03-23', 'Happy World Meteorological Day'), ('2012-03-25', 'Happy Maryland Day'), ('2012-04-12', 'Happy Human Space Flight Day'), ('2012-04-25', 'Happy Administrative Professionals Day'), ('2012-05-03', 'Happy World Press Freedom Day'), ('2012-05-14', 'Happy World Migratory Bird Day'), ('2012-05-22', 'Happy National Maritime Day'), ('2012-06-08', 'Happy World Oceans Day'), ('2012-07-22', 'Happy Parents'' Day'), ('2012-07-30', 'Happy World Friendship Day'), ('2012-08-12', 'Happy International Youth Day'), ('2012-09-22', 'Happy Autumnal Equinox'), ('2012-11-04', 'Set your clocks back'), ('2012-11-10', 'Happy World Science Day'), ('2012-11-20', 'Happy Universal Children''s Day'), ('2012-11-21', 'Happy World Television Day'), ('2012-12-09', 'Happy Hanukkah'), ('2012-12-10', 'Happy Holidays'), ('2012-12-11', 'Happy Holidays'), ('2012-12-12', 'Happy Holidays'), ('2012-12-13', 'Happy Holidays'), ('2012-12-14', 'Happy Monkey Day'), ('2012-12-15', 'Happy Holidays'), ('2012-12-16', 'Happy Holidays'), ('2012-12-17', 'Happy Holidays'), ('2012-12-18', 'Happy Holidays'), ('2012-12-19', 'Happy Holidays'), ('2012-12-20', 'Happy Holidays'), ('2012-12-22', 'Happy Holidays'), ('2012-12-23', 'Happy Festivus'), ('2012-12-26', 'Happy Holidays'), ('2012-12-27', 'Happy Holidays'), ('2012-12-28', 'Happy Holidays'), ('2012-12-29', 'Happy Holidays'), ('2012-12-30', 'Happy Holidays'), ('2012-12-31', 'Happy New Year'), ('2012-01-11', 'Happy World Laughter Day'), ('2012-01-28', 'Happy Data Privacy Day'), ('2012-03-09', 'Happy Middle Name Pride Day'), ('2012-03-14', 'Happy Pi Day'), ('2012-05-25', 'Happy Towel Day'), ('2012-05-26', 'Happy Paper Airplane Day'), ('2012-07-27', 'Happy System Administrator Appreciation Day'), ('2012-09-01', 'Happy Bacon Day'), ('2012-09-16', 'Happy Software Freedom Day'), ('2012-10-11', 'Happy National Coming Out Day'), ('2012-04-20', 'Happy 420!!! Go get stoned'), ('2012-06-25', 'Happy National Catfish Day'), ('2012-10-29', 'Happy National Cat Day'), ('2012-01-05', 'Happy National Bird Day'), ('2012-01-07', 'Happy Harlem Globetrotters Day')")

		#INSERT PERSONAL DEBUGGING STUFF -remove for production version
		rand = ")'( Randull"
		cur.execute("INSERT INTO RoomUsers (userid, username, role) VALUES ('4f91b93aeb35c175110001d2', 'pleasuretek', '4'), ('4f94e63deb35c17511000427', 'Roe Bbott', '3'), ('4ea8d05fa3f751271d024366', 'Fuzzy Bubblewrap', '3'), ('4e0367b4a3f751791e058631', 'TheKollection' , '3')")

		con.commit()
		cur.close()
	except MySQLdb.Error, e:
		con.rollback()
		print "Error %d: %s" %(e.args[0],e.args[1])
		sys.exit(1)

