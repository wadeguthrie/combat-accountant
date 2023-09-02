#! /usr/bin/python

import copy
import curses
import unittest

import ca   # combat accountant
import ca_debug
import ca_gurps_ruleset

'''
FWIW, I realize that many of the Mocks in here are actually Fakes.
'''

# TODO: test options

# TODO: there should be a test.reset() that would clear out the
# set_menu_response and the set_input_box_response values (and
# maybe some other stuff I'm not thinking about).  It should be called prior
# to each test's init.

# Save a fight
# TODO: test that saving a fight and starting up again doesn't change the
#       fight (pending actions, injuries, fight order) -- check out test_save

# Looting bodies
# TODO: test that looting bodies works:
#           * moving something from one body to another works properly
#           * only loot unconscious and dead monsters
# TODO: test that quitting a fight offers to loot and save when appropriate
#       and not when not:
#       (4 tests: loot, save; loot, no save; no loot, save; no loot, no save)

# Notes
# TODO: test that notes are saved properly

# TODO: test 'search'
# TODO: test 'resurrect fight'
# TODO: test equipping characters


class TestRuleset(ca_gurps_ruleset.GurpsRuleset):
    def __init__(self, window_manager):
        super(TestRuleset, self).__init__(window_manager)

    # Our test creatures aren't totally consistent so we don't want to mess
    # with the test.
    def is_creature_consistent(self,
                               name,     # string: creature's name
                               creature, # dict from Game File
                               fight_handler=None
                               ):
        return True

class TestPersonnelHandler(ca.PersonnelHandler):
    def __init__(self,
                 window_manager,
                 world,
                 creature_type  # one of: NPCs, PCs, or MONSTERs
                 ):
        super(TestPersonnelHandler, self).__init__(
                window_manager,
                world,
                creature_type,  # one of: NPCs, PCs, or MONSTERs
                )
        self.__command_ribbon_input = []
        self.__saved_thing = None

    def set_command_ribbon_input(self,
                                 character  # command ribbon input
                                 ):
        debug = ca_debug.Debug()
        #if character < 256:
        #    debug.print('\n  set_command_ribbon_input: add: %c' % character)
        #else:
        #    debug.print('\n  set_command_ribbon_input: add: %r' % character)

        if character in [curses.KEY_HOME, curses.KEY_UP, curses.KEY_DOWN,
                         curses.KEY_PPAGE, curses.KEY_NPAGE, curses.KEY_LEFT,
                         curses.KEY_RIGHT]:
            self.__command_ribbon_input.append(character)
        else:
            self.__command_ribbon_input.append(ord(character))

        #debug.print('  gives us a response queue of:')
        #debug.print('    ', end=' ')
        #queue = []
        #for c in self.__command_ribbon_input:
        #    queue.append(chr(c) if c < 256 else c)
        #debug.pprint(queue)

    def handle_user_input_until_done(self):
        debug = ca_debug.Debug()
        if len(self.__command_ribbon_input) == 0:
            debug.print ('** command ribbon input is empty, can\'t respond')
            assert False

        keep_going = True
        while keep_going:
            if len(self.__command_ribbon_input) <= 0:
                self._window_manager.error(
                        ['Empty handle_user_input_until_done queue'])
                return

            # FIFO queue
            string = self.__command_ribbon_input.pop(0)

            #if string < 256:
            #    debug.print('\n  handle_user_input_until_done: got %c' % string)
            #else:
            #    debug.print('\n  handle_user_input_until_done: got %r' % string)
            #debug.print('    gives us a response queue of:', end=' ')
            #queue = []
            #for c in self.__command_ribbon_input:
            #    queue.append(chr(c) if c < 256 else c)
            #debug.pprint(queue)

            if string in self._choices:
                keep_going = self._choices[string]['func']()
            elif string < 256:
                self._window_manager.error(
                        ['Invalid command: "%c" ' % chr(string)])
            else:
                self._window_manager.error(
                        ['Invalid command: "<%d>" ' % string])

        def set_obj_from_index(self,
                               thing,   # ThingsInFight (fighter or venue)
                               ):
            self.__saved_thing = thing

        def get_obj_from_index(self):
            saved_thing = self.__saved_thing
            self.__saved_thing = None
            return saved_thing


class WorldData(object):
    def __init__(self, world_dict):
        self.read_data = copy.deepcopy(world_dict)


