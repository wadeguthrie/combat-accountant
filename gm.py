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
#   - Need way to 'P'romote bad guy to NPC status
#   - Fights should have their own equipment
#   - add laser sights to weapons

#   - add ability to undo the -m option

#   - add a timer that is tied to the round change
#   - should warn when trying to do a second action (take note of fastdraw)
#
# TODO (eventually):
#   - add ability to edit any creature
#   - should only be able to ready an unready weapon.
#   - Add 2 weapon (or weapon & shield)
#   - Allow for markdown in 'notes' and 'short-notes'
#   - On startup, check each of the characters
#       o eventually, there needs to be a list of approved skills &
#         advantages; characters' data should only match the approved list
#         (this is really to make sure that stuff wasn't mis-typed).
#   - reloading where the number of shots is in the 'clip' (like with a gun or
#     a quiver) rather than in the weapon (like in disruptors or lasers)
#   - plusses on range-based ammo (a bullet with a spell on it, for instance)
#   - Go for a transactional model -- will allow me to do better debugging,
#       playback of debug stuff, and testing.  Instead of modifying 'world'
#       directly, issue a transaction to an object that handles world.  Save
#       the transaction to _history.
#   - Optimize the way I'm using curses.  I'm willy-nilly touching and
#     redrawing everything way more often than I should.  Turns out, it's not
#     costing me much but it's ugly, none-the-less

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
        self.__char_detail = [] # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        top_line = 1
        height = (lines                 # The whole window height, except...
            - top_line                  # ...a block at the top, and...
            - 4)                        # ...a space for the command ribbon.
        
        width = (cols / 2) - 1 # -1 for margin

        self.__char_list_window = GmScrollableWindow(
                                                 self.__char_list,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 1)
        self.__char_detail_window  = GmScrollableWindow(
                                                 self.__char_detail,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 width)

    def close(self):
        # Kill my subwindows, first
        if self.__char_list_window is not None:
            del self.__char_list_window
            self.__char_list_window = None
        if self.__char_detail_window is not None:
            del self.__char_detail_window
            self.__char_detail_window = None
        super(MainGmWindow, self).close()


    def refresh(self):
        super(MainGmWindow, self).refresh()
        if self.__char_list_window is not None:
            self.__char_list_window.refresh()
        if self.__char_detail_window is not None:
            self.__char_detail_window.refresh()

    def scroll_char_detail_down(self):
        self.__char_detail_window.scroll_down()
        self.__char_detail_window.draw_window()
        self.__char_detail_window.refresh()

    def scroll_char_detail_up(self):
        self.__char_detail_window.scroll_up()
        self.__char_detail_window.draw_window()
        self.__char_detail_window.refresh()

    def show_character_detail(self,
                              character, # dict as found in the JSON
                              ruleset
                             ):
        self.__char_detail_window.clear()
        if character is None:
            self.refresh()
            return

        del self.__char_detail[:]
        ruleset.get_character_detail(character, self.__char_detail)

        # ...and show the screen

        self.__char_detail_window.draw_window()
        self.__char_detail_window.refresh()


    def show_character_list(self,
                            char_list,  # [ {'name': xxx,
                                        #    'group': xxx,
                                        #    'details':xxx}, ...
                            current_index,
                            standout = False
                           ):
        del self.__char_list[:]

        if char_list is None:
            self.__char_list_window.draw_window()
            self.refresh()
            return

        for line, char in enumerate(char_list):
            mode = curses.A_REVERSE if standout else 0
            if char['group'] == 'NPCs':
                mode |= curses.color_pair(GmWindowManager.CYAN_BLACK)
            else:
                mode |= self._window_manager.get_mode_from_fighter_state(
                                    Fighter.get_fighter_state(char['details']))

            mode |= (curses.A_NORMAL if current_index is None or
                                       current_index != line
                                    else curses.A_STANDOUT)

            self.__char_list.append([{'text': char['name'], 
                                      'mode': mode}])

        self.__char_list_window.draw_window()
        self.refresh()


    def touchwin(self):
        super(MainGmWindow, self).touchwin()
        if self.__char_list_window is not None:
            self.__char_list_window.touchwin()
        if self.__char_detail_window is not None:
            self.__char_detail_window.touchwin()



