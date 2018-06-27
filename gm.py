#! /usr/bin/python

import argparse
import copy
import curses
import curses.textpad
import datetime
import json
import os
import pprint
import random
import sys

# TODO:
#   - add explanation for to-hit, damage, and active defense rolls
#   - dodge and drop (B377)
#   - add outfit characters and a store for weapons and other items
#   - damage other than dice
#   - < 1/3 FP = 1/2 move, dodge, st
#   - Warning if window is smaller than expected
#   - Update the Templates in the JSON to match the character data
#   - Add book references in more places
#
# TODO (eventually)
#   - scrolling menus (et al.)
#   - entering monsters and characters from the screen
#   - truncate (don't wrap) long lines
#   - Go for a transactional model -- will allow me to do better debugging,
#       playback of debug stuff, and testing.  Instead of modifying 'world'
#       directly, issue a transaction to an object that handles world.  Save
#       the transaction to _history.
#   - Optimize the way I'm using curses.  I'm willy-nilly touching and
#     redrawing everything way more often than I should.  Turns out, it's not
#     costing me much but it's ugly, none-the-less


class GmJson(object):
    '''
    Context manager that opens and loads a JSON.  Does so in a context manager
    and does all this in ASCII (for v2.7 Python).  Needs to know about
    a window manager.
    '''

    def __init__(self,
                 filename,             # file containing the JSON to be read
                 window_manager = None # send error messages here
                ):
        self.__filename = filename
        self.__window_manager = window_manager
        self.read_data = None
        self.write_data = None


    def __enter__(self):
        try:
            with open(self.__filename, 'r') as f:
              self.read_data = GmJson.__json_load_byteified(f)
        except:
            if self.__window_manager is not None:
                        
                self.__window_manager.error(['Could not read JSON file "%s"' %
                                                self.__filename])
            self.read_data = None
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

        if self.write_data is not None:
            with open(self.__filename, 'w') as f:
                json.dump(self.write_data, f, indent=2)
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

'''
How to use this GUI.

You need an XxxHandler object to handle the business logic:
    class XxxHandler(ScreenHandler):

And an XxxGmWindow to do the actual window manipulation:
    class XxxGmWindow(GmWindow):

The XxxHandler is handed a WindowManager object which it uses to instantiate
an XxxGmWindow.

    class XxxHandler(ScreenHandler):
        def __init__(self, window_manager, ...):
            super(XxxHandler, self).__init__(window_manager)
            self._choices = {
                ord('f'): {'name': 'fight (run)', 'func': self.__run_fight},
                ord('H'): {'name': 'Heal',  'func': self.__fully_heal},
                ord('q'): {'name': 'quit',  'func': self.__quit}
            }
            self._window = XxxGmWindow(self._window_manager)


And, then, invoke like so:

    xxx_handler = XxxHandler(self._window_manager, ...)
    xxx_handler.handle_user_input_until_done()
    self._draw_screen() # Redraw current screen when done with XxxHandler

'''

class GmWindow(object):
    '''
    Generic window for the GM tool.
    '''
    def __init__(self,
                 window_manager, # A GmWindowManager object
                 # Using curses screen addressing w/0,0 in upper left corner
                 height,
                 width,
                 top_line,
                 left_column):
        self._window_manager = window_manager
        # Don't need to save the window location and size because:
        #   window.getbegyx()
        #   window.getmaxyx()
        # both return a (y, x) tuple to solve this
        self._window = self._window_manager.new_native_window(height,
                                                              width,
                                                              top_line,
                                                              left_column)
        self._window_manager.push_gm_window(self)


    def clear(self):
        '''Clears the screen.'''
        self._window.clear()


    def close(self):
        '''
        Explicit destructor because Python is broken when it comes to
        destructors.
        '''
        self._window_manager.pop_gm_window(self)
        del self._window                   # kill ourselves
        self._window_manager.refresh_all() # refresh everything else
        return True


    def command_ribbon(
            self,
            choices # hash: ord('f'): {'name': 'xxx', 'func': self.func}
           ):
        '''
        Draws a list of commands across the bottom of the screen
        '''

        # Build the choice strings

        max_width = 0
        choice_strings = []
        for command, body in choices.iteritems():
            if command == ord(' '):
                command_string = '" "'
            else:
                command_string = '%c' % chr(command)

            choice_text = {'bar': '| ',
                           'command': ('%s' % command_string),
                           'body': (' %s ' % body['name'])
                          }
            choice_strings.append(choice_text)
            choice_string = '%s%s%s' % (choice_text['bar'],
                                        choice_text['command'],
                                        choice_text['body'])
            if max_width < len(choice_string):
                max_width = len(choice_string)

        # Calculate the number of rows needed for all the commands

        lines, cols = self._window.getmaxyx()
        choices_per_line = int((cols - 1)/max_width) # -1 for last '|'
        # Adding 0.9999 so last partial line doesn't get truncated by 'int'
        lines_for_choices = int((len(choices) / (choices_per_line + 0.0))
                                                                + 0.9999999)

        # Print stuff out

        choice_strings.sort(reverse=True, key=lambda s: s['command'].lower())
        line = lines - 1 # -1 because last line is lines-1
        for subline in reversed(range(lines_for_choices)):
            line = lines - (subline + 1) # -1 because last line is lines-1
            left = 0
            for i in range(choices_per_line):
                if len(choice_strings) == 0:
                    self._window.addstr(line, left, '|', curses.A_NORMAL)
                else:
                    choice_text = choice_strings.pop()
                    my_left = left
                    self._window.addstr(line,
                                        my_left,
                                        choice_text['bar'],
                                        curses.A_NORMAL)
                    my_left += len(choice_text['bar'])
                    self._window.addstr(line,
                                        my_left,
                                        choice_text['command'],
                                        curses.A_REVERSE)
                    my_left += len(choice_text['command'])
                    self._window.addstr(line,
                                        my_left,
                                        choice_text['body'],
                                        curses.A_BOLD)
                left += max_width
            self._window.addstr(line, left, '|', curses.A_NORMAL)
        self.refresh()


    def getmaxyx(self):
        return self._window.getmaxyx()

    def refresh(self):
        self._window.refresh()


    def touchwin(self):
        self._window.touchwin()


class MainGmWindow(GmWindow):
    def __init__(self, window_manager):
        super(MainGmWindow, self).__init__(window_manager,
                                           curses.LINES,
                                           curses.COLS,
                                           0,
                                           0)


class BuildFightGmWindow(GmWindow):
    def __init__(self, window_manager):
        super(BuildFightGmWindow, self).__init__(window_manager,
                                                 curses.LINES,
                                                 curses.COLS,
                                                 0,
                                                 0)
        lines, cols = self._window.getmaxyx()
        self.__monster_window = self._window_manager.new_native_window(
                                                                    lines - 4,
                                                                    cols / 2,
                                                                    1,
                                                                    1)

    def close(self):
        # Kill my subwindows, first
        if self.__monster_window is not None:
            del self.__monster_window
            self.__monster_window = None
        super(BuildFightGmWindow, self).close()


    def refresh(self):
        super(BuildFightGmWindow, self).refresh()
        if self.__monster_window is not None:
            self.__monster_window.refresh()


    def show_monsters(self, name, monsters):
        if self.__monster_window is not None:
            self.__monster_window.clear()
            mode = curses.A_NORMAL
            for line, monster_name in enumerate(monsters):
                self.__monster_window.addstr(line, 0, monster_name, mode)

        self.refresh()

    #
    # Private methods
    #

    def __quit(self):
        self._window.close()
        del self._window
        self._window = None
        return False # Leave


