#! /usr/bin/env python
# vim: set sw=4 sts=4 ts=8 et:
#
# PyBorg IRC module
#
# Copyright (c) 2000, 2006 Tom Morton, Sebastien Dailly
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#

import sys, time
from threading import Timer

try:
    from ircbot import *
    from irclib import *
except:
    print "ERROR !!!!\nircbot.py and irclib.py not found, please install them\n(http://python-irclib.sourceforge.net/)"
    sys.exit(1)

#overide irclib function
def my_remove_connection(self, connection):
    # XXX: Why is this here?
    #self.connections.remove(connection)
    if self.fn_to_remove_socket:
        self.fn_to_remove_socket(connection._get_socket())

IRC._remove_connection = my_remove_connection

import os
import pyborg
import cfgfile
import random
import time
import traceback
import thread

def get_time():
    """
    Return time as a nice yummy string
    """
    return time.strftime("%H:%M:%S", time.localtime(time.time()))


class ModIRC(SingleServerIRCBot):
    """
    Module to interface IRC input and output with the PyBorg learn
    and reply modules.
    """
    # The bot recieves a standard message on join. The standard part
    # message is only used if the user doesn't have a part message.
    join_msg = "%s"# is here"
    part_msg = "%s"# has left"

    # For security the owner's host mask is stored
    # DON'T CHANGE THIS
    owner_mask = []


    # Command list for this module
    commandlist =   "IRC Module Commands:\n!chans, !ignore, \
!join, !nick, !part, !quit, !quitmsg, !jump, !reply2ignored, !replyrate, !shutup, \
!stealth, !unignore, !wakeup, !talk, !me, !owner"
    # Detailed command description dictionary
    commanddict = {
            "shutup": "Owner command. Usage: !shutup\nStop the bot talking",
            "wakeup": "Owner command. Usage: !wakeup\nAllow the bot to talk",
            "join": "Owner command. Usage: !join #chan1 [#chan2 [...]]\nJoin one or more channels",
            "part": "Owner command. Usage: !part #chan1 [#chan2 [...]]\nLeave one or more channels",
            "chans": "Owner command. Usage: !chans\nList channels currently on",
            "nick": "Owner command. Usage: !nick nickname\nChange nickname",
            "ignore": "Owner command. Usage: !ignore [nick1 [nick2 [...]]]\nIgnore one or more nicknames. Without arguments it lists ignored nicknames",
            "unignore": "Owner command. Usage: !unignore nick1 [nick2 [...]]\nUnignores one or more nicknames",
            "replyrate": "Owner command. Usage: !replyrate [rate%]\nSet rate of bot replies to rate%. Without arguments (not an owner-only command) shows the current reply rate",
            "reply2ignored": "Owner command. Usage: !reply2ignored [on|off]\nAllow/disallow replying to ignored users. Without arguments shows the current setting",
            "stealth": "Owner command. Usage: !stealth [on|off]\nTurn stealth mode on or off (disable non-owner commands and don't return CTCP VERSION). Without arguments shows the current setting",
            "quitmsg": "Owner command. Usage: !quitmsg [message]\nSet the quit message. Without arguments show the current quit message",
            "talk": "Owner command. Usage !talk nick message\nmake the bot send the sentence 'message' to 'nick'",
            "me": "Owner command. Usage !me nick message\nmake the bot send the sentence 'message' to 'nick'",
            "jump": "Owner command. Usage: !jump\nMake the bot reconnect to IRC",
            "quit": "Owner command. Usage: !quit\nMake the bot quit IRC",
            "owner": "Usage: !owner password\nAllow to become owner of the bot"
    }

    def __init__(self, my_pyborg, args):
        """
        Args will be sys.argv (command prompt arguments)
        """
        # PyBorg
        self.pyborg = my_pyborg
        # load settings

        self.settings = cfgfile.cfgset()
        self.settings.load("pyborg-irc.cfg",
                { "myname": ("The bot's nickname", "PyBorg"),
                  "realname": ("Reported 'real name'", "Pyborg"),
                  "localaddress": ("Local IP to bind to", ""),
                  "ipv6": ("Whether to use IPv6", 0),
                  "owners": ("Owner(s) nickname", [ "OwnerNick" ]),
                  "servers": ("IRC Server to connect to (server, port [,password])", [("irc.sucks.net", 6667)]),
                  "chans": ("Channels to auto-join", ["#cutie578"]),
                  "speaking": ("Allow the bot to talk on channels", 1),
                  "stealth": ("Hide the fact we are a bot", 0),
                  "ignorelist": ("Ignore these nicknames:", []),
                  "reply2ignored": ("Reply to ignored people", 0),
                  "reply_chance": ("Chance of reply (%) per message", 33),
                  "quitmsg": ("IRC quit message", "Bye :-("),
                  "password": ("password for control the bot (Edit manually !)", ""),
                  "autosaveperiod": ("Save every X minutes. Leave at 0 for no saving.", 60)
                })

        # If autosaveperiod is set, trigger it.
        asp = self.settings.autosaveperiod
        if(asp > 0) :
            self.autosave_schedule(asp)

        # Create useful variables.
        self.owners = self.settings.owners[:]
        self.chans = self.settings.chans[:]
        self.inchans = []
        self.wanted_myname = self.settings.myname
        self.attempting_regain = False
        self.feature_monitor = False

        # Parse command prompt parameters

        for x in xrange(1, len(args)):
            # Specify servers
            if args[x] == "-s":
                self.settings.servers = []
                # Read list of servers
                for y in xrange(x+1, len(args)):
                    if args[y][0] == "-":
                        break
                    server = args[y].split(":")
                    # Default port if none specified
                    if len(server) == 1:
                        server.append("6667")
                    self.settings.servers.append((server[0], int(server[1])))
            # Channels
            if args[x] == "-c":
                self.settings.chans = []
                # Read list of channels
                for y in xrange(x+1, len(args)):
                    if args[y][0] == "-":
                        break
                    self.settings.chans.append("#"+args[y])
            # Nickname
            if args[x] == "-n":
                try:
                    self.settings.myname = args[x+1]
                except IndexError:
                    pass

    def our_start(self):
        print "Connecting to server..."
        SingleServerIRCBot.__init__(self, self.settings.servers, self.settings.myname, self.settings.realname, 2, self.settings.localaddress, self.settings.ipv6)

        self.connection.execute_delayed(20, self._chan_checker)
        self.connection.execute_delayed(20, self._nick_checker)
        self.start()

    def on_welcome(self, c, e):
        print self.chans
        for i in self.chans:
            c.join(i)

    def shutdown(self):
        try:
            self.die() # disconnect from server
        except AttributeError, e:
            # already disconnected probably (pingout or whatever)
            pass

    def get_version(self):
        if self.settings.stealth:
            # stealth mode. we shall be a windows luser today
            return "VERSION mIRC32 v5.6 K.Mardam-Bey"
        else:
            return self.pyborg.ver_string

    def on_kick(self, c, e):
        """
        Process leaving
        """
        # Parse Nickname!username@host.mask.net to Nickname
        kicked = e.arguments()[0]
        kicker = e.source().split("!")[0]
        target = e.target() #channel
        if len(e.arguments()) >= 2:
            reason = e.arguments()[1]
        else:
            reason = ""

        if kicked == self.settings.myname:
            print "[%s] <--  %s was kicked off %s by %s (%s)" % (get_time(), kicked, target, kicker, reason)
            self.inchans.remove(target.lower())

    def on_part(self, c, e):
        """
        Process leaving
        """
        # Parse Nickname!username@host.mask.net to Nickname
        parter = e.source().split("!")[0]

        if parter == self.settings.myname:
            target = e.target() #channel
            self.inchans.remove(target.lower())

    def on_join(self, c, e):
        """
        Process Joining
        """
        # Parse Nickname!username@host.mask.net to Nickname
        joiner = e.source().split("!")[0]

        if joiner == self.settings.myname:
            target = e.target() #channel
            self.inchans.append(target.lower())

    def on_privmsg(self, c, e):
        self.on_msg(c, e)

    def on_featurelist(self, c, e):
        for feature in e.arguments():
            if feature[:8] == "MONITOR=":
                print "MONITOR supported."
                self.feature_monitor = True
                c.send_raw("MONITOR + %s" % self.wanted_myname)
                break

    def _failed_new_nickname(self, c, e):
        if self.attempting_regain is False:
            self.settings.myname = c.get_nickname()[:8] + `random.randint(0, 9)`
            self.connection.nick(self.settings.myname)
        else:
            if self.feature_monitor:
                # A collision may have occurred, check again.
                c.send_raw("MONITOR s")
            self.settings.myname = c.get_nickname()
            self.attempting_regain = False

    def on_nicknameinuse(self, c, e):
        self._failed_new_nickname(c, e)

    def on_erroneusnickname(self, c, e):
        self._failed_new_nickname( c, e)

