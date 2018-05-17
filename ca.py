#! /usr/bin/python

import curses
import json
import pprint
# import requests # Easy to use HTTP, requires Python 3

# TODO:
#   - save (init list, opponents, current monster list)
#   - restore on startup
#   - initiative based on DX and random for 2nd and 3rd key (after basic move)
#   - '>' delays the initiative for a creature from the list
#   - monster groups: each group needs a 'used' feature
#   - 'backspace' or 'del' removes creature from initiative list
#   - timers ('t' sets an x-round timer for this creature)
#   - main screen should have a 'h' heal one creature at a time
#
# TODO (eventually)
#   - errors to the Curses screen
#   - separating out ruleset-based stuff into its own class
#   - scrolling menus (et al.)
#   - entering monsters and characters from the screen
#   - make filename a command-line argument
#   - derived features (basic move is based on some stuff, e.g.)


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
    '''
    CaDisplay addresses the graphical part of the user interface.  Here,
    this is provided with the Curses package.
    '''

    ESCAPE = 27 # ASCII value for the escape character

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
        self.__FIGHTER_LINE = 2
        self.__FIGHTER_COL = 0
        self.__OPPONENT_COL = 0

    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak() # respond instantly to keystrokes
            self.__stdscr.keypad(1) # special characters converted by curses
                                    # (e.g., curses.KEY_LEFT)

            self.__FIGHTER_COL = 1
            self.__OPPONENT_COL = (curses.COLS / 2)
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

    def get_one_character(self, window=None):
        if window is None:
            window = self.__stdscr
        c = window.getch()
        # 'c' will be something like ord('p') or curses.KEY_HOME
        return c

    def get_string(self, window=None):
        if window is None:
            window = self.__stdscr
        curses.nocbreak()
        curses.echo()
        string = window.getstr()
        curses.cbreak()
        curses.noecho()
        return string

    def input_box(self, height, width, title):
        border_win, menu_win = self.__centered_boxed_window(height, width,
                                                            title)
        string = self.get_string(menu_win)

        del border_win
        del menu_win
        self.__stdscr.touchwin() # NOTE: assumes this menu is on top of stdscr
        self.__stdscr.refresh()
        return string
    

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

        border_win, menu_win = self.__centered_boxed_window(height, width,
                                                            title)

        index = 0
        for line, string_result in enumerate(strings_results):
            # Maybe use A_BOLD instead of A_STANDOUT -- could also use
            # curses.color_pair(1) or whatever
            mode = curses.A_STANDOUT if line == index else curses.A_NORMAL
            menu_win.addstr(line, 0, string_result[0], mode)
        menu_win.refresh()

        keep_going = True
        while keep_going:
            user_input = self.get_one_character()
            new_index = index
            if user_input == curses.KEY_HOME:
                new_index = 0
            elif user_input == curses.KEY_UP:
                new_index -= 1
            elif user_input == curses.KEY_DOWN:
                new_index += 1
            elif user_input == ord('\n'):
                del border_win
                del menu_win
                # NOTE: assumes this menu is on top of stdscr
                self.__stdscr.touchwin()
                self.__stdscr.refresh()
                return strings_results[index][1]
            elif user_input == CaDisplay.ESCAPE:
                # NOTE: assumes this menu is on top of stdscr
                self.__stdscr.touchwin()
                self.__stdscr.refresh()
                return None

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

    def round_ribbon(self,
                     round_no,
                     current_fighter, # use in future
                     next_fighter # use in future
                    ):
        round_string = 'Round %d' % round_no
        self.__stdscr.addstr(0,
                             0,
                             round_string,
                             curses.A_NORMAL)
        self.__stdscr.refresh()

    def show_fighters(self,
                      current_fighter,
                      current_opponent
                     ):
        self.__stdscr.move(self.__FIGHTER_LINE, self.__FIGHTER_COL)
        self.__stdscr.clrtoeol()
        self.__some_fighter(current_fighter, self.__FIGHTER_COL)

        if current_opponent is not None:
            self.__stdscr.addstr(self.__FIGHTER_LINE,
                                 self.__OPPONENT_COL, 'vs.')
            self.__some_fighter(current_opponent,
                                self.__OPPONENT_COL+4)

        self.__stdscr.refresh()

    def __some_fighter(self, fighter, column):
        fighter_string = '%s HP: %d/%d FP: %d/%d' % (
            fighter['name'],
            fighter['current']['hp'],
            fighter['permanent']['hp'],
            fighter['current']['fp'],
            fighter['permanent']['fp'])
        self.__stdscr.addstr(self.__FIGHTER_LINE,
                             column,
                             fighter_string,
                             curses.A_NORMAL)

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

    def __centered_boxed_window(self,
                                height, # height of INSIDE window
                                width, # width of INSIDE window
                                title
                               ):

        # x and y of text box (not border)
        begin_x = (curses.COLS / 2) - (width/2)
        begin_y = (curses.LINES / 2) - (height/2)

        border_win = curses.newwin(height+2, width+2, begin_y-1, begin_x-1)
        border_win.border()

        if title is not None:
            title_start = ((width + 2) - (len(title))) / 2
            border_win.addstr(0, title_start, title)
        border_win.refresh()

        menu_win = curses.newwin(height, width, begin_y, begin_x)

        return border_win, menu_win


