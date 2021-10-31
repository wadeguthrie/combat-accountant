#! /usr/bin/python

import argparse
import copy
import curses
import datetime
import glob
import json
import os
import pprint
import random
import re
import shutil
import sys
import traceback

import ca_equipment
import ca_fighter
import ca_json
import ca_gui
import ca_ruleset
import ca_gurps_ruleset
import ca_timers

# TODO: GmScrollableWindow should have their lines public and all access to
#   those should be through the object's data

# TODO: Make unarmed stuff more closely mirror the armed stuff.

# TODO: make sure unarmed stuff works:
#   * unarmed Dual-Weapon attack
#   * unarmed parry
#   * brass knuckles

# TODO: flesh-out attack, all-out
# TODO: grenade support (missile-like but not with clips)

# TODO: ISSUE 9: maintain spell
# TODO: ISSUE 20: need a way to generate equipment

# TODO: HouseRule: reload and spells should happen at the end of the timer.  The
#       'reloading' timer should launch the second part of the action when it
#       fires.
# TODO: why do redirect entries have 'stuff' and 'timers' entries?

# TODO: FP should ask if using DR
# TODO: FP should actually subtract DR

# TODO: PC joins NPCs in PC editing mode

# TODO: consistency check for preferred weapons/armor should only ask once

# NOTE: debugging thoughts:
#   - traceback.print_stack()


class CaGmWindowManager(ca_gui.GmWindowManager):
    def __init__(self):
        super(CaGmWindowManager, self).__init__()

    def get_build_fight_gm_window(self,
                                  command_ribbon_choices  # dict: ord('T'):
                                                          #   {'name': xxx,
                                                          #    'func': yyy},...
                                  ):
        '''
        Returns a PersonnelGmWindow object.  Useful for providing Mocks
        in testing.
        '''
        return PersonnelGmWindow(self, command_ribbon_choices)

    def get_fight_gm_window(self,
                            ruleset,                 # Ruleset object
                            command_ribbon_choices,  # dict: ord('T'):
                                                     #   {'name': xxx,
                                                     #    'func': yyy}, ...
                            fight_handler
                            ):
        '''
        Returns a FightGmWindow object.  Useful for providing Mocks in testing.
        '''
        return FightGmWindow(self,
                             ruleset,
                             command_ribbon_choices,
                             fight_handler)

    def get_main_gm_window(self,
                           command_ribbon_choices  # dict: ord('T'):
                                                   #   {'name': xxx,
                                                   #    'func': yyy}, ...
                           ):
        '''
        Returns a MainGmWindow object.  Useful for providing Mocks in testing.
        '''
        return MainGmWindow(self, command_ribbon_choices)

    def _setup_colors(self):
        '''
        Establishes the colors for various states.

        Returns: nothing.
        '''
        self.STATE_COLOR = {
            ca_fighter.Fighter.ALIVE:
                curses.color_pair(ca_gui.GmWindowManager.GREEN_BLACK),
            ca_fighter.Fighter.INJURED:
                curses.color_pair(ca_gui.GmWindowManager.YELLOW_BLACK),
            ca_fighter.Fighter.UNCONSCIOUS:
                curses.color_pair(ca_gui.GmWindowManager.MAGENTA_BLACK),
            ca_fighter.Fighter.DEAD:
                curses.color_pair(ca_gui.GmWindowManager.MAGENTA_BLACK),
            ca_fighter.Fighter.ABSENT:
                curses.color_pair(ca_gui.GmWindowManager.BLUE_BLACK),
            ca_fighter.Fighter.FIGHT:
                curses.color_pair(ca_gui.GmWindowManager.CYAN_BLACK),
        }


class MainGmWindow(ca_gui.GmWindow):
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

        # [[{'text', 'mode'}, ...],   # line 0
        #  [...],                  ]  # line 1...
        self._char_detail = []

        # [[{'text', 'mode'}, ...],   # line 0
        #  [...],                  ]  # line 1...
        self.__char_list = []

        top_line = 1
        height = (lines         # The whole window height, except...
                    - top_line  # ...a block at the top, and...
                    - (self._command_ribbon['lines_for_choices'] + 1))
                                # ...a space for the command ribbon + margin

        width = (cols / 2) - 1  # -1 for margin

        self.__char_list_window = ca_gui.GmScrollableWindow(
                                                 self.__char_list,
                                                 self._window_manager,
                                                 height,
                                                 width-1,
                                                 top_line,
                                                 1)
        self._char_detail_window = ca_gui.GmScrollableWindow(
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

    def show_creatures(self,
                       char_list,       # [Fighter(), Fighter(), ..]
                       current_index,   # int: index into char_list of
                                        #   currently selected fighter
                       standout=False   # True if list to be shown in
                                        #   inverse video, False otherwise
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
            elif char.name == ca_fighter.Venue.name:
                mode |= self._window_manager.color_of_venue()
            else:
                mode |= self._window_manager.get_mode_from_fighter_state(
                        ca_fighter.Fighter.get_fighter_state(char.details))

            mode |= (curses.A_NORMAL if current_index is None or
                     current_index != line else curses.A_STANDOUT)

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


class PersonnelGmWindow(ca_gui.GmWindow):
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
        # TODO (eventually): should _char_detail be in GmWindow?
        self._char_detail = []  # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        self.__char_list = []   # [[{'text', 'mode'}, ...],   # line 0
                                #  [...],                  ]  # line 1...

        top_line = 1
        height = (lines                 # The whole window height, except...
            - top_line                  # ...a block at the top, and...
            - (self._command_ribbon['lines_for_choices'] + 1))
                                        # ...a space for the command ribbon.

        width = (cols / 2) - 2  # -1 for margin

        self.__char_list_window = ca_gui.GmScrollableWindow(
                                                 self.__char_list,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 1)
        self._char_detail_window = ca_gui.GmScrollableWindow(
                                                 self._char_detail,
                                                 self._window_manager,
                                                 height,
                                                 width,
                                                 top_line,
                                                 width+1)

    def char_detail_home(self):
        ''' Scrolls the character detail pane to the top and redraws it. '''
        self._char_detail_window.scroll_to(0)
        self._char_detail_window.draw_window()
        self._char_detail_window.refresh()

    def char_list_home(self):
        ''' Scrolls the character list pane to the top and redraws it.  '''
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

    # TODO (eventually): genericize the scrolling stuff and just pass the
    # window to the generic routine.  Pay attention to '/' because the generic
    # routines have differeent search code than the specific.  You can address
    # it by having the generic code take 'enable_search_code' as a parameter.

    def scroll_char_list_up(self):
        ''' Scrolls the character list pane up.  '''
        self.__char_list_window.scroll_up()
        self.__char_list_window.draw_window()
        self.__char_list_window.refresh()

    def show_creatures(self,
                       char_list,       # [Fighter(), Fighter(), ..]
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
        return False  # Leave


class FightGmWindow(ca_gui.GmWindow):
    '''
    Window display for running a fight.  Has panes for the current fighter,
    the current defender, and the list of creatures.
    '''
    def __init__(self,
                 window_manager,          # GmWindowManager object
                 ruleset,                 # Ruleset object
                 command_ribbon_choices,  # dict: ord('T'): {'name': xxx,
                                          #                  'func': yyy}, ...
                 fight_handler
                 ):
        super(FightGmWindow, self).__init__(window_manager,
                                            curses.LINES,
                                            curses.COLS,
                                            0,
                                            0,
                                            command_ribbon_choices)
        self.__ruleset = ruleset
        self.__fight_handler = fight_handler
        self.__pane_width = curses.COLS / 3  # includes margin
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
                     round_no,           # int: round number
                     next_PC_name,       # string: name of next PC in
                                         #   initiative order
                     input_filename,     # string: name of game file
                     maintain_game_file  # bool: True if we are NOT overwriting
                                         #   game file when exiting
                     ):
        '''
        Prints the fight round information at the top of the screen.

        Returns nothing
        '''

        self._window.move(0, 0)
        self._window.clrtoeol()
        lines, cols = self._window.getmaxyx()

        # start @1, but round is an index (which starts at 0)
        round_string = 'Round %d' % (round_no+1)
        self._window.addstr(0,  # y
                            0,  # x
                            round_string,
                            curses.A_NORMAL)

        if next_PC_name is not None:
            self._window.move(self.__NEXT_LINE, 0)
            self._window.clrtoeol()
            mode = curses.color_pair(ca_gui.GmWindowManager.MAGENTA_BLACK)
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
                      current_index,    # int: Index of fighter that has the
                                        #   initiative
                      selected_index=None   # index to view if it's not the
                                            #  current index
                      ):
        '''
        Displays the current state of the current fighter and his opponent,
        if he has one.
        '''

        self.__show_fighter_notes(current_fighter,
                                  opponent,
                                  is_attacker=True,
                                  window=self.__character_window)

        if opponent is None:
            self.__opponent_window.clear()
            self.__opponent_window.refresh()
        else:
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
            - (self.__FIGHTER_LINE)   # ...a block at the top, and...
            - (self._command_ribbon['lines_for_choices'] + 1))
                                        # ...a space for the command ribbon.

        self.fighter_win_width = self.__pane_width - self.__margin_width

        top_line = self.__FIGHTER_LINE  # Start after the main fighter info

        # TODO: eventually, make these ca_gui.GmScrollableWindow windows
        self.__character_window = self._window_manager.new_native_window(
                height,
                self.fighter_win_width,
                top_line,
                self.__FIGHTER_COL)
        self.__opponent_window = self._window_manager.new_native_window(
                height,
                self.__pane_width - self.__margin_width,
                top_line,
                self.__OPPONENT_COL)
        self.__summary_window = self._window_manager.new_native_window(
                height,
                self.__pane_width - self.__margin_width,
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
        output = []
        fighter.get_description_medium(output, fighter, opponent, is_attacker)

        #
        # Display the output
        # TODO (eventually): make the window scrollable rather than limit
        #

        window.clear()
        lines, cols = window.getmaxyx()
        line = 0
        for pieces in output:
            if line >= lines:
                break
            left = 0
            y_start, x_start = window.getyx()
            for piece in pieces:
                window.addstr(line, left, piece['text'], piece['mode'])
                left += len(piece['text'])
            y, x = window.getyx()

            if y == y_start:
                line += 1
            else:
                line += y - y_start

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
                            fighter.get_description_short(
                                self.__fight_handler))

            if selected_index is not None and selected_index == line:
                mode = mode | curses.A_REVERSE
            elif fighter.group == 'PCs':
                mode = mode | curses.A_BOLD
            self.__summary_window.addstr(line, 0, fighter_string, mode)


