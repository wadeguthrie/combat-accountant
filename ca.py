#! /usr/bin/python

import curses
import json
import pprint
# import requests # Easy to use HTTP, requires Python 3

# read character via json
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
            return [ CaJson.__byteify(item,
                                      ignore_dicts=True) for item in data ]
        # if this is a dictionary, return dictionary of byteified keys and
        # values but only if we haven't already byteified it
        if isinstance(data, dict) and not ignore_dicts:
            return {
                CaJson.__byteify(key, ignore_dicts=True):
                    CaJson.__byteify(value, ignore_dicts=True)
                    for key, value in data.iteritems()
            }
        # if it's anything else, return it in its original form
        return data


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

    def printit(self,
                string  # String to print
               ):
        '''
        Really just for debug.  Prints strings on the screen.
        '''
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
                # NOTE: assumes this is on top of stdscr
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

                #print "INDEX - old:%d, new:%d, final:%d" % (old_index,
                #                                            new_index,
                #                                            index)

                menu_win.addstr(old_index,
                                0,
                                strings_results[old_index][0],
                                curses.A_NORMAL)
                menu_win.addstr(index,
                                0,
                                strings_results[index][0],
                                curses.A_STANDOUT)
                menu_win.refresh()

    def clear(self):
        self.__stdscr.clear()

    def command_ribbon(
            self,
            choices # hash: ord('f'): {'name': 'xxx', 'func': self.func}
           ):
        '''
        Draws a list of commands across the bottom of the screen
        '''
        left = 0

        self.__stdscr.addstr(curses.LINES - 1,
                             left,
                             '|',
                             curses.A_NORMAL)
        left += 2 # adds a space

        for choice, body in choices.iteritems():
            if choice == ord(' '):
                choice_string = '" "'
            else:
                choice_string = '%c' % chr(choice)

            self.__stdscr.addstr(curses.LINES - 1,
                                 left,
                                 choice_string,
                                 curses.A_REVERSE)
            left += len(choice_string) + 1 # add a space after the choice

            self.__stdscr.addstr(curses.LINES - 1,
                                 left,
                                 body['name'],
                                 curses.A_BOLD)

            left += len(body['name']) + 1 # add a space after the choice

            self.__stdscr.addstr(curses.LINES - 1,
                                 left,
                                 '|',
                                 curses.A_NORMAL)
            left += 2 # adds a space

        self.__stdscr.refresh()


class Fight(object):
    def __init__(self,
                 display,
                 characters,
                 monsters,
                 fight_round=0,
                 fighters=None, # Current initiative order of fighters
                 index=0 # Index into fighters order for current fight
                ):
        self.__display = display
        self.__characters = characters
        self.__monsters = monsters
        self.__round = fight_round
        self.__fighters = [] if fighters is None else fighters
        self.__index = index

        if fighters is None:
            self.__fighters = []
            self.__fighters.extend(self.__characters)
            if self.__monsters is not None:
                self.__fighters.extend(self.__monsters)

            # Sort by initiative = basic-speed followed by DEX followed by
            # random
            # TODO: add DEX and random
            # TODO: there should be an 'initiative' value so that someone can
            #   change their initiative with a 'wait' action (although, maybe,
            #   that just changes the order in the list)
            # NOTE: initiative trait is rule
            self.__fighters.sort(key=lambda fighter: 
                fighter['current']['basic-speed'],
                reverse=True) # NOTE: initiative order is a rule
        else:
            self.__fighters = fighters

    def doit(self):
        # TODO draw screen

        keep_going = True
        while keep_going:
            string = display.get_input()
            keep_going = self.handle_input(string)


class MainScreen(object):
    def __init__(self, display, world):
        self.__display = display
        self.__world = world
        self.__choices = {
            ord('f'): {'name': 'fight', 'func': self.__new_fight},
            ord('q'): {'name': 'quit',  'func': self.__quit}
        }

    def doit(self):
        '''
        Draws the screen and does event loop (gets input, responds to input)
        '''
        self._draw_screen()

        keep_going = True
        while keep_going:
            string = display.get_input()
            if string in self.__choices:
                keep_going = self.__choices[string]['func']()

    def _draw_screen(self):
        self.__display.clear()
        self.__display.command_ribbon(self.__choices)

    def __new_fight(self):
        fight_name_menu = [(name, name)
                           for name in self.__world['monsters'].keys()]
        # PP.pprint(fight_name_menu)
        monster_list = display.menu('Fights', fight_name_menu)
        print "MENU RESULT=%s" % result  # For debugging

        if (monster_list is None or
                monster_list not in self.__world['monsters']):
            print "ERROR, monster list %s not found" % monster_list

        # NOTE: this makes the displays recursive (though, the implementation
        # only makes the code recursive but the actual screens will just get
        # reused).
        fight = Fight(self.__display,
                      self.__world['characters'],
                      self.__world['monsters'][monster_list])
        fight.doit()

        return True # Keep going

    def __quit(self):
        return False # Leave



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

        # Error checking for JSON

        if 'characters' not in world:
            #display.Error('No "characters" in %s' % filename)
            print 'No "characters" in %s' % filename # TODO: dump when display


        # TODO: if there's a fight in progress, we need to start it
        #self.__fighters.extend
        #if ('current-fight' in world and 
        #        world['current-fight'] in world['monsters']):
        #    self.__fighters.extend(world['monsters'][world['current-fight']])

        # PP.pprint(fighters)

        # Enter into the mainloop
        with CaDisplay() as display:
            main_screen = MainScreen(display, world)
            main_screen.doit()