class MockProgram(object):
    def __init__(self):
        pass

    def add_snapshot(self, tag, filename):
        pass

    def make_bug_report(self, history, user_description, snapshot, file_tag=None):
        return 'NO FILE'


class MockWorld(object):
    def __init__(self):
        self.playing_back = False


class MockFightHandler(object):
    def __init__(self):
        self.world = MockWorld()
        self.clear_opponents()
        self.__fighter_objects = {}

    def add_to_history(self, action):
        pass

    def clear_opponents(self):
        self.__opponents = {}  # group: {name: object, name: object}

    def get_fighter_object(self,
                           name,
                           group):
        index = 2 # arbitrary
        return index, self.__fighter_objects[group][name]

    def get_opponent_for(self,
                         fighter    # Fighter object
                         ):
        if fighter.group not in self.__opponents:
            return None

        if fighter.name not in self.__opponents[fighter.group]:
            return None

        return self.__opponents[fighter.group][fighter.name]

    def get_round(self):
        return 1 # Don't really need this for anything but timing

    def modify_index(self, adjustment):
        pass

    def pick_opponent(self):
        pass

    def set_fighter_object(self,
                           name,
                           group,
                           fighter_object):
        if group not in self.__fighter_objects:
            self.__fighter_objects[group] = {}
        self.__fighter_objects[group][name] = fighter_object

    def set_opponent_for(self,
                         fighter,   # Fighter object
                         opponent   # Fighter object
                         ):
        if fighter.group not in self.__opponents:
            self.__opponents[fighter.group] = {}
        self.__opponents[fighter.group][fighter.name] = opponent

    def wait_end_action(self,   # Public so it can be called by the ruleset.
                        name,           # String: name of fighter
                        group,          # String: group of fighter
                        in_place=False  # bool: move fighter to new init?
                        ):
        pass # Since we're not, yet, testing initiative holding


class MockMainGmWindow(object):
    def __init__(self, window_manager=None):
        pass

    def char_detail_home(self):
        pass

    def char_list_home(self):
        pass

    def clear(self):
        pass

    def command_ribbon(self):
        pass

    def status_ribbon(self, input_filename, maintain_json):
        pass

    def show_description(self,
                         character  # Fighter or Fight object
                         ):
        pass

    def show_creatures(self,
                       char_list,  # [ {'name': xxx,
                                   #    'group': xxx,
                                   #    'rawdata':xxx}, ...
                       current_index,
                       standout=False
                       ):
        pass


class MockGmWindow(object):
    def clear(self):
        pass

    def close(self):
        pass

    def command_ribbon(self):
        pass

    def getmaxyx(self):
        return 10, 10


class MockPersonnelGmWindow(MockGmWindow):
    def __init__(self):
        pass

    def status_ribbon(self,
                      group,            # name of group being modified,
                      template,         # name of template
                      input_filename,   # passthru to base class
                      maintain_json     # passthru to base class
                      ):
        pass

    def show_creatures(self,
                       new_creatures,   # {name: {rawdata}, ...} like in JSON
                       new_char_name,   # name of character to highlight
                       viewing_index    # index into creature list:
                                        #   dict: {'new'=True, index=0}
                       ):
        pass

    def char_detail_home(self):
        pass


class MockFightGmWindow(MockGmWindow):
    def __init__(self,
                 ruleset    # throw away
                 ):
        self.fighter_win_width = 10
        self.len_timer_leader = 1
        pass

    def start_fight(self):
        pass

    def show_fighters(self,
                      current_fighter,
                      opponent,
                      fighters,
                      index,
                      new_round):
        pass

    def round_ribbon(self,
                     fight_round,
                     next_PC_name,
                     input_filename,
                     maintain_json):
        pass

    def status_ribbon(self, input_filename, maintain_json):
        pass


