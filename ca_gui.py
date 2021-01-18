#! /usr/bin/python

import copy
import curses
import curses.ascii
import curses.textpad
import re


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
    self._draw_screen()  # Redraw current screen when done with XxxHandler

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
    SCREEN_MOVEMENT_CHARS = {
        ord(' '): '" "',
        curses.KEY_HOME: '<HOME>',
        curses.KEY_UP: '<UP>',
        curses.KEY_DOWN: '<DN>',
        curses.KEY_PPAGE: '<PGUP>',
        curses.KEY_NPAGE: '<PGDN>',
        curses.KEY_LEFT: '<LEFT>',
        curses.KEY_RIGHT: '<RIGHT>'
    }

    def __init__(self,
                 window_manager,  # A GmWindowManager object
                 # Using curses screen addressing w/0,0 in upper left corner
                 height,
                 width,
                 top_line,
                 left_column,
                 command_ribbon_choices=None
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
        self._window_manager.refresh_all()  # refresh everything else

    def command_ribbon(self):
        '''
        Draws a list of commands across the bottom of the screen.  Uses
        information gathered through |build_command_ribbon|.

        Returns nothing.
        '''
        choice_strings = copy.deepcopy(self._command_ribbon['choice_strings'])
        lines = self._command_ribbon['lines']
        cols = self._command_ribbon['cols']

        line = lines - 1  # -1 because last line is lines-1
        for subline in reversed(range(
                            self._command_ribbon['lines_for_choices'])):
            line = lines - (subline + 1)  # -1 because last line is lines-1
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

            # TODO (eventually): figure out why, occassionally, this fails.
            # I _think_ it's when the math doesn't quite work out and
            # something goes beyond the edge of the screen, but that's just a
            # theory.
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
                         character  # Fighter or Venue object
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
            if command in GmWindow.SCREEN_MOVEMENT_CHARS:
                command_string = GmWindow.SCREEN_MOVEMENT_CHARS[command]
            elif command < 256:
                command_string = '%c' % chr(command)
            else:
                command_string = '<%d>' % command

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

        self._command_ribbon['choices_per_line'] = int(
                (cols - 1) /
                self._command_ribbon['max_width'])  # -1 for last '|'
        self._command_ribbon['lines_for_choices'] = int(
                (len(choices) /
                    (self._command_ribbon['choices_per_line'] + 0.0))
                + 0.9999999)  # +0.9999 so 'int' won't truncate partial line

        self._command_ribbon['choice_strings'].sort(reverse=True,
                                                    key=lambda s:
                                                    s['command'].lower())


class GmWindowManager(object):
    '''
    GmWindowManager addresses the graphical part of the user interface for
    gm.py.  Here, this is provided with the Curses package.
    '''

    ESCAPE = 27  # ASCII value for the escape character

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
    #   color_pair is setup using: curses.init_pair(1,  # should be a symbol
    #                                               curses.COLOR_RED,  # fg
    #                                               curses.COLOR_WHITE)  # bg
    #   only legal colors: 0:black, 1:red, 2:green, 3:yellow, 4:blue,
    #                      5:magenta, 6:cyan, and 7:white
    #

    def __init__(self):
        self.__stdscr = None
        self.__y = 0  # For debug printouts

        # Stack of GmWindow in Z order.  The screen can be completely re-drawn
        # by building from the bottom of the stack to the top.
        self.__window_stack = []
        self.STATE_COLOR = {}

    def __enter__(self):
        try:
            self.__stdscr = curses.initscr()

            # Seems to be needed for the initial screen to be shown.
            self.__stdscr.refresh()
            curses.start_color()
            curses.use_default_colors()
            self._setup_colors()
            curses.noecho()
            curses.cbreak()  # respond instantly to keystrokes

            # special characters converted by curses (e.g., curses.KEY_LEFT)
            self.__stdscr.keypad(1)

            # Setup some defaults before I overwrite any

            # An experiment showed that there are only 16 colors in the
            # Windows console that I was running.  They are
            # 0:black, 1:red, 2:green, 3:yellow, 4:blue, 5:magenta, 6:cyan,
            # 7:white, and (I think) the dark versions of those.
            # for i in range(0, curses.COLORS):
            #    curses.init_pair(i+1,   # New ID for color pair
            #                     i,     # Specified foreground color
            #                     -1     # Default background
            #                    )

            curses.init_pair(GmWindowManager.RED_BLACK,
                             curses.COLOR_RED,  # fg
                             curses.COLOR_BLACK)  # bg
            curses.init_pair(GmWindowManager.GREEN_BLACK,
                             curses.COLOR_GREEN,  # fg
                             curses.COLOR_BLACK)  # bg
            curses.init_pair(GmWindowManager.YELLOW_BLACK,
                             curses.COLOR_YELLOW,  # fg
                             curses.COLOR_BLACK)  # bg
            curses.init_pair(GmWindowManager.BLUE_BLACK,
                             curses.COLOR_BLUE,  # fg
                             curses.COLOR_BLACK)  # bg
            curses.init_pair(GmWindowManager.MAGENTA_BLACK,
                             curses.COLOR_MAGENTA,  # fg
                             curses.COLOR_BLACK)    # bg
            curses.init_pair(GmWindowManager.CYAN_BLACK,
                             curses.COLOR_CYAN,   # fg
                             curses.COLOR_BLACK)  # bg
            curses.init_pair(GmWindowManager.WHITE_BLACK,
                             curses.COLOR_WHITE,  # fg
                             curses.COLOR_BLACK)  # bg

            curses.init_pair(GmWindowManager.RED_WHITE,
                             curses.COLOR_RED,    # fg
                             curses.COLOR_WHITE)  # bg

            self.__stdscr.clear()
            self.__stdscr.refresh()
        except:
            curses.endwin()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
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
                       title,  # string: the title displayed, centered, in the
                               #   box around the display window.
                       lines   # [[{'text', 'mode'}, ],    # line 0
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
        # max_height = curses.LINES - 2  # 2 for the box
        # if height > max_height:
        #    height = max_height

        width = 0 if title is None else len(title)
        for line in lines:
            this_line_width = 0
            for piece in line:
                this_line_width += len(piece['text'])
            if this_line_width > width:
                width = this_line_width
        width += 1  # Seems to need one more space (or Curses freaks out)

        border_win, display_win = self.__centered_boxed_window(
                                                    height,
                                                    width,
                                                    title,
                                                    data_for_scrolling=lines)
        display_win.refresh()

        keep_going = True
        # on my laptop, <Fn>+<down> is page down EXCEPT it's really easy to
        # type <Alt>+<down> (similarly with <up>).  This just grandfathers
        # those keys to make them work as well.
        ALT_PGDN = 491
        ALT_PGUP = 490

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
            elif user_input == curses.KEY_NPAGE or user_input == ALT_PGDN:
                display_win.scroll_down()
            elif user_input == curses.KEY_PPAGE or user_input == ALT_PGUP:
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
        width += 2  # Need some margin
        border_win, error_win = self.__centered_boxed_window(len(strings)+2,
                                                             width,
                                                             title,
                                                             mode)
        for line, string in enumerate(strings):
            # print 'line %r string %r (len=%d)' % (line, string, len(string))
            error_win.addstr(line+1, 1, string, mode)
        error_win.refresh()

        ignored = self.get_one_character()

        del border_win
        del error_win
        self.hard_refresh_all()

    def get_mode_from_fighter_state(self,
                                    state  # from STATE_COLOR
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
                          window=None  # Window (for Curses)
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

        # TODO(eventually): this should be a mini-context manager that should
        # get the current state of cbreak and echo and set them on entry and
        # then reinstate them on exit.

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

    def input_box_calc(self,
                       height,           # int: height of the data window (the
                                         #   box around it will, therefore, be
                                         #   bigger)
                       width,            # int: width of the data window (see
                                         #   |height|)
                       initial_value,    # int/float: starting value
                       title             # string: the title displayed,
                                         #   centered, in the box around the
                                         #   data.
                       ):
        '''
        Returns input number (but allows addition and subtraction to initial).
        '''

        result = 0 if initial_value is None else initial_value

        string = self.input_box(height, width, title)
        if string is None or len(string) == 0:
            return initial_value

        match = re.match('\s*(?P<sign>[\+\-]?)\s*(?P<value>[0-9\.]+)', string)
        if match is None:
            return result

        try:
            if '.' in match.groupdict()['value']:
                input_value = float(match.groupdict()['value'])
            else:
                input_value = int(match.groupdict()['value'])
        except ValueError:
            self.error(['Invalid value for a number'])
            return initial_value

        if (match.groupdict()['sign'] is None or
                len(match.groupdict()['sign']) == 0):
            return input_value

        if match.groupdict()['sign'] == '+':
            return result + input_value

        return result - input_value

    def input_box_number(self,
                         height,    # int: height of the data window (the
                                    #   box around it will, therefore, be
                                    #   bigger)
                         width,     # int: width of the data window (see
                                    #   |height|)
                         title      # string: the title displayed,
                                    #   centered, in the box around the
                                    #   data.
                         ):
        '''
        Returns input number (does _not_ allow calculations to the number).
        '''
        number_string = self.input_box(height, width, title)
        if len(number_string) <= 0:
            return None

        try:
            if '.' in number_string:
                number = float(number_string)
            else:
                number = int(number_string)
        except ValueError:
            self.error(['Invalid value for a number'])
            return None
        else:
            return number

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
             starting_index=0,  # Who is selected when the menu starts
             skip_singles=True  # Do I show menu even if it's only got 1 item?
             ):
        '''
        Presents a menu to the user and returns the result and the index of
        the result.

        The result value in strings_results can be anything and take any form.
        '''
        (MENU_STRING, MENU_RESULT) = range(0, 2)

        if len(strings_results) < 1:  # if there's no choice, say so
            return None, None

        # if only 1 choice, autoselect it
        if len(strings_results) == 1 and skip_singles:
            return (self.__handle_menu_result(strings_results[0][MENU_RESULT]),
                    0)

        # height and width of text box (not border)
        height = len(strings_results)
        max_height = curses.LINES - 2  # 2 for the box
        if height > max_height:
            height = max_height
        width = 0 if title is None else len(title)
        for string, result in strings_results:
            if len(string) > width:
                width = len(string)
        width += 1  # Seems to need one more space (or Curses freaks out)

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

        index_into_current_pane = starting_index
        while index_into_current_pane >= height:
            menu_win.scroll_down(height)
            index_into_current_pane -= height

        if index_into_current_pane != starting_index:
            menu_win.draw_window()
            menu_win.refresh()

        while True:  # The only way out is to return a result
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
                        strings_results[index][MENU_RESULT]), index
            elif user_input == GmWindowManager.ESCAPE:
                del border_win
                del menu_win
                self.hard_refresh_all()
                return None, None
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
                            return (self.__handle_menu_result(
                                        strings_results[index][MENU_RESULT]),
                                    index)

            if new_index != index:
                old_index = index
                if new_index < 0:
                    index = len(data_for_scrolling) - 1
                elif new_index >= len(data_for_scrolling):
                    index = 0
                else:
                    index = new_index

                # print 'INDEX - old:%d, new:%d, final:%d' % (old_index,
                #                                             new_index,
                #                                             index)

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
                          width=None,  # window size
                          top_line=0,
                          left_column=0  # window placement
                          ):
        '''
        Returns native-typed window (a curses window, in this case).
        '''

        # Doing this because I can't use curses.LINES in the autoassignment
        if height is None:
            height = curses.LINES
        if width is None:
            width = curses.COLS

        window = curses.newwin(height, width, top_line, left_column)
        return window

    def pop_gm_window(self,
                      delete_this_window  # GmWindow object: window to be
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
                                height,  # height of INSIDE window
                                width,   # width of INSIDE window
                                title,   # string: title displayed for the
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

        # print 'c h:%d, w:%d, y:%d, x:%d' % (
        #    height+2, width+2, begin_y-1, begin_x-1)

        border_win = curses.newwin(height+box_margin,
                                   width+box_margin,
                                   begin_y-1,
                                   begin_x-1)
        border_win.border()
        if title is not None:
            max_title_len = width + box_margin
            if len(title) >= max_title_len:
                title = title[:(max_title_len-1)]

            title_start = (max_title_len - (len(title))) / 2
            border_win.addstr(0, title_start, title)

        border_win.refresh()

        if data_for_scrolling is not None:
            menu_win = GmScrollableWindow(data_for_scrolling,
                                          self,
                                          height,
                                          width,
                                          begin_y,
                                          begin_x)
            # menu_win.bkgd(' ', mode)

        else:
            menu_win = curses.newwin(height, width, begin_y, begin_x)
            menu_win.bkgd(' ', mode)

        return border_win, menu_win

    def __handle_menu_result(self,
                             menu_result  # Can literally be anything
                             ):
        '''
        If a menu_result is a dict that contains either another menu or a
        'doit' function, show the menu to the user or call the 'doit' function.

        Returns the result of the menu or the return value of the 'doit'
        function, as appropriate.
        '''

        if isinstance(menu_result, dict):
            while 'menu' in menu_result:
                menu_result, ignore = self.menu('Which', menu_result['menu'])
                if menu_result is None:  # Bail out regardless of nesting level
                    return None          # Keep going

            if 'doit' in menu_result and menu_result['doit'] is not None:
                param = (None if 'param' not in menu_result
                         else menu_result['param'])
                menu_result = (menu_result['doit'])(param)

        return menu_result

    def _setup_colors(self):
        pass


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
                 width=None,  # window size
                 top_line=0,
                 left_column=0  # window placement
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
        # TODO: I've got al these commented-out lines to skip lines that are
        # the result of a wrap (like the Mech in the <<ROOM>> of the Armstrong
        # 1 fight) but then the line count for the window is too small and we
        # get a  crash.
        #line = 0
        for i in range(0, line_cnt):
            left = 0
            #y_start, x_start = self.__window.getyx()
            for piece in self.__lines[i+self.top_line]:
                self.__window.addstr(i, left, piece['text'], piece['mode'])
                # instead of 'i', should be 'line'
                left += len(piece['text'])

            #y, x = self.__window.getyx()
            #if y == y_start:
            #    line += 1
            #else:
            #    line += y - y_start

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
                  line_cnt=None  # int: number of lines to scroll, 'None'
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
