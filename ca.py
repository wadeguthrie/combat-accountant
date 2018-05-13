#! /usr/bin/python

import curses

# read character via json
#  - whole thing in one JSON
#  - characters: perm-stats, current-stats
#    * needs init, hp, fp, opponent
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
    def __init__(self):
        self.__stdscr = None

    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
        except:
            curses.endwin()
        return

    def __exit__ (self, exception_type, exception_value, exception_traceback):
        if exception_type is IOError:
            print 'IOError: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            print 'Traceback: %r' % exception_traceback
        elif exception_type is not None:
            print 'EXCEPTION type: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            print 'Traceback: %r' % exception_traceback

        curses.endwin()
        self.__stdscr = None
        return True


# Main
if __name__ == '__main__':
    with CaDisplay() as display:
        pass

    #stdscr = curses.initscr()
    #curses.endwin()


