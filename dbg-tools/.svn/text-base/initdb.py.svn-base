#!/usr/bin/env python
# -*- coding: UTF-8 -*-


import MySQLdb as mdb
import sys
import getpass

pass1 = getpass.getpass('what is the password for the MySQL root user?' )
host = raw_input ( 'what is the address for the MySQL database?' )

try:
	con=mdb.connect(host, 'root', pass1)
except mdb.Error, e:
	print "Error %d: %s" %(e.args[0],e.args[1])
	sys.exit(1)
with con:
	try:
		cur=con.cursor()
		cur.execute("GRANT ALL ON *.* TO 'yattbotAdmin'@'localhost' IDENTIFIED BY 'yattbotSuperSecret' WITH GRANT OPTION")
		cur.close()
		print 'Database admin user setup, you can start to createdb.py now'
		sys.exit(0)
	except mdb.Error, e:
		print "Error %d: %s" %(e.args[0],e.args[1])
		sys.exit(1)

