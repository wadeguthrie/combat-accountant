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
        self.__y = 0 # For debug printouts

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

    def show(self, string):
        mode = curses.A_STANDOUT if (self.__y % 3 == 0) else curses.A_NORMAL
        self.__stdscr.addstr(self.__y, 0, string, mode)
        self.__y = 0 if self.__y == curses.LINES else self.__y + 1
        self.__stdscr.refresh()

    def get_input(self):
        c = self.__stdscr.getch()
        # 'c' will be something like ord('p') or curses.KEY_HOME
        # TODO: convert 'c' to something ascii-like
        return c

    def menu(self,
             title,
             strings_results # array of tuples (string, return value)
            ):
        # TODO: doesn't handle more entries that would fit on screen

        # height and width of text box (not border)
        height = len(strings_results)
        width = 0 if title is None else len(title)
        for string, result in strings_results:
            if len(string) > width:
                width = len(string)
        width += 1 # Seems to need one more space (or Curses freaks out)

        # x and y of text box (not border)
        begin_x = (curses.COLS / 2) - (width/2)
        begin_y = (curses.LINES / 2) - (height/2)

        border_win = curses.newwin(height+2, width+2, begin_y-1, begin_x-1)
        border_win.border()

        title_start = ((width + 2) - (len(title))) / 2
        border_win.addstr(0, title_start, title)
        border_win.refresh()

        menu_win = curses.newwin(height, width, begin_y, begin_x)
        index = 0
        for line, string_result in enumerate(strings_results):
            # Maybe use A_BOLD instead of A_STANDOUT -- could also use
            # curses.color_pair(1) or whatever
            mode = curses.A_STANDOUT if line == index else curses.A_NORMAL
            menu_win.addstr(line, 0, string_result[0], mode)
        menu_win.refresh()

        keep_going = True
        while keep_going:
            input = self.get_input()
            new_index = index
            if input == curses.KEY_HOME:
                new_index = 0
            elif input == curses.KEY_UP:
                new_index -= 1
            elif input == curses.KEY_DOWN:
                new_index += 1
            elif input == ord('\n'):
                del border_win
                del menu_win
                # TODO: the following shouldn't be stdscr, it should be part
                # of a stack of windows
                self.__stdscr.touchwin()
                self.__stdscr.refresh()
                return strings_results[index][1]
            if new_index != index:
                old_index = index
                if new_index < 0:
                    index = height-1
                elif new_index >= height:
                    index = 0
                else:
                    index = new_index

                print "INDEX - old:%d, new:%d, final:%d" % (old_index,
                                                            new_index,
                                                            index)
                menu_win.addstr(old_index,
                                0,
                                strings_results[old_index][0],
                                curses.A_NORMAL)
                menu_win.addstr(index,
                                0,
                                strings_results[index][0],
                                curses.A_STANDOUT)
                menu_win.refresh()


class CaJson(object):

    def __init__(self, filename):
        self.__filename = filename

    def __enter__(self):
        try:
            with open(self.__filename, 'r') as f:
              #world = json.load(f)
              world = CaJson.__json_load_byteified(f)
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

    # Used to keep JSON load from automatically converting to Unicode.
    # Alternatively, I could have gone to Python 3 (which doesn't have that
    # problem) but I didn't want to install a new version of Python and a new
    # version of Curses.
    #
    # Solution from https://stackoverflow.com/questions/956867/
    #        how-to-get-string-objects-instead-of-unicode-from-json?
    #        utm_medium=organic&utm_source=google_rich_qa&
    #        utm_campaign=google_rich_qa
    @staticmethod
    def __json_load_byteified(file_handle):
        return CaJson.__byteify(
            json.load(file_handle, object_hook=CaJson.__byteify),
            ignore_dicts=True
        )

    @staticmethod
    def __byteify(data, ignore_dicts = False):
        # if this is a unicode string, return its string representation
        if isinstance(data, unicode):
            return data.encode('utf-8')
        # if this is a list of values, return list of byteified values
        if isinstance(data, list):
            return [ CaJson.__byteify(item, ignore_dicts=True) for item in data ]
        # if this is a dictionary, return dictionary of byteified keys and values
        # but only if we haven't already byteified it
        if isinstance(data, dict) and not ignore_dicts:
            return {
                CaJson.__byteify(key, ignore_dicts=True): CaJson.__byteify(value, ignore_dicts=True)
                for key, value in data.iteritems()
            }
        # if it's anything else, return it in its original form
        return data


# Main
if __name__ == '__main__':
    PP = pprint.PrettyPrinter(indent=3, width=150)
    filename = 'persephone.json' # TODO: make this a command-line argument

    # TODO: need a game object -- it'll deal with starting fights, etc.

    # Arriving -- read our stuff
    with CaJson(filename) as world:

        # Build convenient data structures starting from:
        #   {
        #       'current': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
        #       'permenant': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
        #       'name': 'groucho', 
        #       'opponent': null
        #   }, 

        fighters = []
        if 'characters' not in world:
            #display.Error('No "characters" in %s' % filename)
            print 'No "characters" in %s' % filename # TODO: dump when display
        fighters.extend(world['characters'])
        if ('current-fight' in world and 
                world['current-fight'] in world['monsters']):
            fighters.extend(world['monsters'][world['current-fight']])

        # Sort by initiative = basic-speed followed by DEX followed by random
        # TODO: add DEX and random
        # TODO: there should be an 'initiative' value so that someone can
        #   change their initiative with a 'wait' action (although, maybe,
        #   that just changes the order in the list)
        fighters.sort(key=lambda fighter: fighter['current']['basic-speed'],
                      reverse=True)

        # PP.pprint(fighters)


        # Enter into the mainloop
        with CaDisplay() as display:
            for fighter in fighters:
                display.show(fighter['name'])

            fight_name_menu = [(name, name)
                               for name in world['monsters'].keys()]
            # PP.pprint(fight_name_menu)
            result = display.menu('Fights', fight_name_menu)
            print "MENU RESULT=%s" % result

            while display.get_input() != ord('q'):
                pass