class ScreenHandler(object):
    '''
    Base class for the "business logic" backing the user interface.
    '''

    def __init__(self, display):
        self._display = display
        self._choices = { }

    def doit(self):
        '''
        Draws the screen and does event loop (gets input, responds to input)
        '''
        self._draw_screen()

        keep_going = True
        while keep_going:
            string = self._display.get_one_character()
            if string in self._choices:
                keep_going = self._choices[string]['func']()

    def _draw_screen(self):
        pass



class FightHandler(ScreenHandler):
    def __init__(self,
                 display,
                 characters,
                 monsters,
                 fight_round=0,
                 fighters=None, # Current initiative order of fighters
                 index=0 # Index into fighters order for current fight
                ):
        super(FightHandler, self).__init__(display)

        self._choices = {
            ord(' '): {'name': 'next', 'func': self.__next_fighter},
            ord('<'): {'name': 'prev', 'func': self.__prev_fighter},
            # TODO: 'h' and 'f' are based on the ruleset
            ord('h'): {'name': 'damage', 'func': self.__damage_HP},
            ord('f'): {'name': 'damage', 'func': self.__damage_FP},
            ord('o'): {'name': 'opponent', 'func': self.__pick_opponent},
            ord('q'): {'name': 'quit', 'func': self.__quit}
        }

        self.__characters = characters
        self.__monsters = monsters
        self.__round = fight_round
        self.__fighters = [] if fighters is None else fighters
        self.__index = index

        # TODO: if we're mid-fight, I need to find this
        self.__most_recent_character = None

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

    def _draw_screen(self):
        self._display.clear()
        # TODO: look-up "up next" in self.__characters after
        # self.__most_recent_character (which may be 'None')
        self._display.round_ribbon(self.__round,
                                   None, #self.xxx, # up now
                                   None) #self.xxx) # next PC
        opponent = self.__find_opponent(self.__fighters[self.__index])
        self._display.show_fighters(self.__fighters[self.__index], opponent)
        self._display.command_ribbon(self._choices)

    def __find_opponent(self,
                        current_fighter # struct containing fighter
                       ):
        # TODO: there's got to be a better way 
        if current_fighter is None or current_fighter['opponent'] is None:
            return None
        opponent_name = current_fighter['opponent']
        for fighter in self.__fighters:
            if fighter['name'] == opponent_name:
                return fighter
        return None

    def __next_fighter(self):
        self.__index += 1
        if self.__index >= len(self.__fighters):
            self.__index = 0
            self.__round += 1
        # TODO: maybe combine the following two
        self._display.round_ribbon(self.__round,
                                   None, # current fighter
                                   None) # next PC
        opponent = self.__find_opponent(self.__fighters[self.__index])
        self._display.show_fighters(self.__fighters[self.__index], opponent)
        return True # Keep going

    def __prev_fighter(self):
        if self.__index == 0 and self.__round == 0:
            return True # Not going backwards from the origin

        self.__index -= 1
        if self.__index < 0:
            self.__index = len(self.__fighters) - 1
            self.__round -= 1
        # TODO: maybe combine the following two
        self._display.round_ribbon(self.__round,
                                   None, # current fighter
                                   None) # next PC
        opponent = self.__find_opponent(self.__fighters[self.__index])
        self._display.show_fighters(self.__fighters[self.__index], opponent)
        return True # Keep going

    def __damage_HP(self):
        opponent = self.__find_opponent(self.__fighters[self.__index])
        if opponent is not None:
            title = 'Change HP By...'
            height = 1
            width = len(title)
            adj_string = self._display.input_box(height, width, title)
            adj = int(adj_string)
            opponent['current']['hp'] += adj # TODO: this should be in rules
            self._display.show_fighters(self.__fighters[self.__index], opponent)
        return True # Keep going

    def __damage_FP(self):
        opponent = self.__find_opponent(self.__fighters[self.__index])
        if opponent is not None:
            title = 'Change FP By...'
            height = 1
            width = len(title)
            adj_string = self._display.input_box(height, width, title)
            adj = int(adj_string)
            opponent['current']['fp'] += adj # TODO: this should be in rules
            self._display.show_fighters(self.__fighters[self.__index], opponent)
        return True # Keep going

    def __pick_opponent(self):
        opponent_menu = [(fighter['name'], fighter['name']) for fighter in
                self.__fighters]
        opponent_name = self._display.menu('Opponent', opponent_menu)
        if opponent_name is not None:
            self.__fighters[self.__index]['opponent'] = opponent_name

        opponent = self.__find_opponent(self.__fighters[self.__index])

        # Ask to have them fight each other
        if opponent is not None and opponent['opponent'] is None:
            back_menu = [('Yes', True), ('No', False)]
            answer = self._display.menu('Make Opponents Go Both Ways',
                                        back_menu)
            if answer == True:
                opponent['opponent'] = self.__fighters[self.__index]['name']

        self._display.show_fighters(self.__fighters[self.__index], opponent)
        return True # Keep going

    def __quit(self):
        # Put all fighters into a non-fighting mode (mostly, just remove
        # their opponents)
        for fighter in self.__fighters:
            fighter['opponent'] = None
        return False # Leave the fight


