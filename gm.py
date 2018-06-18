#! /usr/bin/python

import argparse
import copy
import curses
import curses.textpad
import json
import os
import pprint
import random
import sys

# TODO:
#   - guns w/shots and reload time (so equipment, equip, unequip, ...)
#   - add 'attacker or defender' menu to all actions
#   - summary chart
#   - < 1/3 FP = 1/2 move, dodge, st
#   - truncate (don't wrap) long lines
#   - HP/FP on second line
#   - history of actions in a fight
#   - remind to do action when going to next creature
#   - attack / active defense numbers on screen
#   - position w/plusses and minuses
#   - high pain threshold = no shock
#
# TODO (eventually)
#   - TESTS, for the love of God
#   - scrolling menus (et al.)
#   - entering monsters and characters from the screen


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

            choice_string = '| %s %s ' % (command_string, body['name'])
            choice_strings.append(choice_string)
            if max_width < len(choice_string):
                max_width = len(choice_string)

        # Calculate the number of rows needed for all the commands

        lines, cols = self._window.getmaxyx()
        choices_per_line = int((cols - 1)/max_width) # -1 for last '|'
        # Adding 0.9999 so last partial line doesn't get truncated by 'int'
        lines_for_choices = int((len(choices) / (choices_per_line + 0.0))
                                                                + 0.9999999)

        # Print stuff out

        choice_strings.sort(reverse=True, key=lambda s: s.lower())
        line = lines - 1 # -1 because last line is lines-1
        for subline in reversed(range(lines_for_choices)):
            line = lines - (subline + 1) # -1 because last line is lines-1
            left = 0
            for i in range(choices_per_line):
                choice_string = ('|' if len(choice_strings) == 0
                                     else choice_strings.pop())
                self._window.addstr(line, left, choice_string, curses.A_NORMAL)
                left += max_width
            self._window.addstr(line, left, '|', curses.A_NORMAL)
        self.refresh()


    def getmaxyx(self):
        return self._window.getmaxyx()

    def refresh(self):
        self._window.refresh()


    def touchwin(self):
        self._window.touchwin()

    #
    # Private methods
    #



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

        self.__FIGHTER_LINE = 4
        self.__NEXT_LINE = 2

        self.__character_window = None
        self.__opponent_window = None
        self.__summary_window = None
        self.fighter_win_width = 0
        self.__round_count_string = '%d Rnds: '
        # assume rounds takes as much space as '%d' 
        self.len_timer_leader = len(self.__round_count_string)

        self.__state_color = {
                Ruleset.FIGHTER_STATE_HEALTHY  : GmWindowManager.GREEN_BLACK,
                Ruleset.FIGHTER_STATE_INJURED  : GmWindowManager.YELLOW_BLACK,
                Ruleset.FIGHTER_STATE_CRITICAL : GmWindowManager.RED_BLACK,
                Ruleset.FIGHTER_STATE_DEAD     : GmWindowManager.RED_BLACK}

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


    def touchwin(self):
        super(FightGmWindow, self).touchwin()
        if self.__character_window is not None:
            self.__character_window.touchwin()
        if self.__opponent_window is not None:
            self.__opponent_window.touchwin()
        if self.__summary_window is not None:
            self.__summary_window.touchwin()


    def show_fighters(self,
                      current_name,
                      current_fighter_details,
                      opponent_name,
                      opponent_details,
                      next_PC_name,
                      fight
                     ):
        '''
        Displays the current state of the current fighter and his opponent,
        if he has one.
        '''

        if next_PC_name is not None:
            self._window.move(self.__NEXT_LINE, self.__FIGHTER_COL)
            self._window.clrtoeol()
            self._window.addstr(self.__NEXT_LINE,
                                self.__FIGHTER_COL,
                                '(Next: %s)' % next_PC_name)


        self._window.move(self.__FIGHTER_LINE, self.__FIGHTER_COL)
        self._window.clrtoeol()

        if self.__show_fighter(current_name,
                               current_fighter_details,
                               self.__FIGHTER_COL):
            self.__show_fighter_notes(self.__character_window,
                                      current_fighter_details)

        if opponent_details is None:
            self.__opponent_window.clear()
            self.__opponent_window.refresh()
        else:
            if self.__show_fighter(opponent_name,
                                   opponent_details,
                                   self.__OPPONENT_COL+4):
                self.__show_fighter_notes(self.__opponent_window,
                                          opponent_details)
        self.show_summary_window(fight)
        self.refresh()


    def round_ribbon(self,
                     round_no,
                     saved,
                     current_fighter, # use in future
                     next_fighter # use in future
                    ):
        '''Prints the fight round information at the top of the screen.'''

        self._window.move(0, 0)
        self._window.clrtoeol()

        round_string = 'Round %d' % round_no
        self._window.addstr(0, # y
                            0, # x
                            round_string,
                            curses.A_NORMAL)
        if saved:
            string = "SAVED"
            length = len(string)
            lines, cols = self._window.getmaxyx()
            self._window.addstr(0, # y
                                cols - (length + 1), # x
                                string,
                                curses.A_BOLD)
        self._window.refresh()


    def show_summary_window(self, fight):
        self.__summary_window.clear()
        for line, fighter in enumerate(fight['fighters']):
            fighter_state = self.__ruleset.get_fighter_state(fighter['details'])
            mode = self.__state_color[fighter_state]
            fighter_string = '%s%s HP:%d/%d' % (
                ('> ' if line == fight['index'] else '  '),
                fighter['name'],
                fighter['details']['current']['hp'],
                fighter['details']['permanent']['hp'])
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


    def __show_fighter(self,
                       fighter_name,    # String holding name of fighter
                       fighter_details, # dict holding fighter information
                       column
                      ):
        is_alive = True # alive
        if fighter_details['alive']:
            fighter_string = '%s HP: %d/%d FP: %d/%d' % (
                fighter_name,
                fighter_details['current']['hp'],
                fighter_details['permanent']['hp'],
                fighter_details['current']['fp'],
                fighter_details['permanent']['fp'])

            fighter_state = self.__ruleset.get_fighter_state(fighter_details)
            mode = self.__state_color[fighter_state]
        else:
            fighter_string = '(DEAD)'
            mode = self.__state_color(Ruleset.FIGHTER_STATE_DEAD)
            is_alive = False

        self._window.addstr(self.__FIGHTER_LINE, column, fighter_string, mode)
        return is_alive


    def __show_fighter_notes(self,
                             window,            # Curses window for fighter's
                                                #   notes
                             fighter_details,   # The dict w/the fighter info
                            ):
        '''
        Displays ancillary information about the fighter
        '''
        window.clear()
        line = 0
        mode = curses.A_NORMAL

        # NOTE: { belongs in Ruleset

        if fighter_details['shock'] != 0:
            string = 'DX and IQ are at %d' % fighter_details['shock']
            window.addstr(line, 0, string, mode)
            line += 1

        if (fighter_details['current']['hp'] <
                                    fighter_details['permanent']['hp']/3.0):
            window.addstr(line, 0, "Dodge/move are at 1/2", mode)
            line += 1

        # Each round you do something

        if (fighter_details['current']['fp'] <=
                                        -fighter_details['permanent']['fp']):
            # TODO: have an 'unconscious' flag that allows creatures to
            # show up but doesn't allow them to do anything.  Maybe make
            # 'dead' act different between monsters and PCs
            window.addstr(line, 0, "*UNCONSCIOUS*", curses.A_REVERSE)
            line += 1

        else:
            if fighter_details['current']['fp'] <= 0:
                window.addstr(line, 0, "On action: Will roll or pass out", mode)
                line += 1

            if fighter_details['current']['hp'] <= 0:
                window.addstr(line, 0, "On turn: 3d vs HT or pass out", mode)
                line += 1

        if fighter_details['check_for_death']:
            window.addstr(line, 0, "3d vs HT or DIE", curses.A_REVERSE)
            fighter_details['check_for_death'] = False  # Only show/roll once
            line += 1

        # NOTE: end of Ruleset }

        # Timers
        for timer in fighter_details['timers']:
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

        if 'notes' in fighter_details and fighter_details['notes'] is not None:
            for note in fighter_details['notes'].split('\n'):
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
    (GREEN_BLACK,   # green text over black background
     YELLOW_BLACK,
     RED_BLACK,
     RED_WHITE) = range(1, 5)

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
        self.__window_stack = [] # Stack of GmWindow


    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
            curses.start_color()
            curses.noecho()
            curses.cbreak() # respond instantly to keystrokes
            self.__stdscr.keypad(1) # special characters converted by curses
                                    # (e.g., curses.KEY_LEFT)

            curses.init_pair(GmWindowManager.GREEN_BLACK,
                             curses.COLOR_GREEN, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.YELLOW_BLACK,
                             curses.COLOR_YELLOW, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.RED_BLACK,
                             curses.COLOR_RED, # fg
                             curses.COLOR_BLACK) # bg
            curses.init_pair(GmWindowManager.RED_WHITE,
                             curses.COLOR_RED, # fg
                             curses.COLOR_WHITE) # bg

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
              title=" ERROR "
             ):
        '''Provides an error to the screen.'''

        #mode = curses.A_NORMAL # curses.color_pair(GmWindowManager.RED_WHITE)
        mode = curses.color_pair(GmWindowManager.RED_WHITE)
        width = max(len(string) for string in strings)
        if width < len(title):
            width = len(title)
        width += 2 # Need some margin
        border_win, error_win = self.__centered_boxed_window(len(strings),
                                                             width,
                                                             title,
                                                             mode)
        for line, string in enumerate(strings):
            #print "line %r string %r (len=%d)" % (line, string, len(string))
            error_win.addstr(line, 0, string, mode)
        error_win.refresh()

        ignored = self.get_one_character()
        #ignored = self.get_string(error_win)

        del border_win
        del error_win
        self.hard_refresh_all()
        return string

    def get_fight_gm_window(self, ruleset):
        return FightGmWindow(self, ruleset)

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
             strings_results # array of tuples (string, return value)
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


    def refresh_all(self):
        '''
        Refreshes all of the windows, from back to front
        '''
        for window in self.__window_stack:
            window.refresh()

    def hard_refresh_all(self):
        '''
        Touches and refreshes all of the windows, from back to front
        '''
        for window in self.__window_stack:
            window.touchwin()

        for window in self.__window_stack:
            window.refresh()



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


