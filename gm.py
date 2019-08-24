#! /usr/bin/python

import argparse
import copy
import curses
import curses.ascii
import curses.textpad
import datetime
import json
import os
import pprint
import random
import re
import sys
import traceback

# TODO:
#   - Fighter objects should be saved and passed around rather than re-created
#   - campaign_debug_json doesn't need to be passed around since it's in
#     World.
#   - Monsters should have a way to get pocket lint.
#   - Need to be able to generate a blank creature (maybe it's a default
#     Template).
#   - Should have a 'post-action-accounting' method where an action can be
#     augmented. (?)  Need to save to history first.  Also need to append to
#     actions this round.
#   - Overhaul of spell casting
#       o Spell stuff should all be in GurpsRuleset
#       o Need maintain spell action
#   - add laser sights to weapons
#   - Add playback of actions, like from: self._saved_fight['history']
#   - need a test for each action (do_action)
#   - Need equipment containers
#
# TODO (eventually):
#   - should have some concept of time slots and activities that take up time
#     slots.  Not sure if that'll require too much input (to give up the
#     5-foot step slot in D&D if you don't use it).
#       * should warn when trying to do a second action (take note of fastdraw)
#   - Multiple weapons
#   - an item's type should be an array (so that a battle mech can be both
#     armor and weapon.
#   - Rules-specific equipment support
#       o Equipping item should ask to add ammo for item
#       o Equipping item should ask to add skills if they aren't there
#   - anything with 'RULESET' comment should be moved to the ruleset
#   - should only be able to ready an unready weapon.
#   - Allow for markdown in 'notes' and 'short-notes'
#   - On startup, check each of the characters
#       o eventually, there needs to be a list of approved skills &
#         advantages; characters' data should only match the approved list
#         (this is really to make sure that stuff wasn't mis-typed).
#   - reloading where the number of shots is in the 'clip' (like with a gun or
#     a quiver) rather than in the weapon (like in disruptors or lasers)
#   - plusses on range-based ammo (a bullet with a spell on it, for instance)
#   - Optimize the way I'm using curses.  I'm willy-nilly touching and
#     redrawing everything way more often than I should.  Turns out, it's not
#     costing me much but it's ugly, none-the-less
#   - need a way to generate equipment
#   - names, maybe, in a different file

# NOTE: debugging thoughts:
#   - traceback.print_stack()

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
              self.read_data, error_msg = GmJson.__json_load_byteified(f)
              if self.read_data is None:
                    error_array = ['Could not read JSON file "%s"' %
                                                            self.__filename]
                    if error_msg is not None:
                        error_array.append(error_msg)

                    if self.__window_manager is None:
                        print ''
                        for message in error_array:
                            print '%s' % message
                        print ''
                    else:
                        self.__window_manager.error(error_array)

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
            traceback.print_exc() # or traceback.format_exc()
        elif exception_type is not None:
            print 'EXCEPTION type: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            traceback.print_exc() # or traceback.format_exc()

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
        error_message = None
        try:
            my_dict = json.load(file_handle, object_hook=GmJson.__byteify)
        except Exception as e:
            return None, 'Couldn\'t read JSON: "%s"' % str(e)

        return GmJson.__byteify(my_dict, ignore_dicts=True), None

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
            elif command == curses.KEY_HOME:
                command_string = '<HOME>'
            elif command == curses.KEY_UP:
                command_string = '<UP>'
            elif command == curses.KEY_DOWN:
                command_string = '<DN>'
            elif command == curses.KEY_PPAGE:
                command_string = '<PGUP>'
            elif command == curses.KEY_NPAGE:
                command_string = '<PGDN>'
            elif command == curses.KEY_LEFT:
                command_string = '<LEFT>'
            elif command == curses.KEY_RIGHT:
                command_string = '<RIGHT>'
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

        lines, cols = self.getmaxyx()
        choices_per_line = int((cols - 1)/max_width) # -1 for last '|'
        # Adding 0.9999 so last partial line doesn't get truncated by 'int'
        # TODO: save lines_for_choices as self.command_ribbon_height for
        #   use bg MainGmWindow::__init__
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


    def show_description(self,
                         character # Fighter or Fight object
                        ):
        self._char_detail_window.clear()
        if character is None:
            self.refresh()
            return

        del self._char_detail[:]
        character.get_description(self._char_detail)

        # ...and show the screen

        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def status_ribbon(self,
                      filename,
                      maintain_json):

        lines, cols = self.getmaxyx()

        file_string = '%s' % filename
        wont_be_saved_string = ' (WILL NOT BE SAVED)'
        len_file_string = len(file_string)
        len_whole_string = len_file_string + (
                        0 if not maintain_json else len(wont_be_saved_string))
        start_file_string = (cols - len_whole_string) / 2

        mode = curses.A_NORMAL 
        self._window.addstr(0,
                            start_file_string,
                            '%s' % filename,
                            mode | curses.A_BOLD)

        if maintain_json:
            mode = curses.color_pair(GmWindowManager.MAGENTA_BLACK)
            self._window.addstr(0,
                                start_file_string + len_file_string,
                                wont_be_saved_string,
                                mode | curses.A_BOLD)


    def touchwin(self):
        self._window.touchwin()


    def uses_whole_screen(self):
        lines, cols = self.getmaxyx()
        if lines < curses.LINES or cols < curses.COLS:
            return False
        # No need to check top and left since there'd be an error if they were
        # non-zero given the height and width of the window.
        return True


class MainGmWindow(GmWindow):
    def __init__(self, window_manager):
        super(MainGmWindow, self).__init__(window_manager,
                                           curses.LINES,
                                           curses.COLS,
                                           0,
                                           0)

        lines, cols = self._window.getmaxyx()
        self._char_detail = [] # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        top_line = 1
        # TODO: get the actual size of the command ribbon.  The problem is
        # that the window is created before the command ribbon is added so the
        # window has no way to know how big the command ribbon will be.
        height = (lines                 # The whole window height, except...
            - top_line                  # ...a block at the top, and...
            - 5)                        # ...a space for the command ribbon.
        
        width = (cols / 2) - 1 # -1 for margin

        self.__char_list_window = GmScrollableWindow(
                                                 self.__char_list,
                                                 self._window_manager,
                                                 height,
                                                 width-1,
                                                 top_line,
                                                 1)
        self._char_detail_window  = GmScrollableWindow(
                                                 self._char_detail,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 width)


    def char_detail_home(self):
        self._char_detail_window.scroll_to(0)
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def char_list_home(self):
        self.__char_list_window.scroll_to(0)
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    def close(self):
        # Kill my subwindows, first
        if self.__char_list_window is not None:
            del self.__char_list_window
            self.__char_list_window = None
        if self._char_detail_window is not None:
            del self._char_detail_window
            self._char_detail_window = None
        super(MainGmWindow, self).close()


    def refresh(self):
        super(MainGmWindow, self).refresh()
        if self.__char_list_window is not None:
            self.__char_list_window.refresh()
        if self._char_detail_window is not None:
            self._char_detail_window.refresh()


    def scroll_char_detail_down(self):
        self._char_detail_window.scroll_down()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def scroll_char_detail_up(self):
        self._char_detail_window.scroll_up()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def scroll_char_list_down(self):
        self.__char_list_window.scroll_down()
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    def scroll_char_list_up(self):
        self.__char_list_window.scroll_up()
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    # MainGmWindow
    def show_creatures(self,
                       char_list,  # [ Fighter(), Fighter(), ..]
                       current_index,
                       standout = False
                      ):
        del self.__char_list[:]

        if char_list is None:
            self.__char_list_window.draw_window()
            self.refresh()
            return

        for line, char in enumerate(char_list):
            # TODO: perhaps the colors should be consolidated in the Figher
            #   and Fight objects
            mode = curses.A_REVERSE if standout else 0
            if char.group == 'NPCs':
                mode |= curses.color_pair(GmWindowManager.CYAN_BLACK)
            elif char.name == Fight.name:
                mode |= curses.color_pair(GmWindowManager.BLUE_BLACK)
            else:
                mode |= self._window_manager.get_mode_from_fighter_state(
                                    Fighter.get_fighter_state(char.details))

            mode |= (curses.A_NORMAL if current_index is None or
                                       current_index != line
                                    else curses.A_STANDOUT)

            self.__char_list.append([{'text': char.detailed_name,
                                      'mode': mode}])

        self.__char_list_window.draw_window()
        self.refresh()


    def touchwin(self):
        super(MainGmWindow, self).touchwin()
        if self.__char_list_window is not None:
            self.__char_list_window.touchwin()
        if self._char_detail_window is not None:
            self._char_detail_window.touchwin()



class BuildFightGmWindow(GmWindow):
    def __init__(self, window_manager):
        super(BuildFightGmWindow, self).__init__(window_manager,
                                                 curses.LINES,
                                                 curses.COLS,
                                                 0,
                                                 0)
        lines, cols = self._window.getmaxyx()
        # TODO: should _char_detail be in GmWindow?
        self._char_detail = []  # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        top_line = 1
        height = (lines                 # The whole window height, except...
            - top_line                  # ...a block at the top, and...
            - 4)                        # ...a space for the command ribbon.
        
        width = (cols / 2) - 2 # -1 for margin

        self.__char_list_window = GmScrollableWindow(
                                                 self.__char_list,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 1)
        self._char_detail_window  = GmScrollableWindow(
                                                 self._char_detail,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 width+1)


    def close(self):
        #print '  BuildFightGmWindow::close'
        # Kill my subwindows, first
        if self.__char_list_window is not None:
            del self.__char_list_window
            self.__char_list_window = None
        if self._char_detail_window is not None:
            del self._char_detail_window
            self._char_detail_window = None
        super(BuildFightGmWindow, self).close()


    def refresh(self):
        #print '  BuildFightGmWindow::refresh'
        super(BuildFightGmWindow, self).refresh()
        if self.__char_list_window is not None:
            self.__char_list_window.refresh()
        if self._char_detail_window is not None:
            self._char_detail_window.refresh()


    def scroll_char_detail_down(self):
        #print '  ** BuildFightGmWindow::scroll_char_detail_down'
        self._char_detail_window.scroll_down()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def scroll_char_detail_up(self):
        #print '  ** BuildFightGmWindow::scroll_char_detail_up'
        self._char_detail_window.scroll_up()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    # BuildFightGmWindow
    def show_creatures(self,
                       char_list,       # [ Fighter(), Fighter(), ..]
                       new_char_name,   # name of character to highlight
                       viewing_index    # index into creature list:
                                        #   dict: {'new'=True, index=0}
                      ):

        # self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
        #                         #  [...],                  ]  # line 1...

        self.__char_list_window.clear()
        del self.__char_list[:]

        highlighted_creature = None
        for index, char in enumerate(char_list):
            mode = curses.A_NORMAL
            if viewing_index is None:
                if new_char_name is not None and char.name == new_char_name:
                    mode |= curses.A_REVERSE
                    highlighted_creature = char
            else:
                if index == viewing_index:
                    mode |= curses.A_REVERSE
                    highlighted_creature = char

            self.__char_list.append([{'text': char.detailed_name,
                                      'mode': mode}])

        # ...and show the screen

        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()

        # show the detail of the selected guy

        self.show_description(highlighted_creature)

        self.refresh() # TODO: needed?


    def status_ribbon(self,
                      group,            # name of group being modified,
                      template,         # name of template 
                      input_filename,   # passthru to base class
                      maintain_json     # passthru to base class
                     ):
        '''Prints the fight round information at the top of the screen.'''

        group = '(No Group)' if group is None else group
        template = '(No Template)' if template is None else template
        self._window.move(0, 0)
        self._window.clrtoeol()

        self._window.addstr(0, 0,
                            '"%s" from "%s" template' % (group, template),
                            curses.A_NORMAL)

        super(BuildFightGmWindow, self).status_ribbon(input_filename,
                                                      maintain_json)

        self._window.refresh()


    def touchwin(self):
        super(BuildFightGmWindow, self).touchwin()
        if self.__char_list_window is not None:
            self.__char_list_window.touchwin()
        if self._char_detail_window is not None:
            self._char_detail_window.touchwin()

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
                     keep,
                     next_PC_name,
                     input_filename,
                     maintain_json
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

        if saved or keep:
            strings = []
            if saved:
                strings.append('SAVED')
            if keep:
                strings.append('KEEP')
            string = ', '.join(strings)
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

        self.status_ribbon(input_filename, maintain_json)
        self._window.refresh()


    def show_fighters(self,
                      current_fighter,  # Fighter object
                      opponent,         # Fighter object
                      fighters,
                      current_index,
                      selected_index=None   # index to view if it's not the
                                            #  current index
                     ):
        '''
        Displays the current state of the current fighter and his opponent,
        if he has one.
        '''

        self._window.move(self.__FIGHTER_LINE, self.__FIGHTER_COL)
        self._window.clrtoeol()

        if self.__show_fighter(current_fighter, self.__FIGHTER_COL):
            self.__show_fighter_notes(current_fighter,
                                      opponent,
                                      is_attacker=True,
                                      window=self.__character_window)

        if opponent is None:
            self.__opponent_window.clear()
            self.__opponent_window.refresh()
        else:
            if self.__show_fighter(opponent, self.__OPPONENT_COL):
                self.__show_fighter_notes(opponent,
                                          current_fighter,
                                          is_attacker=False,
                                          window=self.__opponent_window)
        self.__show_summary_window(fighters, current_index, selected_index)
        self.refresh()


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
        fighter_string = fighter.get_long_summary_string()
        fighter_state = fighter.get_state()
        mode = (self._window_manager.get_mode_from_fighter_state(fighter_state)
                                                            | curses.A_BOLD)
        self._window.addstr(self.__FIGHTER_LINE, column, fighter_string, mode)
        return show_more_info


    def __show_fighter_notes(self,
                             fighter,           # Fighter object
                             opponent,          # Fighter object
                             is_attacker,       # True | False
                             window             # Curses window for fighter's
                                                #   notes
                            ):
        '''
        Displays ancillary information about the fighter
        '''
        window.clear()
        line = 0

        fighter_state = fighter.get_state()
        mode = (self._window_manager.get_mode_from_fighter_state(fighter_state)
                                                            | curses.A_BOLD)
        if fighter_state == Fighter.FIGHT:
            pass
        elif fighter_state == Fighter.DEAD:
            window.addstr(line, 0, '** DEAD **', mode)
            line += 1
        elif fighter_state == Fighter.UNCONSCIOUS:
            window.addstr(line, 0, '** UNCONSCIOUS **', mode)
            line += 1
        elif fighter_state == Fighter.ABSENT:
            window.addstr(line, 0, '** ABSENT **', mode)
            line += 1
        elif fighter.details['stunned']:
            mode = curses.color_pair(GmWindowManager.RED_BLACK) | curses.A_BOLD
            window.addstr(line, 0, '** STUNNED **', mode)
            line += 1

        # Defender

        if is_attacker:
            mode = curses.A_NORMAL 
        else:
            mode = curses.color_pair(GmWindowManager.CYAN_BLACK)
            mode = mode | curses.A_BOLD

        notes, ignore = fighter.get_defenses_notes(opponent)
        if notes is not None:
            for note in notes:
                window.addstr(line, 0, note, mode)
                line += 1

        # Attacker

        if is_attacker:
            mode = curses.color_pair(GmWindowManager.CYAN_BLACK)
            mode = mode | curses.A_BOLD
        else:
            mode = curses.A_NORMAL 
        notes = fighter.get_to_hit_damage_notes(opponent)
        if notes is not None:
            for note in notes:
                window.addstr(line, 0, note, mode)
                line += 1

        # now, back to normal
        mode = curses.A_NORMAL
        notes = fighter.get_notes()
        if notes is not None:
            for note in notes:
                window.addstr(line, 0, note, mode)
                line += 1

        # Timers
        for timer in fighter.timers.get_all():
            strings = timer.get_description()
            for string in strings:
                window.addstr(line, 0, string, mode)
                line += 1

        if ('short-notes' in fighter.details and 
                                fighter.details['short-notes'] is not None):
            for note in fighter.details['short-notes']:
                window.addstr(line, 0, note, mode)
                line += 1

        window.refresh()


    def __show_summary_window(self,
                              fighters,  # array of <Fighter object>
                              current_index,
                              selected_index=None):
        self.__summary_window.clear()
        for line, fighter in enumerate(fighters):
            mode = self._window_manager.get_mode_from_fighter_state(
                                                        fighter.get_state())
            fighter_string = '%s%s' % (
                            ('> ' if line == current_index else '  '),
                            fighter.get_short_summary_string())

            if selected_index is not None and selected_index == line:
                mode = mode | curses.A_REVERSE
            elif fighter.group == 'PCs':
                mode = mode | curses.A_BOLD
            self.__summary_window.addstr(line, 0, fighter_string, mode)