class FightGmWindow(GmWindow):
    def __init__(self, window_manager, ruleset):
        super(FightGmWindow, self).__init__(window_manager,
                                           curses.LINES,
                                           curses.COLS,
                                           0,
                                           0)
        self.__ruleset = ruleset
        self.__pane_width = curses.COLS / 3 # includes margin
        self.__margin_width = 2

        self.__FIGHTER_COL = 0
        self.__OPPONENT_COL = self.__pane_width
        self.__SUMMARY_COL = 2 * self.__pane_width

        self.__FIGHTER_LINE = 3
        self.__NEXT_LINE = 1

        self.__character_window = None
        self.__opponent_window = None
        self.__summary_window = None
        self.fighter_win_width = 0
        self.__round_count_string = '%d Rnds: '
        # assume rounds takes as much space as '%d' 
        self.len_timer_leader = len(self.__round_count_string)

        self.__state_color = {
                Fighter.ALIVE :
                    curses.color_pair(GmWindowManager.GREEN_BLACK),
                Fighter.INJURED :
                    curses.color_pair(GmWindowManager.YELLOW_BLACK),
                Fighter.UNCONSCIOUS :
                    curses.color_pair(GmWindowManager.RED_BLACK),
                Fighter.DEAD :
                    curses.color_pair(GmWindowManager.RED_BLACK),
        }

    def close(self):
        # Kill my subwindows, first
        if self.__character_window is not None:
            del self.__character_window
            self.__character_window = None
        if self.__opponent_window is not None:
            del self.__opponent_window
            self.__opponent_window = None
        if self.__summary_window is not None:
            del self.__summary_window
            self.__summary_window = None
        super(FightGmWindow, self).close()


    def refresh(self):
        super(FightGmWindow, self).refresh()
        if self.__character_window is not None:
            self.__character_window.refresh()
        if self.__opponent_window is not None:
            self.__opponent_window.refresh()
        if self.__summary_window is not None:
            self.__summary_window.refresh()


    def round_ribbon(self,
                     round_no,
                     saved,
                     next_PC_name
                    ):
        '''Prints the fight round information at the top of the screen.'''

        self._window.move(0, 0)
        self._window.clrtoeol()
        lines, cols = self._window.getmaxyx()

        round_string = 'Round %d' % round_no
        self._window.addstr(0, # y
                            0, # x
                            round_string,
                            curses.A_NORMAL)

        if saved:
            string = 'SAVED'
            length = len(string)
            self._window.addstr(0, # y
                                cols - (length + 1), # x
                                string,
                                curses.A_BOLD)

        if next_PC_name is not None:
            self._window.move(self.__NEXT_LINE, 0)
            self._window.clrtoeol()
            mode = curses.color_pair(GmWindowManager.MAGENTA_BLACK)
            mode = mode | curses.A_BOLD
            self._window.addstr(self.__NEXT_LINE,
                                0,
                                ('Next PC: %s' % next_PC_name),
                                mode)

        self._window.refresh()


    def show_fighters(self,
                      current_fighter,  # Fighter object
                      opponent,         # Fighter object
                      fighters,
                      current_index
                     ):
        '''
        Displays the current state of the current fighter and his opponent,
        if he has one.
        '''

        self._window.move(self.__FIGHTER_LINE, self.__FIGHTER_COL)
        self._window.clrtoeol()

        if self.__show_fighter(current_fighter, self.__FIGHTER_COL):
            self.__show_fighter_notes(current_fighter,
                                      is_attacker=True,
                                      window=self.__character_window)

        if opponent is None:
            self.__opponent_window.clear()
            self.__opponent_window.refresh()
        else:
            if self.__show_fighter(opponent, self.__OPPONENT_COL):
                self.__show_fighter_notes(opponent,
                                          is_attacker=False,
                                          window=self.__opponent_window)
        self.__show_summary_window(fighters, current_index)
        self.refresh()


    def __show_summary_window(self,
                              fighters,  # array of <Fighter object>
                              current_index,
                              selected_index=None):
        self.__summary_window.clear()
        for line, fighter in enumerate(fighters):
            mode = self.__state_color[fighter.get_state()]
            fighter_string = '%s%s HP:%d/%d' % (
                                ('> ' if line == current_index else '  '),
                                fighter.name,
                                fighter.details['current']['hp'],
                                fighter.details['permanent']['hp'])


            if selected_index is not None and selected_index == line:
                mode = mode | curses.A_REVERSE
            elif fighter.group == 'PCs':
                mode = mode | curses.A_BOLD
            self.__summary_window.addstr(line, 0, fighter_string, mode)

    def start_fight(self):
        lines, cols = self._window.getmaxyx()
        height = (lines                 # The whole window height, except...
            - (self.__FIGHTER_LINE+1)   # ...a block at the top, and...
            - 4)                        # ...a space for the command ribbon.
        
        self.fighter_win_width = self.__pane_width - self.__margin_width

        top_line = self.__FIGHTER_LINE+1 # Start after the main fighter info

        self.__character_window = self._window_manager.new_native_window(
                                                height,
                                                self.fighter_win_width,
                                                top_line,
                                                self.__FIGHTER_COL)
        self.__opponent_window  = self._window_manager.new_native_window(
                                                height,
                                                self.__pane_width -
                                                        self.__margin_width,
                                                top_line,
                                                self.__OPPONENT_COL)
        self.__summary_window   = self._window_manager.new_native_window(
                                                height,
                                                self.__pane_width -
                                                        self.__margin_width,
                                                top_line,
                                                self.__SUMMARY_COL)


    def touchwin(self):
        super(FightGmWindow, self).touchwin()
        if self.__character_window is not None:
            self.__character_window.touchwin()
        if self.__opponent_window is not None:
            self.__opponent_window.touchwin()
        if self.__summary_window is not None:
            self.__summary_window.touchwin()

    #
    # Private Methods
    #

    def __show_fighter(self,
                       fighter, # Fighter object
                       column
                      ):
        show_more_info = True # conscious -- show all the fighter's info
        fighter_state = fighter.get_state()
        if fighter_state == Fighter.DEAD:
            fighter_string = '(DEAD)'
            show_more_info = False
        elif fighter_state == Fighter.UNCONSCIOUS:
            fighter_string = '(UNCONSCIOUS)'
            show_more_info = False
        else:
            fighter_string = '%s HP: %d/%d FP: %d/%d' % (
                                        fighter.name,
                                        fighter.details['current']['hp'],
                                        fighter.details['permanent']['hp'],
                                        fighter.details['current']['fp'],
                                        fighter.details['permanent']['fp'])

        mode = self.__state_color[fighter_state] | curses.A_BOLD
        self._window.addstr(self.__FIGHTER_LINE, column, fighter_string, mode)
        return show_more_info


    def __show_fighter_notes(self,
                             fighter,           # Fighter object
                             is_attacker,       # True | False
                             window             # Curses window for fighter's
                                                #   notes
                            ):
        '''
        Displays ancillary information about the fighter
        '''
        window.clear()
        line = 0

        # Defender

        if is_attacker:
            mode = curses.A_NORMAL 
        else:
            mode = curses.color_pair(GmWindowManager.CYAN_BLACK)
            mode = mode | curses.A_BOLD

        notes, why = self.__ruleset.get_fighter_defenses_notes(fighter)
        for note in notes:
            window.addstr(line, 0, note, mode)
            line += 1

        # Attacker

        if is_attacker:
            mode = curses.color_pair(GmWindowManager.CYAN_BLACK)
            mode = mode | curses.A_BOLD
        else:
            mode = curses.A_NORMAL 
        notes = self.__ruleset.get_fighter_to_hit_damage_notes(fighter)
        for note in notes:
            window.addstr(line, 0, note, mode)
            line += 1

        # now, back to normal
        mode = curses.A_NORMAL
        notes = self.__ruleset.get_fighter_notes(fighter)
        for note in notes:
            window.addstr(line, 0, note, mode)
            line += 1

        # Timers
        for timer in fighter.details['timers']:
            round_count_string = self.__round_count_string % timer['rounds']
            if type(timer['string']) is list:
                for i, substring in enumerate(timer['string']):
                    string = substring if i != 0 else (
                        '%s%s' % (round_count_string, substring))
                    window.addstr(line, 0, string, mode)
                    line += 1
            else:
                string = '%s%s' % (round_count_string, timer['string'])
                window.addstr(line, 0, string, mode)
                line += 1

        if 'notes' in fighter.details and fighter.details['notes'] is not None:
            for note in fighter.details['notes'].split('\n'):
                window.addstr(line, 0, note, mode)
                line += 1

        window.refresh()


class GmWindowManager(object):
    '''
    GmWindowManager addresses the graphical part of the user interface for
    gm.py.  Here, this is provided with the Curses package.
    '''

    ESCAPE = 27 # ASCII value for the escape character

    # Foreground / background colors
    (RED_BLACK,
     GREEN_BLACK,   # green text over black background
     YELLOW_BLACK,
     BLUE_BLACK,
     MAGENTA_BLACK,
     CYAN_BLACK,
     WHITE_BLACK,
     
     RED_WHITE) = range(1, 9)

    # NOTE: remember to call win.refresh()
    # win.addstr(y, x, 'String', attrib)
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
        self.__window_stack = [] # Stack of GmWindow


    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.noecho()
            curses.cbreak() # respond instantly to keystrokes
            self.__stdscr.keypad(1) # special characters converted by curses
                                    # (e.g., curses.KEY_LEFT)

            # Setup some defaults before I overwrite any

            # An experiment showed that there are only 16 colors in the
            # Windows console that I was running.  They are
            # 0:black, 1:red, 2:green, 3:yellow, 4:blue, 5:magenta, 6:cyan,
            # 7:white, and (I think) the dark versions of those.
            for i in range(0, curses.COLORS):
                curses.init_pair(i+1,   # New ID for color pair
                                 i,     # Specified foreground color
                                 -1     # Default background
                                )

            curses.init_pair(GmWindowManager.RED_BLACK,
                             curses.COLOR_RED, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.GREEN_BLACK,
                             curses.COLOR_GREEN, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.YELLOW_BLACK,
                             curses.COLOR_YELLOW, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.BLUE_BLACK,
                             curses.COLOR_BLUE, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.MAGENTA_BLACK,
                             curses.COLOR_MAGENTA, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.CYAN_BLACK,
                             curses.COLOR_CYAN, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.WHITE_BLACK,
                             curses.COLOR_WHITE, # fg
                             curses.COLOR_BLACK) # bg

            self.__stdscr.clear()
            self.__stdscr.refresh()
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

    def edit_window(self,
                    height, width,
                    contents,  # initial string (w/ \n) for the window
                    title,
                    footer
                   ):

        border_win, edit_win = self.__centered_boxed_window(height, width,
                                                            title)
        if footer is not None:
            footer_start = ((width+2) - (len(footer))) / 2
            border_win.addstr((height+1), footer_start, footer)
            border_win.refresh()
            edit_win.refresh()

        if contents is not None:
            for line, string in enumerate(contents.split('\n')):
                edit_win.addstr(line, 0, string, curses.A_NORMAL)
        textbox = curses.textpad.Textbox(edit_win, insert_mode=True)
        contents = textbox.edit()

        del border_win
        del edit_win
        self.hard_refresh_all()
        return contents

    def error(self,
              strings, # array of single-line strings
              title=' ERROR '
             ):
        '''Provides an error to the screen.'''

        mode = curses.color_pair(GmWindowManager.RED_WHITE)
        width = max(len(string) for string in strings)
        if width < len(title):
            width = len(title)
        width += 2 # Need some margin
        border_win, error_win = self.__centered_boxed_window(len(strings)+2,
                                                             width,
                                                             title,
                                                             mode)
        for line, string in enumerate(strings):
            #print 'line %r string %r (len=%d)' % (line, string, len(string))
            error_win.addstr(line+1, 1, string, mode)
        error_win.refresh()

        ignored = self.get_one_character()
        #ignored = self.get_string(error_win)

        del border_win
        del error_win
        self.hard_refresh_all()
        return string

    def get_fight_gm_window(self, ruleset):
        return FightGmWindow(self, ruleset)

    def getmaxyx(self):
        return curses.LINES, curses.COLS

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


    def hard_refresh_all(self):
        '''
        Touches and refreshes all of the windows, from back to front
        '''
        for window in self.__window_stack:
            window.touchwin()

        for window in self.__window_stack:
            window.refresh()


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
        self.hard_refresh_all()
        return string
    

    def menu(self,
             title,
             strings_results, # array of tuples (string, return value)
             starting_index = 0 # Who is selected when the menu starts
            ):
        '''
        Presents a menu to the user and returns the result.
        '''

        # TODO: doesn't handle more entries that would fit on screen

        # height and width of text box (not border)
        height = len(strings_results)
        max_height = curses.LINES - 2 # 2 for the box
        if height > max_height:
            height = max_height
        width = 0 if title is None else len(title)
        for string, result in strings_results:
            if len(string) > width:
                width = len(string)
        width += 1 # Seems to need one more space (or Curses freaks out)

        border_win, menu_win = self.__centered_boxed_window(height, width,
                                                            title)

        index = 0 if starting_index >= len(strings_results) else starting_index
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
                self.hard_refresh_all()
                return strings_results[index][1]
            elif user_input == GmWindowManager.ESCAPE:
                del border_win
                del menu_win
                self.hard_refresh_all()
                return None
            else:
                # Look for a match and return the selection
                for index, entry in enumerate(strings_results):
                    # (string, return value)
                    if user_input == ord(entry[0][0]): # 1st char of the string
                        del border_win
                        del menu_win
                        self.hard_refresh_all()
                        return strings_results[index][1]

            if new_index != index:
                old_index = index
                if new_index < 0:
                    index = height-1
                elif new_index >= height:
                    index = 0
                else:
                    index = new_index

                #print 'INDEX - old:%d, new:%d, final:%d' % (old_index,
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


    def new_native_window(self,
                          height=None,
                          width=None, # window size
                          top_line=0,
                          left_column=0 # window placement
                         ):
        '''
        Returns native-typed window (a curses window, in this case).
        '''

        # Doing this because I can't use curses.LINES in the autoassignment
        if height is None:
            height=curses.LINES
        if width is None:
            width=curses.COLS

        window = curses.newwin(height, width, top_line, left_column)
        return window


    def push_gm_window(self, window):
        self.__window_stack.append(window)


    def pop_gm_window(self, delete_this_window):
        top_window = self.__window_stack[-1]
        for index, window in enumerate(self.__window_stack):
            if window is delete_this_window:
                del self.__window_stack[index]
                return

        print 'ERROR: could not find window %r' % window


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


    def refresh_all(self):
        '''
        Refreshes all of the windows, from back to front
        '''
        for window in self.__window_stack:
            window.refresh()


    #
    # Private Methods
    #

    def __centered_boxed_window(self,
                                height, # height of INSIDE window
                                width, # width of INSIDE window
                                title,
                                mode=curses.A_NORMAL
                               ):
        '''
        Creates a temporary window, on top of the current one, that is
        centered and has a box around it.
        '''

        # x and y of text box (not border)
        begin_x = (curses.COLS / 2) - (width/2)
        begin_y = (curses.LINES / 2) - (height/2)

        #print 'c h:%d, w:%d, y:%d, x:%d' % (
        #    height+2, width+2, begin_y-1, begin_x-1)

        border_win = curses.newwin(height+2, width+2, begin_y-1, begin_x-1)
        border_win.border()

        if title is not None:
            title_start = ((width + 2) - (len(title))) / 2
            border_win.addstr(0, title_start, title)
        border_win.refresh()

        menu_win = curses.newwin(height, width, begin_y, begin_x)
        menu_win.bkgd(' ', mode)

        return border_win, menu_win



