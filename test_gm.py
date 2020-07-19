#! /usr/bin/python

import argparse
import copy
import curses
import pprint
import random
import unittest

import ca   # combat accountant
import ca_fighter
import ca_gurps_ruleset
import ca_timers

'''
FWIW, I realize that many of the Mocks in here are actually Fakes.
'''

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

# -- OutfitCharactersHandler --
# TODO: test that adding something actually adds the right thing and that it's
#       permenant
# TODO: test that removing something works

# TODO: test 'search'
# TODO: test 'resurrect fight'
# TODO: test equipping characters


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

    def set_command_ribbon_input(self,
                                 character  # command ribbon input
                                 ):
        if ARGS.verbose:
            if character < 256:
                print '\n  set_command_ribbon_input: add: %c' % character
            else:
                print '\n  set_command_ribbon_input: add: %r' % character

        if character in [curses.KEY_HOME, curses.KEY_UP, curses.KEY_DOWN,
                         curses.KEY_PPAGE, curses.KEY_NPAGE, curses.KEY_LEFT,
                         curses.KEY_RIGHT]:
            self.__command_ribbon_input.append(character)
        else:
            self.__command_ribbon_input.append(ord(character))

        if ARGS.verbose:
            print '  gives us a response queue of:'
            print '    ',
            queue = []
            for c in self.__command_ribbon_input:
                queue.append(chr(c) if c < 256 else c)
            PP.pprint(queue)

    def handle_user_input_until_done(self):
        if len(self.__command_ribbon_input) == 0:
            print ('** command ribbon input is empty, can\'t respond')
            assert False

        keep_going = True
        while keep_going:
            if len(self.__command_ribbon_input) <= 0:
                self._window_manager.error(
                        ['Empty handle_user_input_until_done queue'])
                return

            # FIFO queue
            string = self.__command_ribbon_input.pop(0)

            if ARGS.verbose:
                if string < 256:
                    print '\n  handle_user_input_until_done: got %c' % string
                else:
                    print '\n  handle_user_input_until_done: got %r' % string
                print '    gives us a response queue of:',
                queue = []
                for c in self.__command_ribbon_input:
                    queue.append(chr(c) if c < 256 else c)
                PP.pprint(queue)

            if string in self._choices:
                keep_going = self._choices[string]['func']()
            elif string < 256:
                self._window_manager.error(
                        ['Invalid command: "%c" ' % chr(string)])
            else:
                self._window_manager.error(
                        ['Invalid command: "<%d>" ' % string])


class WorldData(object):
    def __init__(self, world_dict):
        self.read_data = copy.deepcopy(world_dict)


class MockProgram(object):
    def __init__(self):
        pass

    def add_snapshot(self, tag, filename):
        pass

    def make_bug_report(self, history, user_description):
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
                                   #    'details':xxx}, ...
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
                       new_creatures,   # {name: {details}, ...} like in JSON
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
     ) = range(4)

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
        if len(self.__expected_error) > 0:
            if string_array == self.__expected_error:
                self.error_state = MockWindowManager.FOUND_EXPECTED_ERROR
            else:
                self.error_state == MockWindowManager.FOUND_WRONG_ERROR
                print '\n** Found wrong error:'
                PP.pprint(string_array)

        elif self.error_state == MockWindowManager.FOUND_NO_ERROR:
            self.error_state == MockWindowManager.FOUND_EXTRA_ERROR

        elif self.error_state == MockWindowManager.FOUND_EXPECTED_ERROR:
            self.error_state == MockWindowManager.FOUND_EXTRA_ERROR
            print '\n** Found extra error:'
            PP.pprint(string_array)

        else:
            print '\n** Found another error:'
            PP.pprint(string_array)

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
        # print 'set_menu_response: title: %s, add selection:' % title
        # print '    ',
        # PP.pprint(selection)

        if title not in self.__menu_responses:
            self.__menu_responses[title] = []
        self.__menu_responses[title].append(selection)

        # print '  gives us a response queue of:'
        # print '    ',
        # PP.pprint(self.__menu_responses)

    def menu(self,
             title,
             strings_results,  # array of tuples (string, return value)
             starting_index=0  # Who is selected when the menu starts
             ):
        if ARGS.verbose:
            print '\n  menu title: "%s"' % title

        if title not in self.__menu_responses:
            print ('\n** menu: title "%s" not found in stored responses' %
                   title)
            PP.pprint(self.__menu_responses)
            assert False
        if len(self.__menu_responses[title]) == 0:
            print ('\n** menu: responses["%s"] is empty, can\'t respond' %
                   title)
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

        if ARGS.verbose:
            print '  menu: title: "%s", returning:' % title,
            PP.pprint(menu_result)
            print '    gives us a response queue of:'
            print '      ',
            PP.pprint(self.__menu_responses)

        return menu_result, 0 # supply a dummy index to the menu

    def set_input_box_response(self,
                               title,
                               selection  # first part of string_results tuple
                               ):
        '''
        NOTE: |input_box| and |input_box_number| share the same response queue
        '''
        # print 'set_input_box_response: title: %s, add selection:' % title,
        # PP.pprint(selection)

        if title not in self.__input_box_responses:
            self.__input_box_responses[title] = []
        self.__input_box_responses[title].append(selection)

        # print '  gives us a response queue of:'
        # PP.pprint(self.__input_box_responses)

    def input_box(self,
                  height,  # ignore
                  width,  # ignore
                  title):
        if title not in self.__input_box_responses:
            print ('** input_box: title "%s" not found in stored responses' %
                   title)
            assert False
        if len(self.__input_box_responses[title]) == 0:
            print ('** input_boxes: responses["%s"] is empty, can\'t respond' %
                   title)
            assert False

        # FIFO queue
        result = self.__input_box_responses[title].pop(0)

        if ARGS.verbose:
            print '\n  input_box title: "%s", returning:' % title,
            PP.pprint(result)
            print '    gives us a response queue of:'
            print '    ',
            PP.pprint(self.__input_box_responses)

        return result

    def input_box_number(self,
                         height,  # ignore
                         width,  # ignore
                         title):
        if title not in self.__input_box_responses:
            print ('** input_box_number: title "%s" not found in stored responses' %
                   title)
            assert False
        if len(self.__input_box_responses[title]) == 0:
            print ('** input_box_number: responses["%s"] is empty, can\'t respond' %
                   title)
            assert False

        # FIFO queue
        result = self.__input_box_responses[title].pop(0)

        if ARGS.verbose:
            print '\n  input_box_number title: "%s", returning:' % title,
            PP.pprint(result)
            print '    gives us a response queue of:'
            print '    ',
            PP.pprint(self.__input_box_responses)

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
        # print 'set_char_response: add selection:'
        # print '    ',
        # PP.pprint(chr(selection))

        self.__char_responses.append(selection)

        # print '  gives us a response queue of:'
        # print '    ',
        # PP.pprint(self.__char_responses)

    def get_one_character(self):

        if len(self.__char_responses) == 0:
            print '** character responses is empty, can\'t respond'
            assert False
        result = self.__char_responses.pop()

        # print 'get_one_character: returning:'
        # print '    ',
        # PP.pprint(chr(result))
        # print '  gives us a response queue of:'
        # print '    ',
        # PP.pprint(self.__char_responses)

        return result