class BuildFightGmWindow(GmWindow):
    def __init__(self, window_manager):
        super(BuildFightGmWindow, self).__init__(window_manager,
                                                 curses.LINES,
                                                 curses.COLS,
                                                 0,
                                                 0)
        lines, cols = self._window.getmaxyx()
        self.__char_detail = [] # [[{'text', 'mode'}, ...],   # line 0
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
        self.__char_detail_window  = GmScrollableWindow(
                                                 self.__char_detail,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 width+1)

    def close(self):
        #print '  BuildFightGmWindow::close' # TODO: remove
        # Kill my subwindows, first
        if self.__char_list_window is not None:
            del self.__char_list_window
            self.__char_list_window = None
        if self.__char_detail_window is not None:
            del self.__char_detail_window
            self.__char_detail_window = None
        super(BuildFightGmWindow, self).close()


    def refresh(self):
        #print '  BuildFightGmWindow::refresh' # TODO: remove
        super(BuildFightGmWindow, self).refresh()
        if self.__char_list_window is not None:
            self.__char_list_window.refresh()
        if self.__char_detail_window is not None:
            self.__char_detail_window.refresh()

    def scroll_char_detail_down(self):
        #print '  ** BuildFightGmWindow::scroll_char_detail_down' # TODO: remove
        self.__char_detail_window.scroll_down()
        self.__char_detail_window.draw_window()
        self.__char_detail_window.refresh()

    def scroll_char_detail_up(self):
        #print '  ** BuildFightGmWindow::scroll_char_detail_up' # TODO: remove
        self.__char_detail_window.scroll_up()
        self.__char_detail_window.draw_window()
        self.__char_detail_window.refresh()

    def show_character_detail(self,
                              character, # dict as found in the JSON
                              ruleset
                             ):
        #print '  BuildFightGmWindow::show_character_detail' # TODO: remove
        self.__char_detail_window.clear()
        if character is None:
            self.refresh()
            return

        del self.__char_detail[:]
        ruleset.get_character_detail(character, self.__char_detail)

        # ...and show the screen

        self.__char_detail_window.touchwin() # TODO: needed?
        self.__char_detail_window.draw_window()
        self.__char_detail_window.refresh()

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

    def show_creatures(self,
                       old_creatures,   # {name: {details}, ...} like in JSON
                       new_creatures,   # {name: {details}, ...} like in JSON
                       new_char_name    # name of character to highlight
                      ):

        #self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
        #                        #  [...],                  ]  # line 1...

        self.__char_list_window.clear()
        del self.__char_list[:]

        mode = curses.A_NORMAL
        line = 0
        if old_creatures is not None:
            for old_name in sorted(old_creatures.keys()):
                self.__char_list.append([{'text': old_name, 'mode': mode}])

            # Blank line between old creatures and new
            self.__char_list.append([{'text': '', 'mode': mode}])

        for new_name in sorted(new_creatures.keys()):
            now_mode = mode
            if new_char_name is not None and new_name == new_char_name:
                now_mode |= curses.A_REVERSE
            self.__char_list.append([{'text': new_name, 'mode': now_mode}])
            line += 1

        # ...and show the screen

        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()

        self.refresh() # TODO: needed?

    def touchwin(self):
        super(BuildFightGmWindow, self).touchwin()
        if self.__char_list_window is not None:
            self.__char_list_window.touchwin()
        if self.__char_detail_window is not None:
            self.__char_detail_window.touchwin()

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


    def __show_summary_window(self,
                              fighters,  # array of <Fighter object>
                              current_index,
                              selected_index=None):
        self.__summary_window.clear()
        for line, fighter in enumerate(fighters):
            mode = self._window_manager.get_mode_from_fighter_state(
                                                        fighter.get_state())
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
        fighter_string = '%s HP: %d/%d FP: %d/%d' % (
                                    fighter.name,
                                    fighter.details['current']['hp'],
                                    fighter.details['permanent']['hp'],
                                    fighter.details['current']['fp'],
                                    fighter.details['permanent']['fp'])

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
        if fighter_state == Fighter.DEAD:
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

        notes, ignore = self.__ruleset.get_fighter_defenses_notes(fighter,
                                                                  opponent)
        for note in notes:
            window.addstr(line, 0, note, mode)
            line += 1

        # Attacker

        if is_attacker:
            mode = curses.color_pair(GmWindowManager.CYAN_BLACK)
            mode = mode | curses.A_BOLD
        else:
            mode = curses.A_NORMAL 
        notes = self.__ruleset.get_fighter_to_hit_damage_notes(fighter,
                                                               opponent)
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
            if 'string' in timer:
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

        if ('short-notes' in fighter.details and 
                                fighter.details['short-notes'] is not None):
            for note in fighter.details['short-notes']:
                window.addstr(line, 0, note, mode)
                line += 1

        window.refresh()


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

    def show_character(self,
                       character # dict: {'name': None, 'details': None}
                      ):
        # TODO (move to ruleset): this is ruleset specific
        self.__outfit_window.clear()
        if character['name'] is None:
            self.refresh()
            return

        line = 0
        mode = curses.color_pair(GmWindowManager.GREEN_BLACK) | curses.A_BOLD
        self.__outfit_window.addstr(line, 0, '%s' % character['name'], mode)
        line += 1

        if character['details'] is None:
            self.refresh()
            return

        mode = curses.A_NORMAL 
        self.__outfit_window.addstr(line, 0, 'Equipment', mode | curses.A_BOLD)
        line += 1
        found_stuff = False
        for item in character['details']['stuff']:
            found_stuff = True

            # TODO: equipment must have an object with a 'show me' method
            #   that method would give weapon and armor details
            texts = ['%s' % item['name']]
            if 'count' in item and item['count'] != 1:
                texts.append(' (%d)' % item['count'])

            if ('notes' in item and item['notes'] is not None and
                                                    (len(item['notes']) > 0)):
                texts.append(': %s' % item['notes'])

            self.__outfit_window.addstr(line, 0, '  %s' % ''.join(texts), mode)
            line += 1
            if item['owners'] is not None and len(item['owners']) > 0:
                texts = ['Owners: ']
                texts.append('%s' % '->'.join(item['owners']))
                self.__outfit_window.addstr(line,
                                            0,
                                            '    %s' % ''.join(texts),
                                            mode)
                line += 1

        if not found_stuff:
            self.__outfit_window.addstr(line, 0, '  (Nothing)', mode)
            line += 1

        mode = curses.A_NORMAL 
        self.__outfit_window.addstr(line, 0, 'Skills', mode | curses.A_BOLD)
        line += 1
        found_skill = False
        for skill, value in character['details']['skills'].iteritems():
            found_skill = True
            self.__outfit_window.addstr(line,
                                        0,
                                        '  %s: %d' % (skill, value),
                                        mode)
            line += 1

        if not found_skill:
            self.__outfit_window.addstr(line, 0, '  (Nothing)', mode)
            line += 1

        self.refresh()


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

    def get_mode_from_fighter_state(self,
                                    state # from STATE_COLOR
                                   ):
        return self.STATE_COLOR[state]


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

    def get_outfit_gm_window(self):
        return OutfitCharactersGmWindow(self)

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
        '''

        if len(strings_results) < 1: # if there's no choice, say so
            return None
        if len(strings_results) == 1: # if there's only 1 choice, autoselect it
            return strings_results[0][1]

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
            data_for_scrolling.append([{'text': entry[0],
                                        'mode': mode}])
        border_win, menu_win = self.__centered_boxed_window(
                                        height,
                                        width,
                                        title,
                                        data_for_scrolling=data_for_scrolling)
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
                return strings_results[index][1]
            elif user_input == GmWindowManager.ESCAPE:
                del border_win
                del menu_win
                self.hard_refresh_all()
                return None
            else:
                # Look for a match and return the selection
                # TODO: this won't work on page 2, etc.
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
                                mode=curses.A_NORMAL,
                                data_for_scrolling=None
                               ):
        '''
        Creates a temporary window, on top of the current one, that is
        centered and has a box around it.
        '''
        box_margin = 2

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

    def touchwin(self):
        self.__window.touchwin()


class World(object):
    def __init__(self,
                 world_details,  # dict from entire JSON
                 window_manager  # a GmWindowManager object to handle I/O
                ):
        self.details = world_details
        self.__window_manager = window_manager

    def get_creature_details(self, name, group):
        if name is None or group is None:
            self.__window_manager.error(
                ['Name: %r or group: %r is "None"' % (name, group)])
            return None

        if group == 'PCs':
            details = self.details['PCs'][name]
        elif group == 'NPCs':
            details = self.details['NPCs'][name]
        else:
            if group not in self.details['monsters']:
                self.__window_manager.error(
                    ['No "%s" group in "monsters"' % group])
                return None

            if name not in self.details['monsters'][group]:
                self.__window_manager.error(
                    ['No name "%s" in monster group "%s"' % (name, group)])
                return None

            details = self.details['monsters'][group][name]

        if 'redirect' in details:
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

    def get_list(self,
                 group_name  # 'PCs', 'NPCs', or a monster group
                ):
        '''
        Used to get PCs, NPCs, or monsters.
        '''

        if group_name in self.details:
            return self.details[group_name]

        if group_name in self.details['monsters']:
            return self.details['monsters'][group_name]

        return None

    def get_random_name(self):
        if self.details['Names'] is None:
            self.__window_manager.error(
                                    ['There are no "Names" in the database'])
            return None, None, None

        type_menu = [(x, x) for x in self.details['Names']]
        type_name = self.__window_manager.menu('What kind of name', type_menu)
        if type_name is None:
            type_name = random.choice(self.details['Names'].keys())
            gender_name = random.choice(
                            self.details['Names'][type_name].keys())

        else:
            gender_menu = [(x, x)
                   for x in self.details['Names'][type_name]]
            gender_name = self.__window_manager.menu('What Gender', gender_menu)
            if gender_name is None:
                gender_name = random.choice(
                                self.details['Names'][type_name].keys())

        index = random.randint(0,
            len(self.details['Names'][type_name][gender_name]) - 1)

        return (self.details['Names'][type_name][gender_name][index],
                type_name,
                gender_name)



class Fighter(object):
    # Injured is separate since it's tracked by HP
    (ALIVE,
     UNCONSCIOUS,
     DEAD,
     STATES,    # States after this aren't in the 'bump_consciousness' cycle

     INJURED,
     ABSENT) = range(6)

    conscious_map = {
        'alive': ALIVE,
        'unconscious': UNCONSCIOUS,
        'dead': DEAD,
        'absent': ABSENT,
    }

    def __init__(self,
                 name,              # string
                 group,             # string = 'PCs' or some monster group
                 fighter_details,   # dict as in the JSON
                 ruleset,           # a Ruleset object
                 window_manager     # a GmWindowManager object
                ):
        self.name = name
        self.group = group
        self.details = fighter_details
        self.__ruleset = ruleset
        self.__window_manager = window_manager

    def add_equipment(self,
                      new_item,   # dict describing new equipment
                      source=None # string describing where equipment came from
                     ):
        # TODO: test source names
        if source is not None and new_item['owners'] is not None:
            new_item['owners'].append(source)

        for item in self.details['stuff']:
            if item['name'] == new_item['name']:
                if self.__is_same_thing(item, new_item):
                    item['count'] += new_item['count']
                    return
                break

        self.details['stuff'].append(new_item)

    def add_timer(self,
                  rounds,           # rounds until timer fires (3.0 rounds
                                    #   fires at end of 3 rounds; 2.9 rounds
                                    #   fires at beginning of 3 rounds.
                  text,             # string to display (in fighter's notes)
                                    #   while timer is running
                  announcement=None # string to display (in its own window)
                                    #   when timer fires
                 ):
        timer = {'rounds': rounds,
                 'string': text}
        if announcement is not None:
            timer['announcement'] = announcement

        self.details['timers'].append(timer)


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

    def can_finish_turn(self):
        # TODO (move to ruleset): actions are ruleset-based.
        if self.details['did_action_this_turn'] or not self.is_conscious():
            return True
        return False


    def decrement_timers(self):
        for timer in self.details['timers']:
            timer['rounds'] -= 1


    # TODO (move to ruleset): do_aim is ruleset-based.
    def do_aim(self,
               braced   # True | False
              ):
        rounds = self.details['aim']['rounds']
        if rounds == 0:
            self.details['aim']['braced'] = braced
            self.details['aim']['rounds'] = 1
        elif rounds < 3:
            self.details['aim']['rounds'] += 1

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


    def end_turn(self):
        self.__ruleset.end_turn(self)
        self.remove_expired_kill_dying_timers()


    def get_current_armor(self):
        armor_index = self.details['armor-index']
        if armor_index is None:
            return None, None
        return self.details['stuff'][armor_index], armor_index


    def get_current_weapon(self):
        weapon_index = self.details['weapon-index']
        if weapon_index is None:
            return None, None
        return self.details['stuff'][weapon_index], weapon_index


    @staticmethod
    def get_fighter_state(details):
        conscious_number = Fighter.conscious_map[details['state']]
        if (conscious_number == Fighter.ALIVE and 
                        details['current']['hp'] < details['permanent']['hp']):
            return Fighter.INJURED
        return conscious_number

    def get_state(self):
        return Fighter.get_fighter_state(self.details)


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


    def is_conscious(self):
        # NOTE: 'injured' is not stored in self.details['state']
        return True if self.details['state'] == 'alive' else False


    def is_dead(self):
        return True if self.details['state'] == 'dead' else False

    def is_absent(self):
        return True if self.details['state'] == 'absent' else False

    def perform_action_this_turn(self):
        # TODO (move to ruleset): actions are ruleset-based.
        self.details['did_action_this_turn'] = True

    def remove_expired_keep_dying_timers(self):
        '''
        Removes timers but keep the timers that are dying this round.  Call
        this at the beginning of the round.  Standard timers that die this
        round are kept so that they're shown.
        '''

        remove_these = []
        for index, timer in enumerate(self.details['timers']):
            if timer['rounds'] < 0:     # < keeps the timers dying this round
                remove_these.insert(0, index) # largest indexes last
        for index in remove_these:
            self.__fire_timer(self.details['timers'][index])
            del self.details['timers'][index]


    def remove_expired_kill_dying_timers(self):
        '''
        Removes timers and kills the timers that are dying this round.  Call
        this at the end of the round to scrape off the timers that expire this
        round.
        '''
        # Remove any expired timers
        remove_these = []
        for index, timer in enumerate(self.details['timers']):
            if timer['rounds'] <= 0:    # <= kills the timers dying this round
                remove_these.insert(0, index) # largest indexes last
        for index in remove_these:
            self.__fire_timer(self.details['timers'][index])
            del self.details['timers'][index]

    def reset_aim(self):
        # TODO (move to ruleset): do_aim is ruleset-based.
        self.details['aim']['rounds'] = 0
        self.details['aim']['braced'] = False


    def start_fight(self):
        # NOTE: we're allowing health to still be messed-up, here
        self.details['state'] = 'alive'
        self.details['timers'] = []
        self.details['weapon-index'] = None
        # NOTE: person may go around wearing armor -- no need to reset
        self.details['opponent'] = None
        self.start_turn()
        self.__ruleset.start_fight(self)


    def start_turn(self):
        self.__ruleset.start_turn(self)
        self.decrement_timers()
        self.remove_expired_keep_dying_timers()


    def __fire_timer(self, timer):

        if 'state' in timer:
            self.details['state'] = timer['state']
        if 'announcement' in timer:
            self.__window_manager.display_window(
                                       ('Timer Fired for %s' % self.name),
                                        [[{'text': timer['announcement'],
                                           'mode': curses.A_NORMAL }]])


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

    def search_one_creature(self,
                            name,       # string containing the name
                            group,      # string containing the group
                            creature,   # dict describing the creature
                            look_for_re # compiled Python regex
                           ):
        result = []

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

    # Posture: B551; 'attack' is melee, 'target' is ranged
    posture = {
        'standing':  {'attack':  0, 'defense':  0, 'target':  0},
        'crouching': {'attack': -2, 'defense':  0, 'target': -2},
        'kneeling':  {'attack': -2, 'defense': -2, 'target': -2},
        'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        'sitting':   {'attack': -2, 'defense': -2, 'target': -2},
        'lying':     {'attack': -4, 'defense': -3, 'target': -2},
    }

    (MAJOR_WOUND_SUCCESS,
     MAJOR_WOUND_SIMPLE_FAIL,
     MAJOR_WOUND_BAD_FAIL) = range(3)

    def __init__(self, window_manager):
        super(GurpsRuleset, self).__init__(window_manager)


    def adjust_hp(self,
                  fighter,  # Fighter object
                  adj       # the number of HP to gain or lose
                 ):
        if adj < 0:
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
                if 'high pain threshold' in fighter.details['advantages']:
                    total = fighter.details['current']['ht'] + 3
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT+3 (%d) or be stunned' %
                                                                        total)
                elif 'low pain threshold' in fighter.details['advantages']:
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
                    self.change_posture({'fighter': fighter,
                                         'posture': 'lying'})
                    fighter.draw_weapon_by_index(None)
                    fighter.details['stunned'] = True

        if 'high pain threshold' not in fighter.details['advantages']: # B59
            shock_amount = -4 if adj <= -4 else adj
            if fighter.details['shock'] > shock_amount:
                fighter.details['shock'] = shock_amount

        # WILL roll or lose aim
        if fighter.details['aim']['rounds'] > 0:
            aim_menu = [('made WILL roll', True),
                        ('did NOT make WILL roll', False)]
            made_will_roll = self._window_manager.menu(
                ('roll <= WILL (%d) or lose aim' %
                                            fighter.details['current']['wi']),
                aim_menu)
            if not made_will_roll:
                fighter.reset_aim()

        super(GurpsRuleset, self).adjust_hp(fighter, adj)

    def cast_spell(self,
                       param, # dict {'fighter': <Fighter object>,
                              #       'spell': <index in 'spells'>}
                      ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''

        fighter = param['fighter']
        spell_index = param['spell']
        spell = fighter.details['spells'][spell_index]

        if spell['cost'] is None:
            title = 'Cost to cast (%s) - see (%s) ' % (spell['name'],
                                                       spell['notes'])
            height = 1
            width = len(title)
            cost_string = ''
            while len(cost_string) <= 0:
                cost_string = self._window_manager.input_box(height,
                                                             width,
                                                             title)
            cost = int(cost_string)
        else:
            cost = spell['cost']

        # M8 - High skill level costs less
        skill = spell['skill'] - 15
        while skill >= 0:
            cost -= 1
            skill -= 5
        if cost < 0:
            cost = 0

        fighter.details['current']['fp'] -= cost
        fighter.add_timer(spell['time'] - 0.1,  # -0.1 so that it doesn't show
                                                # up on the first round you
                                                # can do something after you
                                                # cast
                          'Casting (%s) @ skill (%d): %s' % (spell['name'],
                                                             spell['skill'],
                                                             spell['notes']))


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

    def do_maneuver(self, fighter):
        fighter.perform_action_this_turn()

    def end_turn(self, fighter):
        fighter.details['shock'] = 0
        if fighter.details['stunned']:
            stunned_menu = [('Succeeded (roll <= HT)', True),
                            ('Missed roll', False),]
            recovered_from_stun = self._window_manager.menu(
                            'Stunned: Roll <= HT (%d) to recover' % 
                                            fighter.details['current']['ht'],
                            stunned_menu)
            if recovered_from_stun:
                fighter.details['stunned'] = False

    def get_action_menu(self,
                        fighter # Fighter object
                       ):
        ''' Builds the menu of maneuvers allowed for the fighter. '''

        action_menu = []

        move = fighter.details['current']['basic-move']

        if fighter.details['stunned']:
            action_menu.append(
                ('do nothing (stunned)', {'text': ['Do Nothing (Stunned)',
                                                   ' Defense: any @-4',
                                                   ' Move: none'],
                                          'doit': None}
                )
            )
            return action_menu


        # Figure out who we are and what we're holding.

        weapon, weapon_index = fighter.get_current_weapon()
        holding_ranged = (False if weapon is None else
                                (weapon['type'] == 'ranged weapon'))

        # Draw weapon SUB-menu

        draw_weapon_menu = []   # list of weapons that may be drawn this turn
        for index, item in enumerate(fighter.details['stuff']):
            if (item['type'] == 'ranged weapon' or
                    item['type'] == 'melee weapon' or
                    item['type'] == 'shield'):
                if weapon is None or weapon_index != index:
                    draw_weapon_menu.append(
                        (item['name'], {'text': [('draw %s' % item['name']),
                                                  ' Defense: any',
                                                  ' Move: step'],
                                        'doit': self.draw_weapon,
                                        'param': {'weapon': index,
                                                  'fighter': fighter}
                                       }
                        )
                    )

        # Armor SUB-menu

        armor, armor_index = fighter.get_current_armor()
        don_armor_menu = []   # list of weapons that may be drawn this turn
        for index, item in enumerate(fighter.details['stuff']):
            if item['type'] == 'armor':
                if armor is None or armor_index != index:
                    don_armor_menu.append((item['name'],
                                        {'text': [('Don %s' % item['name']),
                                                  ' Defense: none',
                                                  ' Move: none'],
                                         'doit': self.don_armor,
                                         'param': {'armor': index,
                                                   'fighter': fighter}}))

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
                                 'doit': self.change_posture,
                                 'param': {'fighter': fighter,
                                           'posture': posture}}))

        # Use SUB-menu

        use_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if item['count'] > 0:
                use_menu.append((item['name'],
                                    {'text': [('Use %s' % item['name']),
                                              ' Defense: (depends)',
                                              ' Move: (depends)'],
                                     'doit': self.use_item,
                                     'param': {'item': index,
                                               'fighter': fighter}}))

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
                                         'doit': self.do_aim,
                                         'param': {'fighter': fighter,
                                                   'braced': False}})
                                      )

                # NOTE: Can only attack with a ranged weapon if there are still
                # shots in the gun.

                # Can only attack if there's someone to attack
                if fighter.details['opponent'] is not None:
                    action_menu.extend([
                        ('attack',          {'text': ['Attack',
                                                      ' Defense: any',
                                                      ' Move: step'],
                                             'doit': self.__do_attack,
                                             'param': fighter}),
                        ('attack, all out', {'text': ['All out attack',
                                                      ' Defense: none',
                                                      ' Move: 1/2 = %d' %
                                                                    (move/2)],
                                             'doit': self.__do_attack,
                                             'param': fighter})
                    ])
        else:
            # Can only attack if there's someone to attack
            if fighter.details['opponent'] is not None:
                action_menu.extend([
                        ('attack',          {'text': ['Attack',
                                                        ' Defense: any',
                                                        ' Move: step'],
                                             'doit': self.__do_attack,
                                             'param': fighter}),
                        ('attack, all out', {'text': ['All out attack',
                                                     ' Defense: none',
                                                     ' Move: 1/2 = %d' %
                                                                    (move/2)],
                                             'doit': self.__do_attack,
                                             'param': fighter})
                ])

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
                                        'doit': None}),
            ('Defense, all out',       {'text': ['All out defense',
                                                 ' Defense: double',
                                                 ' Move: step'],
                                        'doit': self.do_defense,
                                        'param': fighter}),
        ])

        # Spell casters.

        if 'spells' in fighter.details:
            spell_menu = []
            for index, spell in enumerate(fighter.details['spells']):
                cast_text_array = ['%s -' % spell['name']]
                for piece in ['cost', 'skill', 'time', 'notes']:
                    if piece in spell:
                        cast_text_array.append('%s:%r' % (piece, spell[piece]))
                cast_text = ' '.join(cast_text_array)
                spell_menu.append(  
                    (cast_text,
                    {'text': [('Cast (%s)' % spell['name']),
                              ' Defense: none',
                              ' Move: none'],
                     'doit': self.cast_spell,
                     'param': {'spell': index,
                               'fighter': fighter}}))

            action_menu.append(('cast Spell',
                                {'text': ['Cast Spell',
                                          ' Defense: none',
                                          ' Move: none'],
                                 'menu': spell_menu}))

        # TODO: should only be able to ready an unready weapon.

        if len(draw_weapon_menu) == 1:
            action_menu.append(
                (('draw (ready, etc.; B325, B366, B382) %s' %
                                                draw_weapon_menu[0][0]),
                 {'text': ['Ready (draw, etc.)',
                           ' Defense: any',
                           ' Move: step'],
                  'doit': self.draw_weapon,
                  'param': {'weapon': draw_weapon_menu[0][1]['param']['weapon'],
                            'fighter': fighter}}))

        elif len(draw_weapon_menu) > 1:
            action_menu.append(('draw (ready, etc.; B325, B366, B382)',
                                {'text': ['Ready (draw, etc.)',
                                          ' Defense: any',
                                          ' Move: step'],
                                 'menu': draw_weapon_menu}))

        # Use stuff
        if len(use_menu) == 1:
            action_menu.append(
                (('use %s' % use_menu[0][0]),
                 {'text': ['Use Item',
                           ' Defense: (depends)',
                           ' Move: (depends)'],
                  'doit': self.use_item,
                  'param': {'item': use_menu[0][1]['param']['item'],
                            'fighter': fighter}}))

        elif len(use_menu) > 1:
            action_menu.append(('use item',
                                {'text': ['Use Item',
                                          ' Defense: (depends)',
                                          ' Move: (depends)'],
                                 'menu': use_menu}))

        # Armor

        if len(don_armor_menu) == 1:
            action_menu.append(
                (('Don %s' % don_armor_menu[0][0]),
                 {'text': ['Don Armor',
                           ' Defense: none',
                           ' Move: none'],
                  'doit': self.don_armor,
                  'param': {'armor': don_armor_menu[0][1]['param']['armor'],
                            'fighter': fighter}}))

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
                                    'doit': self.don_armor,
                                    'param': {'armor': None,
                                              'fighter': fighter}}))

        action_menu.append(('evaluate (B364)', {'text': ['Evaluate',
                                                         ' Defense: any',
                                                         ' Move: step'],
                                                'doit': None}))

        # Can only feint with a melee weapon
        if weapon is not None and holding_ranged == False:
            action_menu.append(('feint (B365)',
                                           {'text': ['Feint',
                                                     ' Defense: any, parry *',
                                                     ' Move: step'],
                                            'doit': None}))

        if weapon is not None:
            action_menu.append((('holster/sheathe %s' % weapon['name']), 
                                   {'text': [('Unready %s' % weapon['name']),
                                             ' Defense: any',
                                             ' Move: step'],
                                    'doit': self.draw_weapon,
                                    'param': {'weapon': None,
                                              'fighter': fighter}}))

        
        if (fighter.details['current']['fp'] <
                        (fighter.details['permanent']['fp'] / 3)):
            move_string = 'half=%d (FP:B426)' % (move/2)
        else:
            move_string = 'full=%d' % move

        action_menu.extend([
            ('move (B364) %s' % move_string,
                                       {'text': ['Move',
                                                 ' Defense: any',
                                                 ' Move: %s' % move_string],
                                        'doit': None}),
            ('Move and attack (B365)', {'text': ['Move & Attack',
                                                 ' Defense: Dodge,block',
                                                 ' Move: %s' % move_string],
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
            ('wait (B366)',    {'text': ['Wait',
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

        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

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

    def get_character_detail(self,
                             character,   # dict as found in the JSON
                             char_detail, # recepticle for character detail.
                                          # [[{'text','mode'},...],  # line 0
                                          #  [...],               ]  # line 1...
                            ):

        # attributes

        mode = curses.A_NORMAL 
        char_detail.append([{'text': 'Attributes',
                             'mode': mode | curses.A_BOLD}])
        found_one = False
        pieces = []

        first_row = ['iq', 'st', 'ht', 'dx']
        for row in range(2):
            found_one_this_row = False
            for item_key in character['permanent'].iterkeys():
                in_first_row = item_key in first_row
                if row == 0 and not in_first_row:
                    continue
                if row != 0 and in_first_row:
                    continue
                leader = '' if found_one_this_row else '  '
                text = '%s%s:%d/%d' % (leader,
                                       item_key,
                                       character['current'][item_key],
                                       character['permanent'][item_key])
                if (character['current'][item_key] == 
                                            character['permanent'][item_key]):
                    mode = curses.A_NORMAL
                else:
                    mode = (curses.color_pair(GmWindowManager.YELLOW_BLACK) |
                                                                curses.A_BOLD)

                pieces.append({'text': '%s ' % text, 'mode': mode})
                found_one = True
                found_one_this_row = True

            if found_one_this_row:
                char_detail.append(copy.deepcopy(pieces))
                del pieces[:]

        if not found_one:
            char_detail.append([{'text': '  (None)',
                                 'mode': mode}])

        # stuff

        mode = curses.A_NORMAL 
        char_detail.append([{'text': 'Equipment',
                             'mode': mode | curses.A_BOLD}])

        found_one = False
        for item in character['stuff']:
            found_one = True
            texts = ['  %s' % item['name']]
            if 'count' in item and item['count'] != 1:
                texts.append(' (%d)' % item['count'])

            if ('notes' in item and item['notes'] is not None and
                                                    (len(item['notes']) > 0)):
                texts.append(': %s' % item['notes'])
            char_detail.append([{'text': ''.join(texts),
                                 'mode': mode}])

            if item['owners'] is not None and len(item['owners']) > 0:
                texts = ['    Owners: ']
                texts.append('%s' % '->'.join(item['owners']))
                char_detail.append([{'text': ''.join(texts),
                                     'mode': mode}])

        if not found_one:
            char_detail.append([{'text': '  (None)',
                                 'mode': mode}])

        # advantages

        mode = curses.A_NORMAL 
        char_detail.append([{'text': 'Advantages',
                             'mode': mode | curses.A_BOLD}])

        found_one = False
        for advantage, value in sorted(character['advantages'].iteritems(),
                                       key=lambda (k,v): (k, v)):
            found_one = True
            char_detail.append([{'text': '  %s: %d' % (advantage, value),
                                 'mode': mode}])

        if not found_one:
            char_detail.append([{'text': '  (None)',
                                 'mode': mode}])

        # skills

        mode = curses.A_NORMAL 
        char_detail.append([{'text': 'Skills',
                             'mode': mode | curses.A_BOLD}])

        found_one = False
        for skill, value in sorted(character['skills'].iteritems(),
                                   key=lambda (k,v): (k,v)):
            found_one = True
            char_detail.append([{'text': '  %s: %d' % (skill, value),
                                 'mode': mode}])

        if not found_one:
            char_detail.append([{'text': '  (None)',
                                 'mode': mode}])

        # spells

        if 'spells' in character:
            mode = curses.A_NORMAL 
            char_detail.append([{'text': 'Spells',
                                 'mode': mode | curses.A_BOLD}])

            found_one = False
            for spell in sorted(character['spells'], key=lambda(x): x['name']):
                found_one = True
                char_detail.append(
                                    [{'text': '  %s: %s' % (spell['name'],
                                                            spell['notes']),
                                      'mode': mode}])

            if not found_one:
                char_detail.append([{'text': '  (None)',
                                     'mode': mode}])

        # notes

        mode = curses.A_NORMAL 
        char_detail.append([{'text': 'Notes',
                             'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in character:
            for note in character['notes']:
                found_one = True
                char_detail.append([{'text': '  %s' % note,
                                     'mode': mode}])

        if not found_one:
            char_detail.append([{'text': '  (None)',
                                 'mode': mode}])



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


    def get_dodge_skill(self,
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

    def get_fighter_defenses_notes(self,
                                   fighter,  # Fighter object
                                   opponent
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

        # ARmor

        armor, armor_index = fighter.get_current_armor()
        if armor is not None:
            notes.append('Armor: "%s", DR: %d' % (armor['name'], armor['dr']))
            if 'notes' in armor and len(armor['notes']) != 0:
                why.append('Armor: "%s"' % armor['name'])
                why.append('  %s' % armor['notes'])


        return notes, why

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
        if ('brawling' in fighter.details['skills'] and
                                                'brawling' in unarmed_skills):
            if result['punch_skill'] <= fighter.details['skills']['brawling']:
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
            if result['parry_skill'] <= fighter.details['skills']['brawling']:
                result['parry_skill'] = fighter.details['skills']['brawling']
                result['parry_string'] = 'Brawling Parry (B182, B376)'
        if ('karate' in fighter.details['skills'] and
                                                'karate' in unarmed_skills):
            if result['punch_skill'] <= fighter.details['skills']['karate']:
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
            if result['parry_skill'] <= fighter.details['skills']['karate']:
                result['parry_skill'] = fighter.details['skills']['karate']
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

        if 'combat reflexes' in fighter.details['advantages']:
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


        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

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
        # TODO: need convenient defaults
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


    def make_empty_creature(self):
        to_monster = super(GurpsRuleset, self).make_empty_creature()
        to_monster.update({'aim': { 'braced': False, 'rounds': 0 }, 
                           'skills': { }, 
                           'shock': 0, 
                           'stunned': 0,
                           'advantages': { }, 
                           'did_action_this_turn': False,
                           'check_for_death': False, 
                           'posture': 'standing'})
        return to_monster


    def start_fight(self, fighter):
        '''
        Removes all the ruleset-related stuff from the old fight except injury.
        '''
        fighter.details['shock'] = 0
        fighter.details['stunned'] = 0
        fighter.details['check_for_death'] = False
        fighter.details['posture'] = 'standing'
        fighter.reset_aim()


    def start_turn(self, fighter):
        fighter.details['did_action_this_turn'] = False

        if fighter.is_conscious():
            if fighter.details['current']['fp'] <= 0:
                pass_out_menu = [('made WILL roll (or did nothing)', True),
                                 ('did NOT make WILL roll', False)]
                made_will_roll = self._window_manager.menu(
                    ('On Action: roll <= WILL (%d) or pass out' %
                                            fighter.details['current']['wi']),
                    pass_out_menu)
                if not made_will_roll:
                    fighter.details['state'] = 'unconscious'

        # B327 -- immediate check for death
        if fighter.is_conscious() and fighter.details['check_for_death']:
            dead_menu = [('made HT roll', True),
                         ('did NOT make HT roll', False)]
            made_ht_roll = self._window_manager.menu(
                ('%s: roll <= HT (%d) or DIE (B327)' %
                            (fighter.name, fighter.details['current']['ht'])),
                 dead_menu)

            if not made_ht_roll:
                fighter.details['state'] = 'dead'

            fighter.details['check_for_death'] = False  # Only show/roll once

        # B327 -- checking on each round whether the fighter is still
        # conscious

        if fighter.is_conscious() and fighter.details['current']['hp'] <= 0:
            pass_out_menu = [('made HT roll', True),
                             ('did NOT make HT roll', False)]

            if 'high pain threshold' in fighter.details['advantages']:
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
                reload_time = weapon['reload']
                if 'fast-draw (ammo)' in fighter.details['skills']:
                    reload_time -= 1
                weapon['ammo']['shots_left'] = weapon['ammo']['shots']
                item['count'] -= 1
                fighter.add_timer(reload_time, 'RELOADING')
                fighter.reset_aim()
                return

        return

    def don_armor(self,
                  param # dict: {'armor': index, 'fighter': Fighter obj}
                 ):
        '''
        Called to handle a menu selection.
        Returns: Nothing, return values for these functions are ignored.
        '''
        param['fighter'].don_armor_by_index(param['armor'])

    def use_item(self,
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

    def draw_weapon(self,
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
            damage_type_str = '%s=x%.1f' % (
                                        damage_type,
                                        GurpsRuleset.damage_mult[damage_type])
        else:
            damage_type_str = '%s' % damage_type
        return damage_type_str


    def get_weapons_unarmed_skills(self,
                                   weapon # None or dict from JSON
                                  ):
        '''
        If this weapon (which may be none) uses the unarmed combat skills.
        That's basically a blackjack or brass knuckles but there may be more.
        Assumes weapon's skill is the most advanced skill supported.

        Returns array of skills supported by this weapon.
        '''

        # Skills in increasing order of difficulty
        all_unarmed_skills = ['dx', 'brawling', 'boxing', 'karate']

        if weapon is None: # No weapon uses unarmed skills by definition
            return all_unarmed_skills

        if weapon['skill'] not in all_unarmed_skills:
            return None

        for i, skill in enumerate(all_unarmed_skills):
            if weapon['skill'] == skill:
                # Returns all of the skills through the matched one
                return all_unarmed_skills[:i+1]

        return None # Camel in Cairo -- should never get here


class ScreenHandler(object):
    '''
    Base class for the "business logic" backing the user interface.
    '''

    def __init__(self,
                 window_manager,
                 campaign_debug_json,
                 filename,
                 saved_fight,
                 maintain_json):
        self._window_manager = window_manager
        self._campaign_debug_json = campaign_debug_json
        self._input_filename = filename
        self._saved_fight = saved_fight
        self._maintain_json = maintain_json

        self._choices = {
            ord('B'): {'name': 'Bug Report', 'func': self._make_bug_report},
        }

    def add_to_history(self, string):
        self._saved_fight['history'].append(string)

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

        bug_report_json = timeStamped('bug_report', 'txt')
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
                 filename, # JSON file containing the world
                 maintain_json
                ):
        super(BuildFightHandler, self).__init__(
                                            window_manager,
                                            campaign_debug_json,
                                            filename,
                                            world.details['current-fight'],
                                            maintain_json)
        self._add_to_choice_dict({
            ord('a'): {'name': 'add creature',    'func': self.__add_creature},
            ord('d'): {'name': 'delete creature', 'func':
                                                    self.__delete_creature},
            ord('e'): {'name': 'existing group',  'func':
                                                    self.__existing_group},
            ord('n'): {'name': 'new group',       'func': self.__new_group},
            ord('t'): {'name': 'change template', 'func': self.__new_template},
            ord('q'): {'name': 'quit',            'func': self.__quit},
        })

        self._window = self._window_manager.get_build_fight_gm_window()

        self.__world = world
        self.__ruleset = ruleset

        self.__is_new = None    # If we're creating a new group (i.e., a new
                                # group of monsters), we'll have to add the
                                # group when we save it.  We won't add the
                                # group if we don't save it so that we don't
                                # have a bunch of empty monster groups hanging
                                # around.  If we're NOT creating a new group,
                                # we'll just add our monsters to the existing
                                # one when we save.


        self.__template_name = None # Name of templates we'll use to create
                                    # new creatures.

        self.__new_creatures = {}   # This is the recepticle for the new
                                    # creatures while they're being built.
                                    # In the event that they're saved,
                                    # they'll be transferred to their new
                                    # home.

        self.__equipment_manager = EquipmentManager(world,
                                                    window_manager)

        self.__new_char_name = None

        if creature_type == BuildFightHandler.NPCs:
            self.__is_new = False
            self.__group_name = 'NPCs'
            self.__new_home = self.__world.get_list('NPCs')
            self._draw_screen()
            self.__add_creature()
        elif creature_type == BuildFightHandler.PCs:
            self.__is_new = False
            self.__group_name = 'PCs'
            self.__new_home = self.__world.get_list('PCs')
            self._draw_screen()
            self.__add_creature()
        else: # creature_type == BuildFightHandler.MONSTERs:
            self.__new_home = None      # This is a pointer to the existing
                                        # group (either a group of monsters,
                                        # the NPCs, or the PCs) or a pointer
                                        # to a monster group (if it's a new
                                        # group).

            self.__group_name = None    # The name of the monsters or 'PCs'
                                        # that will ultimately take these
                                        # creatures.

            new_existing_menu = [('new monster group', 'new'),
                                 ('existing monster group', 'existing')]
            new_existing = None
            while new_existing is None:
                new_existing = self._window_manager.menu('New or Pre-Existing',
                                                          new_existing_menu)
            self._draw_screen()

            if new_existing == 'new':
                self.__new_group()
            else:
                self.__existing_group()

            self._draw_screen()
            self.__add_creature()


    #
    # Protected Methods
    #

    def _draw_screen(self):
        self._window.clear()
        self._window.status_ribbon(self.__group_name,
                                   self.__template_name,
                                   self._input_filename,
                                   self._maintain_json)
        self._window.command_ribbon(self._choices)
        self._window.show_creatures(
                            (None if self.__is_new else self.__new_home),
                            self.__new_creatures,
                            self.__new_char_name)
        if (self.__new_char_name is not None and
                                self.__new_char_name in self.__new_creatures):
            self._window.show_character_detail(
                                   self.__new_creatures[self.__new_char_name],
                                   self.__ruleset)

    #
    # Private Methods
    #

    def __add_creature(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # TODO: Add some comments in here (or refactor), it's really hard
        # to read.

        if self.__new_home is None or self.__group_name is None:
            self._window_manager.error(
                ['You must select a new or existing group to which to',
                 'add this creature.'])
            return True # Keep going

        keep_adding_creatures = True
        while keep_adding_creatures:
            if self.__template_name is None:
                self.__new_template()

            # Based on which monster from the template
            monster_menu = [(from_monster_name, from_monster_name)
                for from_monster_name in
                        self.__world.details['Templates'][self.__template_name]]
            from_monster_name = self._window_manager.menu('Monster',
                                                          sorted(monster_menu))
            if from_monster_name is None:
                return True # Keep going

            # Generate the Monster

            from_monster = (self.__world.details[
                        'Templates'][self.__template_name][from_monster_name])
            to_monster = self.__ruleset.make_empty_creature()

            for key, value in from_monster.iteritems():
                if key == 'permanent':
                    for ikey, ivalue in value.iteritems():
                        to_monster['permanent'][ikey] = (
                            self.__get_value_from_template(ivalue,
                                                           from_monster))
                        to_monster['current'][ikey] = to_monster[
                                                            'permanent'][ikey]
                else:
                    to_monster[key] = self.__get_value_from_template(
                                                        value, from_monster)

            # Get the new Monster Name

            keep_asking = True
            lines, cols = self._window.getmaxyx()
            monster_num = len(self.__new_creatures) + 1
            if not self.__is_new:
                monster_num += len(self.__new_home)
            while keep_asking:
                base_name = self._window_manager.input_box(1,      # height
                                                           cols-4, # width
                                                           'Monster Name')
                if base_name is None or len(base_name) == 0:
                    base_name, where, gender = self.__world.get_random_name()
                    if base_name is None:
                        self._window_manager.error(
                            ['Monster needs a name'])
                        keep_asking = True
                    else:
                        if where is not None:
                            to_monster['notes'].append('origin: %s' % where)
                        if gender is not None:
                            to_monster['notes'].append('gender: %s' % gender)

                if self.__group_name == 'NPCs' or self.__group_name == 'PCs':
                    monster_name = base_name
                else:
                    monster_name = '%d - %s' % (monster_num, base_name)

                if monster_name in self.__new_creatures:
                    self._window_manager.error(
                        ['Monster "%s" already exists' % monster_name])
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

                        to_monster['notes'].append('%s: %s' % (name, trait))

            # Modify the creature we just created

            keep_changing_this_creature = True

            fighter = Fighter(monster_name,
                              self.__group_name,
                              to_monster,
                              self.__ruleset,
                              self._window_manager)

            while keep_changing_this_creature:
                temp_list = copy.deepcopy(self.__new_creatures)
                temp_list[monster_name] = to_monster
                self.__new_char_name = monster_name
                self._window.show_creatures(
                                (None if self.__is_new else self.__new_home),
                                temp_list,
                                self.__new_char_name)
                self._window.show_character_detail(
                                to_monster,
                                self.__ruleset)

                action_menu = [('append to name', 'append'),
                               ('Add equipment', 'add'),
                               ('Remove equipment', 'remove'),
                               ('notes', 'notes'),
                               ('continue (add another creature)', 'continue'),
                               ('quit', 'quit')]

                action = self._window_manager.menu('What Next',
                                                   action_menu,
                                                   4) # start on 'continue'
                if action == 'append':
                    more_text = self._window_manager.input_box(1, # height
                                                               cols-4, # width
                                                               'Add to Name')
                    temp_monster_name = '%s - %s' % (monster_name,
                                                     more_text)
                    if temp_monster_name in self.__new_creatures:
                        self._window_manager.error(
                            ['Monster "%s" alread exists' % temp_monster_name])
                    else:
                        monster_name = temp_monster_name
                elif action == 'notes':
                    if 'notes' not in to_monster:
                        notes = None
                    else:
                        notes = '\n'.join(to_monster['notes'])
                    notes = self._window_manager.edit_window(
                                lines - 4,
                                cols/2,
                                notes,  # initial string (w/ \n) for the window
                                'Notes',
                                '^G to exit')
                    to_monster['notes'] = [x for x in notes.split('\n')]

                elif action == 'add':
                    self.__equipment_manager.add_equipment(fighter)

                elif action == 'remove':
                    self.__equipment_manager.remove_equipment(fighter)

                elif action == 'continue':
                    keep_changing_this_creature = False

                elif action == 'quit':
                    keep_changing_this_creature = False
                    keep_adding_creatures = False

            self.__new_creatures[monster_name] = to_monster
            self._window.show_creatures(
                                (None if self.__is_new else self.__new_home),
                                self.__new_creatures,
                                self.__new_char_name)

        return True # Keep going

    def __delete_creature(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if len(self.__new_creatures) == 0:
            return True

        critter_menu = [(name, name)
                                for name in self.__new_creatures.iterkeys()]
        critter_name = self._window_manager.menu('Delete Which Creature',
                                                 critter_menu)
        if critter_name is not None:
            del(self.__new_creatures[critter_name])

        self._window.show_creatures(
                                (None if self.__is_new else self.__new_home),
                                self.__new_creatures,
                                self.__new_char_name)

        return True # Keep going

    def __existing_group(self):
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

        group_menu = [(group_name,
                       {'name': group_name,
                        'group': self.__world.get_list(group_name)})
                for group_name in self.__world.details['monsters']]
        group_menu.insert(0, ('NPCs',
                              {'name': 'NPCs',
                               'group': self.__world.get_list('NPCs')}))
        group_menu.insert(0, ('PCs',
                              {'name': 'PCs',
                               'group': self.__world.get_list('PCs')}))
        group_answer = self._window_manager.menu('To Which Group', group_menu)
        if group_answer is None:
            return True # Keep going

        # Save the existing group (if there is one)

        if self.__group_name is not None and self.__new_creatures is not None:
            self.__maybe_save_group()

        # Set the name and group of the new group

        self.__is_new = False
        self.__group_name = group_answer['name']
        self.__new_home = group_answer['group']
        self.__new_creatures = {}

        # Display our new state

        self._draw_screen()

        return True # Keep going

    def __maybe_save_group(self):
        keep_asking = True
        while keep_asking:
            save_menu = [('save', 'save'), ('quit (don\'t save)', 'don\'t')]
            save = self._window_manager.menu(
                                'Save %s' % self.__group_name, save_menu)
            if save is not None:
                keep_asking = False
                if save == 'save':
                    if self.__is_new:
                        self.__new_home[self.__group_name] = (
                                                        self.__new_creatures)
                    else:
                        # add self.__new_creatures to self.__new_home
                        self.__new_home.update(self.__new_creatures)

            # Throw the old ones away
            self.__new_creatures = {}


    def __new_group(self):
        '''
        Command ribbon method.
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
            elif group_name in self.__world.details['monsters']:
                self._window_manager.error(
                    ['Fight name "%s" alread exists' % group_name])
                keep_asking = True
            else:
                keep_asking = False


        # Save the existing group (if there is one)

        if self.__group_name is not None and self.__new_creatures is not None:
            self.__maybe_save_group()

        # Set the name and group of the new group

        self.__is_new = True
        self.__group_name = group_name
        self.__new_home = self.__world.details['monsters'] # New groups can
                                                           # only be monsters.
        self.__new_creatures = {}

        # Display our new state

        self._draw_screen()

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

    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__maybe_save_group()
        # TODO: do I need to del self._window?
        self._window.close()
        return False # Stop building this fight



