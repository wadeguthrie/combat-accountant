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
import shutil
import sys
import traceback

# NOTE: debugging thoughts:
#   - traceback.print_stack()

class GmJson(object):
    '''
    Context manager that opens and loads a JSON file.  Does so in a context
    manager and does all this in ASCII (for v2.7 Python).  Needs to know about
    a window manager for error reporting.
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
            message = 'Could not read JSON file "%s"' % self.__filename
            if self.__window_manager is None:
                print message
            else:
                self.__window_manager.error([message])
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

        self.open_write_json_and_close(self.write_data)

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


    def open_write_json_and_close(self,
                                  write_data   # Python data to be written to the file
                                 ):
        '''
        Dump Python data to the JSON file.
        '''
        if write_data is not None:
            with open(self.__filename, 'w') as f:
                json.dump(write_data, f, indent=2)


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

    Like much of this code, it reflects the abstractions provided by Curses
    since that's the initial GUI implementation.  The idea behind that is it
    seemed stupid to invent an arbitrary API just to convert Curses' API to
    that.  I figure that anyone that wants to port this to, say, a _REAL_ GUI,
    could just port their API to curses'.  If there are any incompatibilies,
    we'll address them, then.
    '''
    def __init__(self,
                 window_manager, # A GmWindowManager object
                 # Using curses screen addressing w/0,0 in upper left corner
                 height,
                 width,
                 top_line,
                 left_column,
                 command_ribbon_choices = None
                ):
        self._window_manager = window_manager

        self._command_ribbon = {
            'choices_per_line': 0,
            'lines_for_choices': 0,
        }
        if command_ribbon_choices is not None:
            self.__build_command_ribbon(height, width, command_ribbon_choices)

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

        Returns: nothing.
        '''
        self._window_manager.pop_gm_window(self)
        del self._window                   # kill ourselves
        self._window_manager.refresh_all() # refresh everything else


    def command_ribbon(self):
        '''
        Draws a list of commands across the bottom of the screen.  Uses
        information gathered through |build_command_ribbon|.

        Returns nothing.
        '''
        choice_strings = copy.deepcopy(self._command_ribbon['choice_strings'])
        lines = self._command_ribbon['lines']
        cols = self._command_ribbon['cols']

        line = lines - 1 # -1 because last line is lines-1
        for subline in reversed(range(
                            self._command_ribbon['lines_for_choices'])):
            line = lines - (subline + 1) # -1 because last line is lines-1
            left = 0
            for i in range(self._command_ribbon['choices_per_line']):
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
                left += self._command_ribbon['max_width']
            # TODO: figure out why, occassionally, this fails.  I _think_ it's when the math
            # doesn't quite work out and something goes beyond the edge of the screen, but
            # that's just a theory.
            try:
                self._window.addstr(line, left, '|', curses.A_NORMAL)
            except:
                pass
        self.refresh()


    def getmaxyx(self):
        '''
        Returns the tuple containing the number of lines and columns in
        the window.
        '''
        return self._window.getmaxyx()


    def refresh(self):
        ''' Redraws the window. '''
        self._window.refresh()


    def show_description(self,
                         character # Fighter or Venue object
                        ):
        '''
        Displays the description of the Fighter/Venue object in the current
        window.

        Returns: nothing.
        '''
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
                      maintain_game_file):
        '''
        Displays the current status of the window handler across the top of the
        window.

        Returns: nothing
        '''

        lines, cols = self.getmaxyx()

        file_string = '%s' % filename
        wont_be_saved_string = ' (WILL NOT BE SAVED)'
        len_file_string = len(file_string)
        len_whole_string = len_file_string + (
                        0 if not maintain_game_file else len(wont_be_saved_string))
        start_file_string = (cols - len_whole_string) / 2

        mode = curses.A_NORMAL
        self._window.addstr(0,
                            start_file_string,
                            '%s' % filename,
                            mode | curses.A_BOLD)

        if maintain_game_file:
            mode = curses.color_pair(GmWindowManager.MAGENTA_BLACK)
            self._window.addstr(0,
                                start_file_string + len_file_string,
                                wont_be_saved_string,
                                mode | curses.A_BOLD)


    def touchwin(self):
        '''
        Pretends that the window has been modified so that 'refresh' will
        redraw it.

        Returns nothing.
        '''
        self._window.touchwin()


    def uses_whole_screen(self):
        '''
        Returns True if this window takes-up the whole screen, False,
        otherwise.
        '''
        lines, cols = self.getmaxyx()
        if lines < curses.LINES or cols < curses.COLS:
            return False
        # No need to check top and left since there'd be an error if they were
        # non-zero given the height and width of the window.
        return True


    #
    # Protected and Private Members
    #

    def __build_command_ribbon(self,
                               lines,     # from lines, cols = self.getmaxyx()
                               cols,
                               choices,   # hash: ord('f'): {'name': 'xxx',
                                          #                  'func': self.func}
                              ):
        '''
        Given a set of commands (here, called 'choices'), this routine builds
        the strings for the command ribbon and arranges them into lines.

        Returns nothing.
        '''
        # Build the choice strings

        self._command_ribbon = {
            'lines': lines,
            'cols': cols,
            'max_width': 0,
            'choice_strings': []
        }
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
            self._command_ribbon['choice_strings'].append(choice_text)
            choice_string = '%s%s%s' % (choice_text['bar'],
                                        choice_text['command'],
                                        choice_text['body'])
            if self._command_ribbon['max_width'] < len(choice_string):
                self._command_ribbon['max_width'] = len(choice_string)

        # Calculate the number of rows needed for all the commands

        self._command_ribbon['choices_per_line'] = int((cols - 1)/
                        self._command_ribbon['max_width']) # -1 for last '|'
        self._command_ribbon['lines_for_choices'] = int(
            (len(choices) /
            (self._command_ribbon['choices_per_line'] + 0.0))
            + 0.9999999) # +0.9999 so 'int' won't truncate last partial line

        self._command_ribbon['choice_strings'].sort(reverse=True,
                                        key=lambda s: s['command'].lower())


class MainGmWindow(GmWindow):
    '''
    This is the startup window for the program.
    '''
    def __init__(self,
                 window_manager,
                 command_ribbon_choices
                ):
        super(MainGmWindow, self).__init__(window_manager,
                                           curses.LINES,
                                           curses.COLS,
                                           0,
                                           0,
                                           command_ribbon_choices)

        lines, cols = self._window.getmaxyx()
        self._char_detail = []  # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        top_line = 1
        height = (lines         # The whole window height, except...
                    - top_line  # ...a block at the top, and...
                    - (self._command_ribbon['lines_for_choices'] + 1))
                                # ...a space for the command ribbon + margin

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
        '''
        Scrolls the character detail pane to the top and redraws the pane.

        Return: nothing
        '''
        self._char_detail_window.scroll_to(0)
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def char_list_home(self):
        '''
        Scrolls the character list pane to the top and redraws the pane.

        Return: nothing
        '''
        self.__char_list_window.scroll_to(0)
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    def close(self):
        ''' Closes the window and disposes of its resources.  '''
        # Kill my subwindows, first
        if self.__char_list_window is not None:
            del self.__char_list_window
            self.__char_list_window = None
        if self._char_detail_window is not None:
            del self._char_detail_window
            self._char_detail_window = None
        super(MainGmWindow, self).close()


    def refresh(self):
        ''' Re-draws all of the window's panes.  '''
        super(MainGmWindow, self).refresh()
        if self.__char_list_window is not None:
            self.__char_list_window.refresh()
        if self._char_detail_window is not None:
            self._char_detail_window.refresh()


    def scroll_char_detail_down(self):
        ''' Scrolls the character detail pane down.  '''
        self._char_detail_window.scroll_down()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def scroll_char_detail_up(self):
        ''' Scrolls the character detail pane up.  '''
        self._char_detail_window.scroll_up()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def scroll_char_list_down(self):
        ''' Scrolls the character list pane down.  '''
        self.__char_list_window.scroll_down()
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    def scroll_char_list_up(self):
        ''' Scrolls the character list pane up.  '''
        self.__char_list_window.scroll_up()
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    # MainGmWindow
    def show_creatures(self,
                       char_list,  # [ Fighter(), Fighter(), ..]
                       current_index,
                       standout = False
                      ):
        '''
        Builds a color-annotated character list from the passed-in list.
        Displays the color-annotated list.

        Returns nothing.
        '''
        del self.__char_list[:]

        if char_list is None:
            self.__char_list_window.draw_window()
            self.refresh()
            return

        for line, char in enumerate(char_list):
            mode = curses.A_REVERSE if standout else 0
            if char.group == 'NPCs':
                mode |= self._window_manager.color_of_npc()
            elif char.name == Venue.name:
                mode |= self._window_manager.color_of_venue()
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
        ''' Touches all of this window's sub-panes.  '''
        super(MainGmWindow, self).touchwin()
        if self.__char_list_window is not None:
            self.__char_list_window.touchwin()
        if self._char_detail_window is not None:
            self._char_detail_window.touchwin()



class PersonnelGmWindow(GmWindow):
    '''
    Window display for building individual creatures, assembling creatures
    into groups, and moving creatures between groups.  A group is one of:
    'PCs', 'NPCs', or a group of monsters (for a fight).
    '''
    def __init__(self,
                 window_manager,
                 command_ribbon_choices
                ):
        super(PersonnelGmWindow, self).__init__(window_manager,
                                                curses.LINES,
                                                curses.COLS,
                                                0,
                                                0,
                                                command_ribbon_choices)
        lines, cols = self._window.getmaxyx()
        # TODO: should _char_detail be in GmWindow?
        self._char_detail = []  # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        top_line = 1
        height = (lines                 # The whole window height, except...
            - top_line                  # ...a block at the top, and...
            - (self._command_ribbon['lines_for_choices'] + 1))
                                        # ...a space for the command ribbon.

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


    def char_detail_home(self):
        ''' Scrolls the character detail pane to the top and redraws the pane. '''
        self._char_detail_window.scroll_to(0)
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def char_list_home(self):
        ''' Scrolls the character list pane to the top and redraws the pane.  '''
        self.__char_list_window.scroll_to(0)
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    def close(self):
        ''' Closes the window and disposes of its resources.  '''
        # Kill my subwindows, first
        if self.__char_list_window is not None:
            del self.__char_list_window
            self.__char_list_window = None
        if self._char_detail_window is not None:
            del self._char_detail_window
            self._char_detail_window = None
        super(PersonnelGmWindow, self).close()


    def refresh(self):
        ''' Re-draws all of the window's panes.  '''
        super(PersonnelGmWindow, self).refresh()
        if self.__char_list_window is not None:
            self.__char_list_window.refresh()
        if self._char_detail_window is not None:
            self._char_detail_window.refresh()


    def scroll_char_detail_down(self):
        ''' Scrolls the character detail pane down.  '''
        self._char_detail_window.scroll_down()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def scroll_char_detail_up(self):
        ''' Scrolls the character detail pane up.  '''
        self._char_detail_window.scroll_up()
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()


    def scroll_char_list_down(self):
        ''' Scrolls the character list pane down.  '''
        self.__char_list_window.scroll_down()
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    # TODO: genericize the scrolling stuff and just pass the window to the
    # generic routine.
    def scroll_char_list_up(self):
        ''' Scrolls the character list pane up.  '''
        self.__char_list_window.scroll_up()
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()


    # PersonnelGmWindow
    def show_creatures(self,
                       char_list,       # [ Fighter(), Fighter(), ..]
                       new_char_name,   # name of character to highlight
                       viewing_index    # index into creature list:
                                        #   dict: {'new'=True, index=0}
                      ):
        '''
        Builds a color-annotated character list from the passed-in list.
        Displays the color-annotated list.  Shows details in the right-hand
        pane for the 'current' creature,

        Returns nothing.
        '''

        # self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
        #                         #  [...],                  ]  # line 1...

        self.__char_list_window.clear()
        del self.__char_list[:]

        if char_list is None:
            self.__char_list_window.draw_window()
            self.refresh()
            return

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


    def status_ribbon(self,
                      group,            # name of group being modified,
                      template,         # name of template
                      input_filename,   # passthru to base class
                      maintain_game_file     # passthru to base class
                     ):
        '''Prints the fight round information at the top of the screen.'''

        group = '(No Group)' if group is None else group
        template = '(No Template)' if template is None else template
        self._window.move(0, 0)
        self._window.clrtoeol()

        self._window.addstr(0, 0,
                            '"%s" from "%s" template' % (group, template),
                            curses.A_NORMAL)

        super(PersonnelGmWindow, self).status_ribbon(input_filename,
                                                     maintain_game_file)

        self._window.refresh()


    def touchwin(self):
        ''' Touches all of this window's sub-panes.  '''
        super(PersonnelGmWindow, self).touchwin()
        if self.__char_list_window is not None:
            self.__char_list_window.touchwin()
        if self._char_detail_window is not None:
            self._char_detail_window.touchwin()

    #
    # Private methods
    #

    def __quit(self):
        ''' Closes the window. '''
        self._window.close()
        del self._window
        self._window = None
        return False # Leave


class FightGmWindow(GmWindow):
    '''
    Window display for running a fight.  Has panes for the current fighter,
    the current defender, and the list of creatures.
    '''
    def __init__(self,
                 window_manager,        # GmWindowManager object
                 ruleset,               # Ruleset object
                 command_ribbon_choices # dict: ord('T'): {'name': xxx,
                                        #                  'func': yyy}, ...
                ):
        super(FightGmWindow, self).__init__(window_manager,
                                            curses.LINES,
                                            curses.COLS,
                                            0,
                                            0,
                                            command_ribbon_choices)
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
        ''' Closes the window and disposes of its resources.  '''
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
        ''' Re-draws all of the window's panes.  '''
        super(FightGmWindow, self).refresh()
        if self.__character_window is not None:
            self.__character_window.refresh()
        if self.__opponent_window is not None:
            self.__opponent_window.refresh()
        if self.__summary_window is not None:
            self.__summary_window.refresh()


    def round_ribbon(self,
                     round_no,
                     next_PC_name,
                     input_filename,
                     maintain_game_file
                    ):
        '''
        Prints the fight round information at the top of the screen.

        Returns nothing
        '''

        self._window.move(0, 0)
        self._window.clrtoeol()
        lines, cols = self._window.getmaxyx()

        round_string = 'Round %d' % round_no
        self._window.addstr(0, # y
                            0, # x
                            round_string,
                            curses.A_NORMAL)

        #if saved or keep:
        #    strings = []
        #    if saved:
        #        strings.append('SAVE Fight')
        #    if keep:
        #        strings.append('KEEP Fight')
        #    string = ', '.join(strings)
        #    length = len(string)
        #    self._window.addstr(0, # y
        #                        cols - (length + 1), # x
        #                        string,
        #                        curses.A_BOLD)

        if next_PC_name is not None:
            self._window.move(self.__NEXT_LINE, 0)
            self._window.clrtoeol()
            mode = curses.color_pair(GmWindowManager.MAGENTA_BLACK)
            mode = mode | curses.A_BOLD
            self._window.addstr(self.__NEXT_LINE,
                                0,
                                ('Next PC: %s' % next_PC_name),
                                mode)

        self.status_ribbon(input_filename, maintain_game_file)
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
        '''
        Builds the windows for the fight.  This is separate from the
        constructor because you need things in the following order:
            create the big window (so we know the width of that)
            create the command ribbon (based on the width of the background
                window)
            create the sub-panes (based on the number of lines in the command
                ribbon)

        Returns: nothing.
        '''
        lines, cols = self._window.getmaxyx()
        height = (lines                 # The whole window height, except...
            - (self.__FIGHTER_LINE+1)   # ...a block at the top, and...
            - (self._command_ribbon['lines_for_choices'] + 1))
                                        # ...a space for the command ribbon.

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
        ''' Touches all of this window's sub-panes.  '''
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
                       column   # int: column in which to display |fighter|
                      ):
        '''
        Display's a summary of a single fighter.

        Returns: True if the fighter is alive (indicating that showing the
        fighter's notes might be in order), False otherwise
        '''
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
        Displays ancillary information about |fighter|.

        Returns nothing.
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
            mode = curses.color_pair(GmWindowManager.MAGENTA_BLACK) | curses.A_BOLD
            window.addstr(line, 0, '** STUNNED **', mode)
            line += 1

        # Defender

        if is_attacker:
            mode = curses.A_NORMAL
        else:
            mode = self._window_manager.color_of_fighter()
            mode = mode | curses.A_BOLD

        notes, ignore = fighter.get_defenses_notes(opponent)
        if notes is not None:
            for note in notes:
                window.addstr(line, 0, note, mode)
                line += 1

        # Attacker

        if is_attacker:
            mode = self._window_manager.color_of_fighter()
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
        '''
        Shows a short summary of each of the fighters in initiative order.

        Returns nothing.
        '''
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
        self.__window_stack = [] # Stack of GmWindow in Z order.  The screen
                                 # can be completely re-drawn by building from
                                 # the bottom of the stack to the top.
        self.STATE_COLOR = {}


    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()
            self.__stdscr.refresh() # Seems to be needed for the initial screen to be shown.
            curses.start_color()
            curses.use_default_colors()
            self.STATE_COLOR = {
                Fighter.ALIVE :
                    curses.color_pair(GmWindowManager.GREEN_BLACK),
                Fighter.INJURED :
                    curses.color_pair(GmWindowManager.YELLOW_BLACK),
                Fighter.UNCONSCIOUS :
                    curses.color_pair(GmWindowManager.MAGENTA_BLACK),
                Fighter.DEAD :
                    curses.color_pair(GmWindowManager.MAGENTA_BLACK),
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

    def color_of_fighter(self):
        return curses.color_pair(GmWindowManager.CYAN_BLACK)

    def color_of_npc(self):
        return curses.color_pair(GmWindowManager.CYAN_BLACK)

    def color_of_venue(self):
        return curses.color_pair(GmWindowManager.BLUE_BLACK)

    def display_window(self,
                       title, # string: the title displayed, centered, in the
                              #   box around the display window.
                       lines  # [[{'text', 'mode'}, ],    # line 0
                              #  [...],               ]   # line 1
                      ):
        '''
        Presents a display of |lines| to the user.  Scrollable.

        Returns: nothing
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
                    height,     # int: height of the window in characters
                    width,      # int: width of the window in characters
                    contents,   # initial string (w/ \n) for the window
                    title,      # string: the title displayed, centered, in the
                                #   box around the edit window.
                    footer      # string: something to be displayed, centered,
                                #   at the bottom of the box around the window
                   ):
        '''
        Creates a window to edit a block of text using an EMACS style
        interface.

        Returns the edited contents of the window
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
              strings,          # array of single-line strings
              title=' ERROR '   # string: the title displayed, centered, in the
                                #   box around the error message.
             ):
        ''' Displays an error to the screen. '''

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

        del border_win
        del error_win
        self.hard_refresh_all()


    def get_build_fight_gm_window(self,
                                  command_ribbon_choices
                                 ):
        '''
        Returns a PersonnelGmWindow object.  Useful for providing Mocks
        in testing.
        '''
        return PersonnelGmWindow(self, command_ribbon_choices)


    def get_fight_gm_window(self,
                            ruleset,                # Ruleset object
                            command_ribbon_choices  # dict: ord('T'):
                                                    #   {'name': xxx,
                                                    #    'func': yyy}, ...
                           ):
        '''
        Returns a FightGmWindow object.  Useful for providing Mocks in testing.
        '''
        return FightGmWindow(self, ruleset, command_ribbon_choices)


    def get_main_gm_window(self,
                           command_ribbon_choices,
                          ):
        '''
        Returns a MainGmWindow object.  Useful for providing Mocks in testing.
        '''
        return MainGmWindow(self, command_ribbon_choices)


    def get_mode_from_fighter_state(self,
                                    state # from STATE_COLOR
                                   ):
        '''
        Returns the color (in the format of a CURSES color) associated with
        |state|.
        '''
        return self.STATE_COLOR[state]


    def getmaxyx(self):
        ''' Returns a tuple containing the height and width of the screen. '''
        return curses.LINES, curses.COLS


    def get_one_character(self,
                          window=None # Window (for Curses)
                         ):
        '''Returns one character read from the keyboard.'''

        if window is None:
            window = self.__stdscr
        c = window.getch()
        # |c| will be something like ord('p') or curses.KEY_HOME
        return c


    def get_string(self, window=None):
        '''
        Returns a complete string from the keyboard.  For Curses, you have to
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
        Touches and refreshes all of the windows, in z-order, as per the
        stack.

        Returns nothing.
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
                  height,   # int: height of the data window (the box around
                            #   it will, therefore, be bigger)
                  width,    # int: width of the data window (see |height|)
                  title     # string: the title displayed, centered, in the
                            #   box around the data.
                 ):
        '''
        Provides a window to get input from the screen.

        Returns the string provided by the user.
        '''

        border_win, menu_win = self.__centered_boxed_window(height,
                                                            width,
                                                            title)
        string = self.get_string(menu_win)

        del border_win
        del menu_win
        self.hard_refresh_all()
        return string


    def menu(self,
             title,             # string: title of the menu, displayed to user
             strings_results,   # array of tuples (string, return-value).  If
                                #   |return-value| is a dict, special
                                #   processing may be perfomred, based on the
                                #   dict members.  |return-value['doit']| is
                                #   assumed to be a method whose return value
                                #   is the result of the user making this
                                #   selection.  It takes one parameter (the
                                #   value in |return-value['param']|).
                                #   |return-value['menu']| is assumed to be a
                                #   nested menu (of the form equivalent to
                                #   |strings_results|.  NOTE: ['menu'] takes
                                #   precidence over ['doit'].
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


    def pop_gm_window(self,
                      delete_this_window # GmWindow object: window to be
                                         #  removed
                     ):
        ''' Removes a specified window from the stack.  '''
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
        ''' Adds a window to the stack.  '''
        self.__window_stack.append(window)


    def refresh_all(self):
        ''' Re-draws all of the window's panes.  '''
        for window in self.__window_stack:
            window.refresh()


    #
    # Private Methods
    #

    def __centered_boxed_window(self,
                                height, # height of INSIDE window
                                width,  # width of INSIDE window
                                title,  # string: title displayed for the
                                        #   window
                                mode=curses.A_NORMAL,
                                data_for_scrolling=None
                               ):
        '''
        Creates a temporary window, on top of the current one, that is
        centered and has a box around it.

        Returns a tuple with the outer (box) and inner (data) window.
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
        'doit' function, show the menu to the user or call the 'doit' function.

        Returns the result of the menu or the return value of the 'doit'
        function, as appropriate.
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
    '''
    This class represents a window of data that might be larger than the
    window can show at one time.  The view of the data can be moved up or
    down (scrolled) as necessary.
    '''
    def __init__(self,
                 lines,             # [[{'text', 'mode'}, ...],  # line 0
                                    #  [...]                  ]  # line 1
                 window_manager,    # GmWindowManager object
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
        ''' Removes the printable data from the window. '''
        self.__window.clear()


    def draw_window(self):
        ''' Fills the window with the data that's supposed to be in it.  '''
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
        '''
        Returns a dict containing the ordinal number of the line at the top
        window and the ordinal number of the line at the bottom of the window.
        '''
        win_line_cnt, win_col_cnt = self.__window.getmaxyx()
        return {'top_line': self.top_line,
                'bottom_line': self.top_line + win_line_cnt - 1}


    def refresh(self):
        ''' Re-draws all of the window's panes.  '''
        self.__window.refresh()


    def scroll_down(self,
                    line_cnt=None,  # int: lines to scroll the window, 'None'
                                    #   scrolls a half screen.
                   ):
        ''' Scrolls the window down. '''
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


    def scroll_to(self,
                  line  # int: scroll to this line
                 ):
        ''' Scrolls the window to a specific line.  '''
        self.top_line = line
        if self.top_line < 0:
            self.top_line = 0
        if self.top_line > len(self.__lines):
            self.top_line = len(self.__lines)
        self.draw_window()


    def scroll_to_end(self):
        ''' Scrolls the window to the last line of the data. '''
        win_line_cnt, win_col_cnt = self.__window.getmaxyx()

        self.top_line = len(self.__lines) - win_line_cnt
        if self.top_line < 0:
            self.top_line = 0
        self.draw_window()


    def scroll_up(self,
                  line_cnt=None # int: number of lines to scroll, 'None'
                                #   scrolls half the screen
                 ):
        ''' Scrolls the window up. '''
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
        ''' Touches all of this window's sub-panes.  '''
        self.__window.touchwin()