class World(object):
    '''
    Manages the data in the Game File. This contains the base information for
    the entire world.
    '''
    debug_directory = 'debug'

    def __init__(self,
                 source_filename,     # Name of file w/ the Game File
                 world_details,       # GmJson object
                 ruleset,             # Ruleset object
                 program,             # Program object to collect snapshot info
                 window_manager,      # a GmWindowManager object to handle I/O
                 save_snapshot=True   # Here so tests can disable it
                 ):
        self.source_filename = source_filename
        self.program = program

        # only used for toggling whether the data is saved on exit of the
        # program.
        self.__gm_json = world_details

        self.details = world_details.read_data  # entire dict from Game File
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

        # Are we currently playing back a debug file?
        self.playing_back = False

        if save_snapshot:
            self.do_debug_snapshot('startup')

    @staticmethod
    def get_empty_world(
            stuff=[]    # List of equipment (dict) to include in empty world
            ):
        '''
        Returns a dict that contains an empty world -- used for creating new
        game files.
        '''
        result = {'templates': {},
                  'fights': {},
                  'PCs': {},
                  'dead-monsters': [],
                  'current-fight': {'history': [],
                                    'held-init': [],
                                    'saved': False},
                  'NPCs': {},
                  'stuff': stuff,
                  'options': {}
                  }
        return result

    def add_to_history(self,
                       action   # {'action-name':xxx, ...} -
                                #   see Ruleset::do_action()
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
        Causes the local copy of the Game File data NOT to be written back
        to the file when the program ends.

        Returns nothing.
        '''
        self.__gm_json.write_data = None
        ScreenHandler.maintain_game_file = True

    def get_creature(self,
                     name,  # String: name of creature to get
                     group  # String: 'PCs', 'NPCs', or monster group
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
            self.__fighters[group][name] = ca_fighter.Fighter(
                                            name,
                                            group,
                                            self.get_creature_details(name,
                                                                      group),
                                            self.ruleset,
                                            self.__window_manager)

        return self.__fighters[group][name]

    def get_creature_details(self,
                             name,       # string name of creature
                             group_name  # string name of creature's group
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
                    ['No name "%s" in monster group "%s"' %
                        (name, group_name)])
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
                                  group_name  # string: 'PCs', 'NPCs', or a
                                              #     monster group
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
        # TODO (eventually): should return an array so that any structure of
        # naming categories is permitted.
        randomly_generate = False

        # TODO (eventually): 'names' should be optional
        if 'names' not in self.details or self.details['names'] is None:
            return None, None, None

        # Country

        country_menu = [(x, x) for x in self.details['names']]
        country_name, ignore = self.__window_manager.menu('What kind of name',
                                                          country_menu)
        if country_name is None:
            randomly_generate = True
            country_name = random.choice(self.details['names'].keys())

        # Gender

        gender_list = ['male', 'female']
        if not randomly_generate:
            gender_menu = [(x, x) for x in gender_list]
            gender, ignore = self.__window_manager.menu('What Gender',
                                                        gender_menu)
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
            fmt = '%Y-%m-%d-%H-%M-%S'
            date = datetime.datetime.now().strftime(fmt).format()

            monsters = self.details['fights'][group_name]['monsters']
            self.details['dead-monsters'].append({'name': group_name,
                                                  'date': date,
                                                  'monsters': monsters})

            # Remove fight from regular monster list
            del self.details['fights'][group_name]
            del self.__fighters[group_name]

    def restore_fight(self,
                      group_index  # index into |dead-monsters|
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
                if mod_date < two_days_ago:  # '<' means 'earlier than'
                    os.remove(path)


class ScreenHandler(object):
    '''
    Base class for the "business logic" backing the user interface.
    '''

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
            ord('B'): {'name': 'Bug Report',
                       'func': self._make_bug_report,
                       'help': 'Builds a bug report including asking ' +
                               'you for a description and taking ' +
                               'a few snapshots of your game file.  ' +
                               'Puts all this in a directory tagged ' +
                               'by the date and time of the report.'},
            ord('H'): {'name': 'Help',
                       'func': self._print_help,
                       'help': 'Prints this text.'},
        }

        if ARGS.debug:
            self._choices[ord('X')] = {'name': 'CRASH',
                                       'func': self._crash,
                                       'help': 'Crashes the system.'}

    @staticmethod
    def string_from_character_input(char    # character to convert
                                    ):
        '''
        Returns a printable string from a character.  This is intended to be
        used to display messages regarding screen input.
        '''
        if char < 256:
            return '%c' % chr(char)

        if char in ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS:
            return '%s' % ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS[char]

        return '%d' % char

    def add_to_history(self,
                       action   # {'action-name':xxx, ...} -
                                #   see Ruleset::do_action()
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
                        ScreenHandler.string_from_character_input(string)])
        return True

    #
    # Protected Methods
    #

    def _add_to_choice_dict(self,
                            new_choices  # dict: {
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
                if key < 256:
                    self._window_manager.error(
                        ['Collision of _choices on key "%c"' % chr(key)])
                    self._window_manager.error(
                        ['Collision of _choices on key "<%d>"' % key])
                return False  # Found a problem

        self._choices.update(new_choices)

    def _crash(self):
        gonna_crash_it = {}
        check = gonna_crash_it['crash_it_now']

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

        bug_report_game_file = self.world.program.make_bug_report(
                self._saved_fight['history'],
                report,
                None, # snapshot filename
                'requested')

        self._window_manager.display_window(
                'Bug Reported',
                [[{'text': ('Output file "%s"' % bug_report_game_file),
                   'mode': curses.A_NORMAL}]])

        return True  # Keep doing whatever you were doing.

    def _print_help(self):
        '''
        Prints out the help screens for the current command ribbon.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        # Figure out how big the different columns are

        max_key_len = 0
        max_name_len = 0
        margin_len = 2
        max_help_len = 0
        for key, value in self._choices.iteritems():
            if key in ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS:
                char = ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS[key]
            elif key < 256:
                char = chr(key)
            else:
                char = '<%d>' % key
            if max_key_len < len(char):
                max_key_len = len(char)
            if 'name' in value and max_name_len < len(value['name']):
                max_name_len = len(value['name'])
            if 'help' in value and max_help_len < len(value['help']):
                max_help_len = len(value['help'])

        lines, cols = self._window_manager.getmaxyx()

        # Just an aesthetic choice to have the help box just a little
        # smaller than the screen.
        cols -= 2

        window_box_margin = 2  # Space for the box around the display window
        help_indent = max_key_len + margin_len + max_name_len + margin_len

        actual_max_help_len = (cols - window_box_margin) - help_indent
        if max_help_len > actual_max_help_len:
            max_help_len = actual_max_help_len

        # Put in sorted order

        keys = []
        for key in self._choices.iterkeys():
            if key in ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS:
                char = ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS[key]
            elif key < 256:
                char = '%c' % chr(key)
            else:
                char = '<%d>' % key
            keys.append({'sort_key': char,
                         'choice_key': key})
        keys.sort(key=lambda x: x['sort_key'].lower())

        # Now, assemble the output

        # Instead of BOLD, it was: curses.color_pair(
        # ca_gui.GmWindowManager.CYAN_BLACK),
        colors = [curses.A_BOLD, curses.A_NORMAL]
        color_index = 1

        output = []
        for x in keys:
            key = x['choice_key']
            value = self._choices[key]
            color_index = 1 if color_index == 0 else 0

            line_parts = []

            # Add the key

            if key in ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS:
                key = ca_gui.GmWindow.SCREEN_MOVEMENT_CHARS[key]
            elif key < 256:
                key = chr(key)
            else:
                key = '<%d>' % key

            line_parts.append(key)
            line_parts.append(' ' * (max_key_len - len(key)))
            line_parts.append(' ' * margin_len)

            # Add the name

            name = '' if 'name' not in value else value['name']
            line_parts.append(name)
            line_parts.append(' ' * (max_name_len - len(name)))
            line_parts.append(' ' * margin_len)

            # Add the help -- need to wrap the lines at spaces

            if 'help' not in value:
                output.append([{'text': ''.join(line_parts),
                                'mode': colors[color_index]}])
            else:
                end = len(value['help'])

                index_this_line = 0
                index_next_line = (len(value['help'])
                                   if max_help_len >= len(value['help'])
                                   else max_help_len)

                while index_this_line < end:
                    # Find the end of the line (stop at a space if the line
                    # is long).
                    if index_next_line >= end:
                        space = -1  # Don't go looking for a space
                    else:
                        space = value['help'].rfind(' ',
                                                    index_this_line,
                                                    index_next_line)
                    if space < 0:
                        string = value['help'][index_this_line:index_next_line]
                    else:
                        string = value['help'][index_this_line:space].rstrip()
                        index_next_line = space + 1

                    # Save up to end of the line
                    line_parts.append(string)

                    # Build the output string
                    output.append([{'text': ''.join(line_parts),
                                    'mode': colors[color_index]}])

                    # Ready for next loop
                    index_this_line = index_next_line
                    index_next_line += max_help_len
                    if index_next_line >= end:
                        index_next_line = end
                    line_parts = [' ' * help_indent]

        self._window_manager.display_window('The Command Ribbon, Explained',
                                            output)
        return True  # Keep doing whatever you were doing.


class AttributeWidget(object):
    '''
    GUI widget used to modify the attributes of a fighter.
    '''
    def __init__(self,
                 window_manager,    # GmWindowManager object for menus
                                    #   and error reporting
                 screen_handler,    # ScreenHandler object that encloses
                                    #   this widget
                 fighter            # Fighter object -- changing this
                                    #   guy's attributes
                 ):
        self.__window_manager = window_manager
        self.__fighter = fighter
        self.__screen_handler = screen_handler
        self.__ruleset = fighter.get_ruleset()

    def doit(self):
        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        starting_attribute = 0
        while keep_asking:
            perm_current_menu = [('current', 'current'),
                                 ('permanent', 'permanent')]
            attr_type, ignore = self.__window_manager.menu(
                    ('%s: Change What Type Of Attribute' %
                        self.__fighter.name), perm_current_menu)
            if attr_type is None:
                return None
            else:
                change_current = True if attr_type == 'current' else False

            attr_menu = [(attr, attr)
                         for attr in self.__fighter.details[attr_type].keys()]

            attr, starting_attribute = self.__window_manager.menu(
                    'Attr To Modify', attr_menu, starting_attribute)
            if attr is None:
                return None

            if change_current:
                title = ('New Value (old value: %d/%d)' %
                         (self.__fighter.details['current'][attr],
                          self.__fighter.details['permanent'][attr]))
            else:
                title = ('New Value (old value: %d)' %
                         self.__fighter.details['permanent'][attr])
            height = 1
            width = len(title) + 2
            keep_ask_attr = True

            new_attr_value = (
                    self.__window_manager.input_box_calc(
                        height,
                        width,
                        self.__fighter.details[attr_type][attr],
                        title))

            force_current = False
            if change_current:
                if (new_attr_value >
                        self.__fighter.details['permanent'][attr]):
                    cap_menu = [('yes', True), ('no', False)]
                    cap_current, ignore = self.__window_manager.menu(
                            'Cap the "current" Value to the "permanent" value',
                            cap_menu)
                    if cap_current:
                        new_attr_value = (
                                self.__fighter.details['permanent'][attr])
            else:
                both_menu = [('yes', True), ('no', False)]
                force_current, ignore = self.__window_manager.menu(
                        'Change "current" Value To Match ', both_menu)

            self.__ruleset.do_action(self.__fighter,
                           {'action-name': 'adjust-attribute',
                            'attr-type': attr_type,
                            'attribute': attr,
                            'new-value': new_attr_value},
                           None)
            if force_current:
                self.__ruleset.do_action(self.__fighter,
                               {'action-name': 'adjust-attribute',
                                'attr-type': 'current',
                                'attribute': attr,
                                'new-value': new_attr_value},
                               None)

            self.__screen_handler.draw_screen()
            keep_asking, ignore = self.__window_manager.menu(
                    'Change More Attributes', keep_asking_menu)
        return True


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
                 monster_group_name = None # name of monster group, None is OK
                 ):
        super(PersonnelHandler, self).__init__(window_manager, world)
        self._add_to_choice_dict({
            curses.KEY_HOME: {'name': 'scroll home',
                              'func': self.__first_page},
            curses.KEY_UP: {'name': 'prev creature',
                            'func': self.__view_prev},
            curses.KEY_DOWN: {'name': 'next creature',
                              'func': self.__view_next},
            curses.KEY_NPAGE: {'name': 'scroll down',
                               'func': self.__next_page,
                               'help': 'Scroll DOWN on the current pane ' +
                                       'which may may be either the ' +
                                       'character pane (on the left) or ' +
                                       'the details pane (on the right)'},
            curses.KEY_PPAGE: {'name': 'scroll up',
                               'func': self.__prev_page,
                               'help': 'Scroll UP on the current pane which ' +
                                       'may may be either the character ' +
                                       'pane (on the left) or the details ' +
                                       'pane (on the right)'},
            curses.KEY_LEFT: {'name': 'scroll char list',
                              'func': self.__left_pane,
                              'help': 'Choose the character pane (on the ' +
                                      'left) for scrolling.'},
            curses.KEY_RIGHT: {'name': 'scroll char detail',
                               'func': self.__right_pane,
                               'help': 'Choose the details pane (on the ' +
                                       'right) for scrolling.'},

            ord('a'): {'name': 'add creature',
                       'func': self.__add_creature,
                       'help': 'Add a creature to the current group.'},
            ord('c'): {'name': 'change creature',
                       'func': self.__change_creature,
                       'help': 'Modify the currently selected creature by ' +
                               'changing attributes, adding or removing' +
                               'equipment, or changing some other feature.'},
            ord('d'): {'name': 'delete creature',
                       'func': self.__delete_creature,
                       'help': 'Delete the currently selected creature ' +
                               'from the current group.'},
            ord('e'): {'name': 'equip creature',
                       'func': self.__equip,
                       'help': 'Modify the currently selected creature by ' +
                               'changing attributes, adding or removing' +
                               'equipment, or changing some other feature.'},
            ord('g'): {'name': 'create template group',
                       'func': self.__create_template_group,
                       'help': 'Make a new collection of templates (like ' +
                               'bad guys or space marines).'},
            ord('I'): {'name': 'Import character.',
                       'func': self.__import_creature,
                       'help': 'Import character into combat accountant.'},
            # TODO (now): ruleset-based
            ord('s'): {'name': 'list Spells',
                       'func': self.__list_spells,
                       'help': 'Display the list of available ' +
                               'spells.'},
            ord('t'): {'name': 'change template group',
                       'func': self.__change_template_group,
                       'help': 'Change the group of templates on which ' +
                               'you will base newly created creatures ' +
                               'going forward.'},
            ord('T'): {'name': 'make into template',
                       'func': self.__create_template,
                       'help': 'Convert the currently selected creature ' +
                               'into a template and add that template into ' +
                               'the currently selected template group.'},
            ord('U'): {'name': 'Update character.',
                       'func': self.__update_creature,
                       'help': 'Update character from .GCS file.'},
            ord('q'): {'name': 'quit',
                       'func': self.__quit,
                       'help': 'Quit changing personnel.'},
        })

        if creature_type == PersonnelHandler.NPCs:
            self._add_to_choice_dict({
                ord('p'): {'name': 'NPC joins PCs',
                           'func': self.NPC_joins_PCs,
                           'help': 'Make the currently selected NPC join ' +
                                   'the player characters.  The NPC will ' +
                                   'be listed in both groups but they will ' +
                                   'both refer to the same creature ' +
                                   '(changing one will change the other).'},
                ord('P'): {'name': 'NPC leaves PCs',
                           'func': self.__NPC_leaves_PCs,
                           'help': 'If the current NPC has joined the ' +
                                   'party, this will cause him/her to leave ' +
                                   'the party.'},
                ord('m'): {'name': 'NPC joins Monsters',
                           'func': self.NPC_joins_monsters,
                           'help': 'Make the currently selected NPC join ' +
                                   'one of the groups of monsters.  The NPC ' +
                                   'will ' +
                                   'be listed in both groups but they will ' +
                                   'both refer to the same creature ' +
                                   '(changing one will change the other).'},
            })

        self._window = self._window_manager.get_build_fight_gm_window(
                                                                self._choices)
        self.__current_pane = PersonnelHandler.CHAR_DETAIL

        # Name of templates we'll use to create new creatures.
        self.__template_group = None

        # The following is a dict of the Fighters/Venues in a group (PCs,
        # NPCs, or monster group) sorted by the the Fighters' names (with the
        # venue, if it exists, stuffed at the top).  The dict is:
        # {
        #   'data': array of dict found in the data file
        #   'obj':  array of Fighter/Venue object
        # }
        # NOTE: [data][n] is the same creature as [obj][n]
        self.__critters = None

        self.__deleted_critter_count = 0
        self.__equipment_manager = ca_equipment.EquipmentManager(
                self.world, window_manager)

        self.__new_char_name = None
        self.__viewing_index = None

        if creature_type == PersonnelHandler.NPCs:
            self.__group_name = 'NPCs'
            self.__existing_group(creature_type)
        elif creature_type == PersonnelHandler.PCs:
            self.__group_name = 'PCs'
            self.__existing_group(creature_type)
        else:  # creature_type == PersonnelHandler.MONSTERs:
            # This is the name of the monsters or 'PCs' that will ultimately
            # take these creatures.
            self.__group_name = monster_group_name
            new_existing = 'existing' # If group_name != None

            if self.__group_name is None:
                new_existing_menu = [('new monster group', 'new')]
                if len(self.world.get_fights()) > 0:
                    new_existing_menu.append(('existing monster group',
                                              'existing'))

                new_existing = None
                while new_existing is None:
                    new_existing, ignore = self._window_manager.menu(
                            'New or Pre-Existing', new_existing_menu)

            if new_existing == 'new':
                self.__new_group()
            else:
                self.__existing_group(creature_type,
                                      monster_group_name)

        self.__viewing_index = (0 if self.__critters_contains_critters()
                                else None)
        self._draw_screen()

        if not self.__critters_contains_critters():
            self.__add_creature()

        return

    #
    # Public Methods
    #

    def draw_screen(self):
        '''
        Draws the complete screen for the FightHandler.  This is here so a
        widget can redraw its parent's screen.

        Returns: nothing.
        '''
        self._draw_screen()

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
        fight_name, ignore = self._window_manager.menu('Join Which Fight',
                                                       fight_menu)

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
                     pane=None,  # CHAR_LIST, CHAR_DETAIL,
                                 #    CHAR_LIST|CHAR_DETAIL
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

    def __import_creature(self):
        '''
        Command ribbon method.

        Imports a character into this program.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # get the filename to import

        extension = self.world.ruleset.get_import_file_extension()
        filename_window = ca_gui.GetFilenameWindow(self._window_manager)
        filename = filename_window.get_filename(extension)
        if filename is None:
            return True

        # actually import the new creature

        name, creature = self.world.ruleset.import_creature_from_file(filename)
        if creature is None:
            return True

        # get the creature's name

        if name in self.__critters['data']:
            self._window_manager.error(
                    ['Creature with name "%s" already exists' % name])
            name = None

        if name is None:
            keep_going = True
            while keep_going:
                lines, cols = self._window.getmaxyx()
                name = self._window_manager.input_box(1,      # height
                                                      cols-4,  # width
                                                      'Creature Name')
                if name is None:
                    return True
                elif name in self.__critters['data']:
                    self._window_manager.error(
                            ['Creature with name "%s" already exists' % name])
                else:
                    keep_going = False

        # install in the current group

        self.__critters['data'][name] = creature
        self.__critters['obj'].append(self.world.get_creature(
                                                    name,
                                                    self.__group_name))
        self.__viewing_index = len(self.__critters['obj']) - 1


        self.__new_char_name = name
        self._window.show_creatures(self.__critters['obj'],
                                    self.__new_char_name,
                                    self.__viewing_index)
        return True

    def __left_pane(self):
        '''
        Command ribbon method.

        Changes the currently active pane to the left-hand one.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__current_pane = PersonnelHandler.CHAR_LIST
        return True

    def __list_spells(self):
        '''
        Command ribbon method.

        Displays the list of available spells.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        ca_gurps_ruleset.GurpsRuleset.show_spells(self._window_manager)
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

    def __update_creature(self):
        '''
        Command ribbon method.

        Imports a character into this program.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return True

        # get the filename from which to update

        need_file_message = None
        filename = None # Import from the character's internal filename
        if 'gcs-file' not in fighter.details:
            need_file_message = 'No file is associated with %s' % fighter.name
        elif not os.path.isfile(os.path.join(os.getcwd(),
                                fighter.details['gcs-file'])):
            need_file_message = 'File "%s" does not exist, pick a new one' % (
                    fighter.details['gcs-file'])

        if need_file_message is not None:
            self._window_manager.error('%s' % need_file_message)

            extension = self.world.ruleset.get_import_file_extension()
            filename_window = ca_gui.GetFilenameWindow(self._window_manager)
            filename = filename_window.get_filename(extension)
            if filename is None:
                return True

        # actually import the new creature

        changes = self.world.ruleset.update_creature_from_file(fighter.details,
                                                               filename)
        changes_with_modes = [
                [{'text': x, 'mode': curses.A_NORMAL}] for x in changes ]

        # new_list = [expression(i) for i in old_list if filter(i)]

        self._window_manager.display_window(
                ('Changes made to %s' % fighter.name), changes_with_modes)

        #        'Bug Reported',
        #        [[{'text': ('Output file "%s"' % bug_report_game_file),
        #           'mode': curses.A_NORMAL}]])

        self._window.show_creatures(self.__critters['obj'],
                                    fighter.name,
                                    self.__viewing_index)
        return True

    #
    # Other methods
    #
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
            return True  # Keep going

        # Add as many creatures as we want

        keep_adding_creatures = True
        while keep_adding_creatures:
            new_creature = self.__make_creature_from_template()
            if new_creature is None:
                keep_adding_creatures = False
                break

            creature_name = self.__get_name_for_creature(new_creature)

            if self.__group_name != 'PCs':
                self.__get_personality(new_creature)

            creature_name, keep_adding_creatures = self.__modify_new_creature(
                    creature_name, new_creature)

            # Add our new creature to its group and show it to the world.

            self.__critters['data'][creature_name] = new_creature
            self.__critters['obj'].append(self.world.get_creature(
                                                        creature_name,
                                                        self.__group_name))
            self.__viewing_index = len(self.__critters['obj']) - 1
            # PersonnelGmWindow
            self._window.show_creatures(self.__critters['obj'],
                                        self.__new_char_name,
                                        self.__viewing_index)

        return True  # Keep going

    def __add_equipment_from_store(
            self,
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
        starting_index = 0
        while keep_asking:
            # |starting_index| is the index into the store's list.  Allows
            #   multiple iterations to start in the list at the last selection
            #   from the list.

            # NOTE: I keep having to look this up, so here it is:
            # here ->
            #   PersonnelHandler::__add_equipment_from_store (this func) ->
            #   EquipmentManager::add_equipment_from_store ->
            #   Fighter::add_equipment ->
            #   Equipment::add
            starting_index = self.__equipment_manager.add_equipment_from_store(
                    fighter, starting_index)
            self._draw_screen()
            keep_asking, ignore = self._window_manager.menu(
                    'Add More Equipment', keep_asking_menu)
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
        current_selection = 0
        while keep_asking:
            new_spell_name, current_selection = self._window_manager.menu(
                    'Spell to Add', spell_menu, current_selection)
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
                    skill = self._window_manager.input_box_number(
                            height, width, title)
                    if skill is not None:
                        my_copy['skill'] = skill
                        keep_ask_skill = False
                    else:
                        self._window_manager.error(
                                                ['You must specify a skill'])

                fighter.details['spells'].append(my_copy)
                self._draw_screen()

            keep_asking, ignore = self._window_manager.menu('Add More Spells',
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

        # self.world.ruleset...
        timers_widget = ca_timers.TimersWidget(fighter.timers,
                                               self._window_manager)

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            timers_widget.make_timer(fighter.name)
            self._draw_screen()
            keep_asking, ignore = self._window_manager.menu('Add More Timers',
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

        attribute_widget = AttributeWidget(self._window_manager,
                                           self,
                                           fighter)
        return attribute_widget.doit()

    def __change_consciousness(self,
                               throw_away   # Required/used by the caller
                                            #   because there's a list of
                                            #   methods to call, and
                                            #   (apparently) some of them may
                                            #   use this parameter.  It's
                                            #   ignored by this method,
                                            #   however.
                               ):
        '''
        Handler for a change consciousness sub-menu entry.

        Provides a way for a Fighter change his/her level of consciousness

        Returns: None if we want to bail-out of the change consciousness
                 process, True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        state_menu = sorted(ca_fighter.Fighter.conscious_map.iteritems(),
                            key=lambda x: x[1])
        new_state_number, ignore = self._window_manager.menu('New State',
                                                             state_menu)
        if new_state_number is None:
            return None

        self.world.ruleset.do_action(
                fighter,
                {
                    'action-name': 'set-consciousness',
                    'level': new_state_number,
                    'comment': '(%s) is now (%s)' % (
                        fighter.name,
                        ca_fighter.Fighter.get_name_from_state_number(
                                                            new_state_number))
                },
                self)

        self._draw_screen()
        return True  # anything but 'None' for a successful menu handler

    def __change_creature(self):
        '''
        Command ribbon method.

        Provides a sub-menu for different ways to augment a Fighter

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return True

        sub_menu = []
        sub_menu.extend([
            ('attributes (change)', {'doit': self.__change_attributes}),
            ('change consciousness',
                {'doit': self.__change_consciousness}),
        ])

        self.__ruleset_abilities = self.world.ruleset.get_creature_abilities()
        for ability in self.__ruleset_abilities:
            if ability in fighter.details:
                sub_menu.extend([
                    ('%s (add)' % ability,
                        {'doit': self.__ruleset_ability,
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

        if 'fight-notes' in fighter.details:
            sub_menu.extend([
                ('notes (fight)',   {'doit': self.__fight_notes})
            ])

        if 'notes' in fighter.details:
            sub_menu.extend([
                ('Notes',           {'doit': self.__full_notes})
            ])

        self._window_manager.menu('Do what', sub_menu)

        # Do a consistency check once you're done equipping
        self.world.ruleset.is_creature_consistent(fighter.name,
                                                  fighter.details)

        self._window.touchwin()
        self._window.refresh()
        return True  # Keep going

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
        template_group, ignore = self._window_manager.menu(
                'Which Template Group', template_menu)
        if template_group is None:
            return True  # Keep going
        self.__template_group = template_group

        # Display our new state

        self._draw_screen()

        return True  # Keep going

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

        self._window.char_detail_home()

    def __container_close(
                    self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                    ):
        '''
        Method for 'equip' sub-menu.

        Closes the top container in the container stack.

        Returns: None if we want to bail-out, True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        self.world.ruleset.do_action(
                fighter,
                {'action-name': 'close-container'},
                None)
        self._draw_screen()
        return True  # anything but 'None' for a menu handler

    def __container_move_to(
                    self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                    ):
        '''
        Method for 'equip' sub-menu.

        Moves an item at the current level of the conatiner stack to a
        sub-container

        Returns: None if we want to bail-out, True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        container_stack = fighter.details['open-container']
        container = fighter.equipment.get_container(container_stack)
        containers = fighter.equipment.get_container_list(container)

        # Build the menu - move which item

        move_item_menu = []
        for index, item in enumerate(container):
            move_item_menu.append((item['name'], index))
        move_item_menu = sorted(move_item_menu, key=lambda x: x[0].upper())

        # Get the index

        item_index, ignore = self._window_manager.menu('Move Which Item',
                                                       move_item_menu)
        if item_index is None:
            return None
        item = container[item_index]

        # Build the menu - move to which container

        open_container_menu = []
        for index, item_name in containers:
            open_container_menu.append((item_name, index))
        open_container_menu = sorted(open_container_menu,
                                     key=lambda x: x[0].upper())

        # Get the index

        container_index, ignore = self._window_manager.menu(
                'To Which Container', open_container_menu)
        if container_index is None:
            return None

        # Move item INTO container & FROM container

        self.world.ruleset.do_action(
                fighter,
                {'action-name': 'move-between-container',
                 'item-index': item_index,
                 'item-name': item['name'],
                 'destination-index': container_stack + [container_index],
                 },
                None)
        self._draw_screen()
        return True  # anything but 'None' for a menu handler

    def __container_move_to_top_level(
                    self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                    ):
        '''
        Method for 'equip' sub-menu.

        Moves an item to the top-level of the container stack

        Returns: None if we want to bail-out, True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        container_stack = fighter.details['open-container']
        if len(container_stack) == 0:
            return None
        container = fighter.equipment.get_container(container_stack)

        # Build the menu - move which item

        move_item_menu = []
        for index, item in enumerate(container):
            move_item_menu.append((item['name'], index))
        move_item_menu = sorted(move_item_menu, key=lambda x: x[0].upper())

        # Get the index

        item_index, ignore = self._window_manager.menu('Move Which Item',
                                                       move_item_menu)
        if item_index is None:
            return None
        item = container[item_index]

        # Move item INTO container & FROM container

        self.world.ruleset.do_action(
                fighter,
                {'action-name': 'move-between-container',
                 'item-index': item_index,
                 'item-name': item['name'],
                 'destination-index': [],
                 },
                None)
        self._draw_screen()
        return True  # anything but 'None' for a menu handler

    def __container_open(
                    self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                    ):
        '''
        Method for 'equip' sub-menu.

        Opens a container that's at the current level

        Returns: None if we want to bail-out of the doff armor process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        container_stack = fighter.details['open-container']
        container = fighter.equipment.get_container(container_stack)
        containers = fighter.equipment.get_container_list(container)

        # Build the menu

        open_container_menu = []
        for index, item_name in containers:
            open_container_menu.append((item_name, index))
        open_container_menu = sorted(open_container_menu,
                                     key=lambda x: x[0].upper())

        # Get the index

        container_index, ignore = self._window_manager.menu(
                'Open Which Container', open_container_menu)
        if container_index is None:
            return None

        # Open the container

        self.world.ruleset.do_action(
                fighter,
                {'action-name': 'open-container',
                 'container-index': container_index
                },
                None)
        self._draw_screen()
        return True  # anything but 'None' for a menu handler

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
            return True  # Keep going

        if self.__viewing_index is None:
            return True  # Keep going

        from_creature = self.get_obj_from_index()
        if from_creature.name == ca_fighter.Venue.name:
            self._window_manager.error(['Can\'t make a template from a room'])
            return True  # Keep going

        # Get the name of the new template

        lines, cols = self._window.getmaxyx()
        keep_asking = True
        while keep_asking:
            template_name = self._window_manager.input_box(1,       # height
                                                           cols-4,  # width
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
                pass  # We're ignoring these

        template_list = self.world.details['templates'][self.__template_group]
        template_list[template_name] = to_creature
        return True  # Keep going

    def __create_template_group(self):
        '''
        Command ribbon method.

        Creates a new template group and changes to that group.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        lines, cols = self._window.getmaxyx()
        keep_asking = True
        while keep_asking:
            template_group = self._window_manager.input_box(
                    1,      # height
                    cols-4,  # width
                    'New Template Group Name')
            if template_group is None or len(template_group) <= 0:
                return True
            elif template_group in self.world.details['templates']:
                self._window_manager.error(
                    ['Template group name "%s" already exists' %
                        template_group])
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
        Returns True if any creature in the self.__critters array is a
        monster, NPC, or PC.  Returns False, otherwise.
        '''
        if self.__critters is None:
            return False
        for critter in self.__critters['obj']:
            if critter.name != ca_fighter.Venue.name:
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
        answer, ignore = self._window_manager.menu(
                'Delete "%s" ARE YOU SURE?' % name_to_delete,
                critter_menu,
                1)  # Choose 'No' by default

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

        return True  # Keep going

    def __doff_armor(self,
                    throw_away   # Required/used by the caller because
                                 #   there's a list of methods to call,
                                 #   and (apparently) some of them may
                                 #   use this parameter.  It's ignored
                                 #   by this method, however.
                    ):
        '''
        Method for 'equip' sub-menu.

        Asks the user which armor the Fighter should wear and puts it on.

        Returns: None if we want to bail-out of the doff armor process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        # Are we even wearing armor?
        armor_index_list = fighter.get_current_armor_indexes()
        if len(armor_index_list) == 0:
            return None

        # Build the menu
        armor_list = fighter.get_items_from_indexes(armor_index_list)
        doff_armor_menu = []
        for item, item_index in zip(armor_list, armor_index_list):
            doff_armor_menu.append((item['name'], item_index))
        doff_armor_menu = sorted(doff_armor_menu, key=lambda x: x[0].upper())

        # Get the index
        if len(doff_armor_menu) == 0:
            return None
        elif len(doff_armor_menu) == 1:
            armor_index = doff_armor_menu[0][1]
        else:
            armor_index, ignore = self._window_manager.menu(
                    'Doff Which Armor', doff_armor_menu)
            if armor_index is None:
                return None

        # Doff the armor
        self.world.ruleset.do_action(
                fighter,
                {'action-name': 'doff-armor',
                 'armor-index': armor_index,
                 'notimer': True},
                None)
        self._draw_screen()
        return True  # anything but 'None' for a menu handler

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

        armor_index_list = fighter.get_current_armor_indexes()
        armor_list = fighter.get_items_from_indexes(armor_index_list)
        don_armor_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if 'armor' in item['type']:
                if index not in armor_index_list:
                    don_armor_menu.append((item['name'], index))
        don_armor_menu = sorted(don_armor_menu, key=lambda x: x[0].upper())
        armor_index = None
        if len(don_armor_menu) == 0:
            return None
        elif len(don_armor_menu) == 1:
            armor_index = don_armor_menu[0][1]
        else:
            armor_index, ignore = self._window_manager.menu(
                    'Don Which Armor', don_armor_menu)
            if armor_index is None:
                return None

        self.world.ruleset.do_action(
                fighter,
                {'action-name': 'don-armor',
                 'armor-index': armor_index,
                 'notimer': True},
                None)
        self._draw_screen()
        return True  # anything but 'None' for a menu handler

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

        weapon_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if ca_equipment.Weapon.is_weapon(item):
                weapon_menu.append((item['name'], index))
        weapon_menu = sorted(weapon_menu, key=lambda x: x[0].upper())

        weapon_index, ignore = self._window_manager.menu(
                'Draw Which Weapon', weapon_menu)
        if weapon_index is None:
            return None

        self.world.ruleset.do_action(fighter,
                                     {'action-name': 'draw-weapon',
                                      'weapon-index': weapon_index,
                                      'notimer': True},
                                     None)

        self._draw_screen()
        return True  # Anything but 'None' for a menu handler

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
                ('equipment (add)',     {'doit':
                    self.__add_equipment_from_store}),
                ('Equipment (remove)',  {'doit': self.__remove_equipment}),
                ('give equipment',      {'doit': self.__give_equipment}),
                ('identify equipment',  {'doit': self.__identify_equipment}),
                ('Ignore equipment',    {'doit': self.__ignore_equipment}),
            ])

        owns_weapon = False
        owns_armor = False
        for item in fighter.details['stuff']:
            if ca_equipment.Weapon.is_weapon(item):
                owns_weapon = True
            if 'armor' in item['type']:
                owns_armor = True

        if 'armor-index' in fighter.details:
            if owns_armor:
                sub_menu.extend([
                    ('Don armor',  {'doit': self.__don_armor}),
                    ('Prefer armor',       {'doit': self.__prefer_armor})
                ])
            armor_indexes = fighter.get_current_armor_indexes()
            if len(armor_indexes) > 0:
                sub_menu.extend([
                    ('Doff armor',  {'doit': self.__doff_armor})
                ])

        if 'weapon-index' in fighter.details:
            if owns_weapon:
                sub_menu.extend([
                    ('draw weapon',     {'doit': self.__draw_weapon}),
                    ('holster weapon',  {'doit': self.__holster_weapon}),
                    ('prefer weapon',   {'doit': self.__prefer_weapon}),
                ])

            weapons = fighter.get_current_weapons()
            found_ranged_weapon = False
            for weapon in weapons:
                if weapon is None:
                    continue
                if 'ranged weapon' in weapon.details['type']:
                    found_ranged_weapon = True

            if found_ranged_weapon:
                sub_menu.extend([
                    ('reload weapon',    {'doit': self.__reload_weapon})
                ])

        # Container Stuff

        container_stack = fighter.details['open-container']
        container = fighter.equipment.get_container(container_stack)
        containers = fighter.equipment.get_container_list(container)

        if len(containers) > 0:
            sub_menu.extend([
                ('open container',      {'doit': self.__container_open}),
                ('move to container',   {'doit': self.__container_move_to}),
            ])
        if len(container_stack) > 0:
            sub_menu.extend([
                ('move to top level',   {'doit': self.__container_move_to_top_level}),
                ('close container',     {'doit': self.__container_close}),
            ])

        sub_menu.sort(key=lambda x: x[0].lower())

        # Menu

        self._window_manager.menu('Do what', sub_menu)

        # Do a consistency check once you're done equipping
        self.world.ruleset.is_creature_consistent(fighter.name,
                                                  fighter.details)

        self._window.touchwin()
        self._window.refresh()
        return True  # Keep going

    def __existing_group(self,
                         creature_type,  # PersonnelHandler.NPCs, ...
                         monster_group_name = None # name of monster group
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
            if monster_group_name is not None:
                group_answer = monster_group_name
            else:
                group_menu = [(group_name, group_name)
                              for group_name in self.world.get_fights()]
                group_menu = sorted(group_menu, key=lambda x: x[0].upper())
                group_answer, ignore = self._window_manager.menu(
                        'To Which Group', group_menu)

        elif creature_type == PersonnelHandler.NPCs:
            group_answer = 'NPCs'

        elif creature_type == PersonnelHandler.PCs:
            group_answer = 'PCs'

        if group_answer is None:
            return True  # Keep going

        # Set the name and group of the new group

        self.__group_name = group_answer
        self.__critters = {
                'data': self.world.get_creature_details_list(
                    self.__group_name),
                'obj': []}

        # Build the Fighter object array

        the_fight_itself = None
        for name, details in self.__critters['data'].iteritems():
            if name == ca_fighter.Venue.name:
                the_fight_itself = details
            else:
                fighter = self.world.get_creature(name, self.__group_name)
                self.__critters['obj'].append(fighter)

        self.__critters['obj'] = sorted(self.__critters['obj'],
                                        key=lambda x: x.name)

        # Add the Venue to the object array (but only for monsters).

        if creature_type == PersonnelHandler.MONSTERs:
            if the_fight_itself is None:
                self.__critters['data'][
                        ca_fighter.Venue.name] = ca_fighter.Venue.empty_venue
                group = self.world.details['fights'][self.__group_name]
                fight = ca_fighter.Venue(
                        self.__group_name,
                        group['monsters'][ca_fighter.Venue.name],
                        self.world.ruleset,
                        self._window_manager)
            else:
                fight = ca_fighter.Venue(self.__group_name,
                                         the_fight_itself,
                                         self.world.ruleset,
                                         self._window_manager)

            self.__critters['obj'].insert(0, fight)

        # Display our new state

        self._draw_screen()

        return True  # Keep going

    def __fight_notes(self,
                      throw_away    # Required/used by the caller because
                                    #   there's a list of methods to call,
                                    #   and (apparently) some of them may use
                                    #   this parameter.  It's ignored by this
                                    #   method, however.
                      ):
        '''
        Handler for an Equip sub-menu entry.

        Lets the user edit a fighter's (or Venue's) fight notes.

        Returns: None
        '''
        return self.__notes('fight-notes')

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
                                       name  # string name of critter
                                       ):
        '''
        Returns Fighter object given the name of the fighter.
        '''
        for critter in self.__critters['obj']:
            if critter.name == name:
                return critter
        return None

    def __get_name_for_creature(self,
                                new_creature    # dict for creature
                                ):
        '''
        Gets a new name for the passed-in creature.

        Returns creature's name.
        '''

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
        creature_num = (previous_creature_count + self.__deleted_critter_count)
        keep_asking = True
        creature_name = '** Anonymous **'  # Shouldn't need this
        while keep_asking:
            base_name = self._window_manager.input_box(1,      # height
                                                       cols-4,  # width
                                                       'Monster Name')
            if base_name is None or len(base_name) == 0:
                base_name, where, gender = self.world.get_random_name()
                if base_name is None:
                    self._window_manager.error(['Monster needs a name'])
                    keep_asking = True
                    continue
                else:
                    if where is not None:
                        new_creature['notes'].append('origin: %s' % where)
                    if gender is not None:
                        new_creature['notes'].append('gender: %s' % gender)

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

        return creature_name

    def __get_personality(self,
                          new_creature  # dict containing creature
                          ):
        '''
        Generates a random personality for the creature.  Adds that description
        to the creature's notes.

        Returns nothing
        '''
        with ca_json.GmJson('gm-npc-random-detail.json') as npc_detail:
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

                new_creature['notes'].append('%s: %s' % (name, trait))

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

        # TODO (eventually, maybe):
        #   {'type': 'ask-string', 'value': x}
        #   {'type': 'ask-numeric', 'value': x}
        #   {'type': 'ask-logical', 'value': x}
        #   {'type': 'dice', 'value': 'ndm+x'}
        #   {'type': 'derived', 'value': comlicated stuff -- eventually}

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

        # Get the object from the viewing index
        from_fighter = self.get_obj_from_index()
        if from_fighter is None:
            return None

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        to_whom = 0
        while keep_asking:
            item_index = self.__equipment_manager.select_item_index(from_fighter)
            if item_index is None:
                return None
            count = from_fighter.ask_how_many(item_index)
            item = from_fighter.details['stuff'][item_index]

            character_list = self.world.get_creature_details_list('PCs')
            character_menu = [(dude, dude) for dude in character_list]
            to_fighter_info, to_whom = self._window_manager.menu(
                    'Give "%s" to whom?' % item['name'],
                    character_menu,
                    to_whom)

            # NOTE: Can't use an action for give-equipment, here, because
            # we're not in a fight and the action needs a fight_handler to
            # get the Fighter object from the recipient name.  We could,
            # alternatively use the 'World' but the ruleset shouldn't need
            # to know about the World, either.

            # TODO (now): not just to PCs, allow transfer to NPCs

            to_fighter = self.world.get_creature(to_fighter_info, 'PCs')
            item = self.__equipment_manager.remove_equipment_by_index(
                    from_fighter, item_index, count)
            if from_fighter.group == 'PCs':
                source = from_fighter.detailed_name
            else:
                source = '%s:%s' % (from_fighter.group,
                                    from_fighter.detailed_name)
            ignore = to_fighter.add_equipment(item, source)
            self._draw_screen()

            keep_asking, ignore = self._window_manager.menu(
                    'Give More Equipment', keep_asking_menu)

        return True  # anything but 'None' for a successful menu handler

    def __holster_weapon(self,
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

        # The following two lists are guaranteed to be in the same order
        weapons = fighter.get_current_weapons()
        weapon_indexes = fighter.get_current_weapon_indexes()
        weapon_menu = []
        for weapon, index in zip(weapons, weapon_indexes):
            if weapon is None:
                continue
            weapon_menu.append((weapon.name, index))
        weapon_index, ignore = self._window_manager.menu(
                'Holster Which Weapon', weapon_menu)
        if weapon_index is not None:
            self.world.ruleset.do_action(
                    fighter,
                    {'action-name': 'holster-weapon',
                     'weapon-index': weapon_index,
                     'notimer': True},
                    None)

        self._draw_screen()
        return True  # Anything but 'None' for a menu handler

    def __identify_equipment(self,
                             throw_away   # Required/used by the caller because
                                          #   there's a list of methods to call,
                                          #   and (apparently) some of them may
                                          #   use this parameter.  It's ignored
                                          #   by this method, however.
                             ):
        '''
        Handler for an Equip sub-menu entry.

        Provides a way for a Fighter to identify a previously unidentified
        item.

        Returns: None if we want to bail-out of the give equipment process,
                 True, otherwise
        '''

        # Get the object from the viewing index
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            item_index = self.__equipment_manager.select_item_index(fighter)
            if item_index is None:
                return None
            item = fighter.details['stuff'][item_index]
            item['identified'] = True

            # provenance?
            destroy_provenance, ignore = self._window_manager.menu(
                    'Remove the previous owners list?', keep_asking_menu)
            if destroy_provenance:
                item['owners'] = None
                fighter.equipment.mother_up_item(item_index)

            self._draw_screen()

            keep_asking, ignore = self._window_manager.menu(
                    'Identify More Equipment', keep_asking_menu)

        return True  # anything but 'None' for a successful menu handler

    def __ignore_equipment(self,
                           throw_away   # Required/used by the caller because
                                        #   there's a list of methods to call,
                                        #   and (apparently) some of them may
                                        #   use this parameter.  It's ignored
                                        #   by this method, however.
                           ):
        '''
        Handler for an Equip sub-menu entry.

        Removes a piece of equipment from the list and keeps it from showing
        up again.

        Returns: None if we want to bail-out of the give equipment process,
                 True, otherwise
        '''

        # Get the object from the viewing index
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        if 'ignored-equipment' not in fighter.details:
            fighter.details['ignored-equipment'] = []

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            item = self.__equipment_manager.remove_equipment(fighter)
            self._draw_screen()
            if item is None or len(fighter.details['stuff']) == 0:
                return True

            fighter.details['ignored-equipment'].append(item['name'].lower())

            keep_asking, ignore = self._window_manager.menu(
                    'Ignore More Equipment', keep_asking_menu)

        return True  # anything but 'None' for a successful menu handler

    def __make_creature_from_template(self):
        '''
        Gets a template for the creature currently being added to the current
        group.

        Returns: dict containing creature generated
        '''
        if self.__template_group is None:
            self.__change_template_group()

        # Based on which creature from the template

        empty_creature = 'Blank Template'
        from_creature_name = empty_creature

        # None means there are no templates or the user decided against
        # a template.

        monster_index = 0
        if self.__template_group is not None:
            creature_menu = []
            for from_creature_name in (
                        self.world.details['templates'][
                            self.__template_group]):
                if from_creature_name == empty_creature:
                    self._window_manager.error(
                            ['Template group "%s" contains bad template:' %
                                self.__template_group,
                             '"%s". Replacing with an empty creature.' %
                                empty_creature])
                else:
                    creature_menu.append((from_creature_name,
                                          from_creature_name))

            creature_menu = sorted(creature_menu, key=lambda x: x[0].upper())
            creature_menu.append((empty_creature, empty_creature))

            from_creature_name, monster_index = self._window_manager.menu(
                    'Monster', creature_menu, monster_index)
            if from_creature_name is None:
                return None

        # Generate the creature for the template

        to_creature = self.world.ruleset.make_empty_creature()

        if from_creature_name != empty_creature:
            from_creature = (self.world.details['templates'][
                             self.__template_group][from_creature_name])
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

        return to_creature


    def __modify_new_creature(self,
                              creature_name,    # string: new creature's name
                              new_creature      # dict containing creature
                              ):
        '''
        Allows the user to modify a created creature. Potentially modifies
        new_creature

        Returns: tuple: (new_creature_name,
                         True to keep adding creatures/False otherwise)
        '''
        keep_changing_this_creature = True
        keep_adding_creatures = True
        lines, cols = self._window.getmaxyx()
        while keep_changing_this_creature:
            # Creating a temporary list to show.  Add the new creature by its
            # current creature name and allow the name to be modified.  Once
            # the creature name is sorted, we can add it to the permanent list.
            # That simplifies the cleanup (since the lists are dictionaries,
            # indexed by creature name).

            # Note: we're not going to touch the objects in temp_list so it's
            # OK that this is just copying references.

            if self.__critters is None:
                temp_list = []
            else:
                temp_list = [x for x in self.__critters['obj']]
            temp_list.append(ca_fighter.Fighter(creature_name,
                                                self.__group_name,
                                                new_creature,
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

            starting_index = 2 # Start on 'continue'
            action, ignore = self._window_manager.menu('What Next',
                                                       action_menu,
                                                       starting_index)
            if action == 'append':
                more_text = self._window_manager.input_box(1,       # ht
                                                           cols-4,  # width
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
                if 'notes' not in new_creature:
                    notes = None
                else:
                    notes = '\n'.join(new_creature['notes'])
                notes = self._window_manager.edit_window(
                            lines - 4,
                            cols/2,
                            notes,  # initial string (w/ \n) for the window
                            'Notes',
                            '^G to exit')
                new_creature['notes'] = [x for x in notes.split('\n')]

            elif action == 'continue':
                keep_changing_this_creature = False

            elif action == 'quit':
                keep_changing_this_creature = False
                keep_adding_creatures = False

        return creature_name, keep_adding_creatures

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
            group_name = self._window_manager.input_box(1,       # height
                                                        cols-4,  # width
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
        fights = self.world.get_fights()  # New groups can only be in fights.

        fights[group_name] = {'monsters': {}}

        self.__critters = {'data': fights[group_name]['monsters'],
                           'obj': []}

        self.__critters['data'][
                        ca_fighter.Venue.name] = ca_fighter.Venue.empty_venue
        fight = ca_fighter.Venue(group_name,
                                 fights[group_name]['monsters'][
                                                    ca_fighter.Venue.name],
                                 self.world.ruleset,
                                 self._window_manager)
        self.__critters['obj'].insert(0, fight)

        # Display our new state

        self._draw_screen()

        return True  # Keep going

    def __notes(self,
                notes_type  # 'fight-notes' or 'notes'
                ):
        '''
        Command ribbon method.

        Allows the user to modify a Fighter's notes or fight-notes.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        notes_recipient = self.get_obj_from_index()
        if notes_recipient is None:
            return True  # Keep fighting

        # Now, get the notes for that person
        lines, cols = self._window.getmaxyx()

        if notes_type not in notes_recipient.details:
            notes = None
        else:
            notes = '\n'.join(notes_recipient.details[notes_type])

        notes = self._window_manager.edit_window(
                    lines - 4,
                    cols - 4,
                    notes,  # initial string (w/ \n) for the window
                    'Notes',
                    '^G to exit')

        notes_recipient.details[notes_type] = [x for x in notes.split('\n')]

        # Display our new state

        self._draw_screen()

        return True  # Keep going

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

    def __prefer_armor(self,
                       throw_away   # Required/used by the caller because
                                    #   there's a list of methods to call,
                                    #   and (apparently) some of them may
                                    #   use this parameter.  It's ignored
                                    #   by this method, however.
                       ):
        '''
        Method for 'equip' sub-menu.

        Asks the user which armor to prefer and prefers it.

        Returns: None if we want to bail-out of the favor prefer process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        # Select the armor to prefer
        armor_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if 'armor' in item['type']:
                preferred_string = (' (preferred)'
                        if index in fighter.details['preferred-armor-index']
                        else '')
                armor_menu.append(('%s%s' % (item['name'], preferred_string),
                                    index))
        armor_menu = sorted(armor_menu, key=lambda x: x[0].upper())
        if len(armor_menu) == 1:
            armor_index = armor_menu[0][1]
        else:
            armor_index, ignore = self._window_manager.menu(
                    'Toggle Preference For Which Armor', armor_menu)
            if armor_index is None:
                return None

        # Prefer (or unprefer) the selected armor
        if armor_index in fighter.details['preferred-armor-index']:
            fighter.details['preferred-armor-index'].remove(armor_index)
        else:
            fighter.details['preferred-armor-index'].append(armor_index)

        self._draw_screen()
        return True  # Anything but 'None' for a menu handler

    def __prefer_weapon(self,
                        throw_away   # Required/used by the caller because
                                     #   there's a list of methods to call,
                                     #   and (apparently) some of them may
                                     #   use this parameter.  It's ignored
                                     #   by this method, however.
                        ):
        '''
        Method for 'equip' sub-menu.

        Asks the user which weapon to prefer and prefers it.

        Returns: None if we want to bail-out of the prefer weapon process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        # Select the weapon to prefer
        weapon_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if ca_equipment.Weapon.is_weapon(item):
                preferred_string = (' (preferred)'
                        if (index in fighter.details['preferred-weapon-index'])
                        else '')
                weapon_menu.append(('%s%s' % (item['name'], preferred_string),
                                    index))
        weapon_menu = sorted(weapon_menu, key=lambda x: x[0].upper())
        if len(weapon_menu) == 1:
            weapon_index = weapon_menu[0][1]
        else:
            weapon_index, ignore = self._window_manager.menu(
                    'Toggle Preference For Which Weapon', weapon_menu)
            if weapon_index is None:
                return None

        # Prefer (or unprefer) the selected weapon
        if weapon_index in fighter.details['preferred-weapon-index']:
            fighter.details['preferred-weapon-index'].remove(weapon_indx)
        else:
            fighter.details['preferred-weapon-index'].append(weapon_index)

        self._draw_screen()
        return True  # Anything but 'None' for a menu handler

    def __quit(self):
        '''
        Command ribbon method.

        Quits out of the PersonnelHandler.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__critters is not None:
            for name, creature in self.__critters['data'].iteritems():
                self.world.ruleset.is_creature_consistent(name, creature)

        # TODO (eventually): do I need to del self._window?
        self._window.close()
        return False  # Stop building this fight

    def __reload_weapon(self,
                        throw_away   # Required/used by the caller because
                                     #   there's a list of methods to call,
                                     #   and (apparently) some of them may
                                     #   use this parameter.  It's ignored
                                     #   by this method, however.
                        ):
        '''
        Method for 'equip' sub-menu.

        Reloads the current weapon.

        Returns: None if we want to bail-out of the draw weapon process,
                 True, otherwise
        '''
        fighter = self.get_obj_from_index()
        if fighter is None:
            return None

        self.world.ruleset.do_action(
                fighter,
                {'action-name': 'reload',
                 'comment': 'Reloading during personnel mods',
                 'notimer': True,
                 'quiet': True},
                None)
        self._draw_screen()
        return True  # Anything but 'None' for a menu handler

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

        keep_asking_menu = [('yes', True), ('no', False)]
        keep_asking = True
        while keep_asking:
            item = self.__equipment_manager.remove_equipment(fighter)
            self._draw_screen()
            if item is None or len(fighter.details['stuff']) == 0:
                return True

            keep_asking, ignore = self._window_manager.menu(
                    'Remove More Equipment', keep_asking_menu)
        return True  # Menu handler's success returns anything but 'None'

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
        current_selection = 0
        while keep_asking:
            # Make the spell list again (since we've removed one)
            spell_menu = [(spell['name'], spell['name'])
                          for spell in sorted(fighter.details['spells'],
                          key=lambda x:x['name'])]
            bad_spell_name, current_selection = self._window_manager.menu(
                    'Spell to Remove', spell_menu, current_selection)

            if bad_spell_name is None:
                return None

            for index, spell in enumerate(fighter.details['spells']):
                if spell['name'] == bad_spell_name:
                    del fighter.details['spells'][index]
                    self._draw_screen()
                    break

            keep_asking, ignore = self._window_manager.menu(
                    'Remove More Spells', keep_asking_menu)
        return True  # Menu handler's success returns anything but 'None'

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
        #       'Skills':     {'Axe/Mace': 8,      'Climbing': 8,},
        #       'Advantages': {'Bad Tempter': -10, 'Nosy': -1,},
        #   }

        ability_menu = [(name, {'name': name, 'predicate': predicate})
                        for name, predicate in
                        self.__ruleset_abilities[param].iteritems()]

        keep_asking_menu = [('yes', True), ('no', False)]

        keep_asking = True
        current_selection = 0
        while keep_asking:
            new_ability, current_selection = self._window_manager.menu(
                    ('Adding %s' % param),
                    sorted(ability_menu),
                    current_selection)
            if new_ability is None:
                return None

            # The predicate will take one of several forms...
            # 'name': {'ask': 'number' | 'string' }
            #         {'value': value}

            result = None
            if 'ask' in new_ability['predicate']:
                if new_ability['predicate']['ask'] == 'number':
                    title = 'Value for %s' % new_ability['name']
                    width = len(title) + 2  # Margin to make it prettier
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

            keep_asking, ignore = self._window_manager.menu(
                    ('Add More %s' % param), keep_asking_menu)

        return True  # Menu handler's success returns anything but 'None'

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
        current_selection = 0
        while keep_asking:
            # Make the ability list again (since we've removed one)
            ability_menu = [(ability, ability)
                            for ability in
                            sorted(fighter.details[param].keys())]
            if len(fighter.details[param]) == 0:
                bad_ability_name = None
            else:
                bad_ability_name, current_selection = self._window_manager.menu(
                        '%s to Remove' % param.capitalize(),
                        ability_menu,
                        current_selection)

            if bad_ability_name is None:
                return None

            del fighter.details[param][bad_ability_name]
            self._draw_screen()

            if len(fighter.details[param]) == 0:
                return True

            keep_asking, ignore = self._window_manager.menu(
                    'Remove More %s' % param.capitalize(), keep_asking_menu)
        return True  # Menu handler's success returns anything but 'None'

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
        index, ignore = self._window_manager.menu('Remove Which Timer',
                                                  timer_menu)
        if index is None:
            return None

        # Delete the timer

        timer_recipient.timers.remove_timer_by_index(index)

        self._draw_screen()

        return True  # Menu handler's success returns anything but 'None'

    def __view_next(self):  # look at next character
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
        return True  # Keep going

    def __view_prev(self):  # look at previous character
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
        return True  # Keep going


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

    timing_file = 'timing.csv'

    def __init__(self,
                 window_manager,        # GmWindowManager object for menus and
                                        #   errors
                 world,                 # World object
                 monster_group,         # string
                 playback_history,      # dict from bug report (usually None)
                 save_snapshot=True     # Here so tests can disable it
                 ):
        super(FightHandler, self).__init__(window_manager, world)
        self.__bodies_looted = False
        self.__keep_monsters = False  # Move monsters to 'dead' after fight
        self.__equipment_manager = ca_equipment.EquipmentManager(
                                                    self.world,
                                                    self._window_manager)

        self.__saved_history = None

        # If we're playing back history from a bug report and this fight has
        # spanned multiple sessions, start the playback history from the
        # beginning of the most recent session (since the snapshot is from
        # that spot).
        if (playback_history is not None and
                'playback_start_index' in world.details['current-fight']):
            self.__next_playback_action_index = (
                    world.details['current-fight']['playback_start_index'])
        else:
            self.__next_playback_action_index = 0  # Only for playback

        if 'history' in world.details['current-fight']:
            world.details['current-fight']['playback_start_index'] = (
                    len(world.details['current-fight']['history']))

        self._add_to_choice_dict({
            curses.KEY_UP: {'name': 'prev character',
                            'func': self.__view_prev},
            curses.KEY_DOWN: {'name': 'next character',
                              'func': self.__view_next},
            curses.KEY_HOME: {'name': 'current character',
                              'func': self.__view_init},

            ord(' '): {'name': 'next fighter',
                       'func': self.__next_fighter,
                       'help': 'Pass the initiative to the NEXT fighter. ' +
                               'That fighter will be the only one that ' +
                               'can maneuver.  If the current fighter ' +
                               'can, but has not yet performed an action, ' +
                               'this will give the fighter the chance ' +
                               'to do something before passing the ' +
                               'initiative.'},
            ord('<'): {'name': 'prev fighter',
                       'func': self.__prev_fighter,
                       'help': 'Pass the initiative to the PREVIOUS ' +
                               'fighter. That fighter will be the only ' +
                               'one that can maneuver.'},
            ord('?'): {'name': 'explain',
                       'func': self.__show_why,
                       'help': 'Explain how the attack and defense numbers ' +
                               'were calculated for the currently selected ' +
                               'figher.'},
            ord('A'): {'name': 'attribute (edit)',
                       'func': self.__edit_attribute,
                       'help': 'Allows the user to edit a fighter\'s ' +
                               'permanent or current attribute values.'},
            ord('d'): {'name': 'defend',
                       'func': self.__defend,
                       'help': 'Cause the currently selected fighter to ' +
                               'defend themselves.  This might, depending ' +
                               'on the current ruleset, cause the fighter ' +
                               'to lose aim.'},
            ord('D'): {'name': 'dead/unconscious',
                       'func': self.__dead,
                       'help': 'Select the state of the fighter to be ' +
                               'alive, dead, unconscious, or absent.'},
            ord('g'): {'name': 'give equipment',
                       'func': self.__give_equipment,
                       'help': 'Cause the selected fighter to give a piece ' +
                               'of equipment to another fighter.'},
            ord('h'): {'name': 'History',
                       'func': self.__show_history,
                       'help': 'Show the list of actions that have happened ' +
                               'in this fight, so far.'},
            ord('i'): {'name': 'character info',
                       'func': self.__show_info,
                       'help': 'Shows the detailed description of the ' +
                               'fighter. This includes equipment and ' +
                               'timers and the like.'},
            ord('-'): {'name': 'HP damage',
                       'func': self.__damage_HP,
                       'help': 'Removes hit points from the currently ' +
                               'selected fighter, or the current opponent ' +
                               '(if nobody is selected), or (if neither ' +
                               'of those) the ' +
                               'fighter that currently has the initiative. ' +
                               'If the opponent is the one losing HP and ' +
                               'the current fighter has not yet attacked ' +
                               'this round, ' +
                               'that fighter will be given the opportunity. ' +
                               'Armor will be taken into account if you ' +
                               'specify (via subsequent menu).'},
            ord('l'): {'name': 'label',
                       'func': self.__label,
                       'help': 'Adds a label to a fighter during the fight.'},
            ord('L'): {'name': 'remove label',
                       'func': self.__remove_label,
                       'help': 'Removes a fighter\'s label.'},
            ord('m'): {'name': 'maneuver',
                       'func': self.__maneuver,
                       'help': 'Causes the fighter with the initiative to ' +
                               'perform some action (selected via ' +
                               'subsequent menu).  Only things the figher ' +
                               'can currently do will be available.'},
            ord('n'): {'name': 'fight notes',
                       'func': self.__fight_notes,
                       'help': 'Changes the notes displayed during a fight ' +
                               'for the currently selected fighter'},
            ord('N'): {'name': 'full Notes',
                       'func': self.__full_notes,
                       'help': 'Changes the notes displayed in detailed ' +
                               'descriptions for the currently selected ' +
                               'fighter.'},
            ord('o'): {'name': 'opponent',
                       'func': self.pick_opponent,
                       'help': 'Selects an opponent for the currently ' +
                               'selected fighter.  If possible, the default ' +
                               'selection on the menu will be for an ' +
                               'unopposed fighter.'},
            ord('O'): {'name': 'Opponent (any)',
                       'func': self.__pick_all_opponent,
                       'help': 'Selects an opponent for the currently ' +
                               'selected fighter.  If possible, the default ' +
                               'selection on the menu will be for an ' +
                               'unopposed fighter.'},
            ord('P'): {'name': 'promote to NPC',
                       'func': self.promote_to_NPC,
                       'help': 'If the currently selected fighter is not' +
                               'a player character, ' +
                               'make the selected fighter into an ' +
                               'NPC.  The fighter will ' +
                               'be listed in both groups but they will ' +
                               'both refer to the same creature ' +
                               '(changing one will change the other).'},
            ord('q'): {'name': 'quit',
                       'func': self.__quit,
                       'help': 'Stop the fight.  You will be given the ' +
                               'opportunity to save it for later, save ' +
                               'it for the next time you start a fight ' +
                               '(if, for example, you shut down the ' +
                               'program at the end of the night but are ' +
                               'not yet finished), or just leave the ' +
                               'fight.  If one or more monsters are no ' +
                               'longer conscious, you will be given the ' +
                               'opportunity to loot the bodies.'},
            ord('t'): {'name': 'timer',
                       'func': self.__timer,
                       'help': 'Start a timer for the selected fighter. ' +
                               'A timer can display something in the ' +
                               'fighters notes until it fires or it can ' +
                               'display something on the screen when it ' +
                               'fires.'},
            ord('T'): {'name': 'Timer cancel',
                       'func': self.__timer_cancel,
                       'help': 'Cancel an existing timer for the selected ' +
                               'fighter.'},
            ord('w'): {'name': 'wait',
                       'func': self.__wait,
                       'help': 'Hold your initiative.'},
            ord('W'): {'name': 'stop waiting',
                       'func': self.__wait_end,
                       'help': 'Move previously held fighter after the' +
                               'current fighter.'},
        })

        if playback_history is not None:
            self._add_to_choice_dict({
                ord('x'): {'name': 'Run ALL history',
                           'func': self.__playback_history,
                           'help': 'Plays back all of the history in the ' +
                                   'playback file.'},
                ord('y'): {'name': 'Step history 1x',
                           'func': self.__single_step_history,
                           'help': 'Plays one step of the history in the ' +
                                   'playback file.'},
                ord('Y'): {'name': 'Step history multi',
                           'func': self.__multi_step_history,
                           'help': 'Plays several steps of the history in ' +
                                   'the playback file.'},
                ord('z'): {'name': 'Show playback history',
                           'func': self.__show_playback,
                           'help': 'Shows the actions in the playback ' +
                                   'history.'},
                    })

        self._add_to_choice_dict(self.world.ruleset.get_fight_commands(self))
        self._window = self._window_manager.get_fight_gm_window(
                self.world.ruleset, self._choices, self)

        self.__viewing_index = None

        fight_order = None
        if self._saved_fight['saved']:
            if save_snapshot:   # True, except for tests
                self.world.do_debug_snapshot('fight')
            monster_group = self._saved_fight['monsters']

            # If the number of creatures don't match the saved fight, make
            # the code regenerate the list.
            fight_order = self._saved_fight['fighters']

            if playback_history is not None:
                # Make a copy of the history so I can play it back
                self.__saved_history = playback_history

                # Clean out the history so we can start over
                self.clear_history()

        else:
            self.clear_history()
            self._saved_fight['held-init'] = []
            self.add_to_history({'comment': '--- Round 1 ---'})

            self._saved_fight['round'] = 0
            self._saved_fight['index'] = 0
            self._saved_fight['monsters'] = monster_group

        init = self.__build_fighter_list(monster_group, fight_order)
        self.__build_saved_fight(init)  # From self.__fighters

        # Make sure the monsters are self-consistent.

        if monster_group is not None:
            for name in self.world.get_creature_details_list(monster_group):
                # TODO (eventually): maybe use get_creature so that the
                # information is cached in World.
                details = self.world.get_creature_details(name,
                                                          monster_group)
                if details is not None:
                    self.world.ruleset.is_creature_consistent(name, details)

        # Setup the first fighter.

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


    def __pick_all_opponent(self):
        '''
        Command ribbon method.

        Allows the user to choose an opponent for the current Fighter.  If the
        opponent does not currently have an opponent of his/her own, it gives
        the user the option of making that opposition mutual (so that the two
        Fighters are opponents of each other).

        Does NOT limit the possible opponents to the other side.  This is
        useful for possessed creatures.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        return self.pick_opponent(allow_all=True)

    #
    # Public Methods
    #

    def draw_screen(self):
        '''
        Draws the complete screen for the FightHandler.

        Returns: nothing.
        '''
        self._draw_screen()

    def get_current_fighter(self):              # Public to support testing
        '''
        Returns the Fighter object of the current fighter.
        '''
        result = self.__fighters[self._saved_fight['index']]
        return result

    def get_fighter_object(self,
                           name,  # <string> name of a fighter in that group
                           group  # <string> 'PCs' or group under
                                  #     world['fights']
                           ):
        '''
        Returns the Fighter object given the name and group of the fighter,
        '''
        for index, fighter in enumerate(self.__fighters):
            if fighter.group == group and fighter.name == name:
                return index, fighter

        return None, None  # Not found

    def get_fighters(self):                     # Public to support testing
        '''
        Returns a list of information for all the Fighters in self.__fighters.
        '''
        return [{'name': fighter.name,
                 'group': fighter.group,
                 'details': fighter.details} for fighter in self.__fighters]

    def get_opponent_for(self,
                         fighter  # Fighter object
                         ):
        ''' Returns Fighter object for opponent of |fighter|. '''
        if (fighter is None or fighter.name == ca_fighter.Venue.name or
                fighter.details['opponent'] is None):
            return None  # No opponent

        ignore, opponent = self.get_fighter_object(
                                        fighter.details['opponent']['name'],
                                        fighter.details['opponent']['group'])
        return opponent

    def get_round(self):
        return self._saved_fight['round']

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
            elif string < 256:
                self._window_manager.error(
                                    ['Invalid command: "%c" ' % chr(string)])
            else:
                self._window_manager.error(
                                    ['Invalid command: "<%d>" ' % string])

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
                self.__keep_monsters is False):
            fight_group = self._saved_fight['monsters']
            self.world.remove_fight(fight_group)

    def is_fighter_holding_init(self,
                                name, # string
                                group # string
                                ):
        # FightHandler
        if 'held-init' not in self._saved_fight:
            return False
        for entry in self._saved_fight['held-init']:
            if name == entry[1]['name'] and group == entry[1]['group']:
                return True
        return False

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
        return True  # Keep asking questions

    def modify_index(self,                      # Public to support testing
                     adj,     # 1 or -1, adjust the index by this
                     raw_modify=False
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
            if current_fighter.name == ca_fighter.Venue.name:
                pass
            elif current_fighter.is_dead():
                if raw_modify:
                    keep_going = False
                elif not self.world.playing_back:
                    self.add_to_history(
                            {'comment': ('(%s) did nothing (dead)' %
                                         current_fighter.name)})
            elif current_fighter.is_absent():
                if raw_modify:
                    keep_going = False
                elif not self.world.playing_back:
                    self.add_to_history(
                            {'comment': ('(%s) did nothing (absent)' %
                                         current_fighter.name)})

            elif (current_fighter.group != 'PCs' and
                    not current_fighter.is_conscious()):
                if raw_modify:
                    keep_going = False
                elif not self.world.playing_back:
                    self.add_to_history(
                            {'comment': ('(%s) did nothing (unconscious)' %
                                         current_fighter.name)})
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
                    (self._saved_fight['round']+1)})

    def pick_opponent(self,
                      allow_all=False # bool: don't limit to other side
                      ):
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

        opponent_menu = []
        default_selection = None
        for fighter in self.__fighters:
            if ((allow_all or fighter.group != current_fighter.group) and
                    fighter.name != ca_fighter.Venue.name and
                    fighter.name != current_fighter.name):
                if fighter.is_conscious():
                    if fighter.details['opponent'] is None:
                        if default_selection is None:
                            default_selection = len(opponent_menu)
                        menu_text = fighter.name
                    else:
                        menu_text = '%s (fighting %s)' % (
                                fighter.name,
                                fighter.details['opponent']['name'])
                    opponent_menu.append((menu_text, {'name': fighter.name,
                                                      'group': fighter.group}))
        if len(opponent_menu) <= 0:
            self._window_manager.error(['All the opponents are dead'])
            return True  # don't leave the fight

        if default_selection is None:
            default_selection = 0
        opponent_name, ignore = self._window_manager.menu(
            'Opponent', opponent_menu, default_selection)

        if opponent_name is None:
            return True  # don't leave the fight

        # Now, reflect the selection in the code.

        self.world.ruleset.do_action(
                current_fighter,
                {'action-name': 'pick-opponent',
                 'opponent': {'name': opponent_name['name'],
                              'group': opponent_name['group']},
                 'comment': ('(%s) picked (%s) as opponent' %
                             (current_fighter.name, opponent_name))
                 },
                self)

        ignore, opponent = self.get_fighter_object(opponent_name['name'],
                                                   opponent_name['group'])

        # Ask to have them fight each other
        if (opponent is not None and opponent.details['opponent'] is None):
            back_menu = [('yes', True), ('no', False)]
            answer, ignore = self._window_manager.menu(
                    'Make Opponents Go Both Ways', back_menu)
            if answer is True:
                self.world.ruleset.do_action(
                        opponent,
                        {'action-name': 'pick-opponent',
                         'opponent': {'name': current_fighter.name,
                                      'group': current_fighter.group},
                         'comment': (
                             '(%s) picked (%s) as opponent right back' %
                             (opponent_name['name'], current_fighter.name))
                         },
                        self)

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True  # Keep going

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
        group[new_NPC.name] = {"redirect": "NPCs"}

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
                                                  'mode': curses.A_NORMAL}]])
                break

        return True  # Keep going

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
        return True  # Keep asking questions

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
        if current_fighter.name == ca_fighter.Venue.name:
            show_fighter = False

        elif current_fighter.is_dead():
            show_fighter = False

        elif current_fighter.is_absent():
            show_fighter = False

        if not show_fighter:
            self.__handle_fighter_background_actions(current_fighter)

        return show_fighter

    def wait_action(self,   # Public so it can be called by the ruleset.
                    name,   # String: name of fighter
                    group   # String: group of fighter
                    ):
        '''
        Action handling for tagging someone as holding their initiative.
        '''
        # Can't store index because 2 held initiatives can cause the index for
        # the 2nd fighter changed by the first.
        self._saved_fight['held-init'].append(
                ('%s:%s' % (group, name),
                 {'name': name, 'group': group}))

        lines = []
        mode = curses.A_NORMAL
        lines.append([{'text': 'The following fighters are holding:',
                       'mode': mode}])
        for fighter in self._saved_fight['held-init']:
            lines.append([{'text': '  %s' % fighter[0],
                           'mode': mode}])
        self._window_manager.display_window(
                'OK, %s:%s is holding his/her initiative' % (name, group),
                lines)

    def wait_end_action(self,   # Public so it can be called by the ruleset.
                        name,           # String: name of fighter
                        group,          # String: group of fighter
                        in_place=False  # bool: move fighter to new init?
                        ):
        '''
        Action handling for tagging someone as no longer holding their
        initiative.
        '''
        # Find the menu_index from the name, group

        menu_index = None
        for index, entry in enumerate(self._saved_fight['held-init']):
            if (name == entry[1]['name'] and
                group == entry[1]['group']):
                    menu_index = index
                    break
        if menu_index is None:
            #self._window_manager.error(
            #        ['%s not found in initiative menu' % name])
            return True # Keep fighting

        # Remove the index entry from the menu

        self._saved_fight['held-init'].pop(menu_index)

        if in_place:
            return

        # Determine destination of move.

        to_index = self.__viewing_index
        if to_index is None:
            to_index = self._saved_fight['index']

        # Get the fighter that we're moving

        from_index, fighter_obj = self.get_fighter_object(name,
                                                          group)
        fighter_dict = self._saved_fight['fighters'][from_index]

        # Build init of moved fighter to locate it in the moved position if we
        # sort by initiative.

        init_tuple = self._saved_fight['fighters'][to_index]['init']
        init_list = list(init_tuple)

        fighter_after = None
        if (to_index+1) < len(self._saved_fight['fighters']):
            fighter_after = self._saved_fight['fighters'][to_index+1]
            init_tuple_plus_1 = fighter_after['init']
            init_list_plus_1 = list(init_tuple_plus_1)
            found_one = False
            for i, datum in enumerate(init_list):
                if datum != init_list_plus_1[i]:
                    init_list[i] = (datum + init_list_plus_1[i]) / 2.0
                    found_one = True
                    break
            if not found_one:
                self._window_manager.error(
                        ['Fighter seems to have the same init as destination'])
                pass
        else:
            # Put the new fighter's initiative beyond the last one
            init_list[-1] += (-1 if self.world.ruleset.sort_init_descending
                              else 1)

        init_tuple = tuple(init_list)
        fighter_dict['init'] = init_tuple

        # Move the fighter

        if from_index == to_index:
            return True  # Keep fighting
        else:
            # This simplifies un-holding a group of fighters to the current
            # init.  It allows the initiative to stay the same as you're
            # adding each member but adds each member after the previous
            # addition.
            self.__viewing_index = to_index

        self.__add_fighter_after_index(fighter_dict, fighter_obj, to_index)

        # If we added one above the removal index, we need to account for that.
        if from_index > to_index:
            from_index += 1

        self.__remove_fighter_at_index(from_index)

    #
    # Private Methods
    #

    def __add_fighter_after_index(
            self,
            fighter_dict,  # dict for saved_fight
            fighter_obj,   # Fighter object for __fighters
            to_index       # index into _saved_fight and __fighters
            ):
        if self.__viewing_index is None:
            pass # |pass| just saves a nesting level
        elif to_index < self.__viewing_index:
            self.__change_viewing_index(-1)

        # Actually add the fighter

        if to_index >= len(self.__fighters) - 1:
            self._saved_fight['fighters'].append(fighter_dict)
            self.__fighters.append(fighter_obj)
        else:
            self._saved_fight['fighters'].insert(to_index+1, fighter_dict)
            self.__fighters.insert(to_index+1, fighter_obj)

        # Adjust initiative index (while maintianing the viewing index)

        if to_index == self.__viewing_index:
            self.__change_viewing_index(1)

        if to_index < self._saved_fight['index']:
            viewing_index = self.__viewing_index
            self.modify_index(1, raw_modify=True)
            self.__viewing_index = viewing_index

    def __build_fighter_list(self,
                             monster_group,  # String
                             fight_order     # {name: {group: index, ...}, ...
                             ):
        '''
        Creates the list of Fighters and the Venue.  This includes the PCs,
        the monster group, and the location of the fight.  They're created in
        initiative order (i.e., the order in which they act in a round of
        fighting, according to the ruleset).

        Saves that list in self.__fighters.

        Returns: dict - (tuple of name, group) -> (tuple of init params)
        '''

        # Build the fighter list (even if the fight was saved since monsters
        # or characters could have been added since the save happened).

        # This is a parallel array to self._saved_fight['fighters'] but the
        # contents are ThingsInFight (i.e., Fighters or a Venue)
        self.__fighters = []

        # Start with the PCs
        for name in self.world.get_creature_details_list('PCs'):
            fighter = self.world.get_creature(name, 'PCs')
            if fighter is not None:
                self.__fighters.append(fighter)

        # Then add the monsters (save the Venue aside, if it exists)
        the_fight_itself = None
        if monster_group is not None:
            for name in self.world.get_creature_details_list(monster_group):
                details = self.world.get_creature_details(name,
                                                          monster_group)
                if details is None:
                    continue

                if name == ca_fighter.Venue.name:
                    the_fight_itself = details
                else:
                    fighter = self.world.get_creature(name, monster_group)
                    self.__fighters.append(fighter)

        # Put the creatures in order

        # Build the 'init' dict: (name, group) -> (init tuple)...
        # ...for all creatures but not for the room, itself.  This contains
        # the data on which the initiatives of the fighters are calculated.
        init = {}

        if fight_order is None:
            # There's no previously established fight order (which would be
            # the case if we're jumping into a fight that was saved) to
            # maintain, just generate the initiative for all of the fighters.
            for fighter in self.__fighters:
                init[(fighter.name,
                      fighter.group)] = self.world.ruleset.initiative(
                              fighter,
                              self.__fighters)
        else:
            # We're assuming that every fighter in fight_order is in
            # self.__fighters but not necessarily the other way around.
            for fighter in fight_order:
                if fighter['name'] == ca_fighter.Venue.name:
                    continue

                # Generate an initiative if it's not already there.  This
                # deals with legacy fights that don't contain initiative.
                if 'init' not in fighter:
                    for f in self.__fighters:
                        if (f.name == fighter['name'] and
                                f.group == fighter['group']):
                            fighter['init'] = self.world.ruleset.initiative(f)
                            break

                # Now, build |init| from the fight order
                init[(fighter['name'], fighter['group'])] = fighter['init']

            # Finally, add initiative for any fighters that aren't represented
            # in the fight order.  This deals with fighters that were added
            # after the fight started.

            for fighter in self.__fighters:
                if (fighter.name, fighter.group) not in init:
                    init[(fighter.name,
                          fighter.group)] = self.world.ruleset.initiative(
                                  fighter)

        # Now, sort based on the initiative we just built

        self.__fighters.sort(key=lambda fighter:
                             init[(fighter.name, fighter.group)],
                             reverse=True)

        # Assign an ordinal to insure the order for fights that are saved
        # and, then, resorted on re-entry.

        if fight_order is None:
            for index, fighter in enumerate(self.__fighters):
                name_group = (fighter.name, fighter.group)
                if name_group in init:
                    init_tuple = init[name_group]
                    init_list = list(init_tuple)
                    ordinal = (-index if self.world.ruleset.sort_init_descending
                               else index)
                    init_list.append(ordinal)
                    init_tuple = tuple(init_list)
                    init[name_group] = init_tuple

        # Put the fight info (if any) at the top of the list.
        if the_fight_itself is not None:
            fight = ca_fighter.Venue(monster_group,
                                     the_fight_itself,
                                     self.world.ruleset,
                                     self._window_manager)

            self.__fighters.insert(0, fight)

        return init

    def __build_saved_fight(self,
                            init    # dict - (name, group) -> (init params)
                            ):
        '''
        Builds self._saved_fight['fighters']

        Returns: Nothing
        '''
        # Copy the fighter information into the saved_fight.  Also, make
        # sure this looks like a _NEW_ fight.

        self._saved_fight['fighters'] = []
        for fighter in self.__fighters:
            if fighter.name == ca_fighter.Venue.name:
                self._saved_fight['fighters'].append(
                        {'name': fighter.name,
                         'group': fighter.group})
            else:
                # NOTE: an ongoing fight is saved so that re-running a crashed
                # fight will come-up in the middle of the fight.
                if not self._saved_fight['saved']:
                    fighter.start_fight()
                self._saved_fight['fighters'].append(
                        {'name': fighter.name,
                         'group': fighter.group,
                         'init': init[(fighter.name, fighter.group)]})

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

            # Not going to do an 'attack' action when the HP was modified
            # through an index
            attacker = None
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
        adj = self._window_manager.input_box_number(height, width, title)
        if adj is None:
            return True

        if adj == 0:
            return True  # Keep fighting
        adj = -adj # NOTE: SUBTRACTING the adjustment

        action = {'action-name': 'adjust-hp', 'adj': adj}

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
                should_attack, ignore = self._window_manager.menu(
                                    ('Should %s Attack?' % attacker.name),
                                    attack_menu)
                if should_attack:
                    comment = '(%s) did (Attack) maneuver' % attacker.name
                    self.world.ruleset.do_action(
                                        attacker,
                                        {'action-name': 'attack',
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

        self.world.ruleset.do_action(hp_recipient, action, self)

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True  # Keep going

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
            return True  # Keep fighting

        state_menu = sorted(ca_fighter.Fighter.conscious_map.iteritems(),
                            key=lambda x: x[1])

        new_state_number, ignore = self._window_manager.menu('New State',
                                                             state_menu)
        if new_state_number is None:
            return True  # Keep fighting

        dead_name = now_dead.name

        self.world.ruleset.do_action(
                now_dead,
                {
                    'action-name': 'set-consciousness',
                    'level': new_state_number,
                    'comment': '(%s) is now (%s)' % (
                        dead_name,
                        ca_fighter.Fighter.get_name_from_state_number(
                                                            new_state_number))
                },
                self)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True  # Keep going

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
            starting_index = 1 # assume the opponent
            defender, ignore = self._window_manager.menu('Who is defending',
                                                         defender_menu,
                                                         starting_index)
        if defender is None:
            return True  # Keep fighting

        self.world.ruleset.do_action(
            defender,
            {
                'action-name': 'defend',
                'comment': '(%s) defended (and lost aim)' % defender.name
            },
            self)

        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True  # Keep going

    def _draw_screen(self):
        '''
        Draws the complete screen for the FightHandler.

        Returns: nothing.
        '''

        self._window.clear()

        if self.__viewing_index is not None:
            current_fighter = self.__fighters[self.__viewing_index]
        else:
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

    def __edit_attribute(self):
        '''
        Command ribbon method.

        Allows the user to modify one or more of the current fighter's
        attributes.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        if self.__viewing_index is not None:
            fighter = self.__fighters[self.__viewing_index]
        else:
            fighter = self.get_current_fighter()

        attribute_widget = AttributeWidget(self._window_manager,
                                           self,
                                           fighter)
        attribute_widget.doit()
        return True  # keep fighting

    def __fight_notes(self):
        '''
        Command ribbon method.

        Lets the user edit a fighter's (or Venue's) fight notes.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        return self.__notes('fight-notes')

    def __full_notes(self):
        '''
        Command ribbon method.

        Allows the user to modify the current fighter's full notes.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__notes('notes')
        return True  # keep fighting

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

        item_index = self.__equipment_manager.select_item_index(from_fighter)
        if item_index is None:
            return None
        count = from_fighter.ask_how_many(item_index)

        pc_list = []
        monster_list = []
        for fighter in self.__fighters:
            if fighter.group == 'PCs':
                pc_list.append(
                        (fighter.name,
                         {'name': fighter.name, 'group': fighter.group}
                         ))
            else:
                monster_list.append(
                        (fighter.name,
                         {'name': fighter.name, 'group': fighter.group}
                         ))
        character_menu = pc_list
        character_menu.extend(monster_list)

        item = from_fighter.details['stuff'][item_index]
        to_fighter_name, ignore = self._window_manager.menu(
                                        'Give "%s" to whom?' % item['name'],
                                        character_menu)

        if to_fighter_name is None:
            return True  # Keep going

        # Give item

        self.world.ruleset.do_action(
                from_fighter,
                {'action-name': 'give-equipment',
                 'item-index': item_index,
                 'count': count,
                 'recipient': to_fighter_name,
                 'comment': '%s gave %s to %s' % (from_fighter.name,
                                                  item['name'],
                                                  to_fighter_name['name'])
                 },
                self)

        return True  # Keep going

    def __handle_fighter_background_actions(
                                    self,
                                    out_of_commision_fighter  # Fighter object
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

    def __label(self):
        label_recipient, current_fighter = self.__select_fighter(
                                                            'Label For Whom')
        if label_recipient is None:
            return True  # Keep fighting

        title = 'Label for %s' % label_recipient.name
        height = 1
        width = len(title)
        label = self._window_manager.input_box(height, width, title)

        label_recipient.details['label'] = label

        # Redraw the fighters
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True

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
        to_whom = 0
        for bad_guy in self.__fighters:
            if bad_guy.group == 'PCs':  # only steal from bad guys
                continue
            if bad_guy.name != ca_fighter.Venue.name:
                # only steal from the dead/unconscious
                if bad_guy.is_conscious() or bad_guy.is_absent():
                    continue
            found_dead_bad_guy = True

            # Reversed so removing items doesn't change the index of others
            for index, item in reversed(list(enumerate(
                                                bad_guy.details['stuff']))):
                # Don't 'loot' natural weapons or armor
                if (('natural-weapon' in item and item['natural-weapon']) or
                        ('natural-armor' in item and item['natural-armor'])):
                    continue
                output = []
                ca_equipment.EquipmentManager.get_description(
                        item, '', [], False, output)
                # output looks like:
                # [[{'text','mode'},...],  # line 0
                #  [...],               ]  # line 1...
                pieces = []
                for piece in output[0]: # the first line of the output
                    pieces.append(piece['text'])
                description = ''.join(pieces)

                found_something_on_dead_bad_guy = True
                xfer_menu = [(good_guy.name, {'guy': good_guy})
                             for good_guy in self.__fighters
                             if good_guy.group == 'PCs']
                xfer_menu.append(('IGNORE', {'ignore': None}))
                xfer_menu.append(('QUIT', {'quit': None}))
                xfer, to_whom = self._window_manager.menu(
                        'Who gets %s\'s %s' % (bad_guy.name,
                                               description),
                        xfer_menu,
                        to_whom)

                if xfer is None or 'ignore' in xfer:
                    continue

                if 'quit' in xfer:
                    return True

                # TODO (now): go back and ask again for items where we didn't
                # get all of them
                new_item = bad_guy.remove_equipment(index)
                source = '%s:%s' % (bad_guy.group,
                                    bad_guy.detailed_name)
                ignore = xfer['guy'].add_equipment(new_item,
                                                   source,
                                                   identified=False)

                # indexes are no longer good, remove the weapon and armor
                if bad_guy.name != ca_fighter.Venue.name:
                    armor_index_list = bad_guy.get_current_armor_indexes()
                    for armor_index in armor_index_list:
                        self.world.ruleset.do_action(
                                bad_guy,
                                {'action-name': 'doff-armor',
                                 'armor-index': armor_index,
                                 'notimer': True},
                                None)

                    weapon_index_list = bad_guy.get_current_weapon_indexes()
                    for weapon_index in weapon_index_list:
                        self.world.ruleset.do_action(
                                bad_guy,
                                {'action-name': 'holster-weapon',
                                 'weapon-index': weapon_index,
                                 'notimer': True},
                                self)


        if not found_dead_bad_guy:
            self._window_manager.error(
                ['Can\'t loot from the living -- there are no dead bad guys.'])
        elif not found_something_on_dead_bad_guy:
            self._window_manager.error(
                ['Bad guys didn\'t have anything worth looting.'])

        return True  # Keep fighting

    def __maneuver(self):
        '''
        Command ribbon method.

        Provides a menu of activities that the current Fighter can perform.
        Performs the selected one.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        current_fighter = self.get_current_fighter()
        if self.__viewing_index is not None:
            viewed_fighter = self.__fighters[self.__viewing_index]

            fighter_menu = [(viewed_fighter.name, viewed_fighter),
                               (current_fighter.name, current_fighter)]
            current_fighter, ignore = self._window_manager.menu(
                    'Who is Manuvering?', fighter_menu)

        opponent = self.get_opponent_for(current_fighter)
        #if self.__viewing_index != self._saved_fight['index']:
        #    self.__viewing_index = None
        #    self._window.show_fighters(current_fighter,
        #                               opponent,
        #                               self.__fighters,
        #                               self._saved_fight['index'],
        #                               self.__viewing_index)

        action_menu = self.world.ruleset.get_action_menu(current_fighter,
                                                         opponent)
        maneuver, ignore = self._window_manager.menu('Maneuver', action_menu)
        if maneuver is None:
            return True  # Keep going

        if 'action' in maneuver:
            maneuver['action']['comment'] = '(%s) did (%s) maneuver' % (
                    current_fighter.name,
                    maneuver['action']['action-name'])

            self.world.ruleset.do_action(current_fighter,
                                         maneuver['action'],
                                         self)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True  # Keep going

    def __multi_step_history(self):
        '''
        Command ribbon method.

        If we're reproducing a scenario (like from a bug report), we're
        provided with a sequence of history.  This routine plays that entire
        sequence.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if self.__saved_history is None:
            return True

        if self.__next_playback_action_index >= len(self.__saved_history):
            self._window_manager.error(
                ['Playback history exhausted -- you are at the end.'])
            return True

        title = ('Execute How Many Steps of Playback (next is %d/%d)?' %
                 (self.__next_playback_action_index,
                  len(self.__saved_history)))
        height = 1
        width = len(title)
        step_count = self._window_manager.input_box_number(height,
                                                           width,
                                                           title)
        if step_count is None:
            return True

        if (self.__next_playback_action_index + step_count >
                len(self.__saved_history)):
            step_count = (len(self.__saved_history) -
                          self.__next_playback_action_index)

        for i in range(step_count):
            action = self.__saved_history[self.__next_playback_action_index]
            self.__next_playback_action_index += 1
            next_fighter = self.get_current_fighter()

            # print '\n--- __multi_step_history'
            # PP.pprint(action)

            self.__raw_single_step(next_fighter,  action)

        lines = []
        mode = curses.A_NORMAL
        line = 'Just executed through %d/%d' % (
                self.__next_playback_action_index - 1,
                len(self.__saved_history))
        lines.append([{'text': line, 'mode': mode}])
        self._window_manager.display_window(
                'Just executed %d actions of playback' % step_count,
                lines)

        return True  # Keep going

    def __next_fighter(self,
                       skip_prev=False # in case prev was (re)moved
                       ):
        '''
        Command ribbon method.

        Close-out the actions of the current fighter and start the actions of
        the next fighter in the fight.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        self.__viewing_index = None

        # Finish off previous guy
        if not skip_prev:
            prev_fighter = self.get_current_fighter()
            if not prev_fighter.can_finish_turn(self):
                return self.__maneuver()
            elif not prev_fighter.is_conscious():
                self.add_to_history({'comment': '(%s) did nothing (unconscious)' %
                                     prev_fighter.name})

            self.world.ruleset.do_action(prev_fighter,
                                         {'action-name': 'end-turn'},
                                         self)
        current_fighter = self.get_current_fighter()
        self.world.ruleset.do_action(current_fighter,
                                     {'action-name': 'start-turn'},
                                     self)

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
        return True  # Keep going

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
                # FightHandler
                next_PC_name = (
                        self._saved_fight['fighters'][next_index]['name'])
                ignore, next_PC = self.get_fighter_object(next_PC_name, 'PCs')
                if next_PC is not None and next_PC.is_conscious():
                    break
                next_PC_name = None
            next_index += 1
        return next_PC_name

    def __notes(self,
                notes_type  # 'fight-notes' or 'notes'
                ):
        '''
        Command ribbon method.

        Allows the user to modify a Fighter's notes or fight-notes.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        notes_recipient, current_fighter = self.__select_fighter(
                                                            'Notes For Whom')
        if notes_recipient is None:
            return True  # Keep fighting

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
        return True  # Keep going

    def __playback_history(self):
        '''
        Command ribbon method.

        If we're reproducing a scenario (like from a bug report), we're
        provided with a sequence of history.  This routine plays that entire
        sequence.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if self.__saved_history is None:
            return True

        if self.__next_playback_action_index >= len(self.__saved_history):
            self._window_manager.error(
                ['Playback history exhausted -- you are at the end.'])
            return True

        step_count = (len(self.__saved_history) -
                      self.__next_playback_action_index)

        for i in range(step_count):
            action = self.__saved_history[self.__next_playback_action_index]
            self.__next_playback_action_index += 1
            next_fighter = self.get_current_fighter()

            # print '\n--- __playback_history'
            # PP.pprint(action)

            self.__raw_single_step(next_fighter,  action)

        return True  # Keep going

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
            return True  # Not going backwards from the origin

        prev_fighter = self.get_current_fighter()
        self.world.ruleset.do_action(prev_fighter,
                                     {'action-name': 'previous-turn'},
                                     self)

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
        return True  # Keep going

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

        # Temporarily, save a bug report at the end of the fight
        # TODO (eventually): remove

        if not ScreenHandler.maintain_game_file:
            self.world.do_debug_snapshot('EndFight')
            bug_report_game_file = self.world.program.make_bug_report(
                self.world.details['current-fight']['history'],
                'Taking a snapshot at the end of the fight',
                None, # snapshot filename
                'end_fight')

            self._window_manager.display_window(
                    'Saved Snapshot After Fight',
                    [[{'text': ('Output file "%s"' % bug_report_game_file),
                       'mode': curses.A_NORMAL}]])

        # Get the state of the monsters.

        ask_to_save = False  # Ask to save if some monster is conscious
        ask_to_loot = False  # Ask to loot if some monster is unconscious
        for fighter in self.__fighters:
            if (fighter.group != 'PCs' and
                    fighter.name != ca_fighter.Venue.name):
                if fighter.is_conscious():
                    ask_to_save = True
                elif not fighter.is_absent():
                    ask_to_loot = True

        # Ask: save or loot?

        # Open up a small window where the fight is not saved.  If there's a
        # crash, here, then we won't come back to the fight.
        self._saved_fight['saved'] = False
        self.__keep_monsters = False  # Don't move monsters to dead after fight

        while ask_to_save or ask_to_loot:
            quit_menu = [('quit -- really', False)]
            # If we're still in the middle of this fight, there's not time to
            # loot the bodies.
            if self._saved_fight['saved']:
                ask_to_loot = False

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

            result, ignore = self._window_manager.menu('Leaving Fight',
                                                       quit_menu)

            if result is None:
                return True  # I guess we're not quitting after all

            elif result is False:
                ask_to_save = False
                ask_to_loot = False

        if not self._saved_fight['saved']:
            reload_after_fight = self.world.ruleset.get_option(
                    'reload-after-fight')
            if reload_after_fight is not None and reload_after_fight:
                window_text = [[{'text': 'Reload, Reload, Reload.',
                                 'mode': curses.A_NORMAL}]]
                self._window_manager.display_window(
                        ('Auto-Reloading After The Fight'),
                        window_text)
            for fighter in self.__fighters:
                fighter.end_fight(self)

        self._window.close()
        return False  # Leave the fight

    def __raw_single_step(self,
                          next_fighter,  # Fighter object
                          action  # dict
                          ):
        current_fighter = next_fighter

        # print '\n--- __single_step_history'
        # PP.pprint(action)

        self.world.playing_back = True

        if 'fighter' in action:
            name = action['fighter']['name']
            group = action['fighter']['group']
            ignore, fighter = self.get_fighter_object(name, group)
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

    def __remove_fighter_at_index(
            self,
            from_index  # index into _saved_fight and __fighters
            ):
        if self.__viewing_index is None:
            pass # Just saves a nesting level
        elif from_index < self.__viewing_index:
            self.__change_viewing_index(-1)
        elif from_index == self.__viewing_index:
            # You can undo the case of 'held' initiative by placing the
            # fighter directly after itself.  Put the "new" guy in first.
            # Deleting the old guy will advance the viewing index to the
            # newly added guy (causing the index to stay the same).
            self.__change_viewing_index(1)

        # Actually remove the fighter

        self._saved_fight['fighters'].pop(from_index)
        self.__fighters.pop(from_index)

        # Do this here so backing from 1 to end of list gets the actual end
        # (not one beyond).
        if from_index <= self._saved_fight['index']:
            viewing_index = self.__viewing_index
            self.modify_index(-1, raw_modify=True)
            self.__viewing_index = viewing_index

    def __remove_label(self):
        label_recipient, current_fighter = self.__select_fighter(
                                                            'Label For Whom')
        if label_recipient is None:
            return True  # Keep fighting

        label_recipient.details['label'] = None

        # Redraw the fighters
        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True

    def __select_fighter(self,
                         menu_title,  # string: title of fighter/opponent menu
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
                selected_fighter, ignore = self._window_manager.menu(
                                                     menu_title,
                                                     selected_fighter_menu,
                                                     default_selection)
        return selected_fighter, current_fighter

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
            return True  # Keep fighting

        info_about.get_description_long(char_info, expand_containers=False)
        self._window_manager.display_window('%s Information' % info_about.name,
                                            char_info)
        return True

    def __show_playback(self):
        '''
        Command ribbon method.

        Displays the actions in the playback history.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if self.__saved_history is None:
            return True

        lines = []
        scroll_to = None
        for index, action in enumerate(self.__saved_history):
            string = PP.pformat(action)
            pieces = string.split('\n')
            mode = (curses.A_BOLD
                    if index >= self.__next_playback_action_index
                    else curses.A_NORMAL)
            for i, piece in enumerate(pieces):
                if i == 0:
                    piece = '%03d %s' % (index, piece)
                    if index == self.__next_playback_action_index:
                        scroll_to = len(lines)
                else:
                    piece = '    %s' % piece
                lines.append([{'text': piece, 'mode': mode}])

        self._window_manager.display_window('Playback History',
                                            lines,
                                            scroll_to)
        return True  # Keep going

    def __show_why(self):
        '''
        Command ribbon method.

        Explain the details that went into a fighter's calculated numbers
        (e.g., to-hit).

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        why_target, current_fighter = self.__select_fighter('Details For Whom')
        if why_target is None:
            return True  # Keep fighting

        lines = why_target.explain_numbers(self)

        self._window_manager.display_window(
                    'How %s\'s Numbers Were Calculated' % why_target.name,
                    lines)
        return True

    def __single_step_history(self):
        '''
        Command ribbon method.

        If we're reproducing a scenario (like from a bug report), we're
        provided with a sequence of history.  This routine plays that entire
        sequence.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if self.__saved_history is None:
            return True

        if self.__next_playback_action_index >= len(self.__saved_history):
            self._window_manager.error(
                ['Playback history exhausted -- you are at the end.'])
            return True

        action = self.__saved_history[self.__next_playback_action_index]
        self.__next_playback_action_index += 1
        next_fighter = self.get_current_fighter()

        # print '\n--- __single_step_history'
        # PP.pprint(action)

        self.__raw_single_step(next_fighter,  action)

        # Show X/Y steps and the action

        # TODO (eventually): there should probably be a method that formats
        # an action.  This routine and playback_history should use it.
        lines = []
        index = self.__next_playback_action_index - 1
        string = PP.pformat(action)
        pieces = string.split('\n')
        mode = curses.A_NORMAL
        for i, piece in enumerate(pieces):
            if i == 0:
                piece = '%03d %s' % (index, piece)
            else:
                piece = '    %s' % piece
            lines.append([{'text': piece, 'mode': mode}])

        self._window_manager.display_window(
                'Just executed %d/%d of playback' % (
                    index,
                    len(self.__saved_history)),
                lines)

        return True  # Keep going

    def __timer(self):
        '''
        Command ribbon method.

        Asks user for information for a timer to add to a Fighter.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        timer_recipient, current_fighter = self.__select_fighter(
                                                            'Who Gets Timer')
        if timer_recipient is None:
            return True  # Keep fighting

        # self.world.ruleset...
        timers_widget = ca_timers.TimersWidget(timer_recipient.timers,
                                               self._window_manager)

        timer_dict = timers_widget.make_timer_dict(timer_recipient.name)
        if timer_dict is not None:
            self.world.ruleset.do_action(timer_recipient,
                                         {'action-name': 'set-timer',
                                          'timer': timer_dict},
                                         self)

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True  # Keep fighting

    def __timer_cancel(self):
        '''
        Command ribbon method.

        Allows the user to cancel one of a Fighter's active timers.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        timer_recipient, current_fighter = self.__select_fighter(
                                                    'Whose Timer To Cancel')
        if timer_recipient is None:
            return True  # Keep fighting

        # Select a timer

        timers = timer_recipient.timers.get_all()
        timer_menu = [(timer.get_one_line_description(), index)
                      for index, timer in enumerate(timers)]
        index, ignore = self._window_manager.menu('Remove Which Timer',
                                                  timer_menu)
        if index is None:
            return True  # Keep fighting

        # Delete the timer

        timer_recipient.timers.remove_timer_by_index(index)

        # Display the results

        opponent = self.get_opponent_for(current_fighter)
        self._window.show_fighters(current_fighter,
                                   opponent,
                                   self.__fighters,
                                   self._saved_fight['index'],
                                   self.__viewing_index)
        return True  # Keep fighting

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
        return True  # Keep going

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
        return True  # Keep going

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
        return True  # Keep going

    def __wait(self):
        '''
        Command ribbon method.

        Holds the initiative of the current fighter until their waiting is
        ended (with a call to __wait_end).

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # Adds the current fighter to the list of fighters who are holding
        # their initiative.  Note that we're just moving the fighter who
        # currently has the initiative.  Not the viewing index fighter.
        from_index = self._saved_fight['index']
        name = self._saved_fight['fighters'][from_index]['name']
        group = self._saved_fight['fighters'][from_index]['group']

        ignore, fighter_obj = self.get_fighter_object(name, group)
        if fighter_obj.can_finish_turn(self):
            self._window_manager.error(
                [('%s has already done something this round' % name),
                 'so s/he cannot hold their initiative.'])
            return True

        self.world.ruleset.do_action(fighter_obj,
                                     {'action-name': 'hold-init',
                                      'name': name,
                                      'group': group},
                                     self)

        return True  # Keep fighting

    def __wait_end(self):
        '''
        Command ribbon method.

        Places a fighter with a previously held initiative after the current
        fighter.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        # TODO (eventually): look at timer handling - maybe base advancing
        #   timers on whether it's OK to move on (check non-action reasons
        #   for moving on, though unconscious fighters can't hold their
        #   initiative).
        # TODO (eventually): when we're done with all of this, if the fighter
        #   that currently has initiative has already gone, move the
        #   initiative to the next fighter. -- NOTE: the actions are cleared
        #   in GurpsRuleset::start_turn

        if len(self._saved_fight['held-init']) <= 0:
            return True # Keep fighting

        # Figure out which fighter we're moving (in case more than one fighter
        # is holding their initiative).

        name_group, menu_index = self._window_manager.menu(
                'Stop Holding Whose Initiative',
                self._saved_fight['held-init'])
        if menu_index is None:
            return True # Keep fighting

        ignore, fighter_obj = self.get_fighter_object(name_group['name'],
                                                      name_group['group'])
        self.world.ruleset.do_action(fighter_obj,
                                     {'action-name': 'hold-init-complete',
                                      'name': name_group['name'],
                                      'group': name_group['group']},
                                     self)

        return True  # Keep fighting


class MainHandler(ScreenHandler):
    '''
    This is the primary screen of the program.  It displays a list of
    creatures, in the left pane.  It highlights the "current" creature and it
    shows the details of the current creature in the right pane.
    '''

    # These are intended to be bits so they can be ored together
    (CHAR_LIST,
     CHAR_DETAIL) = (1, 2)

    def __init__(self,
                 window_manager,    # GmWindowManager object for menus and
                                    #   errors
                 world              # World object
                 ):
        super(MainHandler, self).__init__(window_manager, world)
        self.__current_pane = MainHandler.CHAR_DETAIL
        self._add_to_choice_dict(
                {
                 curses.KEY_HOME: {'name': 'scroll home',
                                   'func': self.__first_page},
                 curses.KEY_UP: {'name': 'previous character',
                                 'func': self.__prev_char},
                 curses.KEY_DOWN: {'name': 'next character',
                                   'func': self.next_char},
                 curses.KEY_NPAGE: {'name': 'scroll down',
                                    'func': self.__next_page,
                                    'help': 'Scroll DOWN on the current ' +
                                            'pane which may may be either ' +
                                            'the character pane (on the ' +
                                            'left) or the details pane ' +
                                            '(on the right)'},
                 curses.KEY_PPAGE: {'name': 'scroll up',
                                    'func': self.__prev_page,
                                    'help': 'Scroll UP on the current ' +
                                            'pane which may may be ' +
                                            'either the character pane ' +
                                            '(on the left) or the details ' +
                                            'pane (on the right)'},
                 curses.KEY_LEFT: {'name': 'scroll chars',
                                   'func': self.__left_pane,
                                   'help': 'Choose the character pane (on ' +
                                           'the left) for scrolling.'},
                 curses.KEY_RIGHT: {'name': 'scroll char detail',
                                    'func': self.__right_pane,
                                    'help': 'Choose the details pane (on ' +
                                            'the right) for scrolling.'},

                 ord('a'): {'name': 'about the program',
                            'func': self.__about},
                 ord('f'): {'name': 'FIGHT',
                            'func': self.__run_fight,
                            'help': 'Start fighting.  If there is a saved ' +
                                    'fight, that one will start.  ' +
                                    'Otherwise, if the displayed group is ' +
                                    'a bunch of monsters, the fight will ' +
                                    'be with them.  Otherwise, you will ' +
                                    'be asked to select the monsters ' +
                                    'from a list.'},

                 # ord('h'): {'name': 'heal selected creature',
                 #            'func': self.__heal},

                 ord('h'): {'name': 'Heal all PCs',
                            'func': self.__fully_heal},
                 ord('m'): {'name': 'show MONSTERs or PC/NPC',
                            'func': self.__toggle_Monster_PC_NPC_display,
                            'help': 'Select whom to display on the main ' +
                                    'screen. '},
                 ord('M'): {'name': 'modify Monsters',
                            'func': self.__add_monsters,
                            'help': 'Change one or more monsters. You ' +
                                    'can add creatures to or subtract ' +
                                    'creatures from the selected list, ' +
                                    'modify stats, or add or remove ' +
                                    'equipment.'},
                 ord('N'): {'name': 'modify NPCs',
                            'func': self.__add_NPCs,
                            'help': 'Change non-player characters. You ' +
                                    'can add creatures to or subtract ' +
                                    'creatures from the selected list, ' +
                                    'modify stats, or add or remove ' +
                                    'equipment.'},
                 ord('P'): {'name': 'modify PCs',
                            'func': self.__add_PCs,
                            'help': 'Change player characters. You ' +
                                    'can add creatures to or subtract ' +
                                    'creatures from the selected list, ' +
                                    'modify stats, or add or remove ' +
                                    'equipment.'},
                 ord('Q'): {'name': 'quit',
                            'func': self.__quit,
                            'help': 'Exit the program'},
                 ord('R'): {'name': 'resurrect fight',
                            'func': self.__resurrect_fight,
                            'help': 'Put a fight that has been completed ' +
                                    'back in the list of availble fights'},
                 ord('S'): {'name': 'toggle: Save On Exit',
                            'func': self.__maintain_game_file,
                            'help': 'Toggle whether all of the changes to ' +
                                    'your game from this session will be ' +
                                    'written back to the game file when ' +
                                    'the program is exited.  This is ' +
                                    'really for debugging.'},
                 ord('/'): {'name': 'search',
                            'func': self.__search,
                            'help': 'Search through all of the various ' +
                                    'creatures in your game for a regular ' +
                                    'expressions.  You will be told where, ' +
                                    'in each search result, the search ' +
                                    'found your search term.  Selecting one ' +
                                    'of the results selects that creature ' +
                                    'on the screen if that creature\'s ' +
                                    'group is currently displayed.'}
                 })
        self._window = self._window_manager.get_main_gm_window(self._choices)

        # name of monster group or 'None' for PC/NPC list
        self.__current_display = None

        self.__setup_PC_list(self.__current_display)

        self.__equipment_manager = ca_equipment.EquipmentManager(
                                                    self.world,
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
                 [{'text': 'Copyright (c) 2019, Wade Guthrie',
                     'mode': curses.A_NORMAL}],
                 [{'text': 'https://github.com/wadeguthrie/combat-accountant',
                     'mode': curses.A_NORMAL}],
                 [{'text': 'License: Apache License 2.0',
                     'mode': curses.A_NORMAL}]]

        self._window_manager.display_window('About Combat Accountant', lines)
        return True

    def __add_monsters(self):
        '''
        Handler for an Party sub-menu entry.

        Modifies an existing monster list or creates a new monster list.

        Returns: True -- anything but None in a menu handler
        '''
        build_fight = PersonnelHandler(self._window_manager,
                                       self.world,
                                       PersonnelHandler.MONSTERs,
                                       self.__current_display)
        build_fight.handle_user_input_until_done()

        # Display the last fight on the main screen

        last_group_name = build_fight.get_group_name()
        if (last_group_name is not None and last_group_name != 'PCs' and
                last_group_name != 'NPCs'):
            self.__current_display = last_group_name

        self.__setup_PC_list(self.__current_display)
        self._draw_screen()
        return True

    def __add_NPCs(self):
        '''
        Handler for an Party sub-menu entry.

        Modifies the NPC list.

        Returns: True -- anything but None in a menu handler
        '''

        build_fight = PersonnelHandler(self._window_manager,
                                       self.world,
                                       PersonnelHandler.NPCs)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list(self.__current_display)  # It may have changed.
        self._draw_screen()  # Redraw current screen when done building fight.
        return True

    def __add_PCs(self):
        '''
        Handler for an Party sub-menu entry.

        Adds PCs to the PC list.

        Returns: True -- anything but None in a menu handler
        '''

        build_fight = PersonnelHandler(self._window_manager,
                                       self.world,
                                       PersonnelHandler.PCs)
        build_fight.handle_user_input_until_done()
        self.__setup_PC_list(self.__current_display)  # It may have changed.
        self._draw_screen()  # Redraw current screen when done building fight.
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
                     pane=None,  # CHAR_LIST, CHAR_DETAIL,
                                 #    CHAR_LIST|CHAR_DETAIL
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
        return True  # Keep going

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
                notes_type  # <string> 'fight-notes' or 'notes'
                ):
        '''
        Handler for an Equip sub-menu entry.

        Allows the user to modify a Fighter's notes or fight-notes.

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
                    cols / 2,  # arbitrary width
                    notes,     # initial string (w/ \n) for the window
                    'Notes',
                    '^G to exit')

        fighter.details[notes_type] = [x for x in notes.split('\n')]
        self._draw_screen()

        return True  # Menu handler's success returns anything but 'None'

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
        return False  # Leave

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
        monster_group_index, ignore = self._window_manager.menu(
                'Resurrect Which Fight',
                list(reversed(fight_name_menu)))
        if monster_group_index is None:
            return True

        monster_group = self.world.details['dead-monsters'][
                monster_group_index]

        if (self.world.get_creature_details_list(monster_group['name'])
                is not None):
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
            monster_group, ignore = self._window_manager.menu('Fights',
                                                              fight_name_menu)
            if monster_group is None:
                return True

        is_new = False if os.path.exists(FightHandler.timing_file) else True
        mode = 'w' if is_new else 'a'
        with open(FightHandler.timing_file, mode) as f:
            self.world.ruleset.set_timing_file(f, is_new)

            fight = FightHandler(self._window_manager,
                                 self.world,
                                 monster_group,
                                 None)  # Playback history
            fight.handle_user_input_until_done()

            self.world.ruleset.set_timing_file(None)

        self.__current_display = None

        # The fight may have changed the PC/NPC lists
        self.__setup_PC_list(self.__current_display)
        self.__first_page(MainHandler.CHAR_LIST | MainHandler.CHAR_DETAIL)
        self._draw_screen()  # Redraw current screen when done with the fight.

        return True  # Keep going

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
            result = self.world.ruleset.search_one_creature(
                    name,
                    'PCs',
                    creature,
                    look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for name in self.world.get_creature_details_list('NPCs'):
            creature = self.world.get_creature_details(name, 'NPCs')
            result = self.world.ruleset.search_one_creature(
                    name,
                    'NPCs',
                    creature,
                    look_for_re)
            if result is not None and len(result) > 0:
                all_results.extend(result)

        for fight_name in self.world.get_fights():
            for name in self.world.get_creature_details_list(fight_name):
                creature = self.world.get_creature_details(name, fight_name)
                result = self.world.ruleset.search_one_creature(
                        name,
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

            select_result, ignore = self._window_manager.menu(
                    menu_title,
                    result_menu,
                    starting_index=0,
                    skip_singles=False)
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
                    if name == ca_fighter.Venue.name:
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

                elif the_fight_itself is not None:
                    fight = ca_fighter.Venue(group,
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
            self.__current_display, ignore = self._window_manager.menu(
                                                    'Which Monster Group',
                                                    group_menu)
        else:
            self.__current_display = None

        self.__setup_PC_list(self.__current_display)
        self._draw_screen()

        # If this is a monster list, run a consistency check
        # if self.__current_display is not None:
        #    monsters = self.world.get_creature_details_list(
        #                                           self.__current_display)
        #    for name in monsters:
        #        creature = self.world.get_creature_details(
        #                                           name,
        #                                           self.__current_display)
        #        self.world.ruleset.is_creature_consistent(name, creature)

        return True


class MyArgumentParser(argparse.ArgumentParser):
    '''
    Code to add better error messages to argparse.
    '''
    def error(self,
              message   # string: message to display
              ):
        '''
        Displays an error message and exits.  Used by argparse to display
        internal error messages.
        '''
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
                     filename   # string: name of output data file
                                #   associated with tag
                     ):
        '''
        Saves the name of a snapshot of the game file.  The name is saved with
        a tag that describes the reason for the snapshot.

        Returns: nothing
        '''
        self.__snapshots[tag] = filename

    def make_bug_report(self,
                        history,           # list of action dicts for the
                                           #   most recently started fight
                                           #   (see Ruleset::do_action)
                        user_description,  # string w/ '\n' to separate lines;
                                           #   user description of bug

                        crash_snapshot,    # string: name of file to be
                                           #   saved as one last snapshot
                        file_tag=None      # string: add tag to filename
                        ):
        '''
        Gathers all the information required (I hope) to reproduce a bug and
        writes it to a file.

        Returns: the name of the file to which the bug summary was written.
        '''

        if crash_snapshot is not None:
            self.add_snapshot('crash', crash_snapshot)
            if history is None:
                with ca_json.GmJson(crash_snapshot) as crashfile:
                    if 'current-fight' in crashfile.read_data:
                        if 'history' in crashfile.read_data['current-fight']:
                            history = crashfile.read_data['current-fight'][
                                    'history']

        # Build the bug report

        bug_report = {
            'version':    VERSION,
            'world':      self.__source_filename,
            'history':    copy.deepcopy(history),
            'report':     user_description,
            'snapshots':  self.__snapshots
        }

        # Find a filename for the bug report

        keep_going = True
        count = 0
        extension = 'json'
        while keep_going:
            if file_tag is None:
                count_string = '%d' % count
            else:
                count_string = '%d-%s' % (count, file_tag)
            bug_report_game_file = timeStamped('bug_report',
                                               count_string,
                                               extension)
            if os.path.exists(bug_report_game_file):
                count += 1
            else:
                keep_going = False

        # Make a directory for the bug report

        extension = '.' + extension
        new_debug_folder = bug_report_game_file
        if new_debug_folder.endswith(extension):
            new_debug_folder = new_debug_folder[:-len(extension)]

        os.mkdir(new_debug_folder)

        # Copy the snapshot files into the bug report directory.

        new_snapshots = {}
        for key, path_name in self.__snapshots.iteritems():
            shutil.copy(path_name, new_debug_folder)
            folder_name, filename = os.path.split(path_name)
            new_snapshots[key] = filename
            # os.path.join(new_debug_folder, filename)

        bug_report['snapshots'] = new_snapshots

        # Dump the bug report into bug report file (in the directory)

        full_bug_report_game_file = os.path.join(new_debug_folder,
                                                 bug_report_game_file)
        with open(full_bug_report_game_file, 'w') as f:
            json.dump(bug_report, f, indent=2)

        return bug_report_game_file


class Options(object):
    def __init__(self,
                 global_options,    # dict, options for program
                 campaign_options   # dict, options for campaign
                 ):
        self.__global_options = global_options
        self.__campaign_options = campaign_options

    def get_option(self,
                   option_name  # string
                   ):
        # NOTE: campaign options override global options
        if option_name in self.__campaign_options:
            return self.__campaign_options[option_name]

        if option_name in self.__global_options:
            return self.__global_options[option_name]

        return None

    def set_campaign_option(self, option_name, option_value):
        self.__campaign_options[option_name] = option_value

    def set_global_option(self, option_name, option_value):
        self.__global_options[option_name] = option_value


# Main
if __name__ == '__main__':
    VERSION = '00.04.02 provisional'    # major version, minor version, bug fixes

    parser = MyArgumentParser()
    parser.add_argument(
            'filename',
            nargs='?',  # We get the filename elsewhere if you don't say here
            help='Input Game File containing characters and monsters')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)
    parser.add_argument(
            '-d', '--debug',
            help='Enable debugging features.  Debugging only.',
            action='store_true',
            default=False)
    parser.add_argument(
            '-m', '--maintain_game_file',
            help='Don\'t overwrite the input Game File.  Debugging only.',
            action='store_true',
            default=False)
    parser.add_argument('-p', '--playback',
                        help='Play history from bug report folder.')

    ARGS = parser.parse_args()

    # parser.print_help()
    # sys.exit(2)

    PP = pprint.PrettyPrinter(indent=3, width=150)

    playback_history = None

    program = None
    with CaGmWindowManager() as window_manager:
        ruleset = ca_gurps_ruleset.GurpsRuleset(window_manager)

        # Prefs
        # NOTE: When other things find their way into the prefs, the scope
        # of the read_prefs ca_json.GmJson will have to be larger
        prefs = {}
        filename = None
        report_text = None

        # Do we have a Playback file (like, we're playing back a bug)?

        if ARGS.playback is not None:
            if not os.path.isdir(ARGS.playback):
                window_manager.error(
                        ['Playback needs a folder name but "%s" is not one' %
                         ARGS.playback])
                sys.exit(2)

            # Find bug_report in directory
            search_path = os.path.join(ARGS.playback, 'bug_report*')
            files = glob.glob(search_path)
            if len(files) != 1:
                window_manager.error(
                        ['Playback folder expects 1 bug_report file, not %d' %
                         len(files)])
                sys.exit(2)

            # Extract information from bug_report file
            with ca_json.GmJson(files[0]) as bug_report:
                filename = bug_report.read_data['snapshots']['fight']
                filename = os.path.join(ARGS.playback, filename)
                playback_history = bug_report.read_data['history']
                if 'report' in bug_report.read_data:
                    report_text = bug_report.read_data['report']
        else:
            filename = ARGS.filename

            prefs_filename = 'gm-prefs.json'
            if not os.path.exists(prefs_filename):
                with open(prefs_filename, 'w') as f:
                    f.write('{ }')  # Provide a default preferences file

            with ca_json.GmJson(prefs_filename) as read_prefs:
                prefs = read_prefs.read_data

                # Get the Campaign's Name
                if filename is not None:
                    read_prefs.write_data = prefs
                    prefs['campaign'] = filename

                elif 'campaign' in prefs:
                    filename = prefs['campaign']

                if filename is None:
                    existing_file_menu = [('new file', False),
                                          ('existing file', True) ]
                    use_existing_file, ignore = window_manager.menu(
                            'Create New or Use Existing Campaign File',
                            existing_file_menu)

                    if use_existing_file:
                        filename_window = ca_gui.GetFilenameWindow(
                                window_manager)
                        filename = filename_window.get_filename(['.json',
                                                                 '.JSON'])

                    lines, cols = window_manager.getmaxyx()
                    while filename is None:
                        # create a new file
                        filename = window_manager.input_box(1,
                                                            cols-4,
                                                            'Campaign name')
                        if len(filename) <= 0:
                            # Guess we're not going to run the program
                            sys.exit(2)

                        if not filename.endswith('.json'):
                            filename = filename + '.json'

                        if os.path.exists(filename):
                            window_manager.error(['Game File "%s" exists' %
                                                  filename])
                            filename = None
                        else:
                            game_file = ca_json.GmJson(filename,
                                                       window_manager)
                            world_data = World.get_empty_world(
                                                    ruleset.get_sample_items())
                            game_file.open_write_json_and_close(world_data)

                    read_prefs.write_data = prefs
                    prefs['campaign'] = filename

        # Read the Campaign Data

        # If the program exits before we turn this to True, we probably
        # exited via a crash
        orderly_shutdown = False
        with ca_json.GmJson(filename, window_manager) as campaign:
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
            campaign_options = (None if 'options' not in world.details else
                                world.details['options'])
            # NOTE: |prefs| is not guaranteed to be writeable
            options = Options(prefs, campaign_options)
            ruleset.set_options(options)

            # Save the state of things when we leave since there wasn't a
            # horrible crash while reading the data.

            if ARGS.playback is not None:
                # Don't save the playback changes -- that way, you can re-play
                # the incident over and over without worry.
                world.dont_save_on_exit()
                # Safe to set this option since we're not writing it back
                options.set_global_option('verbose', True)
            elif ARGS.maintain_game_file:
                world.dont_save_on_exit()
            else:
                world.do_save_on_exit()

            if report_text is not None:
                naked_lines = report_text.split('\n')
                lines = []
                for line in naked_lines:
                    line = line.rstrip('\r')
                    line = line.rstrip('\n')
                    line = line.rstrip()
                    if len(line) > 0:
                        lines.append([{'text': line, 'mode': curses.A_NORMAL}])

                window_manager.display_window('Playing Back Bug Report', lines)


            if world.details['current-fight']['saved']:
                is_new = False if os.path.exists(FightHandler.timing_file) else True
                mode = 'w' if is_new else 'a'
                with open(FightHandler.timing_file, mode) as f:
                    world.ruleset.set_timing_file(f, is_new)

                    fight_handler = FightHandler(window_manager,
                                                 world,
                                                 None,
                                                 playback_history)
                    fight_handler.handle_user_input_until_done()

                    world.ruleset.set_timing_file(None)

            # Enter into the mainloop
            main_handler = MainHandler(window_manager, world)
            orderly_shutdown = main_handler.handle_user_input_until_done()

        # Write a crashdump of the shutdown
        if not orderly_shutdown:
            if program is not None:
                print '\n** Making crash report **'
                crash_filename = program.make_bug_report(
                        None, 'CRASH', filename, 'crash')
                print '   Written to: %s' % crash_filename

else:
    # Just to get some tests to pass
    class ARGS:
        debug = False