class GmTestCase(unittest.TestCase):  # Derive from unittest.TestCase
    def setUp(self):
        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        self.__crawling_attack_mod = -4
        self.__crawling_defense_mod = -3

        self.__colt_pistol_acc = 3
        self.__vodou_priest_fighter_pistol_skill = 15
        self.__vodou_priest_armor_dr = 3
        self.__vodou_priest_ht = 11

        self.__vodou_pistol_index = 0
        self.__vodou_priest_ammo_index = 1
        self.__vodou_armor_index = 2

        self.__vodou_priest_ammo_count = 5
        self.__vodou_priest_initial_shots = 9

        self.__vodou_priest_spell_index = {
            "Awaken": 0,
            "Animate Shadow": 1,
            "Explosive Lightning": 2,
            "Itch": 3,
            "Death Vision": 4,
        }
        self.__vodou_priest_fighter = {
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": None,
            "armor-index": None,
            "stuff": [
                 {"name": "pistol, Colt 170D",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": self.__colt_pistol_acc,
                  "ammo": {"name": "C Cell",
                           "shots_left": self.__vodou_priest_initial_shots,
                           "shots": self.__vodou_priest_initial_shots},
                  "clip": {"name": "C Cell",
                           "type": "misc",
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": 1,
                  "notes": None},  # index 0
                 {"name": "C Cell",
                  "type": "misc",
                  "count": self.__vodou_priest_ammo_count,
                  "notes": "",
                  "owners": None},  # index 1
                 {"count": 1,
                  "type": "armor",
                  "notes": "Enchanted w/fortify spell [M66]",
                  "dr": self.__vodou_priest_armor_dr,
                  "name": "Sport coat/Jeans"}  # index 2
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
                       self.__vodou_priest_fighter_pistol_skill,
                       "Brawling": 12},
            "advantages": {"Combat Reflexes": 15},
            "state": "alive",
            "posture": "standing",
            "current": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10,
                "ht": self.__vodou_priest_ht, "st": 10,
                "dx": 11, "basic-speed": 5.5, "basic-move": 5
            },
            "permanent": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10,
                "ht": self.__vodou_priest_ht, "st": 10,
                "dx": 11, "basic-speed": 5.5, "basic-move": 5
            },
            "timers": [],
            "check_for_death": False,
            "opponent": None
        }

        # self.__one_more_guy is identical to the Vodou Priest Fighter except
        # that his dex is different.  I know that makes the calculation for
        # basic speed wrong but that's not really the point of this exercise
        self.__one_more_guy = {
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": None,
            "weapon-armor": None,
            "stuff": [
                 {"name": "pistol, Colt 170D",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": 3,
                  "ammo": {"name": "C Cell", "shots_left": 9, "shots": 9},
                  "clip": {"name": "C Cell",
                           "type": "misc",
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
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
        self.__bokor_fighter = {
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": None,
            "armor-index": None,
            "stuff": [
                 {"name": "pistol, Kalashnikov Makarov",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+3"},
                  "acc": 2,
                  "ammo": {"name": "C Cell", "shots_left": 8, "shots": 8},
                  "clip": {"name": "C Cell",
                           "type": "misc",
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
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

        self.__tank_fighter_pistol_index = 0
        self.__tank_fighter_stuff_count = 3

        self.__tank_fighter = {
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": None,
            "armor-index": None,
            "stuff": [
                 {"name": "pistol, Sig D65",  # the index of this is stored
                                              # in __tank_fighter_pistol_index
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": 4,
                  "ammo": {"name": "C Cell", "shots_left": 9, "shots": 9},
                  "clip": {"name": "C Cell",
                           "type": "misc",
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "sick stick",
                  "type": "melee weapon",
                  "damage": {"dice": "1d+1 fat"},
                  "skill": "Axe/Mace",
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
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

        self.__thief_knife_skill = 14

        self.__thief_fighter = {
            "shock": 0,
            "stunned": False,
            "actions_this_turn": [],
            "aim": {"rounds": 0, "braced": False},
            "weapon-index": None,
            "armor-index": None,
            "stuff": [
                 {"name": "pistol, Baretta DX 192",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": 2,
                  "ammo": {"name": "C Cell", "shots_left": 8, "shots": 8},
                  "clip": {"name": "C Cell",
                           "type": "misc",
                           "count": 1,
                           "notes": "",
                           "owners": None},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "Large Knife",
                  "type": "melee weapon",
                  "damage": {"dice": "1d-2", "type": "imp"},
                  "skill": "Knife",
                  "parry": -1,
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"count": 1,
                  "name": "brass knuckles",
                  "notes": "B271",
                  "damage": {"thr": {"plus": 0, "type": "cr"}},
                  "parry": 0,
                  "skill": "Karate",
                  "owners": None,
                  "type": "melee weapon"},
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
                  "owners": None}
            ],
            "skills": {"Guns (Pistol)": 12,
                       "Brawling": 14,
                       "Knife": self.__thief_knife_skill},
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
            "Vodou Priest": self.__vodou_priest_fighter,
            "One More Guy": self.__one_more_guy,
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
              "--- Round 0 ---"
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
            "One More Guy": self.__one_more_guy
          },  # NPCs
          "fights": {
            "Dima's Crew": {
              "monsters": {
                "Bokor Fighter": self.__bokor_fighter,
                "Tank Fighter": self.__tank_fighter,
                "One More Guy": {"redirect": "NPCs"}
              }
            },
            "1st Hunting Party": {
              "monsters": {
                "5: Amelia": self.__thief_fighter,
              }
            }
          }  # fights
        }  # End of the world

        # WORLD: 2
        self.init_world_dict = {
            # Don't need dead-monsters, equipment, names
            'templates': {
                'dudes': {
                    'a dude': copy.deepcopy(self.__bokor_fighter)
                },
            },
            'PCs': {
                # 5.25, 10, rand=1
                'Manny': copy.deepcopy(self.__bokor_fighter),

                # 5.75, 12, rand=2
                'Jack': copy.deepcopy(self.__tank_fighter),

                # 5.5, 12, rand=4
                'Moe': copy.deepcopy(self.__one_more_guy),
            },
            'NPCs': {
                # Same body for these as the PCs and horseman fights
                'Groucho': copy.deepcopy(self.__tank_fighter),
                'Zeppo': copy.deepcopy(self.__thief_fighter),
                'Chico': copy.deepcopy(self.__bokor_fighter),
            },
            'fights': {
                'horsemen': {
                  'monsters': {
                    # 5.75, 12, rand=4
                    'Famine': copy.deepcopy(self.__thief_fighter),

                    # 5.5, 11, rand=4
                    'Pestilence': copy.deepcopy(self.__vodou_priest_fighter),
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
                'Bob': copy.deepcopy(self.__vodou_priest_fighter),

                # 5.75, 12, rand=3
                'Ted': copy.deepcopy(self.__tank_fighter),
            },
            'fights': {
                'marx': {
                  'monsters': {
                    # 5.5, 12, rand=4
                    'Groucho': copy.deepcopy(self.__one_more_guy),

                    # 5.75, 12, rand=5
                    'Harpo': copy.deepcopy(self.__thief_fighter),

                    # 5.25, 10, rand=3
                    'Chico': copy.deepcopy(self.__bokor_fighter),
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

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)

    def tearDown(self):
        pass

    def __are_equal(self, lhs, rhs):
        if isinstance(lhs, dict):
            if not isinstance(rhs, dict):
                print '** lhs is a dict but rhs is not'
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                return False
            for key in rhs.iterkeys():
                if key not in lhs:
                    print '** KEY "%s" not in lhs' % key
                    print '\nlhs'
                    PP.pprint(lhs)
                    print '\nrhs'
                    PP.pprint(rhs)
                    return False
            are_equal = True
            for key in lhs.iterkeys():
                if key not in rhs:
                    print '** KEY "%s" not in rhs' % key
                    print '\nlhs'
                    PP.pprint(lhs)
                    print '\nrhs'
                    PP.pprint(rhs)
                    are_equal = False
                elif not self.__are_equal(lhs[key], rhs[key]):
                    print 'lhs[%r] != rhs[%r]' % (key, key)
                    print '\nlhs'
                    PP.pprint(lhs)
                    print '\nrhs'
                    PP.pprint(rhs)
                    are_equal = False
            return are_equal

        elif isinstance(lhs, list):
            if not isinstance(rhs, list):
                print '** lhs is a list but rhs is not'
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                return False
            if len(lhs) != len(rhs):
                print '** length lhs=%d != len rhs=%d' % (len(lhs), len(rhs))
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                return False
            are_equal = True
            for i in range(len(lhs)):
                if not self.__are_equal(lhs[i], rhs[i]):
                    print '** lhs[%d] != rhs[%d]' % (i, i)
                    print '\nlhs'
                    PP.pprint(lhs)
                    print '\nrhs'
                    PP.pprint(rhs)
                    are_equal = False
            return are_equal

        else:
            if lhs != rhs:
                print '** lhs=%r != rhs=%r' % (lhs, rhs)
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                return False
            else:
                return True

    def __is_in_dead_monsters(self, world_obj, fight_name):
        for fight in world_obj.read_data['dead-monsters']:
            if fight_name == fight['name']:
                return True
        return False

    #
    # Actual Tests #
    #

    def test_get_dodge_skill(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_get_dodge_skill ===\n'

        # Deepcopy so that we don't taint the original
        mock_fight_handler = MockFightHandler()
        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == 9

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == (9 + self.__crawling_defense_mod)

        # Next guy

        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self.__bokor_fighter),
                self.__ruleset,
                self.__window_manager)

        self.__ruleset.do_action(bokor_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == 9

        self.__ruleset.do_action(bokor_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == (9 + self.__crawling_defense_mod)

        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(tank_fighter)
        assert dodge_skill == 9

        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self.__thief_fighter),
                self.__ruleset,
                self.__window_manager)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(thief_fighter)
        assert dodge_skill == 8

    def test_get_block_skill(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_get_block_skill ===\n'

        # TODO: need non-trivial block tests
        vodou_priest_fighter = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(
                vodou_priest_fighter, None)
        assert block_skill is None

        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self.__bokor_fighter),
                self.__ruleset,
                self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(bokor_fighter,
                                                                None)
        assert block_skill is None

        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(tank_fighter,
                                                                None)
        assert block_skill is None

        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self.__thief_fighter),
                self.__ruleset,
                self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(thief_fighter,
                                                                None)
        assert block_skill is None

    def test_get_parry_skill(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_get_parry_skill ===\n'

        # Unarmed
        weapon = None
        mock_fight_handler = MockFightHandler()
        vodou_priest_fighter = ca_fighter.Fighter(
                'Vodou Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(
                vodou_priest_fighter, weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self.__bokor_fighter),
                self.__ruleset,
                self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(bokor_fighter,
                                                                weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Armed (sick stick)
        tank_fighter = ca_fighter.Fighter(
                                'Tank',
                                'group',
                                copy.deepcopy(self.__tank_fighter),
                                self.__ruleset,
                                self.__window_manager)
        weapon_index, weapon = tank_fighter.get_weapon_by_name('sick stick')
        self.__ruleset.do_action(tank_fighter,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': weapon_index},
                                 mock_fight_handler)

        self.__ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == 11

        self.__ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == (11 + self.__crawling_defense_mod)

        # Unarmed
        weapon = None
        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self.__thief_fighter),
                self.__ruleset,
                self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Armed (Knife)
        thief_fighter = ca_fighter.Fighter(
                                'Thief',
                                'group',
                                copy.deepcopy(self.__thief_fighter),
                                self.__ruleset,
                                self.__window_manager)
        weapon_index, weapon = thief_fighter.get_weapon_by_name('Large Knife')
        self.__ruleset.do_action(tank_fighter,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': weapon_index},
                                 mock_fight_handler)
        self.__ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == 9

        self.__ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == (9 + self.__crawling_defense_mod)

    def test_get_unarmed_info(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_get_unarmed_info ===\n'

        # Vodou Priest
        unarmed_skills = self.__ruleset.get_weapons_unarmed_skills(None)
        mock_fight_handler = MockFightHandler()
        vodou_priest_fighter = ca_fighter.Fighter(
                'Vodou Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(
                vodou_priest_fighter,
                None,
                None,
                unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage'] == '1d-3 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 10
        assert hand_to_hand_info['kick_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # Bokor
        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self.__bokor_fighter),
                self.__ruleset,
                self.__window_manager)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(bokor_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        # PP.pprint(hand_to_hand_info)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 10   # thr-1, st=10
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # Tank
        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(tank_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

        # Thief
        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self.__thief_fighter),
                self.__ruleset,
                self.__window_manager)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # Thief with posture additions

        self.__ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == (
                14 + self.__crawling_attack_mod)
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == (
                12 + self.__crawling_attack_mod)
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == (
                10 + self.__crawling_defense_mod)

        # Thief w/o brass knuckles
        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self.__thief_fighter),
                self.__ruleset,
                self.__window_manager)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # w/brass knuckles -- Note: that the punch damage is +1
        ignore, weapon = thief_fighter.get_weapon_by_name('brass knuckles')
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            weapon,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == 'thr: 1d-1 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # back to unarmed
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # --- Opponents w/ posture ---

        self.__ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # Picking opponent doesn't change things
        hand_to_hand_info = self.__ruleset.get_unarmed_info(tank_fighter,
                                                            thief_fighter,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

        # change posture of thief (opponent) -- note: posture of opponent does
        # not modify melee attacks

        self.__ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},  # -2
                                 mock_fight_handler)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(tank_fighter,
                                                            thief_fighter,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

        # change posture of thief (back to standing)
        self.__ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(tank_fighter,
                                                            thief_fighter,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

    def test_initiative_order(self):
        '''
        Partially GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_initiative_order ===\n'

        world_data = WorldData(self.init_world_dict)
        mock_program = MockProgram()
        world = ca.World("internal_source_file",
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)

        # Famine and Jack have the same basic speed and dx -- it's up to rand
        # Pestilence and Moe have same basic speed but different dx
        expected = [{'name': 'Famine',     'group': 'horsemen'},  # 5.75, 12, 4
                    {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
                    {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
                    {'name': 'Pestilence', 'group': 'horsemen'},  # 5.5,  11, 4
                    {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1

        # Do this multiple times just to verify that the random stuff works
        for i in range(10):
            # random.randint(1, 6) should generate: 1 2 4 4 4 4 5 6 4 4
            random.seed(9001)  # 9001 is an arbitrary number
            fight_handler = ca.FightHandler(self.__window_manager,
                                            world,
                                            'horsemen',
                                            None,  # Playback history
                                            save_snapshot=False)
            fighters = fight_handler.get_fighters()

            # Check the order against the one that I expect

            for index, ignore in enumerate(fighters):
                assert fighters[index]['name'] == expected[index]['name']
                assert fighters[index]['group'] == expected[index]['group']

        # test that modify index wraps
        # test that cycling a whole round goes to each fighter in order

        expected_index = 0
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 1
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        injured_fighter = current_fighter
        injured_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 2
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        unconscious_fighter = current_fighter
        unconscious_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 3
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        dead_fighter = current_fighter
        dead_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 4
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 0  # wraps
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # test that an unconscious fighter is not skipped but a dead one is

        injured_hp = 3  # arbitrary amount
        injured_fighter.details['current']['hp'] -= injured_hp
        unconscious_fighter.set_consciousness(ca_fighter.Fighter.UNCONSCIOUS)
        dead_fighter.set_consciousness(ca_fighter.Fighter.DEAD)

        assert injured_fighter.get_state() == ca_fighter.Fighter.INJURED
        assert (unconscious_fighter.get_state() ==
                ca_fighter.Fighter.UNCONSCIOUS)
        assert dead_fighter.get_state() == ca_fighter.Fighter.DEAD

        expected_index = 0
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # This is the injured fighter -- should still see this one
        fight_handler.modify_index(1)
        expected_index = 1
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # This is the unconscious fighter -- should still see this one
        fight_handler.modify_index(1)
        expected_index = 2
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # Should skip the dead fighter

        fight_handler.modify_index(1)
        expected_index = 4
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 0  # wraps
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # verify that the only thing that's changed among the fighters is that
        # one is injured, one is unconscious, and one is dead.

        expected_fighters = [
            copy.deepcopy(self.__thief_fighter),
            copy.deepcopy(self.__tank_fighter),
            copy.deepcopy(self.__one_more_guy),
            copy.deepcopy(self.__vodou_priest_fighter),
            copy.deepcopy(self.__bokor_fighter)]

        expected_fighters[injured_index]['current']['hp'] -= injured_hp
        expected_fighters[unconscious_index]['state'] = "unconscious"
        expected_fighters[dead_index]['state'] = "dead"

        fighters = fight_handler.get_fighters()
        assert len(expected_fighters) == len(fighters)

        assert self.__are_equal(expected_fighters[0], fighters[0]['details'])
        assert self.__are_equal(expected_fighters[1], fighters[1]['details'])
        assert self.__are_equal(expected_fighters[2], fighters[2]['details'])
        assert self.__are_equal(expected_fighters[3], fighters[3]['details'])
        assert self.__are_equal(expected_fighters[4], fighters[4]['details'])

    def test_initiative_order_again(self):
        '''
        Partially GURPS-specific test

        This is just like test_initiative_order except the fighters are
        reordered randomly and a different random seed is used.
        '''
        if ARGS.verbose:
            print '\n=== test_initiative_order_again ===\n'

        world_data = WorldData(self.init_world_dict_2)
        mock_program = MockProgram()
        world = ca.World("internal_source_file",
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)

        # Famine and Jack have the same basic speed and dx -- it's up to rand
        # Pestilence and Moe have same basic speed but different dx
        expected = [
                    {'name': 'Harpo',   'group': 'marx'},  # 5.75, 12, 5
                    {'name': 'Ted',     'group': 'PCs'},  # 5.75, 12, 3
                    {'name': 'Groucho', 'group': 'marx'},  # 5.5,  12, 4
                    {'name': 'Bob',     'group': 'PCs'},  # 5.5,  11, 2
                    {'name': 'Chico',   'group': 'marx'},  # 5.25, 10, 3
                   ]

        # Do this multiple times just to verify that the random stuff works
        for i in range(10):
            # random.randint(1, 6) should generate: 2 3 4 5 3
            random.seed(8534)  # 8534 is an arbitrary number
            fight_handler = ca.FightHandler(self.__window_manager,
                                            world,
                                            'marx',
                                            None,  # Playback history
                                            save_snapshot=False)
            fighters = fight_handler.get_fighters()

            # Check the order against the one that I expect

            for index, ignore in enumerate(fighters):
                assert fighters[index]['name'] == expected[index]['name']
                assert fighters[index]['group'] == expected[index]['group']

    def test_change_opponents(self):
        '''
        Test that changing opponents from one that's damaged doesn't affect
        any of the fighters (except that the opponent was changed).  This
        mirrors a bug that I thought I saw a while ago.
        '''
        if ARGS.verbose:
            print '\n=== test_change_opponents ===\n'

        world_data = WorldData(self.init_world_dict)
        mock_program = MockProgram()
        world = ca.World("internal_source_file",
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)

        # Famine and Jack have the same basic speed and dx -- it's up to rand
        # Pestilence and Moe have same basic speed but different dx
        expected = [{'name': 'Famine',     'group': 'horsemen'},  # 5.75, 12, 4
                    {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
                    {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
                    {'name': 'Pestilence', 'group': 'horsemen'},  # 5.5,  11, 4
                    {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1

        injured_hp = 3  # This is arbitrary
        injured_index = 2

        random.seed(9001)  # 9001 is an arbitrary number
        fight_handler = ca.FightHandler(self.__window_manager,
                                        world,
                                        'horsemen',
                                        None,  # Playback history
                                        save_snapshot=False)
        fighters = fight_handler.get_fighters()

        expected_index = 0
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Make fighter 0 fight figher 2

        self.__ruleset.do_action(current_fighter,
                                 {'action-name': 'pick-opponent',
                                  'opponent': {'name': 'Moe', 'group': 'PCs'}},
                                 fight_handler)

        # Make sure pick opponent worked as advertised
        opponent = fight_handler.get_opponent_for(current_fighter)
        assert opponent is not None
        assert opponent.name == 'Moe'
        assert opponent.group == 'PCs'

        # Move ahead to fighter 1
        fight_handler.modify_index(1)
        expected_index = 1
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Wound fighter 2
        fighters[injured_index]['details']['current']['hp'] -= injured_hp

        # Cycle around to fighter 0

        fight_handler.modify_index(1)
        expected_index = 2
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        unconscious_fighter = current_fighter
        unconscious_index = expected_index

        fight_handler.modify_index(1)
        expected_index = 3
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        dead_fighter = current_fighter
        dead_index = expected_index

        fight_handler.modify_index(1)
        expected_index = 4
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()

        fight_handler.modify_index(1)
        expected_index = 0  # wraps
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Change opponent of fighter 0 to fighter 1 -- At one time, I saw a
        # bug where it appeared that changing an opponent from an injured one
        # (in this case, fighter 2/Moe) to a different fighter (in this case,
        # fighter 1/Jack) caused the damage to be transferred to the new
        # opponent.
        self.__ruleset.do_action(current_fighter,
                                 {'action-name': 'pick-opponent',
                                  'opponent': {'name': 'Jack',
                                               'group': 'PCs'}},
                                 fight_handler)

        # Make sure pick opponent worked as advertised
        opponent = fight_handler.get_opponent_for(current_fighter)
        assert opponent is not None
        assert opponent.name == 'Jack'
        assert opponent.group == 'PCs'

        # cycle completely around to fighter 1
        fight_handler.modify_index(1)  # index 1
        fight_handler.modify_index(1)  # index 2
        fight_handler.modify_index(1)  # index 3
        fight_handler.modify_index(1)  # index 4
        fight_handler.modify_index(1)  # index 0
        fight_handler.modify_index(1)  # index 1
        expected_index = 1
        assert world_data.read_data['current-fight']['index'] == expected_index

        # Set expectations to the final configuration.

        expected_fighters = [
            copy.deepcopy(self.__thief_fighter),
            copy.deepcopy(self.__tank_fighter),
            copy.deepcopy(self.__one_more_guy),
            copy.deepcopy(self.__vodou_priest_fighter),
            copy.deepcopy(self.__bokor_fighter)]
        expected_fighters[0]['opponent'] = {'group': 'PCs', 'name': 'Jack'}
        expected_fighters[0]['actions_this_turn'] = ['pick-opponent',
                                                     'pick-opponent']
        expected_fighters[injured_index]['current']['hp'] -= injured_hp

        # Check that everything is as it should be

        assert len(expected_fighters) == len(fighters)
        assert self.__are_equal(expected_fighters[0], fighters[0]['details'])
        assert self.__are_equal(expected_fighters[1], fighters[1]['details'])
        assert self.__are_equal(expected_fighters[2], fighters[2]['details'])
        assert self.__are_equal(expected_fighters[3], fighters[3]['details'])
        assert self.__are_equal(expected_fighters[4], fighters[4]['details'])

    def test_ranged_to_hit(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_ranged_to_hit ===\n'

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)
        requested_weapon_index = self.__vodou_pistol_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # ranged to-hit should be skill + acc (if aimed) + 1 (if braced)
        #   + size modifier + range/speed modifier + special conditions

        # aim for 1 turn += acc, 2 turns += 1, 3+ turns += 1
        # brace += 1

        # no aim, no posture

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset.reset_aim(vodou_priest)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # aim / not braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # no aim, posture (posture doesn't matter for ranged attacks: B551)

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        self.__ruleset.reset_aim(vodou_priest)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, posture (posture not counted for ranged attacks: B551)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc  # aim
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # aim / not braced, posture (no posture minus for ranged attacks: B551)

        self.__ruleset.reset_aim(vodou_priest)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc)  # aim
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # --- Opponents w/ posture ---

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset.reset_aim(vodou_priest)
        tank = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # Picking opponent doesn't change things
        self.__ruleset.do_action(tank,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, tank, weapon)
        assert to_hit == expected_to_hit

        # change posture of thief (-2)
        self.__ruleset.do_action(tank,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},  # -2
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, tank, weapon)
        assert to_hit == (expected_to_hit - 2)

        # change posture of thief (back to standing)
        self.__ruleset.do_action(tank,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, tank, weapon)
        assert to_hit == expected_to_hit

    def test_messed_up_aim(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_messed_up_aim ===\n'

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)
        requested_weapon_index = self.__vodou_pistol_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # Regular, no aim - for a baseline

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset.reset_aim(vodou_priest)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # Damage _would_ ruin aim except for successful Will roll

        self.__ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # adjust_hp but MADE Will roll
        # action['action-name'] == 'adjust-hp':
        damage = -1
        self.__window_manager.set_menu_response(
                'roll <= WILL (13) or lose aim', True)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)

        # aiming for 3 rounds (1st round+brace already in expected_to_hit)
        #   + shock
        assert to_hit == expected_to_hit + 2 + damage

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        # Damage ruins aim -- miss will roll

        self.__ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # adjust_hp and MISSES Will roll
        self.__window_manager.set_menu_response(
                'roll <= WILL (13) or lose aim', False)
        damage = -1
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds (well, 1 round)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + damage  # aiming for 1 round + shock

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        # Draw weapon ruins aim

        self.__ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Draw weapon
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit  # aiming for 1 round

        # Posture ruins aim

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.reset_aim(vodou_priest)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Change posture
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'lying'},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit  # aiming for 1 round

        # Defense ruins aim

        self.__ruleset.reset_aim(vodou_priest)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Defend
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'defend'},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit  # aiming for 3 rounds

        # Last One is Regular - shows nothing carries over

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset.reset_aim(vodou_priest)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

    def test_melee_to_hit(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_melee_to_hit ===\n'

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        thief = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self.__thief_fighter),
                self.__ruleset,
                self.__window_manager)
        requested_weapon_index = 1  # Knife
        self.__ruleset.do_action(thief,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = thief.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # melee to-hit should be skill + special conditions

        # no posture
        expected_to_hit = self.__thief_knife_skill
        self.__ruleset.do_action(thief,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

        # posture
        expected_to_hit = (self.__thief_knife_skill
                           + self.__crawling_attack_mod)
        self.__ruleset.do_action(thief,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

        # --- Opponents w/ posture (shouldn't change melee attack) ---

        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)

        self.__ruleset.do_action(thief,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # Picking opponent doesn't change things
        expected_to_hit = self.__thief_knife_skill
        self.__ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, tank_fighter, weapon)
        assert to_hit == expected_to_hit

        # change posture of tank (opponent)
        self.__ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},  # -2
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, tank_fighter, weapon)
        assert to_hit == expected_to_hit

        # change posture of thief (back to standing)
        self.__ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, tank_fighter, weapon)
        assert to_hit == expected_to_hit

        # --- Aiming does not help ---

        self.__ruleset.reset_aim(thief)
        expected_to_hit = self.__thief_knife_skill
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)

        # 1 round
        self.__ruleset.do_action(thief,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(thief,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

    def test_adjust_hp(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_adjust_hp ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)

        requested_weapon_index = self.__vodou_pistol_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"

        requested_armor_index = 2
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'don-armor',
                                  'armor-index': requested_armor_index},
                                 mock_fight_handler)

        armor, actual_armor_index = vodou_priest.get_current_armor()
        assert actual_armor_index == requested_armor_index
        assert armor['name'] == "Sport coat/Jeans"

        original_to_hit, ignore = self.__ruleset.get_to_hit(vodou_priest,
                                                            None,
                                                            weapon)

        unarmed_skills = self.__ruleset.get_weapons_unarmed_skills(None)

        original_hand_to_hand_info = self.__ruleset.get_unarmed_info(
                vodou_priest,
                None,
                None,
                unarmed_skills)

        original_dodge_skill, ignore = self.__ruleset.get_dodge_skill(
                vodou_priest)

        # Test that the HP are reduced withOUT DR adjustment

        damage_1st = -3
        self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        original_hp = vodou_priest.details['current']['hp']

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage_1st},
                                 mock_fight_handler)

        modified_hp = vodou_priest.details['current']['hp']
        assert modified_hp == original_hp + damage_1st

        # Shock (B419)

        to_hit, ignore = self.__ruleset.get_to_hit(vodou_priest,
                                                   None,
                                                   weapon)
        assert to_hit == original_to_hit + damage_1st  # damage is less than 4

        hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert (hand_to_hand_info['punch_skill'] ==
                original_hand_to_hand_info['punch_skill'] + damage_1st)
        assert (hand_to_hand_info['kick_skill'] ==
                original_hand_to_hand_info['kick_skill'] + damage_1st)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        # Test that the HP are NOT reduced WITH DR adjustment

        damage_2nd = -1
        self.__window_manager.set_menu_response('Use Armor\'s DR?', True)
        original_hp = vodou_priest.details['current']['hp']

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage_2nd},
                                 mock_fight_handler)

        modified_hp = vodou_priest.details['current']['hp']
        assert modified_hp == original_hp  # No damage because of DR

        # Shock (B419) is only from the 1st attack since this did no damage
        # -hp to DX/IQ (not defense) on your next turn

        to_hit, ignore = self.__ruleset.get_to_hit(vodou_priest,
                                                   None,
                                                   weapon)
        assert to_hit == original_to_hit + damage_1st  # damage is less than 4

        hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert (hand_to_hand_info['punch_skill'] ==
                original_hand_to_hand_info['punch_skill'] + damage_1st)
        assert (hand_to_hand_info['kick_skill'] ==
                original_hand_to_hand_info['kick_skill'] + damage_1st)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        # Test that the HP ARE reduced WITH DR adjustment

        expected_damage = -2
        pre_armor_damage = expected_damage - self.__vodou_priest_armor_dr
        self.__window_manager.set_menu_response('Use Armor\'s DR?', True)
        original_hp = vodou_priest.details['current']['hp']

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': pre_armor_damage},
                                 mock_fight_handler)

        modified_hp = vodou_priest.details['current']['hp']
        assert modified_hp == original_hp + expected_damage

        # Shock is capped at -4

        max_shock = -4

        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)

        assert to_hit == original_to_hit + max_shock

        hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert (hand_to_hand_info['punch_skill'] ==
                original_hand_to_hand_info['punch_skill'] + max_shock)
        assert (hand_to_hand_info['kick_skill'] ==
                original_hand_to_hand_info['kick_skill'] + max_shock)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        #
        # Let's heal the guy
        #

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)

        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])

        # Major wound (B420) - Make HT roll (no knockdown or stun)

        # +1 to make sure that the damage is more than half
        major_damage = - ((vodou_priest.details['permanent']['hp'] / 2) + 1)

        self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        self.__window_manager.set_menu_response(
                ('Major Wound (B420): Roll vs HT (%d) or be stunned' %
                 self.__vodou_priest_ht),
                ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SUCCESS)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        dodge_skill, ignore = self.__ruleset.get_dodge_skill(vodou_priest)

        assert dodge_skill == original_dodge_skill  # shock
        assert vodou_priest.details['posture'] == 'standing'

        # Major wound (B420) - miss HT roll (knockdown and stunned)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])

        self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        self.__window_manager.set_menu_response(
                ('Major Wound (B420): Roll vs HT (%d) or be stunned' %
                 self.__vodou_priest_ht),
                ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        stun_penalty = -4
        posture_penalty = -3
        total_penalty = stun_penalty + posture_penalty

        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'] + total_penalty)

        dodge_skill, ignore = self.__ruleset.get_dodge_skill(vodou_priest)

        assert dodge_skill == original_dodge_skill + total_penalty
        assert vodou_priest.details['posture'] == 'lying'

        # End of the turn -- check for stun (B420) to be over

        self.__window_manager.set_menu_response(
                'Priest Stunned (B420): Roll <= HT to recover',
                True)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None,
                                                            unarmed_skills)

        # Stun should be over -- now there's only the posture penalty

        posture_penalty = -3
        total_penalty = posture_penalty

        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'] + total_penalty)

        dodge_skill, ignore = self.__ruleset.get_dodge_skill(vodou_priest)

        assert dodge_skill == original_dodge_skill + total_penalty
        assert vodou_priest.details['posture'] == 'lying'

        # Check for death, check for unconscious
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)

        # Major wound (B420) - bad fail (unconscious)

        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])

        self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        self.__window_manager.set_menu_response(
                ('Major Wound (B420): Roll vs HT (%d) or be stunned' %
                 self.__vodou_priest_ht),
                ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_BAD_FAIL)

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        assert not vodou_priest.is_conscious()

        # # # # # # # # # # # # # # # #

        # Aim (B324) on injury, will roll or lose aim

        # fail will roll #

        # Start by healing him up

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        #

        self.__ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Take damage, fail will roll

        self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        self.__window_manager.set_menu_response(
                "roll <= WILL (13) or lose aim", False)

        damage = -1
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + damage  # aiming for 1 round + shock

        # make will roll #

        # Start by healing him up

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        self.__ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        expected_to_hit += 1  # aiming for 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # Take damage, make will roll

        expected_to_hit += 1  # aiming for 3 rounds
        self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        self.__window_manager.set_menu_response(
                "roll <= WILL (13) or lose aim", True)

        damage = -1
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + damage  # aiming for 1 round + shock

        # B327
        # TODO: if adjusted_hp <= -(5 * fighter.details['permanent']['hp']):
        #        fighter.details['state'] = 'dead'

        # Start by healing him up
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        # Check for death, check for unconscious
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        self.__ruleset.reset_aim(vodou_priest)

    def test_adjust_hp_2(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_adjust_hp_2 ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)

        del vodou_priest.details['advantages']['Combat Reflexes']

        unarmed_skills = self.__ruleset.get_weapons_unarmed_skills(None)

        original_hand_to_hand_info = self.__ruleset.get_unarmed_info(
                vodou_priest,
                None,
                None,
                unarmed_skills)

        original_dodge_skill, ignore = self.__ruleset.get_dodge_skill(
                vodou_priest)

        # high pain threshold (B59)
        # - no shock / +3 to HT roll for knockdown and stunning

        '''
        There's:
            Any damage (NONE for high pain threshold):
            - shock: -damage (-4 max), DX-based skills, NOT defense, 1 round

            Major wound damage (over 1/2 permanent HP)
            - stunning: -4 defense, do nothing, roll at end of turn
            - knockdown

        '''

        # Test High Pain Threshold

        vodou_priest.details['advantages']['High Pain Threshold'] = 10

        self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        high_pain_thrshold_margin = 3
        stun_roll = self.__vodou_priest_ht + high_pain_thrshold_margin
        self.__window_manager.set_menu_response(
            ('Major Wound (B420): Roll vs. HT+3 (%d) or be stunned' %
             stun_roll),
            ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL)

        # failed the high stun roll so knockdown & stun is still in effect

        # +1 to make sure that the damage is more than half
        major_damage = - ((vodou_priest.details['permanent']['hp'] / 2) + 1)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None,
                                                            unarmed_skills)

        attack_lying_penalty = -4   # B551
        defense_lying_penalty = -3  # B551

        assert (hand_to_hand_info['punch_skill'] ==
                original_hand_to_hand_info['punch_skill'] +
                attack_lying_penalty)
        assert (hand_to_hand_info['kick_skill'] ==
                original_hand_to_hand_info['kick_skill'] +
                attack_lying_penalty)

        # Defense is at -4 (stun); shock is the HP stuff

        stun_penalty = -4
        total_penalty = stun_penalty + defense_lying_penalty

        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'] + total_penalty)

        dodge_skill, ignore = self.__ruleset.get_dodge_skill(vodou_priest)

        assert dodge_skill == original_dodge_skill + total_penalty
        assert vodou_priest.details['posture'] == 'lying'

        # # low pain threshold (B142)
        # # - 2x shock / -4 to HT roll for knockdown and stunning
        # # - according to KROMM, the max is -8 for LPT

        # del vodou_priest.details['advantages']['High Pain Threshold']
        # vodou_priest.details['advantages']['Low Pain Threshold'] = -10

        # '''
        # There's:
        #    Any damage (x2 for Low Pain threshold -- According to KROMM, the
        #    max is -8)
        #    - shock: -damage (-4 max), DX-based skills, NOT defense, 1 round

        #    Major wound damage (over 1/2 permanent HP)
        #    - stunning: -4 defense, do nothing, roll at end of turn
        #    - knockdown

        # '''

        # Test High Pain Threshold

        # vodou_priest.details['advantages']['High Pain Threshold'] = 10

        # self.__window_manager.set_menu_response('Use Armor\'s DR?', False)
        # high_pain_thrshold_margin = 3
        # stun_roll = self.__vodou_priest_ht + high_pain_thrshold_margin
        # self.__window_manager.set_menu_response(
        #    ('Major Wound (B420): Roll vs. HT+3 (%d) or be stunned' %
        #                                                        stun_roll),
        #    ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL)

        # # failed the high stun roll so knockdown & stun is still in effect

        # # +1 to make sure that the damage is more than half
        # major_damage = - ((vodou_priest.details['permanent']['hp'] / 2) + 1)
        # self.__ruleset.do_action(vodou_priest,
        #                         {'action-name': 'adjust-hp',
        #                          'adj': major_damage},
        #                         mock_fight_handler)

        # hand_to_hand_info = self.__ruleset.get_unarmed_info(vodou_priest,
        #                                                    None,
        #                                                    None,
        #                                                    unarmed_skills)

        # attack_lying_penalty = -4   # B551
        # defense_lying_penalty = -3  # B551

        # assert (hand_to_hand_info['punch_skill'] ==
        #    original_hand_to_hand_info['punch_skill'] + attack_lying_penalty)
        # assert (hand_to_hand_info['kick_skill'] ==
        #    original_hand_to_hand_info['kick_skill'] + attack_lying_penalty)

        # # Defense is at -4 (stun); shock is the HP stuff

        # stun_penalty = -4
        # total_penalty = stun_penalty + defense_lying_penalty

        # assert (hand_to_hand_info['parry_skill'] ==
        #            original_hand_to_hand_info['parry_skill'] + total_penalty)

        # dodge_skill, ignore = self.__ruleset.get_dodge_skill(vodou_priest)

        # assert dodge_skill == original_dodge_skill + total_penalty
        # assert vodou_priest.details['posture'] == 'lying'

    def test_spell_casting(self):
        '''
        GURPS-specific test
        '''
        if ARGS.verbose:
            print '\n=== test_spell_casting ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)
        opponent = ca_fighter.Fighter(
                'Opponent',
                'other_group',
                copy.deepcopy(self.__one_more_guy),
                self.__ruleset,
                self.__window_manager)

        mock_fight_handler.set_opponent_for(vodou_priest, opponent)
        mock_fight_handler.set_fighter_object('Priest',
                                              'group',
                                              vodou_priest)
        mock_fight_handler.set_fighter_object('Opponent',
                                              'other_group',
                                              opponent)

        expected = [
          {'name': "Awaken",
           'cost': 1,
           'casting time': 1,
           'skill': 18,
           'skill-bonus': -1,
           'duration': 0,
           'notes': "M90"},
          {'name': "Animate Shadow",
           'cost': 4,
           'casting time': 2,
           'skill': 16,
           'skill-bonus': -1,
           'duration': 5,
           'notes': "M154, Subject's shadow attacks them, HT negates"},
          {'name': "Death Vision",
           'cost': 2,
           'casting time': 3,
           'skill': 16,
           'skill-bonus': -1,
           'duration': 1,
           'notes': "M149, vs. IQ"},
          {'name': "Explosive Lightning",
           'cost': 2,
           'casting time': 3,
           'skill': 16,
           'skill-bonus': -1,
           'duration': 0,
           'notes': "M196, cost 2-mage level, damage 1d-1 /2"},
          {'name': "Itch",
           'cost': 2,
           'casting time': 1,
           'skill': 12,
           'skill-bonus': 0,
           'duration': 2,
           'notes': "M35"},
        ]

        original_fp = vodou_priest.details['current']['fp']

        assert original_fp == vodou_priest.details['permanent']['fp']

        for trial in expected:
            opponent.timers.clear_all()

            vodou_priest.timers.clear_all()
            vodou_priest.details['current']['fp'] = original_fp

            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['cost'] is None):
                self.__window_manager.set_input_box_response(
                    'Cost to cast (%s) - see (%s) ' % (trial['name'],
                                                       trial['notes']),
                    trial['cost'])
            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['casting time'] is None):
                self.__window_manager.set_input_box_response(
                    'Seconds to cast (%s) - see (%s) ' % (trial['name'],
                                                          trial['notes']),
                    trial['casting time'])
            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['duration'] is None):
                self.__window_manager.set_input_box_response(
                    'Duration for (%s) - see (%s) ' % (trial['name'],
                                                       trial['notes']),
                    trial['duration'])

            self.__window_manager.set_menu_response(
                    'Mark %s with spell' % opponent.name, True)

            action = {
                'action-name': 'cast-spell',
                'spell-index': self.__vodou_priest_spell_index[trial['name']]
                     }

            self.__ruleset.do_action(vodou_priest, action, mock_fight_handler)

            # Cost

            expected_cost = trial['cost'] + trial['skill-bonus']
            assert (vodou_priest.details['current']['fp'] ==
                    original_fp - expected_cost)

            # Watch the casting time and the spell duration

            casting_text = [('Casting (%s) @ skill (%d): %s' % (
                             trial['name'], trial['skill'], trial['notes'])),
                            ' Defense: none',
                            ' Move: none']
            opponent_casting_text = ('Waiting for "%s" spell to take affect' %
                                     trial['name'])

            # Check each round of casting

            for turn in range(trial['casting time']):
                # For the caster, you're doing the check, end-turn, then
                # start-turn because the action takes place in the middle of a
                # turn.

                assert len(vodou_priest.details['timers']) == 1
                assert (vodou_priest.details['timers'][0]['string'] ==
                        casting_text)
                assert vodou_priest.details['timers'][0]['busy']
                self.__ruleset.do_action(vodou_priest,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)
                self.__ruleset.do_action(vodou_priest,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

                # For the opponent, you need to do start-turn, check, then
                # end-turn because they get affected after the caster does
                # their thing.

                self.__ruleset.do_action(opponent,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

                assert len(opponent.details['timers']) == 1
                assert (opponent.details['timers'][0]['string'] ==
                        opponent_casting_text)

                self.__ruleset.do_action(opponent,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)

            # One extra round for the opponent so that the timers get deleted.
            # Note the proper progression of start-turn / end-turn from the
            # casting loop through this through the duration loop.

            self.__ruleset.do_action(opponent,
                                     {'action-name': 'start-turn'},
                                     mock_fight_handler)

            # Check each round of active spell

            active_text = 'CAST SPELL (%s) ACTIVE' % trial['name']
            opponent_active_text = 'SPELL "%s" AGAINST ME' % trial['name']

            for turn in range(trial['duration']):
                assert len(vodou_priest.details['timers']) == 1
                assert (vodou_priest.details['timers'][0]['string'] ==
                        active_text)
                if 'busy' in vodou_priest.details['timers'][0]:
                    assert not vodou_priest.details['timers'][0]['busy']
                # else, it's OK
                self.__ruleset.do_action(vodou_priest,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)
                self.__ruleset.do_action(vodou_priest,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

                # Opponent

                assert len(opponent.details['timers']) == 1
                assert (opponent.details['timers'][0]['string'] ==
                        opponent_active_text)

                self.__ruleset.do_action(opponent,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)
                self.__ruleset.do_action(opponent,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

            # Make sure that all of the timers are dead

            assert len(vodou_priest.details['timers']) == 0
            assert len(opponent.details['timers']) == 0

    def test_don_doff_armor(self):
        '''
        General test
        '''
        if ARGS.verbose:
            print '\n=== test_don_doff_armor ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)

        # Don armor

        requested_armor_index = self.__vodou_armor_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'don-armor',
                                  'armor-index': requested_armor_index},
                                 mock_fight_handler)

        armor, actual_armor_index = vodou_priest.get_current_armor()
        assert actual_armor_index == requested_armor_index
        assert armor['name'] == "Sport coat/Jeans"

        # Doff armor

        requested_armor_index = None
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'don-armor',
                                  'armor-index': None},
                                 mock_fight_handler)

        armor, actual_armor_index = vodou_priest.get_current_armor()
        assert actual_armor_index == requested_armor_index

        # The effect of the armor is tested in 'hp'

    def test_draw_sheathe_weapon(self):
        '''
        General test
        '''
        if ARGS.verbose:
            print '\n=== test_draw_sheathe_weapon ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)

        # Draw Weapon

        requested_weapon_index = self.__vodou_pistol_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"

        # Sheathe Weapon

        requested_weapon_index = None
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # The effect of the weapon is tested throughout the testing

    def test_reload(self):
        '''
        General test
        '''
        if ARGS.verbose:
            print '\n=== test_reload ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)

        # Draw Weapon

        requested_weapon_index = self.__vodou_pistol_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"
        assert weapon.shots_left() == self.__vodou_priest_initial_shots

        clip = vodou_priest.equipment.get_item_by_index(
                self.__vodou_priest_ammo_index)
        # check the number of clips/batteries

        assert clip['count'] == self.__vodou_priest_ammo_count

        # A. Fire twice and verify that the shots left went down

        shots_taken = 2
        for shot in range(shots_taken):
            self.__ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)

        assert (weapon.shots_left() ==
                (self.__vodou_priest_initial_shots - shots_taken))

        # Discard the rest of the shots in the clip

        shots_taken = weapon.shots_left()
        for shot in range(shots_taken):
            self.__ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)

        # Now, reload

        self.__window_manager.set_menu_response('Reload With What', 1)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert weapon.shots_left() == self.__vodou_priest_initial_shots
        assert clip['count'] == (self.__vodou_priest_ammo_count - 1)

        index, virtual_clip = vodou_priest.equipment.get_item_by_name('C Cell')
        assert(virtual_clip is not None)
        index, second_clip = vodou_priest.equipment.get_item_by_name('C Cell',
                                                                     index)
        assert(second_clip is None)

        # B. Fire and reload until there are no clips available

        # Note: when the last clip is ejected, a new item takes its place and
        # clip['count'] will never go to zero

        clip_count = clip['count']
        for clip_number in range(clip_count):
            # Shoot until this clip is empty (so the reload discards the empty
            # clip)
            shots_left = weapon.shots_left()
            for shot in range(shots_left):
                self.__ruleset.do_action(vodou_priest,
                                         {'action-name': 'attack'},
                                         mock_fight_handler)
            self.__window_manager.set_menu_response('Reload With What', 1)
            self.__ruleset.do_action(vodou_priest,
                                     {'action-name': 'reload'},
                                     mock_fight_handler)

        # C. Shoot a number of times and verify that we have the number of
        #    shots left that we expect (in our last clip).

        shots_taken = 3  # Pick a number at random
        for shot in range(shots_taken):
            self.__ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)

        assert (weapon.shots_left() ==
                (self.__vodou_priest_initial_shots - shots_taken))

        # D. Reload when there's nothing left with which to reload

        self.__window_manager.set_menu_response('Reload With What', None)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert (weapon.details['ammo']['shots_left'] ==
                (self.__vodou_priest_initial_shots - shots_taken))

        throw_away, virtual_clip = vodou_priest.equipment.get_item_by_name(
                'C Cell')
        assert(virtual_clip is None)

    def test_reload_2(self):
        '''
        General test
        '''
        if ARGS.verbose:
            print '\n=== test_reload_2 ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)

        # Draw Weapon

        requested_weapon_index = self.__vodou_pistol_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"
        assert weapon.shots_left() == self.__vodou_priest_initial_shots

        clip = vodou_priest.equipment.get_item_by_index(
                self.__vodou_priest_ammo_index)
        # check the number of clips/batteries

        assert clip['count'] == self.__vodou_priest_ammo_count

        # A. Fire twice and verify that the shots left went down

        shots_taken = 2
        for shot in range(shots_taken):
            self.__ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)

        assert (weapon.shots_left() ==
                (self.__vodou_priest_initial_shots - shots_taken))

        # Reload and verify that there are two different types of clips (a
        # bunch of full ones and one partially full one)

        self.__window_manager.set_menu_response('Reload With What', 1)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert clip['count'] == (self.__vodou_priest_ammo_count - 1)

        first_index, virtual_clip = vodou_priest.equipment.get_item_by_name(
                'C Cell')
        assert(virtual_clip is not None)

        second_index, second_clip = vodou_priest.equipment.get_item_by_name(
                'C Cell', first_index)
        assert(second_clip is not None)

        assert(second_clip['shots_left'] == self.__vodou_priest_initial_shots
               - shots_taken)

        # Now, try to reload other clips

        # Start off by shooting off one shot so the reload will work
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'attack'},
                                 mock_fight_handler)

        # Reload with the partial (the previously ejected one)
        self.__window_manager.set_menu_response('Reload With What',
                                                second_index)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)
        assert (weapon.shots_left() ==
                (self.__vodou_priest_initial_shots - shots_taken))

        # Now, reload with a full one
        self.__window_manager.set_menu_response('Reload With What',
                                                first_index)
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert (weapon.shots_left() == self.__vodou_priest_initial_shots)

    def test_stun_and_consciousness(self):
        '''
        MIXED test
        '''
        if ARGS.verbose:
            print '\n=== test_stun_and_consciousness ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)

        world_data = WorldData(self.init_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)
        fight_handler = ca.FightHandler(self.__window_manager,
                                        world,
                                        'horsemen',
                                        None,  # Playback history
                                        save_snapshot=False)
        current_fighter = fight_handler.get_current_fighter()

        # Consciousness

        # check consciousness level

        state_number = ca_fighter.Fighter.get_fighter_state(
                current_fighter.details)
        assert state_number == ca_fighter.Fighter.ALIVE

        self.__ruleset.do_action(current_fighter,
                                 {'action-name': 'pick-opponent',
                                  'opponent': {'name': 'Moe', 'group': 'PCs'}},
                                 fight_handler)

        # Test

        new_state = ca_fighter.Fighter.ALIVE
        self.__ruleset.do_action(current_fighter,
                                 {'action-name': 'set-consciousness',
                                  'level': new_state},
                                 fight_handler)
        state_number = ca_fighter.Fighter.get_fighter_state(
                current_fighter.details)
        assert state_number == new_state
        opponent = fight_handler.get_opponent_for(current_fighter)
        assert opponent.name == 'Moe'
        assert opponent.group == 'PCs'

        new_state = ca_fighter.Fighter.UNCONSCIOUS
        self.__ruleset.do_action(current_fighter,
                                 {'action-name': 'set-consciousness',
                                  'level': new_state},
                                 fight_handler)
        state_number = ca_fighter.Fighter.get_fighter_state(
                current_fighter.details)
        assert state_number == new_state
        opponent = fight_handler.get_opponent_for(current_fighter)
        assert opponent is None

        # Setup Stun Test

        unarmed_skills = self.__ruleset.get_weapons_unarmed_skills(None)
        original_hand_to_hand_info = self.__ruleset.get_unarmed_info(
                current_fighter,
                None,
                None,
                unarmed_skills)
        original_dodge_skill, ignore = self.__ruleset.get_dodge_skill(
                current_fighter)

        # Stun

        self.__ruleset.do_action(current_fighter,
                                 {'action-name': 'stun', 'stun': True},
                                 fight_handler)

        # Check whether stunned

        hand_to_hand_info = self.__ruleset.get_unarmed_info(current_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        stun_penalty = -4
        total_penalty = stun_penalty

        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'] + total_penalty)

        dodge_skill, ignore = self.__ruleset.get_dodge_skill(current_fighter)

        assert dodge_skill == original_dodge_skill + total_penalty

    def test_defend(self):
        '''
        GURPS test
        '''
        if ARGS.verbose:
            print '\n=== test_defend ===\n'

        # Setup

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self.__vodou_priest_fighter),
                self.__ruleset,
                self.__window_manager)
        requested_weapon_index = self.__vodou_pistol_index
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # The only way you can see a 'defend' action is because aim is lost.

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                           + self.__colt_pistol_acc
                           + 1)  # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # DEFEND, LOSE AIM #

        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'defend'},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit  # aiming for 1 round

    def test_timers(self):
        '''
        Basic test
        '''
        if ARGS.verbose:
            print '\n=== test_timers ===\n'

        fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)

        # Test a standard timer

        timer_id = 0
        round_count = 3
        timer_text = '%d' % timer_id
        timer_obj = ca_timers.Timer(None)
        timer_obj.from_pieces({'parent-name': fighter.name,
                               'rounds': round_count,
                               'string': timer_text})

        fighter.timers.add(timer_obj)

        for i in range(round_count):
            assert len(fighter.details['timers']) == 1
            assert fighter.details['timers'][0]['string'] == timer_text
            # At the _end_ of a fighter's turn, we remove all his expired
            # timers.  That causes the timer expiring this round to be shown.
            fighter.timers.remove_expired_kill_dying()
            fighter.timers.decrement_all()

        fighter.timers.remove_expired_kill_dying()
        assert len(fighter.details['timers']) == 0

        # Test 3 timers simultaneously

        timer_id = 0
        round_count = [1, 2, 3]
        timer_count = 3

        for i in range(timer_count):
            timer_text = '%d' % timer_id
            timer_id += 1
            timer_obj = ca_timers.Timer(None)
            timer_obj.from_pieces({'parent-name': fighter.name,
                                   'rounds': round_count[i],
                                   'string': timer_text})
            fighter.timers.add(timer_obj)

        # round 0
        fighter.timers.remove_expired_kill_dying()
        fighter.timers.decrement_all()
        assert len(fighter.details['timers']) == 3
        expected = ['0', '1', '2']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        # round 1
        fighter.timers.remove_expired_kill_dying()
        fighter.timers.decrement_all()
        assert len(fighter.details['timers']) == 2
        expected = ['1', '2']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        # round 2
        fighter.timers.remove_expired_kill_dying()
        fighter.timers.decrement_all()
        assert len(fighter.details['timers']) == 1
        expected = ['2']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        fighter.timers.remove_expired_kill_dying()
        assert len(fighter.details['timers']) == 0

        # Test a 0.9 timer.  The 0.9 round timer is supposed to show during
        # the current round but not the beginning of the next round.  The
        # normal way this works is:
        #   - start turn
        #   - set 0.9 timer (shows through the end of this round)
        #   - end turn # kills regular timers that showed this turn
        #   - start turn # kills 0.9 timer before stuff is shown this turn

        # add 1 turn timer -- a regular timer are show through the next turn
        timer_id = 0
        round_count = 1
        timer0_text = '%d' % timer_id
        timer_obj = ca_timers.Timer(None)
        timer_obj.from_pieces({'parent-name': fighter.name,
                               'rounds': round_count,
                               'string': timer0_text})

        fighter.timers.add(timer_obj)

        # start turn -- decrement 1-turn timer, timer = 0, keep it this turn
        fighter.timers.decrement_all()
        fighter.timers.remove_expired_keep_dying()

        # assert 1 timer -- didn't kill the 1-turn timer
        assert len(fighter.details['timers']) == 1
        assert fighter.details['timers'][0]['string'] == timer0_text

        # add 0.9 timer -- shown through this turn, killed before next turn
        timer_id = 1
        round_count = 0.9
        timer1_text = '%d' % timer_id
        timer_obj = ca_timers.Timer(None)
        timer_obj.from_pieces({'parent-name': fighter.name,
                               'rounds': round_count,
                               'string': timer1_text})
        fighter.timers.add(timer_obj)

        # assert 2 timers -- right: both timers are there
        assert len(fighter.details['timers']) == 2
        expected = ['0', '1']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        # end turn -- kills 1 turn timer
        fighter.timers.remove_expired_kill_dying()

        # assert 1 timer -- show that the 1-turn timer was killed
        assert len(fighter.details['timers']) == 1
        assert fighter.details['timers'][0]['string'] == timer1_text

        # start turn - kills 0.9 timer before the next turn's stuff is shown
        fighter.timers.decrement_all()
        fighter.timers.remove_expired_keep_dying()

        # assert 0 timers -- yup, 0.9 timer is now gone
        assert len(fighter.details['timers']) == 0

    def test_save(self):
        '''
        Basic test
        '''
        if ARGS.verbose:
            print '\n=== test_save ===\n'

        base_world_dict = copy.deepcopy(self.base_world_dict)

        self.__window_manager = MockWindowManager()
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(self.__window_manager)

        # Test that leaving a fight moves the bad guys to the dead monster
        # list
        if ARGS.verbose:
            print '\n----------- LEAVE FIGHT -----------\n'

        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)

        fight_handler = ca.FightHandler(self.__window_manager,
                                        world,
                                        "Dima's Crew",
                                        None,  # Playback history
                                        save_snapshot=False)

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self.__is_in_dead_monsters(world_data, "Dima's Crew")
        # assert not world_data.read_data['current-fight']['saved']

        self.__window_manager.set_char_response(ord('q'))
        self.__window_manager.set_menu_response('Leaving Fight', False)

        fight_handler.handle_user_input_until_done()

        assert "Dima's Crew" not in world_data.read_data['fights']
        assert self.__is_in_dead_monsters(world_data, "Dima's Crew")
        assert not world_data.read_data['current-fight']['saved']

        #
        # test that SAVING the fight works
        #
        if ARGS.verbose:
            print '\n----------- SAVE FIGHT -----------\n'

        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)

        assert (world_data.read_data['current-fight']['monsters'] !=
                "Dima's Crew")

        fight_handler = ca.FightHandler(self.__window_manager,
                                        world,
                                        "Dima's Crew",
                                        None,  # Playback history
                                        save_snapshot=False)

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self.__is_in_dead_monsters(world_data, "Dima's Crew")
        # assert not world_data.read_data['current-fight']['saved']

        self.__window_manager.set_char_response(ord('q'))
        self.__window_manager.set_menu_response(
                'Leaving Fight', {'doit': fight_handler.save_fight})
        self.__window_manager.set_menu_response('Leaving Fight', False)

        fight_handler.handle_user_input_until_done()

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self.__is_in_dead_monsters(world_data, "Dima's Crew")
        assert world_data.read_data['current-fight']['saved']
        assert (world_data.read_data['current-fight']['monsters'] ==
                "Dima's Crew")

        #
        # test that KEEPING the fight works
        #
        if ARGS.verbose:
            print '\n----------- KEEP FIGHT -----------\n'

        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)

        fight_handler = ca.FightHandler(self.__window_manager,
                                        world,
                                        "Dima's Crew",
                                        None,  # Playback history
                                        save_snapshot=False)

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self.__is_in_dead_monsters(world_data, "Dima's Crew")
        # assert not world_data.read_data['current-fight']['saved']

        self.__window_manager.set_char_response(ord('q'))
        self.__window_manager.set_menu_response(
                'Leaving Fight', {'doit': fight_handler.keep_fight})
        self.__window_manager.set_menu_response('Leaving Fight', False)

        fight_handler.handle_user_input_until_done()

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self.__is_in_dead_monsters(world_data, "Dima's Crew")
        assert not world_data.read_data['current-fight']['saved']

    def test_add_remove_equipment(self):
        '''
        Basic test
        '''
        if ARGS.verbose:
            print '\n=== test_add_remove_equipment ===\n'

        fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self.__tank_fighter),
                self.__ruleset,
                self.__window_manager)
        mock_fight_handler = MockFightHandler()

        original_item = fighter.details['stuff'][
                                        self.__tank_fighter_pistol_index]
        current_count = len(fighter.details['stuff'])
        original_stuff = copy.deepcopy(fighter.details['stuff'])

        # Same item - verify that the count goes up

        assert original_item['count'] == 1
        same_item = copy.deepcopy(original_item)
        same_item['count'] = 2

        before_item_count = fighter.equipment.get_item_count()
        fighter.add_equipment(same_item, 'test')
        after_item_count = fighter.equipment.get_item_count()

        assert original_item['count'] == 3
        assert before_item_count == after_item_count

        # Similar item - verify that it doesn't just bump the count

        similar_item = copy.deepcopy(original_item)
        similar_item['count'] = 1
        similar_item['acc'] = original_item['acc'] + 1

        assert len(fighter.details['stuff']) == current_count
        fighter.add_equipment(similar_item, 'test')

        current_count += 1

        assert len(fighter.details['stuff']) == current_count

        # Different item

        different_item = {"name": "pistol, Baretta DX 192",
                          "type": "ranged weapon",
                          "damage": {"dice": "1d+4"},
                          "acc": 2,
                          "ammo": {"name": "C Cell",
                                   "shots_left": 8,
                                   "shots": 8},
                          "clip": {"name": "C Cell",
                                   "type": "misc",
                                   "count": 1,
                                   "notes": "",
                                   "owners": None},
                          "reload": 3,
                          "skill": "Guns (Pistol)",
                          "count": 1,
                          "owners": None,
                          "notes": ""}

        assert len(fighter.details['stuff']) == current_count
        new_pistol_index = fighter.add_equipment(different_item, 'test')
        current_count += 1
        assert len(fighter.details['stuff']) == current_count

        # Make sure we only add to the end

        for i, original_item in enumerate(original_stuff):
            # We've changed the count on the fighter's pistol
            if i != self.__tank_fighter_pistol_index:
                assert self.__are_equal(original_item,
                                        fighter.details['stuff'][i])

        # Remove counted item
        self.__window_manager.set_input_box_response(
                'How Many Items (3 Available)?', 1)
        fighter.remove_equipment(self.__tank_fighter_pistol_index)
        weapon = fighter.equipment.get_item_by_index(
                self.__tank_fighter_pistol_index)
        assert weapon is not None
        assert weapon['count'] == 2  # one less than before

        # Remove uncounted item
        fighter.remove_equipment(new_pistol_index)
        weapon = fighter.equipment.get_item_by_index(new_pistol_index)
        assert weapon is None

        # Check the whole list

        '''
        [
         0=> {"name": "pistol, Sig D65",  # the index of this is stored
                                          # in __tank_fighter_pistol_index
              "type": "ranged weapon",
              "damage": {"dice": "1d+4"},
              "acc": 4,
              "ammo": {"name": "C Cell", "shots_left": 9, "shots": 9},
              "reload": 3,
              "skill": "Guns (Pistol)",
              "count": 1, <------------------------------------------- now 2
              "owners": None,
              "notes": ""
             },
         1=> {"name": "sick stick",
              "type": "melee weapon",
              "damage": {"dice": "1d+1 fat"},
              "skill": "Axe/Mace",
              "count": 1,
              "owners": None,
              "notes": ""
             },
         2=> {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
              "owners": None,
             },
         3=> {"name": "pistol, Sig D65",  # the index of this is stored
                                          # in __tank_fighter_pistol_index
              "type": "ranged weapon",
              "damage": {"dice": "1d+4"},
              "acc": 4, <---------------------- now 5 -- this is similar item
              "ammo": {"name": "C Cell", "shots_left": 9, "shots": 9},
              "reload": 3,
              "skill": "Guns (Pistol)",
              "count": 1,
              "owners": None,
              "notes": ""
             },
         4=> {"name": "pistol, Baretta DX 192", XXXXX--different item-removed
              "type": "ranged weapon",
              "damage": {"dice": "1d+4"},
              "acc": 2,
              "ammo": {"name": "C Cell", "shots_left": 8, "shots": 8},
              "reload": 3,
              "skill": "Guns (Pistol)",
              "count": 1,
              "owners": None,
              "notes": ""
             }
        ]
        '''
        weapon = fighter.equipment.get_item_by_index(0)
        assert weapon['name'] == "pistol, Sig D65"
        assert weapon['acc'] == 4
        assert weapon['count'] == 2

        weapon = fighter.equipment.get_item_by_index(1)
        assert weapon['name'] == "sick stick"
        assert weapon['count'] == 1

        weapon = fighter.equipment.get_item_by_index(2)
        assert weapon['name'] == "C Cell"
        assert weapon['count'] == 5

        weapon = fighter.equipment.get_item_by_index(3)
        assert weapon['name'] == "pistol, Sig D65"
        assert weapon['acc'] == 5
        assert weapon['count'] == 1

        weapon = fighter.equipment.get_item_by_index(4)  # Removed
        assert weapon is None

        # check weapon index

        sick_stick_index = 1
        self.__ruleset.do_action(fighter,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': sick_stick_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = fighter.get_current_weapon()
        assert actual_weapon_index == sick_stick_index

        # remove counted item before weapon index

        sig_acc_4_index = 0
        self.__window_manager.set_input_box_response(
                'How Many Items (2 Available)?', 1)
        fighter.remove_equipment(sig_acc_4_index) # Should just reduce the count
        weapon = fighter.equipment.get_item_by_index(0)
        assert weapon['name'] == "pistol, Sig D65"
        assert weapon['acc'] == 4
        assert weapon['count'] == 1
        weapon, actual_weapon_index = fighter.get_current_weapon()
        assert actual_weapon_index == sick_stick_index

        # remove non-counted item before weapon index
        fighter.remove_equipment(sig_acc_4_index) # Should remove item
        sick_stick_index -= 1
        weapon = fighter.equipment.get_item_by_index(sick_stick_index)
        assert weapon['name'] == "sick stick"
        weapon, actual_weapon_index = fighter.get_current_weapon()
        assert weapon.name == "sick stick"
        assert actual_weapon_index == sick_stick_index

        # remove item after weapon index
        sig_acc_5_index = 2
        fighter.remove_equipment(sig_acc_5_index)
        weapon = fighter.equipment.get_item_by_index(sick_stick_index)
        assert weapon['name'] == "sick stick"
        weapon, actual_weapon_index = fighter.get_current_weapon()
        assert weapon.name == "sick stick"
        assert actual_weapon_index == sick_stick_index

        # remove item at weapon index
        fighter.remove_equipment(sick_stick_index)
        weapon, actual_weapon_index = fighter.get_current_weapon()
        assert weapon is None
        assert actual_weapon_index is None

    def test_redirects(self):
        '''
        Basic test
        '''
        if ARGS.verbose:
            print '\n=== test_redirects ===\n'

        base_world_dict = copy.deepcopy(self.base_world_dict)
        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)

        # Verify that redirect that's in the World object works the way I
        # expect it to.

        source_char = world.get_creature_details('One More Guy', 'NPCs')
        dest_char = world.get_creature_details('One More Guy', 'Dima\'s Crew')
        assert self.__are_equal(source_char, dest_char)

    def test_redirects_promote_to_NPC(self):
        '''
        Basic test
        '''
        if ARGS.verbose:
            print '\n=== test_redirects_promote_to_NPC ===\n'

        init_world_dict = copy.deepcopy(self.init_world_dict)
        world_data = WorldData(init_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)
        self.__window_manager.reset_error_state()

        # random.randint(1, 6) should generate: 1 2 4 4 4 4 5 6 4 4
        random.seed(9001)  # 9001 is an arbitrary number

        # expected = [{'name': 'Famine',    'group': 'horsemen'}, # 5.75, 12, 4
        monster_famine_index = 0
        #            {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
        pc_jack_index = 1
        #            {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
        pc_moe_index = 2
        #            {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 4
        monster_pestilence_index = 3
        #            {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1
        pc_manny_index = 4

        fight_handler = ca.FightHandler(self.__window_manager,
                                        world,
                                        "horsemen",
                                        None,  # Playback history
                                        save_snapshot=False)

        # FightHandler.promote_to_NPC - check good change #

        fight_handler.set_viewing_index(monster_pestilence_index)
        fight_handler.promote_to_NPC()
        # There should now be an NPC named pestilence
        source_char = world.get_creature_details('Pestilence', 'horsemen')
        dest_char = world.get_creature_details('Pestilence', 'NPCs')
        assert self.__are_equal(source_char, dest_char)

        # FightHandler.promote_to_NPC - check destination has an NPC #

        self.__window_manager.expect_error(
                ['There\'s already an NPC named Pestilence'])
        fight_handler.set_viewing_index(monster_pestilence_index)
        fight_handler.promote_to_NPC()

        assert(self.__window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # TODO: FightHandler.promote_to_NPC - check source already an NPC #

        # if npc_name not in self.__world.details['NPCs']:
        # self._window_manager.error(['%s is already an NPC' %
        #                             new_NPC.name])

    def test_NPC_joins(self):
        '''
        Basic test
        '''
        if ARGS.verbose:
            print '\n=== test_NPC_joins ===\n'

        # NOTE: These indexes assume that we're NOT creating a fight.  When we
        # create a fight, a Fight object '<< ROOM >>' will be created and
        # added to the beginning of the fight.  The indexes, in that case,
        # will be increased by 1 since the Fight will have index 0.  These
        # indexes, however, are not used in the tests that create a new fight.

        # << ROOM >> -- not in the tests that use indexes

        # {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
        pc_jack_index = 0

        # {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1
        pc_manny_index = 1

        # {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
        pc_moe_index = 2
        last_pc_index = 2

        # Chico
        chico_index = 0

        # Grouch
        groucho_index = 1

        # Zeppo
        zeppo_index = 2

        #    'fights': {
        #        'horsemen': {
        #          'monsters': {
        #            # 5.75, 12, rand=4
        #            'Famine': copy.deepcopy(self.__thief_fighter),
        #
        #            # 5.5, 11, rand=4
        #            'Pestilence': copy.deepcopy(self.__vodou_priest_fighter),
        #          }
        #        }
        #    },

        init_world_dict = copy.deepcopy(self.init_world_dict)
        world_data = WorldData(init_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False)
        self.__window_manager.set_menu_response('Which Template Group',
                                                'dudes')
        npc_handler = ca.PersonnelHandler(self.__window_manager,
                                          world,
                                          ca.PersonnelHandler.NPCs)

        self.__window_manager.set_menu_response('Which Template Group',
                                                'dudes')
        pc_handler = ca.PersonnelHandler(self.__window_manager,
                                         world,
                                         ca.PersonnelHandler.PCs)

        # PersonnelHandler.NPC_joins_monsters - not an NPC #

        if ARGS.verbose:
            print '\n----------- NPC_joins_monsters - not an NPC -----------\n'

        self.__window_manager.reset_error_state()

        pc_handler.set_viewing_index(pc_manny_index)
        fighter = pc_handler.get_obj_from_index()
        self.__window_manager.expect_error(['"Manny" not an NPC'])

        self.__window_manager.set_menu_response('Join Which Fight', 'horsemen')
        pc_handler.NPC_joins_monsters()

        assert(self.__window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # PersonnelHandler.NPC_joins_monsters - works #

        if ARGS.verbose:
            print '\n----------- NPC_joins_monsters - works -----------\n'

        self.__window_manager.reset_error_state()

        npc_handler.set_viewing_index(groucho_index)
        fighter = npc_handler.get_obj_from_index()
        assert fighter.name == 'Groucho'

        self.__window_manager.set_menu_response('Join Which Fight', 'horsemen')
        npc_handler.NPC_joins_monsters()

        source_char = world.get_creature_details('Groucho', 'NPCs')
        dest_char = world.get_creature_details('Groucho', 'horsemen')
        assert self.__are_equal(source_char, dest_char)

        # PersonnelHandler.NPC_joins_monsters - NPC already in fight #

        if ARGS.verbose:
            print '\n--- NPC_joins_monsters - NPC already with monster ---\n'

        npc_handler.set_viewing_index(groucho_index)
        fighter = npc_handler.get_obj_from_index()
        assert fighter.name == 'Groucho'

        self.__window_manager.set_menu_response('Join Which Fight', 'horsemen')
        self.__window_manager.expect_error(
                ['"Groucho" already in fight "horsemen"'])

        npc_handler.NPC_joins_monsters()

        assert(self.__window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # PersonnelHandler.NPC_joins_PCs -- not a PC #

        if ARGS.verbose:
            print '\n----------- NPC_joins_PCs - not a PC -----------\n'

        pc_handler.set_viewing_index(pc_manny_index)
        fighter = pc_handler.get_obj_from_index()
        assert fighter.name == 'Manny'

        self.__window_manager.expect_error(['"Manny" not an NPC'])

        pc_handler.NPC_joins_monsters()

        assert(self.__window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # PersonnelHandler.NPC_joins_PCs -- works #

        if ARGS.verbose:
            print '\n----------- NPC_joins_PCs - works -----------\n'

        self.__window_manager.reset_error_state()

        # Doing zeppo so he gets put at the end of the alphabetized PC list
        # to make the next test work.
        npc_handler.set_viewing_index(zeppo_index)
        fighter = npc_handler.get_obj_from_index()
        assert fighter.name == 'Zeppo'

        npc_handler.NPC_joins_PCs()

        source_char = world.get_creature_details('Zeppo', 'NPCs')
        dest_char = world.get_creature_details('Zeppo', 'PCs')
        assert self.__are_equal(source_char, dest_char)

        # PersonnelHandler.NPC_joins_PCs -- already a PC #
        #
        # There isn't a case where something's already a PC where it doesn't
        # fire the 'Not an NPC' error.
        # if ARGS.verbose:
        #    print '\n-------- NPC_joins_PCs - NPC already a PC  --------\n'

        # Zeppo should have been put at the end of the alphabetized PC list by
        # the last test.  Now we know the index of an NPC that is also a PC.
        # npc_handler.set_viewing_index(last_pc_index + 1)
        # fighter = npc_handler.get_obj_from_index()
        # assert fighter.name == 'Zeppo'

        # self.__window_manager.expect_error(['"Zeppo" already a PC'])

        # npc_handler.NPC_joins_monsters()

        # assert(self.__window_manager.error_state ==
        #                            MockWindowManager.FOUND_EXPECTED_ERROR)

    def test_new_fight_new_creatures(self):
        '''
        Basic test
        '''
        # CREATE FIGHT -- WORKING #

        if ARGS.verbose:
            print '\n=== test_new_fight_new_creatures ===\n'

        world_dict = copy.deepcopy(self.base_world_dict)
        world_data = WorldData(world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self.__ruleset,
                         mock_program,
                         self.__window_manager,
                         save_snapshot=False
                         )

        self.__window_manager.clear_menu_responses()
        self.__window_manager.set_menu_response('New or Pre-Existing', 'new')
        self.__window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self.__window_manager.set_input_box_response('New Fight Name',
                                                     'test_new_fight')
        self.__window_manager.set_menu_response('Monster', 'VodouCleric')
        self.__window_manager.set_input_box_response('Monster Name', 'Horatio')
        self.__window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self.__window_manager,
                                           world,
                                           ca.PersonnelHandler.MONSTERs)

        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        fights = world.get_fights()
        assert 'test_new_fight' in fights  # verify that fight  exists
        if 'test_new_fight' in fights:
            creatures = world.get_creature_details_list('test_new_fight')
            if ARGS.verbose:
                print 'Expect: Room, Horatio:'
                PP.pprint(creatures)
            # The 'creatures' should be '<< ROOM >>', '1 - Horatio'
            assert '1 - Horatio' in creatures

        # FIGHT ALREADY EXISTS #

        if ARGS.verbose:
            print '\n--- Test: Fight Already Exists ---\n'

        self.__window_manager.reset_error_state()
        self.__window_manager.clear_menu_responses()
        self.__window_manager.set_menu_response('New or Pre-Existing', 'new')
        self.__window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        # This one should error out
        self.__window_manager.set_input_box_response('New Fight Name',
                                                     'test_new_fight')
        # This one should work
        self.__window_manager.set_input_box_response('New Fight Name', 'foo')

        self.__window_manager.expect_error(
                ['Fight name "test_new_fight" already exists'])

        # These are just so that the test finishes.
        self.__window_manager.set_menu_response('Monster', 'VodouCleric')
        self.__window_manager.set_input_box_response('Monster Name', 'Horatio')
        self.__window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self.__window_manager,
                                           world,
                                           ca.PersonnelHandler.MONSTERs)

        assert(self.__window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        # ADD A CREATURE, DELETE A MONSTER -- WORKS #

        if ARGS.verbose:
            print '\n--- Test: Add and Delete Monster ---\n'

        self.__window_manager.clear_menu_responses()
        self.__window_manager.set_menu_response('New or Pre-Existing',
                                                'existing')
        self.__window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self.__window_manager.set_menu_response('To Which Group',
                                                'test_new_fight')

        self.__window_manager.set_menu_response('Monster', 'VodouCleric')
        self.__window_manager.set_input_box_response('Monster Name', 'Ophelia')

        build_fight = TestPersonnelHandler(self.__window_manager,
                                           world,
                                           ca.PersonnelHandler.MONSTERs)

        build_fight.set_command_ribbon_input('a')   # Add Ophelia

        # The 'creatures' should be '<< ROOM >>', '1 - Horatio', '2 - Ophelia'
        # Delete Horatio

        build_fight.set_command_ribbon_input(curses.KEY_UP)
        build_fight.set_command_ribbon_input('d')   # Delete Horatio
        self.__window_manager.set_menu_response(
                'Delete "1 - Horatio" ARE YOU SURE?', 'yes')
        # finish up the test

        self.__window_manager.set_menu_response('What Next', 'quit')
        build_fight.set_command_ribbon_input('q')   # Quit

        build_fight.handle_user_input_until_done()

        fights = world.get_fights()
        assert 'test_new_fight' in fights  # verify that fight  exists
        if 'test_new_fight' in fights:
            creatures = world.get_creature_details_list('test_new_fight')
            assert '1 - Horatio' not in creatures
            assert '2 - Ophelia' in creatures

        # ADD PCs -- WORKS #

        if ARGS.verbose:
            print '\n--- Test: Add PCs ---\n'

        group = 'PCs'
        self.__window_manager.clear_menu_responses()
        self.__window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self.__window_manager.set_menu_response('Monster', 'VodouCleric')
        self.__window_manager.set_input_box_response('Monster Name', 'Skippy')
        self.__window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self.__window_manager,
                                           world,
                                           ca.PersonnelHandler.PCs)

        build_fight.set_command_ribbon_input('a')
        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        creatures = world.get_creature_details_list(group)
        assert 'Skippy' in creatures

        # ADD NPCs #

        if ARGS.verbose:
            print '\n--- Test: Add NPCs ---\n'

        group = 'NPCs'
        self.__window_manager.clear_menu_responses()
        self.__window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self.__window_manager.set_menu_response('Monster', 'VodouCleric')
        self.__window_manager.set_input_box_response('Monster Name', 'Stinky')
        self.__window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self.__window_manager,
                                           world,
                                           ca.PersonnelHandler.NPCs)

        build_fight.set_command_ribbon_input('a')
        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        creatures = world.get_creature_details_list(group)
        assert 'Stinky' in creatures


class MyArgumentParser(argparse.ArgumentParser):
    '''
    Code to add better error messages to argparse.
    '''
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


if __name__ == '__main__':
    parser = MyArgumentParser()
    # parser.add_argument('filename',
    #         nargs='?', # We get the filename elsewhere if you don't say here
    #         help='Input JSON file containing characters and monsters')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)
    ARGS = parser.parse_args()

    PP = pprint.PrettyPrinter(indent=3, width=150)
    unittest.main()  # runs all tests in this file