class Fighter(object):
    # Injured is separate since it's tracked by HP
    (ALIVE,
     UNCONSCIOUS,
     DEAD,
     STATES,
     INJURED) = range(5)

    # TODO: there are some rules-based things in here and they need to go
    conscious_map = {
        'alive': ALIVE,
        'unconscious': UNCONSCIOUS,
        'dead': DEAD
    }

    def __init__(self,
                 name,              # string
                 group,             # string = 'PCs' or some monster group
                 fighter_details,   # dict as in the JSON
                 ruleset            # a Ruleset object
                ):
        self.name = name
        self.group = group
        self.details = fighter_details
        self.__ruleset = ruleset


    def add_timer(self, rounds, text):
        self.details['timers'].append({'rounds': rounds, 'string': text})

    def bump_consciousness(self):
        '''
        Increments (modulo size) the state of the fighter.
        '''
        conscious_number = Fighter.conscious_map[self.details['state']]
        conscious_number += 1
        if conscious_number >= Fighter.STATES:
            conscious_number = 0

        for state_name, state_num in Fighter.conscious_map.iteritems():
            if state_num == conscious_number:
                self.details['state'] = state_name
                break

    def do_aim(self,
               braced   # True | False
              ):
        rounds = self.details['aim']['rounds']
        if rounds == 0:
            self.details['aim']['braced'] = braced
            self.details['aim']['rounds'] = 1
        elif rounds < 3:
            self.details['aim']['rounds'] += 1

    def get_state(self):
        conscious_number = Fighter.conscious_map[self.details['state']]
        if (conscious_number == Fighter.ALIVE and 
                self.details['current']['hp'] <
                    self.details['permanent']['hp']):
            return Fighter.INJURED
        return conscious_number

    def is_conscious(self):
        # NOTE: 'injured' is not stored in self.details['state']
        return True if self.details['state'] == 'alive' else False

    def is_dead(self):
        return True if self.details['state'] == 'dead' else False


    def reset_aim(self):
        self.details['aim']['rounds'] = 0
        self.details['aim']['braced'] = False


    def draw_weapon_by_index(self,
                             index  # Index of weapon in fighter's 'stuff'
                                    # list.  'None' removes current weapon.
                            ):
        '''Draws or removes weapon from sheath or holster.'''
        self.details['weapon-index'] = index


    def get_weapon_by_name(self,
                           name
                          ):
        '''
        Remove weapon from sheath or holster.

        Returns index, item
        '''
        for index, item in enumerate(self.details['stuff']):
            if item['name'] == name:
                self.details['weapon-index'] = index
                return index, item
        return None, None # didn't find one


    def get_current_weapon(self):
        weapon_index = self.details['weapon-index']
        if weapon_index is None:
            return None, None
        return self.details['stuff'][weapon_index], weapon_index


class Ruleset(object):
    '''
    Any ruleset's character's dict is expected to include the following:
    {
        'state' : 'alive' | 'unconscious' | 'dead'
        'opponent': None | <index into current fight's monster list or, if
                            this is for a monster, index into PC list>
        'stuff' : [ <weapon, armor, items> ],
            The format of 'stuff' contents is ruleset-specific
        'timers': [ <list of timers> ],
        'weapon-index': None | <index into 'stuff'>,
    }

    Timer looks like:
    {
        'rounds': rounds,
        'string': text
    }
    '''

    def __init__(self, window_manager):
        self._window_manager = window_manager

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

    def adjust_hp(self,
                  fighter,  # Fighter object
                  adj       # the number of HP to gain or lose
                 ):
        fighter.details['current']['hp'] += adj


    def heal_fighter(self,
                     fighter_details    # 'details' is OK, here
                    ):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        for stat in fighter_details['permanent'].iterkeys():
            fighter_details['current'][stat] = (
                                        fighter_details['permanent'][stat])
        fighter_details['state'] = 'alive'

    def new_fight(self, fighter):
        '''Removes all the stuff from the old fight except injury.'''
        # NOTE: we're allowing health to still be messed-up, here
        fighter.details['alive'] = True
        fighter.details['timers'] = []
        fighter.details['weapon-index'] = None
        fighter.details['opponent'] = None