#    def on_unavailresource(self, c, e):
#        self._failed_new_nickname(c, e)

    def on_pubmsg(self, c, e):
        self.on_msg(c, e)

    def on_ctcp(self, c, e):
        ctcptype = e.arguments()[0]
        if ctcptype == "ACTION":
            self.on_msg(c, e)
        else:
            SingleServerIRCBot.on_ctcp(self, c, e)

    def _on_disconnect(self, c, e):
#               self.channels = IRCDict()
        print "deconnection"
        self.attempting_regain = False
        self.feature_monitor = False
        self.connection.execute_delayed(self.reconnection_interval, self._connected_checker)


    def on_msg(self, c, e):
        """
        Process messages.
        """
        # Parse Nickname!username@host.mask.net to Nickname
        source = e.source().split("!")[0]
        target = e.target()

        learn = 1

        # First message from owner 'locks' the owner host mask
        # se people can't change to the owner nick and do horrible
        # stuff like '!unlearn the' :-)
        if not e.source() in self.owner_mask and source in self.owners:
            self.owner_mask.append(e.source())
            print "Locked owner as %s" % e.source()

        # Message text
        if len(e.arguments()) == 1:
            # Normal message
            body = e.arguments()[0]
        else:
            # A CTCP thing
            if e.arguments()[0] == "ACTION":
                body = source + " " + e.arguments()[1]
            else:
                # Ignore all the other CTCPs
                return
        # Ignore lines with color
        if body.find("\x03") != -1: return
        if body.find("\033") != -1: return

        #remove special irc fonts chars
        body = re.sub("[\x02\xa0]", "", body)

        # WHOOHOOO!!
        if target == self.settings.myname or source == self.settings.myname:
            print "[%s] Output: <%s> > %s> %s" % (get_time(), source, target, body)

        # Ignore self.
        if source == self.settings.myname: return

        # replace nicknames by "#nick"
        if e.eventtype() == "pubmsg":
            escaped_users = map(re.escape, self.channels[target].users())
            # Match nicks on word boundaries to avoid rewriting words incorrectly as containing nicks.
            p = re.compile(r'\b(' + ('|'.join(escaped_users)) + r')\b')
            body = p.sub('#nick', body)
        print "Input: " + body

        # Ignore selected nicks
        if self.settings.ignorelist.count(source.lower()) > 0 \
                and self.settings.reply2ignored == 1:
            print "[%s] [Nolearn from %s.]" % (get_time(), source)
            learn = 0
        elif self.settings.ignorelist.count(source.lower()) > 0:
            print "[%s] [Ignoring %s.]" % (get_time(), source)
            return

        # Stealth mode. disable commands for non owners
        if (not source in self.owners) and self.settings.stealth:
            while body[:1] == "!":
                body = body[1:]

        if body == "":
            return

        # Ignore quoted messages
        if body[0] == "<" or body[0:1] == "\"" or body[0:1] == " <":
            print "[Ignoring quoted text.]"
            return

        # We want replies reply_chance%, if speaking is on
        replyrate = self.settings.speaking * self.settings.reply_chance

        # Guarantee a reply if the text contains our nickname or this is a private message.
        if (body.lower().find(self.settings.myname.lower()) != -1) or e.eventtype() == "privmsg":
            replyrate = replyrate = 100

        # Parse ModIRC commands
        if body[0] == "!":
            if self.irc_commands(body, source, target, c, e) == 1:return

        # Pass message onto pyborg
        if source in self.owners and e.source() in self.owner_mask:
            self.pyborg.process_msg(self, body, replyrate, learn, (body, source, target, c, e), owner=1)
        else:
            #start a new thread
            thread.start_new_thread(self.pyborg.process_msg, (self, body, replyrate, learn, (body, source, target, c, e)))

    def irc_commands(self, body, source, target, c, e):
        """
        Special IRC commands.
        """
        msg = ""
        command_list = body.split()
        command_list[0] = command_list[0].lower()
        arg_count = len(command_list)

        ### User commands
        # Query replyrate
        if command_list[0] == "!replyrate" and len(command_list)==1:
            msg = "Reply rate is "+`self.settings.reply_chance`+"%."

        if command_list[0] == "!owner" and len(command_list) > 1 and source not in self.owners:
            if command_list[1] == self.settings.password:
                self.owners.append(source)
                self.output("You've been added to owners list.", ("", source, target, c, e))
            else:
                self.output("WRONG. Try again.", ("", source, target, c, e))
        # Stop talking
        elif command_list[0] == "!shutup":
            if self.settings.speaking == 1:
                msg = "Fine, I'll be quiet."
                self.settings.speaking = 0
            else:
                msg = "..."
        elif command_list[0] == "!roll":
            if self.settings.speaking == 0:
                if arg_count <= 1:
                    msg = "%s: Syntax: XdY+/-Z (or X#dY for separate rolls).  Mod, dice or sides max is 99 (-99 for mod)." % source
                else:
                    msg = self.handle_roll(source,command_list[1:len(command_list)])

        elif command_list[0] == "!fate":
            if arg_count <= 1:
                msg = self.handle_fate_roll(source,0)
            else:
                try:
                    modifier = int(command_list[1])
                    msg = self.handle_fate_roll(source,modifier)
                except ValueError:
                    msg = "%s: Syntax: !fate <modifier>." % source
        elif command_list[0] == "!dryh":
            if arg_count <= 4:
                msg = "%s: DRYH syntax: !roll dryh <discipline> <exhaustion> <madness> <pain>." % source
            else:
                pools = []
                for x in range(1,5):
                    try:
                        pools.append(int(command_list[x]))
                    except ValueError:
                        break
                if len(pools) == 4:
                    msg = self.handle_dryh_roll(source,pools)
                else:
                    msg = "%s: DRYH syntax: !roll dryh <discipline> <exhaustion> <madness> <pain>." % source

        elif command_list[0] == "!drink":
            if self.settings.speaking == 0:
                self.output("\x01ACTION slings " + self.get_drink() + " down the bar to " + source + ".\x01", ("<none>", source, target, c, e))
        elif command_list[0] == "!quote":
            if self.settings.speaking == 0:
                quotestr = ""
                if arg_count > 1:
                    for x in range(1, len(command_list)):
                        if x > 1:
                            quotestr = quotestr + " "
                        quotestr = quotestr + str(command_list[x])
                    else:
                        quotestr = "random"
                msg = source + ": " + self.get_quote(quotestr)
        elif command_list[0] == "!note":
            if arg_count == 1:
                msg = "Who do you want to send a note to, " + source + "?"
            elif arg_count == 2:
                msg = "What do you want the note to contain, " + source + "?"
            else:
                note_string = ""
                for x in range(2,arg_count):
                    if(x > 2):
                        note_string = note_string + " "
                    note_string = note_string + command_list[x]
                msg = self.handle_note(source,command_list[1],note_string)

        ### Owner commands
        if (msg == 0 or not msg) and source in self.owners and e.source() in self.owner_mask:

            # Change nick
            if command_list[0] == "!nick":
                try:
                    self.connection.nick(command_list[1])
                    self.settings.myname = command_list[1]
                    self.wanted_myname = self.settings.myname
                except:
                    pass
            # stealth mode
            elif command_list[0] == "!stealth":
                msg = "Stealth mode "
                if len(command_list) == 1:
                    if self.settings.stealth == 0:
                        msg = msg + "off"
                    else:
                        msg = msg + "on"
                else:
                    toggle = command_list[1].lower()
                    if toggle == "on":
                        msg = msg + "on"
                        self.settings.stealth = 1
                    else:
                        msg = msg + "off"
                        self.settings.stealth = 0
                msg = msg + "."
            # filter mirc colours out?
            elif command_list[0] == "!nocolor" or command_list[0] == "!nocolour":
                msg = "Obsolete command."

            # Allow/disallow replying to ignored nicks
            # (they will never be learnt from)
            elif command_list[0] == "!reply2ignored":
                msg = "Replying to ignored users "
                if len(command_list) == 1:
                    if self.settings.reply2ignored == 0:
                        msg = msg + "off"
                    else:
                        msg = msg + "on"
                else:
                    toggle = command_list[1]
                    if toggle == "on":
                        msg = msg + "on"
                        self.settings.reply2ignored = 1
                    else:
                        msg = msg + "off"
                        self.settings.reply2ignored = 0
            # Wake up again
            elif command_list[0] == "!wakeup":
                if self.settings.speaking == 0:
                    self.settings.speaking = 1
                    msg = "I am now awake."
                else:
                    msg = "I'm already active."

            # Join a channel or list of channels
            elif command_list[0] == "!join":
                for x in xrange(1, len(command_list)):
                    if not command_list[x] in self.chans:
                        self.chans.append(command_list[x])
                    if not command_list[x].lower() in self.inchans:
                        msg = "Attempting to join channel %s." % command_list[x]
                        c.join(command_list[x])

            # Part a channel or list of channels
            elif command_list[0] == "!part":
                for x in xrange(1, len(command_list)):
                    if command_list[x] in self.chans:
                        self.chans.remove(command_list[x])
                    if command_list[x].lower() in self.inchans:
                        msg = "Leaving channel %s" % command_list[x]
                        c.part(command_list[x])

            # List channels currently on
            elif command_list[0] == "!chans":
                if len(self.channels.keys())==0:
                    msg = "I'm not currently on any channels."
                else:
                    msg = "I'm currently on: "
                    channels = self.channels.keys()
                    for x in xrange(0, len(channels)):
                        msg = msg+channels[x]+" "
            # add someone to the ignore list
            elif command_list[0] == "!ignore":
                # if no arguments are given say who we are
                # ignoring
                if len(command_list) == 1:
                    msg = "I'm ignoring "
                    if len(self.settings.ignorelist) == 0:
                        msg = msg + "nobody"
                    else:
                        for x in xrange(0, len(self.settings.ignorelist)):
                            msg = msg + self.settings.ignorelist[x] + " "
                    msg = msg + "."
                # Add everyone listed to the ignore list
                # eg !ignore tom dick harry
                else:
                    for x in xrange(1, len(command_list)):
                        self.settings.ignorelist.append(command_list[x].lower())
                        msg = "Done."
            # remove someone from the ignore list
            elif command_list[0] == "!unignore":
                # Remove everyone listed from the ignore list
                # eg !unignore tom dick harry
                for x in xrange(1, len(command_list)):
                    try:
                        self.settings.ignorelist.remove(command_list[x].lower())
                        msg = "Done."
                    except:
                        pass
            # set the quit message
            elif command_list[0] == "!quitmsg":
                if len(command_list) > 1:
                    self.settings.quitmsg = body.split(" ", 1)[1]
                    msg = "New quit message is: \"%s\"." % self.settings.quitmsg
                else:
                    msg = "Quit message is: \"%s\"." % self.settings.quitmsg
            # make the pyborg quit
            elif command_list[0] == "!quit":
                sys.exit()
            elif command_list[0] == "!jump":
                print("Jumping servers...")
                self.jump_server()
            # Change reply rate
            elif command_list[0] == "!replyrate":
                try:
                    self.settings.reply_chance = int(command_list[1])
                    msg = "Now replying to %d%% of messages." % int(command_list[1])
                except:
                    msg = "Reply rate is %d%%." % self.settings.reply_chance
            #make the bot talk
            elif command_list[0] == "!talk":
                if len(command_list) >= 2:
                    phrase=""
                    for x in xrange (2, len (command_list)):
                        phrase = phrase + str(command_list[x]) + " "
                    self.output(phrase, ("", command_list[1], "", c, e))
            #make the bot /me
            elif command_list[0] == "!me":
                if len(command_list) >= 2:
                    phrase=""
                    for x in xrange (2, len (command_list)):
                        phrase = phrase + str(command_list[x]) + " "
                    self.output("\x01ACTION " + phrase + "\x01", ("", command_list[1], "", c, e))
            # Save changes
            save_myname = self.settings.myname
            if self.wanted_myname is not None:
                self.settings.myname = self.wanted_myname
            self.pyborg.settings.save()
            self.settings.save()
            self.settings.myname = save_myname

        if msg == "":
            return 0
        else:
            self.output(msg, ("<none>", source, target, c, e))
            return 1


    def _chan_checker(self):
        if self.connection.is_connected():
            for i in self.chans:
                if not i.split()[0].lower() in self.inchans:
                    print "Attempting to rejoin %s." % i
                    self.connection.join(i)
        self.connection.execute_delayed(20, self._chan_checker)

    def _nick_checker(self):
        if (self.connection.is_connected() and
            self.feature_monitor is False and
            self.connection.get_nickname() != self.wanted_myname):
               self.connection.ison([self.wanted_myname])
        self.connection.execute_delayed(20, self._nick_checker)

    def _try_regain(self, nick):
            print "Attempting to regain nickname %s" % nick
            self.attempting_regain = True
            self.settings.myname = nick
            self.connection.nick(self.settings.myname)

    def on_ison(self, c, e):
        nick_found = False
        for nick in e.arguments()[0].split():
            if nick.lower() == self.wanted_myname.lower():
                nick_found = True
                break
        if not nick_found:
            self._try_regain(self.wanted_myname)

    def on_monoffline(self, c, e):
        for nick in e.arguments()[0].split(','):
            if nick.lower() == self.wanted_myname.lower():
                self._try_regain(self.wanted_myname)
                break

    def output(self, message, args):
        """
        Output a line of text. args = (body, source, target, c, e)
        """
        if not self.connection.is_connected():
            print "Can't send reply: not connected to server"
            return

        # Unwrap arguments
        body, source, target, c, e = args

        # replace by the good nickname
        # message = message.replace("#nick :", "#nick:")
        # message = message.replace("#nick", source)

        # Decide. should we do a ctcp action?
        if message.find(self.settings.myname.lower()+" ") == 0:
            action = 1
            message = message[len(self.settings.myname)+1:]
        else:
            action = 0

        # Joins replies and public messages
        if e.eventtype() == "join" or e.eventtype() == "quit" or e.eventtype() == "part" or e.eventtype() == "pubmsg":
            if action == 0:
                print "[%s] <%s> > %s> %s" % (get_time(), self.settings.myname, target, message)
                c.privmsg(target, message)
            else:
                print "[%s] <%s> > %s> /me %s" % (get_time(), self.settings.myname, target, message)
                c.action(target, message)
        # Private messages
        elif e.eventtype() == "privmsg":
            # normal private msg
            if action == 0:
                print "[%s] <%s> > %s> %s" % (get_time(), self.settings.myname, source, message)
                c.privmsg(source, message)
                # send copy to owner
                if not source in self.owners:
                    c.privmsg(','.join(self.owners), "(From "+source+") "+body)
                    c.privmsg(','.join(self.owners), "(To   "+source+") "+message)
            # ctcp action priv msg
            else:
                print "[%s] <%s> > %s> /me %s" % (get_time(), self.settings.myname, target, message)
                c.action(source, message)
                # send copy to owner
                if not source in self.owners:
                    map ((lambda x: c.action(x, "(From "+source+") "+body)), self.owners)
                    map ((lambda x: c.action(x, "(To   "+source+") "+message)), self.owners)

    ##
    # This function schedules autosave_execute to happen every asp minutes
    # @param asp the autosave period, configured on pyborg-irc.cfg, in minutes.
    def autosave_schedule(self, asp) :
        timer = Timer(asp * 60, self.autosave_execute, ())
        self.should_autosave = True
        timer.setDaemon(True)
        timer.start()

    ##
    # This function gets called every autosaveperiod minutes, and executes the autosaving.
    # @param asp autosaveperiod, see above.
    def autosave_execute(self) :
        if self.should_autosave:
            self.pyborg.save_all()
            self.autosave_schedule(self.settings.autosaveperiod)

    def autosave_stop(self):
        self.should_autosave = False

    # Some extra functions for #trueidlers defined after this point.
    
    ##
    # This function takes a source, a recipient and a string and saves a note to pass to them later.
    # @param sender person sending the message
    # @param recipient target for the message
    # @param note the message body
    def handle_note(self,sender,recipient,note):
        return "Sending \"%s\" to %s, %s (not really, todo)." % (note, recipient, sender)

    ##
    # Processes several strings of dice rolls and returns the results.
    # @param sender person requesting the rolls
    # @param rolls list of roll strings to process
    def handle_roll(self,sender,rolls):

        rollresults = ""

        first = True
        valid_roll = False
        for x in range(0,len(rolls)):

            rolldata = re.match("^([0-9]{0,2})(#?)[dD]([0-9]{1,2})([\+\-][0-9]{1,2})?$",rolls[x])
 
            if not rolldata:
                continue
           
            rolldata = rolldata.groups()

            if not rolldata or not rolldata[2]:
                continue

            rollstring = rolls[x] + ": "

            dice_mul = 1
            dice_sides = int(rolldata[2])
            dice_mod = 0

            if rolldata[3]:
                mod_string = rolldata[3]
                dice_mod = int(mod_string[1:])
                if mod_string[:1] == "-":
                    dice_mod = 0 - dice_mod

            if rolldata[0]: 
                dice_mul = int(rolldata[0])
            
            if dice_mul <= 0 or dice_sides <= 0:
                continue

            if rolldata[1]:
                rollstring += "\x02["
                
            valid_roll= True

            dice_total = 0
            for x in range(1,(dice_mul+1)):
                result = random.randint(1,dice_sides)
                if rolldata[1]:
                    result = max(0,result+dice_mod) 
                    rollstring += str(result)
                    if x < dice_mul:
                        rollstring += ", "
                else:
                    dice_total += result

            if rolldata[1]:
                rollstring += "]\x02"
            else:
                rollstring += "\x02[" + str(max(0,dice_total+dice_mod)) + "]\x02"

            if first:
                first = False
            else:
                rollresults += " "
            rollresults += rollstring 

        if valid_roll:
            return "%s: %s." % (sender, rollresults)
        else:
            return "%s: Syntax: XdY+/-Z (or X#dY for separate rolls). Mod, dice or sides max is 99 (-99 for mod)." % sender

    def handle_fate_roll(self,source,mod):

        results = ["Terrible","Poor","Mediocre","Average","Fair","Good","Great","Superb","Fantastic","Epic","Legendary"]
        result = 0

        result_string = "\x02"
        for x in range(0,4):
            dice_roll = random.randint(1,3)
            if(dice_roll==3):
                result+=1
                result_string += "\x0310+\x03"
            elif(dice_roll==1):
                result-=1
                result_string += "\x0304-\x03"
            else:
                result_string += "\x0315o\x03"
        result_string += "\x02"

        effective_result = result+mod
        result_descriptor = results[min(len(results)-1,max(0,effective_result+2))]
        effective_result = "\x0310+"+str(effective_result)+"\x03" if effective_result >= 0 else "\x0304"+str(effective_result)+"\x03"
        result = "\x0310+"+str(result)+"\x03" if result >= 0 else "\x0304"+str(result)+"\x03"
        return "%s: [%s|%s] %s, %s!" % (source,result_string,result,effective_result,result_descriptor)
        
    def handle_dryh_roll(self,source,totals):

        pools = []
        result_strings = []
        pool_names = ["Discipline","Exhaustion","Madness","Pain"]
        dominating = "Discipline"
        dominating_count = 0

        # Cap possible roll totals.
        totals[0] = max(1,min(totals[0],3)) 
        totals[1] = max(0,min(totals[1],6)) 
        totals[2] = max(0,min(totals[2],8)) 
        totals[3] = max(0,min(totals[3],15))
        
        for x in range(0,4):
            pool = [pool_names[x]]
            pool_total = 0
            pool_size = totals[x]
            result_string = ""
            for y in range(0,pool_size):
                result = random.randint(1,6)
                result_string += str(result)
                pool.append(result)
                if result < 4:
                    pool_total += 1
            result_strings.append(result_string)
            totals[x] = pool_total
            pools.append(pool)

        dominating_pools = list(pools)
        print str(dominating_pools)

        strength = 6
        for x in range(0,6):
            strength = 6 - x
            current_highest = 0
            surviving_pools = []
            for y in range(0,len(dominating_pools)):
                pool = dominating_pools[y]
                strength_score = pool.count(strength)
                if strength_score > current_highest:
                    current_highest = strength_score
                    surviving_pools = []
                    surviving_pools.append(pool)
                elif strength_score == current_highest:
                    surviving_pools.append(pool)
            dominating_pools = surviving_pools
            if len(dominating_pools) <= 1:
                break
            
        if len(dominating_pools) == 1:
            pool = dominating_pools[0]
            dominating = pool[0]
            dominating_count = pool.count(strength)
        else:
            pool_names = []
            pool_strength = []
            for x in range(0,len(dominating_pools)):
                pool = dominating_pools[x]
                pool_names.append(pool[0])
                pool_strength.append(pool.count(strength))

            if pool_names.count("Discipline") > 0:
                dominating = "Discipline"
            elif pool_names.count("Madness") > 0:
                dominating = "Madness"
            elif pool_names.count("Exhaustion") > 0:
                dominating = "Exhaustion"
            elif pool_names.count("Pain") > 0:
                dominating = "Pain"
            try:
                dominating_count = pool_strength.index(dominating)
            except ValueError:
                dominating_count = -1

        if dominating_count > 1:
            strength = str(strength) + "'s"
        else: 
            strength = str(strength)

        winning_score = (totals[0]+totals[1]+totals[2])    
        winner = source
        if totals[3] > winning_score:
            winning_score = totals[3]
            winner = "GM"

        if dominating_count == -1:
            return "%s: [\x0314 D[%s] \x02%d\x02 \x03\x0301E[%s] \x02%d\x02 \x03\x0304M[%s] \x02%d\x02 \x03\x0306P[%s] \x02%d\x02 \x03]: \x02%s wins\x02 with \x02%d\x02 successes, \x02%s dominates\x02 by default." % (source,result_strings[0],totals[0],result_strings[1],totals[1],result_strings[2],totals[2],result_strings[3],totals[3],winner,winning_score,dominating)
        else:
            return "%s: [\x0314 D[%s] \x02%d\x02 \x03\x0301E[%s] \x02%d\x02 \x03\x0304M[%s] \x02%d\x02 \x03\x0306P[%s] \x02%d\x02 \x03]: \x02%s wins\x02 with \x02%d\x02 successes, \x02%s dominates\x02 with %d %s." % (source,result_strings[0],totals[0],result_strings[1],totals[1],result_strings[2],totals[2],result_strings[3],totals[3],winner,winning_score,dominating,dominating_count,strength)
        
    def get_drink(self):
        return "a random drink"

    def get_quote(self,quotestr):
        if not quotestr or quotestr == "random":
            return "No quotes saved."
        else:
            return "No quotes for \"%s\"." % quotestr

if __name__ == "__main__":

    if "--help" in sys.argv:
        print "Pyborg irc bot. Usage:"
        print " pyborg-irc.py [options]"
        print " -s   server:port"
        print " -c   channel"
        print " -n   nickname"
        print "Defaults stored in pyborg-irc.cfg"
        print
        sys.exit(0)
    # start the pyborg
    my_pyborg = pyborg.pyborg()
    bot = ModIRC(my_pyborg, sys.argv)
    try:
        bot.our_start()
    except KeyboardInterrupt, e:
        pass
    except SystemExit, e:
        pass
    except:
        traceback.print_exc()
        c = raw_input("Ooops! It looks like Pyborg has crashed. Would you like to save its dictionary? (y/n) ")
        if c.lower()[:1] == 'n':
            sys.exit(0)
    bot.autosave_stop()
    bot.disconnect(bot.settings.quitmsg)
    if my_pyborg.saving:
        while my_pyborg.saving:
            print "Waiting for save in other thread..."
            time.sleep(1)
    else:
        my_pyborg.save_all()
    del my_pyborg