class World(object):
    '''
    Manages the data in the Game File. This contains the base information for
    the entire world.
    '''
    debug_directory = 'debug'

    def __init__(self,
                 source_filename,     # Name of file that contains the Game File
                 world_details,       # GmJson object
                 ruleset,             # Ruleset object
                 program,             # Program object to collect snapshot information
                 window_manager,      # a GmWindowManager object to handle I/O
                 save_snapshot = True # Here so tests can disable it
                ):
        self.source_filename = source_filename
        self.program = program
        self.__gm_json = world_details # only used for toggling whether the
                                       # data is saved on exit of the program.
        self.details = world_details.read_data # entire dict from Game File
        self.ruleset = ruleset
        self.__window_manager = window_manager
        self.__delete_old_debug_files()
        self.__fighters = {}

        # |playing_back| is True only while we're actively playing back a
        # debug file.  There are two ways the code handles this variable.
        #
        # 1) If an action asks a question, it only asks it when NOT playing
        #    back and then it sends a 2nd action to indicate the result of
        #    the question.  When playing back, the 2nd action is played
        #    back to mimic the answer to the question.
        # 2) If an action does NOT ask a question but does issue a 2nd
        #    action, the 2nd action is sent with 'logit=False' so it is
        #    not recorded.  Then, when playing back, the 1st action will,
        #    again, issue the 2nd action (since it wasn't logged originally,
        #    the 2nd action won't be played-back twice)

        self.playing_back = False   # Are we currently playing back a debug
                                    #   file?

        if save_snapshot:
            self.do_debug_snapshot('startup')

    @staticmethod
    def get_empty_world(
            stuff=[]    # List of equipment (dict) to include in empty world
            ):
        result = { 'templates': {},
                   'fights': {},
                   'PCs': {},
                   'dead-monsters': [],
                   'current-fight': { 'history': [], 'saved': False },
                   'NPCs': {},
                   'stuff': stuff,
                   'options': {}
                 }
        return result

    def add_to_history(self,
                       action # {'name':xxx, ...} - see Ruleset::do_action()
                      ):
        ''' Adds an action to the saved history list.  '''
        self.details['current-fight']['history'].append(action)


    def clear_history(self):
        ''' Removes all the saved history data.  '''
        self.details['current-fight']['history'] = []


    def do_debug_snapshot(self,
                          tag,  # String with which to tag the debug filename
                         ):
        '''
        Saves a copy of the master Game File to a debug directory.

        Returns the filename o which the data was written.
        '''

        if tag is None:
            return None

        # Save the current Game File for debugging, later
        keep_going = True
        count = 0

        while keep_going:
            counted_tag = '%s-%d' % (tag, count)
            base_name = timeStamped('debug_json', counted_tag, 'json')
            debug_filename = os.path.join(World.debug_directory, base_name)
            if os.path.exists(debug_filename):
                count += 1
            else:
                keep_going = False


        with open(debug_filename, 'w') as f:
            json.dump(self.details, f, indent=2)

        self.program.add_snapshot(tag, debug_filename)

        return base_name


    def do_save_on_exit(self):
        '''
        Causes the local copy of the Game File data to be written back to the
        file when the program ends.

        Returns nothing.
        '''
        self.__gm_json.write_data = self.__gm_json.read_data
        ScreenHandler.maintain_game_file = False


    def dont_save_on_exit(self):
        '''
        Causes the local copy of the Game File data NOT to be written back to the
        file when the program ends.

        Returns nothing.
        '''
        self.__gm_json.write_data = None
        ScreenHandler.maintain_game_file = True


    def get_creature(self,
                     name,  # String
                     group  # String
                    ):
        '''
        Keeps the master list of Fighter objects.  If entry is a redirect, the
        complete data from the original creature is included, here, under the
        entry's heading (i.e., the same creature may appear more than once in
        this list but they all point back to the same data).

        Returns: Fighter object
        '''
        if group not in self.__fighters:
            self.__fighters[group] = {}

        if name not in self.__fighters[group]:
            self.__fighters[group][name] = Fighter(
                                            name,
                                            group,
                                            self.get_creature_details(name,
                                                                      group),
                                            self.ruleset,
                                            self.__window_manager)

        return self.__fighters[group][name]


    def get_creature_details(self,
                             name,      # string name of creature
                             group_name # string name of creature's group
                            ):
        '''
        Returns the dict containing the information for the creature in
        question.  If the group is not 'PCs' or 'NPCs', it burrows down to
        find the correct creature.

        This routine also handles redirection of creatures.  If a creature's
        whole details section is "'redirect': <group>", it says that this is
        only a copy and the original is in <group>.
        '''
        if name is None or group_name is None:
            self.__window_manager.error(
                ['Name: %r or group: %r is "None"' % (name, group_name)])
            return None

        if group_name == 'PCs':
            details = self.details['PCs'][name]
        elif group_name == 'NPCs':
            details = self.details['NPCs'][name]
        else:
            group = self.get_creature_details_list(group_name)
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


    def get_creature_details_list(self,
                      group_name  # string: 'PCs', 'NPCs', or a monster group
                     ):
        '''
        Used to get PCs, NPCs, or a fight's list of creatures.  List is in the
        order they are from the Game File (meaning that they are in random
        order).

        Returns dict of details: {name: {<details>}, name: ... }
        '''

        if group_name in self.details:
            return self.details[group_name]

        fights = self.get_fights()
        if group_name in fights:
            return self.details['fights'][group_name]['monsters']

        return None


    def get_fights(self):
        '''
        Returns {fight_name: {details}, fight_name: {details}, ...}
        '''
        return self.details['fights']


    def get_random_name(self):
        '''
        Navigates through the different categories of Names (e.g., racial,
        then male/female, etc.) to find a name.  The user is asked for a
        designation for each category but, if s/he so choses, a random value
        will be supplied.  Once the user abdicates responsibility, random
        values are chosen for the remaining categories.

        Returns a tuple that contains the name, the country name, and the
        gender of the creature.
        '''
        # TODO: should return an array so that any structure of naming
        # categories is permitted.
        randomly_generate = False

        # TODO: 'names' should be optional
        if 'names' not in self.details or self.details['names'] is None:
            return None, None, None

        # Country

        country_menu = [(x, x) for x in self.details['names']]
        country_name = self.__window_manager.menu('What kind of name',
                                               country_menu)
        if country_name is None:
            randomly_generate = True
            country_name = random.choice(self.details['names'].keys())

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

        first_name = random.choice(self.details['names'][country_name][gender])
        last_name = random.choice(self.details['names'][country_name]['last'])
        name = '%s %s' % (first_name, last_name)

        return (name, country_name, gender)


    def is_saved_on_exit(self):
        '''
        Returns True if the local copy of the Game File data will be
        automatically written to the associated file when the program exits;
        False, otherwise.
        '''
        return False if self.__gm_json.write_data is None else True


    def remove_fight(self,
                     group_name  # string, name of the fight
                    ):
        '''
        Moves fight named |group_name| to the dead-monsters list.  Removes
        local references to them.

        Returns nothing.
        '''

        if group_name in self.details['fights']:
            # Put fight in dead-monsters list
            fmt='%Y-%m-%d-%H-%M-%S'
            date = datetime.datetime.now().strftime(fmt).format()

            monsters = self.details['fights'][group_name]['monsters']
            self.details['dead-monsters'].append({'name': group_name,
                                                  'date': date,
                                                  'monsters': monsters})

            # Remove fight from regular monster list
            del self.details['fights'][group_name]
            del self.__fighters[group_name]


    def restore_fight(self,
                      group_index # index into |dead-monsters|
                     ):
        '''
        Moves a fight from the 'dead-monsters' list to the 'fights' list.
        This kind of thing is useful, for example, when a monster from a
        finished fight needs to be made into an NPC.

        Returns nothing.
        '''

        group = self.details['dead-monsters'][group_index]
        group_name = group['name']

        # Put fight into regular monster list
        self.details['fights'][group_name] = {'monsters': group['monsters']}

        # Remove fight from dead-monsters
        del(self.details['dead-monsters'][group_index])


    def toggle_saved_on_exit(self):
        '''
        Toggles whether the local copy of the Game File data is written back
        to the file when the program ends.

        Returns nothing.
        '''
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

        Returns nothing.
        '''

        minimum_files_to_keep = 10  # Arbitrary

        if not os.path.exists(World.debug_directory):
            os.makedirs(World.debug_directory)

        # Get rid of old debugging Game Files.

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
    '''
    Object that manipulates a list of equipment.  The list is assumed to be
    from somewhere in the Game File data but that's not strictly a requirement.
    '''
    def __init__(self,
                 equipment, # self.details['stuff'], list of items
                ):
        self.__equipment = equipment


    def add(self,
            new_item,   # dict describing new equipment
            source=None # string describing where equipment came from
           ):
        '''
        Adds an item to the equipment list.  If a source if given, the source
        string is added to the item's list of owners.

        Returns the current index of the item in the equipment list.
        '''
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
                          index # integer index into the equipment list
                         ):
        '''
        Returns the dictionary data of the index-th item in the equipment
        list.  Returns None if the item is not found.
        '''
        return (None if index >= len(self.__equipment) else
                                                self.__equipment[index])


    def get_item_by_name(self,              # Public to facilitate testing
                         name   # string that matches the name of the thing
                        ):
        '''
        Returns a tuple that contains index, item (i.e., the dict describing
        the item) of the (first) item in the equipment list that has a name
        that matches the passed-in name.  Returns None, None if the item is
        not found.
        '''
        for index, item in enumerate(self.__equipment):
            if item['name'] == name:
                return index, item
        return None, None # didn't find one


    def remove(self,
               item_index   # integer index into the equipment list
              ):
        '''
        Removes an item (by index) from the list of equipment.

        Returns the removed item.
        '''
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
        '''
        Checks that two objects contain the same data.  That is harder than it
        seems since dictionaries have non-constant order.  This does look
        recursively down lists, dictionaries, and scalars.

        Returns True if the left-hand-side thing contains the exact same data
        as the right-hand-side thing.  Returns False otherwise.
        '''
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
    '''
    Embodies a timer that counts down with fight rounds.  There's optional
    text associated with it (that's shown while the timer is counting down)
    and there's optional actions when the timer actually reaches zero.  This
    is an object built around data that is intended to be kept in the Game File
    data file but that's not strictly required for this object to work.
    '''
    round_count_string = '%d Rnds: ' # assume rounds takes same space as '%d'
    len_timer_leader = len(round_count_string)
    announcement_margin = 0.1 # time removed from an announcement timer so that
                              #   it'll go off at the beginning of a round
                              #   rather than the end

    def __init__(self,
                 details    # dict from the Game File, contains timer's info
           ):
        self.details = details  # This needs to actually be from the Game File


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
                    pieces, # { 'parent-name': <text>, string describing the
                            #                          thing calling the timer
                            #   'rounds': <number>,    rounds until timer fires
                            #                          (3.0 rounds fires at end
                            #                          of 3 rounds; 2.9 rounds
                            #                          fires at beginning of 3
                            #                          rounds).
                            #   'string': <text> or [<text>, <text>, ...],
                            #                          string to display (in
                            #                          fighter's notes) while
                            #                          timer is running
                            #   'actions': {'state': <text>,
                            #                          string describing new
                            #                          state of fighter (see
                            #                          Fighter.conscious_map)
                            #               'announcement': <text>},
                            #                          string to display (in
                            #                          its own window) when
                            #                          timer fires
                            # }
                   ):
        '''
        Creates a new timer from scratch (rather than from data that's already
        in the Game File).
        '''

        self.details = copy.deepcopy(pieces)
        if 'parent-name' not in self.details:
            self.details['parent-name'] = '<< Unknown Parent >>'
        if 'actions' not in self.details:
            self.details['actions'] = {}


    def get_description(self):
        '''
        Returns a long description of the timer to show the user.
        '''
        result = [] # List of strings, one per line of output
        this_line = []

        rounds = self.details['rounds']

        if ('announcement' in self.details['actions'] and
                        self.details['actions']['announcement'] is not None):
            # Add back in the little bit we shave off of an announcement so
            # that the timer will announce as the creature's round starts
            # rather than at the end.
            rounds += Timer.announcement_margin

        round_count_string = Timer.round_count_string % (rounds +
                                                    Timer.announcement_margin)
        this_line.append(round_count_string)
        if 'announcement' in self.details['actions']:
            this_line.append('[%s]' % self.details['actions']['announcement'])
            result.append(''.join(this_line))
            this_line = []

        if ('state' in self.details['actions'] and
                            self.details['actions']['state'] is not None):
            this_line.append('<%s>' % self.details['actions']['state'])
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
        Returns a short desctiption of the timer to show the user.
        '''
        this_line = []

        rounds = self.details['rounds']

        if ('announcement' in self.details['actions'] and
                        self.details['actions']['announcement'] is not None):
            # Add back in the little bit we shave off of an announcement so
            # that the timer will announce as the creature's round starts
            # rather than at the end.
            rounds += Timer.announcement_margin

        round_count_string = Timer.round_count_string % (rounds +
                                                    Timer.announcement_margin)
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
                 window_manager # GmWindowManager object for menus and error
                                #   reporting
                ):
        self.__timers = timers
        self.__window_manager = window_manager


    def make_timer(self,
                   timer_recipient_name # string
                   ):
        '''
        Makes a timer object and adds it to the Timers list.

        Returns: nothing
        '''

        timer_dict = self.make_timer_dict(timer_recipient_name)

        if timer_dict is not None:
            timer_obj = Timer(None)
            timer_obj.from_pieces(timer_dict)
            self.__timers.add(timer_obj)


    def make_timer_dict(self,
                        timer_recipient_name, # string
                       ):
        '''
        Builds the data dictionary describing a new timer.  Asks all the
        questions necessary to provide the dict with the data it needs.

        Returns: the dict for the new timer.
        '''

        # How long is the timer?

        title = 'Rounds To Wait...'
        height = 1
        width = len(title)
        adj_string = self.__window_manager.input_box(height, width, title)
        if adj_string is None or len(adj_string) <= 0:
            return None
        rounds = int(adj_string)
        if rounds <= 0:
            return None

        # What does the timer do?

        keep_asking_menu = [('yes', True), ('no', False)]
        param = {'announcement': None,
                 'continuous_message': None,
                 'state': None}
        actions_menu = [('message (continuous)',
                                {'doit': self.__continuous_message_action,
                                 'param': param}),
                        ('announcement',
                                {'doit': self.__announcement_action,
                                 'param': param}),
                        ('state change',
                                {'doit': self.__new_state_action,
                                 'param': param})]
        keep_asking = True
        while keep_asking:
            result = self.__window_manager.menu('Timer Action', actions_menu)
            if result is None:
                return None
            keep_asking = self.__window_manager.menu('Pick More Actions',
                                                     keep_asking_menu)
            if keep_asking is None:
                keep_asking = True

        # Install the timer.

        if 'announcement' in param and param['announcement'] is not None:
            # Shave a little off the time so that the timer will announce
            # as his round starts rather than at the end.
            rounds -= Timer.announcement_margin

        timer_dict = { 'parent-name': timer_recipient_name,
                       'rounds': rounds,
                       'string': param['continuous_message'],
                       'actions': {} }

        if param['announcement'] is not None:
            timer_dict['actions']['announcement'] = param['announcement']
        if param['state'] is not None:
            timer_dict['actions']['state'] = param['state']

        return timer_dict



    # Private and Protected Methods


    def __announcement_action(self,
                              param    # dict passed by the menu handler --
                                       #   contains the announcement text
                                       #   associated with the timer
                             ):
        '''
        Handler for the timer's 'what do I do with this timer' entry.

        Sets the timer up to display a window containing text when the timer
        fires.

        Returns: True -- just so it's not None
        '''
        title = 'Enter the Announcement'
        height = 1
        width = (curses.COLS - 4) - Timer.len_timer_leader
        announcement = self.__window_manager.input_box(height, width, title)
        if announcement is not None and len(announcement) <= 0:
            announcement = None
        param['announcement'] = announcement
        return True


    def __continuous_message_action(self,
                                    param   # dict passed by the menu
                                            #  handler -- contains the text
                                            #  associated with the timer
                                   ):
        '''
        Handler for the timer's 'what do I do with this timer' entry.

        Sets the timer up to display the provided text when the timer is
        displayed.

        Returns: True -- just so it's not None
        '''
        title = 'Enter the Continuous Message'
        height = 1
        width = (curses.COLS - 4) - Timer.len_timer_leader
        string = self.__window_manager.input_box(height, width, title)
        if string is not None and len(string) <= 0:
            string = None
        param['continuous_message'] = string
        return True


    def __new_state_action(self,
                           param    # dict passed by the menu handler --
                                    #   contains the destination state of the
                                    #   Fighter associated with the timer
                          ):
        '''
        Handler for the timer's 'what do I do with this timer' entry.

        Sets the timer up to change the consciousness state of it's associated
        object when the timer fires.

        Returns: True -- just so it's not None
        '''
        state_menu = [(x, x) for x in Fighter.conscious_map.keys()
                                                            if x != 'fight']
        state_menu = sorted(state_menu, key=lambda x: x[0].upper())
        state = self.__window_manager.menu('Which State', state_menu)
        if state is not None:
            param['state'] = state
        return True


class Timers(object):
    '''
    Keeps a list of timers.  There are two parallel lists: 'data' keeps the
    actual data (it's a pointer to the spot in the Game File where the ultimate
    data is stored) while 'obj' keeps Timer objects.
    '''
    def __init__(self,
                 timer_details, # List from Game File containing timers
                 owner,         # ThingsInFight object to receive timer
                                #   actions.
                 window_manager # For displaying error messages
                ):

        # data and obj are parallel arrays.  'data' is just like it is in the
        # Game File (and, in fact, should point to the Game File data) and
        # 'obj' is the Timer object from that data.
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
        '''
        Adds a timer to this list's timers.

        Returns the timer right back, again.
        '''
        self.__timers['data'].append(timer.details)
        self.__timers['obj'].append(timer)
        return timer


    def clear_all(self):
        ''' Removes all of this list's timers. '''
        # I think I have to pop the timer data, individually, because setting
        # ['data'] to [] would just remove our pointer to the Game File data
        # without modifying the Game File data.
        while len(self.__timers['data']) > 0:
            self.__timers['data'].pop()
        self.__timers['obj'] = []


    def decrement_all(self):
        ''' Decrements all timers. '''
        for timer_obj in self.__timers['obj']:
            timer_obj.decrement()


    def get_all(self):
        ''' Returns a complete list of this list's Timer objects.  '''
        return self.__timers['obj']


    def remove_expired_keep_dying(self):
        '''
        Removes expired timers BUT KEEPS the timers that are dying this
        round.  Call this at the beginning of the round.  Standard timers that
        die this round are kept so that they're shown.

        Returns nothing.
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
        Removes expired timers AND REMOVES the timers that are dying this
        round.  Call this at the end of the round to scrape off the timers
        that expire this round.

        Returns nothing.
        '''

        # TODO: should I just reverse the order we go through the timer list?
        remove_these = []
        for index, timer in enumerate(self.__timers['obj']):
            if timer.details['rounds'] <= 0:    # <= kills the timers dying
                                                #   this round
                remove_these.insert(0, index)   # largest indexes last
        for index in remove_these:
            self.__fire_timer(self.__timers['obj'][index])
            self.remove_timer_by_index(index)


    def remove_timer_by_index(self,
                              index # Index of the timer to be removed
                             ):
        '''
        Removes a timer from the timer list.

        Returns nothing.
        '''
        del self.__timers['data'][index]
        del self.__timers['obj'][index]

    #
    # Private methods
    #

    def __fire_timer(self,
                     timer  # Timer object
                    ):
        '''
        Has the timer do whatever it does when it fires (i.e., when its time
        runs out).

        Returns nothing.
        '''
        new_timer = timer.fire(self.__owner, self.__window_manager)
        if new_timer is not None:
            self.add(Timer(new_timer))