class OutfitCharactersGmWindow(GmWindow):
    def __init__(self, window_manager):
        super(OutfitCharactersGmWindow, self).__init__(window_manager,
                                                 curses.LINES,
                                                 curses.COLS,
                                                 0,
                                                 0)
        lines, cols = self._window.getmaxyx()
        self.__outfit_window = self._window_manager.new_native_window(
                                                                    lines - 4,
                                                                    cols / 2,
                                                                    1,
                                                                    1)


    def close(self):
        # Kill my subwindows, first
        if self.__outfit_window is not None:
            del self.__outfit_window
            self.__outfit_window = None
        super(OutfitCharactersGmWindow, self).close()


    def refresh(self):
        super(OutfitCharactersGmWindow, self).refresh()
        if self.__outfit_window is not None:
            self.__outfit_window.refresh()


    def touchwin(self):
        super(OutfitCharactersGmWindow, self).touchwin()
        if self.__outfit_window is not None:
            self.__outfit_window.touchwin()

    #
    # Private methods
    #

    def __quit(self):
        self._window.close()
        del self._window
        self._window = None
        return False # Leave


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
        self.STATE_COLOR = {}


    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            self.STATE_COLOR = {
                Fighter.ALIVE : 
                    curses.color_pair(GmWindowManager.GREEN_BLACK),
                Fighter.INJURED : 
                    curses.color_pair(GmWindowManager.YELLOW_BLACK),
                Fighter.UNCONSCIOUS : 
                    curses.color_pair(GmWindowManager.RED_BLACK),
                Fighter.DEAD : 
                    curses.color_pair(GmWindowManager.RED_BLACK),
                Fighter.ABSENT : 
                    curses.color_pair(GmWindowManager.BLUE_BLACK),
                Fighter.FIGHT : 
                    curses.color_pair(GmWindowManager.CYAN_BLACK),
            }

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

            curses.init_pair(GmWindowManager.RED_WHITE,
                             curses.COLOR_RED,   # fg
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

    def display_window(self,
                       title,
                       lines  # [[{'text', 'mode'}, ],    # line 0
                              #  [...],               ]   # line 1
                      ):
        '''
        Presents a display of |lines| to the user.  Scrollable.
        '''

        # height and width of text box (not border)
        height = len(lines)

        # I don't think I need the following now that I'm using a scrolling
        # window:
        #
        #max_height = curses.LINES - 2 # 2 for the box
        #if height > max_height:
        #    height = max_height

        width = 0 if title is None else len(title)
        for line in lines:
            this_line_width = 0
            for piece in line:
                this_line_width += len(piece['text'])
            if this_line_width > width:
                width = this_line_width
        width += 1 # Seems to need one more space (or Curses freaks out)

        border_win, display_win = self.__centered_boxed_window(
                                                    height,
                                                    width,
                                                    title,
                                                    data_for_scrolling=lines)
        display_win.refresh()

        keep_going = True
        while keep_going:
            user_input = self.get_one_character()
            if user_input == curses.KEY_HOME:
                display_win.scroll_to(0)
            elif user_input == curses.KEY_END:
                display_win.scroll_to(len(lines)-1)
            elif user_input == curses.KEY_UP:
                display_win.scroll_up(1)
            elif user_input == curses.KEY_DOWN:
                display_win.scroll_down(1)
            elif user_input == curses.KEY_NPAGE:
                display_win.scroll_down()
            elif user_input == curses.KEY_PPAGE:
                display_win.scroll_up()
            else:
                del border_win
                del display_win
                self.hard_refresh_all()
                return

            display_win.draw_window()
            display_win.refresh()


    def edit_window(self,
                    height, width,
                    contents,  # initial string (w/ \n) for the window
                    title,
                    footer
                   ):
        '''
        Creates a window to edit a block of text using an EMACS style
        interface.
        '''
        border_win, edit_win = self.__centered_boxed_window(height,
                                                            width,
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


    def get_build_fight_gm_window(self):
        return BuildFightGmWindow(self)


    def get_fight_gm_window(self, ruleset):
        return FightGmWindow(self, ruleset)


    def get_mode_from_fighter_state(self,
                                    state # from STATE_COLOR
                                   ):
        return self.STATE_COLOR[state]


    def get_main_gm_window(self):
        return MainGmWindow(self)


    def getmaxyx(self):
        return curses.LINES, curses.COLS


    def get_one_character(self,
                          window=None # Window (for Curses)
                         ):
        '''Reads one character from the keyboard.'''

        if window is None:
            window = self.__stdscr
        c = window.getch()
        # |c| will be something like ord('p') or curses.KEY_HOME
        return c


    def get_outfit_gm_window(self):
        return OutfitCharactersGmWindow(self)


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
        # First, find the top-most window that is a whole-screen window --
        # only touch and refresh from there, above.  Look from bottom up since
        # the stack should not be too deep.  Slightly faster would be to look
        # from the top down.
        top_index = 0
        for index, window in enumerate(self.__window_stack):
            if window.uses_whole_screen():
                top_index = index

        for i in range(top_index, len(self.__window_stack)):
            self.__window_stack[i].touchwin()

        for i in range(top_index, len(self.__window_stack)):
            self.__window_stack[i].refresh()


    def input_box(self,
                  height,
                  width,
                  title
                 ):
        '''Provides a window to get input from the screen.'''

        border_win, menu_win = self.__centered_boxed_window(height,
                                                            width,
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

        The result value in strings_results can be anything and take any form.
        '''
        (MENU_STRING, MENU_RESULT) = range(0, 2)

        if len(strings_results) < 1: # if there's no choice, say so
            return None
        if len(strings_results) == 1: # if there's only 1 choice, autoselect it
            return self.__handle_menu_result(strings_results[0][MENU_RESULT])

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

        lines, cols = self.getmaxyx()
        if width > cols-4:
            width = cols-4

        data_for_scrolling = []
        index = 0 if starting_index >= len(strings_results) else starting_index
        for i, entry in enumerate(strings_results):
            mode = curses.A_STANDOUT if i == index else curses.A_NORMAL
            data_for_scrolling.append([{'text': entry[0], 'mode': mode}])
        border_win, menu_win = self.__centered_boxed_window(
                                        height,
                                        width,
                                        title,
                                        data_for_scrolling=data_for_scrolling)
        menu_win.refresh()

        while True: # The only way out is to return a result
            user_input = self.get_one_character()
            new_index = index
            if user_input == curses.KEY_HOME:
                new_index = 0
            elif user_input == curses.KEY_UP:
                new_index -= 1
            elif user_input == curses.KEY_DOWN:
                new_index += 1
            elif user_input == curses.KEY_NPAGE:
                menu_win.scroll_down()
                showable = menu_win.get_showable_menu_lines()
                if index < showable['top_line']:
                    new_index = showable['top_line']
            elif user_input == curses.KEY_PPAGE:
                menu_win.scroll_up()
                showable = menu_win.get_showable_menu_lines()
                if index > showable['bottom_line']:
                    new_index = showable['bottom_line']
            elif user_input == ord('\n'):
                del border_win
                del menu_win
                self.hard_refresh_all()
                return self.__handle_menu_result(
                                        strings_results[index][MENU_RESULT])
            elif user_input == GmWindowManager.ESCAPE:
                del border_win
                del menu_win
                self.hard_refresh_all()
                return None
            else:
                # Look for a match and return the selection
                showable = menu_win.get_showable_menu_lines()
                for index, entry in enumerate(strings_results):
                    # (string, return value)
                    # entry[MENU_STRING][0] is the 1st char of the string
                    if index > showable['bottom_line']:
                        break
                    if index >= showable['top_line']:
                        if user_input == ord(entry[MENU_STRING][0]):
                            del border_win
                            del menu_win
                            self.hard_refresh_all()
                            return self.__handle_menu_result(
                                        strings_results[index][MENU_RESULT])

            if new_index != index:
                old_index = index
                if new_index < 0:
                    index = len(data_for_scrolling) - 1
                elif new_index >= len(data_for_scrolling):
                    index = 0
                else:
                    index = new_index

                #print 'INDEX - old:%d, new:%d, final:%d' % (old_index,
                #                                            new_index,
                #                                            index)

                for piece in data_for_scrolling[old_index]:
                    piece['mode'] = curses.A_NORMAL

                for piece in data_for_scrolling[index]:
                    piece['mode'] = curses.A_STANDOUT

                # NOTE: assumes we're only changing by one line at a time so
                # we don't have to worry about scrolling more than once to get
                # to the current index.
                showable = menu_win.get_showable_menu_lines()
                if (index > showable['bottom_line'] or
                                                index < showable['top_line']):
                    menu_win.scroll_to(index)

            menu_win.draw_window()
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


    def push_gm_window(self, window):
        self.__window_stack.append(window)


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
                                width,  # width of INSIDE window
                                title,
                                mode=curses.A_NORMAL,
                                data_for_scrolling=None
                               ):
        '''
        Creates a temporary window, on top of the current one, that is
        centered and has a box around it.
        '''
        box_margin = 2

        if title is not None:
            title = ' %s ' % title  # Add some space around the title
            if width < len(title):
                width = len(title)

        # make sure we're not bigger than the screen
        if height > (curses.LINES - box_margin):
            height = curses.LINES - box_margin
        if width > (curses.COLS - box_margin):
            width = curses.COLS - box_margin

        # x and y of text box (not border)
        begin_x = (curses.COLS / 2) - (width/2)
        begin_y = (curses.LINES / 2) - (height/2)

        #print 'c h:%d, w:%d, y:%d, x:%d' % (
        #    height+2, width+2, begin_y-1, begin_x-1)

        border_win = curses.newwin(height+box_margin,
                                   width+box_margin,
                                   begin_y-1,
                                   begin_x-1)
        border_win.border()
        if title is not None:
            title_start = ((width+box_margin) - (len(title))) / 2
            border_win.addstr(0, title_start, title)

        border_win.refresh()

        if data_for_scrolling is not None:
            menu_win  = GmScrollableWindow(data_for_scrolling,
                                           self,
                                           height,
                                           width,
                                           begin_y,
                                           begin_x)
            #menu_win.bkgd(' ', mode)

        else:
            menu_win = curses.newwin(height, width, begin_y, begin_x)
            menu_win.bkgd(' ', mode)

        return border_win, menu_win


    def __handle_menu_result(self,
                             menu_result # Can literally be anything
                            ):
        '''
        If a menu_result is a dict that contains either another menu or a
        'doit' function do the menu or the doit function.
        '''

        if isinstance(menu_result, dict):
            while 'menu' in menu_result:
                menu_result = self.menu('Which', menu_result['menu'])
                if menu_result is None: # Bail out regardless of nesting level
                    return None         # Keep going

            if 'doit' in menu_result and menu_result['doit'] is not None:
                param = (None if 'param' not in menu_result 
                              else menu_result['param'])
                menu_result = (menu_result['doit'])(param)

        return menu_result


class GmScrollableWindow(object):
    def __init__(self,
                 lines,            # [[{'text', 'mode'}, ...],  # line 0
                                   #  [...]                  ]  # line 1
                 window_manager,
                 height=None,
                 width=None, # window size
                 top_line=0,
                 left_column=0 # window placement
                ):
        self.__window_manager = window_manager
        self.__lines = lines
        self.__window = self.__window_manager.new_native_window(height,
                                                                width,
                                                                top_line,
                                                                left_column)
        self.top_line = 0
        self.draw_window()
        self.refresh()

        win_line_cnt, win_col_cnt = self.__window.getmaxyx()
        self.__default_scroll_lines = win_line_cnt / 2


    def clear(self):
        self.__window.clear()


    def draw_window(self):
        '''
        Fills the window with the data that's supposed to be in it.
        '''
        self.clear()
        line_cnt = len(self.__lines) - self.top_line
        win_line_cnt, win_col_cnt = self.__window.getmaxyx()
        line_cnt = line_cnt if line_cnt < win_line_cnt else win_line_cnt
        for i in range(0, line_cnt):
            left = 0
            for piece in self.__lines[i+self.top_line]:
                self.__window.addstr(i, left, piece['text'], piece['mode'])
                left += len(piece['text'])


    def get_showable_menu_lines(self):
        win_line_cnt, win_col_cnt = self.__window.getmaxyx()
        return {'top_line': self.top_line,
                'bottom_line': self.top_line + win_line_cnt - 1}


    def refresh(self):
        self.__window.refresh()


    def scroll_down(self, line_cnt=None):
        if line_cnt is None:
            line_cnt = self.__default_scroll_lines
        win_line_cnt, win_col_cnt = self.__window.getmaxyx()

        # If we're at the end of the page and we're scrolling down, don't
        # bother.
        if len(self.__lines) - self.top_line < win_line_cnt:
            return

        self.top_line += line_cnt
        if self.top_line > len(self.__lines):
            win_line_cnt, win_col_cnt = self.__window.getmaxyx()
            self.top_line = len(self.__lines) - win_line_cnt
            if self.top_line < 0:
                self.top_line = 0

        self.draw_window()
        # NOTE: refresh the window yourself.  That way, you can modify the
        # lines before the refresh happens.


    def scroll_to(self, line):
        self.top_line = line
        if self.top_line < 0:
            self.top_line = 0
        if self.top_line > len(self.__lines):
            self.top_line = len(self.__lines)
        self.draw_window()


    def scroll_to_end(self):
        win_line_cnt, win_col_cnt = self.__window.getmaxyx()

        self.top_line = len(self.__lines) - win_line_cnt
        if self.top_line < 0:
            self.top_line = 0
        self.draw_window()


    def scroll_up(self, line_cnt=None):
        if line_cnt is None:
            line_cnt = self.__default_scroll_lines
        if self.top_line == 0:
            return
        self.top_line = (0 if self.top_line <= line_cnt else
                           self.top_line - line_cnt)
        self.draw_window()
        # NOTE: refresh the window yourself.  That way, you can modify the
        # lines before the refresh happens.


    def touchwin(self):
        self.__window.touchwin()


class World(object):
    debug_directory = 'debug'

    def __init__(self,
                 world_details,  # GmJson object
                 ruleset,        # Ruleset object
                 window_manager  # a GmWindowManager object to handle I/O
                ):
        self.__gm_json = world_details # only used for toggling whether the
                                       # data is saved on exit of the program.
        self.details = world_details.read_data # entire dict from JSON
        self.__ruleset = ruleset
        self.__window_manager = window_manager
        self.__delete_old_debug_files()
        self.campaign_debug_json = self.do_debug_snapshot('startup')


    def do_debug_snapshot(self,
                          tag,  # String with which to tag the debug filename
                         ):
        '''
        Saves a copy of the master JSON file to a debug directory.
        '''

        # Save the current JSON for debugging, later
        debug_filename = os.path.join(World.debug_directory,
                                      timeStamped('debug_json', tag, 'txt'))
        with open(debug_filename, 'w') as f:
            json.dump(self.details, f, indent=2)

        return debug_filename


    def dont_save_on_exit(self):
        self.__gm_json.write_data = None
        ScreenHandler.maintainjson = True


    def do_save_on_exit(self):
        self.__gm_json.write_data = self.__gm_json.read_data
        ScreenHandler.maintainjson = False


    def get_creatures(self,
                      group_name  # 'PCs', 'NPCs', or a monster group
                     ):
        '''
        Used to get PCs, NPCs, or a fight's list of creatures.

        Returns dict of details: {name: {<details>}, name: ... }
        '''

        if group_name in self.details:
            return self.details[group_name]

        fights = self.get_fights()
        if group_name in fights:
            fight = Fight(group_name,
                          self.details['fights'][group_name],
                          self.__ruleset,
                          self.__window_manager
                          )
            return fight.get_creatures()

        return None


    def get_creature_details(self, name, group_name):
        if name is None or group_name is None:
            self.__window_manager.error(
                ['Name: %r or group: %r is "None"' % (name, group_name)])
            return None

        if group_name == 'PCs':
            details = self.details['PCs'][name]
        elif group_name == 'NPCs':
            details = self.details['NPCs'][name]
        else:
            group = self.get_creatures(group_name)
            if group is None:
                self.__window_manager.error(
                                    ['No "%s" group in "fights"' % group_name])
                return None

            if name not in group:
                self.__window_manager.error(
                    ['No name "%s" in monster group "%s"' % (name, group_name)])
                return None

            details = group[name]

        if 'redirect' in details:
            # NOTE: this only allows redirects to PCs and NPCs since monsters
            # are buried deeper in the details.  That's by design since
            # monsters are transitory.
            if details['redirect'] not in self.details:
                self.__window_manager.error(
                    ['No "%s" group in world (redirect)' %
                     details['redirect']])
                return None
            if name not in self.details[details['redirect']]:
                self.__window_manager.error(
                    ['No name "%s" in "%s" group (redirect)' %
                     (name, details['redirect'])])
                return None
            details = self.details[details['redirect']][name]

        return details


    def get_fights(self):
        '''
        Returns {fight_name: {details}, fight_name: {details}, ...}
        '''
        return self.details['fights']


    def get_random_name(self):
        randomly_generate = False

        if self.details['Names'] is None:
            self.__window_manager.error(
                                    ['There are no "Names" in the database'])
            return None, None, None

        # Country

        country_menu = [(x, x) for x in self.details['Names']]
        country_name = self.__window_manager.menu('What kind of name',
                                               country_menu)
        if country_name is None:
            randomly_generate = True
            country_name = random.choice(self.details['Names'].keys())

        # Gender

        gender_list = ['male', 'female']
        if not randomly_generate:
            gender_menu = [(x, x) for x in gender_list]
            gender = self.__window_manager.menu('What Gender', gender_menu)
            if gender is None:
                randomly_generate = True

        if randomly_generate:
            gender = random.choice(gender_list)

        # Name

        first_name = random.choice(self.details['Names'][country_name][gender])
        last_name = random.choice(self.details['Names'][country_name]['last'])
        name = '%s %s' % (first_name, last_name)

        return (name, country_name, gender)


    def is_saved_on_exit(self):
        return False if self.__gm_json.write_data is None else True


    def toggle_saved_on_exit(self):
        if self.is_saved_on_exit():
            self.dont_save_on_exit()
        else:
            self.do_save_on_exit()

    #
    # Private and Protected
    #

    def __delete_old_debug_files(self):
        '''
        Delete debug files that are older than a couple of days old but remove
        no more than the last 10 files.  This is all pretty arbitrary but it
        seems like a reasonable amount to keep on hand.
        '''

        minimum_files_to_keep = 10  # Arbitrary

        if not os.path.exists(World.debug_directory):
            os.makedirs(World.debug_directory)

        # Get rid of old debugging JSON files.
         
        entries = (os.path.join(World.debug_directory, fn)
                                    for fn in os.listdir(World.debug_directory))
        entries = (
                (datetime.datetime.fromtimestamp(os.path.getctime(fpath)),
                 fpath) for fpath in entries)
        entries = sorted(entries, key=lambda x: x[0], reverse=True)

        # Keep files that are less than 2 days (an arbitrary number) old.
        two_days_ago = datetime.datetime.now() - datetime.timedelta(days=2)

        if len(entries) > minimum_files_to_keep:
            for mod_date, path in entries[minimum_files_to_keep:]:
                if mod_date < two_days_ago: # '<' means 'earlier than'
                    os.remove(path)

class Equipment(object):
    def __init__(self,
                 equipment, # self.details['stuff'], list of items
                ):
        self.__equipment = equipment


    def add(self,
            new_item,   # dict describing new equipment
            source=None # string describing where equipment came from
           ):
        if source is not None and new_item['owners'] is not None:
            new_item['owners'].append(source)

        for item in self.__equipment:
            if item['name'] == new_item['name']:
                if self.__is_same_thing(item, new_item):
                    item['count'] += new_item['count']
                    return
                break

        self.__equipment.append(new_item)

        return len(self.__equipment) - 1 # current index of the added item


    def get_item_by_index(self,
                          index
                         ):
        return (None if index >= len(self.__equipment) else
                                                self.__equipment[index])


    def get_item_by_name(self,              # Public to facilitate testing
                         name
                        ):
        '''
        Remove weapon from sheath or holster.

        Returns index, item
        '''
        for index, item in enumerate(self.__equipment):
            if item['name'] == name:
                return index, item
        return None, None # didn't find one


    def remove(self,
               item_index
              ):
        # NOTE: This assumes that there won't be any placeholder items --
        # items with a count of 0 (or less).
        if item_index >= len(self.__equipment):
            return None

        if ('count' in self.__equipment[item_index] and
                                self.__equipment[item_index]['count'] > 1):
            item = copy.deepcopy(self.__equipment[item_index])
            item['count'] = 1
            self.__equipment[item_index]['count'] -= 1
        else:
            item = self.__equipment[item_index]
            self.__equipment.pop(item_index)

        return item

    #
    # Private methods
    #

    def __is_same_thing(self,
                        lhs,    # part of equipment dict (at level=0, is dict)
                        rhs,    # part of equipment dict (at level=0, is dict)
                        level=0 # how far deep in the recursive calls are we
                       ):
        level += 1

        if isinstance(lhs, dict):
            if not isinstance(rhs, dict):
                return False
            for key in rhs.iterkeys():
                if key not in rhs:
                    return False
            for key in lhs.iterkeys():
                if key not in rhs:
                    return False
                elif key == 'count' and level == 1:
                    return True # the count doesn't go into the match of item
                elif not self.__is_same_thing(lhs[key], rhs[key], level):
                    return False
            return True
                
        elif isinstance(lhs, list):
            if not isinstance(rhs, list):
                return False
            if len(lhs) != len(rhs):
                return False
            for i in range(len(lhs)):
                if not self.__is_same_thing(lhs[i], rhs[i], level):
                    return False
            return True

        else:
            return False if lhs != rhs else True


class Timer(object):
    round_count_string = '%d Rnds: ' # assume rounds takes same space as '%d' 
    len_timer_leader = len(round_count_string)
    announcement_margin = 0.1 # time removed from an announcement timer so that
                              #   it'll go off at the beginning of a round
                              #   rather than the end

    def __init__(self,
                 details    # dict from the JSON, contains timer's info
           ):
        self.details = details  # This need to actually be from the JSON


    def decrement(self):
        self.details['rounds'] -= 1


    def fire(self,
             owner,         # ThingsInFight object to receive timer action
             window_manager # GmWindowManager object -- for display
            ):
        ''' Fires the timer. '''

        result = None   # If there's a timer to be added back into the list,
                        #   this will be used to return it

        if 'state' in self.details['actions']:
            owner.details['state'] = self.details['actions']['state']

        if 'announcement' in self.details['actions']:
            window_manager.display_window(
                           ('Timer Fired for %s' % self.details['parent-name']),
                            [[{'text': self.details['actions']['announcement'],
                               'mode': curses.A_NORMAL }]])

        if 'timer' in self.details['actions']:
            result = self.details['actions']['timer']

        return result


    def from_pieces(self,
                    parent_name,           # string describing the thing
                                           #   calling the timer
                    rounds,                # rounds until timer fires
                                           #   (3.0 rounds fires at end
                                           #   of 3 rounds; 2.9 rounds
                                           #   fires at beginning of 3
                                           #   rounds).
                    text,                  # string to display (in
                                           #   fighter's notes) while
                                           #   timer is running
                    announcement = None,   # string to display (in its
                                           #   own window) when timer
                                           #   fires
                    state = None           # string describing new state of
                                           #   fighter (see
                                           #   Fighter.conscious_map)
           ):
        '''
        Creates a new timer from scratch (rather than from data that's already
        in the JSON).
        '''

        name = '<< Unknown Parent >>' if parent_name is None else parent_name
        self.details = {'parent-name': name,
                        'rounds': rounds,
                        'string': text,
                        'actions': {}}

        if state is not None:
            self.details['actions']['state'] = state

        if announcement is not None:
            self.details['actions']['announcement'] = announcement


    def get_description(self):
        result = [] # List of strings, one per line of output
        this_line = []

        rounds = self.details['rounds']

        if ('announcement' in self.details['actions'] and
                        self.details['actions']['announcement'] is not None):
            # Add back in the little bit we shave off of an announcement so
            # that the timer will announce as the creature's round starts
            # rather than at the end.
            rounds += Timer.announcement_margin

        round_count_string = Timer.round_count_string % rounds
        this_line.append(round_count_string)
        if 'announcement' in self.details['actions']:
            this_line.append('[%s]' % self.details['actions']['announcement'])
            result.append(''.join(this_line))
            this_line = []

        if ('string' in self.details and self.details['string'] is not None
                                        and len(self.details['string']) > 0):
            if type(self.details['string']) is list:
                for substring in self.details['string']:
                    this_line.append('%s' % (substring))
                    result.append(''.join(this_line))
                    this_line = []
            else:
                this_line.append('%s' % (self.details['string']))
                result.append(''.join(this_line))
                this_line = []

        if len(this_line) > 0:
            this_line.append('<<UNNAMED TIMER>>')
            result.append(''.join(this_line))

        return result


    def get_one_line_description(self):
        '''
        '''
        this_line = []

        rounds = self.details['rounds']

        if ('announcement' in self.details['actions'] and
                        self.details['actions']['announcement'] is not None):
            # Add back in the little bit we shave off of an announcement so
            # that the timer will announce as the creature's round starts
            # rather than at the end.
            rounds += Timer.announcement_margin

        round_count_string = Timer.round_count_string % rounds
        this_line.append(round_count_string)

        needs_headline = True
        if 'announcement' in self.details['actions']:
            this_line.append('[%s]' %
                                    self.details['actions']['announcement'][0])
            needs_headline = False

        if ('string' in self.details and self.details['string'] is not None
                                        and len(self.details['string']) > 0):
            if type(self.details['string']) is list:
                this_line.append('%s' % (self.details['string'][0]))
            else:
                this_line.append('%s' % (self.details['string']))
            needs_headline = False

        if needs_headline:
            this_line.append('<<UNNAMED TIMER>>')

        return ' '.join(this_line)


    def mark_owner_as_busy(self,
                           is_busy = True):
        self.details['busy'] = is_busy


class TimersWidget(object):
    '''
    Consolodated GUI widget for creating timers.
    '''

    def __init__(self,
                 timers,        # Timers object
                 window_manager # GmWindowManager object
                ):
        self.__timers = timers
        self.__window_manager = window_manager


    def make_timer(self,
                   timer_recipient_name # string
                   ):

        # How long is the timer?

        title = 'Rounds To Wait...'
        height = 1
        width = len(title)
        adj_string = self.__window_manager.input_box(height, width, title)
        if adj_string is None or len(adj_string) <= 0:
            return
        rounds = int(adj_string)
        if rounds <= 0:
            return

        # What does the timer do?

        keep_asking = True
        keep_asking_menu = [('yes', True), ('no', False)]
        param = {'announcement': None,
                 'continuous_message': None,
                 'state': None}
        actions_menu = [('Continuous Message', 
                                {'doit': self.__continuous_message_action,
                                 'param': param}),
                        ('Announcement',       
                                {'doit': self.__announcement_action,
                                 'param': param}),
                        ('New State',          
                                {'doit': self.__new_state_action,
                                 'param': param})]
        while keep_asking:
            self.__window_manager.menu('Timer Action', actions_menu)
            keep_asking = self.__window_manager.menu('Pick More Actions',
                                                     keep_asking_menu)

        # Install the timer.

        if 'announcement' in param and param['announcement'] is not None:
            # Shave a little off the time so that the timer will announce
            # as his round starts rather than at the end.
            rounds -= Timer.announcement_margin

        timer_obj = Timer(None)
        timer_obj.from_pieces(timer_recipient_name,
                              rounds,
                              param['continuous_message'],
                              param['announcement'],
                              param['state'])
        self.__timers.add(timer_obj)


    # Private and Protected Methods

    def __continuous_message_action(self,
                                    param
                                   ):
        title = 'Enter the Continuous Message'
        height = 1
        width = (curses.COLS - 4) - Timer.len_timer_leader
        string = self.__window_manager.input_box(height, width, title)
        if string is not None and len(string) <= 0:
            string = None
        param['continuous_message'] = string


    def __announcement_action(self,
                              param
                             ):
        title = 'Enter the Announcement'
        height = 1
        width = (curses.COLS - 4) - Timer.len_timer_leader
        announcement = self.__window_manager.input_box(height, width, title)
        if announcement is not None and len(announcement) <= 0:
            announcement = None
        param['announcement'] = announcement


    def __new_state_action(self,
                           param
                          ):
        state_menu = [(x, x) for x in Fighter.conscious_map.keys() 
                                                            if x != 'fight']
        state_menu = sorted(state_menu, key=lambda x: x[0].upper())
        state = self.__window_manager.menu('Which State', state_menu)
        if state is not None:
            param['state'] = state


class Timers(object):
    def __init__(self,
                 timer_details, # List from JSON containing timers
                 owner,         # ThingsInFight object to receive timer
                                #   actions.
                 window_manager # For displaying error messages
                ):

        # data and obj are parallel arrays.  'data' is just like it is in the
        # JSON (and, in fact, should point to the JSON data) and 'obj' is the
        # Timer object from that data.
        self.__timers = {'data': timer_details,
                         'obj': []}

        self.__owner = owner

        for timer_data in timer_details:
            timer_obj = Timer(timer_data)
            self.__timers['obj'].append(timer_obj)

        self.__window_manager = window_manager


    def add(self,
            timer   # Timer object
           ):
        self.__timers['data'].append(timer.details)
        self.__timers['obj'].append(timer)
        return timer


    def clear_all(self):
        while len(self.__timers['data']) > 0:
            self.__timers['data'].pop()
        self.__timers['obj'] = []


    def decrement_all(self):
        ''' Decrements all timers. '''
        for timer_obj in self.__timers['obj']:
            timer_obj.decrement()


    def get_all(self):
        return self.__timers['obj']


    def remove_expired_keep_dying(self):
        '''
        Removes timers BUT KEEPS the timers that are dying this round.  Call
        this at the beginning of the round.  Standard timers that die this
        round are kept so that they're shown.
        '''

        remove_these = []
        for index, timer in enumerate(self.__timers['obj']):
            if timer.details['rounds'] < 0:     # < keeps the timers dying
                                                #   this round
                remove_these.insert(0, index)   # largest indexes last
        for index in remove_these:
            self.__fire_timer(self.__timers['obj'][index])
            self.remove_timer_by_index(index)


    def remove_expired_kill_dying(self):
        '''
        Removes timers AND KILLS the timers that are dying this round.  Call
        this at the end of the round to scrape off the timers that expire this
        round.
        '''

        remove_these = []
        for index, timer in enumerate(self.__timers['obj']):
            if timer.details['rounds'] <= 0:    # <= kills the timers dying
                                                #   this round
                remove_these.insert(0, index)   # largest indexes last
        for index in remove_these:
            self.__fire_timer(self.__timers['obj'][index])
            self.remove_timer_by_index(index)


    def remove_timer_by_index(self,
                              index
                             ):
        del self.__timers['data'][index]
        del self.__timers['obj'][index]

    #
    # Private methods
    #

    def __fire_timer(self,
                     timer  # Timer object
                    ):
        new_timer = timer.fire(self.__owner, self.__window_manager)
        if new_timer is not None:
            self.add(Timer(new_timer))


class ThingsInFight(object):
    def __init__(self,
                 name,          # string, name of the thing
                 group,         # string to index into world['fights']
                 details,       # world.details['fights'][name] (world is
                                #   a World object)
                 ruleset,       # Ruleset object
                 window_manager # GmWindowManager object for reporting errors
                ):
        self.name = name
        self.detailed_name = self.name
        self.group = group
        self.details = details
        self._ruleset = ruleset
        self._window_manager = window_manager

        # Equipment

        if 'stuff' not in self.details:     # Public to facilitate testing
            self.details['stuff'] = []

        self.equipment = Equipment(self.details['stuff'])

        # Timers

        if 'timers' not in details:
            details['timers'] = []
        self.timers = Timers(self.details['timers'],
                             self,
                             self._window_manager)


    #
    # Equipment related methods
    #

    def add_equipment(self,
                      new_item,   # dict describing new equipment
                      source=None # string describing where equipment came from
                      ):
        return self.equipment.add(new_item, source)


    def remove_equipment(self,
                         item_index
                        ):
        return self.equipment.remove(item_index)

    #
    # Notes methods
    #

    def get_defenses_notes(self,
                           opponent # Throw away Fighter object
                          ):
        return None, None


    def get_long_summary_string(self):
        return '%s' % self.name


    def get_notes(self):
        return None 


    def get_short_summary_string(self):
        return '%s' % self.name


    def get_to_hit_damage_notes(self,
                                opponent # Throw away Fighter object
                               ):
        return None

    #
    # Miscellaneous methods
    #

    def end_fight(self,
                  world,          # World object
                  fight_handler   # FightHandler object
                 ):
        self.timers.clear_all()

    def start_fight(self):
        pass

    #
    # Protected
    #

    def _explain_numbers(self,
                         fight_handler  # FightHandler object, ignored
                        ):
        '''
        Explains how the stuff in the descriptions were calculated.

        Returns [[{'text':x, 'mode':x}, {...}], [], [], ...]
            where the outer array contains lines
            each line is an array that contains a line-segment
            each line segment has its own mode so, for example, only SOME of
               the line is shown in bold
        '''
        return [[{'text': '(Nothing to explain)', 'mode': curses.A_NORMAL}]]



class Fight(ThingsInFight):
    name = '<< ROOM >>'                 # Describes the FIGHT object
    detailed_name = '<< ROOM: %s >>'    # insert the group into the '%s' slot
    empty_fight = {
        'stuff': [],
        'notes': [],
        'timers': []
    }
    def __init__(self,
                 group,         # string to index into world['fights']
                 details,       # world.details['fights'][name] (world is
                                #   a World object)
                 ruleset,       # Ruleset object
                 window_manager # GmWindowManager object for error reporting
                ):
        super(Fight, self).__init__(Fight.name,
                                    group,
                                    details,
                                    ruleset,
                                    window_manager)
        self.detailed_name = Fight.detailed_name % group


    def get_creatures(self):
        '''
        Returns dict of details: {name: {<details>}, name: ... }
        '''
        return self.details['monsters']


    def get_description(self,
                        char_detail, # recepticle for character detail.
                                     # [[{'text','mode'},...],  # line 0
                                     #  [...],               ]  # line 1...
                        ):
        self._ruleset.get_fight_description(self, char_detail)


    def get_state(self):
        return Fighter.FIGHT




class Fighter(ThingsInFight):
    (ALIVE,
     UNCONSCIOUS,
     DEAD,

     INJURED, # Injured is separate since it's tracked by HP
     ABSENT,
     FIGHT) = range(6)

    conscious_map = {
        'alive': ALIVE,
        'unconscious': UNCONSCIOUS,
        'dead': DEAD,
        'absent': ABSENT,
        'fight': FIGHT,
    }

    def __init__(self,
                 name,              # string
                 group,             # string = 'PCs' or some monster group
                 fighter_details,   # dict as in the JSON
                 ruleset,           # a Ruleset object
                 window_manager     # a GmWindowManager object
                ):
        super(Fighter, self).__init__(name,
                                      group,
                                      fighter_details,
                                      ruleset,
                                      window_manager)
        pass


    @staticmethod
    def get_fighter_state(details):
        conscious_number = Fighter.conscious_map[details['state']]
        if (conscious_number == Fighter.ALIVE and 
                        details['current']['hp'] < details['permanent']['hp']):
            return Fighter.INJURED
        return conscious_number

    @staticmethod
    def get_name_from_state_number(number):
        for name, value in Fighter.conscious_map.iteritems():
            if value == number:
                return name
        return '<unknown>'


    #
    # Equipment related methods
    #

    def add_equipment(self,
                      new_item,   # dict describing new equipment
                      source=None # string describing where equipment came from
                      ):
        index = self.equipment.add(new_item, source)
        self.details['weapon-index'] = None
        self.details['armor-index'] = None
        return index


    def don_armor_by_index(self,
                           index  # Index of armor in fighter's 'stuff'
                                  # list.  'None' removes current armor.
                          ):
        '''Puts on armor.'''
        self.details['armor-index'] = index


    def draw_weapon_by_index(self,
                             index  # Index of weapon in fighter's 'stuff'
                                    # list.  'None' removes current weapon.
                            ):
        '''Draws or removes weapon from sheath or holster.'''
        # NOTE: call this from the ruleset if you want the ruleset to do its
        # due dilligence (i.e., stop the aim).
        self.details['weapon-index'] = index


    def end_fight(self,
                  world,          # World object (for options)
                  fight_handler   # FightHandler object (for do_action)
                 ):
        super(Fighter, self).end_fight(world, fight_handler)
        # TODO: only if group is PC
        if ('reload-after-fight' in world.details['Options'] and 
                            world.details['Options']['reload-after-fight']):
            self._ruleset.do_action(self, {'name': 'reload'}, fight_handler)
        self.details['weapon-index'] = None


    def get_current_armor(self):
        if 'armor-index' not in self.details:
            return None, None
        armor_index = self.details['armor-index']
        if armor_index is None:
            return None, None
        armor = self.equipment.get_item_by_index(armor_index)
        return armor, armor_index


    def get_current_weapon(self):
        weapon_index = self.details['weapon-index']
        if weapon_index is None:
            return None, None
        weapon = self.equipment.get_item_by_index(weapon_index)
        return weapon, weapon_index


    def get_weapon_by_name(self,                # Public to support testing
                           name
                          ):
        '''
        Remove weapon from sheath or holster.

        Returns index, item
        '''
        index, item = self.equipment.get_item_by_name(name)
        if index is not None:
            self.details['weapon-index'] = index
        return index, item


    def remove_equipment(self,
                         item_index
                        ):
        item = self.equipment.remove(item_index)
        self.details['weapon-index'] = None
        self.details['armor-index'] = None
        return item


    #
    # Notes related methods
    #

    def get_defenses_notes(self,
                           opponent # Fighter object
                          ):
        defense_notes, defense_why = self._ruleset.get_fighter_defenses_notes(
                                                                self,
                                                                opponent)
        return defense_notes, defense_why


    def get_description(self,
                        output, # recepticle for character detail.
                                # [[{'text','mode'},...],  # line 0
                                #  [...],               ]  # line 1...
                        ):
        self._ruleset.get_character_description(self, output)


    def get_long_summary_string(self):
        fighter_string = '%s HP: %d/%d FP: %d/%d' % (
                                    self.name,
                                    self.details['current']['hp'],
                                    self.details['permanent']['hp'],
                                    self.details['current']['fp'],
                                    self.details['permanent']['fp'])
        return fighter_string


    def get_notes(self):
        notes = self._ruleset.get_fighter_notes(self)
        return notes


    def get_to_hit_damage_notes(self,
                                opponent # Fighter object
                               ):
        notes = self._ruleset.get_fighter_to_hit_damage_notes(self, opponent)
        return notes


    def get_short_summary_string(self):
        fighter_string = '%s HP:%d/%d' % (self.name,
                                          self.details['current']['hp'],
                                          self.details['permanent']['hp'])
        return fighter_string


    #
    # Miscellaneous methods
    #

    def can_finish_turn(self):
        return self._ruleset.can_finish_turn(self)


    def end_turn(self):
        self._ruleset.end_turn(self)
        self.timers.remove_expired_kill_dying()


    def get_state(self):
        return Fighter.get_fighter_state(self.details)


    def is_conscious(self):
        # NOTE: 'injured' is not stored in self.details['state']
        return True if self.details['state'] == 'alive' else False


    def is_dead(self):
        return True if self.details['state'] == 'dead' else False


    def is_absent(self):
        return True if self.details['state'] == 'absent' else False


    def set_consciousness(self, conscious_number):
        '''
        Sets the state of the fighter.
        '''

        for state_name, state_num in Fighter.conscious_map.iteritems():
            if state_num == conscious_number:
                self.details['state'] = state_name
                break

        if not self.is_conscious():
            self.details['opponent'] = None # dead men fight nobody


    def start_fight(self):
        # NOTE: we're allowing health to still be messed-up, here
        # NOTE: person may go around wearing armor -- no need to reset
        self.details['opponent'] = None
        self._ruleset.start_fight(self)


    def start_turn(self):
        self._ruleset.start_turn(self)
        self.timers.decrement_all()
        self.timers.remove_expired_keep_dying()
        for timer in self.timers.get_all():
            if 'busy' in timer.details and timer.details['busy']:
                window_text = []
                lines = timer.get_description()
                for line in lines:
                    window_text.append([{'text': line,
                                         'mode': curses.A_NORMAL}])
                self._window_manager.display_window(
                                                ('%s is busy' % self.name),
                                                window_text)

                # Allow the fighter to continue without doing anything since
                # s/he's already busy
                self.details['actions_this_turn'].append('busy')


    def toggle_absent(self):

        if self.details['state'] == 'absent':
            self.details['state'] = 'alive'
        else:
            self.details['state'] = 'absent'


    #
    # Protected and Private Methods
    #

    def _explain_numbers(self,
                         fight_handler  # FightHandler object
                        ):
        '''
        Returns [[{'text':x, 'mode':x}, {...}], [], [], ...]
            where the outer array contains lines
            each line is an array that contains a line-segment
            each line segment has its own mode so, for example, only SOME of
               the line is shown in bold
        '''

        why_opponent = fight_handler.get_opponent_for(self)
        weapon, holding_weapon_index = self.get_current_weapon()

        lines = []

        unarmed_skills = self._ruleset.get_weapons_unarmed_skills(weapon)

        if unarmed_skills is not None:
            unarmed_info = self._ruleset.get_unarmed_info(self,
                                                          why_opponent,
                                                          weapon,
                                                          unarmed_skills)
            lines = [[{'text': x,
                       'mode': curses.A_NORMAL}] for x in unarmed_info['why']]
        else:
            if weapon['skill'] in self.details['skills']:
                ignore, to_hit_why = self._ruleset.get_to_hit(self,
                                                              why_opponent,
                                                              weapon)
                lines = [[{'text': x,
                           'mode': curses.A_NORMAL}] for x in to_hit_why]

                # Damage

                ignore, damage_why = self._ruleset.get_damage(self, weapon)
                lines.extend([[{'text': x,
                                'mode': curses.A_NORMAL}] for x in damage_why])

            if 'notes' in weapon and len(weapon['notes']) != 0:
                lines.extend([[{'text': 'Weapon: "%s"' % weapon['name'],
                               'mode': curses.A_NORMAL}]])
                lines.extend([[{'text': '  %s' % weapon['notes'],
                               'mode': curses.A_NORMAL}]])

        ignore, defense_why = self.get_defenses_notes(why_opponent)
        if defense_why is not None:
            lines = [[{'text': x,
                       'mode': curses.A_NORMAL}] for x in defense_why] + lines

        return lines


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
        'busy': true | false
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

    #
    # Public Methods
    #


    def can_finish_turn(self,
                        fighter # Fighter object
                       ):
        return True


    def do_action(self,
                  fighter,      # Fighter object
                  action,       # {'name': <action>, parameters...}
                  fight_handler # FightHandler object
                 ):
        '''
        ONLY to be used for fights (otherwise, there's no fight handler to log
        the actions).

        Default, non-ruleset related, action handling.  Good for drawing
        weapons and such.
        '''

        # Actions

        handled = False

        if 'name' not in action:
            handled = True # It's just a comment, ignore (but mark it 'handled')

        elif action['name'] == 'adjust-hp':
            self._adjust_hp(fighter, action['adj'])
            handled = True

        elif action['name'] == 'attack' or action['name'] == 'all-out-attack':
            self._do_attack({'fighter': fighter,
                             'fight_handler': fight_handler})
            handled = True

        elif action['name'] == 'set-consciousness':
            fighter.set_consciousness(action['level'])
            handled = True

        elif action['name'] == 'user-defined':
            self._do_custom_action(action)
            handled = True

        elif action['name'] == 'draw-weapon':
            self._draw_weapon({'fighter': fighter,
                               'weapon':  action['weapon-index']})
            handled = True

        elif action['name'] == 'don-armor': # or doff armor
            self._don_armor({'fighter': fighter,
                             'armor': action['armor-index']})
            handled = True

        elif action['name'] == 'pick-opponent':
            fighter.details['opponent'] = {'group': action['opponent-group'],
                                           'name': action['opponent-name']}
            handled = True

        elif action['name'] == 'reload': # or doff armor
            self._do_reload({'fighter': fighter})
            handled = True

        elif action['name'] == 'use-item':
            self._use_item({'fighter': fighter,
                            'item': action['item-index']})
            handled = True

        if fight_handler is not None:
            fight_handler.add_to_history(action)

        return handled


    def get_action_menu(self,
                        action_menu,    # menu for user [(name, predicate)...]
                        fighter,        # Fighter object
                        opponent        # Fighter object
                       ):
        '''
        Builds the menu of maneuvers allowed for the fighter. This is for the
        non-ruleset-based stuff like drawing weapons and such.
        '''

        # Figure out who we are and what we're holding.

        weapon, weapon_index = fighter.get_current_weapon()
        holding_ranged = (False if weapon is None else
                                (weapon['type'] == 'ranged weapon'))

        ### Armor ###

        # Armor SUB-menu

        armor, armor_index = fighter.get_current_armor()
        don_armor_menu = []   # list of armor that may be donned this turn
        for index, item in enumerate(fighter.details['stuff']):
            if item['type'] == 'armor':
                if armor is None or armor_index != index:
                    don_armor_menu.append((item['name'],
                                        {'text': [('Don %s' % item['name']),
                                                  ' Defense: none',
                                                  ' Move: none'],
                                         'action': { 'name': 'don-armor',
                                                     'armor-index': index}
                                        }))
        don_armor_menu = sorted(don_armor_menu, key=lambda x: x[0].upper())

        # Armor menu

        if len(don_armor_menu) == 1:
            action_menu.append(
                (('Don %s' % don_armor_menu[0][0]),
                 {'text': ['Don Armor',
                           ' Defense: none',
                           ' Move: none'],
                  'action': {
                    'name': 'don-armor',
                    'armor-index': don_armor_menu[0][1]['action']['armor-index']
                  }
                 }))

        elif len(don_armor_menu) > 1:
            action_menu.append(('Don Armor',
                                {'text': ['Don Armor',
                                          ' Defense: none',
                                          ' Move: none'],
                                 'menu': don_armor_menu}))

        if armor is not None:
            action_menu.append((('Doff %s' % armor['name']), 
                                   {'text': [('Doff %s' % armor['name']),
                                             ' Defense: none',
                                             ' Move: none'],
                                    'action': {'name': 'don-armor',
                                               'armor-index': None}
                                   }))

        ### Attack ###


        # RULESET: All of the 'text', below, is GurpsRuleset-based
        move = fighter.details['current']['basic-move']

        if holding_ranged:
            if weapon['ammo']['shots_left'] > 0:
                # Can only attack if there's someone to attack
                action_menu.extend([
                    ('attack',          {'text': ['Attack',
                                                  ' Defense: any',
                                                  ' Move: step'],
                                         'action': {'name': 'attack'}
                                        }),
                    ('attack, all out', {'text': ['All out attack',
                                                  ' Defense: none',
                                                  ' Move: 1/2 = %d' %
                                                                (move/2)],
                                         'action': {'name': 'all-out-attack'}
                                        })
                ])
        else:
            action_menu.extend([
                    ('attack',          {'text': ['Attack',
                                                    ' Defense: any',
                                                    ' Move: step'],
                                         'action': {'name': 'attack'}
                                        }),
                    ('attack, all out', {'text': ['All out attack',
                                                 ' Defense: none',
                                                 ' Move: 1/2 = %d' % (move/2)],
                                         'action': {'name': 'all-out-attack'}
                                        })
            ])

        ### Draw or Holster weapon ###

        if weapon is not None:
            action_menu.append((('holster/sheathe %s' % weapon['name']), 
                                   {'text': [('Unready %s' % weapon['name']),
                                             ' Defense: any',
                                             ' Move: step'],
                                    'action': {'name': 'draw-weapon',
                                               'weapon-index': None}
                                   }))
        else:
            # Draw weapon SUB-menu

            draw_weapon_menu = []   # weapons that may be drawn this turn
            for index, item in enumerate(fighter.details['stuff']):
                if (item['type'] == 'ranged weapon' or
                        item['type'] == 'melee weapon' or
                        item['type'] == 'shield'):
                    if weapon is None or weapon_index != index:
                        draw_weapon_menu.append(
                            (item['name'], {'text': [('draw %s' % item['name']),
                                                      ' Defense: any',
                                                      ' Move: step'],
                                            'action': {'name': 'draw-weapon',
                                                       'weapon-index': index}
                                           }))
            draw_weapon_menu = sorted(draw_weapon_menu,
                                      key=lambda x: x[0].upper())

            # Draw menu

            if len(draw_weapon_menu) == 1:
                action_menu.append(
                    (('draw (ready, etc.; B325, B366, B382) %s' %
                                                    draw_weapon_menu[0][0]),
                     {'text': ['Ready (draw, etc.)',
                               ' Defense: any',
                               ' Move: step'],
                      'action': {'name': 'draw-weapon',
                                 'weapon-index': 
                            draw_weapon_menu[0][1]['action']['weapon-index']}
                     }))

            elif len(draw_weapon_menu) > 1:
                action_menu.append(('draw (ready, etc.; B325, B366, B382)',
                                    {'text': ['Ready (draw, etc.)',
                                              ' Defense: any',
                                              ' Move: step'],
                                     'menu': draw_weapon_menu}))

        ### RELOAD ###

        if holding_ranged:
            action_menu.append(('reload (ready)',
                                               {'text': ['Ready (reload)',
                                                         ' Defense: any',
                                                         ' Move: step'],
                                                'action': {'name': 'reload'}
                                               }))

        ### Use Item ###

        # Use SUB-menu

        use_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if item['count'] > 0:
                use_menu.append((item['name'],
                                    {'text': [('Use %s' % item['name']),
                                              ' Defense: (depends)',
                                              ' Move: (depends)'],
                                     'action': {'name': 'use-item',
                                                'item-index': index}
                                    }))
        use_menu = sorted(use_menu, key=lambda x: x[0].upper())

        # Use menu

        if len(use_menu) == 1:
            action_menu.append(
                (('use %s' % use_menu[0][0]),
                 {'text': ['Use Item',
                           ' Defense: (depends)',
                           ' Move: (depends)'],
                  'action': {'name':       'use-item',
                             'item-index':
                                use_menu[0][1]['action']['item-index']}
                 }))

        elif len(use_menu) > 1:
            action_menu.append(('use item',
                                {'text': ['Use Item',
                                          ' Defense: (depends)',
                                          ' Move: (depends)'],
                                 'menu': use_menu}))

        ### User-defined ###

        action_menu.append(('User-defined', {'text': ['User-defined action'],
                                             'action': {'name': 'user-defined'}}
                          ))

        return # No need to return action menu since it was a parameter


    def get_sections_in_template(self):
        '''
        This returns an array of the Fighter section headings that are
        expected (well, not _expected_ but any headings that aren't in this
        list should probably not be there) to be in a template.
        '''

        return ['stuff']  # permanent is handled specially

        # Transitory sections, not used in template:
        #   armor-index, state, weapon-index, opponent
        #
        # Not part of template:
        #   notes, short-notes, current, timers

        return sections


    def heal_fighter(self,
                     fighter_details    # 'details' is OK, here
                    ):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        if 'permanent' not in fighter_details:
            return

        for stat in fighter_details['permanent'].iterkeys():
            fighter_details['current'][stat] = (
                                        fighter_details['permanent'][stat])
        if (fighter_details['state'] != 'absent' and
                                        fighter_details['state'] != 'fight'):
            fighter_details['state'] = 'alive'
        # TODO: if ['Options']['reload-on-heal']: reload


    def make_empty_creature(self):
        return {'stuff': [],
                'weapon-index': None,
                'armor-index': None,
                'permanent': {},
                'current': {},
                'state': 'alive',
                'timers': [],
                'opponent': None,
                'notes': [],
                'short-notes': [],
                }


    def search_one_creature(self,
                            name,       # string containing the name
                            group,      # string containing the group
                            creature,   # dict describing the creature
                            look_for_re # compiled Python regex
                           ):
        result = []

        if look_for_re.search(name):
            result.append({'name': name,
                           'group': group,
                           'location': 'name',
                           'notes': name})

        if 'stuff' in creature:
            for thing in creature['stuff']:
                if look_for_re.search(thing['name']):
                    result.append({'name': name,
                                   'group': group,
                                   'location': 'stuff["name"]',
                                   'notes': thing['name']})
                if 'notes' in thing and look_for_re.search(thing['notes']):
                    result.append({'name': name,
                                   'group': group,
                                   'location': '%s["notes"]' % thing['name'],
                                   'notes': thing['notes']})

        if 'notes' in creature:
            for line in creature['notes']:
                if look_for_re.search(line):
                    result.append({'name': name,
                                   'group': group,
                                   'location': 'notes'})
                    break # Don't want an entry for each time it's in notes

        if 'short-notes' in creature:
            for line in creature['short-notes']:
                if look_for_re.search(line):
                    result.append({'name': name,
                                   'group': group,
                                   'location': 'short-notes',
                                   'notes': creature['short-notes']})

        return result

    #
    # Private and Protected Methods
    #


    def _adjust_hp(self,
                   fighter,  # Fighter object
                   adj       # the number of HP to gain or lose
                  ):
        fighter.details['current']['hp'] += adj


    def _do_attack(self,
                   param # {'fighter': xxx, Fighter object for attacker
                         #  'fight_handler', ...
                  ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''

        if param['fighter'].details['opponent'] is None:
            param['fight_handler'].pick_opponent()

        weapon, weapon_index = param['fighter'].get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return

        weapon['ammo']['shots_left'] -= 1
        return


    def _do_custom_action(self,
                          action       # {'name': <action>, parameters...}
                         ):
        height = 1
        title = 'What Action Is Performed'
        width = self._window_manager.getmaxyx()
        comment_string = self._window_manager.input_box(height, width, title)
        action['comment'] += ' -- %s' % comment_string
        return True


    def _do_reload(self,
                   param # {'fighter': Fighter object for attacker
                  ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        weapon, weapon_index = param['fighter'].get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return False

        clip_name = weapon['ammo']['name']
        for item in param['fighter'].details['stuff']:
            if item['name'] == clip_name and item['count'] > 0:
                weapon['ammo']['shots_left'] = weapon['ammo']['shots']
                item['count'] -= 1
                return True
        return False


    def _don_armor(self,
                  param # dict: {'armor': index, 'fighter': Fighter obj}
                 ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        param['fighter'].don_armor_by_index(param['armor'])
        return None if 'text' not in param else param


    def _draw_weapon(self,
                    param # dict: {'weapon': index, 'fighter': Fighter obj}
                   ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        param['fighter'].draw_weapon_by_index(param['weapon'])
        return


    def _use_item(self,
                  param # dict: {'item': index, 'fighter': Fighter obj}
                 ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        fighter = param['fighter']
        item_index = param['item']
        item = fighter.details['stuff'][item_index]
        item['count'] -= 1
        return


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
                         'sw':  {'num_dice': 3, 'plus': +2}},
                    21: {'thr': {'num_dice': 2, 'plus': 0},
                         'sw':  {'num_dice': 4, 'plus': -1}},
                    22: {'thr': {'num_dice': 2, 'plus': 0},
                         'sw':  {'num_dice': 4, 'plus': 0}},
                    23: {'thr': {'num_dice': 2, 'plus': +1},
                         'sw':  {'num_dice': 4, 'plus': +1}},
                    24: {'thr': {'num_dice': 2, 'plus': +1},
                         'sw':  {'num_dice': 4, 'plus': +2}},
                    25: {'thr': {'num_dice': 2, 'plus': +2},
                         'sw':  {'num_dice': 5, 'plus': -1}}
                         }

    abilities = {
        'skills': {
            # 'name': {'ask': 'number' | 'string' }
            #         {'value': value}
            "Acting": {'ask': 'number'}, 
            "Area Knowledge (Space Station)": {'ask': 'number'},
            "Armoury (Heavy Weapons)": {'ask': 'number'}, 
            "Armoury (Small Arms)": {'ask': 'number'}, 
            "Axe/Mace": {'ask': 'number'}, 
            "Bartender": {'ask': 'number'}, 
            "Beam Weapons (Pistol)": {'ask': 'number'}, 
            "Beam Weapons (Rifle)": {'ask': 'number'}, 
            "Brawling": {'ask': 'number'}, 
            "Camouflage": {'ask': 'number'}, 
            "Climbing": {'ask': 'number'}, 
            "Climbing": {'ask': 'number'}, 
            "Computer Hacking": {'ask': 'number'}, 
            "Computer Operation": {'ask': 'number'}, 
            "Computer Programming": {'ask': 'number'}, 
            "Connoisseur (Visual Arts)": {'ask': 'number'}, 
            "Cryptography": {'ask': 'number'}, 
            "Current Affairs (Teraforming)": {'ask': 'number'}, 
            "Detect Lies": {'ask': 'number'}, 
            "Diplomacy": {'ask': 'number'}, 
            "Electronics Operation (Security)": {'ask': 'number'}, 
            "Electronics Operation (Teraforming)": {'ask': 'number'}, 
            "Electronics Repair (Security)": {'ask': 'number'}, 
            "Electronics Repair (Teraforming)": {'ask': 'number'}, 
            "Engineer (Electronics)": {'ask': 'number'}, 
            "Engineer (Starships)": {'ask': 'number'}, 
            "Escape": {'ask': 'number'}, 
            "Expert Skill (Computer Security)": {'ask': 'number'}, 
            "Fast-Draw (Ammo)": {'ask': 'number'}, 
            "Fast-Draw (Knife)": {'ask': 'number'}, 
            "Fast-Draw (Pistol)": {'ask': 'number'}, 
            "Fast-Talk": {'ask': 'number'}, 
            "Filch": {'ask': 'number'}, 
            "First Aid": {'ask': 'number'}, 
            "Forensics": {'ask': 'number'}, 
            "Forgery": {'ask': 'number'}, 
            "Gambling": {'ask': 'number'}, 
            "Gesture": {'ask': 'number'}, 
            "Gunner (Beams)": {'ask': 'number'}, 
            "Gunner (Cannon)": {'ask': 'number'}, 
            "Guns (Grenade Launcher)": {'ask': 'number'}, 
            "Guns (Pistol)": {'ask': 'number'}, 
            "Hazardous Materials (Chemical)": {'ask': 'number'}, 
            "Holdout": {'ask': 'number'}, 
            "Interrogation": {'ask': 'number'}, 
            "Intimidation": {'ask': 'number'}, 
            "Karate": {'ask': 'number'}, 
            "Knife": {'ask': 'number'}, 
            "Law (Conglomerate)": {'ask': 'number'},
            "Law (Conglomerate, Trans territorial jurisdiction/the void)":
            {'ask': 'number'}, 
            "Lip Reading": {'ask': 'number'}, 
            "Lockpicking": {'ask': 'number'}, 
            "Mathematics (Applied)": {'ask': 'number'}, 
            "Mechanic (Spacecraft)": {'ask': 'number'}, 
            "Observation": {'ask': 'number'}, 
            "Physician": {'ask': 'number'}, 
            "Physics": {'ask': 'number'}, 
            "Pickpocket": {'ask': 'number'}, 
            "Piloting (Loader Mech)": {'ask': 'number'},
            "Piloting (Low-Performance Spacecraft)": {'ask': 'number'}, 
            "Running": {'ask': 'number'}, 
            "Scrounging": {'ask': 'number'},
            "Search": {'ask': 'number'}, 
            "Stealth": {'ask': 'number'}, 
            "Streetwise": {'ask': 'number'}, 
            "Theology (Vodun)": {'ask': 'number'}, 
            "Throwing": {'ask': 'number'}, 
            "Thrown Weapon (Knife)": {'ask': 'number'}, 
            "Tonfa": {'ask': 'number'}, 
            "Traps": {'ask': 'number'}, 
            "Urban Survival": {'ask': 'number'}, 
        },
        'advantages': {
    # 'name': {'ask': 'number' | 'string' }
    #         {'value': value}
            "Acute Vision": {'ask': 'number'}, 
            "Phobia": {'ask': 'string'},
            "Alcohol Intolerance": {'value': -1}, 
            "Appearance": {'ask': 'string'}, 
            "Bad Sight": {'value': -25}, 
            "Bad Temper": {'value': -10}, 
            "Cannot Speak": {'value': -10}, 
            "Channeling": {'value': 10}, 
            "Code of Honor": {'ask': 'string'}, 
            "Combat Reflexes": {'value': 15},
            "Compulsive Behavior": {'ask': 'string'}, 
            "Cultural Familiarity": {'ask': 'string'},
            "Curious": {'value': -5}, 
            "Deep Sleeper": {'value': 1}, 
            "Delusions": {'ask': 'string'},
            "Distractible": {'value': 1}, 
            "Dreamer": {'value': -1},
            "Dyslexia": {'value': -10}, 
            "Eidetic Memory": {'ask': 'number'}, 
            "Empathy": {'ask': 'number'},
            "Enemy": {'ask': 'string'},
            "Extra Hit Points": {'ask': 'number'}, 
            "Fit": {'value': 5}, 
            "Flashbacks": {'ask': 'string'}, 
            "G-Experience": {'ask': 'number'},
            "Guilt Complex": {'ask': 'string'},
            "Habit": {'ask': 'string'}, 
            "High Pain Threshold": {'value': 10}, 
            "Honest Face": {'value': 1}, 
            "Humble": {'value', -1}, 
            "Impulsiveness": {'ask': 'number'}, 
            "Light Sleeper": {'value': -5}, 
            "Like (Quirk) ": {'ask': 'string'},
            "Lwa": {'ask': 'string'},
            "Night Vision": {'ask': 'number'},
            "No Sense of Humor": {'value': -10}, 
            "Nosy": {'value': -1}, 
            "Personality Change": {'ask': 'string'}, 
            "Pyromania": {'value': -10}, 
            "Rapid Healing": {'value': 5}, 
            "Responsive": {'value': -1}, 
            "Secret": {'ask': 'string'},
            "Short Attention Span": {'value': -10}, 
            "Squeamish": {'value': -10}, 
            "Versatile": {'value': 5}, 
            "Vodou Practitioner (level 0)": {'value': 5},
            "Vodou Practitioner (Mambo/Hougan 1)": {'value': 15},
            "Vodou Practitioner (Mambo/Hougan 2)": {'value': 35},
            "Vodou Practitioner (Mambo/Hougan 3)": {'value': 65},
            "Vodou Practitioner (Bokor 1)": {'value': 20},
            "Vodou Practitioner (Bokor 2)": {'value': 45},
            "Vodou Practitioner (Bokor 3)": {'value': 75},
            "Vow": {'ask': 'string'},
            "Wealth": {'ask': 'string'},
            "Weirdness Magnet": {'value': -15}, 
        }
    }

    # These are specific to the Persephone version of the GURPS ruleset
    spells = {

        # Alphabetized for conevenience

        "Agonize": {
          "cost": 8, 
          "notes": "M40, HT negates", 
          "maintain": 6, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Alarm": {
          "cost": 1, 
          "notes": "M100", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 604800,   # one week
        }, 
        "Alter Visage": {
          "cost": 4, 
          "notes": "M41", 
          "maintain": 0, 
          "casting time": 60, 
          "duration": 3600,
        }, 
        "Analyze Magic": {
          "cost": 8, 
          "notes": "M102", 
          "maintain": None, 
          "casting time": 3600, 
          "duration": 0,    # Instant
        }, 
        "Animate Shadow": {
          "cost": 4, 
          "notes": "M154, Subject's shadow attacks them, HT negates", 
          "maintain": 4, 
          "casting time": 2, 
          "duration": 5,
        },
        "Armor": {
          "cost": None, 
          "notes": "M167, 2xDR, lasts 1 minute", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Awaken": {
          "cost": 1, 
          "notes": "M90", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Bless Plants": {
          "cost": 1, 
          "notes": "M161", 
          "maintain": 4, 
          "casting time": 300, 
          "duration": 0,    # One season - no need to keep track
        }, 
        "Blink": {
          "cost": 2, 
          "notes": "M148", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Boost Dexterity": {
          "cost": 1, 
          "notes": "M37", 
          "maintain": 2, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Bravery": {
          "cost": 2, 
          "notes": "M134", 
          "maintain": 2, 
          "casting time": 1, 
          "duration": 3600,
        }, 
        "Charm": {
          "cost": 6, 
          "notes": "M139, vs. Will", 
          "maintain": 3, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Choke": {
          "cost": 4, 
          "notes": "M40, vs. HT", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 30,
        }, 
        "Climbing": {
          "cost": 1, 
          "notes": "M35", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Clumsiness": {
          "cost": 1, 
          "notes": "M36", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Command": {
          "cost": 4, 
          "notes": "M136, vs. Will", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Communicate": {
          "cost": 4, 
          "notes": "M48", 
          "maintain": 4, 
          "casting time": 4, 
          "duration": 60,
        }, 
        "Conceal Magic": {
          "cost": 1, 
          "notes": "M122", 
          "maintain": None, 
          "casting time": 3, 
          "duration": 36000,    # 10 hours
        }, 
        "Cure Disease": {
          "cost": 4, 
          "notes": "M91", 
          "maintain": 2, 
          "casting time": 600, 
          "duration": 0,
        }, 
        "Daze": {
          "cost": 3, 
          "notes": "M134", 
          "maintain": 2, 
          "casting time": 2, 
          "duration": 60,
        }, 
        "Death Touch": {
          "cost": None, 
          "notes": "M41, 1-3, needs touch", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Death Vision": {
          "cost": 2, 
          "notes": "M149, vs. IQ", 
          "maintain": None, 
          "casting time": 3, 
          "duration": 1,
        }, 
        "Detect Magic": {
          "cost": 2, 
          "notes": "M101", 
          "maintain": None, 
          "casting time": 300, 
          "duration": 0,
        }, 
        "Emotion Control": {
          "cost": 2, 
          "notes": "M137", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 3600,
        }, 
        "Enchant": {
          "cost": None, 
          "notes": "M56", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,    # Permanent - no need to track
        }, 
        "Enslave": {
          "cost": 30, 
          "notes": "M141, vs. Will", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,    # Permanent - no need to track
        }, 
        "Evisceration": {
          "cost": 10, 
          "notes": "M154, HT/IQ negates, Magery 3", 
          "maintain": 0, 
          "casting time": 5, 
          "duration": 0,
        }, 
        "Explosive Lightning": {
          "cost": None, 
          "notes": "M196, cost 2-mage level, damage 1d-1 /2", 
          "maintain": 0, 
          "casting time": None, 
          "duration": 0,
        },
        "False Memory": {
          "cost": 3, 
          "notes": "M139, vs. Will", 
          "maintain": 0, 
          "casting time": 5, 
          "duration": None, # Ask
        }, 
        "Far Hearing": {
          "cost": 4, 
          "notes": "M173", 
          "maintain": 2, 
          "casting time": 3, 
          "duration": 60,
        }, 
        "Fear": {
          "cost": 1, 
          "notes": "M134", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 36000,    # 10 minutes
        }, 
        "Fog": {
          "cost": None, 
          "notes": "M193, cost: 2/yard radius, lasts 1 minute", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Foolishness": {
          "cost": None, 
          "notes": "M134", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Fumble": {
          "cost": 3, 
          "notes": "M38", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Golem": {
          "cost": 250, 
          "notes": "M59", 
          "maintain": 0, 
          "casting time": 0, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Grace": {
          "cost": 4, 
          "notes": "M37", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Great Ward": {
          "cost": None, 
          "notes": "M122, cost: 1/person (min:4)", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        },
        "Hair Growth": {
          "cost": 1, 
          "notes": "M39", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 5,
        }, 
        "Haircut": {
          "cost": 2, 
          "notes": "M39", 
          "maintain": None, 
          "casting time": 2, 
          "duration": 0,
        }, 
        "Heal Plant": {
          "cost": 3, 
          "notes": "M161", 
          "maintain": None, 
          "casting time": 60, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Identify Plant": {
          "cost": 2, 
          "notes": "M161", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Identify Spell": {
          "cost": 2, 
          "notes": "M102", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Itch": {
          "cost": 2, 
          "notes": "M35", 
          "maintain": None, 
          "casting time": 1, 
          "duration": None, # Ask
        }, 
        "Lend Energy": {
          "cost": None, 
          "notes": "M89", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Lend Vitality": {
          "cost": None, 
          "notes": "M89", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 3600,
        }, 
        "Lesser Geas": {
          "cost": 12, 
          "notes": "M140, vs. Will ", 
          "maintain": 0, 
          "casting time": 30, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Light": {
          "cost": 1, 
          "notes": "M110", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Lightning": {
          "cost": None, 
          "notes": "M196, cost 1-3, cast=cost, needs an attack", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Lightning Whip": {
          "cost": None, 
          "notes": "M196, cost 1 per 2 yards reach", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 10,
        },
        "Loyalty": {
          "cost": 2, 
          "notes": "M136", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 3600,
        }, 
        "Luck": {
          "cost": 2, 
          "notes": "V2", 
          "maintain": 1, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Lure": {
          "cost": 1, 
          "notes": "M137", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 3600,
        }, 
        "Madness": {
          "cost": None, 
          "notes": "M136, cost: 2-6", 
          "maintain": 0, 
          "casting time": 2, 
          "duration": 60,
        },
        "Major Heal": {
          "cost": None, 
          "notes": "M91", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Malfunction": {
          "cost": 5, 
          "notes": "M177, touch", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Manastone": {
          "cost": None, 
          "notes": "M70", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,    # Indefinite -- no need to track
        }, 
        "Might": {
          "cost": None, 
          "notes": "M37", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Mind-Sending": {
          "cost": 4, 
          "notes": "M47", 
          "maintain": 4, 
          "casting time": 4, 
          "duration": 60,
        }, 
        "Minor Heal": {
          "cost": None, 
          "notes": "M91", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Pain": {
          "cost": 2, 
          "notes": "M36, vs. HT", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 1,
        }, 
        "Panic": {
          "cost": 4, 
          "notes": "M134, vs. Will", 
          "maintain": 2, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Phase": {
          "cost": 3, 
          "notes": "M83, avoid an attack", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        },
        "Planar Summons": {
          "cost": None, 
          "notes": "M82", 
          "maintain": 0, 
          "casting time": 300, 
          "duration": 3600,
        }, 
        "Powerstone": {
          "cost": 20, 
          "notes": "M69", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Relieve Sickness": {
          "cost": 2, 
          "notes": "M90", 
          "maintain": 2, 
          "casting time": 10, 
          "duration": 600,  # 10 minutes
        }, 
        "Repair": {
          "cost": None, 
          "notes": "M118", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Restoration": {
          "cost": 15, 
          "notes": "M93", 
          "maintain": 0, 
          "casting time": 60, 
          "duration": 0,    # Permanent -- no need to track
        }, 
        "Rotting Death": {
          "cost": 3, 
          "notes": "M154 vs. HT, needs touch", 
          "maintain": 2, 
          "casting time": 1, 
          "duration": 1,
        }, 
        "Seek Machine": {
          "cost": 3, 
          "notes": "M175", 
          "maintain": None, 
          "casting time": 10, 
          "duration": 0,
        }, 
        "Seek Plant": {
          "cost": 2, 
          "notes": "M161", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Sense Emotion": {
          "cost": 2, 
          "notes": "M45", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Sense Foes": {
          "cost": 2, 
          "notes": "M45", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Sense Life": {
          "cost": None, 
          "notes": "M45, cost 1/2 per yard radius, see M11", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Shapeshifting": {
          "cost": None, 
          "notes": "M32", 
          "maintain": None, 
          "casting time": 3, 
          "duration": 3600,
        }, 
        "Shield": {
          "cost": 2, 
          "notes": "M167", 
          "maintain": None, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Sleep": {
          "cost": 4, 
          "notes": "M135", 
          "maintain": 0, 
          "casting time": 3, 
          "duration": 0,
        }, 
        "Spasm": {
          "cost": 2, 
          "notes": "M35", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Stop Power": {
          "cost": None, 
          "notes": "M179, 3 pts /1.5 yard radius", 
          "maintain": 0, 
          "casting time": 3, 
          "duration": 60,
        }, 
        "Strike Blind": {
          "cost": 4, 
          "notes": "M38, vs HT", 
          "maintain": 2, 
          "casting time": 1, 
          "duration": 10,
        }, 
        "Stun": {
          "cost": 2, 
          "notes": "M37, B420, vs. HT", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Summon Demon": {
          "cost": 20, 
          "notes": "M155", 
          "maintain": 0, 
          "casting time": 300, 
          "duration": 3600,
        }, 
        "Summon Spirit": {
          "cost": 20, 
          "notes": "M150", 
          "maintain": 0, 
          "casting time": 300, 
          "duration": 60,
        }, 
        "Teleport": {
          "cost": None, 
          "notes": "M147, cost: 5 for 100 yards", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Terror": {
          "cost": 4, 
          "notes": "M134, Area, Will negates", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Tell Time": {
          "cost": 1, 
          "notes": "M100", 
          "maintain": 2, 
          "casting time": 1, 
          "duration": 0,
        }, 
        "Throw Spell": {
          "cost": 3, 
          "notes": "M128", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 0,    # Indefinite -- no need to track
        }, 
        "Total Paralysis": {
          "cost": None, 
          "notes": "M40, cost: 2-6", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 60,
        },
        "Wall Of Lightning": {
          "cost": None, 
          "notes": "M197", 
          "maintain": 0, 
          "casting time": 1, 
          "duration": 60,
        }, 
        "Wizard Eye": {
          "cost": 4, 
          "notes": "M104", 
          "maintain": 2, 
          "casting time": 2, 
          "duration": 60,
        }, 
        "Zombie": {
          "cost": 8, 
          "notes": "M151", 
          "maintain": None, 
          "casting time": 60, 
          "duration": 0,    # Permanent -- no need to track
        }
    }

    # Posture: B551; 'attack' is melee, 'target' is ranged
    posture = {
        'standing':  {'attack':  0, 'defense':  0, 'target':  0},
        'crouching': {'attack': -2, 'defense':  0, 'target': -2},
        'kneeling':  {'attack': -2, 'defense': -2, 'target': -2},
        'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        'sitting':   {'attack': -2, 'defense': -2, 'target': -2},
        'lying':     {'attack': -4, 'defense': -3, 'target': -2},
    }

    hit_location_table = {3:  'head',
                          4:  'head',
                          5:  'face',
                          6:  'right thigh',
                          7:  'right calf',
                          8:  'right arm',
                          9:  'stomach',
                          10: 'chest/back',
                          11: 'groin/hip/butt',
                          12: 'left arm',
                          13: 'left calf',
                          14: 'left thigh',
                          15: 'hand',
                          16: 'foot',
                          17: 'neck',
                          18: 'neck'}

    (MAJOR_WOUND_SUCCESS,
     MAJOR_WOUND_SIMPLE_FAIL,
     MAJOR_WOUND_BAD_FAIL) = range(3)

    def __init__(self, window_manager):
        super(GurpsRuleset, self).__init__(window_manager)


    #
    # Public Methods
    #


    def can_finish_turn(self,
                        fighter # Fighter object
                       ):
        if len(fighter.details['actions_this_turn']) > 0:
            return True

        if not fighter.is_conscious():
            return True

        return False


    def damage_to_string(self,
                         damages # list of dict -- returned by 'get_damage'
                        ):
        '''
        Converts array of dicts returned by get_damage into a string.
        '''
        results = []
        for damage in damages:
            string = []
            if damage['attack_type'] is not None:
                string.append('%s: ' % damage['attack_type'])
            string.append('%dd%+d ' % (damage['num_dice'], damage['plus']))
            string.append('(%s)' % damage['damage_type'])
            results.append(''.join(string))

        return ', '.join(results)


    def do_action(self,
                  fighter,      # Fighter object
                  action,       # {'name': <action>, parameters...}
                  fight_handler # FightHandler object
                 ):
        handled = super(GurpsRuleset, self).do_action(fighter,
                                                      action,
                                                      fight_handler)

        if 'name' not in action:
            return # It's just a comment

        if action['name'] == 'adjust-fp':
            self._do_adjust_fp(fighter, action['adj'])
            handled = True

        elif action['name'] == 'aim':
            self._do_aim({'fighter': fighter,
                          'braced': action['braced'],
                          'fight_handler': fight_handler})
            handled = True

        elif action['name'] == 'cast-spell':
            self._cast_spell({'fighter': fighter,
                              'spell': action['spell-index'],
                              'fight_handler': fight_handler})
            handled = True

        elif action['name'] == 'change-posture':
            self._change_posture({'fighter': fighter,
                                  'posture': action['posture']})
            handled = True

        elif action['name'] == 'concentrate':
            handled = True # This is here just so that it's logged

        elif action['name'] == 'defend':
            self._do_defense({'fighter': fighter})
            handled = True

        elif action['name'] == 'evaluate':
            handled = True # This is here just so that it's logged

        elif action['name'] == 'feint':
            handled = True # This is here just so that it's logged
        
        elif action['name'] == 'move':
            handled = True # This is here just so that it's logged

        elif action['name'] == 'move-and-attack':
            self._do_attack({'fighter': fighter,
                             'fight_handler': fight_handler})
            handled = True # This is here just so that it's logged

        elif action['name'] == 'nothing':
            handled = True # This is here just so that it's logged

        elif action['name'] == 'pick-opponent':
            self.reset_aim(fighter)
            handled = True

        elif action['name'] == 'stun':
            fighter.details['stunned'] = True
            handled = True

        # TODO: put this in Ruleset as post_action_accounting()
        if handled:
            fighter.details['actions_this_turn'].append(action['name'])
        else:
            self._window_manager.error(
                            ['action "%s" is not handled by any ruleset' %
                                                            action['name']])

        return # Nothing to return


    def end_turn(self, fighter):
        fighter.details['shock'] = 0
        if fighter.details['stunned']:
            stunned_menu = [
                (('Succeeded (roll <= HT (%d))' %
                            fighter.details['current']['ht']), True),
                ('Missed roll', False),]
            recovered_from_stun = self._window_manager.menu(
                                            'Stunned: Roll <= HT to recover',
                                            stunned_menu)
            if recovered_from_stun:
                fighter.details['stunned'] = False


    def get_action_menu(self,
                        fighter,    # Fighter object
                        opponent    # Fighter object
                       ):
        ''' Builds the menu of maneuvers allowed for the fighter. '''

        action_menu = []

        move = fighter.details['current']['basic-move']

        if fighter.details['stunned']:
            action_menu.append(
                ('do nothing (stunned)', {'text': ['Do Nothing (Stunned)',
                                                   ' Defense: any @-4',
                                                   ' Move: none'],
                                          'action': {'name': 'nothing'}}
                )
            )
            return action_menu # No other actions permitted


        # Figure out who we are and what we're holding.

        weapon, weapon_index = fighter.get_current_weapon()
        holding_ranged = (False if weapon is None else
                                (weapon['type'] == 'ranged weapon'))


        # Posture SUB-menu

        posture_menu = []
        for posture in GurpsRuleset.posture.iterkeys():
            if posture != fighter.details['posture']:
                posture_menu.append(
                    (posture,   {'text': [('Change posture to %s' % posture),
                                          ' NOTE: crouch 1st action = free',
                                          '       crouch->stand = free',
                                          '       kneel->stand = step',
                                          ' Defense: any',
                                          ' Move: none'],
                                 'action': {'name': 'change-posture',
                                            'posture': posture}
                                }))


        # Build the action_menu.  Alphabetical order.  Only allow the things
        # the fighter can do based on zis current situation.

        if holding_ranged:
            if weapon['ammo']['shots_left'] > 0:

                # Aim
                #
                # Ask if we're bracing if this is the first round of aiming
                # B364 (NOTE: Combat Lite on B234 doesn't mention bracing).
                if fighter.details['aim']['rounds'] == 0:
                    brace_menu = [
                        ('Bracing (B364)',
                                        {'text': ['Aim with brace',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'action': {'name': 'aim',
                                                    'braced': True}
                                        }),
                        ('Not Bracing', {'text': ['Aim',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'action': {'name': 'aim',
                                                   'braced': False}})
                    ]
                    action_menu.append(('Aim (B324, B364)',
                                        {'text': ['Aim',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'menu': brace_menu})
                                      )
                else:
                    action_menu.append(('Aim (B324, B364)',  
                                        {'text': ['Aim',
                                                  ' Defense: any loses aim',
                                                  ' Move: step'],
                                         'action': {'name': 'aim',
                                                    'braced': False}})
                                      )


        action_menu.extend([
            ('posture (B551)',         {'text': [
                                            'Change posture',
                                            ' NOTE: crouch 1st action = free',
                                            '       crouch->stand = free',
                                            '       kneel->stand = step',
                                            ' Defense: any',
                                            ' Move: none'],
                                        'menu': posture_menu}),
            ('Concentrate (B366)',     {'text': ['Concentrate',
                                                 ' Defense: any w/will roll',
                                                 ' Move: step'],
                                        'action': {'name': 'concentrate'}}),
            ('Defense, all out',       {'text': ['All out defense',
                                                 ' Defense: double',
                                                 ' Move: step'],
                                        'action': {'name': 'defend'}
                                       }),
        ])

        # Spell casters.

        if 'spells' in fighter.details:
            spell_menu = []
            for index, spell in enumerate(fighter.details['spells']):
                if spell['name'] not in GurpsRuleset.spells:
                    self._window_manager.error(
                        ['Spell "%s" not in GurpsRuleset.spells' %
                                                                spell['name']]
                    )
                    continue
                complete_spell = copy.deepcopy(spell)
                complete_spell.update(GurpsRuleset.spells[spell['name']])

                cast_text_array = ['%s -' % complete_spell['name']]

                for piece in ['cost',
                              'skill',
                              'casting time',
                              'duration',
                              'notes']:
                    if piece in complete_spell:
                        cast_text_array.append('%s:%r' % (piece,
                                                         complete_spell[piece]))
                cast_text = ' '.join(cast_text_array)
                spell_menu.append(  
                    (cast_text,
                    {'text': [('Cast "%s"' % complete_spell['name']),
                              ' Defense: none',
                              ' Move: none'],

                     'action': {'name': 'cast-spell',
                                'spell-index': index}
                    }))
            spell_menu = sorted(spell_menu, key=lambda x: x[0].upper())

            action_menu.append(('cast Spell',
                                {'text': ['Cast Spell',
                                          ' Defense: none',
                                          ' Move: none'],
                                 'menu': spell_menu}))


        action_menu.append(('evaluate (B364)', {'text': ['Evaluate',
                                                         ' Defense: any',
                                                         ' Move: step'],
                                                'action': {'name': 'evaluate'}
                                               }))

        # Can only feint with a melee weapon
        if weapon is not None and holding_ranged == False:
            action_menu.append(('feint (B365)',
                                   {'text': ['Feint',
                                             ' Contest of melee weapon or DX',
                                             '   subtract score from opp',
                                             '   active defense next turn',
                                             '   (for both, if all-out-attack)',
                                             ' Defense: any, parry *',
                                             ' Move: step'],
                                    'action': {'name': 'feint'}
                                   }))
        
        if (fighter.details['current']['fp'] <
                        (fighter.details['permanent']['fp'] / 3)):
            move_string = 'half=%d (FP:B426)' % (move/2)
        else:
            move_string = 'full=%d' % move

        # Move and attack info
        move_and_attack_notes = ['Move & Attack',
                                 ' Defense: Dodge,block',
                                 ' Move: %s' % move_string]
        if weapon is None:
            unarmed_skills = self.get_weapons_unarmed_skills(weapon)
            unarmed_info = self.get_unarmed_info(fighter,
                                                 opponent,
                                                 weapon,
                                                 unarmed_skills)
            to_hit = unarmed_info['punch_skill'] - 4
            to_hit = 9 if to_hit > 9 else to_hit
            move_and_attack_notes.append(' Punch to-hit: %d' % to_hit)

            to_hit = unarmed_info['kick_skill'] - 4
            to_hit = 9 if to_hit > 9 else to_hit
            move_and_attack_notes.append(' Kick to-hit: %d' % to_hit)
        else:
            to_hit, ignore_why = self.get_to_hit(fighter, opponent, weapon)
            if holding_ranged:
                to_hit -= 2 # or weapon's bulk rating, whichever is worse
            else:
                to_hit -= 4

            to_hit = 9 if to_hit > 9 else to_hit
            move_and_attack_notes.append(' %s to-hit: %d' % (weapon['name'],
                                                             to_hit))

        action_menu.extend([
            ('move (B364) %s' % move_string,
                                       {'text': ['Move',
                                                 ' Defense: any',
                                                 ' Move: %s' % move_string],
                                        'action': {'name': 'move'}}),
            ('Move and attack (B365)', {'text': move_and_attack_notes,
                                        'action': {'name': 'move-and-attack'}}),
            ('nothing',                {'text': ['Do nothing',
                                                 ' Defense: any',
                                                 ' Move: none'],
                                        'action': {'name': 'nothing'}}),
        ])

        super(GurpsRuleset, self).get_action_menu(action_menu,
                                                  fighter,
                                                  opponent)

        action_menu = sorted(action_menu, key=lambda x: x[0].upper())
        return action_menu


    def get_block_skill(self,                       # Public to aid in testing.
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

        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.details['advantages']:
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


    #   { 
    #       'Skills': { 'Axe/Mace': 8, 'Climbing': 8, },
    #       'Advantages': { 'Bad Tempter': -10, 'Nosy': -1, },
    #   }


    def get_character_description(self,
                                  character,   # Fighter object
                                  output,      # recepticle for character data.
                                               # [[{'text','mode'},...], #line 0
                                               #  [...],               ] #line 1
                                 ):

        # attributes

        mode = curses.A_NORMAL 
        output.append([{'text': 'Attributes', 'mode': mode | curses.A_BOLD}])
        found_one = False
        pieces = []

        first_row = ['st', 'dx', 'iq', 'ht', 'per']
        first_row_pieces = {}
        for row in range(2):
            found_one_this_row = False
            for item_key in character.details['permanent'].iterkeys():
                in_first_row = item_key in first_row
                if row == 0 and not in_first_row:
                    continue
                if row != 0 and in_first_row:
                    continue
                text = '%s:%d/%d' % (item_key,
                                     character.details['current'][item_key],
                                     character.details['permanent'][item_key])
                if (character.details['current'][item_key] == 
                                     character.details['permanent'][item_key]):
                    mode = curses.A_NORMAL
                else:
                    mode = (curses.color_pair(GmWindowManager.YELLOW_BLACK) |
                                                                curses.A_BOLD)

                if row == 0:
                    # Save the first row as pieces so we can put them in the
                    # proper order, later.
                    first_row_pieces[item_key] = {'text': '%s ' % text,
                                                  'mode': mode}
                else:
                    pieces.append({'text': '%s ' % text, 'mode': mode})
                found_one = True
                found_one_this_row = True

            if found_one_this_row:
                if row == 0:
                    for item_key in first_row:
                        pieces.append(first_row_pieces[item_key])

                pieces.insert(0, {'text': '  ', 'mode': curses.A_NORMAL})
                output.append(copy.deepcopy(pieces))
                del pieces[:]

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # stuff

        mode = curses.A_NORMAL 
        output.append([{'text': 'Equipment', 'mode': mode | curses.A_BOLD}])

        in_use_items = []
        armor_in_use, throw_away = character.get_current_armor()
        if armor_in_use is not None:
            in_use_items.append(armor_in_use)
        weapon_in_use, throw_away = character.get_current_weapon()
        if weapon_in_use is not None:
            in_use_items.append(weapon_in_use)

        found_one = False
        for item in sorted(character.details['stuff'], key=lambda x: x['name']):
            found_one = True
            EquipmentManager.get_description(item, in_use_items, output)

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # advantages

        mode = curses.A_NORMAL 
        output.append([{'text': 'Advantages', 'mode': mode | curses.A_BOLD}])

        found_one = False
        for advantage, value in sorted(
                                    character.details['advantages'].iteritems(),
                                    key=lambda (k,v): (k, v)):
            found_one = True
            output.append([{'text': '  %s: %r' % (advantage, value),
                            'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # skills

        mode = curses.A_NORMAL 
        output.append([{'text': 'Skills', 'mode': mode | curses.A_BOLD}])

        found_one = False
        for skill, value in sorted(character.details['skills'].iteritems(),
                                   key=lambda (k,v): (k,v)):
            found_one = True
            output.append([{'text': '  %s: %d' % (skill, value),
                            'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # spells

        if 'spells' in character.details:
            mode = curses.A_NORMAL 
            output.append([{'text': 'Spells', 'mode': mode | curses.A_BOLD}])

            found_one = False
            for spell in sorted(character.details['spells'],
                                key=lambda(x): x['name']):
                if spell['name'] not in GurpsRuleset.spells:
                    self._window_manager.error(
                        ['Spell "%s" not in GurpsRuleset.spells' %
                                                                spell['name']]
                    )
                    continue
                complete_spell = copy.deepcopy(spell)
                complete_spell.update(GurpsRuleset.spells[spell['name']])
                found_one = True
                output.append(
                        [{'text': '  %s (%d): %s' % (complete_spell['name'],
                                                     complete_spell['skill'],
                                                     complete_spell['notes']),
                          'mode': mode}])

            if not found_one:
                output.append([{'text': '  (None)', 'mode': mode}])

        # timers

        mode = curses.A_NORMAL 
        output.append([{'text': 'Timers', 'mode': mode | curses.A_BOLD}])

        found_one = False
        timers = character.timers.get_all() # objects
        for timer in timers:
            found_one = True
            text = timer.get_description()
            leader = '  '
            for line in text:
                output.append([{'text': '%s%s' % (leader, line),
                                'mode': mode}])
                leader = '    '

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # notes

        mode = curses.A_NORMAL 
        output.append([{'text': 'Notes', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in character.details:
            for note in character.details['notes']:
                found_one = True
                output.append([{'text': '  %s' % note, 'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])


    def get_creature_abilities(self):
        return GurpsRuleset.abilities


    def get_damage(self,
                   fighter,   # Fighter object
                   weapon     # dict {'type': 'imp', 'thr': +1, ...}
                  ):
        st = fighter.details['current']['st']
        results = []
        why = []

        if 'dice' in weapon['damage']:
            damage_type_str = self.__get_damage_type_str(
                                            weapon['damage']['dice']['type'])
            results.append(
                {'attack_type': None,
                 'num_dice': weapon['damage']['dice']['num_dice'],
                 'plus': weapon['damage']['dice']['plus'],
                 'damage_type': damage_type_str})
            why.append('Weapon %s Damage: %dd%+d' % (
                                          weapon['name'],
                                          weapon['damage']['dice']['num_dice'],
                                          weapon['damage']['dice']['plus']))
        if 'sw' in weapon['damage']:
            damage_type_str = self.__get_damage_type_str(
                                            weapon['damage']['sw']['type'])
            results.append(
                {'attack_type': 'sw',
                 'num_dice': GurpsRuleset.melee_damage[st]['sw']['num_dice'],
                 'plus': GurpsRuleset.melee_damage[st]['sw']['plus'] +
                                            weapon['damage']['sw']['plus'],
                 'damage_type': damage_type_str})

            why.append('Weapon %s Damage: sw%+d' % (
                                             weapon['name'],
                                             weapon['damage']['sw']['plus']))
            why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                       (st,
                        GurpsRuleset.melee_damage[st]['sw']['num_dice'],
                        GurpsRuleset.melee_damage[st]['sw']['plus']))
            if weapon['damage']['sw']['plus'] != 0:
                why.append('  ...%+d for the weapon' % 
                                            weapon['damage']['sw']['plus'])
            why.append('  ...damage: %dd%+d' % 
                (GurpsRuleset.melee_damage[st]['sw']['num_dice'],
                 GurpsRuleset.melee_damage[st]['sw']['plus'] +
                                            weapon['damage']['sw']['plus']))

        if 'thr' in weapon['damage']:
            damage_type_str = self.__get_damage_type_str(
                                            weapon['damage']['thr']['type'])
            results.append(
                {'attack_type': 'thr',
                 'num_dice': GurpsRuleset.melee_damage[st]['thr']['num_dice'],
                 'plus': GurpsRuleset.melee_damage[st]['thr']['plus'] +
                                            weapon['damage']['thr']['plus'],
                 'damage_type': damage_type_str})

            why.append('Weapon %s Damage: thr%+d' % (
                                            weapon['name'],
                                            weapon['damage']['thr']['plus']))
            why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                            (st,
                             GurpsRuleset.melee_damage[st]['thr']['num_dice'],
                             GurpsRuleset.melee_damage[st]['thr']['plus']))
            if weapon['damage']['thr']['plus'] != 0:
                why.append('  ...%+d for the weapon' % 
                                            weapon['damage']['thr']['plus'])
            why.append('  ...damage: %dd%+d' % 
                (GurpsRuleset.melee_damage[st]['thr']['num_dice'],
                 GurpsRuleset.melee_damage[st]['thr']['plus'] +
                                            weapon['damage']['thr']['plus']))

        if len(results) == 0:
            return '(None)', why

        return results, why


    def get_dodge_skill(self,                       # Public to aid in testing
                        fighter # Fighter object
                       ): # B326
        dodge_why = []
        dodge_skill_modified = False

        dodge_skill = 3 + int(fighter.details['current']['basic-speed'])
        dodge_why.append('Dodge (B326) @ int(basic-speed(%.1f))+3 = %d' % (
                                fighter.details['current']['basic-speed'],
                                dodge_skill))

        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.details['advantages']: # B43
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
                '  dodge(%d)/2 (round up) due to hp(%d) < perm-hp(%d)/3 (B327)'
                                    % (dodge_skill,
                                       fighter.details['current']['hp'],
                                       fighter.details['permanent']['hp']))
            dodge_skill = int(((dodge_skill)/2.0) + 0.5)

        # B426
        if (fighter.details['current']['fp'] <
                                    fighter.details['permanent']['fp']/3.0):
            dodge_skill_modified = True
            dodge_why.append(
                '  dodge(%d)/2 (round up) due to fp(%d) < perm-fp(%d)/3 (B426)'
                                    % (dodge_skill,
                                       fighter.details['current']['fp'],
                                       fighter.details['permanent']['fp']))
            dodge_skill = int(((dodge_skill)/2.0) + 0.5)

        if dodge_skill_modified:
            dodge_why.append('  ...for a dodge skill total = %d' % dodge_skill)

        return dodge_skill, dodge_why


    def get_fight_description(self,
                              fight,     # Fight object
                              output,    # recepticle for fight detail.
                                         # [[{'text','mode'},...],  # line 0
                                         #  [...],               ]  # line 1...
                             ):

        # stuff

        mode = curses.A_NORMAL 
        output.append([{'text': 'Equipment', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'stuff' in fight.details:
            for item in sorted(fight.details['stuff'], key=lambda x: x['name']):
                found_one = True
                EquipmentManager.get_description(item, [], output)

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # Timers

        mode = curses.A_NORMAL 
        output.append([{'text': 'Timers', 'mode': mode | curses.A_BOLD}])

        found_one = False
        timers = fight.timers.get_all() # objects
        for timer in timers:
            found_one = True
            text = timer.get_description()
            leader = '  '
            for line in text:
                output.append([{'text': '%s%s' % (leader, line),
                                'mode': mode}])
                leader = '    '

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # Notes

        mode = curses.A_NORMAL 
        output.append([{'text': 'Notes', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in fight.details:
            for note in fight.details['notes']:
                found_one = True
                output.append([{'text': '  %s' % note, 'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])


    def get_fighter_defenses_notes(self,
                                   fighter, # Fighter object
                                   opponent # Fighter object
                                  ):
        notes = []
        why = []

        weapon, holding_weapon_index = fighter.get_current_weapon()
        unarmed_skills = self.get_weapons_unarmed_skills(weapon)

        unarmed_info = None
        if unarmed_skills is not None:
            unarmed_info = self.get_unarmed_info(fighter,
                                                 opponent,
                                                 weapon,
                                                 unarmed_skills)

        dodge_skill, dodge_why = self.get_dodge_skill(fighter)
        if dodge_skill is not None:
            dodge_string = 'Dodge (B326): %d' % dodge_skill
            why.extend(dodge_why)
            notes.append(dodge_string)

        if unarmed_skills is not None: # Unarmed Parry
            notes.append('%s: %d' % (unarmed_info['parry_string'],
                                     unarmed_info['parry_skill']))

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

        # Armor


        dr = 0
        dr_text_array = []
        armor, armor_index = fighter.get_current_armor()
        if armor is not None:
            dr += armor['dr']
            dr_text_array.append(armor['name'])

        if 'Damage Resistance' in fighter.details['advantages']:
            # GURPS rules, B46, 5 points per level of DR advantage
            dr += (fighter.details['advantages']['Damage Resistance']/5)
            dr_text_array.append('DR Advantage')

        dr_text = ' + '.join(dr_text_array)

        if dr > 0:
            notes.append('Armor: "%s", DR: %d' % (dr_text, dr))
            why.append('Armor: "%s", DR: %d' % (dr_text, dr))
            if (armor is not None and 'notes' in armor and
                                                    len(armor['notes']) != 0):
                why.append('  %s' % armor['notes'])


        return notes, why



    def get_fighter_to_hit_damage_notes(self,
                                        fighter,    # Fighter object
                                        opponent    # Fighter object
                                       ):
        notes = []
        weapon, holding_weapon_index = fighter.get_current_weapon()
        unarmed_skills = self.get_weapons_unarmed_skills(weapon)

        if weapon is not None:
            notes.append('%s' % weapon['name'])

        if unarmed_skills is None:
            if weapon['skill'] in fighter.details['skills']:
                to_hit, ignore_why = self.get_to_hit(fighter, opponent, weapon)
                if to_hit is None:
                    self._window_manager.error(
                        ['%s requires "%s" skill not had by "%s"' %
                                                             (weapon['name'],
                                                              weapon['skill'],
                                                              fighter.name)])
                else:
                    damage, ignore_why = self.get_damage(fighter, weapon)
                    damage_str = self.damage_to_string(damage)
                    notes.append('  to-hit: %d' % to_hit)
                    notes.append('  damage: %s' % damage_str)
            else:
                self._window_manager.error(
                    ['%s requires "%s" skill not had by "%s"' %
                                                             (weapon['name'],
                                                              weapon['skill'],
                                                              fighter.name)])
        else:
            unarmed_info = self.get_unarmed_info(fighter,
                                                 opponent,
                                                 weapon,
                                                 unarmed_skills)

            notes.append(unarmed_info['punch_string'])
            notes.append('  to-hit: %d, damage: %s' % (
                                                unarmed_info['punch_skill'],
                                                unarmed_info['punch_damage']))

            notes.append(unarmed_info['kick_string'])
            notes.append('  to-hit: %d, damage: %s' % (
                                                unarmed_info['kick_skill'],
                                                unarmed_info['kick_damage']))

        return notes


    def get_fighter_notes(self,
                          fighter   # Fighter object
                         ):
        notes = []

        # Ranged weapon status

        weapon, holding_weapon_index = fighter.get_current_weapon()
        if holding_weapon_index is not None:
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
                

        # Active aim

        if (fighter.details['aim'] is not None and
                                    fighter.details['aim']['rounds'] != 0):
            notes.append('Aiming')

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


        return notes


    def get_parry_skill(self,                       # Public to aid in testing
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

        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'parry' in weapon:
            parry_skill += weapon['parry']
            parry_skill_modified = True
            parry_why.append('  %+d due to weapon modifiers' % weapon['parry'])

        if 'Combat Reflexes' in fighter.details['advantages']:
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


    def get_fight_commands(self,
                           fight_handler    # FightHandler object
                          ):
        ''' Returns fight commands that are specific to the GURPS ruleset. '''
        return { 
            ord('f'): {'name': 'FP damage',
                       'func': self.__damage_FP,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                      },
            ord('S'): {'name': 'Stun',
                       'func': self.__stun,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                      },
            }

    def get_sections_in_template(self):
        '''
        This returns an array of the Fighter section headings that are
        expected (well, not _expected_ but any headings that aren't in this
        list should probably not be there) to be in a template.
        '''
        sections = ['skills', 'advantages', 'spells']
        sections.extend(super(GurpsRuleset, self).get_sections_in_template())

        # Transitory sections, not used in template:
        #   aim, stunned, shock, posture, check_for_death,
        #   actions_this_turn,

        return sections


    def get_to_hit(self,
                   fighter,     # Fighter object
                   opponent,    # Fighter object
                   weapon
                  ):
        '''
        Returns tuple (skill, why) where:
            'skill' (number) is the value the attacker needs to roll to-hit
                    the target.
            'why'   is an array of strings describing why the to-hit numbers
                    are what they are.
        '''
        # TODO: need convenient defaults -- maybe as an entry to the skill
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

        # Shock

        if fighter.details['shock'] != 0:
            why.append('  %+d due to shock' % fighter.details['shock'])
            skill += fighter.details['shock']

        # Posture

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['attack'] != 0:
            if weapon['type'] == 'melee weapon':
                why.append('  %+d due %s posture' % (
                        posture_mods['attack'], fighter.details['posture']))
                skill += posture_mods['attack']
            else:
                why.append('  NOTE: %s posture doesn\'t matter for ranged' % 
                                                    fighter.details['posture'])
                why.append('    attacks (B551).')

        # Opponent's posture

        if opponent is not None:
            opponent_posture_mods = self.get_posture_mods(
                                                opponent.details['posture'])
            if opponent_posture_mods is not None:
                if weapon['type'] == 'ranged weapon':
                    skill += opponent_posture_mods['target']
                    why.append('  %+d for opponent\'s %s posture' %
                                        (opponent_posture_mods['target'],
                                         opponent.details['posture']))


        why.append('  ...for a to-hit total of %d' % skill)
        return skill, why


    def get_unarmed_info(self,
                         fighter,       # Fighter object
                         opponent,      # Fighter object
                         weapon,        # None or dict.  May be brass knuckles.
                         unarmed_skills # [string, string, ...]
                        ):
        '''
        Makes sense of the cascade of unarmed skills (brawling, boxing,
        karate).
        '''
        # Assumes 'dx' is in unarmed_skills
        result = {
            'punch_skill': fighter.details['current']['dx'],
            'punch_string': 'Punch (DX) (B271, B370)',
            'punch_damage': None,   # String: nd+m

            'kick_skill': 0,
            'kick_string': 'Kick (DX-2) (B271, B370)',
            'kick_damage': None,    # String: nd+m

            'parry_skill': fighter.details['current']['dx'],
            'parry_string': 'Unarmed Parry (B376)',

            'why': []
        }

        # Using separate arrays so that I can print them out in a different
        # order than I calculate them.
        punch_why = []
        punch_damage_why = []
        kick_why = []
        kick_damage_why = []
        parry_why = []

        plus_per_die_of_thrust = 0
        plus_per_die_of_thrust_string = None

        # boxing, brawling, karate, dx
        if ('Brawling' in fighter.details['skills'] and
                                                'Brawling' in unarmed_skills):
            if result['punch_skill'] <= fighter.details['skills']['Brawling']:
                result['punch_string'] = 'Brawling Punch (B182, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['Brawling']
                result['kick_string'] = 'Brawling Kick (B182, B271, B370)'
                # Brawling: @DX+2 = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.details['current']['dx']+2:
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Brawling(%d) @DX(%d)+2 = +1/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
            if result['parry_skill'] <= fighter.details['skills']['Brawling']:
                result['parry_skill'] = fighter.details['skills']['Brawling']
                result['parry_string'] = 'Brawling Parry (B182, B376)'
        if ('karate' in fighter.details['skills'] and
                                                'karate' in unarmed_skills):
            if result['punch_skill'] <= fighter.details['skills']['Karate']:
                result['punch_string'] = 'Karate Punch (B203, B271, B370)'
                result['kick_string'] = 'Karate Kick (B203, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['Karate']
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
            if result['parry_skill'] <= fighter.details['skills']['Karate']:
                result['parry_skill'] = fighter.details['skills']['Karate']
                result['parry_string'] = 'Karate Parry (B203, B376)'

        # (brawling, karate, dx) - 2
        result['kick_skill'] = result['punch_skill'] - 2
        kick_why.append('%s = %s (%d) -2 = to-hit: %d' % (
                                                    result['kick_string'],
                                                    result['punch_string'],
                                                    result['punch_skill'],
                                                    result['kick_skill']))

        if ('boxing' in fighter.details['skills'] and
                                                'boxing' in unarmed_skills):
            # TODO: if skills are equal, boxing should be used in favor of
            # brawling or DX but NOT in favor of karate.  It's placed here
            # because the kick skill isn't improved by boxing.
            if result['punch_skill'] < fighter.details['skills']['Boxing']:
                result['punch_string'] = 'Boxing Punch (B182, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['Boxing']
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
            if result['parry_skill'] < fighter.details['skills']['Boxing']:
                result['parry_skill'] = fighter.details['skills']['Boxing']
                result['parry_string'] = 'Boxing Parry (B182, B376)'

        punch_why.append('%s, to-hit: %d' % (result['punch_string'],
                                             result['punch_skill']))

        # Shock

        if fighter.details['shock'] != 0:
            result['punch_skill'] += fighter.details['shock']
            result['kick_skill'] += fighter.details['shock']

            punch_why.append('  %+d due to shock' % fighter.details['shock'])
            kick_why.append('  %+d due to shock' % fighter.details['shock'])

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

        # Opponent's posture only for ranged attacks -- not used, here

        parry_raw = result['parry_skill']
        parry_damage_modified = False

        # Brawling, Boxing, Karate, DX: Parry int(skill/2) + 3
        result['parry_skill'] = 3 + int(result['parry_skill']/2)
        parry_why.append('%s @ (punch(%d)/2)+3 = %d' % (result['parry_string'],
                                                        parry_raw,
                                                        result['parry_skill']))
        # Stunned
        if fighter.details['stunned']:
            result['parry_skill'] -= 4
            parry_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.details['advantages']:
            parry_damage_modified = True
            result['parry_skill'] += 1
            parry_why.append('  +1 due to combat reflexes (B43)')

        if posture_mods is not None and posture_mods['defense'] != 0:
            result['parry_skill'] += posture_mods['defense']

            parry_why.append('  %+d due to %s posture' % 
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))

        # Final 'why' results

        if parry_damage_modified:
            parry_why.append('  ...for a parry total = %d' %
                                                        result['parry_skill'])
        punch_why.append('  ...for a punch total = %d' % result['punch_skill'])
        kick_why.append('  ...for a kick total = %d' % result['kick_skill'])

        # Damage

        punch_damage = None # Expressed as dice
        kick_damage = None  # Expressed as dice
        st = fighter.details['current']['st']

        # Base damage

        kick_damage_why.append('Kick damage(B271)=thr')

        damage_modified = False
        kick_damage = copy.deepcopy(GurpsRuleset.melee_damage[st]['thr'])
        kick_damage_why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                                            (st,
                                             kick_damage['num_dice'],
                                             kick_damage['plus']))

        # TODO: maybe I want to make everything use damage_array instead of
        # making it a special case for brass knuckles.
        damage_array = None
        if weapon is None:
            punch_damage = copy.deepcopy(GurpsRuleset.melee_damage[st]['thr'])
            punch_damage_why.append('Punch damage(B271) = thr-1')
            punch_damage_why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                                                (st,
                                                 punch_damage['num_dice'],
                                                 punch_damage['plus']))
            punch_damage['plus'] -= 1
            punch_damage_why.append('  -1 (damage is thr-1) = %dd%+d' %
                                                (punch_damage['num_dice'],
                                                 punch_damage['plus']))
        else:
            damage_array, why = self.get_damage(fighter, weapon)
            punch_damage_why.extend(why)

        # Plusses to damage

        if plus_per_die_of_thrust != 0:
            damage_modified = True
            kick_damage['plus'] += (kick_damage['num_dice'] *
                                    plus_per_die_of_thrust)
            kick_damage_why.append('  %+d/die due to %s' % (
                                                plus_per_die_of_thrust,
                                                plus_per_die_of_thrust_string))
            if damage_array is not None:
                for damage in damage_array:
                    if damage['attack_type'] == 'thr':
                        damage['plus'] += (damage['num_dice'] *
                                                 plus_per_die_of_thrust)
            else:
                punch_damage['plus'] += (punch_damage['num_dice'] *
                                         plus_per_die_of_thrust)

            punch_damage_why.append('  %+d/die of thrust due to %s' % (
                                                plus_per_die_of_thrust,
                                                plus_per_die_of_thrust_string))

        # Show the 'why'
        if damage_modified:
            kick_damage_why.append('  ...for a kick damage total = %dd%+d' % (
                                            kick_damage['num_dice'],
                                            kick_damage['plus']))
            if damage_array is not None:
                damage_str = self.damage_to_string(damage_array)
                punch_damage_why.append('  ...for a punch damage total = %s' % 
                                        damage_str)
            else:
                punch_damage_why.append(
                                '  ...for a punch damage total = %dd%+d' % (
                                                punch_damage['num_dice'],
                                                punch_damage['plus']))


        # Assemble final damage and 'why'

        # NOTE: doesn't handle fangs and such which have a damage type of
        # impaling, etc.
        damage_type_str = self.__get_damage_type_str('cr')

        if damage_array is None:
            damage_array = [{
                'attack_type': None,
                'num_dice': punch_damage['num_dice'],
                'plus': punch_damage['plus'],
                'damage_type': damage_type_str
            }]
        result['punch_damage'] = self.damage_to_string(damage_array)

        if kick_damage is not None:
            damage_array = [{
                'attack_type': None,
                'num_dice': kick_damage['num_dice'],
                'plus': kick_damage['plus'],
                'damage_type': damage_type_str
            }]
            result['kick_damage'] = self.damage_to_string(damage_array)

        # Using this order because that's the order the data is shown in the
        # regular window.
        result['why'].extend(parry_why)
        result['why'].extend(punch_why)
        result['why'].extend(punch_damage_why)
        result['why'].extend(kick_why)
        result['why'].extend(kick_damage_why)

        return result


    def get_weapons_unarmed_skills(self,
                                   weapon # None or dict from JSON
                                  ):
        '''
        If this weapon (which may be None) uses the unarmed combat skills.
        That's basically a blackjack or brass knuckles but there may be more.
        Assumes weapon's skill is the most advanced skill supported.

        Returns array of skills supported by this weapon.
        '''

        # Skills in increasing order of difficulty
        all_unarmed_skills = ['dx', 'Brawling', 'Boxing', 'Karate']

        if weapon is None: # No weapon uses unarmed skills by definition
            return all_unarmed_skills

        if weapon['skill'] not in all_unarmed_skills:
            return None

        for i, skill in enumerate(all_unarmed_skills):
            if weapon['skill'] == skill:
                # Returns all of the skills through the matched one
                return all_unarmed_skills[:i+1]

        return None # Camel in Cairo -- should never get here


    def heal_fighter(self,
                     fighter_details    # Details is OK, here
                    ):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        super(GurpsRuleset, self).heal_fighter(fighter_details)
        fighter_details['shock'] = 0
        fighter_details['stunned'] = False
        fighter_details['check_for_death'] = False


    def initiative(self,
                   fighter # Fighter object
                  ):
        return (fighter.details['current']['basic-speed'],
                fighter.details['current']['dx'],
                Ruleset.roll(1, 6)
                )


    def is_creature_consistent(self,
                               name,    # string: creature's name
                               creature # dict from JSON
                              ):
        '''
        Make sure creature has skills for all their stuff.  Trying to make
        sure that one or the other of the skills wasn't entered incorrectly.
        '''
        result = True

        if 'skills' not in creature:
            return result

        unarmed_skills = self.get_weapons_unarmed_skills(None)

        for item in creature['stuff']:
            # NOTE: if the skill is one of the unarmed skills, then the skill
            # defaults to DX and that's OK -- we don't have to tell the user
            # about this.
            if ('skill' in item and
                                item['skill'] not in creature['skills'] and
                                item['skill'] not in unarmed_skills):
                self._window_manager.error([
                    'Creature "%s"' % name,
                    '  has item "%s"' % item['name'],
                    '  that requires skill "%s"' % item['skill'],
                    '  but not the skill to use it'])
                result = False
        return result


    def make_empty_creature(self):
        to_monster = super(GurpsRuleset, self).make_empty_creature()
        to_monster.update({'aim': { 'braced': False, 'rounds': 0 },
                           'skills': { },
                           'shock': 0,
                           'stunned': False,
                           'advantages': { },
                           'actions_this_turn': [],
                           'check_for_death': False,
                           'posture': 'standing'})
        to_monster['permanent'] = copy.deepcopy({'fp': 10, 
                                                 'iq': 10, 
                                                 'hp': 10, 
                                                 'wi': 10, 
                                                 'st': 10, 
                                                 'ht': 10, 
                                                 'dx': 10, 
                                                 'basic-move': 5, 
                                                 'basic-speed': 5, 
                                                 'per': 10})
        to_monster['current'] = copy.deepcopy(to_monster['permanent'])
        return to_monster


    def reset_aim(self,                         # Public to support testing
                  fighter # Fighter object
                 ):
        fighter.details['aim']['rounds'] = 0
        fighter.details['aim']['braced'] = False


    def search_one_creature(self,
                            name,       # string containing the name
                            group,      # string containing the group
                            creature,   # dict describing the creature
                            look_for_re # compiled Python regex
                           ):

        result = super(GurpsRuleset, self).search_one_creature(name,
                                                               group,
                                                               creature,
                                                               look_for_re)

        if 'advantages' in creature:
            for advantage in creature['advantages']:
                if look_for_re.search(advantage):
                    result.append(
                        {'name': name,
                         'group': group,
                         'location': 'advantages',
                         'notes': '%s=%d' % (
                                        advantage,
                                        creature['advantages'][advantage])})

        if 'skills' in creature:
            for skill in creature['skills']:
                if look_for_re.search(skill):
                    result.append(
                            {'name': name,
                             'group': group,
                             'location': 'skills',
                             'notes': '%s=%d' % (skill,
                                                 creature['skills'][skill])})

        return result


    def start_fight(self, fighter):
        '''
        Removes all the ruleset-related stuff from the old fight except injury.
        '''
        fighter.details['shock'] = 0
        fighter.details['stunned'] = False
        fighter.details['check_for_death'] = False
        fighter.details['posture'] = 'standing'
        self.reset_aim(fighter)


    def start_turn(self, fighter):
        fighter.details['actions_this_turn'] = []

        if fighter.is_conscious():
            if fighter.details['current']['fp'] <= 0:
                pass_out_menu = [(('roll <= WILL (%s), or did nothing' %
                                    fighter.details['current']['wi']), True),
                                 ('did NOT make WILL roll', False)]
                made_will_roll = self._window_manager.menu(
                                    'On Action: roll <= WILL or pass out',
                                    pass_out_menu)
                if not made_will_roll:
                    fighter.details['state'] = 'unconscious'

        # B327 -- immediate check for death
        if fighter.is_conscious() and fighter.details['check_for_death']:
            dead_menu = [
                (('roll <= HT (%d)' % fighter.details['current']['ht']), True),
                ('did NOT make HT roll', False)]
            made_ht_roll = self._window_manager.menu(
                ('%s: roll <= HT or DIE (B327)' % fighter.name), 
                 dead_menu)

            if not made_ht_roll:
                fighter.details['state'] = 'dead'

            fighter.details['check_for_death'] = False  # Only show/roll once

        # B327 -- checking on each round whether the fighter is still
        # conscious

        if fighter.is_conscious() and fighter.details['current']['hp'] <= 0:
            pass_out_menu = [('made HT roll', True),
                             ('did NOT make HT roll', False)]

            if 'High Pain Threshold' in fighter.details['advantages']:
                unconscious_roll = fighter.details['current']['ht'] + 3

                made_ht_roll = self._window_manager.menu(
                    ('%s: HP < 0: roll <= HT+3 (%d) or pass out (B327,B59)' %
                        (fighter.name, unconscious_roll)),
                     pass_out_menu)

                if not made_ht_roll:
                    fighter.details['state'] = 'unconscious'
            else:
                made_ht_roll = self._window_manager.menu(
                    ('%s: HP < 0: roll <= HT (%d) or pass out (B327)' %
                        (fighter.name, fighter.details['current']['ht'])),
                     pass_out_menu)

                if not made_ht_roll:
                    fighter.details['state'] = 'unconscious'


    #
    # Protected and Private Methods
    #

    def _adjust_hp(self,
                   fighter,  # Fighter object
                   adj       # the number of HP to gain or lose
                  ):
        if adj < 0:
            # Hit location (just for flavor, not for special injury)
            table_lookup = (random.randint(1,6) +
                            random.randint(1,6) +
                            random.randint(1,6))
            hit_location = GurpsRuleset.hit_location_table[table_lookup]

            window_text = [
                [{'text': ('...%s\'s %s' % (fighter.name, hit_location)),
                  'mode': curses.A_NORMAL}]
                           ]

            # Adjust for armor
            dr = 0
            dr_text_array = []
            use_armor = False
            armor, armor_index = fighter.get_current_armor()
            if armor is not None:
                dr += armor['dr']
                dr_text_array.append(armor['name'])

            if 'Damage Resistance' in fighter.details['advantages']:
                # GURPS rules, B46, 5 points per level of DR advantage
                dr += (fighter.details['advantages']['Damage Resistance']/5)
                dr_text_array.append('DR Advantage')

            if dr != 0:
                use_armor_menu = [('yes', True), ('no', False)]
                use_armor = self._window_manager.menu('Use Armor\'s DR?',
                                                                use_armor_menu)
            if use_armor:
                if dr >= -adj:
                    window_text = [
                        [{'text': 'The armor absorbed all the damage',
                          'mode': curses.A_NORMAL}]
                    ]
                    self._window_manager.display_window(
                                    ('Did *NO* damage to %s' % fighter.name),
                                    window_text)
                    return

                original_adj = adj
                adj += dr
                dr_text = '; '.join(dr_text_array)
                window_text.append([{'text':'', 'mode': curses.A_NORMAL}])
                window_text.append(
                    [{'text': ('%s was wearing %s (total dr:%d)' % (
                                                              fighter.name,
                                                              dr_text,
                                                              dr)),
                      'mode': curses.A_NORMAL}]
                                  )
                window_text.append(
                    [{'text': ('so adj(%d) - dr(%d) = damage (%d)' % (
                                                              -original_adj,
                                                              dr,
                                                              -adj)),
                      'mode': curses.A_NORMAL}]
                                  )

            self._window_manager.display_window(
                                    ('Did %d hp damage to...' % -adj),
                                    window_text)



            # Check for Death (B327)
            adjusted_hp = fighter.details['current']['hp'] + adj

            if adjusted_hp <= -(5 * fighter.details['permanent']['hp']):
                fighter.details['state'] = 'dead'
            else:
                threshold = -fighter.details['permanent']['hp']
                while fighter.details['current']['hp'] <= threshold:
                    threshold -= fighter.details['permanent']['hp']
                if adjusted_hp <= threshold:
                    fighter.details['check_for_death'] = True

            # Check for Major Injury (B420)
            if -adj > (fighter.details['permanent']['hp'] / 2):
                (SUCCESS, SIMPLE_FAIL, BAD_FAIL) = range(3)
                total = fighter.details['current']['ht']
                if 'High Pain Threshold' in fighter.details['advantages']:
                    total = fighter.details['current']['ht'] + 3
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT+3 (%d) or be stunned' %
                                                                        total)
                elif 'Low Pain Threshold' in fighter.details['advantages']:
                    total = fighter.details['current']['ht'] - 4
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT-4 (%d) or be stunned' %
                                                                        total)
                else:
                    total = fighter.details['current']['ht']
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT (%d) or be stunned' % 
                                                                        total)

                stunned_menu = [('Succeeded (roll <= HT (%d))' % total,
                                 GurpsRuleset.MAJOR_WOUND_SUCCESS),
                                ('Missed roll by < 5 (roll < %d)' % (total+5),
                                 GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL),
                                ('Missed roll by >= 5 (roll >= %d)' % (total+5),
                                 GurpsRuleset.MAJOR_WOUND_BAD_FAIL),
                               ]
                stunned_results = self._window_manager.menu(menu_title,
                                                            stunned_menu)
                if stunned_results == GurpsRuleset.MAJOR_WOUND_BAD_FAIL:
                    fighter.details['state'] = 'unconscious'
                    fighter.draw_weapon_by_index(None)
                elif stunned_results == GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL:
                    self._change_posture({'fighter': fighter,
                                          'posture': 'lying'})
                    fighter.draw_weapon_by_index(None)
                    fighter.details['stunned'] = True

        if 'High Pain Threshold' not in fighter.details['advantages']: # B59
            # Shock (B419) is cumulative but only to a maximum of -4
            fighter.details['shock'] += adj    # 'shock' is negative
            if fighter.details['shock'] < -4:
                fighter.details['shock'] = -4

        # WILL roll or lose aim
        if fighter.details['aim']['rounds'] > 0:
            aim_menu = [('made WILL roll', True),
                        ('did NOT make WILL roll', False)]
            made_will_roll = self._window_manager.menu(
                ('roll <= WILL (%d) or lose aim' %
                                            fighter.details['current']['wi']),
                aim_menu)
            if not made_will_roll:
                self.reset_aim(fighter)

        super(GurpsRuleset, self)._adjust_hp(fighter, adj)


    def _cast_spell(self,
                    param, # dict {'fighter': <Fighter object>,
                           #       'spell': <index in 'spells'>,
                           #       'fight_handler': <FightHandler object>}
                   ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''

        fighter = param['fighter']
        spell_index = param['spell']
        spell = fighter.details['spells'][spell_index]

        if spell['name'] not in GurpsRuleset.spells:
            self._window_manager.error(
                ['Spell "%s" not in GurpsRuleset.spells' % spell['name']]
            )
            return True
        complete_spell = copy.deepcopy(spell)
        complete_spell.update(GurpsRuleset.spells[spell['name']])

        # Cost

        if complete_spell['cost'] is None:
            title = 'Cost to cast (%s) - see (%s) ' % (complete_spell['name'],
                                                       complete_spell['notes'])
            height = 1
            width = len(title)
            cost_string = ''
            while len(cost_string) <= 0:
                cost_string = self._window_manager.input_box(height,
                                                             width,
                                                             title)
            cost = int(cost_string)
        else:
            cost = complete_spell['cost']

        # Casting time

        if (complete_spell['casting time'] is None or
                                        complete_spell['casting time'] == 0):
            title = 'Seconds to cast (%s) - see (%s) ' % (
                                                    complete_spell['name'],
                                                    complete_spell['notes'])
            height = 1
            width = len(title)
            casting_time_string = ''
            while len(casting_time_string) <= 0:
                casting_time_string = self._window_manager.input_box(height,
                                                                     width,
                                                                     title)
            casting_time = int(casting_time_string)
        else:
            casting_time = complete_spell['casting time']


        # M8 - High skill level costs less
        skill = complete_spell['skill'] - 15
        while skill >= 0:
            cost -= 1
            skill -= 5
        if cost < 0:
            cost = 0

        fighter.details['current']['fp'] -= cost

        timer = Timer(None)
        casting_time -= 0.1 # -0.1 so that it doesn't show up on the first
                            # round you can do something after you cast
        timer.from_pieces(fighter.name,
                          casting_time,
                          'Casting (%s) @ skill (%d): %s' % (
                                                    complete_spell['name'],
                                                    complete_spell['skill'],
                                                    complete_spell['notes']))
        timer.mark_owner_as_busy()  # When casting, the owner is busy
        fighter.timers.add(timer)

        # If the spell lasts any time at all, put a timer up so that we see
        # that it's active
        if (complete_spell['duration'] is not None and
                                            complete_spell['duration'] > 1):
            duration_timer = Timer(None)
            duration_timer.from_pieces(
                                fighter.name,
                                complete_spell['duration'],
                                'SPELL ACTIVE: %s' % complete_spell['name'])
            timer.details['actions']['timer'] = duration_timer.details

            # Opponent?

            opponent = None
            if 'fight_handler' in param and param['fight_handler'] is not None:
                fight_handler = param['fight_handler']
                opponent = fight_handler.get_opponent_for(fighter)

            if opponent is not None:
                opponent_timer_menu = [('yes', True), ('no', False)]
                timer_for_opponent = self._window_manager.menu(
                                    ('Mark %s with spell' % opponent.name),
                                    opponent_timer_menu)
                if not timer_for_opponent:
                    opponent = None

            if opponent:
                delay_timer = Timer(None)
                delay_timer.from_pieces(
                        opponent.name,
                        casting_time,
                        ('Waiting for "%s" spell to take affect' %
                                                    complete_spell['name']))

                spell_timer = Timer(None)
                spell_timer.from_pieces(
                        opponent.name,
                        complete_spell['duration'],
                        'SPELL "%s" AGAINST ME' % complete_spell['name'])
                delay_timer.details['actions']['timer'] = spell_timer.details
                opponent.timers.add(delay_timer)

        return None if 'text' not in param else param


    def _change_posture(self,
                        param, # dict {'fighter': <Fighter object>,
                               #       'posture': <string=new posture>}
                       ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        param['fighter'].details['posture'] = param['posture']
        self.reset_aim(param['fighter'])
        return None if 'text' not in param else param


    def __damage_FP(self,
                    param    # {'view': xxx, 'view-opponent': xxx,
                             #  'current': xxx, 'current-opponent': xxx,
                             #  'fight_handler': <fight handler> } where
                             # xxx are Fighter objects
                   ):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if param is None:
            return True
        elif param['view'] is not None:
            fp_recipient = param['view']
        elif param['current-opponent'] is not None:
            fp_recipient = param['current-opponent']
        elif param['current'] is not None:
            fp_recipient = param['current']
        else:
            return True

        title = 'Reduce (%s\'s) FP By...' % fp_recipient.name
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        if len(adj_string) <= 0:
            return True
        adj = -int(adj_string)  # NOTE: SUBTRACTING the adjustment

        if adj < 0:
            comment = '(%s) lost %d FP' % (fp_recipient.name, -adj)
        else:
            comment = '(%s) regained %d FP' % (fp_recipient.name, adj)
        action = {'name': 'adjust-fp', 'adj': adj, 'comment': comment}

        fight_handler = (None if 'fight_handler' not in param
                                                else param['fight_handler'])
        self.do_action(fp_recipient, action, fight_handler)

        return True # Keep going


    def _do_adjust_fp(self,
                      fighter,  # Fighter object
                      adj       # number: amount to adjust FP
                     ):
        # If FP go below zero, you lose HP along with FP
        hp_adj = 0
        if adj < 0  and -adj > fighter.details['current']['fp']:
            hp_adj = adj
            if fighter.details['current']['fp'] > 0:
                hp_adj += fighter.details['current']['fp']

        fighter.details['current']['hp'] += hp_adj
        fighter.details['current']['fp'] += adj
        return


    def _do_aim(self,
                param, # dict {'fighter': <Fighter object>,
                       #       'braced': True | False}
               ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''

        if param['fighter'].details['opponent'] is None:
            param['fight_handler'].pick_opponent()

        rounds = param['fighter'].details['aim']['rounds']
        if rounds == 0:
            param['fighter'].details['aim']['braced'] = param['braced']
            param['fighter'].details['aim']['rounds'] = 1
        elif rounds < 3:
            param['fighter'].details['aim']['rounds'] += 1

        return


    def _do_attack(self,
                   param # {'fighter': xxx, Fighter object for attacker
                         #  'fight_handler', ...
                  ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        to_monster = super(GurpsRuleset, self)._do_attack(param)
        self.reset_aim(param['fighter'])
        return


    def _do_defense(self,
                    param # {'fighter': <Fighter object>, ...
                   ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        self.reset_aim(param['fighter'])
        return None if 'text' not in param else param


    def _do_reload(self,
                   param # {'fighter': Fighter object for attacker
                  ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        if super(GurpsRuleset, self)._do_reload(param):
            weapon, weapon_index = param['fighter'].get_current_weapon()
            if weapon is None or 'ammo' not in weapon:
                return False

            reload_time = weapon['reload']
            if 'fast-draw (ammo)' in param['fighter'].details['skills']:
                reload_time -= 1
            timer = Timer(None)
            timer.from_pieces(param['fighter'].name, reload_time, 'RELOADING')
            timer.mark_owner_as_busy()  # When reloading, the owner is busy
            param['fighter'].timers.add(timer)

            self.reset_aim(param['fighter'])
            return True

        return


    def _draw_weapon(self,
                    param # dict: {'weapon': index, 'fighter': Fighter obj}
                   ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        super(GurpsRuleset, self)._draw_weapon(param)
        self.reset_aim(param['fighter'])
        return


    def __get_damage_type_str(self,
                              damage_type
                             ):
        if damage_type in GurpsRuleset.damage_mult:
            damage_type_str = '%s=x%.1f' % (
                                        damage_type,
                                        GurpsRuleset.damage_mult[damage_type])
        else:
            damage_type_str = '%s' % damage_type
        return damage_type_str


    def __stun(self,
               param    # {'view': xxx, 'view-opponent': xxx,
                        #  'current': xxx, 'current-opponent': xxx,
                        #  'fight_handler': <fight handler> } where
                        # xxx are Fighter objects
              ):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if param is None:
            return True
        elif param['view'] is not None:
            stunned_dude = param['view']
        elif param['current-opponent'] is not None:
            stunned_dude = param['current-opponent']
        elif param['current'] is not None:
            stunned_dude = param['current']
        else:
            return True

        action = {'name': 'stun',
                  'comment': ('(%s) got stunned' % stunned_dude.name)}
        fight_handler = (None if 'fight_handler' not in param
                                                else param['fight_handler'])
        self.do_action(stunned_dude, action, fight_handler)

        return True # Keep going


class ScreenHandler(object):
    '''
    Base class for the "business logic" backing the user interface.
    '''

    maintainjson = False

    def __init__(self,
                 window_manager,
                 campaign_debug_json,
                 filename,
                 saved_fight):
        self._window_manager = window_manager
        self._campaign_debug_json = campaign_debug_json
        self._input_filename = filename
        self._saved_fight = saved_fight

        self._choices = {
            ord('B'): {'name': 'Bug Report', 'func': self._make_bug_report},
        }


    def add_to_history(self,
                       action # {'name':xxx, ...} - see Ruleset::do_action()
                      ):
        self._saved_fight['history'].append(action)


    def clear_history(self):
        self._saved_fight['history'] = []


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
            else:
                self._window_manager.error(
                                    ['Invalid command: "%c" ' % chr(string)])

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
            'history' : self._saved_fight['history'],
            'report'  : report
        }

        bug_report_json = timeStamped('bug_report', None, 'txt')
        with open(bug_report_json, 'w') as f:
            json.dump(bug_report, f, indent=2)

        return True # Keep doing whatever you were doing.


class BuildFightHandler(ScreenHandler):
    (NPCs,
     PCs,
     MONSTERs) = range(3)

    def __init__(self,
                 window_manager,
                 world,
                 ruleset,
                 creature_type, # one of: NPCs, PCs, or MONSTERs
                 campaign_debug_json,
                 filename # JSON file containing the world
                ):
        super(BuildFightHandler, self).__init__(
                                            window_manager,
                                            campaign_debug_json,
                                            filename,
                                            world.details['current-fight'])
        self._add_to_choice_dict({
            curses.KEY_UP:
                      {'name': 'prev character',  'func': self.__view_prev},
            curses.KEY_DOWN:
                      {'name': 'next character',  'func': self.__view_next},
            ord('a'): {'name': 'add creature',    'func': self.__add_creature},
            ord('d'): {'name': 'delete creature', 'func':
                                                    self.__delete_creature},
            ord('g'): {'name': 'new group',       'func': self.__new_group},
            ord('G'): {'name': 'existing group',  'func':
                                                    self.__existing_group},
            ord('t'): {'name': 'change template', 'func': self.__new_template},
            ord('T'): {'name': 'make template',   'func': self.__make_template},
            ord('q'): {'name': 'quit',            'func': self.__quit},
        })
        self._window = self._window_manager.get_build_fight_gm_window()

        self.__world = world
        self.__ruleset = ruleset
        self.__template_name = None # Name of templates we'll use to create
                                    # new creatures.

        self.__critters = None # dict of parallel arrays:
                               #    {'data': <dict from json>,
                               #     'obj': array of <Fighter> obj or <Fight>
                               #        obj in display order}

        self.__deleted_critter_count = 0
        self.__equipment_manager = EquipmentManager(world, window_manager)

        self.__new_char_name = None
        self.__viewing_index = None # integer index into self.__critters

        if creature_type == BuildFightHandler.NPCs:
            self.__group_name = 'NPCs'
            self.__existing_group(creature_type)
        elif creature_type == BuildFightHandler.PCs:
            self.__group_name = 'PCs'
            self.__existing_group(creature_type)
        else: # creature_type == BuildFightHandler.MONSTERs:
            self.__group_name = None    # The name of the monsters or 'PCs'
                                        # that will ultimately take these
                                        # creatures.

            new_existing_menu = [('new monster group', 'new'),
                                 ('existing monster group', 'existing')]
            new_existing = None
            while new_existing is None:
                new_existing = self._window_manager.menu('New or Pre-Existing',
                                                          new_existing_menu)
            if new_existing == 'new':
                self.__new_group()
            else:
                self.__existing_group(creature_type)

        if self.__critters is None:
            return

        self._draw_screen()
        self.__add_creature()
        return

    #
    # Public Methods
    #

    def change_viewing_index(self,              # Public to support testing.
                             adj  # integer adjustment to viewing index
                            ):
        '''
        NOTE: this breaks if |adj| is > len(self.__critters['data'])
        '''

        len_list = len(self.__critters['data'])
        if len_list == 0:
            return

        if self.__viewing_index is None:
            # autoselect last added creature
            self.__viewing_index = len_list - 1

        self.__viewing_index += adj

        if self.__viewing_index >= len_list:
            self.__viewing_index = 0

        elif self.__viewing_index < 0:
            self.__viewing_index = len_list - 1


    def get_group_name(self):
        return self.__group_name


    #
    # Protected Methods
    #

    def _draw_screen(self):
        self._window.clear()
        self._window.status_ribbon(self.__group_name,
                                   self.__template_name,
                                   self._input_filename,
                                   ScreenHandler.maintainjson)
        self._window.command_ribbon(self._choices)
        # BuildFightGmWindow
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        if (self.__new_char_name is not None and
                            self.__new_char_name in self.__critters['data']):
            critter = self.__get_fighter_object_from_name(self.__new_char_name)
            self._window.show_description(critter)

    #
    # Private Methods
    #

    def __add_creature(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # A little error checking

        self.__viewing_index = None
        if self.__group_name is None:
            self._window_manager.error(
                ['You must select a new or existing group to which to',
                 'add this creature.'])
            return True # Keep going

        # Add as many creatures as we want

        keep_adding_creatures = True
        while keep_adding_creatures:

            # Get a template
            if self.__template_name is None:
                self.__new_template()

            # TODO: allow just a blank creature made by:
            # to_creature = self.__ruleset.make_empty_creature()

            # Based on which creature from the template
            creature_menu = [(from_creature_name, from_creature_name)
                for from_creature_name in
                        self.__world.details['Templates'][self.__template_name]]
            creature_menu = sorted(creature_menu, key=lambda x: x[0].upper())

            from_creature_name = self._window_manager.menu('Monster',
                                                           creature_menu)
            # TODO: maybe not
            if from_creature_name is None:
                return True # Keep going

            # Generate the creature for the template

            from_creature = (self.__world.details[
                        'Templates'][self.__template_name][from_creature_name])
            to_creature = self.__ruleset.make_empty_creature()

            for key, value in from_creature.iteritems():
                if key == 'permanent':
                    for ikey, ivalue in value.iteritems():
                        to_creature['permanent'][ikey] = (
                            self.__get_value_from_template(ivalue,
                                                           from_creature))
                        to_creature['current'][ikey] = to_creature[
                                                            'permanent'][ikey]
                else:
                    to_creature[key] = self.__get_value_from_template(
                                                        value, from_creature)

            # Get the new creature name

            keep_asking = True
            lines, cols = self._window.getmaxyx()

            # We're not filling in the holes if we delete a monster, we're
            #   just adding to the total of monsters created
            # NOTE: this is still imperfect.  If you delete a monster and then
            #   come back later, you'll still have numbering problems.
            # ALSO NOTE: we use 'len' rather than 'len'+1 because we've added
            #   a Fight to the list -- the Fight has an implied prefix of '0'
            creature_num = (len(self.__critters['data']) +
                                                self.__deleted_critter_count)
            while keep_asking:
                base_name = self._window_manager.input_box(1,      # height
                                                           cols-4, # width
                                                           'Monster Name')
                if base_name is None or len(base_name) == 0:
                    base_name, where, gender = self.__world.get_random_name()
                    if base_name is None:
                        self._window_manager.error(['Monster needs a name'])
                        keep_asking = True
                    else:
                        if where is not None:
                            to_creature['notes'].append('origin: %s' % where)
                        if gender is not None:
                            to_creature['notes'].append('gender: %s' % gender)

                if self.__group_name == 'NPCs' or self.__group_name == 'PCs':
                    creature_name = base_name
                else:
                    creature_name = '%d - %s' % (creature_num, base_name)

                if creature_name in self.__critters['data']:
                    self._window_manager.error(
                        ['Monster "%s" already exists' % creature_name])
                    keep_asking = True
                else:
                    keep_asking = False

            # Add personality stuff to notes
        
            if self.__group_name != 'PCs':
                with GmJson('npc_detail.json') as npc_detail:
                    for name, traits in npc_detail.read_data['traits'].iteritems():
                        trait = random.choice(traits)
                        if isinstance(trait, dict):
                            trait_array = [trait['text']]
                            for key in trait:
                                if key in npc_detail.read_data['support']:
                                    trait_array.append('%s: %s' %
                                        (key, 
                                         random.choice(
                                            npc_detail.read_data['support'][key])))
                            trait = ', '.join(trait_array)

                        to_creature['notes'].append('%s: %s' % (name, trait))

            # Modify the creature we just created

            keep_changing_this_creature = True

            while keep_changing_this_creature:
                # Creating a temporary list to show.  Add the new creature by
                # its current creature name and allow the name to be modified.
                # Once the creature name is sorted, we can add it to the
                # permanent list.  That simplifies the cleanup (since the
                # lists are dictionaries, indexed by creature name).

                # Note: we're not going to touch the objects in temp_list so
                # it's OK that this is just copying references.
                temp_list = [x for x in self.__critters['obj']]
                temp_list.append(Fighter(creature_name,
                                         self.__group_name,
                                         to_creature,
                                         self.__ruleset,
                                         self._window_manager))
                self.__new_char_name = creature_name
                # BuildFightGmWindow
                self._window.show_creatures(temp_list,
                                            self.__new_char_name,
                                            self.__viewing_index)

                action_menu = [('append to name', 'append'),
                               ('notes', 'notes'),
                               ('continue (add another creature)', 'continue'),
                               ('quit', 'quit')]

                action = self._window_manager.menu('What Next',
                                                   action_menu,
                                                   2) # start on 'continue'
                if action == 'append':
                    more_text = self._window_manager.input_box(1, # height
                                                               cols-4, # width
                                                               'Add to Name')
                    temp_creature_name = '%s - %s' % (creature_name,
                                                     more_text)
                    if temp_creature_name in self.__critters['data']:
                        self._window_manager.error(
                                            ['Monster "%s" already exists' %
                                                temp_creature_name])
                    else:
                        creature_name = temp_creature_name
                elif action == 'notes':
                    if 'notes' not in to_creature:
                        notes = None
                    else:
                        notes = '\n'.join(to_creature['notes'])
                    notes = self._window_manager.edit_window(
                                lines - 4,
                                cols/2,
                                notes,  # initial string (w/ \n) for the window
                                'Notes',
                                '^G to exit')
                    to_creature['notes'] = [x for x in notes.split('\n')]

                elif action == 'continue':
                    keep_changing_this_creature = False

                elif action == 'quit':
                    keep_changing_this_creature = False
                    keep_adding_creatures = False

            # Add our new creature to its group and show it to the world.

            self.__critters['data'][creature_name] = to_creature
            self.__critters['obj'].append(Fighter(creature_name,
                                                  self.__group_name,
                                                  to_creature,
                                                  self.__ruleset,
                                                  self._window_manager))
            # BuildFightGmWindow
            self._window.show_creatures(self.__critters['obj'],
                                        self.__new_char_name,
                                        self.__viewing_index)

        return True # Keep going


    def __delete_creature(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__viewing_index is None:
            # Auto-select the most recently added new creature
            name_to_delete = self.__new_char_name

        else:
            name_to_delete, ignore_body = self.__name_and_obj_from_index(
                                                        self.__viewing_index)

        if name_to_delete is None:
            return True

        critter_menu = [('yes', 'yes'), ('no', 'no')]
        answer = self._window_manager.menu(
                                'Delete "%s" ARE YOU SURE?' % name_to_delete,
                                critter_menu,
                                1) # Choose 'No' by default

        if answer is not None and answer == 'yes':
            found = False
            for index, obj in enumerate(self.__critters['obj']):
                if obj.name == name_to_delete:
                    del(self.__critters['obj'][index])
                    found = True
                    break
            if not found:
                self._window_manager.error(
                    ['Deleting monster "%s" who is not in object list' %
                                                            name_to_delete])
            self.__new_char_name = None
            del(self.__critters['data'][name_to_delete])
            self.__deleted_critter_count += 1

        self.__viewing_index = None
        # BuildFightGmWindow
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)

        return True # Keep going


    def __existing_group(self,
                         creature_type # BuildFightHandler.NPCs, ...
                        ):

        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Get the template name

        lines, cols = self._window.getmaxyx()
        template_menu = [(template_name, template_name)
                    for template_name in self.__world.details['Templates']]
        template_name = self._window_manager.menu('From Which Template',
                                                         template_menu)
        if template_name is None:
            return True  # Keep going
        self.__template_name = template_name

        # Get the group information

        if creature_type == BuildFightHandler.MONSTERs:
            group_menu = [(group_name, group_name)
                            for group_name in self.__world.get_fights()]
            group_menu = sorted(group_menu, key=lambda x: x[0].upper())
            group_answer = self._window_manager.menu('To Which Group',
                                                     group_menu)

        elif creature_type == BuildFightHandler.NPCs:
            group_answer = 'NPCs'

        elif creature_type == BuildFightHandler.PCs:
            group_answer = 'PCs'

        if group_answer is None:
            return True # Keep going

        # Set the name and group of the new group

        self.__group_name = group_answer
        self.__critters = {
                    'data': self.__world.get_creatures(self.__group_name),
                    'obj': []}

        # Build the Fighter object array

        the_fight_itself = None
        for name, details in self.__critters['data'].iteritems():
            if name == Fight.name:
                the_fight_itself = details
            else:
                fighter = Fighter(
                            name,
                            self.__group_name,
                            # Calls 'get_creature_details' in case 'details'
                            # is a redirect.
                            self.__world.get_creature_details(
                                                    name, self.__group_name),
                            self.__ruleset,
                            self._window_manager)
                self.__critters['obj'].append(fighter)

        self.__critters['obj'] = sorted(self.__critters['obj'],
                                        key=lambda x: x.name)

        # Add the Fight to the object array (but only for monsters).

        if creature_type == BuildFightHandler.MONSTERs:
            if the_fight_itself is None:
                self.__critters['data'][Fight.name] = Fight.empty_fight
                fight = Fight(self.__group_name,
                              self.__world.details['fights'][self.__group_name],
                              self.__ruleset,
                              self._window_manager)
            else:
                fight = Fight(self.__group_name,
                              the_fight_itself,
                              self.__ruleset,
                              self._window_manager)

            self.__critters['obj'].insert(0, fight)

        # Display our new state

        self._draw_screen()

        return True # Keep going


    def __get_fighter_object_from_name(self,
                                       name # string name of critter
                                      ):
        for critter in self.__critters['obj']:
            if critter.name == name:
                return critter
        return None


    def __get_value_from_template(self,
                                  template_value,
                                  template
                                 ):
        if template_value['type'] == 'value':
            return template_value['value']

        # TODO(eventually, maybe):
        #   {'type': 'ask-string', 'value': x}
        #   {'type': 'ask-numeric', 'value': x}
        #   {'type': 'ask-logical', 'value': x}
        #   {'type': 'dice', 'value': 'ndm+x'}
        #   {'type': 'derived', 'value': comlicated bunch of crap -- eventually}

        return None


    def __name_and_obj_from_index(self,
                                  index, # index into self.__critters['obj']
                                 ):
        if index is None:
            return None, None

        fighter = self.__critters['obj'][index]

        return fighter.name, fighter


    def __new_group(self):
        '''
        Command ribbon method.

        Creates new group of monsters.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Get the template info.

        lines, cols = self._window.getmaxyx()
        template_menu = [(template_name, template_name)
                    for template_name in self.__world.details['Templates']]
        template_name = self._window_manager.menu('From Which Template',
                                                         template_menu)
        if template_name is None:
            return True  # Keep going
        self.__template_name = template_name

        # Get the new group info.

        keep_asking = True
        group_name = None
        while keep_asking:
            group_name = self._window_manager.input_box(1,      # height
                                                        cols-4, # width
                                                        'New Fight Name')
            if group_name is None or len(group_name) == 0:
                self._window_manager.error(['You have to name your fight'])
                keep_asking = True
            elif self.__world.get_creatures(group_name) is not None:
                self._window_manager.error(
                    ['Fight name "%s" already exists' % group_name])
                keep_asking = True
            else:
                keep_asking = False

        # Set the name and group of the new group

        self.__group_name = group_name
        fights = self.__world.get_fights() # New groups can
                                           # only be in fights.

        fights[group_name] = {'monsters': {}}

        self.__critters = {'data': fights[self.__group_name]['monsters'],
                           'obj': []}


        self.__critters['data'][Fight.name] = Fight.empty_fight
        fight = Fight(self.__group_name,
                      self.__world.details['fights'][self.__group_name],
                      self.__ruleset,
                      self._window_manager)
        self.__critters['obj'].insert(0, fight)

        # Display our new state

        self._draw_screen()

        return True # Keep going


    def __make_template(self):
        '''
        Creates a template from a creature.  Puts it in the same section.
        '''

        # A little error checking

        if self.__template_name is None:
            self._window_manager.error(
                ['You must select a template list to which to',
                 'add this template.'])
            return True # Keep going

        if self.__viewing_index is None:
            return True # Keep going

        ignore_name, from_creature  = self.__name_and_obj_from_index(
                                                        self.__viewing_index)
        if from_creature.name == Fight.name:
            self._window_manager.error(['Can\'t make a template from a room'])
            return True # Keep going

        # Get the name of the new template

        lines, cols = self._window.getmaxyx()
        keep_asking = True
        template_name = None
        while keep_asking:
            template_name = self._window_manager.input_box(1,      # height
                                                           cols-4, # width
                                                           'New Template Name')
            if template_name is None or len(template_name) == 0:
                return True
            elif (template_name in
                    self.__world.details['Templates'][self.__template_name]):
                self._window_manager.error(
                    ['Template name "%s" already exists' % template_name])
                keep_asking = True
            else:
                keep_asking = False

        # Copy current creature into the template

        to_creature = {}
        allowable_section_names = self.__ruleset.get_sections_in_template()

        for section_name, section_body in from_creature.details.iteritems():
            if section_name == 'permanent':
                to_creature['permanent'] = {}
                for stat_name, stat_body in section_body.iteritems():
                    to_creature['permanent'][stat_name] = {
                                                    'type': 'value',
                                                    'value': stat_body}
            elif section_name in allowable_section_names:
                to_creature[section_name] = {'type': 'value',
                                             'value': section_body}
            else:
                pass # We're ignoring these

        template_list = self.__world.details['Templates'][self.__template_name]
        template_list[template_name] = to_creature
        return True # Keep going


    def __new_template(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Get the new group info.

        # Get the template
        lines, cols = self._window.getmaxyx()
        template_menu = [(template_name, template_name)
                    for template_name in self.__world.details['Templates']]
        template_name = self._window_manager.menu('From Which Template',
                                                  template_menu)
        if template_name is None:
            return True  # Keep going
        self.__template_name = template_name

        # Display our new state

        self._draw_screen()

        return True # Keep going


    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        for name, creature in self.__critters['data'].iteritems():
            self.__ruleset.is_creature_consistent(name, creature)

        # TODO: do I need to del self._window?
        self._window.close()
        return False # Stop building this fight


    def __view_prev(self): # look at previous character
        self.change_viewing_index(-1)
        # BuildFightGmWindow
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        return True # Keep going


    def __view_next(self): # look at next character
        self.change_viewing_index(1)
        # BuildFightGmWindow
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        return True # Keep going



class FightHandler(ScreenHandler):
    def __init__(self,
                 window_manager,
                 world,
                 monster_group,
                 ruleset,
                 campaign_debug_json,   # TODO: we can get this from 'world'
                 filename # JSON file containing the world
                ):
        super(FightHandler, self).__init__(window_manager,
                                           campaign_debug_json,
                                           filename,
                                           world.details['current-fight'])
        self._window = self._window_manager.get_fight_gm_window(ruleset)
        self.__ruleset = ruleset
        self.__bodies_looted = False
        self.__keep_monsters = False # Move monsters to 'dead' after fight
        self.__equipment_manager = EquipmentManager(world,
                                                    self._window_manager)

        self._add_to_choice_dict({
            curses.KEY_UP:
                      {'name': 'prev character',
                                              'func': self.__view_prev},
            curses.KEY_DOWN:
                      {'name': 'next character',
                                              'func': self.__view_next},
            curses.KEY_HOME:
                      {'name': 'current character',
                                              'func': self.__view_init},

            ord(' '): {'name': 'next fighter','func': self.__next_fighter},
            ord('<'): {'name': 'prev fighter','func': self.__prev_fighter},
            ord('?'): {'name': 'explain',     'func': self.__show_why},
            ord('d'): {'name': 'defend',      'func': self.__defend},
            ord('D'): {'name': 'dead/unconscious',
                                              'func': self.__dead},
            ord('g'): {'name': 'give equip',  'func': self.__give_equipment},
            ord('h'): {'name': 'History',     'func': self.__show_history},
            ord('i'): {'name': 'character info',
                                              'func': self.__show_info},
            ord('k'): {'name': 'keep monsters',
                                              'func': self.__do_keep_monsters},
            ord('-'): {'name': 'HP damage',   'func': self.__damage_HP},
            #ord('L'): {'name': 'Loot bodies', 'func': self.__loot_bodies},
            ord('m'): {'name': 'maneuver',    'func': self.__maneuver},
            ord('n'): {'name': 'short notes', 'func': self.__short_notes},
            ord('N'): {'name': 'full Notes',  'func': self.__full_notes},
            ord('o'): {'name': 'opponent',    'func': self.pick_opponent},
            ord('P'): {'name': 'promote to NPC',
                                              'func': self.promote_to_NPC},
            ord('q'): {'name': 'quit',        'func': self.__quit},
            ord('s'): {'name': 'save',        'func': self.__save},
            ord('t'): {'name': 'timer',       'func': self.__timer},
            ord('T'): {'name': 'Timer cancel','func': self.__timer_cancel},
        })

        self._add_to_choice_dict( self.__ruleset.get_fight_commands(self) )

        self.__world = world
        self.__viewing_index = None

        # self._saved_fight takes the form:
        # {
        #   'index': <number>  # current fighter that has the initiative
        #   'fighters': [ {'group': <group>,
        #                  'name': <name>}, ... # fighters in initiative order
        #   'saved': True | False
        #   'round': <number>  # round of the fight
        #   'monsters': <name> # group name of the monsters in the fight
        # }

        # TODO: keep the fighter objects for the PCs and NPCs in the World
        #   object .

        # Do the debug file snapshot before anything in the JSON file data is
        # changed.

        if self._saved_fight['saved']:
            monster_group = self._saved_fight['monsters']

        self.__world.do_debug_snapshot('fight-%s' % monster_group)

        # Now we can go off and change the JSON file data

        if not self._saved_fight['saved']:
            self.clear_history()
            # Allowed add_to_history.
            self.add_to_history({'comment': '--- Round 0 ---'})

            self._saved_fight['round'] = 0
            self._saved_fight['index'] = 0
            self._saved_fight['monsters'] = monster_group

        # Rebuild the fighter list (even if the fight was saved since monsters
        # or characters could have been added since the save happened).

        self.__fighters = [] # This is a parallel array to
                             # self._saved_fight['fighters'] but the contents
                             # are: {'group': <groupname>,
                             #       'info': <Fighter object>}

        for name in self.__world.get_creatures('PCs'):
            details = self.__world.get_creature_details(name, 'PCs')
            if details is not None:
                fighter = Fighter(name,
                                  'PCs',
                                  details,
                                  self.__ruleset,
                                  self._window_manager)
                self.__fighters.append(fighter)

        the_fight_itself = None
        if monster_group is not None:
            for name in self.__world.get_creatures(monster_group):
                details = self.__world.get_creature_details(name,
                                                            monster_group)
                if details is None:
                    continue

                if name == Fight.name:
                    the_fight_itself = details
                else:
                    fighter = Fighter(name,
                                      monster_group,
                                      details,
                                      self.__ruleset,
                                      self._window_manager)
                    self.__fighters.append(fighter)

        # Sort by initiative = basic-speed followed by DEX followed by
        # random
        self.__fighters.sort(
                key=lambda fighter:
                    self.__ruleset.initiative(fighter), reverse=True)

        # Put the fight info (if any) at the top of the list.
        if the_fight_itself is not None:
            fight = Fight(monster_group,
                          the_fight_itself,
                          self.__ruleset,
                          self._window_manager)

            self.__fighters.insert(0, fight)

        # Copy the fighter information into the saved_fight.  Also, make
        # sure this looks like a _NEW_ fight.
        self._saved_fight['fighters'] = []
        for fighter in self.__fighters:
            fighter.start_fight()
            self._saved_fight['fighters'].append({'group': fighter.group,
                                                   'name': fighter.name})

        if monster_group is not None:
            for name in self.__world.get_creatures(monster_group):
                details = self.__world.get_creature_details(name,
                                                            monster_group)
                if details is not None:
                    self.__ruleset.is_creature_consistent(name, details)

        self._saved_fight['saved'] = False

        if not self.should_we_show_current_fighter():
            self.modify_index(1)

        first_fighter = self.get_current_fighter()
        first_fighter.start_turn()

        self._window.start_fight()

    #
    # Public Methods
    #

    def display_window(self,
                       title,
                       lines  # [{'text', 'mode'}, ...]
                      ):
        return True


    def get_current_fighter(self):              # Public to support testing
        '''
        Returns the Fighter object of the current fighter.
        '''
        result = self.__fighters[ self._saved_fight['index'] ]
        return result


    def get_fighters(self):                     # Public to support testing
        '''  '''
        return [{'name': fighter.name,
                 'group': fighter.group,
                 'details': fighter.details} for fighter in self.__fighters]


    def get_opponent_for(self,
                         fighter # Fighter object
                        ):
        ''' Returns Fighter object for opponent of 'fighter'. '''
        if (fighter is None or fighter.name == Fight.name or
                                        fighter.details['opponent'] is None):
            return None

        opponent = self.__get_fighter_object(
                                        fighter.details['opponent']['name'],
                                        fighter.details['opponent']['group'])
        return opponent


    def handle_user_input_until_done(self):
        '''
        Draws the screen and does event loop (gets input, responds to input)
        '''
        self._draw_screen()

        keep_going = True
        while keep_going:
            string = self._window_manager.get_one_character()
            if string in self._choices:
                choice = self._choices[string]

                viewed_fighter = (None if self.__viewing_index is None
                        else self.__fighters[self.__viewing_index])
                viewed_opponent = self.get_opponent_for(viewed_fighter)
                current_fighter = self.get_current_fighter()
                current_opponent = self.get_opponent_for(current_fighter)


                if 'param' not in choice or choice['param'] is None:
                    keep_going = self._choices[string]['func']()

                else:
                    param = choice['param']
                    if 'view' in param:
                        param['view'] = viewed_fighter
                    if 'view-opponent' in param:
                        param['view-opponent'] = viewed_opponent
                    if 'current' in param:
                        param['current'] = current_fighter
                    if 'current-opponent' in param:
                        param['current-opponent'] = current_opponent

                    keep_going = self._choices[string]['func'](param)

                if 'show' in choice and choice['show']:
                    show_fighter = (current_fighter if viewed_fighter is None
                                                        else viewed_fighter)
                    show_opponent = self.get_opponent_for(show_fighter)
                    self._window.show_fighters(show_fighter,
                                               show_opponent,
                                               self.__fighters,
                                               self._saved_fight['index'],
                                               self.__viewing_index)
            else:
                self._window_manager.error(
                                    ['Invalid command: "%c" ' % chr(string)])

            # Display stuff when we're done.

            # NOTE: this won't work because some choices (__show_why, for
            # example) don't want the screen to be redrawn
            if keep_going:
                if self.__viewing_index is None:
                    current_fighter = self.get_current_fighter()
                else:
                    current_fighter = self.__fighters[self.__viewing_index]
                opponent = self.get_opponent_for(current_fighter)

                self._window.show_fighters(current_fighter,
                                           opponent,
                                           self.__fighters,
                                           self._saved_fight['index'],
                                           self.__viewing_index)

        # When done, move current fight to 'dead-monsters'
        if (not self._saved_fight['saved'] and
                                self._saved_fight['monsters'] is not None and
                                self.__keep_monsters == False):
            fight_group = self._saved_fight['monsters']
            fight = self.__world.get_creatures(fight_group)

            fmt='%Y-%m-%d-%H-%M-%S'
            date = datetime.datetime.now().strftime(fmt).format()
            self.__world.details['dead-monsters'].append({'name': fight_group,
                                                          'date': date,
                                                          'fight': fight})
            fights = self.__world.get_fights()
            del fights[fight_group]


    def modify_index(self,                      # Public to support testing
                     adj      # 1 or -1, adjust the index by this
                    ):
        '''
        Increment or decrement the index.  Only stop on living creatures.
        '''
        first_index = self._saved_fight['index']

        round_before = self._saved_fight['round']
        keep_going = True
        while keep_going:
            self._saved_fight['index'] += adj
            if self._saved_fight['index'] >= len(
                                            self._saved_fight['fighters']):
                self._saved_fight['index'] = 0
                self._saved_fight['round'] += adj 
            elif self._saved_fight['index'] < 0:
                self._saved_fight['index'] = len(
                                            self._saved_fight['fighters']) - 1
                self._saved_fight['round'] += adj 
            current_fighter = self.get_current_fighter()
            if current_fighter.name == Fight.name:
                pass
            elif current_fighter.is_dead():
                # Allowed add_to_history
                self.add_to_history({'comment': ' (%s) did nothing (dead)' %
                                                        current_fighter.name})
            elif current_fighter.is_absent():
                # Allowed add_to_history.
                self.add_to_history({'comment': ' (%s) did nothing (absent)' %
                                                        current_fighter.name})

            else:
                keep_going = False

            # If we're skipping a fighter (due to his state), exercise his
            # timers, anyway
            if keep_going:
                self.__handle_fighter_background_actions(current_fighter)

            # If we didn't change the index (for instance, if everyone's
            # dead), stop looking.  Otherwise, we're in an infinite loop.
            if self._saved_fight['index'] == first_index:
                keep_going = False

        if round_before != self._saved_fight['round']:
            # Allowed add_to_history.
            self.add_to_history({'comment': '--- Round %d ---' %
                                                self._saved_fight['round']})


    def pick_opponent(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
        else:
            current_fighter = self.get_current_fighter()

        # Pick the opponent.

        opponent_group = None
        opponent_menu = []
        default_selection = None
        for fighter in self.__fighters:
            if (fighter.group != current_fighter.group and
                                                fighter.name != Fight.name):
                opponent_group = fighter.group
                if fighter.is_conscious():
                    if fighter.details['opponent'] is None:
                        if default_selection is None:
                            default_selection = len(opponent_menu)
                        menu_text = fighter.name
                    else:
                        menu_text = '%s (fighting %s)' % (
                                fighter.name,
                                fighter.details['opponent']['name'])
                    opponent_menu.append((menu_text, fighter.name))
        if len(opponent_menu) <= 0:
            self._window_manager.error(['All the opponents are dead'])
            return True # don't leave the fight

        if default_selection is None:
            default_selection = 0
        opponent_name = self._window_manager.menu('Opponent',
                                                  opponent_menu,
                                                  default_selection)

        if opponent_name is None:
            return True # don't leave the fight

        # Now, reflect the selection in the code.

        self.__ruleset.do_action(current_fighter,
                                 {'name': 'pick-opponent',
                                  'opponent-name': opponent_name,
                                  'opponent-group': opponent_group,
                                  'comment': '(%s) picked (%s) as opponent' % 
                                                    (current_fighter.name,
                                                     opponent_name)
                                 },
                                 self)

        opponent = self.__get_fighter_object(opponent_name, opponent_group)

        # Ask to have them fight each other
        if (opponent is not None and opponent.details['opponent'] is None):
            back_menu = [('yes', True), ('no', False)]
            answer = self._window_manager.menu('Make Opponents Go Both Ways',
                                        back_menu)
            if answer == True:
                self.__ruleset.do_action(
                    opponent,
                    {'name': 'pick-opponent',
                     'opponent-name': current_fighter.name,
                     'opponent-group': current_fighter.group,
                     'comment': '(%s) picked (%s) as opponent right back' % 
                                                        (opponent_name,
                                                         current_fighter.name)
                    },
                    self)

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def promote_to_NPC(self):                       # Public to support testing
        if self.__viewing_index is not None:
            new_NPC = self.__fighters[self.__viewing_index]
        else:
            current_fighter = self.get_current_fighter()
            if (current_fighter.group == 'PCs' or
                                            current_fighter.group == 'NPCs'):
                opponent = self.get_opponent_for(current_fighter)
                new_NPC = current_fighter if opponent is None else opponent
            else:
                new_NPC = current_fighter

        if new_NPC.group == 'PCs':
            self._window_manager.error(['%s is already a PC' % new_NPC.name])
            return True
        if new_NPC.group == 'NPCs':
            self._window_manager.error(['%s is already an NPC' % new_NPC.name])
            return True

        # Now we have chosen a monster that's NOT an NPC or PC, promote him.

        # Make the NPC entry

        if new_NPC.name in self.__world.details['NPCs']:
            self._window_manager.error(['There\'s already an NPC named %s' %
                                        new_NPC.name])
            return True

        # TODO: do we need to call 'get_creature_details' in case 'details'
        #   is a redirect?

        details_copy = copy.deepcopy(new_NPC.details)
        self.__world.details['NPCs'][new_NPC.name] = details_copy

        # Make the redirect entry

        group = self.__world.get_creatures(new_NPC.group)
        group[new_NPC.name] = { "redirect": "NPCs" }

        # Replace fighter information with new fighter information

        for index, fighter in enumerate(self.__fighters):
            if (fighter.name == new_NPC.name and
                                            fighter.group == new_NPC.group):
                new_fighter = Fighter(new_NPC.name,
                                      new_NPC.group,
                                      details_copy,
                                      self.__ruleset,
                                      self._window_manager)
                self.__fighters[index] = new_fighter
                self._window_manager.display_window(
                                               ('Promoted Monster to NPC'),
                                                [[{'text': new_NPC.name,
                                                   'mode': curses.A_NORMAL }]])
                break

        return True # Keep going


    def set_viewing_index(self, new_index):     # Public to support testing.
        self.__viewing_index = new_index


    def should_we_show_current_fighter(self):
        '''
        Only called when the fight starts to see if the first creature (or the
        Fight) should be displayed.
        '''
        show_fighter = True
        current_fighter = self.get_current_fighter()
        if current_fighter.name == Fight.name:
            show_fighter = False

        elif current_fighter.is_dead():
            show_fighter = False

        elif current_fighter.is_absent():
            show_fighter = False

        if not show_fighter:
            self.__handle_fighter_background_actions(current_fighter)

        return show_fighter


    def simply_save(self, throw_away):
        self._saved_fight['saved'] = True

    #
    # Private Methods
    #

    def __change_viewing_index(self,
                               adj  # integer adjustment to viewing index
                              ):
        self.__viewing_index += adj
        if self.__viewing_index >= len(self._saved_fight['fighters']):
            self.__viewing_index = 0
        elif self.__viewing_index < 0:
            self.__viewing_index = len(self._saved_fight['fighters']) - 1


    def __damage_HP(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Figure out who loses the hit points

        attacker = None
        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
            opponent = self.get_opponent_for(current_fighter)
            hp_recipient = current_fighter
            attacker = None # Not going to do an 'attack' action when the HP
                            #   was modified through an index
        else:
            current_fighter = self.get_current_fighter()
            opponent = self.get_opponent_for(current_fighter)
            if opponent is None:
                hp_recipient = current_fighter
                attacker = None
            else:
                hp_recipient = opponent
                attacker = current_fighter

        # Reduce the HP

        title = 'Reduce (%s\'s) HP By...' % hp_recipient.name
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        if len(adj_string) <= 0:
            return True

        adj = -int(adj_string) # NOTE: SUBTRACTING the adjustment
        if adj == 0:
            return True # Keep fighting

        action = {'name': 'adjust-hp', 'adj': adj}

        # Record for posterity
        if hp_recipient is opponent:
            if adj < 0:
                action['comment'] = '(%s) did %d HP to (%s)' % (
                                                        current_fighter.name,
                                                        -adj,
                                                        opponent.name)
            else:
                action['comment'] = '(%s) regained %d HP' % (opponent.name,
                                                             adj)

            # Did attacker already attack

            if attacker is None:
                ask_to_attack = False
            elif 'attack' in attacker.details['actions_this_turn']:
                ask_to_attack = False
            elif 'all-out-attack' in attacker.details['actions_this_turn']:
                ask_to_attack = False
            else:
                ask_to_attack = True

            if ask_to_attack:
                attack_menu = [('yes', True), ('no', False)]
                should_attack = self._window_manager.menu(
                                    ('Should %s Attack?' % attacker.name),
                                    attack_menu)
                if should_attack:
                    comment = '(%s) did (Attack) maneuver' % attacker.name
                    self.__ruleset.do_action(attacker,
                                             {'name': 'attack',
                                              'comment': comment},
                                             self)
        else:
            if adj < 0:
                action['comment'] = '%d HP was done to (%s)' % (
                                                        -adj,
                                                        current_fighter.name)
            else:
                action['comment'] = ' (%s) regained %d HP' % (
                                                        current_fighter.name,
                                                        adj)

        self.__ruleset.do_action(hp_recipient, action, self)

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __dead(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        now_dead, current_fighter = self.__select_fighter('Who is Dead',
                                                          default_selection=1)
        if now_dead is None:
            return True # Keep fighting

        state_menu = sorted(Fighter.conscious_map.iteritems(),
                            key=lambda x:x[1])

        new_state_number = self._window_manager.menu('New State', state_menu)
        if new_state_number is None:
            return True # Keep fighting

        dead_name = now_dead.name

        self.__ruleset.do_action(
                now_dead,
                {
                    'name': 'set-consciousness',
                    'level': new_state_number,
                    'comment': '(%s) is now (%s)' % (
                        dead_name,
                        Fighter.get_name_from_state_number(new_state_number))
                },
                self)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __defend(self):
        '''
        Performed on the opponent of the current fighter.

        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        if self.__viewing_index != self._saved_fight['index']:
            self.__viewing_index = None
            self._window.show_fighters(current_fighter,
                                       opponent,
                                       self.__fighters,
                                       self._saved_fight['index'],
                                       self.__viewing_index)

        # Figure out who is defending
        if opponent is None:
            defender = current_fighter
        else:
            defender_menu = [(current_fighter.name, current_fighter),
                                 (opponent.name, opponent)]
            defender = self._window_manager.menu('Who is defending',
                                                 defender_menu,
                                                 1) # assume the opponent
        if defender is None:
            return True # Keep fighting

        self.__ruleset.do_action(
            defender,
            {
                'name': 'defend',
                'comment': '(%s) defended (and lost aim)' % defender.name
            },
            self)

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __do_keep_monsters(self):
        # TODO: keep and saved are mutually exclusive -- should store them in
        # one variable.
        # TODO: when leaving the fight, should ask save/keep
        self.__keep_monsters = True # Don't move monsters to dead after fight
        self._saved_fight['saved'] = False
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  self._saved_fight['saved'],
                                  self.__keep_monsters,
                                  next_PC_name,
                                  self._input_filename,
                                  ScreenHandler.maintainjson)
        return True # Keep going


    def _draw_screen(self):
        self._window.clear()
        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  self._saved_fight['saved'],
                                  self.__keep_monsters,
                                  next_PC_name,
                                  self._input_filename,
                                  ScreenHandler.maintainjson)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        self._window.status_ribbon(self._input_filename,
                                   ScreenHandler.maintainjson)
        self._window.command_ribbon(self._choices)


    def __full_notes(self):
        return self.__notes('notes')


    def __get_fighter_details(self,
                              name,     # string
                              group     # string
                             ):
        ''' Used for constructing a Fighter from the JSON information. '''
        return self.__world.get_creature_details(name, group)


    def __get_fighter_object(self,
                             name,  # name of a fighter in that group
                             group  # 'PCs' or group under world['fights']
                            ):
        for fighter in self.__fighters:
            if fighter.group == group and fighter.name == name:
                return fighter

        return None


    def __give_equipment(self):
        if self.__viewing_index is not None:
            from_fighter = self.__fighters[self.__viewing_index]
        else:
            from_fighter = self.get_current_fighter()

        item = self.__equipment_manager.remove_equipment(from_fighter)
        if item is None:
            return True # Keep going


        character_list = self.__world.get_creatures(from_fighter.group)
        character_menu = [(dude, dude) for dude in character_list]
        to_fighter_name = self._window_manager.menu(
                                        'Give "%s" to whom?' % item['name'],
                                        character_menu)

        if to_fighter_name is None:
            from_fighter.add_equipment(item, None)
            return True # Keep going

        to_fighter = self.__get_fighter_object(to_fighter_name,
                                               from_fighter.group)

        to_fighter.add_equipment(item, from_fighter.detailed_name)
        return True # Keep going


    def __handle_fighter_background_actions(
                                    self,
                                    out_of_commision_fighter # Fighter object
                                    ):
        '''
        Called when a fighter is being skipped (because, for example, he's
        unconscious).  Handles background stuff that happens for the fighter
        even if he's not able to do anything overtly.
        '''
        out_of_commision_fighter.timers.decrement_all()
        out_of_commision_fighter.timers.remove_expired_kill_dying()


    def __loot_bodies(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if self.__viewing_index != self._saved_fight['index']:
            current_fighter = self.get_current_fighter()
            opponent = self.get_opponent_for(current_fighter)
            self.__viewing_index = None
            self._window.show_fighters(current_fighter,
                                       opponent,
                                       self.__fighters,
                                       self._saved_fight['index'],
                                       self.__viewing_index)

        self.__bodies_looted = True
        found_dead_bad_guy = False
        found_something_on_dead_bad_guy = False

        # Go through bad buys and distribute their items
        for bad_guy in self.__fighters:
            if bad_guy.group == 'PCs': # only steal from bad guys
                continue
            if bad_guy.is_conscious(): # only steal from the dead/unconscious
                # Note that absent characters are not marked as conscious
                continue
            found_dead_bad_guy = True

            # Reversed so removing items doesn't change the index of others
            for index, item in reversed(list(enumerate(
                                                bad_guy.details['stuff']))):
                found_something_on_dead_bad_guy = True
                xfer_menu = [(good_guy.name, {'guy': good_guy})
                                 for good_guy in self.__fighters
                                            if good_guy.group == 'PCs']
                xfer_menu.append(('QUIT', {'quit': None}))
                xfer = self._window_manager.menu(
                        'Who gets %s\'s %s' % (bad_guy.name,
                                               item['name']),
                        xfer_menu)

                if xfer is None:
                    continue

                if 'quit' in xfer:
                    return True

                new_item = bad_guy.details['stuff'].pop(index)
                xfer['guy'].add_equipment(new_item, bad_guy.detailed_name)

                # indexes are no longer good, remove the weapon and armor
                bad_guy.don_armor_by_index(None)
                bad_guy.draw_weapon_by_index(None)

        if not found_dead_bad_guy:
            self._window_manager.error(
                ['Can\'t loot from the living -- there are no dead bad guys.'])
        elif not found_something_on_dead_bad_guy:
            self._window_manager.error(
                ['Bad guys didn\'t have anything worth looting.'])

        return True # Keep fighting


    def __maneuver(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        if self.__viewing_index != self._saved_fight['index']:
            self.__viewing_index = None
            self._window.show_fighters(current_fighter,
                                       opponent,
                                       self.__fighters,
                                       self._saved_fight['index'],
                                       self.__viewing_index)

        action_menu = self.__ruleset.get_action_menu(current_fighter,
                                                     opponent)
        maneuver = self._window_manager.menu('Maneuver', action_menu)
        if maneuver is None:
            return True # Keep going

        if 'action' in maneuver:
            maneuver['action']['comment'] = '(%s) did (%s) maneuver' % (
                                                          current_fighter.name,
                                                          maneuver['text'][0])
            maneuver['action']['fighter'] = current_fighter.name
            maneuver['action']['group'] = current_fighter.group
            self.__ruleset.do_action(current_fighter,
                                     maneuver['action'],
                                     self)

        # a round count larger than 0 will get shown but less than 1 will
        # get deleted before the next round

        timer = Timer(None)
        timer.from_pieces(current_fighter.name, 0.9, maneuver['text'])
        current_fighter.timers.add(timer)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __next_fighter(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__viewing_index = None

        # Finish off previous guy
        prev_fighter = self.get_current_fighter()
        if not prev_fighter.can_finish_turn():
            return self.__maneuver()
        elif not prev_fighter.is_conscious():
            # Allowed add_to_history.
            self.add_to_history({'comment': '(%s) did nothing (unconscious)' %
                                                    prev_fighter.name})

        prev_fighter.end_turn()

        # Start the new guy
        self.modify_index(1)
        current_fighter = self.get_current_fighter()
        current_fighter.start_turn()

        # Show all the displays
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  self._saved_fight['saved'],
                                  self.__keep_monsters,
                                  next_PC_name,
                                  self._input_filename,
                                  ScreenHandler.maintainjson)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __next_PC_name(self):
        '''
        Finds the name of the next PC to fight _after_ the current index.
        '''

        next_PC_name = None
        next_index = self._saved_fight['index'] + 1
        for ignore in self._saved_fight['fighters']:
            if next_index >= len(self._saved_fight['fighters']):
                next_index = 0
            if self._saved_fight['fighters'][next_index]['group'] == 'PCs':
                next_PC_name = (
                        self._saved_fight['fighters'][next_index]['name'])
                break
            next_index += 1
        return next_PC_name


    def __notes(self,
                notes_type  # 'short-notes' or 'notes'
               ):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        notes_recipient, current_fighter = self.__select_fighter(
                                                            'Notes For Whom')
        if notes_recipient is None:
            return True # Keep fighting

        # Now, get the notes for that person
        lines, cols = self._window.getmaxyx()

        if notes_type not in notes_recipient.details:
            notes = None
        else:
            notes = '\n'.join(notes_recipient.details[notes_type])

        notes = self._window_manager.edit_window(
                    lines - 4,
                    self._window.fighter_win_width,
                    notes,  # initial string (w/ \n) for the window
                    'Notes',
                    '^G to exit')

        notes_recipient.details[notes_type] = [x for x in notes.split('\n')]

        # Redraw the fighters
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __prev_fighter(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__viewing_index = None
        if (self._saved_fight['index'] == 0 and 
                self._saved_fight['round'] == 0):
            return True # Not going backwards from the origin

        self.modify_index(-1)
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  self._saved_fight['saved'],
                                  self.__keep_monsters,
                                  next_PC_name,
                                  self._input_filename,
                                  ScreenHandler.maintainjson)
        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Get the state of the monsters.

        ask_to_save = False # Ask to save if some monster is conscious
        ask_to_loot = False # Ask to loot if some monster is unconscious
        for fighter in self.__fighters:
            if fighter.group != 'PCs' and fighter.name != Fight.name:
                if fighter.is_conscious():
                    ask_to_save = True
                else:
                    ask_to_loot = True

        # Ask: save or loot?

        while ask_to_save or ask_to_loot:
            quit_menu = [('quit -- really', {'doit': None})]

            if not self.__bodies_looted and ask_to_loot:
                quit_menu.append(('loot the bodies',
                                 {'doit': self.__loot_bodies}))

            if not self._saved_fight['saved'] and ask_to_save:
                quit_menu.append(('save the fight',
                                 {'doit': self.simply_save}))

            result = self._window_manager.menu('Leaving Fight', quit_menu)
            if result is None:
                return True # I guess we're not quitting after all
            elif result['doit'] is None:
                ask_to_save = False
                ask_to_loot = False
            else:
                (result['doit'])(None)

        if not self._saved_fight['saved']:
            for fighter in self.__fighters:
                fighter.end_fight(self.__world, self)

        self._window.close()
        return False # Leave the fight


    def __short_notes(self):
        return self.__notes('short-notes')


    def __save(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self._saved_fight['saved'] = True
        self.__keep_monsters = False # Don't move monsters to dead after fight
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  self._saved_fight['saved'],
                                  self.__keep_monsters,
                                  next_PC_name,
                                  self._input_filename,
                                  ScreenHandler.maintainjson)
        return True # Keep going


    def __select_fighter(self,
                         menu_title, # string: title of fighter/opponent menu
                         default_selection=0  # int: for menu:
                                              #   0=current fighter, 1=opponent
                         ):
        '''
        Selects a fighter to be the object of the current action.
        '''
        selected_fighter = None
        current_fighter = None
        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
            opponent = self.get_opponent_for(current_fighter)
            selected_fighter = current_fighter
        else:
            current_fighter = self.get_current_fighter()
            opponent = self.get_opponent_for(current_fighter)

            if opponent is None:
                selected_fighter = current_fighter
            else:
                selected_fighter_menu = [
                                    (current_fighter.name, current_fighter),
                                    (opponent.name, opponent)]
                selected_fighter = self._window_manager.menu(
                                                     menu_title,
                                                     selected_fighter_menu,
                                                     default_selection)
        return selected_fighter, current_fighter


    def __show_history(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        lines = []
        for action in self._saved_fight['history']:
            if 'comment' in action:
                line = action['comment']
                mode = (curses.A_STANDOUT if line.startswith('---')
                        else curses.A_NORMAL)
                lines.append([{'text': line, 'mode': mode}])

        self._window_manager.display_window('Fight History', lines)
        return True


    def __show_info(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        char_info = []

        info_about, current_fighter = self.__select_fighter('Info About Whom')
        if info_about is None:
            return True # Keep fighting

        info_about.get_description(char_info)
        self._window_manager.display_window('%s Information' % info_about.name,
                                            char_info)
        return True


    def __show_why(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        why_target, current_fighter = self.__select_fighter('Details For Whom')
        if why_target is None:
            return True # Keep fighting

        lines = why_target._explain_numbers(self)

        ignore = self._window_manager.display_window(
                    'How %s\'s Numbers Were Calculated' % why_target.name,
                    lines)
        return True


    def __timer(self):
        '''
        Command ribbon method.
        Asks user for information for timer to add to a fighter.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        timer_recipient, current_fighter = self.__select_fighter(
                                                            'Who Gets Timer')
        if timer_recipient is None:
            return True # Keep fighting

        timers_widget = TimersWidget(timer_recipient.timers,
                                     self._window_manager)
        timers_widget.make_timer(timer_recipient.name)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep fighting


    def __timer_cancel(self):
        '''
        Command ribbon method.
        Asks user for information for timer to add to a fighter.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        timer_recipient, current_fighter = self.__select_fighter(
                                                    'Whose Timer To Cancel')
        if timer_recipient is None:
            return True # Keep fighting

        # Select a timer

        timers = timer_recipient.timers.get_all()
        timer_menu = [(timer.get_one_line_description(), index)
                                for index, timer in enumerate(timers)]
        index = self._window_manager.menu('Remove Which Timer', timer_menu)
        if index is None:
            return True # Keep fighting

        # Delete the timer

        timer_recipient.timers.remove_timer_by_index(index)

        # Display the results

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep fighting


    def __view_init(self):
        ''' look at initiative character (back to fight) '''
        self.__viewing_index = None
        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __view_prev(self):
        ''' look at previous character, don't change init '''
        if self.__viewing_index is None:
            self.__viewing_index = self._saved_fight['index']
        self.__change_viewing_index(-1)
        viewing_fighter = self.__fighters[self.__viewing_index]
        opponent = self.get_opponent_for(viewing_fighter)
        if self.__viewing_index == self._saved_fight['index']:
            self.__viewing_index = None
        self._window.show_fighters(viewing_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __view_next(self):
        ''' look at next character, don't change init '''
        if self.__viewing_index is None:
            self.__viewing_index = self._saved_fight['index']
        self.__change_viewing_index(1)
        viewing_fighter = self.__fighters[self.__viewing_index]
        opponent = self.get_opponent_for(viewing_fighter)
        if self.__viewing_index == self._saved_fight['index']:
            self.__viewing_index = None
        self._window.show_fighters(viewing_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


class MainHandler(ScreenHandler):
    (CHAR_LIST,
     CHAR_DETAIL) = (1, 2)  # These are intended to be bits so they can be ored
                            # together

    def __init__(self,
                 window_manager,
                 world,
                 ruleset,
                 campaign_debug_json, # For Debugging only
                 filename # For Debugging Only: JSON file containing the world
                ):
        super(MainHandler, self).__init__(window_manager,
                                          campaign_debug_json,
                                          filename,
                                          world.details['current-fight'])
        self.__world = world
        self.__ruleset = ruleset
        self.__current_pane = MainHandler.CHAR_DETAIL
        self._add_to_choice_dict({
            curses.KEY_HOME:
                      {'name': 'scroll home',         'func':
                                                       self.__first_page},
            curses.KEY_UP:
                      {'name': 'previous character',  'func':
                                                       self.__prev_char},
            curses.KEY_DOWN:
                      {'name': 'next character',      'func':
                                                       self.next_char},
            curses.KEY_NPAGE:
                      {'name': 'scroll down',         'func':
                                                       self.__next_page},
            curses.KEY_PPAGE:
                      {'name': 'scroll up',           'func':
                                                       self.__prev_page},
            curses.KEY_LEFT:
                      {'name': 'scroll chars',        'func':
                                                       self.__left_pane},
            curses.KEY_RIGHT:
                      {'name': 'scroll char detail',  'func':
                                                       self.__right_pane},

            ord('e'): {'name': 'EQUIP/mod PC/NPC/monster', 'func': 
                                                       self.__equip},
            ord('p'): {'name': 'move/add PERSONNEL',  'func': 
                                                       self.__party},
            ord('f'): {'name': 'FIGHT',               'func':
                                                       self.__run_fight},
            ord('h'): {'name': 'heal selected creature', 'func':
                                                       self.__heal},
            ord('H'): {'name': 'Heal all PCs',        'func':
                                                       self.__fully_heal},
            ord('m'): {'name': 'show MONSTERs or PC/NPC', 'func':
                                       self.__toggle_Monster_PC_NPC_display},

            ord('q'): {'name': 'quit',                'func':
                                                       self.__quit},
            ord('R'): {'name': 'resurrect fight',     'func':
                                                       self.__resurrect_fight},
            ord('S'): {'name': 'toggle: Save On Exit','func':
                                                       self.__maintain_json},
            ord('/'): {'name': 'search',              'func':
                                                       self.__search}
        })
        self.__current_display = None   # name of monster group or 'None' for
                                        # PC/NPC list
        self.__setup_PC_list(self.__current_display)
        self._window = self._window_manager.get_main_gm_window()
        self.__equipment_manager = EquipmentManager(self.__world,
                                                    self._window_manager)

        # Check characters for consistency.
        for name in self.__world.get_creatures('PCs'):
            details = self.__world.get_creature_details(name, 'PCs')
            if details is not None:
                self.__ruleset.is_creature_consistent(name, details)

    #
    # Public Methods
    #

    def get_fighter_from_char_index(self):      # Public to support testing
        return self.__chars[self.__char_index]


    def next_char(self,                         # Public to support testing
                  index=None  # Just for testing
                 ):
        if index is not None:
            self.__char_index = index
        elif self.__char_index is None:
            self.__char_index = 0
        else:
            self.__char_index += 1
            if self.__char_index >= len(self.__chars):
                self.__char_index = 0
        self.__first_page(MainHandler.CHAR_DETAIL)
        self._draw_screen()
        return True


    def NPC_joins_monsters(self, throw_away):   # Public to support testing
        # Make sure the person is an NPC
        npc_name = self.__chars[self.__char_index].name
        if self.__chars[self.__char_index].group != 'NPCs':
            self._window_manager.error(['"%s" not an NPC' % npc_name])
            return True

        # Select the fight
        fight_menu = [(fight_name, fight_name)
                                for fight_name in self.__world.get_fights()]
        fight_name = self._window_manager.menu('Join Which Fight', fight_menu)

        # Make sure the person isn't already in the fight
        fight = self.__world.get_creatures(fight_name)
        if npc_name in fight:
            self._window_manager.error(['"%s" already in fight "%s"' %
                                                    (npc_name, fight_name)])
            return True

        fight[npc_name] = {'redirect': 'NPCs'}
        self.__setup_PC_list(self.__current_display)
        self._draw_screen()
        return True


    def NPC_joins_PCs(self,                     # Public to support testing
                      throw_away):
        npc_name = self.__chars[self.__char_index].name
        if self.__chars[self.__char_index].group != 'NPCs':
            self._window_manager.error(['"%s" not an NPC' % npc_name])
            return True

        if npc_name in self.__world.details['PCs']:
            self._window_manager.error(['"%s" already a PC' % npc_name])
            return True

        self.__world.details['PCs'][npc_name] = {'redirect': 'NPCs'}
        self.__setup_PC_list(self.__current_display)
        self._draw_screen()
        return True

    #
    # Protected and Private Methods
    #

    def __add_equipment(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]

        keep_asking = True
        keep_asking_menu = [('yes', True), ('no', False)]
        while keep_asking:
            self.__equipment_manager.add_equipment(fighter)
            self._draw_screen()
            keep_asking = self._window_manager.menu('Add More Equipment',
                                                    keep_asking_menu)
        return True # Keep going


    def __add_monsters(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world,
                                        self.__ruleset,
                                        BuildFightHandler.MONSTERs,
                                        self.__world.campaign_debug_json,
                                        self._input_filename)
        build_fight.handle_user_input_until_done()

        # Display the last fight on the main screen

        last_group_name = build_fight.get_group_name()
        if (last_group_name is not None and last_group_name != 'PCs' and
                                            last_group_name != 'NPCs'):
            self.__current_display = last_group_name

        self.__setup_PC_list(self.__current_display)
        self._draw_screen()

        return True # Keep going


    def __add_NPCs(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world,
                                        self.__ruleset,
                                        BuildFightHandler.NPCs,
                                        self.__world.campaign_debug_json,
                                        self._input_filename)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list(self.__current_display) # Since it may have changed
        self._draw_screen() # Redraw current screen when done building fight.
        return True # Keep going


    def __add_PCs(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world,
                                        self.__ruleset,
                                        BuildFightHandler.PCs,
                                        self.__world.campaign_debug_json,
                                        self._input_filename)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list(self.__current_display) # Since it may have changed
        self._draw_screen() # Redraw current screen when done building fight.
        return True # Keep going


    def __add_spell(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]

        # Is the fighter a caster?
        if 'spells' not in fighter.details:
            self._window_manager.error(
                ['Doesn\'t look like %s casts spells' % fighter.name])
            return True

        # Pick from the spell list
        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        spell_menu = [(spell_name, spell_name)
                                for spell_name in
                                    sorted(self.__ruleset.spells.iterkeys())]
        while keep_asking:
            new_spell_name = self._window_manager.menu('Spell to Add',
                                                       spell_menu)
            if new_spell_name is None:
                return True

            # Check if spell is already there
            for spell in fighter.details['spells']:
                if spell['name'] == new_spell_name:
                    self._window_manager.error(
                            ['%s already has spell "%s"' % (fighter.name,
                                                            spell['name'])])
                    new_spell_name = None
                    break

            if new_spell_name is not None:
                my_copy = {'name': new_spell_name}

                title = 'At What Skill Level...'
                height = 1
                width = len(title) + 2
                keep_ask_skill = True
                while keep_ask_skill:
                    skill_string = self._window_manager.input_box(height,
                                                                  width,
                                                                  title)
                    if skill_string is not None and len(skill_string) > 0:
                        my_copy['skill'] = int(skill_string)
                        keep_ask_skill = False
                    else:
                        self._window_manager.error(
                                                ['You must specify a skill'])

                fighter.details['spells'].append(my_copy)
                self._draw_screen()

            keep_asking = self._window_manager.menu('Add More Spells',
                                                    keep_asking_menu)
        return True # Keep going


    def __add_timer(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]
        lines, cols = self._window.getmaxyx()
        timers_widget = TimersWidget(fighter.timers, self._window_manager)

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            timers_widget.make_timer(fighter.name)
            self._draw_screen()
            keep_asking = self._window_manager.menu('Add More Timers',
                                                    keep_asking_menu)
        return True # Keep going


    def __change_attributes(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]
        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            perm_current_menu = [('current', 'current'),
                                 ('permanent', 'permanent')]
            attr_type = self._window_manager.menu('What Type Of Attribute',
                                                           perm_current_menu)
            if attr_type is None:
                return True

            attr_menu = [(attr, attr) 
                                for attr in fighter.details[attr_type].keys()]

            attr = self._window_manager.menu('Attr To Modify', attr_menu)
            if attr is None:
                return True

            title = 'New Value'
            height = 1
            width = len(title) + 2
            keep_ask_attr = True
            while keep_ask_attr:
                attr_string = self._window_manager.input_box(height,
                                                              width,
                                                              title)
                if attr_string is not None and len(attr_string) > 0:
                    fighter.details[attr_type][attr] = int(attr_string)
                    keep_ask_attr = False
                else:
                    self._window_manager.error(
                                    ['You must specify an attribute value'])

            if attr_type == 'permanent':
                both_menu = [('yes', True), ('no', False)]
                both = self._window_manager.menu(
                                            'Change "current" Value To Match ',
                                            both_menu)
                if both:
                    fighter.details['current'][attr] = (
                                            fighter.details['permanent'][attr])

            self._draw_screen()
            keep_asking = self._window_manager.menu('Change More Attributes',
                                                    keep_asking_menu)
        return True # Keep going


    def __don_armor(self, throw_away):
        fighter = self.__chars[self.__char_index]
        armor, throw_away = fighter.get_current_armor()
        armor_index = None
        if armor is None:
            don_armor_menu = []
            for index, item in enumerate(fighter.details['stuff']):
                if item['type'] == 'armor':
                    if armor_index != index:
                        don_armor_menu.append((item['name'], index))
            don_armor_menu = sorted(don_armor_menu, key=lambda x: x[0].upper())
            if len(don_armor_menu) == 1:
                armor_index = don_armor_menu[0][1]
            else:
                armor_index = self._window_manager.menu('Don Which Armor',
                                                        don_armor_menu)
                if armor_index is None:
                    return

        self.__ruleset.do_action(fighter,
                                 {'name': 'don-armor',
                                  'armor-index': armor_index
                                 },
                                 None)
        self._draw_screen()


    def _draw_screen(self, inverse=False):
        self._window.clear()
        self._window.status_ribbon(self._input_filename,
                                   ScreenHandler.maintainjson)

        # MainGmWindow
        self._window.show_creatures(self.__chars,
                                    self.__char_index,
                                    inverse)

        person = (None if self.__char_index is None
                       else self.__chars[self.__char_index])
        self._window.show_description(person)

        self._window.command_ribbon(self._choices)


    def __draw_weapon(self, throw_away):
        fighter = self.__chars[self.__char_index]
        weapon, throw_away = fighter.get_current_weapon()
        weapon_index = None
        if weapon is None:
            weapon_menu = []
            for index, item in enumerate(fighter.details['stuff']):
                if (item['type'] == 'melee weapon' or 
                        item['type'] == 'ranged weapon' or
                        item['type'] == 'shield'):
                    if weapon_index != index:
                        weapon_menu.append((item['name'], index))
            weapon_menu = sorted(weapon_menu, key=lambda x: x[0].upper())
            if len(weapon_menu) == 1:
                weapon_index = weapon_menu[0][1]
            else:
                weapon_index = self._window_manager.menu('Draw Which Weapon',
                                                         weapon_menu)
                if weapon_index is None:
                    return

        self.__ruleset.do_action(fighter,
                                 {'name': 'draw-weapon',
                                  'weapon-index': weapon_index
                                 },
                                 None)
        self._draw_screen()


    def __equip(self):
        fighter = self.__chars[self.__char_index]

        sub_menu = []
        if 'stuff' in fighter.details:
            sub_menu.extend([
                ('attributes (change)', {'doit': self.__change_attributes}),
                ('equipment (add)',     {'doit': self.__add_equipment}),
                ('Equipment (remove)',  {'doit': self.__remove_equipment}),
                ('give equipment',      {'doit': self.__give_equipment}),
            ])

        self.__ruleset_abilities = self.__ruleset.get_creature_abilities()
        for ability in self.__ruleset_abilities:
            if ability in fighter.details:
                sub_menu.extend([
                    ('%s (add)' % ability, {'doit': self.__ruleset_ability,
                                            'param': ability}),
                    ('%s (remove)' % ability.capitalize(),
                                            {'doit': self.__ruleset_ability_rm,
                                             'param': ability})
                ])

        # Add these at the end since they're less likely to be used (I'm
        # guessing) than the abilities from the ruleset
        if 'spells' in fighter.details:
            sub_menu.extend([
                ('magic spell (add)',       {'doit': self.__add_spell}),
                ('Magic spell (remove)',    {'doit': self.__remove_spell})
            ])

        if 'timers' in fighter.details:
            sub_menu.extend([
                ('timers (add)',           {'doit': self.__add_timer})
            ])
            sub_menu.extend([
                ('Timers (remove)',           {'doit': self.__timer_cancel})
            ])

        if 'notes' in fighter.details:
            sub_menu.extend([
                ('notes',           {'doit': self.__full_notes})
            ])

        if 'short-notes' in fighter.details:
            sub_menu.extend([
                ('Notes (short)',   {'doit': self.__short_notes})
            ])


        if 'armor-index' in fighter.details:
            sub_menu.extend([
                        ('Don/doff armor',  {'doit': self.__don_armor})
            ])

        if 'weapon-index' in fighter.details:
            sub_menu.extend([
                    ('Draw/drop weapon',    {'doit': self.__draw_weapon})
            ])

        self._window_manager.menu('Do what', sub_menu)

        # Do a consistency check once you're done equipping
        self.__ruleset.is_creature_consistent(fighter.name, fighter.details)

        return True # Keep going


    def __first_page(self,
                     pane = None, # CHAR_LIST, CHAR_DETAIL,
                                  # CHAR_LIST|CHAR_DETAIL
                    ):
        if pane is None:
            pane = self.__current_pane

        if (pane & MainHandler.CHAR_DETAIL) != 0:
            self._window.char_detail_home()

        if (pane & MainHandler.CHAR_LIST) != 0:
            self.__char_index = 0
            self._window.char_list_home()
            self._draw_screen()
        return True


    def __full_notes(self, throw_away):
        return self.__notes('notes')


    def __fully_heal(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        for name in self.__world.get_creatures('PCs'):
            details = self.__world.get_creature_details(name, 'PCs')
            if details is not None:
                self.__ruleset.heal_fighter(details)
        self._draw_screen()
        return True


    def __give_equipment(self, throw_away):
        from_fighter = self.__chars[self.__char_index]

        item = self.__equipment_manager.remove_equipment(from_fighter)
        if item is None:
            return True # Keep going

        character_list = self.__world.get_creatures('PCs')
        character_menu = [(dude, dude) for dude in character_list]
        to_fighter_info = self._window_manager.menu(
                                        'Give "%s" to whom?' % item['name'],
                                        character_menu)

        if to_fighter_info is None:
            from_fighter.add_equipment(item, None)
            self._draw_screen()
            return True # Keep going

        to_fighter = Fighter(to_fighter_info,
                             'PCs',
                             character_list[to_fighter_info],
                             self.__ruleset,
                             self._window_manager)

        to_fighter.add_equipment(item, from_fighter.detailed_name)
        self._draw_screen()
        return True # Keep going


    def __heal(self):
        '''
        Command ribbon method.

        Heals the selected creature.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__ruleset.heal_fighter(self.__chars[self.__char_index].details)
        self._draw_screen()

        return True


    def __left_pane(self):
        self.__current_pane = MainHandler.CHAR_LIST
        return True


    def __maintain_json(self):
        '''
        Command ribbon method.  Toggles whether the results of this session
        are saved to the .json file when the program is exited.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        world.toggle_saved_on_exit()
        self._draw_screen()
        return True # Keep going


    def __next_page(self):
        if self.__current_pane == MainHandler.CHAR_DETAIL:
            self._window.scroll_char_detail_down()
        else:
            self._window.scroll_char_list_down()
        return True


    def __notes(self,
                notes_type  # 'short-notes' or 'notes'
               ):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]
        if fighter is None:
            return True # Keep fighting

        # Now, get the notes for that person
        lines, cols = self._window.getmaxyx()

        if notes_type not in fighter.details:
            notes = None
        else:
            notes = '\n'.join(fighter.details[notes_type])

        notes = self._window_manager.edit_window(
                    lines - 4,
                    cols / 2, # arbitrary width
                    notes,    # initial string (w/ \n) for the window
                    'Notes',
                    '^G to exit')

        fighter.details[notes_type] = [x for x in notes.split('\n')]
        self._draw_screen()

        return True # Keep going


    def __NPC_leaves_PCs(self, throw_away):
        npc_name = self.__chars[self.__char_index].name
        if npc_name not in self.__world.details['NPCs']:
            self._window_manager.error(['"%s" not an NPC' % npc_name])
            return True

        if npc_name not in self.__world.details['PCs']:
            self._window_manager.error(['"%s" not in PC list' % npc_name])
            return True

        del(self.__world.details['PCs'][npc_name])
        self.__setup_PC_list(self.__current_display)
        self._draw_screen()
        return True


    def __party(self):
        sub_menu = [
                    ('monster list',       {'doit': self.__add_monsters}),
                    ('npc list',           {'doit': self.__add_NPCs}),
                    ('NPC joins PCs',      {'doit': self.NPC_joins_PCs}),
                    ('NPC leaves PCs',     {'doit': self.__NPC_leaves_PCs}),
                    ('NPC joins Monsters', {'doit': self.NPC_joins_monsters}),
                    ('pc list',            {'doit': self.__add_PCs}),
                    ]
        self._window_manager.menu('Do what', sub_menu)
        return True


    def __prev_char(self):
        if self.__char_index is None:
            self.__char_index = len(self.__chars) - 1
        else:
            self.__char_index -= 1
            if self.__char_index < 0:
                self.__char_index = len(self.__chars) - 1
        self.__first_page(MainHandler.CHAR_DETAIL)
        self._draw_screen()
        return True


    def __prev_page(self):
        if self.__current_pane == MainHandler.CHAR_DETAIL:
            self._window.scroll_char_detail_up()
        else:
            self._window.scroll_char_list_up()
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


    def __remove_equipment(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]
        self.__equipment_manager.remove_equipment(fighter)
        self._draw_screen()
        return True # Keep going


    def __remove_spell(self, throw_away):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]

        # Is the fighter a caster?
        if 'spells' not in fighter.details:
            self._window_manager.error(
                ['Doesn\'t look like %s casts spells' % fighter.name])
            return True

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            # Make the spell list again (since we've removed one)
            spell_menu = [(spell['name'], spell['name'])
                        for spell in sorted(fighter.details['spells'],
                                            key=lambda x:x['name'])]
            bad_spell_name = self._window_manager.menu('Spell to Remove',
                                                       spell_menu)

            if bad_spell_name is None:
                return True

            for index, spell in enumerate(fighter.details['spells']):
                if spell['name'] == bad_spell_name:
                    del fighter.details['spells'][index]
                    self._draw_screen()
                    break

            keep_asking = self._window_manager.menu('Remove More Spells',
                                                    keep_asking_menu)
        return True # Keep going


    def __resurrect_fight(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Ask which monster group to resurrect
        fight_name_menu = []
        for i, entry in enumerate(self.__world.details['dead-monsters']):
            fight_name_menu.append((entry['name'], i))
        monster_group_index = self._window_manager.menu('Resurrect Which Fight',
                                                        fight_name_menu)
        if monster_group_index is None:
            return True

        monster_group = self.__world.details['dead-monsters'][
                                                        monster_group_index]

        if self.__world.get_creatures(monster_group['name']) is not None:
            self._window_manager.error(['Fight by name "%s" exists' %
                                                    monster_group['name']])
            return True

        # Put fight into regular monster list
        fights = self.__world.get_fights()
        fights[monster_group['name']] = monster_group['fight']

        # Remove fight from dead-monsters
        del(self.__world.details['dead-monsters'][monster_group_index])
        return True


    def __right_pane(self):
        self.__current_pane = MainHandler.CHAR_DETAIL
        return True


    def __ruleset_ability(self,
                          param # string: ability name
                         ):
        fighter = self.__chars[self.__char_index]

        if param not in fighter.details:
            self._window_manager.error(['%s doesn\'t support' % (fighter.name,
                                                                 param)])
            return True

        #   { 
        #       'Skills':     { 'Axe/Mace': 8,      'Climbing': 8, },
        #       'Advantages': { 'Bad Tempter': -10, 'Nosy': -1, },
        #   }

        ability_menu = [(name, {'name': name, 'predicate': predicate})
            for name, predicate in self.__ruleset_abilities[param].iteritems()]


        keep_asking_menu = [('yes', True), ('no', False)]

        keep_asking = True
        while keep_asking:
            new_ability = self._window_manager.menu(('Adding %s' % param),
                                                          sorted(ability_menu))
            if new_ability is None:
                return True

            # The predicate will take one of several forms...
            # 'name': {'ask': 'number' | 'string' }
            #         {'value': value}

            result = None
            if 'ask' in new_ability['predicate']:
                if new_ability['predicate']['ask'] == 'number':
                    title = 'Value for %s' % new_ability['name']
                    width = len(title) + 2 # Margin to make it prettier
                else:
                    title = 'String for %s' % new_ability['name']
                    lines, cols = self._window.getmaxyx()
                    width = cols/2
                height = 1
                adj_string = self._window_manager.input_box(height,
                                                            width,
                                                            title)
                if adj_string is None or len(adj_string) <= 0:
                    return True

                if new_ability['predicate']['ask'] == 'number':
                    result = int(adj_string)
                else:
                    result = adj_string

            elif 'value' in new_ability['predicate']:
                result = new_ability['predicate']['value']
            else:
                result = None
                self._window_manager.error(
                    ['unknown predicate "%r" for "%s"' % 
                            (new_ability['predicate'], new_ability['name'])])

            if result is not None:
                fighter.details[param][new_ability['name']] = result
            self._draw_screen()

            keep_asking = self._window_manager.menu(('Add More %s' % param),
                                                    keep_asking_menu)
        return None if 'text' not in param else param


    def __ruleset_ability_rm(self,
                             param # string: ability name
                            ):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.__chars[self.__char_index]

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            # Make the ability list again (since we've removed one)
            ability_menu = [(ability, ability)
                        for ability in sorted(fighter.details[param].keys())]
            bad_ability_name = self._window_manager.menu(
                                        '%s to Remove' % param.capitalize(),
                                        ability_menu)

            if bad_ability_name is None:
                return True

            del fighter.details[param][bad_ability_name]
            self._draw_screen()

            keep_asking = self._window_manager.menu(
                                        'Remove More %s' % param.capitalize(),
                                        keep_asking_menu)
        return True # Keep going


    def __run_fight(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        monster_group = None
        if self._saved_fight['saved']:
            pass
        elif self.__current_display is not None:
            monster_group = self.__current_display
        else:
            fight_name_menu = [(name, name)
                                       for name in self.__world.get_fights()]
            fight_name_menu = sorted(fight_name_menu,
                                     key=lambda x: x[0].upper())
            monster_group = self._window_manager.menu('Fights',
                                                      fight_name_menu)
            if monster_group is None:
                return True

        fight = FightHandler(self._window_manager,
                             self.__world,
                             monster_group,
                             self.__ruleset,
                             self._campaign_debug_json,
                             self._input_filename)

        fight.handle_user_input_until_done()

        self.__current_display = None
        self.__setup_PC_list(self.__current_display) # The fight may have
                                                     # changed the PC/NPC lists
        self.__first_page(MainHandler.CHAR_LIST | MainHandler.CHAR_DETAIL)
        self._draw_screen() # Redraw current screen when done with the fight.

        return True # Keep going


    def __search(self):
        lines, cols = self._window.getmaxyx()
        look_for_string = self._window_manager.input_box(1,
                                                         cols-4,
                                                         'Search For What?')

        if look_for_string is None or len(look_for_string) <= 0:
            return True
        look_for_re = re.compile(look_for_string)

        all_results = []
        for name in self.__world.get_creatures('PCs'):
            creature = self.__world.get_creature_details(name, 'PCs')
            result = self.__ruleset.search_one_creature(name,
                                                        'PCs',
                                                        creature,
                                                        look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for name in self.__world.get_creatures('NPCs'):
            creature = self.__world.get_creature_details(name, 'NPCs')
            result = self.__ruleset.search_one_creature(name,
                                                        'NPCs',
                                                        creature,
                                                        look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for fight_name in self.__world.get_fights():
            for name in self.__world.get_creatures(fight_name):
                creature = self.__world.get_creature_details(name, fight_name)
                result = self.__ruleset.search_one_creature(name,
                                                            '%s' % fight_name,
                                                            creature,
                                                            look_for_re)
                if result is not None and len(result) > 0:
                    all_results.extend(result)

        if len(all_results) <= 0:
            self._window_manager.error(['"%s" not found' % look_for_string])
        else:
            lines = []
            result_menu = []

            for match in all_results:
                if 'notes' in match:
                    match_string = '%s (%s): in %s - %s' % (match['name'],
                                                            match['group'],
                                                            match['location'],
                                                            match['notes'])
                else:
                    match_string = '%s (%s): in %s' % (match['name'],
                                                       match['group'],
                                                       match['location'])

                index = None
                for i, character in enumerate(self.__chars):
                    if (character.name == match['name'] and
                                    character.group == match['group']):
                        index = i

                result_menu.append((match_string, index))

            menu_title = 'Found "%s"' % look_for_string

            select_result = self._window_manager.menu(menu_title, result_menu)
            if select_result is not None:
                self.__char_index = select_result
                self._draw_screen()

        return True


    def __setup_PC_list(self,
                        group=None):
        if group is not None:
            self.__chars = []
            monsters = self.__world.get_creatures(group)
            if monsters is not None:
                the_fight_itself = None
                for name, details in monsters.iteritems():
                    if name == Fight.name:
                        the_fight_itself = details
                    else:
                        fighter = Fighter(
                                    name,
                                    group,
                                    self.__world.get_creature_details(name,
                                                                      group),
                                    self.__ruleset,
                                    self._window_manager)
                        self.__chars.append(fighter)

                self.__chars = sorted(self.__chars, key=lambda x: x.name)

                # Add the Fight to the object array

                if len(self.__chars) == 0:
                    group = None

                # NOTE: I think we shouldn't add a fight object if one doesn't
                # exist.
                #
                #elif the_fight_itself is None:
                #    fight =  Fight(group,
                #                   self.__world.details['fights'][group],
                #                   self.__ruleset)

                elif the_fight_itself is not None:
                    fight = Fight(group,
                                  the_fight_itself,
                                  self.__ruleset,
                                  self._window_manager)
                    self.__chars.insert(0, fight)


        if group is None:
            self.__chars = [
                    Fighter(x,
                            'PCs',
                            self.__world.get_creature_details(x, 'PCs'),
                            self.__ruleset,
                            self._window_manager)
                    for x in sorted(self.__world.get_creatures('PCs'))]

            npcs = self.__world.get_creatures('NPCs')
            if npcs is not None:
                self.__chars.extend([
                        Fighter(x,
                                'NPCs',
                                self.__world.get_creature_details(x, 'NPCs'),
                                self.__ruleset,
                                self._window_manager)
                        for x in sorted(self.__world.get_creatures('NPCs'))])
        else:
            pass

        self.__char_index = 0


    def __short_notes(self, throw_away):
        return self.__notes('short-notes')


    def __timer_cancel(self, throw_away):
        '''
        Command ribbon method.
        Asks user for information for timer to add to a fighter.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        timer_recipient = self.__chars[self.__char_index]

        # Select a timer

        timers = timer_recipient.timers.get_all()
        timer_menu = [(timer.get_one_line_description(), index)
                                for index, timer in enumerate(timers)]
        index = self._window_manager.menu('Remove Which Timer', timer_menu)
        if index is None:
            return True # Keep fighting

        # Delete the timer

        timer_recipient.timers.remove_timer_by_index(index)

        self._draw_screen()

        return True # Keep fighting


    def __toggle_Monster_PC_NPC_display(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__current_display is None:
            group_menu = [(group_name, group_name)
                            for group_name in self.__world.get_fights()]
            group_menu = sorted(group_menu, key=lambda x: x[0].upper())
            self.__current_display = self._window_manager.menu(
                                                    'Which Monster Group',
                                                    group_menu)
        else:
            self.__current_display = None

        self.__setup_PC_list(self.__current_display)
        self._draw_screen()

        # If this is a monster list, run a consistency check
        #if self.__current_display is not None:
        #    monsters = self.__world.get_creatures(self.__current_display)
        #    for name in monsters:
        #        creature = self.__world.get_creature_details(
        #                                                name,
        #                                                self.__current_display)
        #        self.__ruleset.is_creature_consistent(name, creature)

        return True


class EquipmentManager(object):
    def __init__(self,
                 world,         # World object
                 window_manager # GmWindowManager object
                ):
        '''
        If you don't have a fighter object, do the following:

        # Temporarily create a 'Fighter' object just to use one of its member
        # functions.

        fighter = Fighter(self.__character['name'],
                          self.__group_name,
                          self.__character['details'],
                          self.__ruleset,
                          self._window_manager)

        '''
        self.__world = world
        self.__window_manager = window_manager

    @staticmethod
    def get_description(
                        item,           # Input: dict for a 'stuff' item from
                                        #   JSON
                        in_use_items,   # List of items that are in use.
                                        #   These should be references so that
                                        #   it will match identically to
                                        #   'item' if it is in use.
                        char_detail     # Output: recepticle for character
                                        # detail.
                                        # [[{'text','mode'},...],  # line 0
                                        #  [...],               ]  # line 1...
                       ):
        '''
        This is kind-of messed up.  Each type of equipment should have its own
        class that has its own 'get_description'.  In lieu of that, though,
        I'm going to centralize it.
        '''

        mode = curses.A_NORMAL 

        in_use_string = ' (in use)' if item in in_use_items else ''

        texts = ['  %s%s' % (item['name'], in_use_string)]
        if 'count' in item and item['count'] != 1:
            texts.append(' (%d)' % item['count'])

        if ('notes' in item and item['notes'] is not None and
                                                (len(item['notes']) > 0)):
            texts.append(': %s' % item['notes'])
        char_detail.append([{'text': ''.join(texts),
                             'mode': mode}])

        # TODO: this should be brought out into type-specific objects
        if item['type'] == 'ranged weapon':
            texts = []
            texts.append('acc: %d' % item['acc'])
            texts.append('dam(%s): %dd%+d' % (
                                          item['damage']['dice']['type'],
                                          item['damage']['dice']['num_dice'],
                                          item['damage']['dice']['plus']))
            texts.append('reload: %d' % item['reload'])
            char_detail.append([{'text': ('     ' + ', '.join(texts)),
                                 'mode': mode}])
        elif item['type'] == 'melee weapon':
            texts = []
            if 'dice' in item['damage']:
                texts.append('dam(%s): %dd%+d' % (
                                          item['damage']['dice']['type'],
                                          item['damage']['dice']['num_dice'],
                                          item['damage']['dice']['plus']))
            if 'sw' in item['damage']:
                texts.append('dam(sw): %s%+d' % (
                                          item['damage']['sw']['type'],
                                          item['damage']['sw']['plus']))
            if 'thr' in item['damage']:
                texts.append('dam(thr): %s%+d' % (
                                          item['damage']['thr']['type'],
                                          item['damage']['thr']['plus']))
            if 'parry' in item:
                texts.append('parry: %d' % item['parry'])

            char_detail.append([{'text': ('     ' + ', '.join(texts)),
                                 'mode': mode}])
        elif item['type'] == 'armor':
            texts = []
            texts.append('dr: %d' % item['dr'])
            char_detail.append([{'text': ('     ' + ', '.join(texts)),
                                 'mode': mode}])

        if ('owners' in item and item['owners'] is not None and
                                                    len(item['owners']) > 0):
            texts = ['     Owners: ']
            texts.append('%s' % '->'.join(item['owners']))
            char_detail.append([{'text': ''.join(texts),
                                 'mode': mode}])

    #
    # Public Methods
    #

    def add_equipment(self,
                      fighter,      # Fighter object
                      item = None   # dict
                     ):
        '''
        Transfer an item of equipment from the store to a fighter.  Ask the
        user which item.
        '''
        if fighter is None:
            return

        # Pick an item off the shelf

        # Rebuild this every time in case there are unique items in the
        # equipment list
        item_menu = [(item['name'], item)
                            for item in self.__world.details['stuff']]
        item_menu = sorted(item_menu, key=lambda x: x[0].upper())
        item = self.__window_manager.menu('Item to Add', item_menu)
        if item is not None:
            source = None
            if item['owners'] is not None and len(item['owners']) == 0:
                source = 'the store'

            fighter.add_equipment(copy.deepcopy(item), source)


    def remove_equipment(self,
                         fighter       # Fighter object
                        ):
        if fighter is None:
            return

        item_menu = [(item['name'], index)
                    for index, item in enumerate(fighter.details['stuff'])]
        item_index = self.__window_manager.menu('Item to Remove', item_menu)
        if item_index is None:
            return None

        return fighter.remove_equipment(item_index)



class MyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2) 


def timeStamped(fname, tag, ext, fmt='{fname}-%Y-%m-%d-%H-%M-%S{tag}.{ext}'):
    tag = '' if tag is None else ('-%s' % tag)
    return datetime.datetime.now().strftime(fmt).format(fname=fname,
                                                        tag=tag,
                                                        ext=ext)


def are_equal(self, lhs, rhs):
    if isinstance(lhs, dict):
        if not isinstance(rhs, dict):
            return False
        for key in rhs.iterkeys():
            if key not in lhs:
                return False
        are_equal = True
        for key in lhs.iterkeys():
            if key not in rhs:
                are_equal = False
            elif not self.__are_equal(lhs[key], rhs[key]):
                are_equal = False
        return are_equal
            
    elif isinstance(lhs, list):
        if not isinstance(rhs, list):
            return False
        if len(lhs) != len(rhs):
            return False
        are_equal = True
        for i in range(len(lhs)):
            if not self.__are_equal(lhs[i], rhs[i]):
                are_equal = False
        return are_equal

    else:
        if lhs != rhs:
            return False
        else:
            return True

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

            # Error check the JSON
            if 'PCs' not in campaign.read_data:
                window_manager.error(['No "PCs" in %s' % filename])
                sys.exit(2)

            world = World(campaign, ruleset, window_manager)

            # Save the state of things when we leave since there wasn't a
            # horrible crash while reading the data.
            if ARGS.maintainjson:
                world.dont_save_on_exit()
            else:
                world.do_save_on_exit()

            if campaign.read_data['current-fight']['saved']:
                fight_handler = FightHandler(window_manager,
                                             world,
                                             None,
                                             ruleset,
                                             world.campaign_debug_json,
                                             filename)
                fight_handler.handle_user_input_until_done()

            # Enter into the mainloop
            main_handler = MainHandler(window_manager,
                                       world,
                                       ruleset,
                                       world.campaign_debug_json,
                                       filename)

            main_handler.handle_user_input_until_done()

