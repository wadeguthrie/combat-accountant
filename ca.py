#! /usr/bin/python

import curses
import json
import pprint
# import requests # Easy to use HTTP, requires Python 3

# read character via json
#  - whole thing in one JSON
#  - characters: perm-stats, current-stats
#    * needs basic-speed, hp, fp, opponent
#  - current fight: which monsters
#  - monster groups: each group needs a 'used' feature
#  - timers

# sort characters and current monster group by initiative

# use curses
#  - top of page: round, current person, next person
#  - current person shows: init, hp, fp, opponent
#  - opponent also shown on screen
#  - single key input
#    * space is next initiative
#    * '-' removes HP
#    * ? removes FP
#    * 'o' picks opponent off list
#    * 'backspace' or 'del' removes creature from initiative list
#    * 't' sets an x-round timer for this creature
#    * '>' delays the initiative for a creature from the list



#def do_stuff():  # Defines a function.

class CaDisplay(object):

    # NOTE: remember to call win.refresh()
    # win.addstr(y, x, "String", attrib)
    #   attrib can be curses.color_pair(1) or curses.A_REVERSE, ...
    #   color_pair is setup using: curses.init_pair(1, # should be a symbol
    #                                               curses.COLOR_RED, # fg
    #                                               curses.COLOR_WHITE) # bg
    #   only legal colors: 0:black, 1:red, 2:green, 3:yellow, 4:blue,
    #                      5:magenta, 6:cyan, and 7:white
    # 

    def __init__(self):
        self.__stdscr = None

    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak() # respond instantly to keystrokes
            self.__stdscr.keypad(1) # special characters converted by curses
                                    # (e.g., curses.KEY_LEFT)
        except:
            curses.endwin()
        return self

    def __exit__ (self, exception_type, exception_value, exception_traceback):
        if exception_type is IOError:
            print 'IOError: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            print 'Traceback: %r' % exception_traceback
        elif exception_type is not None:
            print 'EXCEPTION type: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            print 'Traceback: %r' % exception_traceback

        self.__stdscr.keypad(0)
        curses.nocbreak()
        curses.echo()
        curses.endwin()
        self.__stdscr = None
        return True

    def GetInput(self):
        c = self.__stdscr.getch()
        # 'c' will be something like ord('p') or curses.KEY_HOME
        # TODO: convert 'c' to something ascii-like
        return chr(c) # I _think_ converts it to ASCII

    def Menu(self):
        begin_x = 20; begin_y = 7
        height = 5; width = 40
        win = curses.newwin(height, width, begin_y, begin_x)


class CaJson(object):

    def __init__(self, filename):
        self.__filename = filename

    def __enter__(self):
        try:
            with open(self.__filename, 'r') as f:
              world = json.load(f)
        except:
            pass
        return world

    def __exit__ (self, exception_type, exception_value, exception_traceback):
        if exception_type is IOError:
            print 'IOError: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            print 'Traceback: %r' % exception_traceback
        elif exception_type is not None:
            print 'EXCEPTION type: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            print 'Traceback: %r' % exception_traceback

        with open(self.__filename, 'w') as f:
            json.dump(world, f, indent=4)
        return True


# Main
if __name__ == '__main__':
    PP = pprint.PrettyPrinter(indent=3, width=150)
    filename = 'persephone.json' # TODO: make this a command-line argument

    # Arriving -- read our stuff
    with CaJson(filename) as world:

        # Build convenient data structures starting from:
        #   {
        #       'current': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
        #       'permenant': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
        #       'name': 'groucho', 
        #       'opponent': null
        #   }, 

        # Enter into the mainloop
        #with CaDisplay() as display:
        #    while display.GetInput() != 'e':
        #        pass

        fighters = []
        if 'characters' not in world:
            #display.Error('No "characters" in %s' % filename)
            print 'No "characters" in %s' % filename # TODO: dump when display
        fighters.extend(world['characters'])
        if ('current-fight' in world and 
                world['current-fight'] in world['monsters']):
            fighters.extend(world['monsters'][world['current-fight']])

        PP.pprint(fighters)