class ThingsInFight(object):
    '''
    Base class to manage timers, equipment, and notes for Fighters and Venues.
    '''
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
        '''
        Accept a new item of equipment and put it in the list.

        Returns the new index of the equipment.
        '''
        return self.equipment.add(new_item, source)


    def remove_equipment(self,
                         item_index
                        ):
        '''
        Discards an item from the Fighter's/Venue's equipment list.

        Returns: the discarded item
        '''
        return self.equipment.remove(item_index)

    #
    # Notes methods
    #

    def get_defenses_notes(self,
                           opponent # Throw away Fighter object
                          ):
        '''
        Returns a tuple of strings describing:

        1) the current (based on weapons held, armor worn, etc) defensive
           capability of the Fighter, and
        2) the pieces that went into the above calculations

        Or, in the case of the base class, None.
        '''
        return None, None


    def get_long_summary_string(self):
        '''
        Returns a string that contains a short (but not the shortest)
        description of the state of the Fighter or Venue.
        '''
        return '%s' % self.name


    def get_notes(self):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.).  There's decidedly less information than that returned by the
        base class.
        '''
        return None


    def get_short_summary_string(self):
        '''
        Returns a string that contains the shortest description of the Fighter.
        '''
        return '%s' % self.name


    def get_to_hit_damage_notes(self,
                                opponent # Throw away Fighter object
                               ):
        '''
        Returns a list of strings describing the current (using the current
        weapon, in the current posture, etc.) fighting capability (to-hit and
        damage) of a fighter.  It does nothing in the base class.
        '''
        return None

    #
    # Miscellaneous methods
    #

    def end_fight(self,
                  world,          # World object
                  fight_handler   # FightHandler object
                 ):
        '''
        Perform the post-fight cleanup.  Remove all the timers, that sort of
        thing.

        Returns nothing.
        '''
        self.timers.clear_all()

    def start_fight(self):
        '''
        Configures the Fighter or Venue to start a fight.

        Returns nothing.
        '''
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


class Venue(ThingsInFight):
    '''
    Incorporates all of the information for a room (or whatever).  This is the
    mechanism whereby items can be distributed in a room.  The data
    is just a pointer to the Game File data so that it's edited in-place.
    '''
    name = '<< ROOM >>'                 # Describes the FIGHT object
    detailed_name = '<< ROOM: %s >>'    # insert the group into the '%s' slot
    empty_venue = {
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
        super(Venue, self).__init__(Venue.name,
                                    group,
                                    details,
                                    ruleset,
                                    window_manager)
        self.detailed_name = Venue.detailed_name % group


    def get_description(self,
                        char_detail, # recepticle for character detail.
                                     # [[{'text','mode'},...],  # line 0
                                     #  [...],               ]  # line 1...
                        ):
        '''
        Provides a text description of all of the components of a Venue.

        Returns: nothing -- output is written to the |char_detail| variable
        '''

        # stuff

        mode = curses.A_NORMAL
        char_detail.append([{'text': 'Equipment',
                             'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'stuff' in self.details:
            for item in sorted(self.details['stuff'], key=lambda x: x['name']):
                found_one = True
                EquipmentManager.get_description(item, [], char_detail)

        if not found_one:
            char_detail.append([{'text': '  (None)', 'mode': mode}])

        # Timers

        mode = curses.A_NORMAL
        char_detail.append([{'text': 'Timers', 'mode': mode | curses.A_BOLD}])

        found_one = False
        timers = self.timers.get_all() # objects
        for timer in timers:
            found_one = True
            text = timer.get_description()
            leader = '  '
            for line in text:
                char_detail.append([{'text': '%s%s' % (leader, line),
                                     'mode': mode}])
                leader = '    '

        if not found_one:
            char_detail.append([{'text': '  (None)', 'mode': mode}])

        # Notes

        mode = curses.A_NORMAL
        char_detail.append([{'text': 'Notes', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in self.details:
            for note in self.details['notes']:
                found_one = True
                char_detail.append([{'text': '  %s' % note, 'mode': mode}])

        if not found_one:
            char_detail.append([{'text': '  (None)', 'mode': mode}])


    def get_state(self):
        return Fighter.FIGHT


class Fighter(ThingsInFight):
    '''
    Incorporates all of the information for a PC, NPC, or monster.  The data
    is just a pointer to the Game File data so that it's edited in-place.
    '''
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
                 fighter_details,   # dict as in the Game File
                 ruleset,           # a Ruleset object
                 window_manager     # a GmWindowManager object for display
                                    #   windows
                ):
        super(Fighter, self).__init__(name,
                                      group,
                                      fighter_details,
                                      ruleset,
                                      window_manager)
        pass


    @staticmethod
    def get_fighter_state(details):
        '''
        Returns the fighter state number.  Note that Fighter.INJURED needs to
        be calculated -- we don't store that in the Fighter as a separate
        state.
        '''
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
        '''
        Accept a new item of equipment and put it in the list.

        Returns the new index of the equipment.
        '''
        index = self.equipment.add(new_item, source)
        # TODO: Do we really need to sheath weapon and doff armor?
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
        '''
        Perform the post-fight cleanup.  Remove all the timers, reload if the
        option is set.  Sheathe the weapon.

        Returns nothing.
        '''
        super(Fighter, self).end_fight(world, fight_handler)
        if ('reload-after-fight' in world.details['options'] and
                            world.details['options']['reload-after-fight'] and
                            self.group == 'PCs'):
            self._ruleset.do_action(self,
                                    {'name': 'reload',
                                     'comment': 'Reloading after fight',
                                     'quiet': True},
                                    fight_handler)
        self.details['weapon-index'] = None


    def get_current_armor(self):
        '''
        Gets the armor the Fighter is wearing.

        Returns a tuple:
            1) a dict (from the Game File)
            2) index of the weapon
        '''
        if 'armor-index' not in self.details:
            return None, None
        armor_index = self.details['armor-index']
        if armor_index is None:
            return None, None
        armor = self.equipment.get_item_by_index(armor_index)
        return armor, armor_index


    def get_current_weapon(self):
        '''
        Gets the weapon that the Fighter is holding.

        Returns a tuple:
            1) a dict (from the Game File)
            2) index of the weapon
        '''
        if 'weapon-index' not in self.details:
            return None, None
        weapon_index = self.details['weapon-index']
        if weapon_index is None:
            return None, None
        weapon = self.equipment.get_item_by_index(weapon_index)
        return weapon, weapon_index


    def get_weapon_by_name(self,                # Public to support testing
                           name
                          ):
        '''
        Draw weapon from sheath or holster.

        Returns index, item
        '''
        index, item = self.equipment.get_item_by_name(name)
        if index is not None:
            self.details['weapon-index'] = index
        return index, item


    def remove_equipment(self,
                         item_index # <int> index into Equipment list
                        ):
        '''
        Discards an item from the Fighter's equipment list.

        Returns: the discarded item
        '''
        item = self.equipment.remove(item_index)

        # Unhand the weapon and doff the armor since the index messes that up.

        # TODO: find a way to keep the weapon and armor when an item is
        # removed.  Maybe get the name of the item, remove the equipment,
        # get_item_by_name (what to do about duplcate names?)
        self.details['weapon-index'] = None
        self.details['armor-index'] = None
        return item


    #
    # Notes related methods
    #

    def get_defenses_notes(self,
                           opponent # Fighter object
                          ):
        '''
        Returns a tuple of strings describing:

        1) the current (based on weapons held, armor worn, etc) defensive
           capability of the Fighter, and
        2) the pieces that went into the above calculations
        '''
        defense_notes, defense_why = self._ruleset.get_fighter_defenses_notes(
                                                                self,
                                                                opponent)
        return defense_notes, defense_why


    def get_description(self,
                        output, # recepticle for character detail.
                                # [[{'text','mode'},...],  # line 0
                                #  [...],               ]  # line 1...
                        ):
        '''
        Provides a text description of a Fighter including all of the
        attributes (current and permanent), equipment, etc.

        Returns: nothing.  The output is written to the |output| variable.
        '''
        self._ruleset.get_character_description(self, output)


    def get_long_summary_string(self):
        '''
        Returns a string that contains a short (but not the shortest)
        description of the state of the Fighter.
        '''
        # TODO: this is ruleset-based
        fighter_string = '%s HP: %d/%d FP: %d/%d' % (
                                    self.name,
                                    self.details['current']['hp'],
                                    self.details['permanent']['hp'],
                                    self.details['current']['fp'],
                                    self.details['permanent']['fp'])
        return fighter_string


    def get_notes(self):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.)
        '''
        notes = self._ruleset.get_fighter_notes(self)
        return notes


    def get_short_summary_string(self):
        '''
        Returns a string that contains the shortest description of the Fighter.
        '''
        # TODO: this is ruleset based
        fighter_string = '%s HP:%d/%d' % (self.name,
                                          self.details['current']['hp'],
                                          self.details['permanent']['hp'])
        return fighter_string


    def get_to_hit_damage_notes(self,
                                opponent # Fighter object
                               ):
        '''
        Returns a list of strings describing the current (using the current
        weapon, in the current posture, etc.) fighting capability (to-hit and
        damage) of the fighter.
        '''
        notes = self._ruleset.get_fighter_to_hit_damage_notes(self, opponent)
        return notes


    #
    # Miscellaneous methods
    #

    def can_finish_turn(self):
        '''
        If a Fighter has done something this turn, we can move to the next
        Fighter.  Otherwise, the Fighter should do something before we go to
        the next Fighter.

        Returns: <bool> telling the caller whether this Fighter needs to do
        something before we move on.
        '''
        return self._ruleset.can_finish_turn(self)


    def end_turn(self,
                 fight_handler  # FightHandler object
                ):
        '''
        Performs all of the stuff required for a Fighter to end his/her
        turn.

        Returns: nothing
        '''
        self._ruleset.end_turn(self, fight_handler)
        self.timers.remove_expired_kill_dying()


    def get_state(self):
        return Fighter.get_fighter_state(self.details)


    def is_absent(self):
        return True if self.details['state'] == 'absent' else False


    def is_conscious(self):
        # NOTE: 'injured' is not stored in self.details['state']
        return True if self.details['state'] == 'alive' else False


    def is_dead(self):
        return True if self.details['state'] == 'dead' else False


    def set_consciousness(self,
                          conscious_number  # <int> See Fighter.conscious_map
                         ):
        '''
        Sets the state (alive, unconscious, dead, absent, etc.) of the
        Fighter.

        Returns nothing.
        '''

        for state_name, state_num in Fighter.conscious_map.iteritems():
            if state_num == conscious_number:
                self.details['state'] = state_name
                break

        if not self.is_conscious():
            self.details['opponent'] = None # unconscious men fight nobody
            self.draw_weapon_by_index(None) # unconscious men don't hold stuff


    def start_fight(self):
        '''
        Configures the Fighter to start a fight.

        Returns nothing.
        '''
        # NOTE: we're allowing health to still be messed-up, here
        # NOTE: person may go around wearing armor -- no need to reset
        self.details['opponent'] = None
        self._ruleset.start_fight(self)


    def start_turn(self,
                   fight_handler    # FightHandler object
                  ):
        '''
        Performs all of the stuff required for a Fighter to start his/her
        turn.  Handles timer stuff.

        Returns: nothing
        '''
        self._ruleset.start_turn(self, fight_handler)
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
        '''
        Toggles the consciousness state between absent and alive.

        Returns nothing.
        '''

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
        Explains how the stuff in the descriptions were calculated.

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

    (UNHANDLED, HANDLED_OK, HANDLED_ERROR) = range(3)

    def __init__(self,
                 window_manager # GmWindowManager object for menus and errors
                ):
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
                  fighter,          # Fighter object
                  action,           # {'name': <action>, parameters...}
                  fight_handler,    # FightHandler object
                  logit=True        # Log into history and 'actions_this_turn'
                                    #   because the action is not a side-effect
                                    #   of another action
                 ):
        '''
        Executes an action for a Fighter then records that action.

        Returns nothing.
        '''
        handled = self._perform_action(fighter, action, fight_handler, logit)
        self._record_action(fighter, action, fight_handler, handled, logit)


    def get_action_menu(self,
                        action_menu,    # menu for user [(name, predicate)...]
                        fighter,        # Fighter object
                        opponent        # Fighter object
                       ):
        '''
        Builds a list of all of the things that this fighter can do this
        round.  This list will be fed to GmWindowManager.menu(), so each
        element is a tuple of

        1) the string to be displayed
        2) a dict that contains one or more of

            'text' - text to go in a timer to show what the Fighter is doing
            'action' - an action to be sent to the ruleset
            'menu' - a menu to be recursively called

        NOTE: all menu items should end, ultimately, in an 'action' because
        then the activity will be logged in the history and can be played-back
        if there's a bug to be reported.

        Returns the menu (i.e., the list)
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
                                           {'action': {'name': 'don-armor',
                                                       'armor-index': index}}
                                         ))
        don_armor_menu = sorted(don_armor_menu, key=lambda x: x[0].upper())

        # Armor menu

        if len(don_armor_menu) == 1:
            action_menu.append(
                (('Don %s' % don_armor_menu[0][0]),
                 {'action': {
                    'name': 'don-armor',
                    'armor-index': don_armor_menu[0][1]['action']['armor-index']
                  }
                 }))

        elif len(don_armor_menu) > 1:
            action_menu.append(('Don Armor', {'menu': don_armor_menu}))

        if armor is not None:
            action_menu.append((('Doff %s' % armor['name']),
                                 {'action': {'name': 'don-armor',
                                             'armor-index': None}}
                              ))

        ### Attack ###

        if holding_ranged:
            if weapon['ammo']['shots_left'] > 0:
                # Can only attack if there's someone to attack
                action_menu.extend([
                    ('attack',          {'action': {'name': 'attack'}}),
                    ('attack, all out', {'action': {'name': 'all-out-attack'}})
                ])
        else:
            action_menu.extend([
                    ('attack',          {'action': {'name': 'attack'}}),
                    ('attack, all out', {'action': {'name': 'all-out-attack'}})
            ])

        ### Draw or Holster weapon ###

        if weapon is not None:
            action_menu.append((('holster/sheathe %s' % weapon['name']),
                                   {'action': {'name': 'draw-weapon',
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
                            (item['name'], {'action': {'name': 'draw-weapon',
                                                       'weapon-index': index}
                                           }))
            draw_weapon_menu = sorted(draw_weapon_menu,
                                      key=lambda x: x[0].upper())

            # Draw menu

            if len(draw_weapon_menu) == 1:
                action_menu.append(
                    (('draw (ready, etc.; B325, B366, B382) %s' %
                                                    draw_weapon_menu[0][0]),
                     {'action': {'name': 'draw-weapon',
                                 'weapon-index':
                            draw_weapon_menu[0][1]['action']['weapon-index']}
                     }))

            elif len(draw_weapon_menu) > 1:
                action_menu.append(('draw (ready, etc.; B325, B366, B382)',
                                    {'menu': draw_weapon_menu}))

        ### RELOAD ###

        if holding_ranged:
            action_menu.append(('reload (ready)',
                               {'action': {'name': 'reload'}}
                              ))

        ### Use Item ###

        # Use SUB-menu

        use_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if item['count'] > 0:
                use_menu.append((item['name'],
                                {'action': {'name': 'use-item',
                                            'item-index': index}}
                               ))
        use_menu = sorted(use_menu, key=lambda x: x[0].upper())

        # Use menu

        if len(use_menu) == 1:
            action_menu.append(
                (('use %s' % use_menu[0][0]),
                 {'action': {'name': 'use-item',
                             'item-index':
                                use_menu[0][1]['action']['item-index']}
                 }))

        elif len(use_menu) > 1:
            action_menu.append(('use item', {'menu': use_menu}))

        ### User-defined ###

        action_menu.append(('User-defined',
                            {'action': {'name': 'user-defined'}}
                          ))

        return # No need to return action menu since it was a parameter


    def get_sample_items(self):
        '''
        Returns a list of sample equipment for creating new game files.
        '''
        return []


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


    # Ruleset
    def heal_fighter(self,
                     fighter,   # Fighter object
                     world      # World object
                    ):
        '''
        Removes all injury (and their side-effects) from a fighter.

        Returns: nothing.
        '''
        if 'permanent' not in fighter.details:
            return

        for stat in fighter.details['permanent'].iterkeys():
            fighter.details['current'][stat] = (
                                        fighter.details['permanent'][stat])
        if (fighter.details['state'] != 'absent' and
                                        fighter.details['state'] != 'fight'):
            fighter.details['state'] = 'alive'

        if ('reload-on-heal' in world.details['options'] and
                            world.details['options']['reload-on-heal'] and
                            fighter.group == 'PCs'):
            throw_away, original_weapon_index = fighter.get_current_weapon()
            for index, item in enumerate(fighter.details['stuff']):
                if item['type'] == 'ranged weapon':
                    fighter.draw_weapon_by_index(index)
                    self.do_action(fighter,
                                   {'name': 'reload',
                                    'comment': 'Reloading on heal',
                                    'notimer': True,
                                    'quiet': True},
                                   None)
            fighter.draw_weapon_by_index(original_weapon_index)


    def make_empty_creature(self):
        '''
        Builds the minimum legal character detail (the dict that goes into the
        Game File).  You can feed this to the constructor of a Fighter.  First,
        however, you need to install it in the World's Game File so that it's
        backed-up and recognized by the rest of the software.

        Returns: the dict.
        '''
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
        '''
        Looks through a creature for the regular expression |look_for_re|.

        Returns: dict: with name, group, location (where in the character the
        regex was found), and notes (text for display to the user).
        '''
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
                   fighter,          # Fighter object
                   action,           # {'name': 'adjust-hp',
                                     #  'adj': <int> # add to HP
                                     #  'comment': <string>, # optional
                                     #  'quiet': <bool> # use defaults for all
                                     #                    user interactions --
                                     #                    optional
                                     # }
                   fight_handler,    # FightHandler object
                  ):
        '''
        Action handler for Ruleset.

        Adjust the Fighter's hit points.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.details['current']['hp'] += action['adj']
        return Ruleset.HANDLED_OK


    def __do_attack(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'attack' | 'all-out-attack' |
                                      #          'move-and-attack'
                                      #  'comment': <string>, # optional
                    fight_handler     # FightHandler object
                   ):
        '''
        Action handler for Ruleset.

        Performs an attack action for the Fighter.  Picks an opponent if the
        fighter doesn't have one.  Reduces the ammo if the Fighter's weapon
        takes ammunition.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        # TODO: this should be in two parts like cast_spell since the user can
        # be asked to pick an opponent.
        if (fighter.details['opponent'] is None and
                                        fight_handler is not None and
                                        not fight_handler.world.playing_back):
            fight_handler.pick_opponent()

        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return Ruleset.HANDLED_OK

        weapon['ammo']['shots_left'] -= 1
        return Ruleset.HANDLED_OK


    # TODO: this should be a two-stage action like 'cast-spell'
    def __do_custom_action(self,
                           fighter,          # Fighter object
                           action,           # {'name': 'user-defined',
                                             #  'comment': <string>, # optional
                           fight_handler,    # FightHandler object
                          ):
        '''
        Action handler for Ruleset.

        Allows the user to describe some action that wasn't in the Ruleset or
        the derived Ruleset.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        height = 1
        title = 'What Action Is Performed'
        width = self._window_manager.getmaxyx()
        comment_string = self._window_manager.input_box(height, width, title)
        action['comment'] += ' -- %s' % comment_string
        return Ruleset.HANDLED_OK


    def __do_reload(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'reload',
                                      #  'comment': <string>, # optional
                                      #  'notimer': <bool>, # whether to
                                      #                       return a timer
                                      #                       for the fighter
                                      #                       -- optional
                                      #  'quiet': <bool>    # use defaults for
                                      #                       all user
                                      #                       interactions
                                      #                       -- optional
                                      # }
                    fight_handler,    # FightHandler object
                  ):
        '''
        Action handler for Ruleset.

        Reloads the Fighter's current weapon.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return Ruleset.HANDLED_ERROR

        clip_name = weapon['ammo']['name']
        for item in fighter.details['stuff']:
            if item['name'] == clip_name and item['count'] > 0:
                weapon['ammo']['shots_left'] = weapon['ammo']['shots']
                item['count'] -= 1
                return Ruleset.HANDLED_OK
        return Ruleset.HANDLED_ERROR


    def __don_armor(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'don-armor',
                                      #  'armor-index': <int> # index in
                                      #         fighter.details['stuff',
                                      #         None doffs armor
                                      #  'comment': <string> # optional
                    fight_handler,    # FightHandler object
                   ):
        '''
        Action handler for Ruleset.

        Dons a specific piece of armor for the Fighter.  If the index is None,
        it doffs the current armor.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.don_armor_by_index(action['armor-index'])
        return Ruleset.HANDLED_OK


    def __draw_weapon(self,
                      fighter,          # Fighter object
                      action,           # {'name': 'draw-weapon',
                                        #  'weapon-index': <int> # index in
                                        #       fighter.details['stuff'],
                                        #       None drops weapon
                                        #  'comment': <string> # optional
                      fight_handler,    # FightHandler object
                     ):
        '''
        Action handler for Ruleset.

        Draws a specific weapon for the Fighter.  If index in None, it
        holsters the current weapon.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.draw_weapon_by_index(action['weapon-index'])
        return Ruleset.HANDLED_OK


    def __end_turn(self,
                   fighter,          # Fighter object
                   action,           # {'name': 'end-turn',
                                     #  'comment': <string> # optional
                   fight_handler,    # FightHandler object
                  ):
        '''
        Action handler for Ruleset.

        Does all of the shut-down operations for a Fighter to complete his
        turn.  Moves to the next Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        if fight_handler is not None:
            fighter.end_turn(fight_handler)
            fight_handler.modify_index(1)
        return Ruleset.HANDLED_OK


    def _perform_action(self,
                        fighter,          # Fighter object
                        action,           # {'name': <action>, parameters...}
                        fight_handler,    # FightHandler object
                        logit=True        # Log into history and
                                          #  'actions_this_turn' because the
                                          #  action is not a side-effect of
                                          #  another action
                       ):
        '''
        This routine delegates actions to routines that perform the action.
        The 'doit' routines return whether the action was successfully handled
        or not (i.e., UNHANDLED, HANDLED_OK, or HANDLED_ERROR) and that is, in
        turn, returned to the calling routine.

        Default, non-ruleset related, action handling.  Good for drawing
        weapons and such.

        ONLY to be used for fights (otherwise, there's no fight handler to log
        the actions).

        This is called directly from the child ruleset (which is called from
        do_action because _perform_action is overridden by the child class.

        Returns: nothing
        '''

        actions = {
            'adjust-hp':            {'doit': self._adjust_hp},
            'all-out-attack':       {'doit': self.__do_attack},
            'attack':               {'doit': self.__do_attack},
            'don-armor':            {'doit': self.__don_armor},
            'draw-weapon':          {'doit': self.__draw_weapon},
            'end-turn':             {'doit': self.__end_turn},
            'pick-opponent':        {'doit': self.__pick_opponent},
            'reload-really':        {'doit': self.__do_reload},
            'set-consciousness':    {'doit': self.__set_consciousness},
            'set-timer':            {'doit': self.__set_timer},
            'start-turn':           {'doit': self.__start_turn},
            'use-item':             {'doit': self.__use_item},
            'user-defined':         {'doit': self.__do_custom_action},
        }

        handled = Ruleset.UNHANDLED
        if 'name' in action:
            if action['name'] in actions:
                action_info = actions[action['name']]
                if action_info['doit'] is not None:
                    handled = action_info['doit'](fighter,
                                                  action,
                                                  fight_handler)
        else:
            handled = Ruleset.HANDLED_OK  # No name? It's just a comment.

        return handled


    def __pick_opponent(self,
                        fighter,          # Fighter object
                        action,           # {'name': 'pick-opponent',
                                          #  'opponent':
                                          #     {'name': opponent_name,
                                          #      'group': opponent_group},
                                          #  'comment': <string> # optional
                        fight_handler,    # FightHandler object
                       ):
        '''
        Action handler for Ruleset.

        Establishes a Fighter's opponent for future actions.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.details['opponent'] = {'group': action['opponent']['group'],
                                       'name': action['opponent']['name']}
        return Ruleset.HANDLED_OK


    def _record_action(self,
                       fighter,          # Fighter object
                       action,           # {'name': <action>, parameters...}
                       fight_handler,    # FightHandler object
                       handled,          # bool: whether/how the action was
                                         #   handled
                       logit=True        # Log into history and
                                         #  'actions_this_turn' because the
                                         #  action is not a side-effect of
                                         #  another action
                      ):
        '''
        Logs a performed 'action' in the fight's history.

        Returns: nothing.
        '''

        if fight_handler is not None and logit:
            fight_handler.add_to_history(action)

        return


    def __set_consciousness(self,
                            fighter,          # Fighter object
                            action,           # {'name': 'set-consciousness',
                                              #  'level': <int> # see
                                              #         Fighter.conscious_map
                                              #  'comment': <string> # optional
                            fight_handler,    # FightHandler object
                           ):
        '''
        Action handler for Ruleset.

        Configures the consciousness state of the Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.set_consciousness(action['level'])
        return Ruleset.HANDLED_OK


    def __set_timer(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'set-timer',
                                      #  'timer': <dict> # see
                                      #                    Timer::from_pieces
                                      #  'comment': <string> # optional
                    fight_handler,    # FightHandler object
                   ):
        '''
        Action handler for Ruleset.

        Attaches a Timer to the Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        timer_obj = Timer(None)
        timer_obj.from_pieces(action['timer'])
        fighter.timers.add(timer_obj)
        return Ruleset.HANDLED_OK


    def __start_turn(self,
                     fighter,          # Fighter object
                     action,           # {'name': 'start-turn',
                                       #  'comment': <string> # optional
                     fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for Ruleset.

        Action to do all the preparatory work for a Fighter to start his/her
        turn.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        fighter.start_turn(fight_handler)
        return Ruleset.HANDLED_OK


    def __use_item(self,
                   fighter,          # Fighter object
                   action,           # {'name': 'use-item',
                                     #  'item-index': <int> # index in
                                     #       fighter.details['stuff']
                                     #  'comment': <string>, # optional
                   fight_handler,    # FightHandler object
                  ):
        '''
        Action handler for Ruleset.

        Use and discard a specific item (decrements its count).

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        item = fighter.equipment.get_item_by_index(action['item-index'])
        if item is not None and 'count' in item:
            item['count'] -= 1
        return Ruleset.HANDLED_OK