class MainHandler(ScreenHandler):
    def __init__(self, display, world):
        super(MainHandler, self).__init__(display)
        self.__world = world
        self._choices = {
            ord('f'): {'name': 'fight', 'func': self.__new_fight},
            ord('H'): {'name': 'HEAL',  'func': self.__fully_heal},
            ord('q'): {'name': 'quit',  'func': self.__quit}
        }

    def _draw_screen(self):
        self._display.clear()
        self._display.command_ribbon(self._choices)

    def __fully_heal(self):
        for character in self.__world['characters']:
            for stat in character['permanent']:
                character['current'][stat] = character['permanent'][stat]
        return True

    def __new_fight(self):
        fight_name_menu = [(name, name)
                           for name in self.__world['monsters'].keys()]
        # PP.pprint(fight_name_menu)
        monster_list = self._display.menu('Fights', fight_name_menu)
        if monster_list is None:
            return True
        print "MENU RESULT=%s" % monster_list  # For debugging

        if (monster_list is None or
                monster_list not in self.__world['monsters']):
            print "ERROR, monster list %s not found" % monster_list

        # NOTE: this makes the displays recursive (though, the implementation
        # only makes the code recursive but the actual screens will just get
        # reused).
        fight = FightHandler(self._display,
                             self.__world['characters'],
                             self.__world['monsters'][monster_list])
        fight.doit()
        self._draw_screen() # Redraw current screen when done with the fight.

        return True # Keep going

    def __quit(self):
        return False # Leave



# Main
if __name__ == '__main__':
    PP = pprint.PrettyPrinter(indent=3, width=150)
    filename = 'persephone.json' # TODO: make this a command-line argument

    # Arriving -- read our stuff
    with CaJson(filename) as world:

        # Build convenient data structures starting from:
        #   {
        #       'current': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
        #       'permanent': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
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
            main_handler = MainHandler(display, world)
            main_handler.doit()