class Ruleset(object):
    (FIGHTER_STATE_HEALTHY,
     FIGHTER_STATE_INJURED,
     FIGHTER_STATE_CRITICAL,
     FIGHTER_STATE_DEAD) = range(4)

    def __init__(self):
        pass

    def new_fight(self, fighter):
        '''
        Removes all the stuff from the old fight except injury.
        '''
        fighter['alive'] = True
        fighter['timers'] = []
        fighter['stuff'] = []
        fighter['weapon'] = None # What's the form of this?
        fighter['opponent'] = None

    def heal_fighter(self, fighter):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        for stat in fighter['permanent'].iterkeys():
            fighter['current'][stat] = fighter['permanent'][stat]
        fighter['alive'] = True

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


class GurpsRuleset(Ruleset):
    '''
    This is a place for all of the ruleset (e.g., GURPS, AD&D) specific
    stuff.
    '''

    def __init__(self):
        super(GurpsRuleset, self).__init__()

    # TODO: need a template for new characters

    def new_fight(self, fighter):
        '''
        Removes all the stuff from the old fight except injury.
        '''
        super(GurpsRuleset, self).new_fight(fighter)
        fighter['shock'] = 0

    def get_fighter_state(self, fighter_details):

        if (fighter_details['current']['fp'] <= 0 or
                                    fighter_details['current']['hp'] <= 0):
            return Ruleset.FIGHTER_STATE_CRITICAL

        if (fighter_details['current']['hp'] <
                                    fighter_details['permanent']['hp']):
            return Ruleset.FIGHTER_STATE_INJURED

        return Ruleset.FIGHTER_STATE_HEALTHY


    def heal_fighter(self, fighter):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        super(GurpsRuleset, self).heal_fighter(fighter)
        fighter['shock'] = 0
        fighter['last_negative_hp'] = 0
        fighter['check_for_death'] = False


    def initiative(self,
                   fighter # dict for the creature as in the json file
                  ):
        return (fighter['current']['basic-speed'],
                fighter['current']['dx'],
                Ruleset.roll(1, 6)
                )