class MockWindowManager(object):
    (FOUND_NO_ERROR,
     FOUND_EXPECTED_ERROR,
     FOUND_WRONG_ERROR,  # Error state won't advance from here
     FOUND_EXTRA_ERROR  # Error state won't advance from here
     ) = list(range(4))

    def __init__(self):
        self.__menu_responses = {}  # {menu_title: [selection, selection...]

        # {input_box_title: [selection, selection...]
        self.__input_box_responses = {}

        self.__char_responses = []  # array of characters
        self.__expected_error = []  # array of single-line strings
        self.error_state = MockWindowManager.FOUND_NO_ERROR

    def reset_error_state(self):
        self.error_state = MockWindowManager.FOUND_NO_ERROR

    def expect_error(self, string_array):
        '''
        Use this like so:
            mock_window_manager.expect_error(xxx)
            <do your test>
            assert(mock_window_manager.error_state ==
                   MockWindowManager.FOUND_EXPECTED_ERROR)
        '''
        self.__expected_error = string_array

    def error(self, string_array):
        debug = ca_debug.Debug()
        if len(self.__expected_error) > 0:
            if string_array == self.__expected_error:
                self.error_state = MockWindowManager.FOUND_EXPECTED_ERROR
            else:
                self.error_state == MockWindowManager.FOUND_WRONG_ERROR
                debug.print('\n** Found wrong error:')
                debug.pprint(string_array)

        elif self.error_state == MockWindowManager.FOUND_NO_ERROR:
            self.error_state == MockWindowManager.FOUND_EXTRA_ERROR

        elif self.error_state == MockWindowManager.FOUND_EXPECTED_ERROR:
            self.error_state == MockWindowManager.FOUND_EXTRA_ERROR
            debug.print('\n** Found extra error:')
            debug.pprint(string_array)

        else:
            debug.print('\n** Found another error:')
            debug.pprint(string_array)

    def get_build_fight_gm_window(self, command_ribbon_choices):
        return MockPersonnelGmWindow()

    def display_window(self,
                       title,
                       lines  # [{'text', 'mode'}, ...]
                       ):
        pass

    def clear_menu_responses(self):
        self.__menu_responses = {}

    def set_menu_response(self,
                          title,
                          selection  # SECOND part of string_results tuple
                          ):
        debug = ca_debug.Debug()
        # debug.print 'set_menu_response: title: %s, add selection:' % title
        # debug.print '    ',
        # debug.pprint(selection)

        if title not in self.__menu_responses:
            self.__menu_responses[title] = []
        self.__menu_responses[title].append(selection)

        # debug.print '  gives us a response queue of:'
        # debug.print '    ',
        # debug.pprint(self.__menu_responses)

    def menu(self,
             title,
             strings_results,  # array of tuples (string, return value)
             starting_index=0  # Who is selected when the menu starts
             ):
        debug = ca_debug.Debug()

        # If the menu has only one entry, just return that -- no need to check
        # responses.

        # Now, go check responses for longer menus

        if title not in self.__menu_responses:
            debug.print(('\n** menu: title "%s" not found in stored responses' %
                   title))
            debug.pprint(self.__menu_responses)
            debug.print_tb()
            assert False
        if len(self.__menu_responses[title]) == 0:
            debug.print(('\n** menu: responses["%s"] is empty, can\'t respond' %
                   title))
            debug.print_tb()
            assert False

        # FIFO queue
        menu_result = self.__menu_responses[title].pop(0)

        if isinstance(menu_result, dict):
            while 'menu' in menu_result:
                menu_result = self.menu('Which', menu_result['menu'])
                if menu_result is None:  # Bail out regardless of nesting level
                    return None, None    # Keep going

            if 'doit' in menu_result and menu_result['doit'] is not None:
                param = (None if 'param' not in menu_result
                         else menu_result['param'])
                menu_result = (menu_result['doit'])(param)

        #debug.print('  menu: title: "%s", returning:' % title, end=' ')
        #debug.pprint(menu_result)
        #debug.print('    gives us a response queue of:')
        #debug.print('      ', end=' ')
        #debug.pprint(self.__menu_responses)

        return menu_result, 0 # supply a dummy index to the menu

    def set_input_box_response(self,
                               title,
                               selection  # first part of string_results tuple
                               ):
        '''
        NOTE: |input_box| and |input_box_number| share the same response queue
        '''
        debug = ca_debug.Debug()
        # debug.print 'set_input_box_response: title: %s, add selection:' % title,
        # debug.pprint(selection)

        if title not in self.__input_box_responses:
            self.__input_box_responses[title] = []
        self.__input_box_responses[title].append(selection)

        # debug.print '  gives us a response queue of:'
        # debug.pprint(self.__input_box_responses)

    def input_box(self,
                  height,  # ignore
                  width,  # ignore
                  title):
        debug = ca_debug.Debug()
        if title not in self.__input_box_responses:
            debug.print(('** input_box: title "%s" not found in stored responses' %
                   title))
            assert False
        if len(self.__input_box_responses[title]) == 0:
            debug.print(('** input_boxes: responses["%s"] is empty, can\'t respond' %
                   title))
            assert False

        # FIFO queue
        result = self.__input_box_responses[title].pop(0)

        #debug.print('\n  input_box title: "%s", returning:' % title, end=' ')
        #debug.pprint(result)
        #debug.print('    gives us a response queue of:')
        #debug.print('    ', end=' ')
        #debug.pprint(self.__input_box_responses)

        return result

    def input_box_number(self,
                         height,  # ignore
                         width,  # ignore
                         title):
        debug = ca_debug.Debug()
        if title not in self.__input_box_responses:
            debug.print(('** input_box_number: title "%s" not found in stored responses' %
                   title))
            debug.pprint(self.__input_box_responses)
            assert False
        if len(self.__input_box_responses[title]) == 0:
            debug.print(('** input_box_number: responses["%s"] is empty, can\'t respond' %
                   title))
            assert False

        # FIFO queue
        result = self.__input_box_responses[title].pop(0)

        #debug.print('\n  input_box_number title: "%s", returning:' % title, end=' ')
        #debug.pprint(result)
        #debug.print('    gives us a response queue of:')
        #debug.print('    ', end=' ')
        #debug.pprint(self.__input_box_responses)

        return result

    def get_fight_gm_window(self,
                            ruleset,
                            command_ribbon_choices,
                            fight_handler):
        return MockFightGmWindow(ruleset)

    def get_main_gm_window(self, command_ribbon_choices):
        return MockMainGmWindow()  # it takes a 'window manager' param

    def set_char_response(self,
                          selection  # character
                          ):
        debug = ca_debug.Debug()
        # debug.print 'set_char_response: add selection:'
        # debug.print '    ',
        # debug.pprint(chr(selection))

        self.__char_responses.append(selection)

        # debug.print '  gives us a response queue of:'
        # debug.print '    ',
        # debug.pprint(self.__char_responses)

    def get_one_character(self):

        debug = ca_debug.Debug()
        if len(self.__char_responses) == 0:
            debug.print('** character responses is empty, can\'t respond')
            assert False
        result = self.__char_responses.pop()

        # debug.print 'get_one_character: returning:'
        # debug.print '    ',
        # debug.pprint(chr(result))
        # debug.print '  gives us a response queue of:'
        # debug.print '    ',
        # debug.pprint(self.__char_responses)

        return result


