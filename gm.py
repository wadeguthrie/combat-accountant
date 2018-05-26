#! /usr/bin/python

import copy
import curses
import json
import pprint
import random
# import requests # Easy to use HTTP, requires Python 3

# TODO:
#   - be able to remove characters from the fight (death)
#   - notes
#   - main screen should have a 'h' heal one creature at a time
#
# TODO (eventually)
#   - make filename a command-line argument
#   - errors go to the Curses screen
#   - scrolling menus (et al.)
#   - entering monsters and characters from the screen


class GmJson(object):
    '''
    Context manager that opens and loads a JSON for combat accountant on entry
    and saves and closes it on exit.
    '''


    def __init__(self, filename):
        self.__filename = filename


    def __enter__(self):
        try:
            with open(self.__filename, 'r') as f:
              #world = json.load(f)
              world = GmJson.__json_load_byteified(f)
        except:
            # TODO: ship out an error message
            world = None
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
    def __byteify(data, ignore_dicts = False):
        # if this is a unicode string, return its string representation
        if isinstance(data, unicode):
            return data.encode('utf-8')
        # if this is a list of values, return list of byteified values
        if isinstance(data, list):
            return [ GmJson.__byteify(item,
                                      ignore_dicts=True) for item in data ]
        # if this is a dictionary, return dictionary of byteified keys and
        # values but only if we haven't already byteified it
        if isinstance(data, dict) and not ignore_dicts:
            return {
                GmJson.__byteify(key, ignore_dicts=True):
                    GmJson.__byteify(value, ignore_dicts=True)
                    for key, value in data.iteritems()
            }
        # if it's anything else, return it in its original form
        return data


    @staticmethod
    def __json_load_byteified(file_handle):
        return GmJson.__byteify(
            json.load(file_handle, object_hook=GmJson.__byteify),
            ignore_dicts=True
        )