class GurpsRuleset(Ruleset):
    '''
    GURPS is a trademark of Steve Jackson Games, and its rules and art are
    copyrighted by Steve Jackson Games. All rights are reserved by Steve
    Jackson Games. This game aid is the original creation of Wade Guthrie and
    is released for free distribution, and not for resale, under the
    permissions granted in the
    <a href="http://www.sjgames.com/general/online_policy.html">Steve Jackson
    Games Online Policy</a>.

    Steve Jackson Games appears to allow the creation of a "Game Aid" which is
    PC-based and not a phone or tablet app.  This is done in
    http://sjgames.com/general/online_policy.html. The relevant text is as
    follows:

        "If you mean [by 'So, does that mean I can...Create a character
        generator or other game aid?] a "game aid" or "player aid" program,
        yes, you certainly can, if it's for a PC-type computer and you
        include the appropriate notices. We currently do not allow "apps"
        for mobile devices to be created using our content or trademarks. [...]

        We want to ENCOURAGE our fans to create these programs, share them
        with the community, and have fun doing it. If you want to charge money
        for a game aid based on our work, the Online Policy does NOT apply
        . . . you must either get a license from us, or sell us the game aid
        for distribution as a regular product, and either way we'll hold you
        to professional standards. Email licensing@sjgames.com with a formal
        proposal letter."

    So, we're not charging, we're not putting this on a mobile device, and the
    appropriate notices are included above, so we _should_ be good.  I've
    included the notice at the beginning of this class because it is my intent
    to compartmentalize all GURPS-specific stuff in this class.  The rest of
    this program is (supposed to be) generic.

    This is a place for all of the ruleset (GURPS, in this case) specific
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

    def __init__(self,
                 window_manager # GmWindowManager object for menus and errors
                ):
        super(GurpsRuleset, self).__init__(window_manager)


    #
    # Public Methods
    #

    def can_finish_turn(self,
                        fighter # Fighter object
                       ):
        '''
        If a Fighter has done something this turn, we can move to the next
        Fighter.  Otherwise, the Fighter should do something before we go to
        the next Fighter.

        Returns: <bool> telling the caller whether this Fighter needs to do
        something before we move on.
        '''

        # If the fighter does one of these things and the turn is over, he
        # clearly hasn't forgotten to do something.  Other actions are passive
        # and their existence doesn't mean that the fighter has actually tried
        # to do anything.

        active_actions = [
            'aim',             'all-out-attack', 'attack',
            'cast-spell',      'change-posture', 'concentrate',
            'defend',          'don-armor',      'draw-weapon',
            'evaluate',        'feint',          'move',
            'move-and-attack', 'nothing',        'reload',
            'reload-really',   'stun',           'use-item',
            'user-defined'
        ]

        for action in fighter.details['actions_this_turn']:
            if action in active_actions:
                return True

        if not fighter.is_conscious():
            return True

        return False


    def damage_to_string(self,
                         damages # list of dict -- returned by 'get_damage'.
                                 # The dict looks like:
                                 #
                                 #  {'attack_type': <string> (e.g., 'sw')
                                 #   'num_dice': <int>
                                 #   'plus': <int>
                                 #   'damage_type': <string> (e.g., 'crushing')}
                        ):
        '''
        Converts array of dicts returned by get_damage into a string.

        Returns the string.
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


    def end_turn(self,
                 fighter,       # Fighter object
                 fight_handler  # FightHandler object
                ):
        '''
        Performs all of the stuff required for a Fighter to end his/her
        turn.  Does all the consciousness/death checks, etc.

        Returns: nothing
        '''
        fighter.details['shock'] = 0

        if fighter.details['stunned'] and not fight_handler.world.playing_back:
            stunned_menu = [
                (('Succeeded (roll <= HT (%d))' %
                            fighter.details['current']['ht']), True),
                ('Missed roll', False),]
            recovered_from_stun = self._window_manager.menu(
                                        'Stunned: Roll <= HT to recover',
                                        stunned_menu)
            if recovered_from_stun:
                self.do_action(fighter,
                               {'name': 'stun', 'stun': False},
                               fight_handler)


    def get_action_menu(self,
                        fighter,    # Fighter object
                        opponent    # Fighter object
                       ):
        '''
        Builds a list of all of the things that this fighter can do this
        round.  This list will be fed to GmWindowManager.menu(), so each
        element is a tuple of

        1) the string to be displayed
        2) a dict that contains one or more of

            'text' - text to go in a timer to show what the Fighter is doing
            'action' - an action to be sent to the ruleset
            'menu' - a menu to be recursively called

        NOTE: all menu items should end, ultimately, in an 'action' because
        then the activity will be logged in the history and can be played-back
        if there's a bug to be reported.

        Returns the menu (i.e., the list)
        '''

        action_menu = []

        if fighter.details['stunned']:
            # TODO: not quite sure how to handle this one for playback
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
                posture_menu.append((posture,
                                     {'action': {'name': 'change-posture',
                                      'posture': posture}}
                                   ))


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
                        ('Bracing (B364)', {'action': {'name': 'aim',
                                                       'braced': True}
                                           }),
                        ('Not Bracing', {'action': {'name': 'aim',
                                                    'braced': False}})
                    ]
                    action_menu.append(('Aim (B324, B364)',
                                        {'menu': brace_menu}))
                else:
                    action_menu.append(('Aim (B324, B364)',
                                        {'action': {'name': 'aim',
                                                    'braced': False}}))


        action_menu.extend([
            ('posture (B551)',         {'menu': posture_menu}),
            ('Concentrate (B366)',     {'action': {'name': 'concentrate'}}),
            ('Defense, all out',       {'action': {'name': 'defend'}}),
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
                    {'action': {'name': 'cast-spell', 'spell-index': index}
                    }))
            spell_menu = sorted(spell_menu, key=lambda x: x[0].upper())

            action_menu.append(('cast Spell', {'menu': spell_menu}))


        action_menu.append(('evaluate (B364)', {'action': {'name': 'evaluate'}}
                          ))

        # Can only feint with a melee weapon
        if weapon is not None and holding_ranged == False:
            action_menu.append(('feint (B365)', {'action': {'name': 'feint'}}))

        # FP: B426
        move = fighter.details['current']['basic-move']
        if (fighter.details['current']['fp'] <
                        (fighter.details['permanent']['fp'] / 3)):
            move_string = 'half=%d (FP:B426)' % (move/2)
        else:
            move_string = 'full=%d' % move


        action_menu.extend([
            ('move (B364) %s' % move_string,
                                       {'action': {'name': 'move'}}),
            ('Move and attack (B365)', {'action': {'name': 'move-and-attack'}}),
            ('nothing',                {'action': {'name': 'nothing'}}),
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
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully block an
               attack
            2) a string describing the calculations that went into the number
        '''
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
        '''
        Provides a text description of a Fighter including all of the
        attributes (current and permanent), equipment, skills, etc.

        Portions of the character description are ruleset-specific.  That's
        why this routine is in GurpsRuleset rather than in the Fighter class.

        Returns: nothing.  The output is written to the |output| variable.
        '''

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
        '''
        Returns the list of capabilities that, according to the ruleset, a
        creature can have.  See |GurpsRuleset.abilities|
        '''
        return GurpsRuleset.abilities


    def get_damage(self,
                   fighter,   # Fighter object
                   weapon     # dict {'type': 'imp', 'thr': +1, ...}
                  ):
        '''
        Returns a tuple of:
            1) A list of dict describing the kind of damage that |fighter|
               can do with |weapon|.  A weapon can do multiple types of damage
               (for instance a sword can do swinging damage or thrust damage).
               Each type of damage looks like this:

                {'attack_type': <string> (e.g., 'sw')
                 'num_dice': <int>
                 'plus': <int>
                 'damage_type': <string> (e.g., 'crushing')}

            2) a string describing the calculations that went into the pieces
               of the dict
        '''
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
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully dodge an
               attack
            2) a string describing the calculations that went into the number
        '''
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


    def get_fight_commands(self,
                           fight_handler    # FightHandler object
                          ):
        '''
        Returns fight commands that are specific to the GURPS ruleset.  These
        commands are structured for a command ribbon.  The functions point
        right back to local functions of the GurpsRuleset.
        '''
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


    def get_fighter_defenses_notes(self,
                                   fighter, # Fighter object
                                   opponent # Fighter object
                                  ):
        '''
        Returns a tuple of strings describing:

        1) the current (based on weapons held, armor worn, etc) defensive
           capability (parry, dodge, block) of the Fighter, and
        2) the pieces that went into the above calculations
        '''
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


    def get_fighter_notes(self,
                          fighter   # Fighter object
                         ):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.)
        '''
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
            notes.append('DX and IQ are at %d (shock)' %
                                                    fighter.details['shock'])

        if (fighter.details['current']['hp'] <
                                    fighter.details['permanent']['hp']/3.0):
            # Already incorporated into Dodge
            notes.append('Dodge/Move are at 1/2')

        return notes


    def get_fighter_to_hit_damage_notes(self,
                                        fighter,    # Fighter object
                                        opponent    # Fighter object
                                       ):
        '''
        Returns a list of strings describing the current (using the current
        weapon, in the current posture, etc.) fighting capability (to-hit and
        damage) of the fighter.
        '''
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


    def get_parry_skill(self,                       # Public to aid in testing
                        fighter,    # Fighter object
                        weapon      # dict
                       ):
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully parry an
               attack
            2) a string describing the calculations that went into the number
        '''
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
        '''
        Returns a dict with the attack, defense, and target minuses for the
        given posture.
        '''
        return (None if posture not in GurpsRuleset.posture else
                                            GurpsRuleset.posture[posture])


    def get_sample_items(self):
        '''
        Returns a list of sample equipment for creating new game files.
        '''
        return [
            {
                "count": 1,
                "notes": "1d for HT+1d hrs unless other healing",
                "type": "misc",
                "owners": None,
                "name": "Patch: light heal"
            },
            {
              "count": 1,
              "owners": [],
              "name": "Armor, Light Street",
              "type": "armor",
              "notes": "Some combination of ballistic, ablative, and disruptor.",
              "dr": 3
            },
            {
                "count": 1,
                "owners": [],
                "name": "Tonfa",
                "notes": "",
                "damage": { "sw": { "type": "cr", "plus": 0 },
                            "thr": { "type": "cr", "plus": 1 } },
                "parry": 0,
                "skill": "Tonfa",
                "type": "melee weapon"
            },
            {
                "acc": 2,
                "count": 1,
                "owners": None,
                "name": "pistol, Baretta DX 192",
                "notes": "",
                "damage": {
                    "dice": { "plus": 4, "num_dice": 1, "type": "pi" }
                },
                "reload": 3,
                "skill": "Beam Weapons (Pistol)",
                "type": "ranged weapon",
                "ammo": { "name": "C Cell", "shots": 8, "shots_left": 8 }
            },
            {
                "count": 1,
                "notes": "",
                "type": "misc",
                "owners": None,
                "name": "C Cell"
            }
        ]


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
            return None, None

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
        karate).  Takes into account posture and other states to determine
        to-hit and damage for hand-to-hand and kicking.

        Returns: dict with all the information
          {
            'punch_skill': <int> number the attacker needs to hit the target
                                 while punching (for best of DX, brawling, etc.)
            'punch_string': <string> describing amount and type of damage
            'punch_damage': <dict> {'num_dice': <int>, 'plus': <int>}

            'kick_skill': <int> number the attacker needs to hit the target
                                while kicking (for best of DX, boxing, etc.)
            'kick_string': <string> describing amount and type of damage
            'kick_damage': <dict> {'num_dice': <int>, 'plus': <int>}

            'parry_skill': <int> number the defender needs to parry an attack
                                 (for best of DX, brawling, etc.)
            'parry_string': <string> describing type of parry

            'why': [] strings describing how each of the above values were
                      determined
          }
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
                                   weapon # None or dict from Game File
                                  ):
        '''
        Determines whether this weapon (which may be None) uses the unarmed
        combat skills.  That's basically a blackjack or brass knuckles but
        there may be more.  Assumes weapon's skill is the most advanced skill
        supported.

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

        return ['dx'] # Camel in Cairo -- should never get here


    # GurpsRuleset
    def heal_fighter(self,
                     fighter,   # Fighter object
                     world      # World object
                    ):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        super(GurpsRuleset, self).heal_fighter(fighter, world)
        fighter.details['shock'] = 0
        fighter.details['stunned'] = False
        fighter.details['check_for_death'] = False


    def initiative(self,
                   fighter # Fighter object
                  ):
        '''
        Generates a tuple of numbers for a creature that determines the order
        in which the creatures get to act in a fight.  Sorting creatures by
        their tuples (1st sorting key on the 1st element of the tuple, ...)
        will put them in the proper order.

        Returns: the 'initiative' tuple
        '''
        return (fighter.details['current']['basic-speed'],
                fighter.details['current']['dx'],
                Ruleset.roll(1, 6)
                )


    def is_creature_consistent(self,
                               name,    # string: creature's name
                               creature # dict from Game File
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
        '''
        Builds the minimum legal character detail (the dict that goes into the
        Game File).  You can feed this to the constructor of a Fighter.  First,
        however, you need to install it in the World's Game File so that it's
        backed-up and recognized by the rest of the software.

        Returns: the dict.
        '''
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
                  fighter           # Fighter object
                 ):
        '''
        Resets the aim for the Fighter.

        Returns: nothing.
        '''
        fighter.details['aim']['rounds'] = 0
        fighter.details['aim']['braced'] = False


    def search_one_creature(self,
                            name,       # string containing the name
                            group,      # string containing the group
                            creature,   # dict describing the creature
                            look_for_re # compiled Python regex
                           ):
        '''
        Looks through a creature for the regular expression |look_for_re|.

        Returns: dict: with name, group, location (where in the character the
        regex was found), and notes (text for display to the user).
        '''

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


    def start_turn(self,
                   fighter,         # Fighter object
                   fight_handler    # FightHandler object
                  ):
        '''
        Performs all of the stuff required for a Fighter to start his/her
        turn.  Does all the consciousness/death checks, etc.

        Returns: nothing
        '''
        playing_back = (False if fight_handler is None else
                                        fight_handler.world.playing_back)
        # B426 - FP check for consciousness
        if fighter.is_conscious() and not playing_back:
            if fighter.details['current']['fp'] <= 0:
                pass_out_menu = [(('roll <= WILL (%s), or did nothing' %
                                    fighter.details['current']['wi']), True),
                                 ('did NOT make WILL roll', False)]
                made_will_roll = self._window_manager.menu(
                    'On Action: roll <= WILL or pass out due to FP (B426)',
                    pass_out_menu)
                if not made_will_roll:
                    self.do_action(fighter,
                                   {'name': 'set-consciousness',
                                    'level': Fighter.UNCONSCIOUS},
                                   fight_handler)

        # B327 -- immediate check for death
        if (fighter.is_conscious() and fighter.details['check_for_death'] and
                                                            not playing_back):
            dead_menu = [
                (('roll <= HT (%d)' % fighter.details['current']['ht']), True),
                ('did NOT make HT roll', False)]
            made_ht_roll = self._window_manager.menu(
                ('%s: roll <= HT or DIE (B327)' % fighter.name),
                 dead_menu)

            if not made_ht_roll:
                self.do_action(fighter,
                               {'name': 'set-consciousness',
                                'level': Fighter.DEAD},
                               fight_handler)

        fighter.details['check_for_death'] = False  # Only show/roll once

        # B327 -- checking on each round whether the fighter is still
        # conscious

        if (fighter.is_conscious() and
                                    fighter.details['current']['hp'] <= 0 and
                                    not playing_back):
            unconscious_roll = fighter.details['current']['ht']
            if 'High Pain Threshold' in fighter.details['advantages']:
                unconscious_roll += 3

                menu_title = (
                    '%s: HP < 0: roll <= HT+3 (%d) or pass out (B327,B59)' %
                    (fighter.name, unconscious_roll))
            else:
                menu_title = (
                    '%s: HP < 0: roll <= HT (%d) or pass out (B327)' %
                    (fighter.name, unconscious_roll))

            pass_out_menu = [('made HT roll', True),
                             ('did NOT make HT roll', False)]
            made_ht_roll = self._window_manager.menu(menu_title, pass_out_menu)

            if not made_ht_roll:
                self.do_action(fighter,
                               {'name': 'set-consciousness',
                                'level': Fighter.UNCONSCIOUS},
                               fight_handler)

        fighter.details['actions_this_turn'] = []


    #
    # Protected and Private Methods
    #

    def _adjust_hp(self,
                   fighter,         # Fighter object
                   action,          # {'name': 'adjust-hp',
                                    #  'adj': <number (usually < 0) HP change>,
                                    #  'comment': <string>, # optional
                                    #  'quiet': <bool - use defaults for all
                                    #            user interactions.> }
                   fight_handler,
                  ):
        '''
        NOTE: This is a huge tangle because, for the GurpsRuleset, we need to
        ask questions (i.e., whether or not to subtract DR from the HP).
        Because of that, there are 2 events: 1) adjust-hp asks the question
        and generates the 2nd event adjust-hp-really EXCEPT for playback mode,
        where it does nothing.  2) adjust-hp-really contains the post-DR
        adjustment and actually reduces the HP.

        ON TOP OF THAT, adjust-hp is handled differently than the rest of the
        actions.  Normally, there's a Ruleset.__xxx and a GurpsRuleset.__xxx
        and they're called in a cascaded manner:

                            GurpsRuleset       Ruleset
                                 |                |
                                 -                -
                    do_action ->| |- do_action ->| |- __xxx -+
                                | |              | |         |
                                | |              | ||<-------+
                                | |<- - - - - - -| |
                                | |- __xxx -+     -
                                | |         |     |
                                | ||<-------+     |
                                 -                |
                                 |                |

        _adjust_hp, though, is PROTECTED (not private) so Ruleset::do_action
        actually calls GurpsRuleset::_xxx and Ruleset::_xxx is overridden:

                            GurpsRuleset         Ruleset
                                 |                  |
                                 -                  -
                    do_action ->| |-- do_action -->| |- _adjust_hp --+
                                | |                | |               |
                                | ||<- _adjust_hp -------------------+
                                | ||- - - - - - - >| |
                                | |                | |
                                | |<- - - - - - - -| |
                                 -                  -
                                 |                  |

        Ruleset::_adjust_hp never gets called for the adjust-hp action.
        Ruleset's function gets called, directly, by the 2nd (GurpsRulest-
        specific) action.

        We do things this way because a) GurpsRuleset::_adjust_hp modifies the
        adj (in the case of armor) so we can't call the Ruleset's version
        first (it has bad data) and b) we can't ask questions in an action
        during playback.
        '''

        if fight_handler.world.playing_back:
            # This is called from Ruleset::do_action so we have to have a
            # return value that works, there.
            return Ruleset.HANDLED_OK

        adj = action['adj']
        quiet = False if 'quiet' not in action else action['quiet']

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

            if not quiet and dr != 0:
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
                    return Ruleset.HANDLED_OK

                original_adj = adj

                adj += dr
                action['adj'] = adj

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
                self.do_action(fighter,
                               {'name': 'set-consciousness',
                                'level': Fighter.DEAD},
                               fight_handler)
            else:
                threshold = -fighter.details['permanent']['hp']
                while fighter.details['current']['hp'] <= threshold:
                    threshold -= fighter.details['permanent']['hp']
                if adjusted_hp <= threshold:
                    self.do_action(fighter,
                                   {'name': 'check-for-death',
                                    'value': True},
                                   fight_handler)

            # Check for Major Injury (B420)
            if -adj > (fighter.details['permanent']['hp'] / 2):
                (SUCCESS, SIMPLE_FAIL, BAD_FAIL) = range(3)
                total = fighter.details['current']['ht']
                if 'High Pain Threshold' in fighter.details['advantages']:
                    total = fighter.details['current']['ht'] + 3
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT+3 (%d) or be stunned' %
                                                                        total)
                #elif 'Low Pain Threshold' in fighter.details['advantages']:
                #    total = fighter.details['current']['ht'] - 4
                #    menu_title = (
                #       'Major Wound (B420): Roll vs. HT-4 (%d) or be stunned' %
                #                                                        total)
                else:
                    total = fighter.details['current']['ht']
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT (%d) or be stunned' %
                                                                        total)

                stunned_menu = [
                   ('Succeeded (roll <= HT (%d))' % total,
                                 GurpsRuleset.MAJOR_WOUND_SUCCESS),
                   ('Missed roll by < 5 (roll < %d) -- stunned' % (total+5),
                                 GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL),
                   ('Missed roll by >= 5 (roll >= %d -- unconscious)' %
                                                                    (total+5),
                                 GurpsRuleset.MAJOR_WOUND_BAD_FAIL),
                               ]
                stunned_results = self._window_manager.menu(menu_title,
                                                            stunned_menu)
                if stunned_results == GurpsRuleset.MAJOR_WOUND_BAD_FAIL:
                    self.do_action(fighter,
                                   {'name': 'set-consciousness',
                                    'level': Fighter.UNCONSCIOUS},
                                   fight_handler)
                elif stunned_results == GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL:
                    self.do_action(fighter,
                                   {'name': 'change-posture',
                                    'posture': 'lying'},
                                   fight_handler)
                    self.do_action(fighter,
                                   {'name': 'stun',
                                    'stun': True},
                                   fight_handler)

        if 'High Pain Threshold' not in fighter.details['advantages']: # B59
            # Shock (B419) is cumulative but only to a maximum of -4
            # Note: 'adj' is negative
            shock_level = fighter.details['shock'] + adj
            if shock_level < -4:
                shock_level = -4
            self.do_action(fighter,
                           {'name': 'shock', 'value': shock_level},
                           fight_handler)

        # WILL roll or lose aim
        if fighter.details['aim']['rounds'] > 0:
            aim_menu = [('made WILL roll', True),
                        ('did NOT make WILL roll', False)]
            made_will_roll = self._window_manager.menu(
                ('roll <= WILL (%d) or lose aim' %
                                            fighter.details['current']['wi']),
                aim_menu)
            if not made_will_roll:
                self.do_action(fighter, {'name': 'reset-aim'}, fight_handler)

        # Have to copy the action because using the old one confuses the
        # do_action routine that called this function.
        new_action = copy.deepcopy(action)
        new_action['name'] = 'adjust-hp-really'
        self.do_action(fighter, new_action, fight_handler)
        return Ruleset.HANDLED_OK


    def __adjust_hp_really(self,
                           fighter,         # Fighter object
                           action,          # {'name': 'adjust-hp-really',
                                            #  'comment': <string>, # optional
                                            #  'adj': <number = HP change>,
                                            #  'quiet': <bool - use defaults
                                            #            for all user
                                            #            interactions.> }
                           fight_handler,
                          ):
        '''
        Action handler for GurpsRuleset.

        This is the 2nd part of a 2-part action.  This action
        ('adjust-hp-really') actually perfoms all the actions and
        side-effects of changing the hit-points.  See
        |GurpsRuleset::_adjust_hp| for an idea of how this method is used.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        super(GurpsRuleset, self)._adjust_hp(fighter, action, fight_handler)
        return None # No timers


    def __cast_spell(self,
                     fighter,      # Fighter object
                     action,       # {'name': 'cast-spell',
                                   #  'spell-index': <index in 'spells'>, ...
                                   #  'comment': <string>, # optional
                     fight_handler # FightHandler object
                    ):
        '''
        Action handler for GurpsRuleset.

        This is the 1st part of a 2-part action.  This action ('cast-spell')
        asks questions of the user and sends the second part
        ('cast-spell-really').  The 1st part isn't executed when playing back.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        if fight_handler is not None and fight_handler.world.playing_back:
            return None # No timers

        # Assemble the spell from the ruleset's copy of it and the Fighter's
        # copy of it.

        spell_index = action['spell-index']
        spell = fighter.details['spells'][spell_index]

        if spell['name'] not in GurpsRuleset.spells:
            self._window_manager.error(
                ['Spell "%s" not in GurpsRuleset.spells' % spell['name']]
            )
            return None # No timers
        complete_spell = copy.deepcopy(spell)
        complete_spell.update(GurpsRuleset.spells[spell['name']])

        # Duration

        if complete_spell['duration'] is None:
            title = 'Duration for (%s) - see (%s) ' % (
                                                    complete_spell['name'],
                                                    complete_spell['notes'])
            height = 1
            width = len(title)
            duration_string = ''
            while len(duration_string) <= 0:
                duration_string = self._window_manager.input_box(height,
                                                                 width,
                                                                 title)
            complete_spell['duration'] = int(duration_string)

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
            complete_spell['cost'] = int(cost_string)

        # M8 - High skill level costs less
        skill = complete_spell['skill'] - 15
        while skill >= 0:
            complete_spell['cost'] -= 1
            skill -= 5
        if complete_spell['cost'] <= 0:
            complete_spell['cost'] = 0

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
            complete_spell['casting time'] = int(casting_time_string)

        # Opponent?

        opponent = None
        if fight_handler is not None:
            opponent = fight_handler.get_opponent_for(fighter)

        if opponent is not None:
            opponent_timer_menu = [('yes', True), ('no', False)]
            timer_for_opponent = self._window_manager.menu(
                                        ('Mark %s with spell' % opponent.name),
                                        opponent_timer_menu)
            if not timer_for_opponent:
                opponent = None

        # Send the action for the second part

        new_action = {'name': 'cast-spell-really',
                      'complete spell': complete_spell}

        if opponent is not None:
            new_action['opponent'] = {'name': opponent.name,
                                      'group': opponent.group}

        self.do_action(fighter, new_action, fight_handler)

        return None # No new timers


    def __cast_spell_really(self,
                            fighter,      # Fighter object
                            action,       # {'name': 'cast-spell-really'
                                          #  'complete spell': <dict> # this
                                          #     is a combination of the spell
                                          #     in the character details and
                                          #     the same spell from the
                                          #     ruleset
                                          #  'comment': <string>, # optional
                            fight_handler # FightHandler object
                           ):
        '''
        Action handler for GurpsRuleset.

        This is the 2nd part of a 2-part action.  This action
        ('cast-spell-really') actually perfoms all the actions and
        side-effects of casting a spell.  This is mostly a bunch of timers.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        complete_spell = action['complete spell']

        # Charge the spell caster for the spell.

        if complete_spell['cost'] > 0:
            self.do_action(fighter,
                           {'name': 'adjust-fp',
                            'adj': -complete_spell['cost']},
                           fight_handler,
                           logit=False)

        # Duration Timer


        # If the spell lasts any time at all, put a timer up so that we see
        # that it's active

        duration_timer = Timer(None)
        if complete_spell['duration'] > 0:
            duration_timer.from_pieces(
                       {'parent-name': fighter.name,
                        'rounds': complete_spell['duration'] -
                                                    Timer.announcement_margin,
                        'string': 'CAST SPELL (%s) ACTIVE' %
                                                        complete_spell['name']
                       })

        # Casting Timer

        casting_timer = Timer(None)
        text = [('Casting (%s) @ skill (%d): %s' % (complete_spell['name'],
                                                    complete_spell['skill'],
                                                    complete_spell['notes'])),
                ' Defense: none',
                ' Move: none']

        actions = {'timer': duration_timer.details}
        if complete_spell['duration'] == 0:
            actions['announcement'] = ('CAST SPELL (%s) FIRED' %
                                                        complete_spell['name'])

        casting_timer.from_pieces({'parent-name': fighter.name,
                           'rounds': complete_spell['casting time'] -
                                                Timer.announcement_margin,
                           'string': text,
                           'actions': actions})
        casting_timer.mark_owner_as_busy()  # When casting, the owner is busy

        # Opponent's Timers

        if 'opponent' in action and fight_handler is not None:
            opponent = fight_handler.get_fighter_object(
                                            action['opponent']['name'],
                                            action['opponent']['group'])

            spell_timer = Timer(None)
            if complete_spell['duration'] > 0:
                spell_timer.from_pieces(
                         {'parent-name': opponent.name,
                          'rounds': complete_spell['duration'] -
                                                Timer.announcement_margin,
                          'string': 'SPELL "%s" AGAINST ME' %
                                                    complete_spell['name']
                         })

            delay_timer = Timer(None)

            actions = {'timer': spell_timer.details}
            if complete_spell['duration'] == 0:
                actions['announcement'] = ('SPELL (%s) AGAINST ME FIRED' %
                                                        complete_spell['name'])

            # Add 1 to the timer because the first thing the opponent will see
            # is a decrement (the caster only sees the decrement on the _next_
            # round)
            delay_timer.from_pieces(
                     {'parent-name': opponent.name,
                      'rounds': 1 + complete_spell['casting time'] -
                                                Timer.announcement_margin,
                      'string': ('Waiting for "%s" spell to take affect' %
                                                complete_spell['name']),
                      'actions': actions
                     })

            opponent.timers.add(delay_timer)

        return casting_timer


    def __change_posture(self,
                         fighter,          # Fighter object
                         action,           # {'name': 'change-posture',
                                           #  'posture': <string> # posture
                                           #        from GurpsRuleset.posture
                                           #  'comment': <string>, # optional
                         fight_handler     # FightHandler object
                        ):
        '''
        Action handler for GurpsRuleset.

        Changes the posture of the Fighter.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['posture'] = action['posture']
        self.reset_aim(fighter)

        # Timer

        timer = Timer(None)

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1 - Timer.announcement_margin,
                           'string': ['Change posture',
                                      ' NOTE: crouch 1st action = free',
                                      '       crouch->stand = free',
                                      '       kneel->stand = step',
                                      ' Defense: any',
                                      ' Move: none'] })

        return timer


    def __check_for_death(self,
                          fighter,          # Fighter object
                          action,           # {'name': 'check-for-death',
                                            #  'value': <bool>,
                                            #  'comment': <string>, # optional
                          fight_handler     # FightHandler object
                         ):
        '''
        Action handler for GurpsRuleset.

        Sets the Fighter's 'check_for_death' field.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['check_for_death'] = action['value']
        return None # No timer


    def __damage_FP(self,
                    param    # {'view': xxx, 'view-opponent': xxx,
                             #  'current': xxx, 'current-opponent': xxx,
                             #  'fight_handler': <fight handler> } where
                             # xxx are Fighter objects
                   ):
        '''
        Command ribbon method.

        Figures out from whom to remove fatigue points and removes them (via
        an action).

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

        fight_handler = (None if 'fight_handler' not in param
                                                else param['fight_handler'])
        self.do_action(fp_recipient,
                       {'name': 'adjust-fp', 'adj': adj, 'comment': comment},
                       fight_handler)

        return True # Keep going


    def __do_adjust_fp(self,
                       fighter,      # Fighter object
                       action,       # {'name': 'adjust-fp',
                                     #  'adj': <int> # number to add to FP
                                     #  'comment': <string>, # optional
                       fight_handler # FightHandler object (for logging)
                      ):
        '''
        Action handler for GurpsRuleset.

        Adjusts the fatigue points of a Fighter and manages all of the side-
        effects associated therewith.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        # See B426 for consequences of loss of FP
        adj = action['adj'] # Adj is likely negative

        # If FP go below zero, you lose HP along with FP
        hp_adj = 0
        if adj < 0  and -adj > fighter.details['current']['fp']:
            hp_adj = adj
            if fighter.details['current']['fp'] > 0:
                hp_adj += fighter.details['current']['fp']

        if hp_adj < 0:
            self.do_action(fighter,
                           {'name': 'adjust-hp', 'adj': hp_adj, 'quiet': True},
                           fight_handler,
                           logit=False)

        fighter.details['current']['fp'] += adj

        if (fighter.details['current']['fp'] <=
                                        -fighter.details['permanent']['fp']):
            self.do_action(fighter,
                           {'name': 'set-consciousness',
                            'level': Fighter.UNCONSCIOUS},
                           fight_handler,
                           logit=False)
        return None  # No timer


    def __do_adjust_shock(self,
                 fighter,      # Fighter object
                 action,       # {'name': 'shock',
                               #  'value': <int> # level to which to set shock
                               #  'comment': <string>, # optional
                 fight_handler # FightHandler object
                ):
        '''
        Action handler for GurpsRuleset.

        Changes the Fighter's shock value.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['shock'] = action['value']
        return None  # No timer


    def __do_aim(self,
                 fighter,      # Fighter object
                 action,       # {'name': 'aim',
                               #  'braced': <bool> # see B364
                               #  'comment': <string>, # optional
                 fight_handler # FightHandler object
                ):
        '''
        Action handler for GurpsRuleset.

        Peforms the 'aim' action.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        if fight_handler is not None and not fight_handler.world.playing_back:
            if fighter.details['opponent'] is None:
                fight_handler.pick_opponent()

        rounds = fighter.details['aim']['rounds']
        if rounds == 0:
            fighter.details['aim']['braced'] = action['braced']
            fighter.details['aim']['rounds'] = 1
        elif rounds < 3:
            fighter.details['aim']['rounds'] += 1

        # Timer

        timer = Timer(None)
        timer.from_pieces(
            {'parent-name': fighter.name,
             'rounds': 1 - Timer.announcement_margin,
             'string': [('Aim%s' % (' (braced)' if action['braced'] else '')),
                         ' Defense: any loses aim',
                         ' Move: step']
            })

        return timer


    def __do_attack(self,
                   fighter,          # Fighter object
                   action,           # {'name': 'attack' | 'all-out-attack' |
                                     #          'move-and-attack'
                                     #  'comment': <string>, # optional
                   fight_handler     # FightHandler object
                  ):
        '''
        Action handler for GurpsRuleset.

        Does the ruleset-specific stuff for an attack.  MOSTLY, that's just
        creating the timer, though, since I don't currently have the code roll
        anything (putting this in a comment will come back to bite me when I
        inevitably add that capability to the code but not read and repair the
        comments).

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = Timer(None)

        move = fighter.details['current']['basic-move']
        if action['name'] == 'all-out-attack':
            text = ['All out attack',
                    ' Defense: none',
                    ' Move: 1/2 = %d' % (move/2)]

        elif action['name'] == 'attack':
            text = ['Attack', ' Defense: any', ' Move: step']

        elif action['name'] == 'move-and-attack':
            # FP: B426
            if (fighter.details['current']['fp'] <
                            (fighter.details['permanent']['fp'] / 3)):
                move_string = 'half=%d (FP:B426)' % (move/2)
            else:
                move_string = 'full=%d' % move

            # Move and attack info
            text = ['Move & Attack',
                    ' Defense: Dodge,block',
                    ' Move: %s' % move_string]

            weapon, throw_away = fighter.get_current_weapon()
            holding_ranged = (False if weapon is None else
                                        (weapon['type'] == 'ranged weapon'))
            if fight_handler is None:
                opponent = None
            else:
                opponent = fight_handler.get_opponent_for(fighter)
            if weapon is None:
                unarmed_skills = self.get_weapons_unarmed_skills(weapon)
                unarmed_info = self.get_unarmed_info(fighter,
                                                     opponent,
                                                     weapon,
                                                     unarmed_skills)
                to_hit = unarmed_info['punch_skill'] - 4
                to_hit = 9 if to_hit > 9 else to_hit
                text.append(' Punch to-hit: %d' % to_hit)

                to_hit = unarmed_info['kick_skill'] - 4
                to_hit = 9 if to_hit > 9 else to_hit
                text.append(' Kick to-hit: %d' % to_hit)
            else:
                to_hit, ignore_why = self.get_to_hit(fighter, opponent, weapon)
                if holding_ranged:
                    to_hit -= 2 # or weapon's bulk rating, whichever is worse
                else:
                    to_hit -= 4

                to_hit = 9 if to_hit > 9 else to_hit
                text.append(' %s to-hit: %d' % (weapon['name'], to_hit))

        else:
            text = ['<<UNHANDLED ACTION: %s' % action['name']]

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1 - Timer.announcement_margin,
                           'string': text})
        return timer


    def __do_nothing(self,
                     fighter,      # Fighter object
                     action,       # {'name': 'concentrate' | 'evaluate' |
                                   #          'feint' | 'move' | 'nothing' |
                                   #          'pick-opponent' | 'use-item' |
                                   #          'user-defined',
                                   #  'comment': <string>, # optional
                                   #
                                   # NOTE: Some actions have other
                                   # parameters used buy |Ruleset|
                                   #
                     fight_handler # FightHandler object
                    ):
        '''
        Action handler for GurpsRuleset.

        Does nothing but create the appropriate timer for the action.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        # Timer

        timer = Timer(None)

        if 'name' not in action:
            return None

        if action['name'] == 'nothing':
            text = ['Do nothing', ' Defense: any', ' Move: none']

        elif action['name'] == 'move':
            move = fighter.details['current']['basic-move']

            if (fighter.details['current']['fp'] <
                            (fighter.details['permanent']['fp'] / 3)):
                move_string = 'half=%d (FP:B426)' % (move/2)
            else:
                move_string = 'full=%d' % move
            text = ['Move', ' Defense: any', ' Move: %s' % move_string]

        elif action['name'] == 'feint':
            text = ['Feint',
                    ' Contest of melee weapon or DX',
                    '   subtract score from opp',
                    '   active defense next turn',
                    '   (for both, if all-out-attack)',
                    ' Defense: any, parry *',
                    ' Move: step']

        elif action['name'] == 'evaluate':
            text = ['Evaluate', ' Defense: any', ' Move: step']


        elif action['name'] == 'concentrate':
            text = ['Concentrate', ' Defense: any w/will roll', ' Move: step']

        elif action['name'] == 'use-item':
            item = fighter.equipment.get_item_by_index(action['item-index'])
            text = [('Use %s' % item['name']),
                    ' Defense: (depends)',
                    ' Move: (depends)']

        elif action['name'] == 'user-defined':
            text = ['User-defined action']

        elif action['name'] == 'pick-opponent':
            return None

        else:
            text = ['<<UNHANDLED ACTION: %s' % action['name']]

        timer.from_pieces( {'parent-name': fighter.name,
                            'rounds': 1 - Timer.announcement_margin,
                            'string': text} )

        return timer


    def __do_reload(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'reload',
                                      #  'notimer': <bool>, # whether to
                                      #                       return a timer
                                      #                       for the fighter
                                      #                       -- optional
                                      #  'comment': <string>, # optional
                                      #  'quiet': <bool>    # use defaults for
                                      #                       all user
                                      #                       interactions
                                      #                       -- optional
                                      # }
                    fight_handler,    # FightHandler object
                  ):
        '''
        Action handler for GurpsRuleset.

        This is the 1st part of a 2-part action.  This action ('reload') asks
        questions of the user and sends the second part ('reload-really').
        The 1st part isn't executed when playing back.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        if fight_handler is not None and fight_handler.world.playing_back:
            return None # No timer

        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return None # No timer

        # Check to see if we need a reload at all

        if weapon['ammo']['shots_left'] == weapon['ammo']['shots']:
            return None # No timer

        # If we do, how long will it take?

        reload_time = weapon['reload']

        # B43: combat reflexes
        if 'Combat Reflexes' in fighter.details['advantages']:
            reload_time -= 1

        quiet = False if 'quiet' not in action else action['quiet']
        if not quiet:
            # B194: fast draw
            if 'Fast-Draw (Ammo)' in fighter.details['skills']:
                skill_menu = [('made SKILL roll', True),
                              ('did NOT make SKILL roll', False)]
                made_skill_roll = self._window_manager.menu(
                    ('roll <= fast-draw skill (%d)' %
                            fighter.details['skills']['Fast-Draw (Ammo)']),
                    skill_menu)

                if made_skill_roll:
                    reload_time -= 1

        if reload_time > 0:
            new_action = {'name': 'reload-really', 'time': reload_time}
            if 'notimer' in action:
                new_action['notimer'] = action['notimer']
            self.do_action(fighter, new_action, fight_handler)

        return None # No timer


    def __do_reload_really(self,
                           fighter, # Fighter object
                           action,  # {'name': 'reload-really',
                                    #  'notimer': <bool>, # whether to
                                    #                       return a timer
                                    #                       for the fighter
                                    #                       -- optional
                                    #  'comment': <string>, # optional
                                    #  'quiet': <bool>    # use defaults for
                                    #                       all user
                                    #                       interactions
                                    #                       -- optional
                                    #  'time': <duration>}
                                    # }
                           fight_handler,    # FightHandler object
                         ):
        '''
        Action handler for GurpsRuleset.

        This is the 2nd part of a 2-part action.  This action ('reload-really')
        actually perfoms all the GurpsRuleset-specific actions and
        side-effects of reloading the Fighter's current weapon.  Note that a
        lot of the obvious part is done by the base class Ruleset.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        self.reset_aim(fighter)

        # Timer

        timer = None
        if 'notimer' not in action or not action['notimer']:
            timer = Timer(None)
            timer.from_pieces(
                        {'parent-name': fighter.name,
                         'rounds': action['time'] - Timer.announcement_margin,
                         'string': 'RELOADING'} )

            timer.mark_owner_as_busy()  # When reloading, the owner is busy

        return timer


    def __draw_weapon(self,
                      fighter,          # Fighter object
                      action,           # {'name': 'draw-weapon',
                                        #  'weapon-index': <int> # index in
                                        #       fighter.details['stuff'],
                                        #       None drops weapon
                                        #  'comment': <string>, # optional
                      fight_handler,    # FightHandler object
                     ):
        '''
        Action handler for GurpsRuleset.

        Does the ruleset-specific stuff to draw or holster a weapon.  The
        majority of the work for this is actually done in the base class.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = Timer(None)

        weapon, throw_away = fighter.get_current_weapon()

        #if 'Fast-Draw (Pistol)' in fighter.details['skills']:
        #    skill_menu = [('made SKILL roll', True),
        #                  ('did NOT make SKILL roll', False)]
        #    made_skill_roll = self._window_manager.menu(
        #        ('roll <= fast-draw skill (%d)' %
        #                fighter.details['skills']['Fast-Draw (Ammo)']),
        #        skill_menu)
        #
        #    if made_skill_roll:
        #        ...

        title = 'Holster weapon' if weapon is None else (
                                                'Draw %s' % weapon['name'])

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1 - Timer.announcement_margin,
                           'string': [title, ' Defense: any', ' Move: step']})
        return timer


    def __get_damage_type_str(self,
                              damage_type   # <string> key in
                                            #   GurpsRuleset.damage_mult
                             ):
        '''
        Expands the short-hand version of damage type with the long form (that
        includes the damage multiplier).

        Returns the long form string.
        '''
        if damage_type in GurpsRuleset.damage_mult:
            damage_type_str = '%s=x%.1f' % (
                                        damage_type,
                                        GurpsRuleset.damage_mult[damage_type])
        else:
            damage_type_str = '%s' % damage_type
        return damage_type_str


    def _perform_action(self,
                        fighter,          # Fighter object
                        action,           # {'name': <action>, parameters...}
                        fight_handler,    # FightHandler object
                        logit=True        # Log into history and
                                          #  'actions_this_turn' because the
                                          #  action is not a side-effect of
                                          #  another action
                       ):
        '''
        This routine delegates actions to routines that perform the action.
        The action routine may return a timer.  _this_ routine adds the timer
        to the Fighter.  That timer is there, primarily, to keep track of what
        the Fighter did but it can also mark the Fighter as busy for a
        multi-round action.

        Returns: nothing
        '''

        # Label the action so playback knows who receives it.

        action['fighter'] = {}
        action['fighter']['name'] = fighter.name
        action['fighter']['group'] = fighter.group

        # PP = pprint.PrettyPrinter(indent=3, width=150)
        # PP.pprint(action)

        # Call base class' perform_action FIRST because GurpsRuleset depends on
        # the actions of the base class.  It make no sense for the base class'
        # actions to depend on the child class'.

        handled = super(GurpsRuleset, self)._perform_action(fighter,
                                                            action,
                                                            fight_handler)

        # The 'really' actions are used when an action needs to ask questions
        # of the user.  The original action asks the questions and sends the
        # 'really' action with all of the answers.  When played back, the
        # original action just returns.  That way, there are no questions on
        # playback and the answers are the same as they were the first time.

        actions = {
            'adjust-fp':            {'doit': self.__do_adjust_fp},
            'adjust-hp-really':     {'doit': self.__adjust_hp_really},
            'aim':                  {'doit': self.__do_aim},
            'all-out-attack':       {'doit': self.__do_attack},
            'attack':               {'doit': self.__do_attack},
            'cast-spell':           {'doit': self.__cast_spell},
            'cast-spell-really':    {'doit': self.__cast_spell_really},
            'change-posture':       {'doit': self.__change_posture},
            'check-for-death':      {'doit': self.__check_for_death},
            'concentrate':          {'doit': self.__do_nothing},
            'defend':               {'doit': self.__reset_aim},
            'don-armor':            {'doit': self.__reset_aim},
            'draw-weapon':          {'doit': self.__draw_weapon},
            'evaluate':             {'doit': self.__do_nothing},
            'feint':                {'doit': self.__do_nothing},
            'move':                 {'doit': self.__do_nothing},
            'move-and-attack':      {'doit': self.__do_attack},
            'nothing':              {'doit': self.__do_nothing},
            'pick-opponent':        {'doit': self.__do_nothing},
            'reload':               {'doit': self.__do_reload},
            'reload-really':        {'doit': self.__do_reload_really},
            'reset-aim':            {'doit': self.__reset_aim},
            'set-consciousness':    {'doit': self.__reset_aim},
            'shock':                {'doit': self.__do_adjust_shock},
            'stun':                 {'doit': self.__stun_action},
            'use-item':             {'doit': self.__do_nothing},
            'user-defined':         {'doit': self.__do_nothing},
        }

        if 'name' not in action:
            return handled

        if handled == Ruleset.HANDLED_ERROR:
            return  handled

        if action['name'] in actions:
            timer = None
            action_info = actions[action['name']]
            if action_info['doit'] is not None:
                timer = action_info['doit'](fighter, action, fight_handler)
            handled = Ruleset.HANDLED_OK

            if timer is not None and logit:
                fighter.timers.add(timer)

        return handled


    def _record_action(self,
                       fighter,          # Fighter object
                       action,           # {'name': <action>, parameters...}
                       fight_handler,    # FightHandler object
                       handled,          # bool: whether/how the action was
                                         #   handled
                       logit=True        # Log into history and
                                         #  'actions_this_turn' because the
                                         #  action is not a side-effect of
                                         #  another action
                      ):
        '''
        Saves a performed 'action' in the Fighter's did-it-this-round list.

        Returns: nothing.
        '''
        super(GurpsRuleset, self)._record_action(fighter,
                                                 action,
                                                 fight_handler,
                                                 handled,
                                                 logit)

        if handled == Ruleset.HANDLED_OK:
            if logit and 'name' in action:
                fighter.details['actions_this_turn'].append(action['name'])
        elif handled == Ruleset.UNHANDLED:
            self._window_manager.error(
                            ['action "%s" is not handled by any ruleset' %
                                                            action['name']])

        # Don't deal with HANDLED_ERROR


    def __reset_aim(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'defend' | 'don-armor' |
                                      #          'reset-aim' |
                                      #          'set-consciousness',
                                      #  'comment': <string>, # optional
                    fight_handler     # FightHandler object
                   ):
        '''
        Action handler for GurpsRuleset.

        Resets any ongoing aim that the Fighter may have had.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = None
        if action['name'] == 'defend':
            timer = Timer(None)
            timer.from_pieces( {'parent-name': fighter.name,
                                'rounds': 1 - Timer.announcement_margin,
                                'string': ['All out defense',
                                           ' Defense: double',
                                           ' Move: step']} )

        elif action['name'] == 'don-armor':
            timer = Timer(None)
            armor, throw_away = fighter.get_current_armor()
            title = ('Doff armor' if armor is None else
                                                ('Don %s' % armor['name']))

            timer.from_pieces( {'parent-name': fighter.name,
                                'rounds': 1 - Timer.announcement_margin,
                                'string': [title,
                                           ' Defense: none',
                                           ' Move: none']} )
        return timer


    def __stun(self,
               param    # {'view': xxx, 'view-opponent': xxx,
                        #  'current': xxx, 'current-opponent': xxx,
                        #  'fight_handler': <fight handler> } where
                        # xxx are Fighter objects
              ):
        '''
        Command ribbon method.

        Figures out whom to stun and stuns them.

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

        fight_handler = (None if 'fight_handler' not in param
                                                else param['fight_handler'])
        self.do_action(stunned_dude,
                       {'name': 'stun',
                        'stun': True,
                        'comment': ('(%s) got stunned' % stunned_dude.name)},
                       fight_handler)

        return True # Keep going


    def __stun_action(self,
                      fighter,          # Fighter object
                      action,           # {'name': 'stun',
                                        #  'stun': False}
                                        #  'comment': <string>, # optional
                      fight_handler,    # FightHandler object
                     ):
        '''
        Action handler for GurpsRuleset.

        Marks the Fighter as stunned.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['stunned'] = action['stun']
        return None # No timer