class ScreenHandler(object):
    '''
    Base class for the "business logic" backing the user interface.
    '''

    def __init__(self, window_manager):
        self._window_manager = window_manager
        self._choices = { }


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


    def _draw_screen(self):
        pass


class BuildFightHandler(ScreenHandler):
    def __init__(self,
                 window_manager,
                 world
                ):
        super(BuildFightHandler, self).__init__(window_manager)
        self._choices = {
            ord('a'): {'name': 'add monster', 'func': self.__add_monster},
            ord('d'): {'name': 'delete monster', 'func': self.__delete_monster},
            ord('q'): {'name': 'quit', 'func': self.__quit},
            # TODO: need a quit but don't save option
        }
        self._window = BuildFightGmWindow(self._window_manager)

        self.__world = world

        lines, cols = self._window.getmaxyx()
        template_menu = [(template_name, template_name)
                for template_name in self.__world["Templates"]]
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


    def _draw_screen(self):
        self._window.clear()
        self._window.command_ribbon(self._choices)


    def __add_monster(self):
        # Based on which monster from the template
        monster_menu = [(from_monster_name, from_monster_name)
                for from_monster_name in world["Templates"][self.__template_name]]
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
            world["Templates"][self.__template_name][from_monster_name])
        to_monster = {'alive': True,
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
                 ruleset
                ):
        super(FightHandler, self).__init__(window_manager)
        self._window = self._window_manager.get_fight_gm_window(ruleset)
        self.__ruleset = ruleset

        self._choices = {
            ord(' '): {'name': 'next', 'func': self.__next_fighter},
            ord('<'): {'name': 'prev', 'func': self.__prev_fighter},
            ord('a'): {'name': 'action', 'func': self.__action},
            ord('d'): {'name': 'dead', 'func': self.__dead},
            # NOTE: 'h' and 'f' belong in Ruleset
            ord('f'): {'name': 'FP damage', 'func': self.__damage_FP},
            ord('h'): {'name': 'HP damage', 'func': self.__damage_HP},
            ord('n'): {'name': 'notes', 'func': self.__notes},
            ord('o'): {'name': 'opponent', 'func': self.__pick_opponent},
            ord('q'): {'name': 'quit', 'func': self.__quit},
            ord('s'): {'name': 'save', 'func': self.__save},
            ord('t'): {'name': 'timer', 'func': self.__timer}
        }

        self.__action_menu = [
            ('attack',                 ['Attack',
                                        ' Defense: any',
                                        ' Move: step']),
            ('Attack, all out',        ['All out attack',
                                        ' Defense: none',
                                        ' Move: 1/2']),
            ('ready',                  ['Ready',
                                        ' Defense: any',
                                        ' Move: step']),
            ('move',                   ['Move',
                                        ' Defense: any',
                                        ' Move: full']),
            ('Move and attack',        ['Move & Attack',
                                        ' Defense: Dodge,block',
                                        ' Move: full']),
            ('Defense, all out',       ['All out defense',
                                        ' Defense: double',
                                        ' Move: step']),
            ('change posture',         ['Change posture',
                                        ' Defense: any',
                                        ' Move: none']),
            ('concentrate',            ['Concentrate',
                                        ' Defense: any w/will roll',
                                        ' Move: step']),
            ('nothing: stun/surprise', ['Do nothing',
                                        ' Defense: any @-4',
                                        ' Move: none']),
            ('Nothing',                ['Do nothing',
                                        ' Defense: any',
                                        ' Move: none']),
            ('aim',                    ['Aim',
                                        ' Defense: any loses aim',
                                        ' Move: step']),
            ('feint',                  ['Feint',
                                        ' Defense: any, parry *',
                                        ' Move: step']),
            ('wait',                   ['Wait',
                                        ' Defense: any, no AA attack ',
                                        ' Move: none']),
            ('evaluate',               ['Evaluate',
                                        ' Defense: any',
                                        ' Move: step']),
        ]

        self.__world = world
        self.__fight = world["current-fight"]

        if not self.__fight['saved']:
            self.__fight['round'] = 0
            self.__fight['index'] = 0
            self.__fight['monsters'] = monster_group

            #self.__fight['fighters'].extend(['PCs', name] for name in
            #        world['PCs'].keys())

            self.__fight['fighters'] = [] # list of {'group': xxx,
                                          #          'name': xxx,
                                          #          'details' : xxx}
                                          #  where 
                                          #   'group' is 'PCs' or the monster
                                          #      list, and
                                          #   'details' is the complete
                                          #      description of the fighter as
                                          #      seen in the JSON.
            self.__fight['fighters'].extend({'group': 'PCs',
                                             'name': dude[0],
                                             'details': dude[1]} for dude in
                                                    world['PCs'].iteritems())
            if monster_group is not None:
                self.__fight['fighters'].extend(
                        ({'group': monster_group,
                          'name': dude[0],
                          'details': dude[1]}) for dude in
                     self.__world['monsters'][monster_group].iteritems())

            # Sort by initiative = basic-speed followed by DEX followed by
            # random
            self.__fight['fighters'].sort(
                    key=lambda fighter:
                        self.__ruleset.initiative(fighter['details']),
                    reverse=True)

            # Make sure this looks like a _NEW_ fight.
            for fighter in self.__fight['fighters']:
                self.__ruleset.new_fight(fighter['details'])

        self.__fight['saved'] = False
        self._window.start_fight()

    def handle_user_input_until_done(self):
        super(FightHandler, self).handle_user_input_until_done()

        # When done, move current fight to 'dead-monsters'
        if not self.__fight['saved']:
            self.__world['dead-monsters'][self.__fight['monsters']] = (
                    self.__world['monsters'][self.__fight['monsters']])
            del(self.__world['monsters'][self.__fight['monsters']])

    def __action(self):
        action = self._window_manager.menu('Action', self.__action_menu)
        if action is not None:
            current_name, current_fighter_details = self.__current_fighter()
            current_fighter_details['timers'].append({'rounds': 1,
                                              'string': action})

            opponent_name, opponent_details = self.__opponent_details(
                                                        current_fighter_details)
            next_PC_name = self.__next_PC_name()
            self._window.show_fighters(current_name, current_fighter_details,
                                       opponent_name, opponent_details,
                                       next_PC_name,
                                       self.__fight)
            return True # Keep going

    def __current_fighter(self):
        index = self.__fight['index']
        # returns the name and the dict
        return (self.__fight['fighters'][index]['name'],
                self.__fight['fighters'][index]['details'])


    def __dead(self):
        current_name, current_fighter_details = self.__current_fighter()
        opponent_name, opponent_details = self.__opponent_details(
                                                    current_fighter_details)
        if opponent_details is not None:
            opponent_details['alive'] = False

            next_PC_name = self.__next_PC_name()
            self._window.show_fighters(current_name, current_fighter_details,
                                       opponent_name, opponent_details,
                                       next_PC_name,
                                       self.__fight)
        return True # Keep going


    def __damage_FP(self):
        current_name, current_fighter_details = self.__current_fighter()
        opponent_name, opponent_details = self.__opponent_details(
                                                        current_fighter_details)
        if opponent_details is None:
            return True

        title = 'Change FP By...'
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        adj = int(adj_string)
        hp_adj = 0

        # If FP go below zero, you lose HP along with FP
        # TODO: all of FP belongs in Ruleset
        if adj < 0  and -adj > opponent_details['current']['fp']:
            hp_adj = adj
            if opponent_details['current']['fp'] > 0:
                hp_adj += opponent_details['current']['fp']

        opponent_details['current']['hp'] += hp_adj # NOTE: belongs in Ruleset
        opponent_details['current']['fp'] += adj # NOTE: belongs in Ruleset
        next_PC_name = self.__next_PC_name()
        self._window.show_fighters(current_name, current_fighter_details,
                                   opponent_name, opponent_details,
                                   next_PC_name,
                                   self.__fight)
        return True # Keep going


    def __damage_HP(self):
        current_name, current_fighter_details = self.__current_fighter()
        opponent_name, opponent_details = self.__opponent_details(
                                                        current_fighter_details)
        if opponent_details is not None:
            title = 'Change HP By...'
            height = 1
            width = len(title)
            adj_string = self._window_manager.input_box(height, width, title)
            adj = int(adj_string)

            # NOTE: check for death belongs in Ruleset
            if adj < 0 and opponent_details['current']['hp'] < 0:
                before_hp = opponent_details['current']['hp']
                before_hp_multiple = (before_hp /
                                        opponent_details['permanent']['hp'])
                after_hp = (opponent_details['current']['hp'] + adj) * 1.0 + 0.1
                after_hp_multiple = (after_hp /
                                        opponent_details['permanent']['hp'])
                if int(before_hp_multiple) != int(after_hp_multiple):
                    opponent_details['check_for_death'] = True

            # NOTE: shock belongs in Ruleset
            shock_amount = -4 if adj <= -4 else adj
            if opponent_details['shock'] > shock_amount:
                opponent_details['shock'] = shock_amount

            opponent_details['current']['hp'] += adj # NOTE: belongs in Ruleset
            next_PC_name = self.__next_PC_name()
            self._window.show_fighters(current_name, current_fighter_details,
                                       opponent_name, opponent_details,
                                       next_PC_name,
                                       self.__fight)
        return True # Keep going


    def _draw_screen(self):
        self._window.clear()
        current_name, current_fighter_details = self.__current_fighter()
        opponent_name, opponent_details = self.__opponent_details(
                                                        current_fighter_details)
        self._window.round_ribbon(self.__fight['round'],
                                   self.__fight['saved'],
                                   current_fighter_details, # up now
                                   None) #self.xxx) # next PC
        next_PC_name = self.__next_PC_name()
        self._window.show_fighters(current_name, current_fighter_details,
                                   opponent_name, opponent_details,
                                   next_PC_name,
                                   self.__fight)
        self._window.command_ribbon(self._choices)


    def __fighter_details(self,
                         group, # 'PCs' or some group under world['monsters']
                         name   # name of a fighter in that group
                        ):
        return (self.__world['PCs'][name] if group == 'PCs' else
                self.__world['monsters'][group][name])


    def __is_alive(self, fighter):
        if fighter['alive'] and (fighter['current']['hp'] > 0):
            return True
        return False

    def __modify_index(self,
                       adj      # 1 or -1, adjust the index by this
                      ):
        '''
        Increment or decrement the index.  Only stop on living creatures.
        '''

        first_index = self.__fight['index']

        keep_going = True

        while keep_going:
            self.__fight['index'] += adj
            if self.__fight['index'] >= len(self.__fight['fighters']):
                self.__fight['index'] = 0
                self.__fight['round'] += adj 
            elif self.__fight['index'] < 0:
                self.__fight['index'] = len(self.__fight['fighters']) - 1
                self.__fight['round'] += adj 
            current_name, current_fighter_details = self.__current_fighter()
            if (current_fighter_details['alive'] or
                    (self.__fight['index'] == first_index)):
                keep_going = False


    def __next_fighter(self):
        # NOTE: shock belongs in Ruleset
        prev_name, prev_fighter_details = self.__current_fighter()
        prev_fighter_details['shock'] = 0 # remove expired shock entry

        # remove any expired timers
        remove_these = []
        for index, timer in enumerate(prev_fighter_details['timers']):
            if timer['rounds'] <= 0:
                remove_these.insert(0, index) # largest indexes last
        for index in remove_these:
            del prev_fighter_details['timers'][index]

        # get next fighter
        self.__modify_index(1)
        self._window.round_ribbon(self.__fight['round'],
                                   self.__fight['saved'],
                                   None, # current fighter
                                   None) # next PC
        current_name, current_fighter_details = self.__current_fighter()
        for timer in current_fighter_details['timers']:
            timer['rounds'] -= 1
        next_PC_name = self.__next_PC_name()
        opponent_name, opponent_details = self.__opponent_details(
                                                        current_fighter_details)
        self._window.show_fighters(current_name, current_fighter_details,
                                   opponent_name, opponent_details,
                                   next_PC_name,
                                   self.__fight)
        return True # Keep going

    def __next_PC_name(self):
        next_PC_name = None
        next_index = self.__fight['index'] + 1
        for ignore in self.__fight['fighters']:
            if next_index >= len(self.__fight['fighters']):
                next_index = 0
            if self.__fight['fighters'][next_index]['group'] == 'PCs':
                next_PC_name = self.__fight['fighters'][next_index]['name']
                break
            next_index += 1
        return next_PC_name

    def __notes(self):
        current_name, current_fighter_details = self.__current_fighter()
        lines, cols = self._window.getmaxyx()

        notes = (None if 'notes' not in current_fighter_details else
                                            current_fighter_details['notes'])
        notes = self._window_manager.edit_window(
                    lines - 4,
                    self._window.fighter_win_width,
                    notes,  # initial string (w/ \n) for the window
                    '%s Notes' % current_name,
                    '^G to exit')
        current_fighter_details['notes'] = notes

        # Redraw the fighters
        next_PC_name = self.__next_PC_name()
        opponent_name, opponent_details = self.__opponent_details(
                                                        current_fighter_details)
        self._window.show_fighters(current_name, current_fighter_details,
                                   opponent_name, opponent_details,
                                   next_PC_name,
                                   self.__fight)
        return True # Keep going

    def __opponent_details(self,
                          fighter_details # dict for a fighter as in the JSON
                         ):
        if fighter_details is None or fighter_details['opponent'] is None:
            return None, None

        opponent_name = fighter_details['opponent']['name']
        opponent_details = self.__fighter_details(
                                        fighter_details['opponent']['group'],
                                        fighter_details['opponent']['name'])
        return opponent_name, opponent_details


    def __pick_opponent(self):
        current_name, current_fighter_details = self.__current_fighter()
        current_index = self.__fight['index']
        current_group = self.__fight['fighters'][current_index]['group']
        current_name  = self.__fight['fighters'][current_index]['name']

        opponent_group = None
        opponent_menu = []
        for fighter in self.__fight['fighters']:
            if fighter['group'] != current_group:
                opponent_group = fighter['group']
                if self.__is_alive(fighter['details']):
                    opponent_menu.append((fighter['name'], fighter['name']))
        if len(opponent_menu) <= 0:
            self._window_manager.error(['All the opponents are dead'])
            return True # don't leave the fight

        opponent_name = self._window_manager.menu('Opponent', opponent_menu)

        if opponent_name is None:
            return True # don't leave the fight

        current_fighter_details['opponent'] = {'group': opponent_group,
                                       'name': opponent_name}
        opponent_details = self.__fighter_details(opponent_group, opponent_name)

        # Ask to have them fight each other
        if (opponent_details is not None and
                                        opponent_details['opponent'] is None):
            back_menu = [('yes', True), ('no', False)]
            answer = self._window_manager.menu('Make Opponents Go Both Ways',
                                        back_menu)
            if answer == True:
                opponent_details['opponent'] = {'group': current_group,
                                        'name': current_name}

        next_PC_name = self.__next_PC_name()
        self._window.show_fighters(current_name, current_fighter_details,
                                   opponent_name, opponent_details,
                                   next_PC_name,
                                   self.__fight)
        return True # Keep going


    def __prev_fighter(self):
        if self.__fight['index'] == 0 and self.__fight['round'] == 0:
            return True # Not going backwards from the origin

        self.__modify_index(-1)
        self._window.round_ribbon(self.__fight['round'],
                                   self.__fight['saved'],
                                   None, # current fighter
                                   None) # next PC
        current_name, current_fighter_details = self.__current_fighter()
        next_PC_name = self.__next_PC_name()
        opponent_name, opponent_details = self.__opponent_details(
                                                        current_fighter_details)
        self._window.show_fighters(current_name, current_fighter_details,
                                   opponent_name, opponent_details,
                                   next_PC_name,
                                   self.__fight)
        return True # Keep going


    def __quit(self):
        if not self.__fight['saved']:

            # Check to see if all monsters are dead
            ask_to_save = False
            for fighter in self.__fight['fighters']:
                if fighter['group'] != 'PCs' and self.__is_alive(
                                                        fighter['details']):
                    ask_to_save = True

            # Ask to save the fight if it's not saved and some monsters live.
            save_menu = [('yes', True), ('no', False)]
            if ask_to_save and self._window_manager.menu('Save Fight',
                                                         save_menu):
                self.__fight['saved'] = True
                
        self._window.close()
        return False # Leave the fight

    def __save(self):
        self.__fight['saved'] = True
        self._window.round_ribbon(self.__fight['round'],
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
        adj_string = self._window_manager.input_box(height, width, title)
        timer['rounds'] = int(adj_string)
        if timer['rounds'] < 1:
            return True # Keep fighting (even without installing the timer)

        title = 'What happens in %d rounds?' % timer['rounds']
        height = 1
        width = curses.COLS - 4
        timer['string'] = self._window_manager.input_box(
                height,
                self._window.fighter_win_width - 
                        self._window.len_timer_leader,
                title)

        if timer['string'] is not None and len(timer['string']) != 0:
            current_name, current_fighter_details = self.__current_fighter()
            current_fighter_details['timers'].append(timer)

        return True # Keep fighting


class MainHandler(ScreenHandler):
    def __init__(self, window_manager, world, ruleset):
        super(MainHandler, self).__init__(window_manager)
        self.__world = world
        self.__ruleset = ruleset
        self._choices = {
            # TODO: template - (build a template of monsters)
            ord('F'): {'name': 'Fight (build)', 'func': self.__build_fight},
            ord('f'): {'name': 'fight (run)', 'func': self.__run_fight},
            ord('H'): {'name': 'Heal',  'func': self.__fully_heal},
            ord('n'): {'name': 'name',  'func': self.__get_a_name},
            ord('q'): {'name': 'quit',  'func': self.__quit}
        }
        self._window = MainGmWindow(self._window_manager)

    def _draw_screen(self):
        self._window.clear()
        self._window.command_ribbon(self._choices)


    def __build_fight(self):
        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world)
        build_fight.handle_user_input_until_done()
        self._draw_screen() # Redraw current screen when done building fight.

        return True # Keep going


    def __fully_heal(self):
        for character in self.__world['PCs'].itervalues():
            self.__ruleset.heal_fighter(character)
        return True

    def __get_a_name(self):
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

    def __run_fight(self):
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
                print "ERROR, monster list %s not found" % monster_group
                return True

        fight = FightHandler(self._window_manager,
                             self.__world,
                             monster_group,
                             self.__ruleset)
        fight.handle_user_input_until_done()
        self._draw_screen() # Redraw current screen when done with the fight.

        return True # Keep going


    def __quit(self):
        self._window.close()
        del self._window
        self._window = None
        return False # Leave


class MyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2) 


# Main
if __name__ == '__main__':
    parser = MyArgumentParser()
    parser.add_argument('filename',
             nargs='?', # We get the filename elsewhere if you don't say here
             help='Input JSON file containing characters and monsters')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)

    ARGS = parser.parse_args()

    # parser.print_help()
    # sys.exit(2)

    PP = pprint.PrettyPrinter(indent=3, width=150)
    ruleset = GurpsRuleset()

    with GmWindowManager() as window_manager:
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

            # Error check the JSON
            if 'PCs' not in campaign.read_data:
                window_manager.error(['No "PCs" in %s' % filename])
                sys.exit(2)

            # Save the state of things when we leave since there wasn't a
            # horrible crash while reading the data.
            campaign.write_data = campaign.read_data

            # Enter into the mainloop
            main_handler = MainHandler(window_manager,
                                       campaign.read_data,
                                       ruleset)

            if campaign.read_data['current-fight']['saved']:
                fight_handler = FightHandler(window_manager,
                                             campaign.read_data,
                                             None,
                                             ruleset)
                fight_handler.handle_user_input_until_done()
            main_handler.handle_user_input_until_done()