class GurpsRuleset(Ruleset):
    '''
    This is a place for all of the ruleset (e.g., GURPS, AD&D) specific
    stuff.

    In addition to what's required by 'Ruleset', each character's dict is
    expected to look like this:
    {
        'aim': {'rounds': <number>, 'braced': True | False}
        'shock': <number, 0 for 'None'>
        'dodge' : <final dodge value (including things like 'Enhanced Dodge'>
        'skills': { <skill name> : <final skill value>, ...}
        'current': { <attribute name> : <final attribute value>, ... }
            These are: 'fp', 'hp', 'iq', 'ht', 'st', 'dx', and 'basic-speed'
        'permanent': { <same attributes as in 'current'> }
        'check_for_death': True | False
    }

    Weapon looks like:
    {
        TBS
        'type': <melee weapon> | <ranged weapon> | <shield>
        'parry': <plus to parry>
    }

    'Final' values include any plusses due to advantages or skills or
    whaterver.  This code doesn't calculate any of the derived values.  This
    may change in the future, however.
    '''

    damage_mult = { 'burn': 1.0, 'cor': 1.0, 'cr':  1.0, 'cut': 1.5,
                    'imp':  2.0, 'pi-': 0.5, 'pi':  1.0, 'pi+': 1.5,
                    'pi++': 2.0, 'tbb': 1.0, 'tox': 1.0
                  }
    melee_damage = {1:  {'thr': {'num_dice': 1, 'plus': -6},
                         'sw':  {'num_dice': 1, 'plus': -5}},
                    2:  {'thr': {'num_dice': 1, 'plus': -6},
                         'sw':  {'num_dice': 1, 'plus': -5}},
                    3:  {'thr': {'num_dice': 1, 'plus': -5},
                         'sw':  {'num_dice': 1, 'plus': -4}},
                    4:  {'thr': {'num_dice': 1, 'plus': -5},
                         'sw':  {'num_dice': 1, 'plus': -4}},
                    5:  {'thr': {'num_dice': 1, 'plus': -4},
                         'sw':  {'num_dice': 1, 'plus': -3}},
                    6:  {'thr': {'num_dice': 1, 'plus': -4},
                         'sw':  {'num_dice': 1, 'plus': -3}},
                    7:  {'thr': {'num_dice': 1, 'plus': -3},
                         'sw':  {'num_dice': 1, 'plus': -2}},
                    8:  {'thr': {'num_dice': 1, 'plus': -3},
                         'sw':  {'num_dice': 1, 'plus': -2}},
                    9:  {'thr': {'num_dice': 1, 'plus': -2},
                         'sw':  {'num_dice': 1, 'plus': -1}},
                    10: {'thr': {'num_dice': 1, 'plus': -2},
                         'sw':  {'num_dice': 1, 'plus': 0}},
                    11: {'thr': {'num_dice': 1, 'plus': -1},
                         'sw':  {'num_dice': 1, 'plus': +1}},
                    12: {'thr': {'num_dice': 1, 'plus': -1},
                         'sw':  {'num_dice': 1, 'plus': +2}},
                    13: {'thr': {'num_dice': 1, 'plus': 0},
                         'sw':  {'num_dice': 2, 'plus': -1}},
                    14: {'thr': {'num_dice': 1, 'plus': 0},
                         'sw':  {'num_dice': 2, 'plus': 0}},
                    15: {'thr': {'num_dice': 1, 'plus': +1},
                         'sw':  {'num_dice': 2, 'plus': +1}},
                    16: {'thr': {'num_dice': 1, 'plus': +1},
                         'sw':  {'num_dice': 2, 'plus': +2}},
                    17: {'thr': {'num_dice': 1, 'plus': +2},
                         'sw':  {'num_dice': 3, 'plus': -1}},
                    18: {'thr': {'num_dice': 1, 'plus': +2},
                         'sw':  {'num_dice': 3, 'plus': 0}},
                    19: {'thr': {'num_dice': 2, 'plus': -1},
                         'sw':  {'num_dice': 3, 'plus': +1}},
                    20: {'thr': {'num_dice': 2, 'plus': -1},
                         'sw':  {'num_dice': 3, 'plus': +2}}}

    # Posture: B551
    posture = {
        'standing':  {'attack':  0, 'defense':  0, 'target':  0},
        'crouching': {'attack': -2, 'defense':  0, 'target': -2},
        'kneeling':  {'attack': -2, 'defense': -2, 'target': -2},
        'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        'sitting':   {'attack': -2, 'defense': -2, 'target': -2},
        'lying':     {'attack': -4, 'defense': -3, 'target': -2},
    }


    def __init__(self, window_manager):
        super(GurpsRuleset, self).__init__(window_manager)
        self.__action_performed_by_this_fighter = False

    # TODO: need a template for new characters

    def adjust_hp(self,
                  fighter,  # Fighter object
                  adj # the number of HP to gain or lose
                 ):
        if adj < 0 and fighter.details['current']['hp'] < 0:
            before_hp = fighter.details['current']['hp']
            before_hp_multiple = (before_hp /
                                    fighter.details['permanent']['hp'])
            after_hp = (fighter.details['current']['hp'] + adj) * 1.0 + 0.1
            after_hp_multiple = (after_hp /
                                    fighter.details['permanent']['hp'])
            if int(before_hp_multiple) != int(after_hp_multiple):
                fighter.details['check_for_death'] = True

        if 'high pain threshold' not in fighter.details['advantages']: # B59
            shock_amount = -4 if adj <= -4 else adj
            if fighter.details['shock'] > shock_amount:
                fighter.details['shock'] = shock_amount

        # TODO: MAJOR WOUND: if adj > HP/2, -4 to active defenses until
        # HT roll made

        # TODO: WILL roll or lose aim

        super(GurpsRuleset, self).adjust_hp(fighter, adj)

    def change_posture(self,
                       param, # dict {'fighter': <Fighter object>,
                              #       'posture': <string=new posture>}
                      ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        param['fighter'].details['posture'] = param['posture']
        param['fighter'].reset_aim()


    def do_aim(self,
               param, # dict {'fighter': <Fighter object>,
                      #       'braced': True | False}
              ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        param['fighter'].do_aim(param['braced'])

    def do_defense(self,
                   fighter  # Fighter object
                  ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        fighter.reset_aim()

    def do_maneuver(self):
        # TODO: this should be part of a Fighter object rather than here
        self.__action_performed_by_this_fighter = True

    def get_action_menu(self,
                        fighter # Fighter object
                       ):
        ''' Builds the menu of maneuvers allowed for the fighter. '''

        action_menu = []

        # Figure out who we are and what we're holding.

        weapon, weapon_index = fighter.get_current_weapon()
        holding_ranged = (False if weapon is None else
                                (weapon['type'] == 'ranged weapon'))

        draw_weapon_menu = []   # list of weapons that may be drawn this turn
        for index, item in enumerate(fighter.details['stuff']):
            if (item['type'] == 'ranged weapon' or
                    item['type'] == 'melee weapon' or
                    item['type'] == 'shield'):
                if weapon is None or weapon_index != index:
                    draw_weapon_menu.append((item['name'],
                                        {'text': [('draw %s' % item['name']),
                                                  ' Defense: any',
                                                  ' Move: step'],
                                         'doit': self.__draw_weapon,
                                         'param': {'weapon': index,
                                                   'fighter': fighter}}))

        # Posture menu

        posture_menu = []
        for posture in GurpsRuleset.posture.iterkeys():
            if posture != fighter.details['posture']:
                posture_menu.append(
                    (posture,   {'text': ['Change posture',
                                          ' Defense: any',
                                          ' Move: none'],
                                 'doit': self.change_posture,
                                 'param': {'fighter': fighter,
                                           'posture': posture}}))

        # Build the action_menu.  Alphabetical order.  Only allow the things
        # the fighter can do based on zis current situation.

        if holding_ranged:
            if weapon['ammo']['shots_left'] > 0:

                # Aim
                #
                # Ask if we're bracing if this is the first round of aiming
                # B364 (NOTE: Combat Lite on B234 doesn't mention bracing).
                if fighter.details['aim']['rounds'] == 0:
                    # TODO: any defense loses your aim
                    brace_menu = [
                        ('Bracing',     {'text': ['Aim with brace',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'doit': self.do_aim,
                                         'param': {'fighter': fighter,
                                                   'braced': True}}),
                        ('Not Bracing', {'text': ['Aim',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'doit': self.do_aim,
                                         'param': {'fighter': fighter,
                                                   'braced': False}})
                    ]
                    action_menu.append(('Aim',  
                                        {'text': ['Aim',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'menu': brace_menu})
                                      )
                else:
                    action_menu.append(('Aim',  
                                        {'text': ['Aim',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'doit': self.do_aim,
                                         'param': {'fighter': fighter,
                                                   'braced': False}})
                                      )

                # Can only attack with a ranged weapon if there are still
                # shots in the gun.

                action_menu.extend([
                    ('attack',          {'text': ['Attack',
                                                  ' Defense: any',
                                                  ' Move: step'],
                                         'doit': self.__do_attack,
                                         'param': fighter}),
                    ('attack, all out', {'text': ['All out attack',
                                                  ' Defense: none',
                                                  ' Move: 1/2'],
                                         'doit': self.__do_attack,
                                         'param': fighter})
                ])
        else:
            action_menu.extend([
                    ('attack',          {'text': ['Attack',
                                                    ' Defense: any',
                                                    ' Move: step'],
                                         'doit': self.__do_attack,
                                         'param': fighter}),
                    ('attack, all out', {'text': ['All out attack',
                                                 ' Defense: none',
                                                 ' Move: 1/2'],
                                         'doit': self.__do_attack,
                                         'param': fighter})
            ])

        action_menu.extend([
            ('posture (change)',       {'text': ['Change posture',
                                                 ' Defense: any',
                                                 ' Move: none'],
                                        'menu': posture_menu}),
            ('Concentrate',            {'text': ['Concentrate',
                                                 ' Defense: any w/will roll',
                                                 ' Move: step'],
                                        'doit': None}),
            ('Defense, all out',       {'text': ['All out defense',
                                                 ' Defense: double',
                                                 ' Move: step'],
                                        'doit': self.do_defense,
                                        'param': fighter}),
        ])

        # TODO: should only be able to ready an unready weapon.

        if len(draw_weapon_menu) == 1:
            action_menu.append(
                    (('draw (ready, etc.) %s' % draw_weapon_menu[0][0]),
                     {'text': ['Ready (draw, etc.)',
                               ' Defense: any',
                               ' Move: step'],
                      'doit': self.__draw_weapon,
                      'param': {'weapon': draw_weapon_menu[0][1]['param'],
                                'fighter': fighter}}))

        elif len(draw_weapon_menu) > 1:
            action_menu.append(('draw (ready, etc.)',
                                {'text': ['Ready (draw, etc.)',
                                          ' Defense: any',
                                          ' Move: step'],
                                 'menu': draw_weapon_menu}))

        action_menu.append(('evaluate', {'text': ['Evaluate',
                                                  ' Defense: any',
                                                  ' Move: step'],
                                         'doit': None}))

        # Can only feint with a melee weapon
        if weapon is not None and holding_ranged == False:
            action_menu.append(('feint',   {'text': ['Feint',
                                                     ' Defense: any, parry *',
                                                     ' Move: step'],
                                            'doit': None}))

        if weapon is not None:
            action_menu.append((('holster/sheathe %s' % weapon['name']), 
                                   {'text': [('Unready %s' % weapon['name']),
                                             ' Defense: any',
                                             ' Move: step'],
                                    'doit': self.__draw_weapon,
                                    'param': {'weapon': None,
                                              'fighter': fighter}}))

        action_menu.extend([
            ('move',                   {'text': ['Move',
                                                 ' Defense: any',
                                                 ' Move: full'],
                                        'doit': None}),
            ('Move and attack',        {'text': ['Move & Attack',
                                                 ' Defense: Dodge,block',
                                                 ' Move: full'],
                                        'doit': None}),
            ('nothing',                {'text': ['Do nothing',
                                                 ' Defense: any',
                                                 ' Move: none'],
                                        'doit': None}),
        ])

        if holding_ranged:
            action_menu.append(('reload (ready)',         
                                       {'text': ['Ready (reload)',
                                                 ' Defense: any',
                                                 ' Move: step'],
                                        'doit': self.__do_reload,
                                        'param': fighter}))

        action_menu.extend([
            ('stun/surprise (do nothing)',
                               {'text': ['Stun/Surprised',
                                         ' Defense: any @-4',
                                         ' Move: none'],
                                'doit': None}),
            ('wait',           {'text': ['Wait',
                                         ' Defense: any, no All Out Attack',
                                         ' Move: none'],
                                'doit': None})
        ])

        return action_menu


    def get_block_skill(self,
                        fighter,    # Fighter object
                        weapon      # dict
                       ):
        if weapon is None or weapon['skill'] not in fighter.details['skills']:
            return None, None
        skill = fighter.details['skills'][weapon['skill']]
        block_why = []
        block_skill_modified = False

        block_skill = 3 + int(skill * 0.5)
        block_why.append('Block (B327, B375) w/%s @ (skill(%d)/2)+3 = %d' % (
                                                                weapon['name'],
                                                                skill,
                                                                block_skill))

        if 'combat reflexes' in fighter.details['advantages']:
            block_skill_modified = True
            block_why.append('  +1 due to combat reflexes (B43)')
            block_skill += 1

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            block_skill_modified = True
            block_skill += posture_mods['defense']
            block_why.append('  %+d due to %s posture' % 
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))

        if block_skill_modified:
            block_why.append('  ...for a block skill total = %d' % block_skill)

        return block_skill, block_why


    def get_dodge_skill(self,
                        fighter # Fighter object
                       ): # B326
        dodge_why = []
        dodge_skill_modified = False

        dodge_skill = 3 + int(fighter.details['current']['basic-speed'])
        dodge_why.append('Dodge (B326) @ int(basic-speed(%f))+3 = %d' % (
                                fighter.details['current']['basic-speed'],
                                dodge_skill))

        if 'combat reflexes' in fighter.details['advantages']: # B43
            dodge_skill_modified = True
            dodge_why.append('  +1 due to combat reflexes (B43)')
            dodge_skill += 1

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            dodge_skill_modified = True
            dodge_skill += posture_mods['defense']
            dodge_why.append('  %+d due to %s posture' % 
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))

        # B327
        if (fighter.details['current']['hp'] <
                                    fighter.details['permanent']['hp']/3.0):
            dodge_skill_modified = True
            dodge_why.append(
                '  skill(%d)/2 (round up) due to hp(%d) < perm-hp(%d)/3' %
                                        (dodge_skill,
                                         fighter.details['current']['hp'],
                                         fighter.details['permanent']['hp']))
            dodge_skill = int(((dodge_skill)/2.0) + 0.5)

        if dodge_skill_modified:
            dodge_why.append('  ...for a dodge skill total = %d' % dodge_skill)

        return dodge_skill, dodge_why

    def get_fighter_to_hit_damage_notes(self,
                                        fighter   # Fighter object
                                       ):
        notes = []
        holding_weapon_index = fighter.details['weapon-index']
        if holding_weapon_index is None:
            hand_to_hand_info = self.get_hand_to_hand_info(fighter)
            damage_type_str = self.__get_damage_type_str('cr')

            notes.append(hand_to_hand_info['punch_string'])
            notes.append('  to hit: %d, damage: %dd%+d, %s' % (
                                hand_to_hand_info['punch_skill'],
                                hand_to_hand_info['punch_damage']['num_dice'],
                                hand_to_hand_info['punch_damage']['plus'],
                                damage_type_str))

            notes.append(hand_to_hand_info['kick_string'])
            notes.append('  to hit: %d, damage: %dd%+d, %s' % (
                                hand_to_hand_info['kick_skill'],
                                hand_to_hand_info['kick_damage']['num_dice'],
                                hand_to_hand_info['kick_damage']['plus'],
                                damage_type_str))
        else:
            weapon = fighter.details['stuff'][holding_weapon_index]
            notes.append('%s' % weapon['name'])

            if weapon['skill'] in fighter.details['skills']:
                to_hit, why = self.get_to_hit(fighter, weapon)

                damage_type = ('' if 'type' not in weapon['damage']
                                    else weapon['damage']['type'])
                damage_type_str = self.__get_damage_type_str(damage_type)

                if 'dice' in weapon['damage']:
                    notes.append('  to hit: %d, damage: %s, %s' %
                                                    (to_hit,
                                                     weapon['damage']['dice'],
                                                     damage_type_str))
                # TODO: handle damage other than 'dice' (e.g., st-based)
            else:
                self._window_manager.error(
                    ['%s requires "%s" skill not had by "%s"' %
                                                             (weapon['name'],
                                                              weapon['skill'],
                                                              fighter.name)])

        return notes

    def get_fighter_defenses_notes(self,
                                   fighter   # Fighter object
                                  ):
        notes = []
        why = []
        holding_weapon_index = fighter.details['weapon-index']
        hand_to_hand_info = None
        weapon = None
        if holding_weapon_index is None:
            hand_to_hand_info = self.get_hand_to_hand_info(fighter)
        else:
            weapon = fighter.details['stuff'][holding_weapon_index]


        dodge_skill, dodge_why = self.get_dodge_skill(fighter)
        if dodge_skill is not None:
            dodge_string = 'Dodge (B326): %d' % dodge_skill
            why.extend(dodge_why)
            notes.append(dodge_string)

        if weapon is None: # Unarmed Parry
            notes.append('%s: %d' % (hand_to_hand_info['parry_string'],
                                     hand_to_hand_info['parry_skill']))

        elif weapon['type'] == 'shield': # NOTE: cloaks also have this 'type'
            block_skill, block_why = self.get_block_skill(fighter, weapon)
            if block_skill is not None:
                why.extend(block_why)
                notes.append('Block (B327, B375): %d' % block_skill)

        elif weapon['type'] == 'melee weapon':
            parry_skill, parry_why = self.get_parry_skill(fighter, weapon)
            if parry_skill is not None:
                why.extend(parry_why)
                notes.append('Parry (B327, B376): %d' % parry_skill)

        return notes, why

    def get_fighter_notes(self,
                          fighter   # Fighter object
                         ):
        notes = []

        # First thing: attack, damage, defense

        holding_weapon_index = fighter.details['weapon-index']
        weapon = None

        if holding_weapon_index is not None:
            weapon = fighter.details['stuff'][holding_weapon_index]
            if weapon['type'] == 'ranged weapon':
                clip_name = weapon['ammo']['name']
                clip = None
                for item in fighter.details['stuff']:
                    if item['name'] == clip_name:
                        clip = item
                        break

                notes.append('  %d/%d shots, %d reloads' % (
                                    weapon['ammo']['shots_left'],
                                    weapon['ammo']['shots'],
                                    (0 if clip is None else clip['count'])))
                

        # And, now, off to the regular stuff

        if fighter.details['posture'] != 'standing':
            notes.append('Posture: %s' % fighter.details['posture'])
        if fighter.details['shock'] != 0:
            notes.append('DX and IQ are at %d' % fighter.details['shock'])

        if (fighter.details['current']['hp'] <
                                    fighter.details['permanent']['hp']/3.0):
            # Already incorporated into Dodge
            notes.append('Dodge/Move are at 1/2')

        if (fighter.details['current']['fp'] <=
                                        -fighter.details['permanent']['fp']):
            fighter.details['state'] = 'unconscious'
            notes.append('*UNCONSCIOUS*')

        else:
            if fighter.details['current']['fp'] <= 0:
                notes.append('On action: Roll vs. Will or pass out')

            if fighter.details['current']['hp'] <= 0: # B327
                if 'high pain threshold' in fighter.details['advantages']: # B59
                    notes.append('On turn: 3d+3 vs. HT or pass out')
                else:
                    notes.append('On turn: 3d vs. HT or pass out')

        if fighter.details['check_for_death']:
            notes.append('3d vs. HT or DIE')
            fighter.details['check_for_death'] = False  # Only show/roll once

        return notes


    def get_hand_to_hand_info(self,
                              fighter   # Fighter object
                             ):
        result = {
            'punch_skill': fighter.details['current']['dx'],
            'punch_string': 'Punch (DX) (B271, B370)',
            'punch_damage': None,

            'kick_skill': 0,
            'kick_string': 'Kick (DX-2) (B271, B370)',
            'kick_damage': None,

            'parry_skill': fighter.details['current']['dx'],
            'parry_string': 'Unarmed Parry (B376)',

            'why': []
        }

        punch_why = []
        kick_why = []
        damage_why = []
        parry_why = []

        plus_per_die_of_thrust = 0
        plus_per_die_of_thrust_string = None

        # boxing, brawling, karate, dx
        if 'brawling' in fighter.details['skills']:
            if result['punch_skill'] < fighter.details['skills']['brawling']:
                result['punch_string'] = 'Brawling Punch (B182, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['brawling']
                result['kick_string'] = 'Brawling Kick (B182, B271, B370)'
                # Brawling: @DX+2 = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.details['current']['dx']+2:
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Brawling(%d) @DX(%d)+2 = +1/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
            if result['parry_skill'] < fighter.details['skills']['brawling']:
                result['parry_skill'] = fighter.details['skills']['brawling']
                result['parry_string'] = 'Brawling Parry (B182, B376)'
        if 'karate' in fighter.details['skills']:
            if result['punch_skill'] < fighter.details['skills']['karate']:
                result['punch_string'] = 'Karate Punch (B203, B271, B370)'
                result['kick_string'] = 'Karate Kick (B203, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['karate']
                # Karate: @DX+1+ = +2 per die of thrusting damage
                # Karate: @DX = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.details['current']['dx']+1:
                    plus_per_die_of_thrust = 2
                    plus_per_die_of_thrust_string = (
                        'Karate(%d) @DX(%d)+1 = +2/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                elif result['punch_skill'] >= fighter.details['current']['dx']:
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Karate(%d) @DX(%d) = +1/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                else:
                    plus_per_die_of_thrust = 0
                    plus_per_die_of_thrust_string = None
            if result['parry_skill'] < fighter.details['skills']['karate']:
                result['parry_skill'] = fighter.details['skills']['karate']
                result['parry_string'] = 'Karate Parry (B203, B376)'

        # (brawling, karate, dx) - 2
        result['kick_skill'] = result['punch_skill'] - 2
        kick_why.append('%s = %s (%d) -2 = to-hit: %d' % (
                                                    result['kick_string'],
                                                    result['punch_string'],
                                                    result['punch_skill'],
                                                    result['kick_skill']))

        if 'boxing' in fighter.details['skills']:
            if result['punch_skill'] < fighter.details['skills']['boxing']:
                result['punch_string'] = 'Boxing Punch (B182, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['boxing']
                # Boxing: @DX+2+ = +2 per die of thrusting damage
                # Boxing: @DX+1 = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.details['current']['dx']+2:
                    plus_per_die_of_thrust = 2
                    plus_per_die_of_thrust_string = (
                        'Boxing(%d) @DX(%d)+2 = +2/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                elif (result['punch_skill'] >= 
                                        fighter.details['current']['dx']+1):
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Boxing(%d) @DX(%d)+1 = +1/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                else:
                    plus_per_die_of_thrust = 0
                    plus_per_die_of_thrust_string = None
            if result['parry_skill'] < fighter.details['skills']['boxing']:
                result['parry_skill'] = fighter.details['skills']['boxing']
                result['parry_string'] = 'Boxing Parry (B182, B376)'

        punch_why.append('%s, to-hit: %d' % (result['punch_string'],
                                             result['punch_skill']))

        # Posture

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['attack'] != 0:
            result['punch_skill'] += posture_mods['attack']
            result['kick_skill'] += posture_mods['attack']

            punch_why.append('  %+d due to %s posture' % 
                                                (posture_mods['attack'],
                                                 fighter.details['posture']))
            kick_why.append('  %+d due to %s posture' % 
                                                (posture_mods['attack'],
                                                 fighter.details['posture']))

        # Opponent's posture

        #opponent = self.get_opponent_for(fighter) # TODO: part of fight handler
        #if opponent is not None:
        #    opponent_posture_mods = self.get_posture_mods(
        #                                        opponent.details['posture'])
        #    if opponent_posture_mods is not None:
        #        result['punch_skill'] += opponent_posture_mods['target']
        #        result['kick_skill'] += opponent_posture_mods['target']

        parry_raw = result['parry_skill']
        parry_damage_modified = False

        # Brawling, Boxing, Karate, DX: Parry int(skill/2) + 3
        result['parry_skill'] = 3 + int(result['parry_skill']/2)
        parry_why.append('%s @ (punch(%d)/2)+3 = %d' % (result['parry_string'],
                                                        parry_raw,
                                                        result['parry_skill']))
        if 'combat reflexes' in fighter.details['advantages']:
            parry_damage_modified = True
            result['parry_skill'] += 1
            parry_why.append('  +1 due to combat reflexes (B43)')

        if parry_damage_modified:
            parry_why.append('  ...for a parry total = %d' %
                                                        result['parry_skill'])

        # Damage

        st = fighter.details['current']['st']

        damage_why.append(
            'Kick damage(B271)=thr -- plug ST(%d) into table on B16' % st)

        result['kick_damage'] = copy.deepcopy(
                                        GurpsRuleset.melee_damage[st]['thr'])
        kick_damage_modified = False
        damage_why.append('  damage: %dd%+d' % (
                                            result['kick_damage']['num_dice'],
                                            result['kick_damage']['plus']))

        if plus_per_die_of_thrust != 0:
            kick_damage_modified = True
            result['kick_damage']['plus'] += (
                                        result['kick_damage']['num_dice'] *
                                        plus_per_die_of_thrust)
            damage_why.append('  %+d/die due to %s' % (
                                                plus_per_die_of_thrust,
                                                plus_per_die_of_thrust_string))

        if kick_damage_modified:
            damage_why.append('  ...for a kick damage total = %dd%+d' % (
                                            result['kick_damage']['num_dice'],
                                            result['kick_damage']['plus']))

        result['punch_damage'] = copy.deepcopy(result['kick_damage'])
        result['punch_damage']['plus'] -= 1
        damage_why.append('Punch damage(B271) = thr-1 = "kick" - 1')
        damage_why.append('  ...for a punch damage total = %dd%+d' % (
                                        result['punch_damage']['num_dice'],
                                        result['punch_damage']['plus']))


        # Assemble the 'why'

        result['why'].extend(parry_why)
        result['why'].extend(punch_why)
        result['why'].extend(kick_why)
        result['why'].extend(damage_why)

        return result


    def get_parry_skill(self,
                        fighter,    # Fighter object
                        weapon      # dict
                       ):
        if weapon is None or weapon['skill'] not in fighter.details['skills']:
            return None, None
        skill = fighter.details['skills'][weapon['skill']]
        parry_why = []
        parry_skill_modified = False

        parry_skill = 3 + int(skill * 0.5)
        parry_why.append('Parry (B327, B376) w/%s @ (skill(%d)/2)+3 = %d' % (
                                                                weapon['name'],
                                                                skill,
                                                                parry_skill))

        if 'parry' in weapon:
            parry_skill += weapon['parry']
            parry_skill_modified = True
            parry_why.append('  %+d due to weapon modifiers' % weapon['parry'])

        if 'combat reflexes' in fighter.details['advantages']:
            parry_skill_modified = True
            parry_why.append('  +1 due to combat reflexes (B43)')
            parry_skill += 1

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            parry_skill_modified = True
            parry_skill += posture_mods['defense']
            parry_why.append('  %+d due to %s posture' % 
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))
        if parry_skill_modified:
            parry_why.append('  ...for a parry skill total = %d' % parry_skill)

        return parry_skill, parry_why

    def get_posture_mods(self,
                         posture    # string: 'standing' | ...
                        ):
        return (None if posture not in GurpsRuleset.posture else
                                            GurpsRuleset.posture[posture])

    def get_to_hit(self,
                   fighter, # Fighter object
                   weapon
                  ):
        '''
        Returns tuple (skill, why) where:
            'skill' (number) is the value the attacker needs to roll to hit
                    the target.
            'why'   is an array of strings describing why the to-hit numbers
                    are what they are.
        '''
        if weapon['skill'] not in fighter.details['skills']:
            return None

        why = []
        skill = fighter.details['skills'][weapon['skill']]
        why.append('Weapon %s w/skill = %d' % (weapon['name'], skill))

        if 'acc' in weapon:
            if fighter.details['aim']['rounds'] > 0:
                why.append('  +%d due to aiming for 1' % weapon['acc'])
                skill += weapon['acc']
                if fighter.details['aim']['braced']:
                    why.append('  +1 due to bracing')
                    skill += 1
            if fighter.details['aim']['rounds'] == 2:
                why.append('  +1 due to one more round of aiming')
                skill += 1

            elif fighter.details['aim']['rounds'] > 2:
                why.append('  +2 due to 2 or more additional rounds of aiming')
                skill += 2

        # Posture

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['attack'] != 0:
            why.append('  %+d due %s posture' % (posture_mods['attack'],
                                                 fighter.details['posture']))
            skill += posture_mods['attack']

        # Opponent's posture

        #opponent = self.get_opponent_for(fighter) # TODO: part of fight handler
        #if opponent is not None:
        #    opponent_posture_mods = self.get_posture_mods(
        #                                        opponent.details['posture'])
        #    if opponent_posture_mods is not None:
        #        skill += opponent_posture_mods['target']

        why.append('  ...for a to hit total of %d' % skill)
        return skill, why


    def heal_fighter(self,
                     fighter_details    # Details is OK, here
                    ):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        super(GurpsRuleset, self).heal_fighter(fighter_details)
        fighter_details['shock'] = 0
        fighter_details['last_negative_hp'] = 0
        fighter_details['check_for_death'] = False


    def initiative(self,
                   fighter # Fighter object
                  ):
        return (fighter.details['current']['basic-speed'],
                fighter.details['current']['dx'],
                Ruleset.roll(1, 6)
                )


    def make_dead(self):
        self.__action_performed_by_this_fighter = True


    def new_fight(self, fighter):
        '''
        Removes all the stuff from the old fight except injury.
        '''
        super(GurpsRuleset, self).new_fight(fighter)
        fighter.details['shock'] = 0
        fighter.reset_aim()
        self.__action_performed_by_this_fighter = False


    def can_move_on_to_next_fighter(self,
                                    prev_fighter   # Fighter object of current
                                                   #  (before moving on) fighter
                                   ):
        # If he's unconscious or dead, we can ignore him and move on
        if not prev_fighter.is_conscious():
            return True, None

        # Force some maneuver for the current fighter before moving on.  That
        # way, we can look at the defense and movement restrictions (as well
        # as a bunch of other stuff, like dealing with 'aim').
        if not self.__action_performed_by_this_fighter:
            return (False,
                    'The fighter should do _some_ maneuver before moving on.')
        prev_fighter.details['shock'] = 0 # remove expired shock entry
        self.__action_performed_by_this_fighter = False
        return True, None

    #
    # Private Methods
    #

    def __do_attack(self,
                    fighter # Fighter object for attacker
                   ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return

        weapon['ammo']['shots_left'] -= 1
        fighter.reset_aim()


    def __do_reload(self,
                    fighter # Fighter object for attacker
                   ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return

        clip_name = weapon['ammo']['name']
        for item in fighter.details['stuff']:
            if item['name'] == clip_name and item['count'] > 0:
                weapon['ammo']['shots_left'] = weapon['ammo']['shots']
                item['count'] -= 1
                fighter.add_timer(weapon['reload'], 'RELOADING')
                fighter.reset_aim()
                return

        return

    def __draw_weapon(self,
                      param # dict: {'weapon': index, 'fighter': Fighter obj}
                     ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        param['fighter'].draw_weapon_by_index(param['weapon'])
        param['fighter'].reset_aim()

    def __get_damage_type_str(self,
                              damage_type
                             ):
        if damage_type in GurpsRuleset.damage_mult:
            damage_type_str = '%s (x%.1f)' % (
                                        damage_type,
                                        GurpsRuleset.damage_mult[damage_type])
        else:
            damage_type_str = '%s' % damage_type
        return damage_type_str

class ScreenHandler(object):
    '''
    Base class for the "business logic" backing the user interface.
    '''

    def __init__(self, window_manager, campaign_debug_json):
        self._campaign_debug_json = campaign_debug_json
        self._window_manager = window_manager
        self._history = []
        self._choices = {
            ord('B'): {'name': 'Bug Report', 'func': self._make_bug_report},
        }

    def handle_user_input_until_done(self):
        '''
        Draws the screen and does event loop (gets input, responds to input)
        '''
        self._draw_screen()

        keep_going = True
        while keep_going:
            string = self._window_manager.get_one_character()
            if string in self._choices:
                keep_going = self._choices[string]['func']()

    #
    # Protected Methods
    #

    def _add_to_choice_dict(self, new_choices):
        # Check for errors...
        for key in self._choices.iterkeys():
            if key in new_choices:
                self._window_manager.error(
                        ['Collision of _choices on key "%c"' % chr(key)])
                return False # Found a problem

        self._choices.update(new_choices)
        return True # Everything's good


    def _draw_screen(self):
        pass


    def _make_bug_report(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        lines, cols = self._window_manager.getmaxyx()
        report = self._window_manager.edit_window(
                    lines - 4,
                    cols - 4,
                    '',  # initial string (w/ \n) for the window
                    'Bug Report',
                    '^G to exit')

        bug_report = {
            'world'   : self._campaign_debug_json,
            'history' : self._history,
            'report'  : report
        }

        bug_report_json = timeStamped('bug_report', 'txt')
        with open(bug_report_json, 'w') as f:
            json.dump(bug_report, f, indent=2)

        return True # Keep doing whatever you were doing.


class BuildFightHandler(ScreenHandler):
    def __init__(self,
                 window_manager,
                 world,
                 campaign_debug_json
                ):
        super(BuildFightHandler, self).__init__(window_manager,
                                                campaign_debug_json)
        self._add_to_choice_dict({
            ord('a'): {'name': 'add monster', 'func': self.__add_monster},
            ord('d'): {'name': 'delete monster', 'func': self.__delete_monster},
            ord('q'): {'name': 'quit', 'func': self.__quit},
            # TODO: need a quit but don't save option
        })
        self._window = BuildFightGmWindow(self._window_manager)

        self.__world = world

        lines, cols = self._window.getmaxyx()
        template_menu = [(template_name, template_name)
                for template_name in self.__world['Templates']]
        self.__template_name = self._window_manager.menu('From Which Template',
                                                         template_menu)
        keep_asking = True
        while keep_asking:
            self.__monsters_name = self._window_manager.input_box(
                                                            1,      # height
                                                            cols-4, # width
                                                            'New Fight Name')
            if self.__monsters_name is None:
                self._window_manager.error(['You have to name your fight'])
                keep_asking = True
            elif self.__monsters_name in self.__world['monsters']:
                self._window_manager.error(
                    ['Fight name "%s" alread exists' % self.__monsters_name])
                keep_asking = True
            else:
                keep_asking = False

        self.__monsters = {}

    #
    # Protected Methods
    #


    def _draw_screen(self):
        self._window.clear()
        self._window.command_ribbon(self._choices)

    #
    # Private Methods
    #


    def __add_monster(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Based on which monster from the template
        monster_menu = [(from_monster_name, from_monster_name)
            for from_monster_name in world['Templates'][self.__template_name]]
        from_monster_name = self._window_manager.menu('Monster', monster_menu)
        if from_monster_name is None:
            return True # Keep going

        # Get the new Monster Name

        keep_asking = True
        lines, cols = self._window.getmaxyx()
        while keep_asking:
            to_monster_name = self._window_manager.input_box(1,      # height
                                                             cols-4, # width
                                                             'Monster Name')
            if to_monster_name is None:
                self._window_manager.error(['You have to name your monster'])
                keep_asking = True
            elif to_monster_name in self.__monsters:
                self._window_manager.error(
                    ['Monster "%s" alread exists' % to_monster_name])
                keep_asking = True
            else:
                keep_asking = False

        # Generate the Monster

        from_monster = (
            world['Templates'][self.__template_name][from_monster_name])
        # TODO: what's in a Template vs. what's supplied, here, should be
        # documeted somewhere
        to_monster = {'state': 'alive',
                      'timers': [],
                      'opponent': None,
                      'permanent': {},
                      'current': {}}

        for key, value in from_monster.iteritems():
            if key == 'permanent':
                for ikey, ivalue in value.iteritems():
                    to_monster['permanent'][ikey] = (
                        self.__get_value_from_template(ivalue, from_monster))
                    to_monster['current'][ikey] = to_monster['permanent'][ikey]
            else:
                to_monster[key] = self.__get_value_from_template(value,
                                                                  from_monster)
        self.__monsters[to_monster_name] = to_monster
        self._window.show_monsters(self.__monsters_name, self.__monsters)
        return True # Keep going

    def __delete_monster(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # TODO
        return True # Keep going

    def __get_value_from_template(self,
                                  template_value,
                                  template
                                 ):
        if template_value['type'] == 'value':
            return template_value['value']

        # TODO(eventually):
        #   {'type': 'ask-string', 'value': x}
        #   {'type': 'ask-numeric', 'value': x}
        #   {'type': 'ask-logical', 'value': x}
        #   {'type': 'dice', 'value': 'ndm+x'}
        #   {'type': 'derived', 'value': comlicated bunch of crap -- eventually}

        return None

    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # TODO: need a way to exit without saving
        #if ARGS.verbose:
        #    print 'monsters:'
        #    PP.pprint(self.__monsters)
        self.__world['monsters'][self.__monsters_name] = self.__monsters
        self._window.close()
        return False # Stop building this fight


class FightHandler(ScreenHandler):
    def __init__(self,
                 window_manager,
                 world,
                 monster_group,
                 ruleset,
                 campaign_debug_json
                ):
        super(FightHandler, self).__init__(window_manager, campaign_debug_json)
        self._window = self._window_manager.get_fight_gm_window(ruleset)
        self.__ruleset = ruleset
        # TODO: when the history is reset (here), the JSON should be rewritten
        self._history = ['--- Round 0 ---']

        # NOTE: 'h' and 'f' belong in Ruleset
        # TODO: Heal
        self._add_to_choice_dict({
            ord(' '): {'name': 'next',      'func': self.__next_fighter},
            ord('<'): {'name': 'prev',      'func': self.__prev_fighter},
            ord('?'): {'name': 'explain',   'func': self.__show_why},
            ord('d'): {'name': 'dead',      'func': self.__dead},
            ord('f'): {'name': 'FP damage', 'func': self.__damage_FP},
            ord('h'): {'name': 'History',   'func': self.__show_history},
            ord('-'): {'name': 'HP damage', 'func': self.__damage_HP},
            ord('m'): {'name': 'maneuver',  'func': self.__maneuver},
            ord('n'): {'name': 'notes',     'func': self.__notes},
            ord('o'): {'name': 'opponent',  'func': self.__pick_opponent},
            ord('q'): {'name': 'quit',      'func': self.__quit},
            ord('s'): {'name': 'save',      'func': self.__save},
            ord('t'): {'name': 'timer',     'func': self.__timer}
        })

        self.__world = world
        # self.__saved_fight takes the form:
        # {
        #   'index': <number>  # current fighter that has the initiative
        #   'fighters': [ {'group': <group>,
        #                  'name': <name>}, ... # fighters in initiative order
        #   'saved': True | False
        #   'round': <number>  # round of the fight
        #   'monsters': <name> # group name of the monsters in the fight
        # }
        self.__saved_fight = world['current-fight']
        self.__fighters = [] # This is a parallel array to
                             # self.__saved_fight['fighters'] but the contents
                             # are: {'group': <groupname>,
                             #       'info': <Fighter object>}

        if self.__saved_fight['saved']:
            for saved_fighter in self.__saved_fight['fighters']:
                fighter = Fighter(saved_fighter['name'],
                                  saved_fighter['group'],
                                  self.__get_fighter_details(
                                                      saved_fighter['name'],
                                                      saved_fighter['group']),
                                  self.__ruleset)
                self.__fighters.append(fighter)
        else:
            self.__saved_fight['round'] = 0
            self.__saved_fight['index'] = 0
            self.__saved_fight['monsters'] = monster_group

            self.__fighters = []    # contains objects

            for name, details in world['PCs'].iteritems():
                fighter = Fighter(name, 'PCs', details, self.__ruleset)
                self.__fighters.append(fighter)

            if monster_group is not None:
                for name, details in (
                        self.__world['monsters'][monster_group].iteritems()):
                    fighter = Fighter(name,
                                      monster_group,
                                      details,
                                      self.__ruleset)
                    self.__fighters.append(fighter)

            # Sort by initiative = basic-speed followed by DEX followed by
            # random
            self.__fighters.sort(
                    key=lambda fighter:
                        self.__ruleset.initiative(fighter), reverse=True)

            # Copy the fighter information into the saved_fight.  Also, make
            # sure this looks like a _NEW_ fight.
            self.__saved_fight['fighters'] = []
            for fighter in self.__fighters:
                self.__ruleset.new_fight(fighter)
                self.__saved_fight['fighters'].append({'group': fighter.group,
                                                       'name': fighter.name})

        self.__saved_fight['saved'] = False
        self._window.start_fight()

    def handle_user_input_until_done(self):
        super(FightHandler, self).handle_user_input_until_done()

        # When done, move current fight to 'dead-monsters'
        if not self.__saved_fight['saved']:
            self.__world['dead-monsters'][self.__saved_fight['monsters']] = (
                    self.__world['monsters'][self.__saved_fight['monsters']])
            del(self.__world['monsters'][self.__saved_fight['monsters']])

    #
    # Private Methods
    #

    def __current_fighter(self):
        '''
        Returns the Fighter object of the current fighter.
        '''
        result = self.__fighters[ self.__saved_fight['index'] ]
        return result



    # TODO: all of FP belongs in Ruleset
    def __damage_FP(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Figure out who loses the FP points
        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        if opponent is None:
            fp_recipient = current_fighter
        else:
            fp_recipient_menu = [(current_fighter.name, current_fighter),
                                 (opponent.name,        opponent)]
            fp_recipient = self._window_manager.menu('Who Loses FP',
                                                     fp_recipient_menu,
                                                     0)
        if fp_recipient is None:
            return True # Keep fighting

        title = 'Change FP By...'
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        adj = -int(adj_string)  # NOTE: SUBTRACTING the adjustment
        hp_adj = 0

        # If FP go below zero, you lose HP along with FP
        # TODO: this -- especially -- should be in Ruleset
        if adj < 0  and -adj > fp_recipient.details['current']['fp']:
            hp_adj = adj
            if fp_recipient.details['current']['fp'] > 0:
                hp_adj += fp_recipient.details['current']['fp']

        fp_recipient.details['current']['hp'] += hp_adj
        fp_recipient.details['current']['fp'] += adj
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going


    def __damage_HP(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Figure out who loses the hit points
        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        if opponent is None:
            hp_recipient = current_fighter
        else:
            hp_recipient_menu = [(current_fighter.name, current_fighter),
                                 (opponent.name, opponent)]
            hp_recipient = self._window_manager.menu('Who Loses HP',
                                                     hp_recipient_menu,
                                                     1) # assume the opponent
        if hp_recipient is None:
            return True # Keep fighting

        title = 'Change HP By...'
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        adj = -int(adj_string) # NOTE: SUBTRACTING the adjustment
        if adj == 0:
            return True # Keep fighting

        self.__ruleset.adjust_hp(hp_recipient, adj)

        # Record for posterity
        if hp_recipient is opponent:
            if adj < 0:
                self._history.insert(0, ' %s did %d HP to %s' %
                                                        (current_fighter.name,
                                                         -adj,
                                                         opponent.name))
            else:
                self._history.insert(0, ' %s regained %d HP' %
                                                        (current_fighter.name,
                                                         adj))
        else:
            if adj < 0:
                self._history.insert(0,
                        ' %s lost %d HP' % (current_fighter.name, -adj))
            else:
                self._history.insert(0,
                        ' %s regained %d HP' % (current_fighter.name, adj))

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going

    def __dead(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)

        if opponent is None:
            now_dead = current_fighter
        else:
            now_dead_menu = [(current_fighter.name, current_fighter),
                             (opponent.name, opponent)]
            now_dead = self._window_manager.menu('Who is Dead',
                                                 now_dead_menu,
                                                 1) # assume it's the opponent
        if now_dead is None:
            return True # Keep fighting

        now_dead.bump_consciousness()
        if now_dead.is_conscious():
            now_dead.details['opponent'] = None # dead men fight nobody
        dead_name = (current_fighter.name if now_dead is current_fighter
                                    else opponent.name)

        self._history.insert(0, ' %s was marked as %s' % (
                                                    dead_name,
                                                    now_dead.details['state']))

        if now_dead is current_fighter and not now_dead.is_conscious():
            # Mark this guy as not having to do a maneuver this round.
            # TODO: this seems like it could look at the current fighter
            # instead of having a global flag
            self.__ruleset.make_dead()

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going


    def _draw_screen(self):
        self._window.clear()
        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self.__saved_fight['round'],
                                  self.__saved_fight['saved'],
                                  next_PC_name)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        self._window.command_ribbon(self._choices)


    def __get_fighter_details(self,
                              name,     # string
                              group     # string
                             ):
        ''' Used for constructing a Fighter from the JSON information. '''
        if group in self.__world['monsters']:
            creatures = self.__world['monsters'][group]
        elif group == 'PCs':
            creatures = self.__world['PCs']
        else:
            return None

        return None if name not in creatures else creatures[name]


    def __get_fighter_object(self,
                             name,  # name of a fighter in that group
                             group  # 'PCs' or group under world['monsters']
                            ):
        for fighter in self.__fighters:
            if fighter.group == group and fighter.name == name:
                return fighter

        return None


    def __maneuver(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        current_fighter = self.__current_fighter()
        action_menu = self.__ruleset.get_action_menu(current_fighter)
        maneuver = self._window_manager.menu('Maneuver', action_menu)
        if maneuver is None:
            return True # Keep going

        while 'menu' in maneuver:
            maneuver = self._window_manager.menu('Which', maneuver['menu'])
            if maneuver is None:    # Can bail out regardless of nesting level
                return True         # Keep going

        if 'doit' in maneuver and maneuver['doit'] is not None:
            param = None if 'param' not in maneuver else maneuver['param']
            (maneuver['doit'])(param)

        self.__ruleset.do_maneuver()
        # a round count larger than 0 will get shown but less than 1 will
        # get deleted before the next round
        current_fighter.add_timer(0.9, maneuver['text'])

        self._history.insert(0, ' %s did "%s" maneuver' % (current_fighter.name,
                                                           maneuver['text'][0]))
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going


    def __modify_index(self,
                       adj      # 1 or -1, adjust the index by this
                      ):
        '''
        Increment or decrement the index.  Only stop on living creatures.
        '''

        first_index = self.__saved_fight['index']

        round_before = self.__saved_fight['round']
        keep_going = True
        while keep_going:
            self.__saved_fight['index'] += adj
            if self.__saved_fight['index'] >= len(
                                            self.__saved_fight['fighters']):
                self.__saved_fight['index'] = 0
                self.__saved_fight['round'] += adj 
            elif self.__saved_fight['index'] < 0:
                self.__saved_fight['index'] = len(
                                            self.__saved_fight['fighters']) - 1
                self.__saved_fight['round'] += adj 
            current_fighter = self.__current_fighter()
            if current_fighter.is_dead():
                self._history.insert(0, '%s did nothing (dead)' %
                                                        current_fighter.name)
            else:
                keep_going = False
            if self.__saved_fight['index'] == first_index:
                keep_going = False

        if round_before != self.__saved_fight['round']:
            self._history.insert(0, '--- Round %d ---' %
                                                self.__saved_fight['round'])


    def __next_fighter(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        prev_fighter = self.__current_fighter()
        ok_to_continue, message = self.__ruleset.can_move_on_to_next_fighter(
                                                                  prev_fighter)
        if not ok_to_continue:
            # NOTE: This should _so_ be in the ruleset but I'm not sure how to
            # achieve that.  It also makes the assumption that you can't move
            # on to the next fighter _because_ no maneuver/action has been
            # performed.
            return self.__maneuver()
            #self._window_manager.error([message])
            #return True # Keep fighting

        # remove any expired timers
        # TODO: Fighter.remove_expired_timers()
        remove_these = []
        for index, timer in enumerate(prev_fighter.details['timers']):
            if timer['rounds'] <= 0:
                remove_these.insert(0, index) # largest indexes last
        for index in remove_these:
            del prev_fighter.details['timers'][index]

        # get next fighter
        self.__modify_index(1)
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self.__saved_fight['round'],
                                  self.__saved_fight['saved'],
                                  next_PC_name) # next PC
        # TODO: Fighter.decrement_timers()
        current_fighter = self.__current_fighter()
        for timer in current_fighter.details['timers']:
            timer['rounds'] -= 1

        # remove any newly expired timers - this is here for the 'maneuver'
        # timers (e.g., 'aim', 'all out attack') which are supposed to be
        # displayed after an attacker's initiative up to but _not_ including
        # the next time they have their initiative (i.e., during his defense).
        remove_these = []
        # TODO: Fighter.remove_expired_timers()
        for index, timer in enumerate(current_fighter.details['timers']):
            if timer['rounds'] < 0:
                remove_these.insert(0, index) # largest indexes last
        for index in remove_these:
            del current_fighter.details['timers'][index]

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going

    def __next_PC_name(self):
        '''
        Finds the name of the next PC to fight _after_ the current index.
        '''

        next_PC_name = None
        next_index = self.__saved_fight['index'] + 1
        for ignore in self.__saved_fight['fighters']:
            if next_index >= len(self.__saved_fight['fighters']):
                next_index = 0
            if self.__saved_fight['fighters'][next_index]['group'] == 'PCs':
                next_PC_name = (
                        self.__saved_fight['fighters'][next_index]['name'])
                break
            next_index += 1
        return next_PC_name


    def __notes(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Figure out for whom these notes are...
        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        if opponent is None:
            notes_recipient = current_fighter
        else:
            notes_recipient_menu = [(current_fighter.name, current_fighter),
                                    (opponent.name, opponent)]
            notes_recipient = self._window_manager.menu('Notes For Whom',
                                                        notes_recipient_menu)
        if notes_recipient is None:
            return True # Keep fighting

        # Now, get the notes for that person
        lines, cols = self._window.getmaxyx()

        notes = (None if 'notes' not in notes_recipient.details else
                                            notes_recipient.details['notes'])
        notes = self._window_manager.edit_window(
                    lines - 4,
                    self._window.fighter_win_width,
                    notes,  # initial string (w/ \n) for the window
                    'Notes',
                    '^G to exit')
        notes_recipient.details['notes'] = notes

        # Redraw the fighters
        next_PC_name = self.__next_PC_name()
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going

    # TODO: move this to the public method area
    def get_opponent_for(self,
                         fighter # Fighter object
                        ):
        ''' Returns Fighter object for opponent of 'fighter'. '''
        if fighter is None or fighter.details['opponent'] is None:
            return None

        opponent = self.__get_fighter_object(
                                        fighter.details['opponent']['name'],
                                        fighter.details['opponent']['group'])
        return opponent


    def __pick_opponent(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        current_fighter = self.__current_fighter()
        opponent_group = None
        opponent_menu = []
        for fighter in self.__fighters:
            if fighter.group != current_fighter.group:
                opponent_group = fighter.group
                if fighter.is_conscious():
                    opponent_menu.append((fighter.name, fighter.name))
        if len(opponent_menu) <= 0:
            self._window_manager.error(['All the opponents are dead'])
            return True # don't leave the fight

        opponent_name = self._window_manager.menu('Opponent', opponent_menu)

        if opponent_name is None:
            return True # don't leave the fight

        current_fighter.details['opponent'] = {'group': opponent_group,
                                               'name': opponent_name}
        opponent = self.__get_fighter_object(opponent_name, opponent_group)

        # Ask to have them fight each other
        if (opponent is not None and opponent.details['opponent'] is None):
            back_menu = [('yes', True), ('no', False)]
            answer = self._window_manager.menu('Make Opponents Go Both Ways',
                                        back_menu)
            if answer == True:
                opponent.details['opponent'] = {'group': current_fighter.group,
                                                'name': current_fighter.name}

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going


    def __prev_fighter(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if (self.__saved_fight['index'] == 0 and 
                self.__saved_fight['round'] == 0):
            return True # Not going backwards from the origin

        self.__modify_index(-1)
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self.__saved_fight['round'],
                                  self.__saved_fight['saved'],
                                  next_PC_name) # next PC
        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self.__saved_fight['index'])
        return True # Keep going


    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if not self.__saved_fight['saved']:

            # Check to see if all monsters are dead
            ask_to_save = False

            for fighter in self.__fighters:
                if fighter.group != 'PCs' and fighter.is_conscious():
                    ask_to_save = True
                    break

            # Ask to save the fight if it's not saved and some monsters live.
            save_menu = [('yes', True), ('no', False)]
            if ask_to_save and self._window_manager.menu('Save Fight',
                                                         save_menu):
                self.__saved_fight['saved'] = True
                
        self._window.close()
        return False # Leave the fight


    def __save(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__saved_fight['saved'] = True
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self.__saved_fight['round'],
                                  self.__saved_fight['saved'],
                                  next_PC_name) # next PC
        return True # Keep going

    def __show_history(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        max_lines = curses.LINES - 4
        lines = (max_lines if len(self._history) > max_lines
                           else len(self._history))

        # It's not really a menu but the window for it works just fine
        pseudo_menu = []
        for line in range(lines):
            pseudo_menu.append((self._history[line], 0))
        ignore = self._window_manager.menu('Fight History (Newest On Top)',
                                           pseudo_menu)
        return True

    def __show_why(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Figure out for whom these notes are...
        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        if opponent is None:
            why_target = current_fighter
        else:
            notes_recipient_menu = [(current_fighter.name, current_fighter),
                                    (opponent.name, opponent)]
            why_target = self._window_manager.menu('Details For Whom',
                                                        notes_recipient_menu)
        if why_target is None:
            return True # Keep fighting

        pseudo_menu = [] # TODO: make a special window -- don't use a menu
        holding_weapon_index = why_target.details['weapon-index']
        if holding_weapon_index is None:
            hand_to_hand_info = self.__ruleset.get_hand_to_hand_info(why_target)
            pseudo_menu = [(x, 0) for x in hand_to_hand_info['why']]
        else:
            weapon = current_fighter.details['stuff'][holding_weapon_index]

            if weapon['skill'] in current_fighter.details['skills']:
                ignore, to_hit_why = self.__ruleset.get_to_hit(current_fighter,
                                                               weapon)
                pseudo_menu = [(x, 0) for x in to_hit_why]

                # NOTE: Won't include damage in 'why' at this point since
                # there're no mods to damage

        ignore, defense_why = self.__ruleset.get_fighter_defenses_notes(
                                                            current_fighter)
        pseudo_menu.extend([(x, 0) for x in defense_why])

        ignore = self._window_manager.menu(
                    'How the Numbers Were Calculated', pseudo_menu)

        return True


    def __timer(self):
        '''
        Command ribbon method.
        Asks user for information for timer to add to a fighter.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Who gets the timer?

        current_fighter = self.__current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        if opponent is None:
            timer_recipient = current_fighter
        else:
            timer_recipient_menu = [(current_fighter.name, current_fighter),
                                    (opponent.name, opponent)]
            timer_recipient = self._window_manager.menu('Who Gets Timer',
                                                        timer_recipient_menu,
                                                        0)
        if timer_recipient is None:
            return True # Keep fighting

        # How long is the timer?

        timer = {'rounds': 0, 'string': None}
        title = 'Rounds To Wait...'
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        timer['rounds'] = int(adj_string)
        if timer['rounds'] < 1:
            return True # Keep fighting (even without installing the timer)

        # What is the timer's message?

        title = 'What happens in %d rounds?' % timer['rounds']
        height = 1
        width = curses.COLS - 4
        timer['string'] = self._window_manager.input_box(
                height,
                self._window.fighter_win_width - 
                        self._window.len_timer_leader,
                title)

        # Instal the timer.

        if timer['string'] is not None and len(timer['string']) != 0:
            timer_recipient.add_timer(timer['rounds'], timer['string'])

        return True # Keep fighting


class MainHandler(ScreenHandler):
    def __init__(self, window_manager, world, ruleset, campaign_debug_json):
        super(MainHandler, self).__init__(window_manager, campaign_debug_json)
        self.__world = world
        self.__ruleset = ruleset
        self._add_to_choice_dict({
            # TODO: template - (build a template of monsters)
            ord('F'): {'name': 'Fight (build)', 'func': self.__build_fight},
            ord('f'): {'name': 'fight (run)',   'func': self.__run_fight},
            ord('H'): {'name': 'Heal',          'func': self.__fully_heal},
            ord('n'): {'name': 'name',          'func': self.__get_a_name},
            ord('q'): {'name': 'quit',          'func': self.__quit}
        })
        self._window = MainGmWindow(self._window_manager)

    #
    # Protected Methods
    #

    def _draw_screen(self):
        self._window.clear()
        self._window.command_ribbon(self._choices)

    #
    # Private Methods - callbacks for 'choices' array for menu
    #

    def __build_fight(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world,
                                        campaign_debug_json)
        build_fight.handle_user_input_until_done()
        self._draw_screen() # Redraw current screen when done building fight.
        return True # Keep going


    def __fully_heal(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        for character_details in self.__world['PCs'].itervalues():
            self.__ruleset.heal_fighter(character_details)
        return True

    def __get_a_name(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if 'Names' not in self.__world:
            self._window_manager.error(['There are no "Names" in the database'])
            return True

        type_menu = [(x, x) for x in self.__world['Names'].keys()]
        type_name = self._window_manager.menu('What kind of name', type_menu)
        if type_name is None:
            type_name = random.choice(self.__world['Names'].keys())
            gender_name = random.choice(self.__world['Names'][type_name].keys())

        else:
            gender_menu = [(x, x)
                           for x in self.__world['Names'][type_name].keys()]
            gender_name = self._window_manager.menu('What Gender', gender_menu)

        index = random.randint(0,
            len(self.__world['Names'][type_name][gender_name]) - 1)

        # This really isn't a menu but it works perfectly to accomplish my
        # goal.
        result = [(self.__world['Names'][type_name][gender_name][index],
                   index)]
        ignore = self._window_manager.menu('Your %s %s name is' % (
                                           type_name, gender_name), result)
        return True


    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self._window.close()
        del self._window
        self._window = None
        return False # Leave


    def __run_fight(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        monster_group = None
        if not self.__world['current-fight']['saved']:
            fight_name_menu = [(name, name)
                               for name in self.__world['monsters'].keys()]
            # PP.pprint(fight_name_menu)
            monster_group = self._window_manager.menu('Fights',
                                                      fight_name_menu)
            if monster_group is None:
                return True
            if (monster_group not in self.__world['monsters']):
                print 'ERROR, monster list %s not found' % monster_group
                return True

        fight = FightHandler(self._window_manager,
                             self.__world,
                             monster_group,
                             self.__ruleset,
                             self._campaign_debug_json)
        fight.handle_user_input_until_done()
        self._draw_screen() # Redraw current screen when done with the fight.

        return True # Keep going


class MyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2) 


def timeStamped(fname, ext, fmt='{fname}-%Y-%m-%d-%H-%M-%S.{ext}'):
    return datetime.datetime.now().strftime(fmt).format(fname=fname, ext=ext)

# Main
if __name__ == '__main__':
    parser = MyArgumentParser()
    parser.add_argument('filename',
             nargs='?', # We get the filename elsewhere if you don't say here
             help='Input JSON file containing characters and monsters')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)
    parser.add_argument('-m', '--maintainjson',
             help='Don\'t overwrite the input JSON.  Only for debugging.',
             action='store_true',
             default=False)

    ARGS = parser.parse_args()

    # parser.print_help()
    # sys.exit(2)

    PP = pprint.PrettyPrinter(indent=3, width=150)

    with GmWindowManager() as window_manager:
        ruleset = GurpsRuleset(window_manager)

        # Prefs
        # NOTE: When other things find their way into the prefs, the scope
        # of the read_prefs GmJson will have to be larger
        prefs = {}
        with GmJson('gm.txt') as read_prefs:
            prefs = read_prefs.read_data

            # Get the Campaign's Name
            filename = ARGS.filename
            if filename is not None:
                read_prefs.write_data = prefs
                prefs['campaign'] = filename

            elif 'campaign' in prefs:
                filename = prefs['campaign']

            if filename is None:
                filename_menu = [
                    (x, x) for x in os.listdir('.') if x.endswith('.json')]

                filename = window_manager.menu('Which File', filename_menu)
                if filename is None:
                    window_manager.error(['Need to specify a JSON file'])
                    sys.exit(2)

                read_prefs.write_data = prefs
                prefs['campaign'] = filename

        # Read the Campaign Data
        with GmJson(filename, window_manager) as campaign:
            if campaign.read_data is None:
                window_manager.error(['JSON file "%s" did not parse right'
                                        % filename])
                sys.exit(2)

            # Save the JSON for debugging, later
            debug_directory = 'debug'
            if not os.path.exists(debug_directory):
                os.makedirs(debug_directory)
            campaign_debug_json = os.path.join(debug_directory,
                                               timeStamped('debug_json','txt'))
            with open(campaign_debug_json, 'w') as f:
                json.dump(campaign.read_data, f, indent=2)

            # Error check the JSON
            if 'PCs' not in campaign.read_data:
                window_manager.error(['No "PCs" in %s' % filename])
                sys.exit(2)

            # Save the state of things when we leave since there wasn't a
            # horrible crash while reading the data.
            if not ARGS.maintainjson:
                campaign.write_data = campaign.read_data

            # Enter into the mainloop
            main_handler = MainHandler(window_manager,
                                       campaign.read_data,
                                       ruleset,
                                       campaign_debug_json)

            if campaign.read_data['current-fight']['saved']:
                fight_handler = FightHandler(window_manager,
                                             campaign.read_data,
                                             None,
                                             ruleset,
                                             campaign_debug_json)
                fight_handler.handle_user_input_until_done()
            main_handler.handle_user_input_until_done()

