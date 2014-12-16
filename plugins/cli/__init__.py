#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#########################################################################
#  This file is part of SmartHome.py.    http://mknx.github.io/smarthome/
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py.  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import threading
import lib.connection

logger = logging.getLogger('')


class CLIHandler(lib.connection.Stream):
    terminator = '\n'.encode()

    def __init__(self, smarthome, sock, source, updates, call_item_allowed=True):
        lib.connection.Stream.__init__(self, sock, source)
        self.source = source
        self.updates_allowed = updates
        self.call_item_allowed = call_item_allowed
        self.sh = smarthome
        self.push("SmartHome.py v{0}\n".format(self.sh.version))
        self.push("Enter 'help' for a list of available commands.\n")
        self.push("> ")

    def push(self, data):
        self.send(data.encode())

    def found_terminator(self, data):
        cmd = data.decode().strip()
        if cmd.startswith('ls'):
            self.push("Items:\n======\n")
            self.ls(cmd.lstrip('ls').strip())
        elif cmd == 'la':
            self.la()
        elif cmd == 'lo':
            self.lo()
        elif cmd == 'll':
            self.lo()
        elif cmd == 'lt':
            self.lt()
        elif cmd == 'cl':
            self.cl()
        elif cmd.startswith('update ') or cmd.startswith('up '):
            self.update(cmd.lstrip('update').strip())
        elif cmd.startswith('call_item ') or cmd.startswith('!'):
            cmd_ = cmd.lstrip('call_item').strip()
            cmd_ = cmd.lstrip('!').strip()
            self.call_item(cmd_)
        elif cmd.startswith('tr'):
            self.tr(cmd.lstrip('tr').strip())
        elif cmd.startswith('rl'):
            self.rl(cmd.lstrip('rl').strip())
        elif cmd.startswith('rr'):
            self.rr(cmd.lstrip('rr').strip())
        elif cmd == 'help' or cmd == 'h':
            self.usage()
        elif cmd in ('quit', 'q', 'exit', 'x'):
            self.push('bye\n')
            self.close()
            return
        else:
            self.push("syntax error.\n")
        self.push("> ")

    def cl(self):
        self.sh.log.clean(self.sh.now())

    def ls(self, path):
        if not path:
            for item in self.sh:
                self.push("{0}\n".format(item.id()))
        else:
            item = self.sh.return_item(path)
            if hasattr(item, 'id'):
                if item._type:
                    self.push("{0} = {1}\n".format(item.id(), item()))
                else:
                    self.push("{}\n".format(item.id()))
                for child in item:
                    self.ls(child.id())
            else:
                self.push("Could not find path: {}\n".format(path))

    def la(self):
        self.push("Items:\n======\n")
        for item in self.sh.return_items():
            if item._type:
                self.push("{0} = {1}\n".format(item.id(), item()))
            else:
                self.push("{0}\n".format(item.id()))

    def update(self, data):
        if not self.updates_allowed:
            self.push("Updating items is not allowed.\n")
            return
        path, sep, value = data.partition('=')
        path = path.strip()
        value = value.strip()
        if not value:
            self.push("You have to specify an item value. Syntax: up item = value\n")
            return
        item = self.sh.return_item(path)
        if not hasattr(item, '_type'):
            self.push("Could not find item with a valid type specified: '{0}'\n".format(path))
            return
        item(value, 'CLI', self.source)

    def call_item(self, data):
        if not self.call_item_allowed:
            self.push("Calling items is not allowed.\n")
            return

        path, arglist = data.split('(')
        path = path.strip()
        arglist = arglist.strip()

        # we expect sth like item.sub_item(arg) or item.sub_item.method(arg)
        if not arglist:
            self.push("You have to specify an item call.\n")
            return
        item = self.sh.return_item(path)
        if item is None:
            # maybe this is not a direct item call but a call to a specific method (like SQL.db())
            path = ".".join(path.split(".")[:-1])
            item = self.sh.return_item(path)
        if item is None:
            self.push("Could not find item.\n")
            return
        hastype = hasattr(item, '_type')
        if not hastype:
            self.push("Could not find item with a valid type specified.\n")
            return
        
        # make the call and catch the retval (or a possible Exception) 
        try:
            retval = eval("self.sh." + data.strip())
        except Exception as e:
            retval = str(e)
        self.push("call returned: %s\n" % retval)

    def tr(self, logic):
        if not self.updates_allowed:
            self.push("Logic triggering is not allowed.\n")
            return
        if logic in self.sh.return_logics():
            self.sh.trigger(logic, by='CLI')
        else:
            self.push("Logic '{0}' not found.\n".format(logic))

    def rl(self, name):
        if not self.updates_allowed:
            self.push("Logic triggering is not allowed.\n")
            return
        if name in self.sh.return_logics():
            logic = self.sh.return_logic(name)
            logic.generate_bytecode()
        else:
            self.push("Logic '{0}' not found.\n".format(name))

    def rr(self, name):
        if not self.updates_allowed:
            self.push("Logic triggering is not allowed.\n")
            return
        if name in self.sh.return_logics():
            logic = self.sh.return_logic(name)
            logic.generate_bytecode()
            logic.trigger(by='CLI')
        else:
            self.push("Logic '{0}' not found.\n".format(name))

    def lo(self):
        self.push("Logics:\n")
        for logic in self.sh.return_logics():
            nt = self.sh.scheduler.return_next(logic)
            if nt is not None:
                self.push("{0} (scheduled for {1})\n".format(logic, nt.strftime('%Y-%m-%d %H:%M:%S%z')))
            else:
                self.push("{0}\n".format(logic))

    def lt(self):
        # list all threads with names
        self.push("{0} Threads:\n".format(threading.activeCount()))
        for t in threading.enumerate():
            self.push("{0}\n".format(t.name))

    def usage(self):
        self.push('cl: clean (memory) log\n')
        self.push('ls: list the first level items\n')
        self.push('ls item: list item and every child item (with values)\n')
        self.push('la: list all items (with values)\n')
        self.push('lo: list all logics and next execution time\n')
        self.push('lt: list current thread names\n')
        self.push('update item = value: update the specified item with the specified value\n')
        self.push('up: alias for update\n')
        self.push('call_item item(args): calls the specified item with the specified arguments\n')
        self.push('!: alias for call_item\n')
        self.push('tr logic: trigger logic\n')
        self.push('rl logic: reload logic\n')
        self.push('rr logic: reload and run logic\n')
        self.push('quit: quit the session\n')
        self.push('q: alias for quit\n')


class CLI(lib.connection.Server):

    def __init__(self, smarthome, update='False', ip='127.0.0.1', port=2323):
        lib.connection.Server.__init__(self, ip, port)
        self.sh = smarthome
        self.updates_allowed = smarthome.string2bool(update)

    def handle_connection(self):
        sock, address = self.accept()
        if sock is None:
            return
        logger.debug("{}: incoming connection from {} to {}".format(self._name, address, self.address))
        CLIHandler(self.sh, sock, address, self.updates_allowed)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False
        self.close()