class GmTestCaseCommon(unittest.TestCase):  # Derive from unittest.TestCase
    def setUp(self):
        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        self._crawling_attack_mod = -4
        self._crawling_defense_mod = -3

        self._colt_pistol_acc = 3
        self._vodou_priest_fighter_pistol_skill = 15
        self._vodou_priest_armor_dr = 3
        self._vodou_priest_ht = 11

        self._vodou_pistol_index = 0
        self._vodou_priest_ammo_index = 1
        self._vodou_armor_index = 2

        self._vodou_priest_ammo_count = 5
        self._vodou_priest_initial_shots = 9

        self._vodou_priest_spell_index = {
            "Awaken": 0,
            "Animate Shadow": 1,
            "Explosive Lightning": 2,
            "Itch": 3,
            "Death Vision": 4,
        }
        self._vodou_priest_fighter = {
            "fight-notes": [],
            "gcs-file": None,
            "notes": [],
            "ignored-equipment": [],
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "open-container": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": [],
            "current-weapon": 0,
            "armor-index": [],
            "preferred-weapon-index": [],
            "preferred-armor-index": [],
            "stuff": [
                 {"name": "pistol, Colt 170D",
                  "type": {
                      "ranged weapon": {"damage": {"dice": {"plus": 4,
                                                            "num_dice": 1,
                                                            "type": "pi"}},
                                        "skill": {"Guns (Pistol)": 0}}
                      },
                  "acc": self._colt_pistol_acc,
                  "ammo": {"name": "C Cell",
                           "shots": self._vodou_priest_initial_shots},
                  "clip": {"name": "C Cell",
                           "type": {"misc": 1},
                           "shots_left": self._vodou_priest_initial_shots,
                           "shots": self._vodou_priest_initial_shots,
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "reload_type": 2,
                  "count": 1,
                  "owners": 1,
                  "notes": None},  # index 0
                 {"name": "C Cell",
                  "type": {"misc": 1},
                  "count": self._vodou_priest_ammo_count,
                  "notes": "",
                  "owners": None},  # index 1
                 {"count": 1,
                  "type": {"armor": {"dr": self._vodou_priest_armor_dr}},
                  "notes": "Enchanted w/fortify spell [M66]",
                  "name": "Sport coat/Jeans"}, # index 2
            ],
            "spells": [
              {
                "skill": 18,
                "name": "Awaken"
              },
              {
                "skill": 16,
                "name": "Animate Shadow"
              },
              {
                "skill": 16,
                "name": "Explosive Lightning"
              },
              {
                "skill": 12,
                "name": "Itch"
              },
              {
                "skill": 16,
                "name": "Death Vision"
              },
            ],
            "skills": {"Guns (Pistol)":
                       self._vodou_priest_fighter_pistol_skill,
                       "Brawling": 12},
            "advantages": {"Combat Reflexes": 15},
            "state": "alive",
            "posture": "standing",
            "current": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10,
                "ht": self._vodou_priest_ht, "st": 10,
                "dx": 11, "basic-speed": 5.5, "basic-move": 5
            },
            "permanent": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10,
                "ht": self._vodou_priest_ht, "st": 10,
                "dx": 11, "basic-speed": 5.5, "basic-move": 5
            },
            "timers": [],
            "check_for_death": False,
            "opponent": None
        }

        # self._one_more_guy is identical to the Vodou Priest Fighter except
        # that his dex is different.  I know that makes the calculation for
        # basic speed wrong but that's not really the point of this exercise
        self._one_more_guy = {
            "fight-notes": [],
            "gcs-file": None,
            "notes": [],
            "ignored-equipment": [],
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "open-container": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": [],
            "current-weapon": 0,
            "armor-index": [],
            "preferred-weapon-index": [],
            "preferred-armor-index": [],
            "stuff": [
                 {"name": "pistol, Colt 170D",
                  "type": {"ranged weapon": {"damage": {"dice": {"plus": 4,
                                                                 "num_dice": 1,
                                                                 "type": "pi"}},
                                             "skill": {"Guns (Pistol)": 0}}
                           },
                  "damage": {"dice": "1d+4"},
                  "acc": 3,
                  "ammo": {"name": "C Cell", "shots": 9},
                  "clip": {"name": "C Cell",
                           "shots_left": 9, "shots": 9,
                           "type": {"misc": 1},
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "reload_type": 2,
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "C Cell", "type": {"misc": 1}, "count": 5, "notes": "",
                  "owners": None}
            ],
            "skills": {"Guns (Pistol)": 15, "Brawling": 12},
            "advantages": {"Combat Reflexes": 15},
            "state": "alive",
            "posture": "standing",
            "current": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10, "ht": 11, "st": 10,
                "dx": 12, "basic-speed": 5.5
            },
            "permanent": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10, "ht": 11, "st": 10,
                "dx": 12, "basic-speed": 5.5
            },
            "timers": [],
            "check_for_death": False,
            "opponent": None
        }
        self._bokor_fighter = {
            "fight-notes": [],
            "gcs-file": None,
            "notes": [],
            "ignored-equipment": [],
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "open-container": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": [],
            "current-weapon": 0,
            "armor-index": [],
            "preferred-weapon-index": [],
            "preferred-armor-index": [],
            "stuff": [
                 {"name": "pistol, Kalashnikov Makarov",
                  "type": {"ranged weapon": {"damage": {"dice": {"plus": 3,
                                                                 "num_dice": 1,
                                                                 "type": "pi"}},
                                             "skill": {"Guns (Pistol)": 0}}
                           },
                  "acc": 2,
                  "ammo": {"name": "C Cell", "shots": 8},
                  "clip": {"name": "C Cell",
                           "shots_left": 8, "shots": 8,
                           "type": {"misc": 1},
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "reload_type": 2,
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "C Cell", "type": {"misc": 1}, "count": 5, "notes": "",
                  "owners": None}
            ],
            "skills": {"Guns (Pistol)": 13, "Brawling": 12},
            "advantages": {"Combat Reflexes": 15},
            "state": "alive",
            "posture": "standing",
            "current": {
                "fp": 11, "iq": 12, "wi": 12, "hp": 10, "ht": 11, "st": 10,
                "dx": 10, "basic-speed": 5.25
            },
            "permanent": {
                "fp": 11, "iq": 12, "wi": 12, "hp": 10, "ht": 11, "st": 10,
                "dx": 10, "basic-speed": 5.25
            },
            "timers": [],
            "check_for_death": False,
            "opponent": None
        }

        self._tank_fighter_pistol_index = 0
        self._tank_fighter_sickstick_index = 1
        #self.__tank_fighter_stuff_count = 3

        self._tank_fighter = {
            "fight-notes": [],
            "gcs-file": None,
            "notes": [],
            "ignored-equipment": [],
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "open-container": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": [],
            "current-weapon": 0,
            "armor-index": [],
            "preferred-weapon-index": [],
            "preferred-armor-index": [],
            "stuff": [
                 {"name": "pistol, Sig D65",  # the index of this is stored
                                              # in _tank_fighter_pistol_index
                  "type": {"ranged weapon": {"damage": {"dice": {"plus": 4,
                                                                 "num_dice": 1,
                                                                 "type": "pi" }},
                                             "skill": {"Guns (Pistol)": 0}},
                           },
                  "acc": 4,
                  "ammo": {"name": "C Cell", "shots": 9},
                  "clip": {"name": "C Cell",
                           "shots_left": 9, "shots": 9,
                           "type": {"misc": 1},
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "reload_type": 2,
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "sick stick", # the index of this is stored in
                                        # _tank_fighter_sickstick_index
                  "type": {
                    "swung weapon": {"damage": {"dice": {"plus": 1,
                                                         "num_dice": 1,
                                                         "type": "fat"}},
                                     "skill": {"Axe/Mace": 0}}
                    },
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "C Cell", "type": {"misc": 1}, "count": 5, "notes": "",
                  "owners": None}
            ],
            "skills": {"Guns (Pistol)": 16, "Brawling": 16, "Axe/Mace": 14},
            "advantages": {"Combat Reflexes": 15},
            "state": "alive",
            "posture": "standing",
            "current": {
                "st": 10, "dx": 12, "iq": 12, "wi": 12, "ht": 11, "fp": 11,
                "hp": 11, "basic-speed": 5.75
            },
            "permanent": {
                "fp": 11, "iq": 12, "wi": 12, "hp": 11, "ht": 11, "st": 10,
                "dx": 12, "basic-speed": 5.75
            },
            "timers": [],
            "check_for_death": False,
            "opponent": None
        }

        self._thief_knife_skill = 14

        self._thief_fighter = {
            "fight-notes": [],
            "gcs-file": None,
            "notes": [],
            "ignored-equipment": [],
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "open-container": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": [],
            "current-weapon": 0,
            "armor-index": [],
            "preferred-weapon-index": [],
            "preferred-armor-index": [],
            "stuff": [
                 {"name": "pistol, Baretta DX 192",
                  "type": {"ranged weapon": {"damage": {"dice": {"plus": 4,
                                                                 "num_dice": 1,
                                                                 "type": "pi"}},
                                             "skill": {"Guns (Pistol)": 0}}
                                             },
                  "acc": 2,
                  "ammo": {"name": "C Cell", "shots": 8},
                  "clip": {"name": "C Cell",
                           "shots_left": 8, "shots": 8,
                           "type": {"misc": 1},
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "reload_type": 2,
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "Large Knife",
                  "type": {
                    "swung weapon": {"damage": {"st": "sw",
                                                "plus": -2,
                                                "type": "cut"},
                                     "skill": {"Knife": 0}},
                    "thrust weapon": {"damage": {"st": "thr",
                                                 "plus": 0,
                                                 "type": "imp"},
                                      "skill": {"Knife": 0}}
                    },
                  #"damage": {"dice": "1d-2", "type": "imp"},
                  "parry": -1,
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"count": 1,
                  "name": "brass knuckles",
                  "notes": "B271",
                  "parry": 0,
                  "owners": None,
                  "type": {
                    #"thrust weapon": {"damage": {"st": "thr", "plus": 1, "type": "cr"}}
                    "thrust weapon": {"damage": {"st": "thr",
                                                 "plus": 0,
                                                 "type": "cr"},
                                      "skill": {"Brawling": 0,
                                                "Boxing": 0,
                                                "Karate": 0}}
                    }
                  },
                 {"name": "C Cell", "type": {"misc": 1}, "count": 5, "notes": "",
                  "owners": None}
            ],
            "skills": {"Guns (Pistol)": 12,
                       "Brawling": 14,
                       "Knife": self._thief_knife_skill},
            "advantages": {},
            "state": "alive",
            "posture": "standing",
            "current": {
                "fp": 11, "iq": 12, "wi": 12, "hp": 12, "ht": 11, "st": 10,
                "dx": 12, "basic-speed": 5.75
            },
            "permanent": {
                "fp": 11, "iq": 12, "wi": 12, "hp": 12, "ht": 11, "st": 10,
                "dx": 12, "basic-speed": 5.75
            },
            "timers": [],
            "check_for_death": False,
            "opponent": None
        }

        # WORLD: 1
        self.base_world_dict = {
          "options": {},
          "templates": {
            "Arena Combat": {
              "VodouCleric": {
                "permanent": {
                  "fp": {"type": "value", "value": 12},
                  "iq": {"type": "value", "value": 13},
                  "wi": {"type": "value", "value": 13},
                  "hp": {"type": "value", "value": 10},
                  "ht": {"type": "value", "value": 11},
                  "st": {"type": "value", "value": 10},
                  "dx": {"type": "value", "value": 11},
                  "basic-speed": {"type": "value", "value": 5.5}
                },
                "timers": {"type": "value", "value": []},
              },
            }
          },  # Templates
          "PCs": {
            "Vodou Priest": self._vodou_priest_fighter,
            "One More Guy": self._one_more_guy,
          },  # PCs
          "dead-monsters": [
            {"name": "Arena Attack Monsters",
             "fight": {
              "5-Tank-B": {
                "state": "alive",
                "current": {"fp": 11, "iq": 12, "wi": 12, "hp": 11,
                            "ht": 11, "st": 10, "dx": 12},
                "permanent": {"fp": 11, "iq": 12, "wi": 12, "hp": 11,
                              "ht": 11, "st": 10, "dx": 12},
              },  # 5-Tank-B
              "date": None
              }
             }  # Arena Attack Monsters
          ],  # dead-monsters
          "current-fight": {
            "index": 0,
            "monsters": "Anybody",
            "fighters": [
              {"group": "Anybody", "name": "Bokor Fighter"},
              {"group": "PCs", "name": "Vodou Priest"},
              {"group": "PCs", "name": "One More Guy"},
              {"group": "Anybody", "name": "Tank Fighter"},
            ],
            "saved": False,
            "round": 0,
            "history": [
              "--- Round 1 ---"
            ]
          },  # current-fight
          "NPCs": {
            "Bokor Requiem": {
                "state": "alive",
                "current":
                    {"fp": 11, "iq": 12, "wi": 12, "hp": 11,
                     "ht": 11, "st": 10, "dx": 12},
                "permanent":
                    {"fp": 11, "iq": 12, "wi": 12, "hp": 11,
                     "ht": 11, "st": 10, "dx": 12},
                "timers": []
            },
            "One More Guy": self._one_more_guy
          },  # NPCs
          "fights": {
            "Dima's Crew": {
              "monsters": {
                "Bokor Fighter": self._bokor_fighter,
                "Tank Fighter": self._tank_fighter,
                "One More Guy": {"redirect": "NPCs"}
              }
            },
            "1st Hunting Party": {
              "monsters": {
                "5: Amelia": self._thief_fighter,
              }
            }
          }  # fights
        }  # End of the world

        # WORLD: 2
        self.init_world_dict = {
            # Don't need dead-monsters, equipment, names
            'templates': {
                'dudes': {
                    'a dude': copy.deepcopy(self._bokor_fighter)
                },
            },
            'PCs': {
                # 5.25, 10, rand=1
                'Manny': copy.deepcopy(self._bokor_fighter),

                # 5.75, 12, rand=2
                'Jack': copy.deepcopy(self._tank_fighter),

                # 5.5, 12, rand=4
                'Moe': copy.deepcopy(self._one_more_guy),
            },
            'NPCs': {
                # Same body for these as the PCs and horseman fights
                'Groucho': copy.deepcopy(self._tank_fighter),
                'Zeppo': copy.deepcopy(self._thief_fighter),
                'Chico': copy.deepcopy(self._bokor_fighter),
            },
            'fights': {
                'horsemen': {
                  'monsters': {
                    # 5.75, 12, rand=4
                    'Famine': copy.deepcopy(self._thief_fighter),

                    # 5.5, 11, rand=4
                    'Pestilence': copy.deepcopy(self._vodou_priest_fighter),
                  }
                }
            },
            'current-fight': {
                # Needed
                'saved': False,
                'history': [],  # Needed (maybe)

                'index': 1,
                'fighters': [],
                'round': 2,
                'monsters': 'horsemen',
            },
        }

        # WORLD: 3
        self.init_world_dict_2 = {
            # Don't need templates, dead-monsters, equipment, names
            'PCs': {
                # 5.5, 11, rand=2
                'Bob': copy.deepcopy(self._vodou_priest_fighter),

                # 5.75, 12, rand=3
                'Ted': copy.deepcopy(self._tank_fighter),
            },
            'fights': {
                'marx': {
                  'monsters': {
                    # 5.5, 12, rand=4
                    'Groucho': copy.deepcopy(self._one_more_guy),

                    # 5.75, 12, rand=5
                    'Harpo': copy.deepcopy(self._thief_fighter),

                    # 5.25, 10, rand=3
                    'Chico': copy.deepcopy(self._bokor_fighter),
                  }
                }
            },
            'current-fight': {
                # Needed
                'saved': False,
                'history': [],  # Needed (maybe)

                # Not needed if not saved
                'index': 1,
                'fighters': [],
                'round': 2,
                'monsters': 'marx',
            },
        }  # End of world

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)

    def tearDown(self):
        pass

    def _are_equal(self, lhs, rhs):
        debug = ca_debug.Debug()
        if isinstance(lhs, dict):
            if not isinstance(rhs, dict):
                debug.print('** lhs is a dict but rhs is not')
                debug.print('\nlhs')
                debug.pprint(lhs)
                debug.print('\nrhs')
                debug.pprint(rhs)
                return False
            for key in rhs.keys():
                if key not in lhs:
                    debug.print('** KEY "%s" not in lhs' % key)
                    debug.print('\nlhs')
                    debug.pprint(lhs)
                    debug.print('\nrhs')
                    debug.pprint(rhs)
                    return False
            are_equal = True
            for key in lhs.keys():
                if key not in rhs:
                    debug.print('** KEY "%s" not in rhs' % key)
                    debug.print('\nlhs')
                    debug.pprint(lhs)
                    debug.print('\nrhs')
                    debug.pprint(rhs)
                    are_equal = False
                elif not self._are_equal(lhs[key], rhs[key]):
                    debug.print('lhs[%r] != rhs[%r]' % (key, key))
                    debug.print('\nlhs')
                    debug.pprint(lhs)
                    debug.print('\nrhs')
                    debug.pprint(rhs)
                    are_equal = False
            return are_equal

        elif isinstance(lhs, list):
            if not isinstance(rhs, list):
                debug.print('** lhs is a list but rhs is not')
                debug.print('\nlhs')
                debug.pprint(lhs)
                debug.print('\nrhs')
                debug.pprint(rhs)
                return False
            if len(lhs) != len(rhs):
                debug.print('** length lhs=%d != len rhs=%d' % (len(lhs), len(rhs)))
                debug.print('\nlhs')
                debug.pprint(lhs)
                debug.print('\nrhs')
                debug.pprint(rhs)
                return False
            are_equal = True
            for i in range(len(lhs)):
                if not self._are_equal(lhs[i], rhs[i]):
                    debug.print('** lhs[%d] != rhs[%d]' % (i, i))
                    debug.print('\nlhs')
                    debug.pprint(lhs)
                    debug.print('\nrhs')
                    debug.pprint(rhs)
                    are_equal = False
            return are_equal

        else:
            if lhs != rhs:
                debug.print('** lhs=%r != rhs=%r' % (lhs, rhs))
                debug.print('\nlhs')
                debug.pprint(lhs)
                debug.print('\nrhs')
                debug.pprint(rhs)
                return False
            else:
                return True

    def _is_in_dead_monsters(self, world_obj, fight_name):
        for fight in world_obj.read_data['dead-monsters']:
            if fight_name == fight['name']:
                return True
        return False

    def _get_current_weapon(self,
                             fighter # Fighter object
                             ):
        # NOTE: assumes a single weapon
        weapons = fighter.get_current_weapons()
        weapon_indexes = fighter.get_current_weapon_indexes()
        weapon = None if len(weapons) == 0 else weapons[0]
        weapon_index = None if len(weapon_indexes) == 0 else weapon_indexes[0]
        return weapon, weapon_index