class GmDisplay(object):
    '''
    GmDisplay addresses the graphical part of the user interface for combat
    accountant.  Here, this is provided with the Curses package.
    '''

    ESCAPE = 27 # ASCII value for the escape character

    # Foreground / background colors
    (RED_BLACK, RED_WHITE) = range(1, 3) # red text over black

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
        self.__NEXT_LINE = 2
        self.__FIGHTER_LINE = 4
        self.__FIGHTER_COL = 0
        self.__OPPONENT_COL = 0
        self.__character_window = None
        self.__opponent_window = None


    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
            curses.start_color()
            curses.noecho()
            curses.cbreak() # respond instantly to keystrokes
            self.__stdscr.keypad(1) # special characters converted by curses
                                    # (e.g., curses.KEY_LEFT)

            curses.init_pair(GmDisplay.RED_BLACK,
                             curses.COLOR_RED, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmDisplay.RED_WHITE,
                             curses.COLOR_RED, # fg
                             curses.COLOR_WHITE) # bg

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

    #
    # Public Methods
    #


    def command_ribbon(
            self,
            choices # hash: ord('f'): {'name': 'xxx', 'func': self.func}
           ):
        '''
        Draws a list of commands across the bottom of the screen
        '''

        left = 0
        line = curses.LINES - 1

        self.__stdscr.addstr(line,
                             left,
                             '|',
                             curses.A_NORMAL)
        left += 2 # adds a space

        for choice, body in choices.iteritems():
            if choice == ord(' '):
                choice_string = '" "'
            else:
                choice_string = '%c' % chr(choice)

            length = len(choice_string) + len(body['name']) + 4
            if (left + length) >= (curses.COLS - 1):
                left = 0
                line -= 1
                self.__stdscr.addstr(line,
                                     left,
                                     '|',
                                     curses.A_NORMAL)
                left += 2 # adds a space

            self.__stdscr.addstr(line,
                                 left,
                                 choice_string,
                                 curses.A_REVERSE)
            left += len(choice_string) + 1 # add a space after the choice

            self.__stdscr.addstr(line,
                                 left,
                                 body['name'],
                                 curses.A_BOLD)

            left += len(body['name']) + 1 # add a space after the choice

            self.__stdscr.addstr(line,
                                 left,
                                 '|',
                                 curses.A_NORMAL)
            left += 2 # adds a space

        self.__stdscr.refresh()


    def clear(self):
        '''Clears the screen.'''

        self.__stdscr.clear()


    def get_one_character(self,
                          window=None # Window (for Curses)
                         ):
        '''Reads one character from the keyboard.'''

        if window is None:
            window = self.__stdscr
        c = window.getch()
        # 'c' will be something like ord('p') or curses.KEY_HOME
        return c


    def get_string(self, window=None):
        '''
        Gets a complete string from the keyboard.  For Curses, you have to 
        turn off raw mode to get the string then turn it back on when you're
        done.
        '''

        # TODO(eventually): this be a mini-context manager that should get the
        # current state of cbreak and echo and set them on entry and then
        # reinstate them on exit.

        if window is None:
            window = self.__stdscr
        curses.nocbreak()
        curses.echo()
        string = window.getstr()
        curses.cbreak()
        curses.noecho()
        return string


    def input_box(self,
                  height,
                  width,
                  title
                 ):
        '''Provides a window to get input from the screen.'''

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
        '''
        Presents a menu to the user and returns the result.
        '''

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
            elif user_input == GmDisplay.ESCAPE:
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


    def round_ribbon(self,
                     round_no,
                     saved,
                     current_fighter, # use in future
                     next_fighter # use in future
                    ):
        '''Prints the fight round information at the top of the screen.'''

        self.__stdscr.move(0, 0)
        self.__stdscr.clrtoeol()

        round_string = 'Round %d' % round_no
        self.__stdscr.addstr(0, # y
                             0, # x
                             round_string,
                             curses.A_NORMAL)
        if saved:
            string = "SAVED"
            length = len(string)
            self.__stdscr.addstr(0, # y
                                 curses.COLS - (length + 1), # x
                                 string,
                                 curses.A_BOLD)
        self.__stdscr.refresh()


    def show_fighters(self,
                      current_name,
                      current_fighter,
                      opponent_name,
                      opponent,
                      next_name # name of next PC
                     ):
        '''
        Displays the current state of the current fighter and his opponent,
        if he has one.
        '''

        if next_name is not None:
            self.__stdscr.move(self.__NEXT_LINE, self.__FIGHTER_COL)
            self.__stdscr.clrtoeol()
            self.__stdscr.addstr(self.__NEXT_LINE,
                                 self.__FIGHTER_COL,
                                 '(Next: %s)' % next_name)


        self.__stdscr.move(self.__FIGHTER_LINE, self.__FIGHTER_COL)
        self.__stdscr.clrtoeol()

        self.__show_fighter(current_name, current_fighter, self.__FIGHTER_COL)
        self.__show_fighter_notes(self.__character_window, current_fighter)

        if opponent is None:
            self.__opponent_window.clear()
            self.__opponent_window.refresh()
        else:
            self.__stdscr.addstr(self.__FIGHTER_LINE,
                                 self.__OPPONENT_COL, 'vs.')
            self.__show_fighter(opponent_name,
                                opponent,
                                self.__OPPONENT_COL+4)
            self.__show_fighter_notes(self.__opponent_window, opponent)

        self.__stdscr.refresh()

    def start_fight(self):
        height = (curses.LINES          # The whole screen height, except...
            - (self.__FIGHTER_LINE+1)   # ...a block at the top, and...
            - 4)                        # ...a space for the command ribbon.
        
        width = (curses.COLS            # The screen width for...
            - (self.__OPPONENT_COL+4)   # ...the opponent...
            - 1)                        # ...minus a little margin

        top_line = self.__FIGHTER_LINE+1 # Start after the main fighter info

        self.__character_window = curses.newwin(height,
                                                width,
                                                top_line,
                                                self.__FIGHTER_COL)
        self.__opponent_window  = curses.newwin(height,
                                                width,
                                                top_line,
                                                self.__OPPONENT_COL+4)

    def stop_fight(self):
        if self.__character_window is not None:
            del self.__character_window
            self.__character_window = None

        if self.__opponent_window is not None:
            del self.__opponent_window
            self.__opponent_window = None

    #
    # Private Methods
    #


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

    def __show_fighter(self,
                       fighter_name,  # String holding name of fighter
                       fighter,       # dict holding fighter information
                       column
                      ):
        fighter_string = '%s HP: %d/%d FP: %d/%d' % (
            fighter_name,
            fighter['current']['hp'],
            fighter['permanent']['hp'],
            fighter['current']['fp'],
            fighter['permanent']['fp'])
        if fighter['current']['fp'] <= 0 or fighter['current']['hp'] <= 0:
            mode = curses.color_pair(GmDisplay.RED_BLACK)
        else:
            mode = curses.A_NORMAL

        line = self.__FIGHTER_LINE
        self.__stdscr.addstr(line, column, fighter_string, mode)


    def __show_fighter_notes(self,
                             window,  # Curses window: shows the fighter's notes
                             fighter, # The dict holding the fighter info
                            ):
        '''
        Displays ancillary information about the fighter
        '''
        window.clear()
        line = 0
        mode = curses.A_NORMAL

        # TODO: This stuff is largely rule-based

        if fighter['shock'] is not None: # Shock
            string = 'DX and IQ are at %d' % fighter['shock']
            window.addstr(line, 0, string, mode)
            line += 1

        if fighter['current']['hp'] < fighter['permanent']['hp']/3.0:
            window.addstr(line, 0, "Dodge/move are at 1/2", mode)
            line += 1

        # Each round you do something
        if fighter['current']['hp'] <= 0:
            window.addstr(line, 0, "On turn: 3d vs HT or pass out", mode)
            line += 1

        if fighter['check_for_death']:
            window.addstr(line, 0, "3d vs HT or DIE", curses.A_REVERSE)
            fighter['check_for_death'] = False  # Only show/roll once
            line += 1

        # Timers are _not_ rule based
        for timer in fighter['timers']:
            string = '%d Rounds Left: %s' % (timer['rounds'], timer['string'])
            window.addstr(line, 0, string, mode)
            line += 1

        window.refresh()