class ScreenHandler(object):
    '''
    Base class for the "business logic" backing the user interface.
    '''

    SCREEN_MOVEMENT_CHARS = {
        curses.KEY_HOME: 'KEY_HOME',
        curses.KEY_UP: 'KEY_UP',
        curses.KEY_DOWN: 'KEY_DOWN',
        curses.KEY_NPAGE: 'KEY_NPAGE',
        curses.KEY_PPAGE: 'KEY_PPAGE',
        curses.KEY_LEFT: 'KEY_LEFT',
        curses.KEY_RIGHT: 'KEY_RIGHT',
    }

    maintain_game_file = False

    def __init__(self,
                 window_manager,    # GmWindowManager object for menus and
                                    #   error reporting
                 world,             # World object
                 ):
        self._window_manager = window_manager
        self.world = world

        self._saved_fight = self.world.details['current-fight']

        # Install default command ribbon command(s).
        self._choices = {
            ord('B'): {'name': 'Bug Report', 'func': self._make_bug_report},
        }


    @staticmethod
    def string_from_character_input(char    # character to convert
                                   ):
        '''
        Returns a printable string from a character.  This is intended to be
        used to display messages regarding screen input.
        '''
        if char < 256:
            return '%c' % chr(char)

        if char in ScreenHandler.SCREEN_MOVEMENT_CHARS:
            return '%s' % ScreenHandler.SCREEN_MOVEMENT_CHARS[char]

        return '%d' % char


    def add_to_history(self,
                       action # {'name':xxx, ...} - see Ruleset::do_action()
                      ):
        '''
        Adds an action (see Ruleset::do_action) to the saved information for
        this session.
        '''
        self.world.add_to_history(action)


    def clear_history(self):
        '''
        Deletes all of the saved information for this session.
        '''
        self.world.clear_history()


    def handle_user_input_until_done(self):
        '''
        Draws the screen and does event loop (gets single-character input,
        looks up input in self._choices (i.e., the command ribbon commands),
        and calls the associated function (if any).

        Returns: True (to be part of a system to detect crashes).
        '''
        self._draw_screen()

        keep_going = True
        while keep_going:
            string = self._window_manager.get_one_character()
            if string in self._choices:
                keep_going = self._choices[string]['func']()
            else:
                self._window_manager.error(
                    ['Invalid command: "%s" ' %
                        ScreenHandler.string_from_character_input(string) ])

        return True

    #
    # Protected Methods
    #

    def _add_to_choice_dict(self,
                            new_choices # dict: {
                                        # key_char: {'name': long description,
                                        #            'func': function to
                                        #                    execute if this
                                        #                    is selected
                           ):
        '''
        Adds options to the command ribbon.

        key_char is the character someone would need to hit to invoke the
        choice.  The key_char can be of the following forms:
            ord('d')
            curses.KEY_UP

        The 'name' is shown (next to the key_char) on the screen.

        The 'func' is executed if the selection is chosen.

        Returns: nothing
        '''

        # Check for errors...
        for key in self._choices.iterkeys():
            if key in new_choices:
                self._window_manager.error(
                        ['Collision of _choices on key "%c"' % chr(key)])
                return False # Found a problem

        self._choices.update(new_choices)


    def _draw_screen(self):
        '''
        Every screen should have a '_draw_screen' method to display the whole
        screen.  This is here as a placeholder.
        '''
        pass


    def _make_bug_report(self):
        '''
        Command ribbon method.

        Gathers all the information required (I hope) to reproduce a bug and
        writes it to a file.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        lines, cols = self._window_manager.getmaxyx()
        report = self._window_manager.edit_window(
                    lines - 4,
                    cols - 4,
                    '',  # initial string (w/ \n) for the window
                    'Bug Report',
                    '^G to exit')

        # Gotta do the debug snapshot first, so it's in snapshot list

        self.world.do_debug_snapshot('bug')

        bug_report_game_file  = self.world.program.make_bug_report(
                                                self._saved_fight['history'],
                                                report)

        self._window_manager.display_window(
               'Bug Reported',
                [[{'text': ('Output file "%s"' % bug_report_game_file),
                   'mode': curses.A_NORMAL }]])

        return True # Keep doing whatever you were doing.


class PersonnelHandler(ScreenHandler):
    '''
    Adds creatures to the PC, NPC, or a monster list (possibly creating a new
    monster list).  These creatures are created from one of the templates
    provided in the World's Game File file.
    '''
    (NPCs,
     PCs,
     MONSTERs) = range(3)

    (CHAR_LIST,
     CHAR_DETAIL) = (1, 2)  # These are intended to be bits so they can be ored

    def __init__(self,
                 window_manager,    # GmWindowManager object for menus and
                                    #   error reporting
                 world,             # World object
                 creature_type,     # one of: NPCs, PCs, or MONSTERs
                ):
        super(PersonnelHandler, self).__init__(window_manager, world)
        self._add_to_choice_dict({
            curses.KEY_HOME:
                  {'name': 'scroll home',            'func': self.__first_page},
            curses.KEY_UP:
                  {'name': 'prev creature',          'func': self.__view_prev},
            curses.KEY_DOWN:
                  {'name': 'next creature',          'func': self.__view_next},
            curses.KEY_NPAGE:
                  {'name': 'scroll down',            'func': self.__next_page},
            curses.KEY_PPAGE:
                  {'name': 'scroll up',              'func': self.__prev_page},
            curses.KEY_LEFT:
                  {'name': 'scroll char list',       'func': self.__left_pane},
            curses.KEY_RIGHT:
                  {'name': 'scroll char detail',     'func': self.__right_pane},

            ord('a'): {'name': 'add creature',       'func': self.__add_creature},
            ord('d'): {'name': 'delete creature',    'func': self.__delete_creature},
            ord('e'): {'name': 'equip/modify creature',
                                                     'func': self.__equip},
            ord('g'): {'name': 'create template group',
                                                     'func': self.__create_template_group},
            ord('t'): {'name': 'change template group',
                                                     'func': self.__change_template_group},
            ord('T'): {'name': 'make into template', 'func': self.__create_template},
            ord('q'): {'name': 'quit',               'func': self.__quit},
        })

        if creature_type == PersonnelHandler.NPCs:
            self._add_to_choice_dict({
                ord('p'): {'name': 'NPC joins PCs',      'func': self.NPC_joins_PCs},
                ord('P'): {'name': 'NPC leaves PCs',     'func': self.__NPC_leaves_PCs},
                ord('m'): {'name': 'NPC joins Monsters', 'func': self.NPC_joins_monsters},
            })

        self._window = self._window_manager.get_build_fight_gm_window(
                                                                self._choices)
        self.__current_pane = PersonnelHandler.CHAR_DETAIL

        self.__template_group = None # Name of templates we'll use to create
                                    # new creatures.

        self.__critters = None  # dict of the Fighters/Venues in a group
                                # (PCs, NPCs, or monster group) sorted by the
                                # the Fighters' names (with the venue, if it
                                # exists, stuffed at the top).  The dict is:
                                # {
                                #   'data': array of dict found in the data file
                                #   'obj':  array of Fighter/Venue object
                                # }
                                #
                                # NOTE: [data][n] is the same creature as [obj][n]

        self.__deleted_critter_count = 0
        self.__equipment_manager = EquipmentManager(self.world, window_manager)

        self.__new_char_name = None
        self.__viewing_index = None

        if creature_type == PersonnelHandler.NPCs:
            self.__group_name = 'NPCs'
            self.__existing_group(creature_type)
        elif creature_type == PersonnelHandler.PCs:
            self.__group_name = 'PCs'
            self.__existing_group(creature_type)
        else: # creature_type == PersonnelHandler.MONSTERs:
            self.__group_name = None    # The name of the monsters or 'PCs'
                                        # that will ultimately take these
                                        # creatures.

            new_existing_menu = [('new monster group', 'new')]
            if len(self.world.get_fights()) > 0:
                new_existing_menu.append(('existing monster group', 'existing'))

            new_existing = None
            while new_existing is None:
                new_existing = self._window_manager.menu('New or Pre-Existing',
                                                          new_existing_menu)
            if new_existing == 'new':
                self.__new_group()
            else:
                self.__existing_group(creature_type)

        self.__viewing_index = 0 if self.__critters_contains_critters() else None
        self._draw_screen()

        if not self.__critters_contains_critters():
            self.__add_creature()

        return

    #
    # Public Methods
    #


    def get_group_name(self):
        '''
        Returns the name of the group ('PCs', 'NPCs', or the monster group)
        that is currently being modified.
        '''
        return self.__group_name


    def get_obj_from_index(self):               # Public to support testing
        '''
        Returns the Fighter/Venue object from the current viewing index into
        the __critters list.
        '''
        if self.__viewing_index is None:
            return None

        fighter = self.__critters['obj'][self.__viewing_index]

        return fighter


    def NPC_joins_monsters(self):               # Public to support testing
        '''
        Command ribbon method.

        Adds an existing NPC to a monster list (that NPC also stays in the NPC
        list).  This is useful if an NPC wishes to fight alongside a group of
        monsters against the party.

        Operates on the currently selected NPC.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Make sure the person is an NPC

        npc = self.get_obj_from_index()
        if npc is None:
            return True

        if npc.group != 'NPCs':
            self._window_manager.error(['"%s" not an NPC' % npc.name])
            return True

        # Select the fight
        fight_menu = [(fight_name, fight_name)
                                for fight_name in self.world.get_fights()]
        fight_name = self._window_manager.menu('Join Which Fight', fight_menu)

        # Make sure the person isn't already in the fight
        fight = self.world.get_creature_details_list(fight_name)
        if npc.name in fight:
            self._window_manager.error(['"%s" already in fight "%s"' %
                                                    (npc.name, fight_name)])
            return True

        fight[npc.name] = {'redirect': 'NPCs'}
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        return True


    def NPC_joins_PCs(self):                    # Public to support testing
        '''
        Command ribbon method.

        Adds an existing NPC to the PC list (that NPC also stays in the NPC
        list).  This is useful if an NPC wishes to fight alongside the party.

        Operates on the currently selected NPC.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        npc = self.get_obj_from_index()
        if npc is None:
            return True

        if npc.group != 'NPCs':
            self._window_manager.error(['"%s" not an NPC' % npc.name])
            return True

        if npc.name in self.world.details['PCs']:
            self._window_manager.error(['"%s" already a PC' % npc.name])
            return True

        self.world.details['PCs'][npc.name] = {'redirect': 'NPCs'}

        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        return True


    def set_viewing_index(self,              # Public to support testing.
                          new_index  # int: new viewing index
                         ):
        ''' Sets the viewing index.  Used for testing. '''
        self.__viewing_index = new_index


    #
    # Private and Protected Methods
    #

    #
    # Page navigation methods
    #

    def __first_page(self,
                     pane = None, # CHAR_LIST, CHAR_DETAIL,
                                  # CHAR_LIST|CHAR_DETAIL
                    ):
        '''
        Command ribbon method.

        Scrolls to the top of the current pain

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if pane is None:
            pane = self.__current_pane

        if (pane & PersonnelHandler.CHAR_DETAIL) != 0:
            self._window.char_detail_home()

        if (pane & PersonnelHandler.CHAR_LIST) != 0:
            self.__char_index = 0
            self._window.char_list_home()
            self._draw_screen()
        return True

    def __left_pane(self):
        '''
        Command ribbon method.

        Changes the currently active pane to the left-hand one.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__current_pane = PersonnelHandler.CHAR_LIST
        return True

    def __next_page(self):
        '''
        Command ribbon method.

        Scrolls down on the current pane.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__current_pane == PersonnelHandler.CHAR_DETAIL:
            self._window.scroll_char_detail_down()
        else:
            self._window.scroll_char_list_down()
        return True


    def __prev_page(self):
        '''
        Command ribbon method.

        Scroll up in the current pane.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__current_pane == PersonnelHandler.CHAR_DETAIL:
            self._window.scroll_char_detail_up()
        else:
            self._window.scroll_char_list_up()
        return True

    def __right_pane(self):
        '''
        Command ribbon method.

        Makes the right-hand pane the active pane for scrolling.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__current_pane = PersonnelHandler.CHAR_DETAIL
        return True

    #
    # Other methods
    #
    # TODO: seems a bit long -- break this up into smaller methods
    def __add_creature(self):
        '''
        Command ribbon method.

        Creates new creatures from user specifications.

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

            # Get a template.

            if self.__template_group is None:
                self.__change_template_group()

            # Based on which creature from the template

            empty_creature = 'Blank Template'
            from_creature_name = empty_creature

            # None means there are no templates or the user decided against a template.

            if self.__template_group is not None:
                creature_menu = []
                for from_creature_name in (
                            self.world.details['templates'][self.__template_group]):
                    if from_creature_name == empty_creature:
                        self._window_manager.error(
                            ['Template group "%s" contains illegal template:' %
                                                            self.__template_group,
                             '"%s". Replacing with an empty creature.' %
                                                            empty_creature])
                    else:
                        creature_menu.append((from_creature_name,
                                              from_creature_name))

                creature_menu = sorted(creature_menu, key=lambda x: x[0].upper())
                creature_menu.append((empty_creature, empty_creature))

                from_creature_name = self._window_manager.menu('Monster',
                                                               creature_menu)
                if from_creature_name is None:
                    keep_adding_creatures = False
                    break

            # Generate the creature for the template

            to_creature = self.world.ruleset.make_empty_creature()

            if from_creature_name != empty_creature:
                from_creature = (self.world.details[
                        'templates'][self.__template_group][from_creature_name])
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

            lines, cols = self._window.getmaxyx()

            # We're not filling in the holes if we delete a monster, we're
            #   just adding to the total of monsters created
            # NOTE: this is still imperfect.  If you delete a monster and then
            #   come back later, you'll still have numbering problems.
            # ALSO NOTE: we use 'len' rather than 'len'+1 because we've added
            #   a Venue to the list -- the Venue has an implied prefix of '0'
            previous_creature_count = (0 if self.__critters is None else
                                                            len(self.__critters['data']))
            creature_num = previous_creature_count + self.__deleted_critter_count
            keep_asking = True
            while keep_asking:
                base_name = self._window_manager.input_box(1,      # height
                                                           cols-4, # width
                                                           'Monster Name')
                if base_name is None or len(base_name) == 0:
                    base_name, where, gender = self.world.get_random_name()
                    if base_name is None:
                        self._window_manager.error(['Monster needs a name'])
                        keep_asking = True
                        continue
                    else:
                        if where is not None:
                            to_creature['notes'].append('origin: %s' % where)
                        if gender is not None:
                            to_creature['notes'].append('gender: %s' % gender)

                if self.__group_name == 'NPCs' or self.__group_name == 'PCs':
                    creature_name = base_name
                else:
                    creature_name = '%d - %s' % (creature_num, base_name)

                if self.__critters is None:
                    keep_asking = False
                elif creature_name in self.__critters['data']:
                    self._window_manager.error(
                        ['Monster "%s" already exists' % creature_name])
                    keep_asking = True
                else:
                    keep_asking = False

            # Add personality stuff to notes

            if self.__group_name != 'PCs':
                with GmJson('gm-npc-random-detail.json') as npc_detail:
                    for name, traits in (
                                npc_detail.read_data['traits'].iteritems()):
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
                if self.__critters is None:
                    temp_list = []
                else:
                    temp_list = [x for x in self.__critters['obj']]
                temp_list.append(Fighter(creature_name,
                                         self.__group_name,
                                         to_creature,
                                         self.world.ruleset,
                                         self._window_manager))
                self.__new_char_name = creature_name
                # PersonnelGmWindow
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
                    if self.__critters is None:
                        creature_name = temp_creature_name
                    elif temp_creature_name in self.__critters['data']:
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
            self.__critters['obj'].append(self.world.get_creature(
                                                        creature_name,
                                                        self.__group_name))
            self.__viewing_index = len(self.__critters['obj']) -1
            # PersonnelGmWindow
            self._window.show_creatures(self.__critters['obj'],
                                        self.__new_char_name,
                                        self.__viewing_index)

        return True # Keep going


    def __add_equipment(self,
                        throw_away   # Required/used by the caller because
                                     #   there's a list of methods to call,
                                     #   and (apparently) some of them may
                                     #   use this parameter.  It's ignored
                                     #   by this method, however.
                       ):
        '''
        Handler for an Equip sub-menu entry.

        Allows the user to add equipment to a Fighter or Venue.

        Returns: True -- anything but 'None' in a menu handler
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return True

        keep_asking = True
        keep_asking_menu = [('yes', True), ('no', False)]
        while keep_asking:
            self.__equipment_manager.add_equipment(fighter)
            self._draw_screen()
            keep_asking = self._window_manager.menu('Add More Equipment',
                                                    keep_asking_menu)
        return True


    def __add_spell(self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                   ):
        '''
        Handler for an Equip sub-menu entry.

        Adds a user-designated magic spell to a Fighter.

        Returns: None if we want to bail out of the process of adding a spell,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        # Is the fighter a caster?
        if 'spells' not in fighter.details:
            self._window_manager.error(
                ['Doesn\'t look like %s casts spells' % fighter.name])
            return None

        # Pick from the spell list
        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        spell_menu = [(spell_name, spell_name)
                            for spell_name in
                                sorted(self.world.ruleset.spells.iterkeys())]
        while keep_asking:
            new_spell_name = self._window_manager.menu('Spell to Add',
                                                       spell_menu)
            if new_spell_name is None:
                return None

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
        return True


    def __add_timer(self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                   ):
        '''
        Handler for an Equip sub-menu entry.

        Adds a user-described timer to a Fighter or Venue.

        Returns: True -- anything but None in a menu handler
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return True

        lines, cols = self._window.getmaxyx()
        timers_widget = TimersWidget(fighter.timers, self._window_manager)

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            timers_widget.make_timer(fighter.name)
            self._draw_screen()
            keep_asking = self._window_manager.menu('Add More Timers',
                                                    keep_asking_menu)
        return True


    def __change_attributes(self,
                            throw_away   # Required/used by the caller because
                                         #   there's a list of methods to call,
                                         #   and (apparently) some of them may
                                         #   use this parameter.  It's ignored
                                         #   by this method, however.
                           ):
        '''
        Handler for an Equip sub-menu entry.

        Allows the user to modify one or more attribute values of the Fighter.
        The specific attributes come from the Ruleset.

        Returns: None if we want to bail-out of the change attributes process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            perm_current_menu = [('current', 'current'),
                                 ('permanent', 'permanent')]
            attr_type = self._window_manager.menu('What Type Of Attribute',
                                                           perm_current_menu)
            if attr_type is None:
                return None

            attr_menu = [(attr, attr)
                                for attr in fighter.details[attr_type].keys()]

            attr = self._window_manager.menu('Attr To Modify', attr_menu)
            if attr is None:
                return None

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
        return True


    def __change_template_group(self):
        '''
        Command ribbon method.

        Selects a new (existing) template to use to make new creatures.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Get the new group info.

        if len(self.world.details['templates']) <= 0:
            return True

        # Get the template
        lines, cols = self._window.getmaxyx()
        template_menu = [(template_group, template_group)
                    for template_group in self.world.details['templates']]
        template_group = self._window_manager.menu('Which Template Group',
                                                   template_menu)
        if template_group is None:
            return True  # Keep going
        self.__template_group = template_group

        # Display our new state

        self._draw_screen()

        return True # Keep going


    def __change_viewing_index(self,
                               adj  # integer adjustment to viewing index
                              ):
        '''
        Changes the viewing index to point to a different creature.

        NOTE: this breaks if |adj| is > len(self.__critters['data'])

        Returns: nothing.
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


    def __create_template(self):
        '''
        Command ribbon method.

        Creates a template from a creature.  Puts it in the same section.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # A little error checking

        if self.__template_group is None:
            self._window_manager.error(
                ['You must select a template group to which to',
                 'add this template.'])
            return True # Keep going

        if self.__viewing_index is None:
            return True # Keep going

        from_creature  = self.get_obj_from_index()
        if from_creature.name == Venue.name:
            self._window_manager.error(['Can\'t make a template from a room'])
            return True # Keep going

        # Get the name of the new template

        lines, cols = self._window.getmaxyx()
        keep_asking = True
        while keep_asking:
            template_name = self._window_manager.input_box(1,      # height
                                                           cols-4, # width
                                                           'New Template Name')
            if template_name is None or len(template_name) == 0:
                return True
            elif (template_name in
                    self.world.details['templates'][self.__template_group]):
                self._window_manager.error(
                    ['Template name "%s" already exists' % template_name])
                keep_asking = True
            else:
                keep_asking = False

        # Copy current creature into the template

        to_creature = {}
        allowable_section_names = self.world.ruleset.get_sections_in_template()

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

        template_list = self.world.details['templates'][self.__template_group]
        template_list[template_name] = to_creature
        return True # Keep going


    def __create_template_group(self):
        '''
        Command ribbon method.

        Creates a new template group and changes to that group.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        lines, cols = self._window.getmaxyx()
        keep_asking = True
        while keep_asking:
            template_group = self._window_manager.input_box(1,      # height
                                                           cols-4, # width
                                                           'New Template Group Name')
            if template_group is None or len(template_group) <= 0:
                return True
            elif template_group in self.world.details['templates']:
                self._window_manager.error(
                    ['Template group name "%s" already exists' % template_group])
                keep_asking = True
            else:
                keep_asking = False

        if len(template_group) > 0:
            self.world.details['templates'][template_group] = {}
            self.__template_group = template_group
            self._draw_screen()

        return True


    def __critters_contains_critters(self):
        '''
        Returns True if any creature in the self.__critters array is a monster, NPC, or PC.
            Returns False, otherwise.
        '''
        if self.__critters is None:
            return False
        for critter in self.__critters['obj']:
            if critter.name != Venue.name:
                return True
        return False


    def __delete_creature(self):
        '''
        Command ribbon method.

        Removes a creature from the creature list.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__viewing_index is None:
            # Auto-select the most recently added new creature
            name_to_delete = self.__new_char_name

        else:
            creature = self.get_obj_from_index()
            name_to_delete = None if creature is None else creature.name

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
        # PersonnelGmWindow
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)

        return True # Keep going


    def __don_armor(self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                   ):
        '''
        Method for 'equip' sub-menu.

        Asks the user which armor the Fighter should wear and puts it on.

        Returns: None if we want to bail-out of the don armor process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

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
                    return None

        self.world.ruleset.do_action(fighter,
                                 {'name': 'don-armor',
                                  'armor-index': armor_index
                                 },
                                 None)
        self._draw_screen()
        return True # anything but 'None' for a menu handler


    def _draw_screen(self):
        '''
        Draws the complete screen for the FightHandler.

        Returns: nothing.
        '''
        self._window.clear()
        self._window.status_ribbon(self.__group_name,
                                   self.__template_group,
                                   self.world.source_filename,
                                   ScreenHandler.maintain_game_file)
        self._window.command_ribbon()
        # PersonnelGmWindow
        fighters = None if self.__critters is None else self.__critters['obj']
        self._window.show_creatures(fighters,
                                    self.__new_char_name,
                                    self.__viewing_index)
        if (self.__new_char_name is not None and
                            self.__new_char_name in self.__critters['data']):
            critter = self.__get_fighter_object_from_name(self.__new_char_name)
            self._window.show_description(critter)


    def __draw_weapon(self,
                      throw_away   # Required/used by the caller because
                                   #   there's a list of methods to call,
                                   #   and (apparently) some of them may
                                   #   use this parameter.  It's ignored
                                   #   by this method, however.
                     ):
        '''
        Method for 'equip' sub-menu.

        Asks the user which weapon (or shield) the Fighter should draw and
        draws it.

        Returns: None if we want to bail-out of the draw weapon process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

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
                    return None

        self.world.ruleset.do_action(fighter,
                                 {'name': 'draw-weapon',
                                  'weapon-index': weapon_index
                                 },
                                 None)
        self._draw_screen()
        return True # Anything but 'None' for a menu handler


    def __equip(self):
        '''
        Command ribbon method.

        Provides a sub-menu for different ways to augment a Fighter

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return True

        sub_menu = []
        if 'stuff' in fighter.details:
            sub_menu.extend([
                ('attributes (change)', {'doit': self.__change_attributes}),
                ('equipment (add)',     {'doit': self.__add_equipment}),
                ('Equipment (remove)',  {'doit': self.__remove_equipment}),
                ('give equipment',      {'doit': self.__give_equipment}),
            ])

        self.__ruleset_abilities = self.world.ruleset.get_creature_abilities()
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
        self.world.ruleset.is_creature_consistent(fighter.name, fighter.details)

        return True # Keep going


    def __existing_group(self,
                         creature_type # PersonnelHandler.NPCs, ...
                        ):

        '''
        Command ribbon method.

        Selects an existing group as the current group to modify.  Builds out
        all of the necessary pieces to make that happen.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Get the template name

        self.__change_template_group()

        # Get the group information

        if creature_type == PersonnelHandler.MONSTERs:
            group_menu = [(group_name, group_name)
                            for group_name in self.world.get_fights()]
            group_menu = sorted(group_menu, key=lambda x: x[0].upper())
            group_answer = self._window_manager.menu('To Which Group', group_menu)

        elif creature_type == PersonnelHandler.NPCs:
            group_answer = 'NPCs'

        elif creature_type == PersonnelHandler.PCs:
            group_answer = 'PCs'

        if group_answer is None:
            return True # Keep going

        # Set the name and group of the new group

        self.__group_name = group_answer
        self.__critters = {
                'data': self.world.get_creature_details_list(self.__group_name),
                'obj': []}

        # Build the Fighter object array

        the_fight_itself = None
        for name, details in self.__critters['data'].iteritems():
            if name == Venue.name:
                the_fight_itself = details
            else:
                fighter = self.world.get_creature(name, self.__group_name)
                self.__critters['obj'].append(fighter)

        self.__critters['obj'] = sorted(self.__critters['obj'],
                                        key=lambda x: x.name)

        # Add the Venue to the object array (but only for monsters).

        if creature_type == PersonnelHandler.MONSTERs:
            if the_fight_itself is None:
                self.__critters['data'][Venue.name] = Venue.empty_venue
                group = self.world.details['fights'][self.__group_name]
                fight = Venue(self.__group_name,
                              group['monsters'][Venue.name],
                              self.world.ruleset,
                              self._window_manager)
            else:
                fight = Venue(self.__group_name,
                              the_fight_itself,
                              self.world.ruleset,
                              self._window_manager)

            self.__critters['obj'].insert(0, fight)

        # Display our new state

        self._draw_screen()

        return True # Keep going


    def __full_notes(self,
                     throw_away   # Required/used by the caller because
                                  #   there's a list of methods to call,
                                  #   and (apparently) some of them may
                                  #   use this parameter.  It's ignored
                                  #   by this method, however.
                    ):
        '''
        Handler for an Equip sub-menu entry.

        Allows the user to modify the current fighter's full notes.

        Returns: None
        '''
        return self.__notes('notes')


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
        '''
        Expands a template item based on the template item's type.

        Returns the expanded value.
        '''
        if template_value['type'] == 'value':
            return template_value['value']

        # TODO(eventually, maybe):
        #   {'type': 'ask-string', 'value': x}
        #   {'type': 'ask-numeric', 'value': x}
        #   {'type': 'ask-logical', 'value': x}
        #   {'type': 'dice', 'value': 'ndm+x'}
        #   {'type': 'derived', 'value': comlicated bunch of crap -- eventually}

        return None


    def __give_equipment(self,
                         throw_away   # Required/used by the caller because
                                      #   there's a list of methods to call,
                                      #   and (apparently) some of them may
                                      #   use this parameter.  It's ignored
                                      #   by this method, however.
                        ):
        '''
        Handler for an Equip sub-menu entry.

        Provides a way for one Fighter (or Venue) to transfer an item of
        equipment to a different Fighter (or Venue).

        Returns: None if we want to bail-out of the give equipment process,
                 True, otherwise
        '''
        from_fighter = self.get_obj_from_index()
        if from_fighter is None:
            return None

        item = self.__equipment_manager.remove_equipment(from_fighter)
        if item is None:
            return None

        character_list = self.world.get_creature_details_list('PCs')
        character_menu = [(dude, dude) for dude in character_list]
        to_fighter_info = self._window_manager.menu(
                                        'Give "%s" to whom?' % item['name'],
                                        character_menu)

        if to_fighter_info is None:
            from_fighter.add_equipment(item, None)
            self._draw_screen()
            return None

        to_fighter = self.world.get_creature(to_fighter_info, 'PCs')
        to_fighter.add_equipment(item, from_fighter.detailed_name)
        self._draw_screen()
        return True # anything but 'None' for a successful menu handler


    def __new_group(self):
        '''
        Command ribbon method.

        Creates new group of monsters.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Get the template info.

        self.__change_template_group()

        # Get the new group info.

        keep_asking = True
        group_name = None
        lines, cols = self._window.getmaxyx()
        while keep_asking:
            group_name = self._window_manager.input_box(1,      # height
                                                        cols-4, # width
                                                        'New Fight Name')
            if group_name is None or len(group_name) == 0:
                self._window_manager.error(['You have to name your fight'])
                keep_asking = True
            elif self.world.get_creature_details_list(group_name) is not None:
                self._window_manager.error(
                    ['Fight name "%s" already exists' % group_name])
                keep_asking = True
            else:
                keep_asking = False

        # Set the name and group of the new group

        self.__group_name = group_name
        fights = self.world.get_fights() # New groups can only be in fights.

        fights[group_name] = {'monsters': {}}

        self.__critters = {'data': fights[group_name]['monsters'],
                           'obj': []}

        self.__critters['data'][Venue.name] = Venue.empty_venue
        fight = Venue(group_name,
                      fights[group_name]['monsters'][Venue.name],
                      self.world.ruleset,
                      self._window_manager)
        self.__critters['obj'].insert(0, fight)

        # Display our new state

        self._draw_screen()

        return True # Keep going


    def __NPC_leaves_PCs(self):
        '''
        Command ribbon method.

        Removes an NPC that's currently in the party list.  He stays being an
        NPC.  Operates on current creature in the creature list.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        npc = self.get_obj_from_index()
        if npc is None:
            return True

        if npc.name not in self.world.details['NPCs']:
            self._window_manager.error(['"%s" not an NPC' % npc.name])
            return True

        if npc.name not in self.world.details['PCs']:
            self._window_manager.error(['"%s" not in PC list' % npc.name])
            return True

        del(self.world.details['PCs'][npc.name])
        self._draw_screen()
        return True


    def __quit(self):
        '''
        Command ribbon method.

        Quits out of the PersonnelHandler.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__critters is not None:
            for name, creature in self.__critters['data'].iteritems():
                self.world.ruleset.is_creature_consistent(name, creature)

        # TODO: do I need to del self._window?
        self._window.close()
        return False # Stop building this fight


    def __remove_equipment(self,
                           throw_away   # Required/used by the caller because
                                        #   there's a list of methods to call,
                                        #   and (apparently) some of them may
                                        #   use this parameter.  It's ignored
                                        #   by this method, however.
                          ):
        '''
        Handler for an Equip sub-menu entry.

        Asks the user which piece of equipment the current Fighter has that
        should be removed from his list.  Then removes that piece of
        equipment.

        Returns: None if we want to bail-out of the remove equipment process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        self.__equipment_manager.remove_equipment(fighter)
        self._draw_screen()
        return True # Menu handler's success returns anything but 'None'


    def __remove_spell(self,
                       throw_away   # Required/used by the caller because
                                    #   there's a list of methods to call,
                                    #   and (apparently) some of them may use
                                    #   this parameter.  It's ignored by this
                                    #   method, however.
                      ):
        '''
        Handler for an Equip sub-menu entry.

        Asks the user which spell the current Fighter currently knows that he
        shouldn't, then removes that spell from the Fighter's spell list.

        Returns: None if we want to bail-out of the remove spell process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        # Is the fighter a caster?
        if 'spells' not in fighter.details:
            self._window_manager.error(
                ['Doesn\'t look like %s casts spells' % fighter.name])
            return None

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
                return None

            for index, spell in enumerate(fighter.details['spells']):
                if spell['name'] == bad_spell_name:
                    del fighter.details['spells'][index]
                    self._draw_screen()
                    break

            keep_asking = self._window_manager.menu('Remove More Spells',
                                                    keep_asking_menu)
        return True # Menu handler's success returns anything but 'None'


    def __ruleset_ability(self,
                          param  # string: Ruleset-defined ability category
                                 #   name (like 'skills' or 'advantages')
                         ):
        '''
        Handler for an Equip sub-menu entry.

        Adds an ability (a Ruleset-defined category of things, like
        'skills' or 'advantages') to a creature.

        Returns: None if we want to bail-out of the add ability process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        if param not in fighter.details:
            self._window_manager.error(['%s doesn\'t support' % (fighter.name,
                                                                 param)])
            return None

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
                return None

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
                    return None

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

        return True # Menu handler's success returns anything but 'None'


    def __ruleset_ability_rm(self,
                             param  # string: Ruleset-defined ability category
                                    #   name (like 'skills' or 'advantages')
                            ):
        '''
        Handler for an Equip sub-menu entry.

        Removes an ability (a Ruleset-defined category of things, like
        'skills' or 'advantages') from a creature.

        Returns: None if we want to bail-out of the remove ability process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

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
                return None

            del fighter.details[param][bad_ability_name]
            self._draw_screen()

            keep_asking = self._window_manager.menu(
                                        'Remove More %s' % param.capitalize(),
                                        keep_asking_menu)
        return True # Menu handler's success returns anything but 'None'


    def __short_notes(self,
                      throw_away    # Required/used by the caller because
                                    #   there's a list of methods to call,
                                    #   and (apparently) some of them may use
                                    #   this parameter.  It's ignored by this
                                    #   method, however.
                     ):
        '''
        Handler for an Equip sub-menu entry.

        Lets the user edit a fighter's (or Venue's) short notes.

        Returns: None
        '''
        return self.__notes('short-notes')


    def __timer_cancel(self,
                       throw_away   # Required/used by the caller because
                                    #   there's a list of methods to call,
                                    #   and (apparently) some of them may use
                                    #   this parameter.  It's ignored by this
                                    #   method, however.
                      ):
        '''
        Handler for an Equip sub-menu entry.

        Asks user for timer to remove from a fighter and removes it.

        Returns: None if we want to bail-out of the cancel timer process,
                 True, otherwise
        '''
        timer_recipient = self.get_obj_from_index()
        if timer_recipient is None:
            return None

        # Select a timer

        timers = timer_recipient.timers.get_all()
        timer_menu = [(timer.get_one_line_description(), index)
                                for index, timer in enumerate(timers)]
        index = self._window_manager.menu('Remove Which Timer', timer_menu)
        if index is None:
            return None

        # Delete the timer

        timer_recipient.timers.remove_timer_by_index(index)

        self._draw_screen()

        return True # Menu handler's success returns anything but 'None'


    def __view_next(self): # look at next character
        '''
        Command ribbon method.

        Changes the current creature to the next one, wrapping if
        necessary.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__change_viewing_index(1)
        # PersonnelGmWindow
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        return True # Keep going


    def __view_prev(self): # look at previous character
        '''
        Command ribbon method.

        Changes the current creature to the previous one, wrapping if
        necessary.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__change_viewing_index(-1)
        # PersonnelGmWindow
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        return True # Keep going


class FightHandler(ScreenHandler):
    '''
    Manages a fight between the PCs and a monster group.

    The Fighters are all shown, intermingled, in initiative order (i.e., the
    order that they may take action, in a fight).

    Operations are communicated with text-based |actions|.  Each action is
    saved to the fight's history so that they can be displayed or can be
    replayed on top of a snapshot of the World taken when the fight starts.

    Has the concept of the "current" Fighter or Venue.  That's normally, the
    Fighter that has initiative but the user can can selete another with up
    and down buttons.
    '''
    def __init__(self,
                 window_manager,        # GmWindowManager object for menus and
                                        #   errors
                 world,                 # World object
                 monster_group,         # string
                 playback_history,      # dict from bug report (usually None)
                 save_snapshot = True   # Here so tests can disable it
                ):
        super(FightHandler, self).__init__(window_manager, world)
        self.__bodies_looted = False
        self.__keep_monsters = False # Move monsters to 'dead' after fight
        self.__equipment_manager = EquipmentManager(self.world,
                                                    self._window_manager)
        self.__saved_history = None

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
            ord('g'): {'name': 'give equipment',
                                              'func': self.__give_equipment},
            ord('h'): {'name': 'History',     'func': self.__show_history},
            ord('i'): {'name': 'character info',
                                              'func': self.__show_info},
            #ord('k'): {'name': 'keep monsters',
            #                                  'func': self.__do_keep_monsters},
            ord('-'): {'name': 'HP damage',   'func': self.__damage_HP},
            #ord('L'): {'name': 'Loot bodies', 'func': self.__loot_bodies},
            ord('m'): {'name': 'maneuver',    'func': self.__maneuver},
            ord('n'): {'name': 'short notes', 'func': self.__short_notes},
            ord('N'): {'name': 'full Notes',  'func': self.__full_notes},
            ord('o'): {'name': 'opponent',    'func': self.pick_opponent},
            ord('P'): {'name': 'promote to NPC',
                                              'func': self.promote_to_NPC},
            ord('q'): {'name': 'quit',        'func': self.__quit},
            #ord('s'): {'name': 'save',        'func': self.__save},
            ord('t'): {'name': 'timer',       'func': self.__timer},
            ord('T'): {'name': 'Timer cancel','func': self.__timer_cancel},
        })

        if playback_history is not None:
            self._add_to_choice_dict({
                                ord('H'): {'name': 'History playback',
                                           'func': self.__playback_history}
                                    })

        self._add_to_choice_dict(self.world.ruleset.get_fight_commands(self) )
        self._window = self._window_manager.get_fight_gm_window(self.world.ruleset,
                                                                self._choices)

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

        fight_order = None
        if self._saved_fight['saved']:
            if save_snapshot:   # True, except for tests
                self.world.do_debug_snapshot('fight')
            monster_group = self._saved_fight['monsters']

            fight_order = {}
            for index, fighter in enumerate(self._saved_fight['fighters']):
                if fighter['name'] not in fight_order:
                    fight_order[fighter['name']] = {fighter['group']: index}
                else:
                    fight_order[fighter['name']][fighter['group']] = index

            if playback_history is not None:
                # Make a copy of the history so I can play it back
                self.__saved_history = playback_history

                # Clean out the history so we can start over
                self.clear_history()

        else:
            self.clear_history()
            self.add_to_history({'comment': '--- Round 0 ---'})

            self._saved_fight['round'] = 0
            self._saved_fight['index'] = 0
            self._saved_fight['monsters'] = monster_group

        self.__build_fighter_list(monster_group, fight_order)

        # Copy the fighter information into the saved_fight.  Also, make
        # sure this looks like a _NEW_ fight.
        self._saved_fight['fighters'] = []
        for fighter in self.__fighters:
            fighter.start_fight()
            self._saved_fight['fighters'].append({'group': fighter.group,
                                                   'name': fighter.name})

        if monster_group is not None:
            for name in self.world.get_creature_details_list(monster_group):
                # TODO: maybe use get_creature so that the information is
                # cached in World.
                details = self.world.get_creature_details(name,
                                                          monster_group)
                if details is not None:
                    self.world.ruleset.is_creature_consistent(name, details)

        if not self.should_we_show_current_fighter():
            self.modify_index(1)

        first_fighter = self.get_current_fighter()
        first_fighter.start_turn(self)

        # Save a snapshot -- if the fight is saved or there's a crash, we'll
        # end up right back here.

        # Save the fight so that debugging a crash will come back to the
        # fight.  We'll unsave the fight right at the end and let the user
        # decide whether to save it for real on exit.
        self._saved_fight['saved'] = True

        if save_snapshot:
            # This will do the debug snapshot in a way that it'll come
            # right to the fight when started.
            self.world.do_debug_snapshot('fight')

        self._window.start_fight()


    #
    # Public Methods
    #

    def get_current_fighter(self):              # Public to support testing
        '''
        Returns the Fighter object of the current fighter.
        '''
        result = self.__fighters[ self._saved_fight['index'] ]
        return result


    def get_fighters(self):                     # Public to support testing
        '''
        Returns a list of information for all the Fighters in self.__fighters.
        '''
        return [{'name': fighter.name,
                 'group': fighter.group,
                 'details': fighter.details} for fighter in self.__fighters]


    def get_fighter_object(self,
                           name,  # <string> name of a fighter in that group
                           group  # <string> 'PCs' or group under
                                  #     world['fights']
                          ):
        '''
        Returns the Fighter object given the name and group of the fighter,
        '''
        for fighter in self.__fighters:
            if fighter.group == group and fighter.name == name:
                return fighter

        return None # Not found


    def get_opponent_for(self,
                         fighter # Fighter object
                        ):
        ''' Returns Fighter object for opponent of |fighter|. '''
        if (fighter is None or fighter.name == Venue.name or
                                        fighter.details['opponent'] is None):
            return None # No opponent

        opponent = self.get_fighter_object(
                                        fighter.details['opponent']['name'],
                                        fighter.details['opponent']['group'])
        return opponent


    def handle_user_input_until_done(self):
        '''
        Draws the screen and does event loop (gets input, responds to input)

        Returns: nothing
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
            self.world.remove_fight(fight_group)


    def keep_fight(self,
                   throw_away   # Required/used by the caller because
                                #   there's a list of methods to call,
                                #   and (apparently) some of them may
                                #   use this parameter.  It's ignored
                                #   by this method, however.
                  ):
        '''
        Don't remove the fight from the list of fights when we're done with it.
        This is useful if the fight contains creatures that we're going to
        need later or if the party disengages from the fight but might come
        back to it.
        '''
        self.__keep_monsters = True
        return True # Keep asking questions


    def modify_index(self,                      # Public to support testing
                     adj      # 1 or -1, adjust the index by this
                    ):
        '''
        Increment or decrement the index to the Fighter that has the
        initiative.  Only stop on living creatures.

        Returns: nothing
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
            if current_fighter.name == Venue.name:
                pass
            elif current_fighter.is_dead():
                if not self.world.playing_back:
                    self.add_to_history(
                            {'comment': ' (%s) did nothing (dead)' %
                                                        current_fighter.name})
            elif current_fighter.is_absent():
                if not self.world.playing_back:
                    self.add_to_history(
                            {'comment': ' (%s) did nothing (absent)' %
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
            if not self.world.playing_back:
                self.add_to_history({'comment': '--- Round %d ---' %
                                                self._saved_fight['round']})


    def pick_opponent(self):
        '''
        Command ribbon method.

        Allows the user to choose an opponent for the current Fighter.  If the
        opponent does not currently have an opponent of his/her own, it gives
        the user the option of making that opposition mutual (so that the two
        Fighters are opponents of each other).

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
        else:
            current_fighter = self.get_current_fighter()

        # Pick the opponent.  The default selection is for someone who doesn't
        # already have an opponent.

        opponent_group = None
        opponent_menu = []
        default_selection = None
        for fighter in self.__fighters:
            if (fighter.group != current_fighter.group and
                                                fighter.name != Venue.name):
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

        self.world.ruleset.do_action(current_fighter,
                                 {'name': 'pick-opponent',
                                  'opponent': {'name': opponent_name,
                                               'group': opponent_group},
                                  'comment': '(%s) picked (%s) as opponent' %
                                                    (current_fighter.name,
                                                     opponent_name)
                                 },
                                 self)

        opponent = self.get_fighter_object(opponent_name, opponent_group)

        # Ask to have them fight each other
        if (opponent is not None and opponent.details['opponent'] is None):
            back_menu = [('yes', True), ('no', False)]
            answer = self._window_manager.menu('Make Opponents Go Both Ways',
                                        back_menu)
            if answer == True:
                self.world.ruleset.do_action(
                    opponent,
                    {'name': 'pick-opponent',
                     'opponent': {'name': current_fighter.name,
                                  'group': current_fighter.group},
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
        '''
        Command ribbon method.

        Converts a monster to an NPC.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
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

        if new_NPC.name in self.world.details['NPCs']:
            self._window_manager.error(['There\'s already an NPC named %s' %
                                        new_NPC.name])
            return True

        details_copy = copy.deepcopy(new_NPC.details)
        self.world.details['NPCs'][new_NPC.name] = details_copy

        # Make the redirect entry

        group = self.world.get_creature_details_list(new_NPC.group)
        group[new_NPC.name] = { "redirect": "NPCs" }

        # Replace fighter information with new fighter information

        for index, fighter in enumerate(self.__fighters):
            if (fighter.name == new_NPC.name and
                                            fighter.group == new_NPC.group):
                new_fighter = self.world.get_creature(new_NPC.name,
                                                      new_NPC.group)
                self.__fighters[index] = new_fighter
                self._window_manager.display_window(
                                               ('Promoted Monster to NPC'),
                                                [[{'text': new_NPC.name,
                                                   'mode': curses.A_NORMAL }]])
                break

        return True # Keep going


    def save_fight(self,
                   throw_away   # Required/used by the caller because
                                #   there's a list of methods to call,
                                #   and (apparently) some of them may
                                #   use this parameter.  It's ignored
                                #   by this method, however.
                  ):
        '''
        Save the fight so that it is the run the next time we start fighting
        (i.e., if we need to interrupt this fight and continue it, later).
        '''
        self._saved_fight['saved'] = True
        return True # Keep asking questions


    def set_viewing_index(self, new_index):     # Public to support testing.
        '''
        Selects a different Fighter or Venue as the currently viewed one.
        Some commands will used the currently viewed entity as their default
        recipient.

        Returns: Nothing
        '''
        self.__viewing_index = new_index


    def should_we_show_current_fighter(self):
        '''
        Only called when the fight starts to see if the first creature (or the
        Venue) should be displayed.
        '''
        show_fighter = True
        current_fighter = self.get_current_fighter()
        if current_fighter.name == Venue.name:
            show_fighter = False

        elif current_fighter.is_dead():
            show_fighter = False

        elif current_fighter.is_absent():
            show_fighter = False

        if not show_fighter:
            self.__handle_fighter_background_actions(current_fighter)

        return show_fighter

    #
    # Private Methods
    #

    def __build_fighter_list(self,
                             monster_group, # String
                             fight_order    # {name: {group: index, ...}, ...
                            ):
        '''
        Creates the list of Fighters and the Venue.  This includes the PCs,
        the monster group, and the location of the fight.  They're created in
        initiative order (i.e., the order in which they act in a round of
        fighting, according to the ruleset).
        '''

        # Build the fighter list (even if the fight was saved since monsters
        # or characters could have been added since the save happened).

        self.__fighters = [] # This is a parallel array to
                             # self._saved_fight['fighters'] but the contents
                             # are ThingsInFight (i.e., Fighters or a Venue)

        # Start with the PCs
        for name in self.world.get_creature_details_list('PCs'):
            fighter = self.world.get_creature(name, 'PCs')
            if fighter is not None:
                self.__fighters.append(fighter)

        # Then add the monsters (and the Venue, if it exists)
        the_fight_itself = None
        if monster_group is not None:
            for name in self.world.get_creature_details_list(monster_group):
                details = self.world.get_creature_details(name,
                                                          monster_group)
                if details is None:
                    continue

                if name == Venue.name:
                    the_fight_itself = details
                else:
                    fighter = self.world.get_creature(name, monster_group)
                    self.__fighters.append(fighter)

        # Put the creatures in order
        if fight_order is None:
            # Sort by initiative = basic-speed followed by DEX followed by
            # random
            self.__fighters.sort(
                    key=lambda fighter:
                        self.world.ruleset.initiative(fighter), reverse=True)
        else:
            # Put them in the same order they were in, before (this is a saved
            # fight).
            self.__fighters.sort(
                    key=lambda fighter:
                        fight_order[fighter.name][fighter.group])

        # Put the fight info (if any) at the top of the list.
        if the_fight_itself is not None:
            fight = Venue(monster_group,
                          the_fight_itself,
                          self.world.ruleset,
                          self._window_manager)

            self.__fighters.insert(0, fight)


    def __change_viewing_index(self,
                               adj  # integer adjustment to viewing index
                              ):
        '''
        Selects a different Fighter or Venue as the currently viewed one.
        Some commands will used the currently viewed entity as their default
        recipient.

        Returns: Nothing
        '''
        self.__viewing_index += adj
        if self.__viewing_index >= len(self._saved_fight['fighters']):
            self.__viewing_index = 0
        elif self.__viewing_index < 0:
            self.__viewing_index = len(self._saved_fight['fighters']) - 1


    def __damage_HP(self):
        '''
        Command ribbon method.

        Removes life levels (or 'hit points' -- HP) from the selected fighter
        or the current fighter's opponent.

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
            elif 'move-and-attack' in attacker.details['actions_this_turn']:
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
                    self.world.ruleset.do_action(
                                        attacker,
                                        {'name': 'attack', 'comment': comment},
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

        self.world.ruleset.do_action(hp_recipient, action, self)

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __dead(self):
        '''
        Command ribbon method.

        Allows the user to change the consciousness level of a creature.  This
        may cause it to become dead, reanimate back to life, or go
        unconscious, for example.

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

        self.world.ruleset.do_action(
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
        Command ribbon method.

        Allows the user to pick a creature to defend itself.  In some rulesets
        (GURPS, for example), that would cause the creature to lose aim.

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

        self.world.ruleset.do_action(
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


    def _draw_screen(self):
        '''
        Draws the complete screen for the FightHandler.

        Returns: nothing.
        '''

        self._window.clear()
        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  next_PC_name,
                                  self.world.source_filename,
                                  ScreenHandler.maintain_game_file)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        self._window.status_ribbon(self.world.source_filename,
                                   ScreenHandler.maintain_game_file)
        self._window.command_ribbon()


    def __full_notes(self):
        '''
        Command ribbon method.

        Allows the user to modify the current fighter's full notes.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        return self.__notes('notes')


    def __give_equipment(self):
        '''
        Command ribbon method.

        Allows user to transfer one item of equipment from the "current"
        Fighter or Venue to another figher.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__viewing_index is not None:
            from_fighter = self.__fighters[self.__viewing_index]
        else:
            from_fighter = self.get_current_fighter()

        item = self.__equipment_manager.remove_equipment(from_fighter)
        if item is None:
            return True # Keep going


        character_list = self.world.get_creature_details_list(
                                                            from_fighter.group)
        character_menu = [(dude, dude) for dude in character_list]
        to_fighter_name = self._window_manager.menu(
                                        'Give "%s" to whom?' % item['name'],
                                        character_menu)

        if to_fighter_name is None:
            from_fighter.add_equipment(item, None)
            return True # Keep going

        to_fighter = self.get_fighter_object(to_fighter_name,
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
        # NOTE: if a ruleset has bleeding rules, there would be a call to the
        # ruleset, here.


    def __loot_bodies(self,
                      throw_away   # Required/used by the caller because
                                   #   there's a list of methods to call,
                                   #   and (apparently) some of them may
                                   #   use this parameter.  It's ignored
                                   #   by this method, however.
                     ):
        '''
        Gives the user the option to distribute the equipment of all the
        unconscious or dead monsters among the PCs.
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

        Provides a menu of activities that the current Fighter can perform.
        Performs the selected one.

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

        action_menu = self.world.ruleset.get_action_menu(current_fighter,
                                                     opponent)
        maneuver = self._window_manager.menu('Maneuver', action_menu)
        if maneuver is None:
            return True # Keep going

        if 'action' in maneuver:
            maneuver['action']['comment'] = '(%s) did (%s) maneuver' % (
                                                  current_fighter.name,
                                                  maneuver['action']['name'])

            self.world.ruleset.do_action(current_fighter, maneuver['action'], self)

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

        Close-out the actions of the current fighter and start the actions of
        the next fighter in the fight.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__viewing_index = None

        # Finish off previous guy
        prev_fighter = self.get_current_fighter()
        if not prev_fighter.can_finish_turn():
            return self.__maneuver()
        elif not prev_fighter.is_conscious():
            self.add_to_history({'comment': '(%s) did nothing (unconscious)' %
                                                    prev_fighter.name})

        self.world.ruleset.do_action(prev_fighter, {'name': 'end-turn'}, self)
        current_fighter = self.get_current_fighter()
        self.world.ruleset.do_action(current_fighter, {'name': 'start-turn'}, self)

        # Show all the displays
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  next_PC_name,
                                  self.world.source_filename,
                                  ScreenHandler.maintain_game_file)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __next_PC_name(self):
        '''
        Finds the name of the next PC (note: the next PC, not the next
        Fighter) to fight _after_ the current initiative.

        Returns the name of that PC.
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

        Allows the user to modify a Fighter's notes or short-notes.

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


    def __playback_history(self):
        '''
        Command ribbon method.

        If we're reproducing a scenario (like from a bug report), we're
        provided with a sequence of history.  This routine plays that entire
        sequence.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        next_fighter = self.get_current_fighter()
        self.world.playing_back = True
        for action in self.__saved_history:
            current_fighter = next_fighter

            #print '\n--- __playback_history'
            #PP.pprint(action)

            if 'fighter' in action:
                name = action['fighter']['name']
                group = action['fighter']['group']
                fighter = self.get_fighter_object(name, group)
            else:
                fighter = current_fighter
            self.world.ruleset.do_action(fighter, action, self)
            next_fighter = self.get_current_fighter()
            if next_fighter != current_fighter:
                # Update the display
                next_PC_name = self.__next_PC_name()
                self._window.round_ribbon(self._saved_fight['round'],
                                          next_PC_name,
                                          self.world.source_filename,
                                          ScreenHandler.maintain_game_file)

                opponent = self.get_opponent_for(next_fighter)
                self._window.show_fighters(next_fighter,
                                           opponent,
                                           self.__fighters,
                                           self._saved_fight['index'],
                                           self.__viewing_index)
        self.world.playing_back = False
        return True # Keep going


    def __prev_fighter(self):
        '''
        Command ribbon method.

        Move the initiative of the fight to the PREVIOUS character.  This is
        against the normal flow of actions but it's here in case the user
        inadvertently advanced the initiative or remembered something s/he
        wanted the previous fighter to have done.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__viewing_index = None
        if (self._saved_fight['index'] == 0 and
                self._saved_fight['round'] == 0):
            return True # Not going backwards from the origin

        self.modify_index(-1)
        next_PC_name = self.__next_PC_name()
        self._window.round_ribbon(self._saved_fight['round'],
                                  next_PC_name,
                                  self.world.source_filename,
                                  ScreenHandler.maintain_game_file)
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

        Quits the fight.  Gives the option to loot the bodies of unconscious
        (or worse) monsters.  Gives the option to keep the fight to be
        available to be fought another day, or to save the fight so that it'll
        be automatically chosen to be continued the next time the user goes to
        fight.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Get the state of the monsters.

        ask_to_save = False # Ask to save if some monster is conscious
        ask_to_loot = False # Ask to loot if some monster is unconscious
        for fighter in self.__fighters:
            if fighter.group != 'PCs' and fighter.name != Venue.name:
                if fighter.is_conscious():
                    ask_to_save = True
                else:
                    ask_to_loot = True

        # Ask: save or loot?

        # Open up a small window where the fight is not saved.  If there's a
        # crash, here, then we won't come back to the fight.
        self._saved_fight['saved'] = False
        self.__keep_monsters = False # Don't move monsters to dead after fight

        while ask_to_save or ask_to_loot:
            quit_menu = [('quit -- really', False)]

            if not self.__bodies_looted and ask_to_loot:
                quit_menu.append(('loot the bodies',
                                 {'doit': self.__loot_bodies}))

            saved_or_kept = (True if (self._saved_fight['saved'] or
                                            self.__keep_monsters) else False)

            if not saved_or_kept and ask_to_save:
                quit_menu.append(
                        ('save this fight as next fight to run',
                         {'doit': self.save_fight}))
                quit_menu.append(
                        ('keep this fight in available fight list',
                         {'doit': self.keep_fight}))

            result = self._window_manager.menu('Leaving Fight', quit_menu)

            if result is None:
                return True # I guess we're not quitting after all

            elif result == False:
                ask_to_save = False
                ask_to_loot = False

        if not self._saved_fight['saved']:
            for fighter in self.__fighters:
                fighter.end_fight(self.world, self)

        self._window.close()
        return False # Leave the fight


    def __select_fighter(self,
                         menu_title, # string: title of fighter/opponent menu
                         default_selection=0  # int: for menu:
                                              #   0=current fighter, 1=opponent
                         ):
        '''
        Selects a fighter to be the object of the current action based on a
        priority scheme in this method's comments, below.
        '''
        selected_fighter = None
        current_fighter = None

        # If there's a currently viewed fighter, choose him/her
        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
            opponent = self.get_opponent_for(current_fighter)
            selected_fighter = current_fighter
        else:
            current_fighter = self.get_current_fighter()
            opponent = self.get_opponent_for(current_fighter)

            if opponent is None:
                # If the fighter that has initiative has no opponent, choose
                # the current initiative fighter
                selected_fighter = current_fighter
            else:
                # If the current initiative fighter _does_ have an opponent,
                # ask the user whether to use the current initiative fighter
                # or the opponent.
                selected_fighter_menu = [
                                    (current_fighter.name, current_fighter),
                                    (opponent.name, opponent)]
                selected_fighter = self._window_manager.menu(
                                                     menu_title,
                                                     selected_fighter_menu,
                                                     default_selection)
        return selected_fighter, current_fighter


    def __short_notes(self):
        '''
        Command ribbon method.

        Lets the user edit a fighter's (or Venue's) short notes.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        return self.__notes('short-notes')


    def __show_history(self):
        '''
        Command ribbon method.

        Displays the actions that have happened in the fight.

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

        Shows detailed information about the selected creature.

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

        Explain the details that went into a fighter's calculated numbers
        (e.g., to-hit).

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        why_target, current_fighter = self.__select_fighter('Details For Whom')
        if why_target is None:
            return True # Keep fighting

        lines = why_target._explain_numbers(self)

        self._window_manager.display_window(
                    'How %s\'s Numbers Were Calculated' % why_target.name,
                    lines)
        return True


    def __timer(self):
        '''
        Command ribbon method.

        Asks user for information for a timer to add to a Fighter.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        timer_recipient, current_fighter = self.__select_fighter(
                                                            'Who Gets Timer')
        if timer_recipient is None:
            return True # Keep fighting

        timers_widget = TimersWidget(timer_recipient.timers,
                                     self._window_manager)

        timer_dict = timers_widget.make_timer_dict(timer_recipient.name)
        if timer_dict is not None:
            self.world.ruleset.do_action(timer_recipient,
                                     {'name': 'set-timer',
                                      'timer': timer_dict},
                                     self)

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

        Allows the user to cancel one of a Fighter's active timers.

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
        '''
        Command ribbon method.

        Make the 'currently viewed' character the one that currently has the
        initiative in the fight.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__viewing_index = None
        current_fighter = self.get_current_fighter()
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True # Keep going


    def __view_next(self):
        '''
        Command ribbon method.

        Look at next character, don't change which character currently has the
        initiative.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
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


    def __view_prev(self):
        '''
        Command ribbon method.

        Look at previous character, don't change which character currently has
        the initiative.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
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


class MainHandler(ScreenHandler):
    '''
    This is the primary screen of the program.  It displays a list of
    creatures, in the left pane.  It highlights the "current" creature and it
    shows the details of the current creature in the right pane.
    '''

    (CHAR_LIST,
     CHAR_DETAIL) = (1, 2)  # These are intended to be bits so they can be ored
                            # together

    def __init__(self,
                 window_manager,    # GmWindowManager object for menus and
                                    #   errors
                 world              # World object
                ):
        super(MainHandler, self).__init__(window_manager, world)
        self.__current_pane = MainHandler.CHAR_DETAIL
        self._add_to_choice_dict({
            curses.KEY_HOME:
                      {'name': 'scroll home',
                       'func': self.__first_page},
            curses.KEY_UP:
                      {'name': 'previous character',
                       'func': self.__prev_char},
            curses.KEY_DOWN:
                      {'name': 'next character',
                       'func': self.next_char},
            curses.KEY_NPAGE:
                      {'name': 'scroll down',
                       'func': self.__next_page},
            curses.KEY_PPAGE:
                      {'name': 'scroll up',
                       'func': self.__prev_page},
            curses.KEY_LEFT:
                      {'name': 'scroll chars',
                       'func': self.__left_pane},
            curses.KEY_RIGHT:
                      {'name': 'scroll char detail',
                       'func': self.__right_pane},

            ord('a'): {'name': 'about the program',
                       'func': self.__about},
            ord('f'): {'name': 'FIGHT',
                       'func': self.__run_fight},
            ord('h'): {'name': 'heal selected creature',
                       'func': self.__heal},
            ord('H'): {'name': 'Heal all PCs',
                       'func': self.__fully_heal},
            ord('m'): {'name': 'show MONSTERs or PC/NPC',
                       'func': self.__toggle_Monster_PC_NPC_display},
            ord('p'): {'name': 'PERSONNEL changes',
                       'func': self.__party},
            ord('q'): {'name': 'quit',
                       'func': self.__quit},
            ord('R'): {'name': 'resurrect fight',
                       'func': self.__resurrect_fight},
            ord('S'): {'name': 'toggle: Save On Exit',
                       'func': self.__maintain_game_file},
            ord('/'): {'name': 'search',
                       'func': self.__search}
        })
        self._window = self._window_manager.get_main_gm_window(self._choices)

        self.__current_display = None   # name of monster group or 'None' for
                                        # PC/NPC list
        self.__setup_PC_list(self.__current_display)

        self.__equipment_manager = EquipmentManager(self.world,
                                                    self._window_manager)

        # Check characters for consistency.
        for name in self.world.get_creature_details_list('PCs'):
            details = self.world.get_creature_details(name, 'PCs')
            if details is not None:
                self.world.ruleset.is_creature_consistent(name, details)


    #
    # Public Methods
    #

    def get_fighter_from_char_index(self):      # Public to support testing
        '''
        Returns the current Fighter (object).
        '''
        if self.__char_index >= len(self.__chars):
            return None
        return self.__chars[self.__char_index]


    def next_char(self,                         # Public to support testing
                  index=None  # Just for testing
                 ):
        '''
        Command ribbon method.

        Moves the pointer to the current creature to the next creature,
        wrapping around the list if necessary.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
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

    #
    # Protected and Private Methods
    #


    def __about(self):
        '''
        Command ribbon method.

        Displays information block for the combat accountant.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        lines = [[{'text': 'Combat Accountant', 'mode': curses.A_BOLD}],
                 [{'text': 'Version %s' % VERSION, 'mode': curses.A_NORMAL}],
                 [{'text': '', 'mode': curses.A_NORMAL}],
                 [{'text': 'Copyright (c) 2019, Wade Guthrie',  'mode': curses.A_NORMAL}],
                 [{'text': 'https://github.com/wadeguthrie/combat-accountant',
                                                                'mode': curses.A_NORMAL}],
                 [{'text': 'License: Apache License 2.0', 'mode': curses.A_NORMAL}]]

        self._window_manager.display_window('About Combat Accountant', lines)
        return True


    def __add_monsters(self,
                       throw_away   # Required/used by the caller because
                                    #   there's a list of methods to call,
                                    #   and (apparently) some of them may
                                    #   use this parameter.  It's ignored
                                    #   by this method, however.
                      ):
        '''
        Handler for an Party sub-menu entry.

        Modifies an existing monster list or creates a new monster list.

        Returns: True -- anything but None in a menu handler
        '''

        build_fight = PersonnelHandler(self._window_manager,
                                       self.world,
                                       PersonnelHandler.MONSTERs)
        build_fight.handle_user_input_until_done()

        # Display the last fight on the main screen

        last_group_name = build_fight.get_group_name()
        if (last_group_name is not None and last_group_name != 'PCs' and
                                            last_group_name != 'NPCs'):
            self.__current_display = last_group_name

        self.__setup_PC_list(self.__current_display)
        self._draw_screen()

        return True


    def __add_NPCs(self,
                   throw_away   # Required/used by the caller because
                                #   there's a list of methods to call,
                                #   and (apparently) some of them may
                                #   use this parameter.  It's ignored
                                #   by this method, however.
                  ):
        '''
        Handler for an Party sub-menu entry.

        Modifies the NPC list.

        Returns: True -- anything but None in a menu handler
        '''

        build_fight = PersonnelHandler(self._window_manager,
                                       self.world,
                                       PersonnelHandler.NPCs)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list(self.__current_display) # Since it may have changed
        self._draw_screen() # Redraw current screen when done building fight.
        return True


    def __add_PCs(self,
                  throw_away   # Required/used by the caller because
                               #   there's a list of methods to call,
                               #   and (apparently) some of them may
                               #   use this parameter.  It's ignored
                               #   by this method, however.
                 ):
        '''
        Handler for an Party sub-menu entry.

        Adds PCs to the PC list.

        Returns: True -- anything but None in a menu handler
        '''

        build_fight = PersonnelHandler(self._window_manager,
                                       self.world,
                                       PersonnelHandler.PCs)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list(self.__current_display) # Since it may have changed
        self._draw_screen() # Redraw current screen when done building fight.
        return True


    def _draw_screen(self,
                     inverse=False
                    ):
        '''
        Draws the complete screen for the MainHandler.

        Returns: nothing.
        '''
        self._window.clear()
        self._window.status_ribbon(self.world.source_filename,
                                   ScreenHandler.maintain_game_file)

        # MainGmWindow
        self._window.show_creatures(self.__chars,
                                    self.__char_index,
                                    inverse)

        person = (None if (self.__char_index is None or len(self.__chars) <= 0)
                       else self.__chars[self.__char_index])
        self._window.show_description(person)

        self._window.command_ribbon()


    def __first_page(self,
                     pane = None, # CHAR_LIST, CHAR_DETAIL,
                                  # CHAR_LIST|CHAR_DETAIL
                    ):
        '''
        Command ribbon method.

        Scrolls to the top of the current pain

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if pane is None:
            pane = self.__current_pane

        if (pane & MainHandler.CHAR_DETAIL) != 0:
            self._window.char_detail_home()

        if (pane & MainHandler.CHAR_LIST) != 0:
            self.__char_index = 0
            self._window.char_list_home()
            self._draw_screen()
        return True


    # MainHandler
    def __fully_heal(self):
        '''
        Command ribbon method.

        Completely heals (makes all of the 'current' stats equal to the
        equivalent 'permanent' stat) one of the PCs.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        for name in self.world.get_creature_details_list('PCs'):
            fighter = self.world.get_creature(name, 'PCs')
            if fighter is not None:
                self.world.ruleset.heal_fighter(fighter, self.world)
        self._draw_screen()
        return True


    # MainHandler
    def __heal(self):
        '''
        Command ribbon method.

        Heals the selected creature.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.get_fighter_from_char_index()
        if fighter is None:
            return True

        self.world.ruleset.heal_fighter(fighter, self.world)
        self._draw_screen()

        return True


    def __left_pane(self):
        '''
        Command ribbon method.

        Changes the currently active pane to the left-hand one.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__current_pane = MainHandler.CHAR_LIST
        return True


    def __maintain_game_file(self):
        '''
        Command ribbon method.  Toggles whether the results of this session
        are saved to the Game File when the program is exited.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        self.world.toggle_saved_on_exit()
        self._draw_screen()
        return True # Keep going


    def __next_page(self):
        '''
        Command ribbon method.

        Scrolls down on the current pane.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__current_pane == MainHandler.CHAR_DETAIL:
            self._window.scroll_char_detail_down()
        else:
            self._window.scroll_char_list_down()
        return True


    def __notes(self,
                notes_type  # <string> 'short-notes' or 'notes'
               ):
        '''
        Handler for an Equip sub-menu entry.

        Allows the user to modify a Fighter's notes or short-notes.

        Returns: None if we want to bail-out of the notes editing process,
                 True, otherwise
        '''
        fighter = self.get_fighter_from_char_index()
        if fighter is None:
            return True

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

        return True # Menu handler's success returns anything but 'None'


    def __party(self):
        '''
        Command ribbon method.

        Changes the mix of creatures in the lists (PC, NPC, and various
        monster lists).  Can create new monster lists.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        sub_menu = [
                    ('monster list',       {'doit': self.__add_monsters}),
                    ('npc list',           {'doit': self.__add_NPCs}),
                    ('pc list',            {'doit': self.__add_PCs}),
                    ]
        self._window_manager.menu('Modify Which List', sub_menu)
        return True


    def __prev_char(self):
        '''
        Command ribbon method.

        Changes the currently selected creature to the previous one in the
        displayed list.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if len(self.__chars) <= 0:
                return True

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
        '''
        Command ribbon method.

        Scroll up in the current pane.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__current_pane == MainHandler.CHAR_DETAIL:
            self._window.scroll_char_detail_up()
        else:
            self._window.scroll_char_list_up()
        return True


    def __quit(self):
        '''
        Command ribbon method.

        Quits out of the program.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self._window.close()
        del self._window
        self._window = None
        return False # Leave


    def __resurrect_fight(self):
        '''
        Command ribbon method.

        Asks the user which fight from the |dead-monsters| pile to put back
        into the list of available fights (then, you know, moves the fight).
        This is useful, for example, when a fight wasn't really done or when
        a monster for a previous fight is needed to be used as an NPC.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Ask which monster group to resurrect
        fight_name_menu = []
        for i, entry in enumerate(self.world.details['dead-monsters']):
            fight_name_menu.append((entry['name'], i))
        monster_group_index = self._window_manager.menu('Resurrect Which Fight',
                                                        fight_name_menu)
        if monster_group_index is None:
            return True

        monster_group = self.world.details['dead-monsters'][monster_group_index]

        if self.world.get_creature_details_list(
                                        monster_group['name']) is not None:
            self._window_manager.error(['Fight by name "%s" exists' %
                                                    monster_group['name']])
            return True

        # And, restore the fight
        self.world.restore_fight(monster_group_index)

        return True


    def __right_pane(self):
        '''
        Command ribbon method.

        Makes the right-hand pane the active pane for scrolling.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__current_pane = MainHandler.CHAR_DETAIL
        return True


    def __run_fight(self):
        '''
        Command ribbon method.

        Goes to the fight screen.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        monster_group = None
        if self._saved_fight['saved']:
            pass
        elif self.__current_display is not None:
            monster_group = self.__current_display
        else:
            fight_name_menu = [(name, name)
                                       for name in self.world.get_fights()]
            fight_name_menu = sorted(fight_name_menu,
                                     key=lambda x: x[0].upper())
            monster_group = self._window_manager.menu('Fights',
                                                      fight_name_menu)
            if monster_group is None:
                return True

        fight = FightHandler(self._window_manager,
                             self.world,
                             monster_group,
                             None)  # Playback history

        fight.handle_user_input_until_done()

        self.__current_display = None
        self.__setup_PC_list(self.__current_display) # The fight may have
                                                     # changed the PC/NPC lists
        self.__first_page(MainHandler.CHAR_LIST | MainHandler.CHAR_DETAIL)
        self._draw_screen() # Redraw current screen when done with the fight.

        return True # Keep going


    def __search(self):
        '''
        Asks the user for a string.  Searches for that string through the PCs,
        NPCs, and all of the fights.  If the user selects one of the matches,
        this method makes that the currently selected creature.

        Returns nothing.
        '''

        lines, cols = self._window.getmaxyx()
        look_for_string = self._window_manager.input_box(1,
                                                         cols-4,
                                                         'Search For What?')

        if look_for_string is None or len(look_for_string) <= 0:
            return True
        look_for_re = re.compile(look_for_string)

        all_results = []
        for name in self.world.get_creature_details_list('PCs'):
            creature = self.world.get_creature_details(name, 'PCs')
            result = self.world.ruleset.search_one_creature(name,
                                                        'PCs',
                                                        creature,
                                                        look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for name in self.world.get_creature_details_list('NPCs'):
            creature = self.world.get_creature_details(name, 'NPCs')
            result = self.world.ruleset.search_one_creature(name,
                                                        'NPCs',
                                                        creature,
                                                        look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for fight_name in self.world.get_fights():
            for name in self.world.get_creature_details_list(fight_name):
                creature = self.world.get_creature_details(name, fight_name)
                result = self.world.ruleset.search_one_creature(name,
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
                        group=None  # <string>  Name of monster list.  If
                                    #   |None|, it means the PCs, NPCs, and
                                    #   the Venue.
                       ):
        '''
        Builds self.__chars, a list of Fighter objects for either the Monsters
        (if |group| is not None) or the PCs, NPCs, and the Venue (all in one
        list).

        Returns nothing.
        '''
        if group is not None:
            self.__chars = []
            monsters = self.world.get_creature_details_list(group)
            if monsters is not None:
                the_fight_itself = None
                for name, details in monsters.iteritems():
                    if name == Venue.name:
                        the_fight_itself = details
                    else:
                        fighter = self.world.get_creature(name, group)
                        self.__chars.append(fighter)

                self.__chars = sorted(self.__chars, key=lambda x: x.name)

                # Add the Venue to the object array

                if len(self.__chars) == 0:
                    group = None

                # NOTE: I think we shouldn't add a fight object if one doesn't
                # exist.
                #
                #elif the_fight_itself is None:
                #  fight =  Venue(
                #   group,
                #   self.world.details['fights'][group]['monsters'][Venue.name],
                #   self.world.ruleset)

                elif the_fight_itself is not None:
                    fight = Venue(group,
                                  the_fight_itself,
                                  self.world.ruleset,
                                  self._window_manager)
                    self.__chars.insert(0, fight)


        if group is None:
            self.__chars = [
                self.world.get_creature(x, 'PCs')
                for x in sorted(self.world.get_creature_details_list('PCs'))]

            npcs = self.world.get_creature_details_list('NPCs')
            if npcs is not None:
                self.__chars.extend([
                        self.world.get_creature(x, 'NPCs')
                        for x in sorted(
                                self.world.get_creature_details_list('NPCs'))])
        else:
            pass

        self.__char_index = 0


    def __toggle_Monster_PC_NPC_display(self):
        '''
        Command ribbon method.

        Puts either a monster group or the PCs/NPCs on the screen.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__current_display is None:
            group_menu = [(group_name, group_name)
                            for group_name in self.world.get_fights()]
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
        #    monsters = self.world.get_creature_details_list(
        #                                           self.__current_display)
        #    for name in monsters:
        #        creature = self.world.get_creature_details(
        #                                           name,
        #                                           self.__current_display)
        #        self.world.ruleset.is_creature_consistent(name, creature)

        return True


class EquipmentManager(object):
    def __init__(self,
                 world,         # World object
                 window_manager # GmWindowManager object for menus and errors
                ):
        '''
        Manages equipment lists.  Meant to be embedded in a Fighter or a Venue.
        '''
        self.__world = world
        self.__window_manager = window_manager

    @staticmethod
    def get_description(
                        item,           # Input: dict for a 'stuff' item from
                                        #   Game File
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

        Puts data in |char_detail|.

        Returns nothing.
        '''

        mode = curses.A_NORMAL

        in_use_string = ' (in use)' if item in in_use_items else ''

        texts = ['  %s%s' % (item['name'], in_use_string)]
        if 'count' in item and item['count'] != 1:
            texts.append(' (%d)' % item['count'])

        if ('notes' in item and item['notes'] is not None and
                                                (len(item['notes']) > 0)):
            texts.append(': %s' % item['notes'])
        char_detail.append([{'text': ''.join(texts), 'mode': mode}])

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
                      fighter       # Fighter object
                     ):
        '''
        Ask user which item to transfer from the store to a fighter and
        transfer it.

        Returns nothing.
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
        '''
        Ask the user which piece of equipment to discard and remove it.

        Returns the removed piece of equipment.
        '''
        if fighter is None:
            return

        item_menu = [(item['name'], index)
                    for index, item in enumerate(fighter.details['stuff'])]
        item_index = self.__window_manager.menu('Item to Remove', item_menu)
        if item_index is None:
            return None

        return fighter.remove_equipment(item_index)



class MyArgumentParser(argparse.ArgumentParser):
    '''
    Code to add better error messages to argparse.
    '''
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


def timeStamped(fname,  # <string> Base filename
                tag,    # <string> Sepecial tag to add to the end of a filename
                ext,    # <string> Filename extnesion
                fmt='{fname}-%Y-%m-%d-%H-%M-%S{tag}.{ext}'
               ):
    '''
    Builds a time-stamped filename.
    '''
    tag = '' if tag is None else ('-%s' % tag)
    return datetime.datetime.now().strftime(fmt).format(fname=fname,
                                                        tag=tag,
                                                        ext=ext)


def are_equal(self, lhs, rhs):
    '''
    Checks to see if two entities are equivalent.
    '''
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


class Program(object):
    '''
    Holds the top-level program stuff.

    As part of that, it manages the debug files (which are really just
    snapshots of the Game File).
    '''
    def __init__(self,
                 source_filename,     # string: Name of the Game File
                ):
        self.__source_filename = source_filename
        self.__snapshots = {'startup': source_filename}

    def add_snapshot(self,
                     tag,       # string: circumstances of snapshot (e.g.,
                                #   startup, bug, etc.)
                     filename   # string: name of output data file associated with tag
                    ):
        '''
        Saves the name of a snapshot of the game file.  The name is saved with
        a tag that describes the reason for the snapshot.

        Returns: nothing
        '''
        self.__snapshots[tag] = filename


    def make_bug_report(self,
                        history,           # list of action dicts for the most recently
                                           #   started fight (see Ruleset::do_action)
                        user_description,  # string w/ '\n' to separate lines; user
                                           #   description of bug

                        crash_snapshot = None   # string: name of file to be
                                                #   saved as one last snapshot
                       ):
        '''
        Gathers all the information required (I hope) to reproduce a bug and
        writes it to a file.

        Returns: the name of the file to which the bug summary was written.
        '''

        if crash_snapshot is not None:
            self.add_snapshot('crash', crash_snapshot)

        # Build the bug report

        bug_report = {
            'version'   : VERSION,
            'world'     : self.__source_filename,
            'history'   : history,
            'report'    : user_description,
            'snapshots' : self.__snapshots
        }

        # Find a filename for the bug report

        keep_going = True
        count = 0
        extension = 'json'
        while keep_going:
            count_string = '%d' % count
            bug_report_game_file = timeStamped('bug_report',
                                               count_string,
                                               extension)
            if os.path.exists(bug_report_game_file):
                count += 1
            else:
                keep_going = False

        # Make a directory for the bug report

        extension = '.' + extension
        directory_name = bug_report_game_file
        if directory_name.endswith(extension):
            directory_name = directory_name[:-len(extension)]

        os.mkdir(directory_name)

        # Copy the snapshot files into the bug report directory

        for filename in self.__snapshots.itervalues():
            shutil.copy(filename, directory_name)

        # Dump the bug report into bug report file (in the directory)

        full_bug_report_game_file = os.path.join(directory_name,
                                                 bug_report_game_file)
        with open(full_bug_report_game_file, 'w') as f:
            json.dump(bug_report, f, indent=2)

        return bug_report_game_file


# Main
if __name__ == '__main__':
    VERSION = '00.00.00' # major version, minor version, bug fixes

    parser = MyArgumentParser()
    parser.add_argument('filename',
             nargs='?', # We get the filename elsewhere if you don't say here
             help='Input Game File containing characters and monsters')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)
    parser.add_argument('-m', '--maintain_game_file',
             help='Don\'t overwrite the input Game File.  Only for debugging.',
             action='store_true',
             default=False)
    parser.add_argument('-p', '--playback',
             help='Play the saved history back.  Only for debugging.')

    ARGS = parser.parse_args()

    # parser.print_help()
    # sys.exit(2)

    PP = pprint.PrettyPrinter(indent=3, width=150)
    playback_history = None

    program = None
    with GmWindowManager() as window_manager:
        ruleset = GurpsRuleset(window_manager)

        # Prefs
        # NOTE: When other things find their way into the prefs, the scope
        # of the read_prefs GmJson will have to be larger
        prefs = {}
        filename = None
        if ARGS.playback is not None:
            with GmJson(ARGS.playback) as bug_report:
                filename = bug_report.read_data['snapshots']['fight']
                playback_history = bug_report.read_data['history']
        else:
            filename = ARGS.filename

            prefs_filename = 'gm-prefs.json'
            if not os.path.exists(prefs_filename):
                with open(prefs_filename, 'w') as f:
                    f.write('{ }') # Provide a default preferences file

            with GmJson(prefs_filename) as read_prefs:
                prefs = read_prefs.read_data

                # Get the Campaign's Name
                if filename is not None:
                    read_prefs.write_data = prefs
                    prefs['campaign'] = filename

                elif 'campaign' in prefs:
                    filename = prefs['campaign']

                if filename is None:
                    filename_menu = [
                        (x, x) for x in os.listdir('.') if x.endswith('.json')]
                    filename_menu.insert(0, ('Create new campaign file', None))

                    filename = window_manager.menu('Which File', filename_menu)

                    lines, cols = window_manager.getmaxyx()
                    while filename is None:
                        # create a new file
                        filename = window_manager.input_box(1,
                                                            cols-4,
                                                            'Campaign name')
                        if len(filename) <= 0:
                            # Guess we're not going to run the program after all
                            sys.exit(2)

                        if not filename.endswith('.json'):
                            filename = filename + '.json'

                        if os.path.exists(filename):
                            window_manager.error(['Game File "%s" exists' % filename])
                            filename = None
                        else:
                            game_file = GmJson(filename, window_manager)
                            world_data = World.get_empty_world(
                                                    ruleset.get_sample_items())
                            game_file.open_write_json_and_close(world_data)

                    read_prefs.write_data = prefs
                    prefs['campaign'] = filename

        # Read the Campaign Data
        orderly_shutdown = False    # If the program exits before we turn this
                                    # to True, we probably exited via a crash
        with GmJson(filename, window_manager) as campaign:
            if campaign.read_data is None:
                window_manager.error(['Game File "%s" did not parse right'
                                        % filename])
                sys.exit(2)

            # Error check the Game File
            if 'PCs' not in campaign.read_data:
                window_manager.error(['No "PCs" in %s' % filename])
                sys.exit(2)

            program = Program(filename)
            world = World(filename, campaign, ruleset, program, window_manager)

            # Save the state of things when we leave since there wasn't a
            # horrible crash while reading the data.
            if ARGS.maintain_game_file:
                world.dont_save_on_exit()
            else:
                world.do_save_on_exit()

            if world.details['current-fight']['saved']:
                fight_handler = FightHandler(window_manager,
                                             world,
                                             None,
                                             playback_history)
                fight_handler.handle_user_input_until_done()

            # Enter into the mainloop
            main_handler = MainHandler(window_manager,
                                       world)
            orderly_shutdown = main_handler.handle_user_input_until_done()

        # Write a crashdump of the shutdown
        if not orderly_shutdown:
            if program is not None:
                program.make_bug_report(None, 'CRASH', filename)