class FightHandler(ScreenHandler):
    def __init__(self,
                 window_manager,
                 world,
                 monster_group,
                 ruleset,
                 campaign_debug_json,
                 filename, # JSON file containing the world
                 maintain_json
                ):
        super(FightHandler, self).__init__(window_manager,
                                           campaign_debug_json,
                                           filename,
                                           world.details['current-fight'],
                                           maintain_json)
        self._window = self._window_manager.get_fight_gm_window(ruleset)
        self.__ruleset = ruleset
        self.__bodies_looted = False
        self.__keep_monsters = False # Move monsters to 'dead' after fight

        # NOTE: 'h' and 'f' belong in Ruleset
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
            ord('f'): {'name': 'FP damage',   'func': self.__damage_FP},
            ord('h'): {'name': 'History',     'func': self.__show_history},
            ord('i'): {'name': 'character info',
                                              'func': self.__show_info},
            ord('k'): {'name': 'keep monsters',
                                              'func': self.__do_keep_monsters},
            ord('-'): {'name': 'HP damage',   'func': self.__damage_HP},
            ord('L'): {'name': 'Loot bodies', 'func': self.__loot_bodies},
            ord('m'): {'name': 'maneuver',    'func': self.__maneuver},
            ord('n'): {'name': 'short notes', 'func': self.__short_notes},
            ord('N'): {'name': 'full Notes',  'func': self.__full_notes},
            ord('o'): {'name': 'opponent',    'func': self.__pick_opponent},
            #ord('P'): {'name': 'promote to NPC',
            #                                  'func': self.__promote_to_NPC},
            ord('q'): {'name': 'quit',        'func': self.__quit},
            ord('s'): {'name': 'save',        'func': self.__save},
            ord('t'): {'name': 'timer',       'func': self.__timer}
        })

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
        self.__fighters = [] # This is a parallel array to
                             # self._saved_fight['fighters'] but the contents
                             # are: {'group': <groupname>,
                             #       'info': <Fighter object>}

        if self._saved_fight['saved']:
            for saved_fighter in self._saved_fight['fighters']:
                fighter = Fighter(saved_fighter['name'],
                                  saved_fighter['group'],
                                  self.__get_fighter_details(
                                                      saved_fighter['name'],
                                                      saved_fighter['group']),
                                  self.__ruleset,
                                  self._window_manager)
                self.__fighters.append(fighter)
        else:
            # TODO: when the history is reset (here), the JSON should be
            # rewritten
            self.clear_history()
            self.add_to_history('--- Round 0 ---')

            self._saved_fight['round'] = 0
            self._saved_fight['index'] = 0
            self._saved_fight['monsters'] = monster_group

            self.__fighters = []    # contains objects

            for name in self.__world.get_list('PCs'):
                details = self.__world.get_creature_details(name, 'PCs')
                if details is not None:
                    fighter = Fighter(name,
                                      'PCs',
                                      details,
                                      self.__ruleset,
                                      self._window_manager)
                    self.__fighters.append(fighter)

            if monster_group is not None:
                for name in self.__world.get_list(monster_group):
                    details = self.__world.get_creature_details(name,
                                                                monster_group)
                    if details is not None:
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

            # Copy the fighter information into the saved_fight.  Also, make
            # sure this looks like a _NEW_ fight.
            self._saved_fight['fighters'] = []
            for fighter in self.__fighters:
                fighter.start_fight()
                self._saved_fight['fighters'].append({'group': fighter.group,
                                                       'name': fighter.name})

        if monster_group is not None:
            for name in self.__world.get_list(monster_group):
                details = self.__world.get_creature_details(name,
                                                            monster_group)
                if details is not None:
                    self.__ruleset.is_creature_consistent(name, details)

        self._saved_fight['saved'] = False
        self._window.start_fight()


    # Public to aid in testing

    def get_current_fighter(self):
        '''
        Returns the Fighter object of the current fighter.
        '''
        result = self.__fighters[ self._saved_fight['index'] ]
        return result


    def get_fighters(self):
        ''' Visibility for testing. '''
        return [{'name': fighter.name,
                 'group': fighter.group,
                 'details': fighter.details} for fighter in self.__fighters]


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


    def handle_user_input_until_done(self):
        super(FightHandler, self).handle_user_input_until_done()

        # When done, move current fight to 'dead-monsters'
        if (not self._saved_fight['saved'] and
                                self._saved_fight['monsters'] is not None and
                                self.__keep_monsters == False):
            fight_group = self._saved_fight['monsters']
            fight = self.__world.get_list(fight_group)
            self.__world.details['dead-monsters'][fight_group] = fight
            del self.__world.details['monsters'][fight_group]


    # Public to assist testing
    def modify_index(self,
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
            if current_fighter.is_dead():
                self.add_to_history(' (%s) did nothing (dead)' %
                                                        current_fighter.name)
            elif current_fighter.is_absent():
                self.add_to_history(' (%s) did nothing (absent)' %
                                                        current_fighter.name)

            else:
                keep_going = False

            # If we're skipping a fighter (due to his state), exercise his
            # timers, anyway
            if keep_going:
                current_fighter.decrement_timers()
                current_fighter.remove_expired_kill_dying_timers()

            # If we didn't change the index (for instance, if everyone's
            # dead), stop looking.  Otherwise, we're in an infinite loop.
            if self._saved_fight['index'] == first_index:
                keep_going = False

        if round_before != self._saved_fight['round']:
            self.add_to_history('--- Round %d ---' %
                                                self._saved_fight['round'])


    #
    # Private Methods
    #

    # TODO (move to ruleset): all of FP belongs in Ruleset
    def __damage_FP(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Figure out who loses the FP points
        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
            opponent = self.get_opponent_for(current_fighter)
            fp_recipient = current_fighter
        else:
            current_fighter = self.get_current_fighter()
            opponent = self.get_opponent_for(current_fighter)
            fp_recipient = current_fighter if opponent is None else opponent

        title = 'Reduce (%s\'s) FP By...' % fp_recipient.name
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        if len(adj_string) <= 0:
            return True
        adj = -int(adj_string)  # NOTE: SUBTRACTING the adjustment
        hp_adj = 0

        # If FP go below zero, you lose HP along with FP
        # TODO (move to ruleset): this -- especially -- should be in Ruleset
        if adj < 0  and -adj > fp_recipient.details['current']['fp']:
            hp_adj = adj
            if fp_recipient.details['current']['fp'] > 0:
                hp_adj += fp_recipient.details['current']['fp']

        fp_recipient.details['current']['hp'] += hp_adj
        fp_recipient.details['current']['fp'] += adj
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __damage_HP(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Figure out who loses the hit points

        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
            opponent = self.get_opponent_for(current_fighter)
            hp_recipient = current_fighter
        else:
            current_fighter = self.get_current_fighter()
            opponent = self.get_opponent_for(current_fighter)
            hp_recipient = current_fighter if opponent is None else opponent

        title = 'Reduce (%s\'s) HP By...' % hp_recipient.name
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        if len(adj_string) <= 0:
            return True
        adj = -int(adj_string) # NOTE: SUBTRACTING the adjustment
        if adj == 0:
            return True # Keep fighting

        self.__ruleset.adjust_hp(hp_recipient, adj)

        # Record for posterity
        if hp_recipient is opponent:
            if adj < 0:
                self.add_to_history(' (%s) did %d HP to (%s)' %
                                                        (current_fighter.name,
                                                         -adj,
                                                         opponent.name))
            else:
                self.add_to_history(' (%s) regained %d HP' %
                                                        (opponent.name,
                                                         adj))
        else:
            if adj < 0:
                self.add_to_history(
                        ' (%s) lost %d HP' % (current_fighter.name, -adj))
            else:
                self.add_to_history(
                        ' (%s) regained %d HP' % (current_fighter.name, adj))

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

        if now_dead.is_conscious():
            now_dead.details['opponent'] = None # dead men fight nobody
        now_dead.bump_consciousness()

        dead_name = now_dead.name
        self.add_to_history(' (%s) was marked as (%s)' % (
                                                    dead_name,
                                                    now_dead.details['state']))

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going

    def __defend(self):
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

        # Defending costs you aim
        defender.reset_aim()

        self.add_to_history(' (%s) defended (and lost aim)' % defender.name)

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
                                  self._maintain_json)
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
                                  self._maintain_json)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        self._window.status_ribbon(self._input_filename,
                                   self._maintain_json)
        self._window.command_ribbon(self._choices)


    def __get_fighter_details(self,
                              name,     # string
                              group     # string
                             ):
        ''' Used for constructing a Fighter from the JSON information. '''
        return self.__world.get_creature_details(name, group)


    def __get_fighter_object(self,
                             name,  # name of a fighter in that group
                             group  # 'PCs' or group under world['monsters']
                            ):
        for fighter in self.__fighters:
            if fighter.group == group and fighter.name == name:
                return fighter

        return None


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
                xfer['guy'].add_equipment(new_item, bad_guy.name)

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

        # TODO: call the ruleset to execute the action
        # TODO: change 'maneuver' to 'action'
        # TODO: fill-in current_fighter, opponent, world
        # if 'action' in maneuver:
        #   self.__ruleset.do_action(action, current_fighter)

        self.__ruleset.do_maneuver(current_fighter)
        # a round count larger than 0 will get shown but less than 1 will
        # get deleted before the next round
        current_fighter.add_timer(0.9, maneuver['text'])

        self.add_to_history(' (%s) did (%s) maneuver' % (current_fighter.name,
                                                         maneuver['text'][0]))
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __change_viewing_index(self,
                               adj  # integer adjustment to viewing index
                              ):
        self.__viewing_index += adj
        if self.__viewing_index >= len(self._saved_fight['fighters']):
            self.__viewing_index = 0
        elif self.__viewing_index < 0:
            self.__viewing_index = len(self._saved_fight['fighters']) - 1

    def __view_prev(self): # look at previous character, don't change init
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

    def __view_next(self): # look at next character, don't change init
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

    def __view_init(self): # look at initiative character (back to fight)
        self.__viewing_index = None
        current_fighter = self.get_current_fighter()
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
            # TODO (move to ruleset): This should _so_ be in the ruleset but
            # I'm not sure how to achieve that.  It also makes the assumption
            # that you can't move on to the next fighter _because_ no
            # maneuver/action has been performed.
            return self.__maneuver()
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
                                  self._maintain_json)

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


    def __short_notes(self):
        return self.__notes('short-notes')


    def __full_notes(self):
        return self.__notes('notes')


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

    def __pick_opponent(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
        else:
            current_fighter = self.get_current_fighter()

        opponent_group = None
        opponent_menu = []
        default_selection = None
        for fighter in self.__fighters:
            if fighter.group != current_fighter.group:
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

        self.add_to_history(' (%s) picked (%s) as opponent' % 
                                                    (current_fighter.name,
                                                     opponent_name))

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

                self.add_to_history(
                                ' (%s) picked (%s) as opponent right back' % 
                                                        (opponent_name,
                                                         current_fighter.name))

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
                                  self._maintain_json)
        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    #def __promote_to_NPC(self):
    #    if self.__viewing_index is not None:
    #        new_NPC = self.__fighters[self.__viewing_index]
    #    else:
    #        current_fighter = self.get_current_fighter()
    #        if (current_fighter.group == 'PCs' or
    #                                        current_fighter.group == 'NPCs'):
    #            opponent = self.get_opponent_for(current_fighter)
    #            new_NPC = current_fighter if opponent is None else opponent
    #        else:
    #            new_NPC = current_fighter

    #    if new_NPC.group == 'PCs':
    #        self._window_manager.error(['%s is already a PC' % new_NPC.name])
    #        return True
    #    if new_NPC.group == 'NPCs':
    #        self._window_manager.error(['%s is already an NPC' % new_NPC.name])
    #        return True

    #    # Now we have chosen a monster that's NOT an NPC or PC, promote him.

    #    # Make the NPC entry

    #    if new_NPC.name in self.__world.details['NPCs']:
    #        self._window_manager.error(['There\'s already an NPC named %s' %
    #                                    new_NPC.name])
    #        return True

    #    details_copy = copy.deepcopy(new_NPC.details)
    #    self.__world.details['NPCs'][new_NPC.name] = details_copy

    #    # Make the redirect entry

    #    redirect_entry = { "redirect": "NPCs" }
    #    new_NPC.details = redirect_entry
    #    self.__world.details['monsters'][new_NPC.group][new_NPC.name] = (
    #                                                        redirect_entry)
    #    return True # Keep going


    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        ask_to_save = False # Ask to save if some monster is conscious
        ask_to_loot = False # Ask to loot if some monster is unconscious
        for fighter in self.__fighters:
            if fighter.group != 'PCs':
                if fighter.is_conscious():
                    ask_to_save = True
                else:
                    ask_to_loot = True

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
                (result['doit'])()

        self._window.close()
        return False # Leave the fight


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

    def simply_save(self):
        self._saved_fight['saved'] = True

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
                                  self._maintain_json)
        return True # Keep going

    def __show_history(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        lines = []
        for line in self._saved_fight['history']:
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

        self.__ruleset.get_character_detail(info_about.details,
                                            char_info)
        self._window_manager.display_window('%s Information' % info_about.name,
                                            char_info)
        return True

    def display_window(self,
                       title,
                       lines  # [{'text', 'mode'}, ...]
                      ):

        return True

    def __show_why(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        why_target, current_fighter = self.__select_fighter('Details For Whom')
        if why_target is None:
            return True # Keep fighting

        lines = []

        why_opponent = self.get_opponent_for(why_target)
        weapon, holding_weapon_index = why_target.get_current_weapon()
        unarmed_skills = self.__ruleset.get_weapons_unarmed_skills(weapon)

        if unarmed_skills is not None:
            unarmed_info = self.__ruleset.get_unarmed_info(why_target,
                                                           why_opponent,
                                                           weapon,
                                                           unarmed_skills)
            lines = [[{'text': x,
                       'mode': curses.A_NORMAL}] for x in unarmed_info['why']]
        else:
            if weapon['skill'] in why_target.details['skills']:
                ignore, to_hit_why = self.__ruleset.get_to_hit(why_target,
                                                               why_opponent,
                                                               weapon)
                lines = [[{'text': x,
                           'mode': curses.A_NORMAL}] for x in to_hit_why]

                # Damage

                ignore, damage_why = self.__ruleset.get_damage(why_target,
                                                               weapon)
                lines.extend([[{'text': x,
                                'mode': curses.A_NORMAL}] for x in damage_why])

            if 'notes' in weapon and len(weapon['notes']) != 0:
                lines.extend([[{'text': 'Weapon: "%s"' % weapon['name'],
                               'mode': curses.A_NORMAL}]])
                lines.extend([[{'text': '  %s' % weapon['notes'],
                               'mode': curses.A_NORMAL}]])

        ignore, defense_why = self.__ruleset.get_fighter_defenses_notes(
                                                            why_target,
                                                            why_opponent)
        lines = [[{'text': x,
                   'mode': curses.A_NORMAL}] for x in defense_why] + lines

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

        # How long is the timer?

        timer = {'rounds': 0, 'string': None}
        title = 'Rounds To Wait...'
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        if adj_string is None or len(adj_string) <= 0:
            return True
        timer['rounds'] = int(adj_string)
        if timer['rounds'] <= 0:
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

        # What is the timer's announcement?

        title = 'Enter an announcement if you want one...'
        height = 1
        width = curses.COLS - 4
        announcement = self._window_manager.input_box(
                                        height,
                                        self._window.fighter_win_width - 
                                                self._window.len_timer_leader,
                                        title)

        if announcement is not None and len(announcement) <= 0:
            announcement = None
        else:
            # Shave a little off the time so that the timer will announce
            # as his round starts rather than at the end.
            timer['rounds'] -= 0.1

        # Instal the timer.

        if timer['string'] is not None and len(timer['string']) != 0:
            timer_recipient.add_timer(timer['rounds'],
                                      timer['string'],
                                      announcement)

        # Show stuff

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep fighting


class MainHandler(ScreenHandler):
    def __init__(self,
                 window_manager,
                 world,
                 ruleset,
                 campaign_debug_json,
                 filename, # JSON file containing the world
                 maintain_json
                ):
        super(MainHandler, self).__init__(window_manager,
                                          campaign_debug_json,
                                          filename,
                                          world.details['current-fight'],
                                          maintain_json)
        self.__world = world
        self.__ruleset = ruleset
        self._add_to_choice_dict({
            # TODO: KEY_LEFT and KEY_RIGHT need to change window scrolled by
            # KEY_UP and KEY_DOWN between char and char detail window.
            curses.KEY_UP:
                      {'name': 'previous character',  'func':
                                                       self.__prev_char},
            curses.KEY_DOWN:
                      {'name': 'next character',      'func':
                                                       self.__next_char},
            curses.KEY_NPAGE:
                      {'name': 'char details pgdown', 'func':
                                                       self.__next_page},
            curses.KEY_PPAGE:
                      {'name': 'char details pgup',   'func':
                                                       self.__prev_page},
            ord('c'): {'name': 'select character',    'func':
                                                       self.__character},
            ord('e'): {'name': 'add equipment',       'func':
                                                       self.__add_equipment},
            ord('E'): {'name': 'remove equipment',    'func':
                                                       self.__remove_equipment},
            ord('g'): {'name': 'give equipment',      'func':
                                                       self.__give_equipment},
            ord('o'): {'name': 'outfit characters',   'func':
                                                       self.__outfit},
            ord('J'): {'name': 'NPC joins PCs',       'func':
                                                       self.__NPC_joins},
            ord('L'): {'name': 'NPC leaves PCs',      'func':
                                                       self.__NPC_leaves},
            ord('N'): {'name': 'new NPCs',            'func':
                                                       self.__add_NPCs},
            ord('P'): {'name': 'new PCs',             'func':
                                                       self.__add_PCs},
            ord('M'): {'name': 'new Monsters',        'func':
                                                       self.__add_monsters},
            ord('f'): {'name': 'fight',               'func':
                                                       self.__run_fight},
            ord('H'): {'name': 'Heal',                'func':
                                                       self.__fully_heal},
            ord('q'): {'name': 'quit',                'func':
                                                       self.__quit},
            ord('/'): {'name': 'search',              'func':
                                                       self.__search}
        })
        self.__setup_PC_list()
        self._window = self._window_manager.get_main_gm_window()
        self.__equipment_manager = EquipmentManager(self.__world,
                                                    self._window_manager)

        # Check characters for consistency.
        for name in self.__world.get_list('PCs'):
            details = self.__world.get_creature_details(name, 'PCs')
            if details is not None:
                self.__ruleset.is_creature_consistent(name, details)


    #
    # Protected Methods
    #

    def _draw_screen(self, inverse=False):
        self._window.clear()
        self._window.status_ribbon(self._input_filename,
                                   self._maintain_json)

        person = (None if self.__char_index is None
                                    else self.__chars[self.__char_index])
        character = None if person is None else person['details']

        self._window.show_character_list(self.__chars,
                                         self.__char_index,
                                         inverse)
        self._window.show_character_detail(character, self.__ruleset)

        self._window.command_ribbon(self._choices)

    #
    # Private Methods - callbacks for 'choices' array for menu
    #

    def __add_NPCs(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world,
                                        self.__ruleset,
                                        BuildFightHandler.NPCs,
                                        campaign_debug_json,
                                        self._input_filename,
                                        self._maintain_json)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list() # Since it may have changed
        self._draw_screen() # Redraw current screen when done building fight.
        return True # Keep going


    def __add_PCs(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world,
                                        self.__ruleset,
                                        BuildFightHandler.PCs,
                                        campaign_debug_json,
                                        self._input_filename,
                                        self._maintain_json)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list() # Since it may have changed
        self._draw_screen() # Redraw current screen when done building fight.
        return True # Keep going


    def __add_monsters(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        build_fight = BuildFightHandler(self._window_manager,
                                        self.__world,
                                        self.__ruleset,
                                        BuildFightHandler.MONSTERs,
                                        campaign_debug_json,
                                        self._input_filename,
                                        self._maintain_json)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list() # Since it may have changed
        self._draw_screen() # Redraw current screen when done building fight.
        return True # Keep going

    def __add_equipment(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = Fighter(self.__chars[self.__char_index]['name'],
                          self.__chars[self.__char_index]['group'],
                          self.__chars[self.__char_index]['details'],
                          self.__ruleset,
                          self._window_manager)
        self.__equipment_manager.add_equipment(fighter)
        self._draw_screen()
        return True # Keep going


    def __give_equipment(self):
        from_fighter = Fighter(self.__chars[self.__char_index]['name'],
                               self.__chars[self.__char_index]['group'],
                               self.__chars[self.__char_index]['details'],
                               self.__ruleset,
                               self._window_manager)

        item = self.__equipment_manager.remove_equipment(from_fighter)
        if item is None:
            return True # Keep going

        character_list = self.__world.get_list('PCs')
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

        to_fighter.add_equipment(item, from_fighter.name)
        self._draw_screen()
        return True # Keep going

    def __remove_equipment(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = Fighter(self.__chars[self.__char_index]['name'],
                          self.__chars[self.__char_index]['group'],
                          self.__chars[self.__char_index]['details'],
                          self.__ruleset,
                          self._window_manager)
        self.__equipment_manager.remove_equipment(fighter)
        self._draw_screen()
        return True # Keep going

    def __outfit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        outfit = OutfitCharactersHandler(self._window_manager,
                                         self.__world,
                                         self.__ruleset,
                                         campaign_debug_json,
                                         self._input_filename,
                                         self._maintain_json)
        outfit.handle_user_input_until_done()
        self._draw_screen() # Redraw current screen when done building fight.
        return True # Keep going

    def __fully_heal(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        for name in self.__world.get_list('PCs'):
            details = self.__world.get_creature_details(name, 'PCs')
            if details is not None:
                self.__ruleset.heal_fighter(details)
        self._draw_screen()
        return True

    def __search(self):
        lines, cols = self._window.getmaxyx()
        look_for_string = self._window_manager.input_box(1,
                                                         cols-4,
                                                         'Search For What?')

        if look_for_string is None or len(look_for_string) <= 0:
            return True
        look_for_re = re.compile(look_for_string)

        all_results = []
        for name in self.__world.get_list('PCs'):
            creature = self.__world.get_creature_details(name, 'PCs')
            result = self.__ruleset.search_one_creature(name,
                                                        'PCs',
                                                        creature,
                                                        look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for name in self.__world.get_list('NPCs'):
            creature = self.__world.get_creature_details(name, 'NPCs')
            result = self.__ruleset.search_one_creature(name,
                                                        'NPCs',
                                                        creature,
                                                        look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for fight in self.__world.details['monsters']:
            for name in self.__world.details['monsters'][fight]:
                creature = self.__world.get_creature_details(name, fight)
                result = self.__ruleset.search_one_creature(name,
                                                            'monsters->%s'
                                                                    % fight,
                                                            creature,
                                                            look_for_re)
                if result is not None and len(result) > 0:
                    all_results.extend(result)

        if len(all_results) <= 0:
            self._window_manager.error(['"%s" not found' % look_for_string])
        else:
            lines = []
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

                lines.append([{'text': match_string,
                               'mode': curses.A_NORMAL}])
            self._window_manager.display_window('Found "%s"' % look_for_string,
                                                lines)

        return True

    def __character(self):
        keep_going = True
        name = ''
        original_index = self.__char_index
        self._draw_screen(inverse=True)
        while keep_going:
            user_input = self._window_manager.get_one_character()
            if user_input == ord('\n'):
                self._draw_screen(inverse=False)
                return True
            elif user_input == GmWindowManager.ESCAPE:
                self.__char_index = self.__char_index
                self._draw_screen(inverse=False)
                return True
            else:
                if user_input == curses.ascii.BS:
                    name = name[:-1]
                elif curses.ascii.isprint(user_input):
                    name += chr(user_input)

                length = len(name)

                # Look for a match and return the selection
                for index, char in enumerate(self.__chars):
                            # [ {'name': xxx,
                            #    'group': xxx,
                            #    'details':xxx}, ...
                    # (string, return value)
                    if name == char['name'][:length]:
                        self.__char_index = index
                        self._draw_screen(inverse=True)
                        break

        return True

    def __next_char(self):
        if self.__char_index is None:
            self.__char_index = 0
        else:
            self.__char_index += 1
            if self.__char_index >= len(self.__chars):
                self.__char_index = 0
        self._draw_screen()
        return True

    def __next_page(self):
        self._window.scroll_char_detail_down()
        return True

    def __NPC_joins(self):
        npc_menu = [(npc, npc) for npc in self.__world.details['NPCs'].keys()]
        npc_name = self._window_manager.menu(
                                'Add which NPC to the party',
                                npc_menu)
        if npc_name is None:
            return True
        
        self.__world.details['PCs'][npc_name] = {'redirect': 'NPCs'}
        self.__setup_PC_list()
        self._draw_screen()
        return True

    def __NPC_leaves(self):
        npc_menu = [(npc, npc) for npc in self.__world.details['PCs'].keys()
                     if 'redirect' in self.__world.details['PCs'][npc]]
        npc_name = self._window_manager.menu(
                                'Remove which NPC from the party',
                                npc_menu)
        if npc_name is None:
            return True
        
        del(self.__world.details['PCs'][npc_name])
        self.__setup_PC_list()
        self._draw_screen()
        return True

    def __prev_char(self):
        if self.__char_index is None:
            self.__char_index = len(self.__chars) - 1
        else:
            self.__char_index -= 1
            if self.__char_index < 0:
                self.__char_index = len(self.__chars) - 1
        self._draw_screen()
        return True

    def __prev_page(self):
        self._window.scroll_char_detail_up()
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
        if not self._saved_fight['saved']:
            fight_name_menu = [(name, name)
                       for name in self.__world.details['monsters']]
            # PP.pprint(fight_name_menu)
            monster_group = self._window_manager.menu('Fights',
                                                      fight_name_menu)
            if (monster_group is not None and
                    monster_group not in self.__world.details['monsters']):
                print 'ERROR, monster list %s not found' % monster_group
                return True

        fight = FightHandler(self._window_manager,
                             self.__world,
                             monster_group,
                             self.__ruleset,
                             self._campaign_debug_json,
                             self._input_filename,
                             self._maintain_json)
        fight.handle_user_input_until_done()
        self._draw_screen() # Redraw current screen when done with the fight.

        return True # Keep going

    def __setup_PC_list(self):
        self.__chars = [
                    {'name': x,
                     'group': 'PCs',
                     'details': self.__world.get_creature_details(x, 'PCs')
                    } for x in sorted(self.__world.get_list('PCs'))]

        npcs = self.__world.get_list('NPCs')
        if npcs is not None:
            self.__chars.extend([
                    {'name': x,
                     'group': 'NPCs',
                     'details': self.__world.get_creature_details(x, 'NPCs')
                    } for x in sorted(self.__world.get_list('NPCs'))])
        self.__char_index = 0


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

    def add_equipment(self,
                      fighter,      # Fighter object
                      item = None   # dict
                     ):
        if fighter is None:
            return

        # Pick an item off the shelf

        # Rebuild this every time in case there are unique items in the
        # equipment list
        item_menu = [(item['name'], item)
                            for item in self.__world.details['Equipment']]
        item = self.__window_manager.menu('Item to Add', item_menu)
        if item is not None:
            fighter.add_equipment(copy.deepcopy(item), 'the store')

        # self._window.show_character(self.__character)

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

        if ('count' in fighter.details['stuff'][item_index] and
                        fighter.details['stuff'][item_index]['count'] > 1):
            item = copy.deepcopy(fighter.details['stuff'][item_index])
            item['count'] = 1
            fighter.details['stuff'][item_index]['count'] -= 1
        else:
            item = fighter.details['stuff'][item_index]
            fighter.details['stuff'].pop(item_index)

            # Now, we're potentially messing with the order of things in the
            # 'stuff' array.  Best not to depend on the weapon-index.
            fighter.details['weapon-index'] = None
            fighter.details['armor-index'] = None


        #self._window.show_character(self.__character)
        return item


class OutfitCharactersHandler(ScreenHandler):
    def __init__(self,
                 window_manager,
                 world,
                 ruleset,
                 campaign_debug_json,
                 filename, # JSON file containing the world
                 maintain_json
                ):
        super(OutfitCharactersHandler, self).__init__(
                                            window_manager,
                                            campaign_debug_json,
                                            filename,
                                            world.details['current-fight'],
                                            maintain_json)

        self._add_to_choice_dict({
            ord('a'): {'name': 'add equipment',    'func':
                                                      self.__add_equipment},
            ord('r'): {'name': 'remove equipment', 'func':
                                                      self.__remove_equipment},
            ord('s'): {'name': 'select character', 'func':
                                                      self.__select_character},
            ord('q'): {'name': 'quit',             'func': self.__quit},
        })
        self._window = self._window_manager.get_outfit_gm_window()
        self.__world = world
        self.__ruleset = ruleset
        self.__equipment_manager = EquipmentManager(self.__world,
                                                    self._window_manager)

        lines, cols = self._window.getmaxyx()
        group_menu = [('PCs', 'PCs')]
        group_menu.extend([(group, group)
                                for group in self.__world.details['monsters']])
        self.__group_name = self._window_manager.menu('Outfit Which Group',
                                                      group_menu)

        # TODO: need to exit if a group isn't chosen

        self.__character = {'name': None, 'details': None}
        self.__select_character()
        self._window.show_character(self.__character)

    #
    # Protected Methods
    #

    def _draw_screen(self):
        self._window.clear()
        self._window.show_character(self.__character)
        self._window.status_ribbon(self._input_filename,
                                   self._maintain_json)
        self._window.command_ribbon(self._choices)

    #
    # Private Methods
    #

    def __add_equipment(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__character['details'] is None:
            self.__select_character()
            return True # TODO: should this really return, now?

        fighter = Fighter(self.__character['name'],
                          self.__group_name,
                          self.__character['details'],
                          self.__ruleset,
                          self._window_manager)
        self.__equipment_manager.add_equipment(fighter)
        self._window.show_character(self.__character)
        return True # Keep going


    def __remove_equipment(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if self.__character['details'] is None:
            self.__select_character()
            return True # TODO: should this really return, now?

        fighter = Fighter(self.__character['name'],
                          self.__group_name,
                          self.__character['details'],
                          self.__ruleset,
                          self._window_manager)
        self.__equipment_manager.remove_equipment(fighter)
        self._window.show_character(self.__character)
        return True # Keep going


    def __select_character(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        character_list = self.__world.get_list(self.__group_name)
        character_menu = [(dude, dude) for dude in character_list]
        character_name = self._window_manager.menu('Character', character_menu)
        if character_name is None:
            return True # Keep going

        details = self.__world.get_creature_details(character_name,
                                                    self.__group_name)
        if details is not None:
            self.__character = {'name': character_name, 'details': details}
            self._window.show_character(self.__character)
        return True # Keep going


    def __quit(self):
        '''
        Command ribbon method.
        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self._window.close()
        return False # Stop building this fight


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

            world = World(campaign.read_data, window_manager)

            # Enter into the mainloop
            main_handler = MainHandler(window_manager,
                                       world,
                                       ruleset,
                                       campaign_debug_json,
                                       filename,
                                       ARGS.maintainjson)

            if campaign.read_data['current-fight']['saved']:
                fight_handler = FightHandler(window_manager,
                                             world,
                                             None,
                                             ruleset,
                                             campaign_debug_json,
                                             filename,
                                             ARGS.maintainjson)
                fight_handler.handle_user_input_until_done()
            main_handler.handle_user_input_until_done()