class GurpsRuleset(object):
    '''
    This is a place for all of the ruleset (e.g., GURPS, AD&D) specific
    stuff.
    '''

    @staticmethod
    def roll(number, # the number of dice
             dice,   # the type of dice
             plus=0  # a number to add to the total of the dice roll
            ):
        '''Simulates a roll of dice.'''
        result = plus
        for count in range(number):
            result += random.randint(1, dice)
        return result


    @staticmethod
    def initiative(fighter # dict for the creature as in the json file
                  ):
        return (fighter['current']['basic-speed'],
                fighter['current']['dx'],
                GurpsRuleset.roll(1, 6)
                )



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
                 world,
                 monster_list_name
                ):
        super(FightHandler, self).__init__(display)

        self._choices = {
            ord(' '): {'name': 'next', 'func': self.__next_fighter},
            ord('<'): {'name': 'prev', 'func': self.__prev_fighter},
            # TODO: 'h' and 'f' are based on the ruleset
            ord('h'): {'name': 'HP damage', 'func': self.__damage_HP},
            ord('f'): {'name': 'FP damage', 'func': self.__damage_FP},
            ord('o'): {'name': 'opponent', 'func': self.__pick_opponent},
            ord('t'): {'name': 'timer', 'func': self.__timer},
            ord('q'): {'name': 'quit', 'func': self.__quit},
            ord('s'): {'name': 'save', 'func': self.__save}
        }

        self.__world = world
        self.__fight = world["current-fight"]

        if not self.__fight['saved']:
            self.__fight['round'] = 0
            self.__fight['index'] = 0
            self.__fight['monsters'] = monster_list_name

            self.__fight['fighters'] = [] # list of [list, name] in init order
            self.__fight['fighters'].extend(['PCs', name] for name in
                    world['PCs'].keys())
            if monster_list_name is not None:
                self.__fight['fighters'].extend(
                        [monster_list_name, name] for name in
                         self.__world['monsters'][monster_list_name].keys())

            # Sort by initiative = basic-speed followed by DEX followed by
            # random
            # TODO: there should be a random value for equal initiatives
            self.__fight['fighters'].sort(key=lambda fighter: 
                    GurpsRuleset.initiative(self.__fighter(fighter[0],
                                                           fighter[1])),
                    reverse=True)

            # Make sure this looks like a _NEW_ fight.
            for fighter_info in self.__fight['fighters']:
                fighter = self.__fighter(fighter_info[0], fighter_info[1])
                fighter['opponent'] = None
                fighter['shock'] = None

        self.__fight['saved'] = False
        self._display.start_fight()

    def doit(self):
        super(FightHandler, self).doit()
        if not self.__fight['saved']:
            self.__world['dead-monsters'][self.__fight['monsters']] = (
                    self.__world['monsters'][self.__fight['monsters']])
            del(self.__world['monsters'][self.__fight['monsters']])

    def __current_fighter(self):
        index = self.__fight['index']
        return (self.__fight['fighters'][index][1],
                self.__fighter(self.__fight['fighters'][index][0], # group
                               self.__fight['fighters'][index][1])) # name


    def __damage_FP(self):
        current_name, current_fighter = self.__current_fighter()
        next_PC = self.__next_PC()
        opponent_name, opponent = self.__opponent(current_fighter)
        if opponent is not None:
            title = 'Change FP By...'
            height = 1
            width = len(title)
            adj_string = self._display.input_box(height, width, title)
            adj = int(adj_string)
            opponent['current']['fp'] += adj # TODO: this should be in rules
            self._display.show_fighters(current_name, current_fighter,
                                        opponent_name, opponent,
                                        next_PC)
        return True # Keep going


    def __damage_HP(self):
        current_name, current_fighter = self.__current_fighter()
        next_PC = self.__next_PC()
        opponent_name, opponent = self.__opponent(current_fighter)
        if opponent is not None:
            title = 'Change HP By...'
            height = 1
            width = len(title)
            adj_string = self._display.input_box(height, width, title)
            adj = int(adj_string)

            # TODO: check for death is rule-based
            if adj < 0 and opponent['current']['hp'] < 0:
                before_hp = opponent['current']['hp']
                before_hp_multiple = before_hp / opponent['permanent']['hp']
                after_hp = (opponent['current']['hp'] + adj) * 1.0 + 0.1
                after_hp_multiple = after_hp / opponent['permanent']['hp']
                if int(before_hp_multiple) != int(after_hp_multiple):
                    opponent['check_for_death'] = True

            # TODO: shock is rule-based
            shock_amount = -4 if adj <= -4 else adj
            if opponent['shock'] is None or opponent['shock'] > shock_amount:
                opponent['shock'] = shock_amount

            opponent['current']['hp'] += adj # TODO: this should be in rules
            self._display.show_fighters(current_name, current_fighter,
                                        opponent_name, opponent,
                                        next_PC)
        return True # Keep going


    def _draw_screen(self):
        self._display.clear()
        current_name, current_fighter = self.__current_fighter()
        next_PC = self.__next_PC()
        opponent_name, opponent = self.__opponent(current_fighter)
        self._display.round_ribbon(self.__fight['round'],
                                   self.__fight['saved'],
                                   current_fighter, # up now
                                   None) #self.xxx) # next PC
        self._display.show_fighters(current_name, current_fighter,
                                    opponent_name, opponent,
                                    next_PC)
        self._display.command_ribbon(self._choices)


    def __fighter(self,
                  group, # 'PCs' or some group under world['monsters']
                  name   # name of a fighter in the aforementioned group
                 ):
        return (self.__world['PCs'][name] if group == 'PCs' else
                self.__world['monsters'][group][name])


    def __next_fighter(self):
        # TODO: shock is rule-set
        prev_name, prev_fighter = self.__current_fighter()
        prev_fighter['shock'] = None # remove expired shock entry

        # remove any expired timers
        remove_these = []
        for index, timer in enumerate(prev_fighter['timers']):
            if timer['rounds'] <= 0:
                remove_these.insert(0, index) # largest indexes last
        for index in remove_these:
            del prev_fighter['timers'][index]

        self.__fight['index'] += 1
        if self.__fight['index'] >= len(self.__fight['fighters']):
            self.__fight['index'] = 0
            self.__fight['round'] += 1
        self._display.round_ribbon(self.__fight['round'],
                                   self.__fight['saved'],
                                   None, # current fighter
                                   None) # next PC
        current_name, current_fighter = self.__current_fighter()
        for timer in current_fighter['timers']:
            timer['rounds'] -= 1
        next_PC = self.__next_PC()
        opponent_name, opponent = self.__opponent(current_fighter)
        self._display.show_fighters(current_name, current_fighter,
                                    opponent_name, opponent,
                                    next_PC)
        return True # Keep going

    def __next_PC(self):
        next_PC = None
        next_index = self.__fight['index'] + 1
        for ignore in self.__fight['fighters']:
            if next_index >= len(self.__fight['fighters']):
                next_index = 0
            if self.__fight['fighters'][next_index][0] == 'PCs':
                next_PC = self.__fight['fighters'][next_index][1]
                break
            next_index += 1
        # TODO: perhaps I should check if next PC is active
        return next_PC


    def __opponent(self,
                   fighter # dict for a fighter as in the JSON
                  ):
        opponent_name = None
        opponent = None
        if fighter is not None and fighter['opponent'] is not None:
            opponent_name = fighter['opponent'][1]
            opponent = self.__fighter(fighter['opponent'][0],
                                      fighter['opponent'][1])
        return opponent_name, opponent


    def __pick_opponent(self):
        current_name, current_fighter = self.__current_fighter()
        next_PC = self.__next_PC()
        current_index = self.__fight['index']
        current_group = self.__fight['fighters'][current_index][0]
        current_name  = self.__fight['fighters'][current_index][1]

        opponent_group = None
        opponent_menu = []
        for fighter in self.__fight['fighters']:
            if fighter[0] != current_group:
                opponent_group = fighter[0]
                opponent_menu.append((fighter[1], fighter[1]))
        opponent_name = self._display.menu('Opponent', opponent_menu)

        if opponent_name is not None:
            current_fighter['opponent'] = [opponent_group, opponent_name]

        opponent = self.__fighter(opponent_group, opponent_name)

        # Ask to have them fight each other
        if opponent is not None and opponent['opponent'] is None:
            back_menu = [('Yes', True), ('No', False)]
            answer = self._display.menu('Make Opponents Go Both Ways',
                                        back_menu)
            if answer == True:
                opponent['opponent'] = [current_group, current_name]

        self._display.show_fighters(current_name, current_fighter,
                                    opponent_name, opponent,
                                    next_PC)
        return True # Keep going


    def __prev_fighter(self):
        if self.__fight['index'] == 0 and self.__fight['round'] == 0:
            return True # Not going backwards from the origin

        self.__fight['index'] -= 1
        if self.__fight['index'] < 0:
            self.__fight['index'] = len(self.__fight['fighters']) - 1
            self.__fight['round'] -= 1
        # TODO: maybe combine the following two
        self._display.round_ribbon(self.__fight['round'],
                                   self.__fight['saved'],
                                   None, # current fighter
                                   None) # next PC
        current_name, current_fighter = self.__current_fighter()
        next_PC = self.__next_PC()
        opponent_name, opponent = self.__opponent(current_fighter)
        self._display.show_fighters(current_name, current_fighter,
                                    opponent_name, opponent,
                                    next_PC)
        return True # Keep going


    def __quit(self):
        self._display.stop_fight()
        return False # Leave the fight

    def __save(self):
        self.__fight['saved'] = True
        self._display.round_ribbon(self.__fight['round'],
                                   self.__fight['saved'],
                                   None, # up now
                                   None) #self.xxx) # next PC
        return True # Keep going

    def __timer(self):
        '''
        Asks user for information for timer to add to fighter.
        '''
        timer = {'rounds': 0, 'string': None}

        title = 'Rounds To Wait...'
        height = 1
        width = len(title)
        adj_string = self._display.input_box(height, width, title)
        timer['rounds'] = int(adj_string)
        if timer['rounds'] < 1:
            return True # Keep fighting (even without installing the timer)

        title = 'What happens in %d rounds?' % timer['rounds']
        height = 1
        width = curses.COLS - 4
        timer['string'] = self._display.input_box(height, width, title)

        if timer['string'] is not None and len(timer['string']) != 0:
            current_name, current_fighter = self.__current_fighter()
            current_fighter['timers'].append(timer)

        return True # Keep fighting


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
        for character in self.__world['PCs'].itervalues():
            for stat in character['permanent'].iterkeys():
                character['current'][stat] = character['permanent'][stat]
            character['shock'] = None
            character['check_for_death'] = False
        return True


    def __new_fight(self):
        fight_name_menu = [(name, name)
                           for name in self.__world['monsters'].keys()]
        # PP.pprint(fight_name_menu)
        monster_list_name = self._display.menu('Fights', fight_name_menu)
        if monster_list_name is None:
            return True
        print "MENU RESULT=%s" % monster_list_name  # For debugging

        if (monster_list_name is None or
                monster_list_name not in self.__world['monsters']):
            print "ERROR, monster list %s not found" % monster_list_name

        # NOTE: this makes the displays recursive (though, the implementation
        # only makes the code recursive but the actual screens will just get
        # reused).
        fight = FightHandler(self._display,
                             self.__world,
                             monster_list_name)
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
    with GmJson(filename) as world:

        # Build convenient data structures starting from:
        #   'groucho': {
        #       'current': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
        #       'permanent': { 'fp': 10, 'hp': 10, 'basic-speed': 1 }, 
        #       'opponent': ['PCs', 'Foo'] # group, name
        #   }, 

        # Error checking for JSON

        if 'PCs' not in world:
            #display.Error('No "PCs" in %s' % filename)
            print 'No "PCs" in %s' % filename # TODO: dump when display

        # Enter into the mainloop
        with GmDisplay() as display:
            main_handler = MainHandler(display, world)
            if world['current-fight']['saved']:
                fight_handler = FightHandler(display,
                                             world,
                                             None)
                fight_handler.doit()
            main_handler.doit()


