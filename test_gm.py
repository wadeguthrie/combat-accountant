#! /usr/bin/python

import copy
import gm
import pprint
import random
import unittest

# Save a fight
# TODO: test that saving a fight and starting up again doesn't change the
#       fight (pending actions, injuries, fight order)

# Opponents
# TODO: test that pick opponent gives you all of the other side and none of
#       the current side
# TODO: test that pick opponent actually selects the opponent that you want
# TODO: test that a non-engaged opponent asks for a two-way and that an
#       engaged one does not

# Looting bodies
# TODO: test that looting bodies works:
#           * moving something from one body to another works properly
#           * only loot unconscious and dead monsters
# TODO: test that quitting a fight offers to loot and save when appropriate
#       and not when not:
#       (4 tests: loot, save; loot, no save; no loot, save; no loot, no save)

# Notes
# TODO: test that notes are saved properly

# -- BuildFightHandler --
# TODO: test that adding a creature works
# TODO: test that deleting a creature works
# TODO: test that you can add to the PCs
# TODO: test that you can add to a monster group
# TODO: test that you can create a new monster group
# TODO: make sure that the templates work as expected (try a blank one, try
#       two others with two different data sets)

# -- OutfitCharactersHandler --
# TODO: test that adding something actually adds the right thing and that it's
#       permenant
# TODO: test that removing something works

class BaseWorld(object):
    def __init__(self, world_dict):
        self.read_data = copy.deepcopy(world_dict)

class MockFightHandler(object):
    def add_to_history(self, action):
        pass

class MockFightGmWindow(object):
    def __init__(self, ruleset):
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
                     saved,
                     keep_monsters,
                     next_PC_name,
                     input_filename,
                     maintain_json):
        pass

    def clear(self):
        pass

    def close(self):
        pass

    def status_ribbon(self, input_filename, maintain_json):
        pass

    def command_ribbon(self, choices):
        pass

    def getmaxyx(self):
        return 10, 10


class MockWindowManager(object):
    def __init__(self):
        self.__menu_responses = {} # {menu_title: [selection, selection...]
        self.__char_responses = [] # array of characters

    def error(self, string_array):
        pass

    def display_window(self,
                       title,
                       lines  # [{'text', 'mode'}, ...]
                      ):
        pass

    def set_menu_response(self,
                          title,
                          selection # first part of string_results tuple
                         ):
        #print 'set_menu_response: title: %s, add selection:' % title
        #print '    ',
        #PP.pprint(selection)

        if title not in self.__menu_responses:
            self.__menu_responses[title] = []
        self.__menu_responses[title].append(selection)

        #print '  gives us a response queue of:'
        #print '    ',
        #PP.pprint(self.__menu_responses)

    def menu(self,
             title,
             strings_results, # array of tuples (string, return value)
             starting_index = 0 # Who is selected when the menu starts
            ):
        if title not in self.__menu_responses:
            print ('** didn\'t find menu title "%s" in stored responses' %
                    title)
            assert False
        if len(self.__menu_responses[title]) == 0:
            print ('** menu responses["%s"] is empty, can\'t respond' %
                    title)
            assert False

        result = self.__menu_responses[title].pop()

        #print 'menu: title: %s, returning:' % title
        #print '    ',
        #PP.pprint(result)
        #print '  gives us a response queue of:'
        #print '    ',
        #PP.pprint(self.__menu_responses)

        return result
        

    def get_fight_gm_window(self, ruleset):
        return MockFightGmWindow(ruleset)

    def set_char_response(self,
                          selection # character
                         ):
        #print 'set_char_response: add selection:'
        #print '    ',
        #PP.pprint(chr(selection))

        self.__char_responses.append(selection)

        #print '  gives us a response queue of:'
        #print '    ',
        #PP.pprint(self.__char_responses)

    def get_one_character(self):

        if len(self.__char_responses) == 0:
            print '** character responses is empty, can\'t respond'
            assert False
        result = self.__char_responses.pop()

        #print 'get_one_character: returning:'
        #print '    ',
        #PP.pprint(chr(result))
        #print '  gives us a response queue of:'
        #print '    ',
        #PP.pprint(self.__char_responses)

        return result

class GmTestCase(unittest.TestCase): # Derive from unittest.TestCase
    def setUp(self):
        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        self.__crawling_attack_mod = -4
        self.__crawling_defense_mod = -3

        self.__colt_pistol_acc = 3
        self.__vodou_priest_fighter_pistol_skill = 15
        self.__vodou_priest_fighter = {
            "shock": 0, 
            "stunned": False,
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                 {"name": "pistol, Colt 170D",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": self.__colt_pistol_acc,
                  "ammo": {"name": "C Cell", "shots_left": 9, "shots": 9},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": 1,
                  "notes": None
                 },
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
                  "owners": None }
            ],
            "skills": {"Guns (Pistol)":
                                    self.__vodou_priest_fighter_pistol_skill,
                       "Brawling": 12},
            "advantages": {"Combat Reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
            "current": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10, "ht": 11, "st": 10,
                "dx": 11, "basic-speed": 5.5
            }, 
            "permanent": {
                "fp": 12, "iq": 13, "wi": 13, "hp": 10, "ht": 11, "st": 10,
                "dx": 11, "basic-speed": 5.5
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
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                 {"name": "pistol, Colt 170D",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": 3,
                  "ammo": {"name": "C Cell", "shots_left": 9, "shots": 9},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""
                 },
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
                  "owners": None,
                 }
            ],
            "skills": {"Guns (Pistol)": 15, "Brawling": 12},
            "advantages": {"Combat Reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
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
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                 {"name": "pistol, Kalashnikov Makarov",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+3"},
                  "acc": 2,
                  "ammo": {"name": "C Cell", "shots_left": 8, "shots": 8},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""
                 },
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
                  "owners": None,
                 }
            ],
            "skills": {"Guns (Pistol)": 13, "Brawling": 12},
            "advantages": {"Combat Reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
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
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                 {"name": "pistol, Sig D65",  # the index of this is stored
                                              # in __tank_fighter_pistol_index
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": 4,
                  "ammo": {"name": "C Cell", "shots_left": 9, "shots": 9},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""
                 },
                 {"name": "sick stick",
                  "type": "melee weapon",
                  "damage": {"dice": "1d+1 fat"},
                  "skill": "Axe/Mace",
                  "count": 1,
                  "owners": None,
                  "notes": ""
                 },
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
                  "owners": None,
                 }
            ],
            "skills": {"Guns (Pistol)": 16, "Brawling": 16, "Axe/Mace": 14},
            "advantages": {"Combat Reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
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
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                 {"name": "pistol, Baretta DX 192",
                  "type": "ranged weapon",
                  "damage": {"dice": "1d+4"},
                  "acc": 2,
                  "ammo": {"name": "C Cell", "shots_left": 8, "shots": 8},
                  "reload": 3,
                  "skill": "Guns (Pistol)",
                  "count": 1,
                  "owners": None,
                  "notes": ""
                 },
                 {"name": "Large Knife",
                  "type": "melee weapon",
                  "damage": {"dice": "1d-2", "type": "imp"},
                  "skill": "Knife",
                  "parry": -1,
                  "count": 1,
                  "owners": None,
                  "notes": ""
                 },
                 {"count": 1, 
                  "name": "brass knuckles", 
                  "notes": "B271", 
                  "damage": { "thr": {"plus": 0, "type": "cr"} }, 
                  "parry": 0, 
                  "skill": "Karate", 
                  "owners": None,
                  "type": "melee weapon"
                 },
                 {"name": "C Cell", "type": "misc", "count": 5, "notes": "",
                  "owners": None,
                 }
            ],
            "skills": {"Guns (Pistol)": 12,
                       "Brawling": 14,
                       "Knife": self.__thief_knife_skill},
            "advantages": {},
            "state" : "alive",
            "posture" : "standing",
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


        self.base_world_dict = {
          "Templates": {
            "Arena Combat": {
              "VodouCleric": {
                "permanent": {
                  "fp": { "type": "value", "value": 12 }, 
                  "iq": { "type": "value", "value": 13 }, 
                  "wi": { "type": "value", "value": 13 }, 
                  "hp": { "type": "value", "value": 10 }, 
                  "ht": { "type": "value", "value": 11 }, 
                  "st": { "type": "value", "value": 10 }, 
                  "dx": { "type": "value", "value": 11 }, 
                  "basic-speed": { "type": "value", "value": 5.5 }
                }
              }, 
            }
          },  # Templates
          "PCs": {
            "Vodou Priest": self.__vodou_priest_fighter, 
            "One More Guy": self.__one_more_guy, 
          }, # PCs
          "dead-monsters": [
            {"name": "Arena Attack Monsters",
             "fight": {
              "5-Tank-B": {
                "state": "alive", 
                "current":
                    {"fp":11,"iq":12,"wi":12,"hp":11,"ht":11,"st":10,"dx":12},
                "permanent":
                    {"fp":11,"iq":12,"wi":12,"hp":11,"ht":11,"st":10,"dx":12}, 
              }, # 5-Tank-B
              "date": None
              }
            } # Arena Attack Monsters
          ], # dead-monsters
          "current-fight": {
            "index": 0, 
            "monsters": "Anybody", 
            "fighters": [
              { "group": "Anybody", "name": "Bokor Fighter" }, 
              { "group": "PCs", "name": "Vodou Priest" }, 
              { "group": "PCs", "name": "One More Guy" }, 
              { "group": "Anybody", "name": "Tank Fighter" }, 
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
                    {"fp":11,"iq":12,"wi":12,"hp":11,"ht":11,"st":10,"dx":12},
                "permanent":
                    {"fp":11,"iq":12,"wi":12,"hp":11,"ht":11,"st":10,"dx":12}, 
            }, 
            "One More Guy": self.__one_more_guy
          }, # NPCs
          "fights": {
            "Dima's Crew": {
              "Bokor Fighter": self.__bokor_fighter, 
              "Tank Fighter": self.__tank_fighter , 
              "One More Guy": { "redirect": "NPCs" }
            }, 
            "1st Hunting Party": {
              "5: Amelia": self.__thief_fighter, 
            }
          } # fights
        } # End of the world

        self.init_world_dict = {
            # Don't need templates, dead-monsters, equipment, names
            'PCs': {
                # 5.25, 10, rand=1
                'Manny' : copy.deepcopy(self.__bokor_fighter),

                # 5.75, 12, rand=2
                'Jack' : copy.deepcopy(self.__tank_fighter),

                # 5.5, 12, rand=4
                'Moe' : copy.deepcopy(self.__one_more_guy),
            },
            'NPCs': {
            },
            'fights': {
                'horsemen' : {
                    # 5.75, 12, rand=4
                    'Famine' : copy.deepcopy(self.__thief_fighter),

                    # 5.5, 11, rand=4
                    'Pestilence' : copy.deepcopy(self.__vodou_priest_fighter),
                }
            },
            'current-fight': {
                # Needed
                'saved': False,
                'history': [], # Needed (maybe)

                'index': 1,
                'fighters': [],
                'round': 2,
                'monsters': 'horsemen',
            },
        } # End of world

        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)
    
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
    #### Actual Tests ####
    #

    def test_get_dodge_skill(self):
        # Deepcopy so that we don't taint the original
        vodou_priest = gm.Fighter('Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset,
                                  self.__window_manager)

        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == 9

        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'crawling'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == (9 + self.__crawling_defense_mod)

        # Next guy

        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset,
                                   self.__window_manager)

        self.__ruleset._change_posture({'fighter': bokor_fighter,
                                        'posture': 'standing'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == 9

        self.__ruleset._change_posture({'fighter': bokor_fighter,
                                        'posture': 'crawling'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == (9 + self.__crawling_defense_mod)

        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset,
                                  self.__window_manager)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(tank_fighter)
        assert dodge_skill == 9

        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset,
                                   self.__window_manager)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(thief_fighter)
        assert dodge_skill == 8

    def test_get_block_skill(self):
        # TODO: need non-trivial block tests
        vodou_priest_fighter = gm.Fighter(
                                  'Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset,
                                  self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(
                                                        vodou_priest_fighter,
                                                        None)
        assert block_skill == None

        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset,
                                   self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(bokor_fighter,
                                                                None)
        assert block_skill == None

        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset,
                                  self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(tank_fighter,
                                                                None)
        assert block_skill == None

        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset,
                                   self.__window_manager)
        block_skill, block_why = self.__ruleset.get_block_skill(thief_fighter,
                                                                None)
        assert block_skill == None

    def test_get_parry_skill(self):
        # Unarmed
        weapon = None
        vodou_priest_fighter = gm.Fighter(
                                    'Vodou Priest',
                                    'group',
                                    copy.deepcopy(self.__vodou_priest_fighter),
                                    self.__ruleset,
                                    self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(
                                                    vodou_priest_fighter,
                                                    weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset,
                                   self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(bokor_fighter,
                                                                weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset,
                                  self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Armed (sick stick)
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset,
                                  self.__window_manager)
        weapon_index, weapon  = tank_fighter.get_weapon_by_name('sick stick')
        tank_fighter.draw_weapon_by_index(weapon_index)

        self.__ruleset._change_posture({'fighter': tank_fighter,
                                        'posture': 'standing'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == 11

        self.__ruleset._change_posture({'fighter': tank_fighter,
                                        'posture': 'crawling'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == (11 + self.__crawling_defense_mod)

        # Unarmed
        weapon = None
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset,
                                   self.__window_manager)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Armed (Knife)
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset,
                                   self.__window_manager)
        weapon_index, weapon = thief_fighter.get_weapon_by_name('Large Knife')
        thief_fighter.draw_weapon_by_index(weapon_index)

        self.__ruleset._change_posture({'fighter': thief_fighter,
                                        'posture': 'standing'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == 9

        self.__ruleset._change_posture({'fighter': thief_fighter,
                                        'posture': 'crawling'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == (9 + self.__crawling_defense_mod)

    def test_get_unarmed_info(self):
        # Vodou Priest
        unarmed_skills = self.__ruleset.get_weapons_unarmed_skills(None)
        vodou_priest_fighter = gm.Fighter(
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
        bokor_fighter = gm.Fighter('Bokor',
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
        tank_fighter = gm.Fighter('Tank',
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
        thief_fighter = gm.Fighter('Thief',
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

        self.__ruleset._change_posture({'fighter': thief_fighter,
                                        'posture': 'crawling'})
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == (14
                                                + self.__crawling_attack_mod)
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == (12
                                                + self.__crawling_attack_mod)
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == (10
                                                + self.__crawling_defense_mod)

        # Thief w/o brass knuckles
        thief_fighter = gm.Fighter('Thief',
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

        self.__ruleset._change_posture({'fighter': thief_fighter,
                                        'posture': 'standing'})

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
        self.__ruleset._change_posture({'fighter': thief_fighter,
                                        'posture': 'crawling'}) # -2
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
        self.__ruleset._change_posture({'fighter': thief_fighter,
                                        'posture': 'standing'})
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
        random_debug_filename = 'foo'

        world_obj = BaseWorld(self.init_world_dict)
        world = gm.World(world_obj, self.__window_manager)

        # Famine and Jack have the same basic speed and dx -- it's up to rand
        # Pestilence and Moe have same basic speed but different dx
        expected = [{'name': 'Famine',     'group': 'horsemen'}, # 5.75, 12, 4
                    {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
                    {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
                    {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 4
                    {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1

        # Do this multiple times just to verify that the random stuff works
        for i in range(10):
            # random.randint(1, 6) should generate: 1 2 4 4 4 4 5 6 4 4
            random.seed(9001) # 9001 is an arbitrary number
            fight_handler = gm.FightHandler(self.__window_manager,
                                            world,
                                            'horsemen',
                                            self.__ruleset,
                                            random_debug_filename,
                                            filename='*INTERNAL*'
                                           )
            fighters = fight_handler.get_fighters()

            # Check the order against the one that I expect

            for index, ignore in enumerate(fighters):
                assert fighters[index]['name'] == expected[index]['name']
                assert fighters[index]['group'] == expected[index]['group']

        # test that modify index wraps
        # test that cycling a whole round goes to each fighter in order

        expected_index = 0
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 1
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        injured_fighter = current_fighter
        injured_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 2
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        unconscious_fighter = current_fighter
        unconscious_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 3
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        dead_fighter = current_fighter
        dead_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 4
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 0 # wraps
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # test that an unconscious fighter is not skipped but a dead one is

        injured_hp = 3 # arbitrary amount
        injured_fighter.details['current']['hp'] -= injured_hp
        unconscious_fighter.set_consciousness(gm.Fighter.UNCONSCIOUS)
        dead_fighter.set_consciousness(gm.Fighter.DEAD)

        assert injured_fighter.get_state() == gm.Fighter.INJURED
        assert unconscious_fighter.get_state() == gm.Fighter.UNCONSCIOUS
        assert dead_fighter.get_state() == gm.Fighter.DEAD

        expected_index = 0
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # This is the injured fighter -- should still see this one
        fight_handler.modify_index(1)
        expected_index = 1
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # This is the unconscious fighter -- should still see this one
        fight_handler.modify_index(1)
        expected_index = 2
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # Should skip the dead fighter

        fight_handler.modify_index(1)
        expected_index = 4
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 0 # wraps
        assert world_obj.read_data['current-fight']['index'] == expected_index
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
        This is just like test_initiative_order_again except the fighters are
        reordered randomly and a different random seed is used.
        '''

        random_debug_filename = 'foo'

        world_obj = BaseWorld({
            # Don't need templates, dead-monsters, equipment, names
            'PCs': {
                # 5.5, 11, rand=2
                'Bob' : copy.deepcopy(self.__vodou_priest_fighter),

                # 5.75, 12, rand=3
                'Ted' : copy.deepcopy(self.__tank_fighter),
            },
            'fights': {
                'marx' : {
                    # 5.5, 12, rand=4
                    'Groucho' : copy.deepcopy(self.__one_more_guy),

                    # 5.75, 12, rand=5
                    'Harpo' : copy.deepcopy(self.__thief_fighter),

                    # 5.25, 10, rand=3
                    'Chico' : copy.deepcopy(self.__bokor_fighter),
                }
            },
            'current-fight': {
                # Needed
                'saved': False,
                'history': [], # Needed (maybe)

                # Not needed if not saved
                'index': 1,
                'fighters': [],
                'round': 2,
                'monsters': 'marx',
            },
        })

        world = gm.World(world_obj, self.__window_manager)

        # Famine and Jack have the same basic speed and dx -- it's up to rand
        # Pestilence and Moe have same basic speed but different dx
        expected = [
                    {'name': 'Harpo',   'group': 'marx'}, # 5.75, 12, 5
                    {'name': 'Ted',     'group': 'PCs'},  # 5.75, 12, 3
                    {'name': 'Groucho', 'group': 'marx'}, # 5.5,  12, 4
                    {'name': 'Bob',     'group': 'PCs'},  # 5.5,  11, 2
                    {'name': 'Chico',   'group': 'marx'}, # 5.25, 10, 3
                   ]

        # Do this multiple times just to verify that the random stuff works
        for i in range(10):
            # random.randint(1, 6) should generate: 2 3 4 5 3
            random.seed(8534) # 8534 is an arbitrary number
            fight_handler = gm.FightHandler(self.__window_manager,
                                            world,
                                            'marx',
                                            self.__ruleset,
                                            random_debug_filename,
                                            filename='*INTERNAL*'
                                           )
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

        random_debug_filename = 'foo'
        world_obj = BaseWorld({
            # Don't need templates, dead-monsters, equipment, names
            'PCs': {
                # 5.25, 10, rand=1
                'Manny' : copy.deepcopy(self.__bokor_fighter),

                # 5.75, 12, rand=2
                'Jack' : copy.deepcopy(self.__tank_fighter),

                # 5.5, 12, rand=4
                'Moe' : copy.deepcopy(self.__one_more_guy),
            },
            'fights': {
                'horsemen' : {
                    # 5.75, 12, rand=4
                    'Famine' : copy.deepcopy(self.__thief_fighter),

                    # 5.5, 11, rand=4
                    'Pestilence' : copy.deepcopy(self.__vodou_priest_fighter),
                }
            },
            'current-fight': {
                # Needed
                'saved': False,
                'history': [], # Needed (maybe)

                'index': 1,
                'fighters': [],
                'round': 2,
                'monsters': 'horsemen',
            },
        })

        world = gm.World(world_obj, self.__window_manager)

        # Famine and Jack have the same basic speed and dx -- it's up to rand
        # Pestilence and Moe have same basic speed but different dx
        expected = [{'name': 'Famine',     'group': 'horsemen'}, # 5.75, 12, 4
                    {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
                    {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
                    {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 4
                    {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1

        injured_hp = 3 # This is arbitrary
        injured_index = 2

        random.seed(9001) # 9001 is an arbitrary number
        fight_handler = gm.FightHandler(self.__window_manager,
                                        world,
                                        'horsemen',
                                        self.__ruleset,
                                        random_debug_filename,
                                        filename='*INTERNAL*'
                                       )
        fighters = fight_handler.get_fighters()

        expected_index = 0
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Make fighter 0 fight figher 2
        current_fighter.details['opponent'] = {'group': 'PCs', 'name': 'Moe'}

        # Move ahead to fighter 1
        fight_handler.modify_index(1)
        expected_index = 1
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Wound fighter 2
        fighters[injured_index]['details']['current']['hp'] -= injured_hp

        # Cycle around to fighter 0

        fight_handler.modify_index(1)
        expected_index = 2
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        unconscious_fighter = current_fighter
        unconscious_index = expected_index

        fight_handler.modify_index(1)
        expected_index = 3
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        dead_fighter = current_fighter
        dead_index = expected_index

        fight_handler.modify_index(1)
        expected_index = 4
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()

        fight_handler.modify_index(1)
        expected_index = 0 # wraps
        assert world_obj.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Change opponent of fighter 0 to fighter 1 -- At one time, I saw a
        # bug where it appeared that changing an opponent from an injured one
        # (in this case, fighter 2/Moe) to a different fighter (in this case,
        # fighter 1/Jack) caused the damage to be transferred to the new
        # opponent.
        current_fighter.details['opponent'] = {'group': 'PCs', 'name': 'Jack'}

        # cycle completely around to fighter 1
        fight_handler.modify_index(1) # index 1
        fight_handler.modify_index(1) # index 2
        fight_handler.modify_index(1) # index 3
        fight_handler.modify_index(1) # index 4
        fight_handler.modify_index(1) # index 0
        fight_handler.modify_index(1) # index 1
        expected_index = 1
        assert world_obj.read_data['current-fight']['index'] == expected_index

        # Set expectations to the final configuration.

        expected_fighters = [
            copy.deepcopy(self.__thief_fighter),
            copy.deepcopy(self.__tank_fighter),
            copy.deepcopy(self.__one_more_guy),
            copy.deepcopy(self.__vodou_priest_fighter),
            copy.deepcopy(self.__bokor_fighter)]
        expected_fighters[0]['opponent']    = {'group': 'PCs', 'name': 'Jack'}
        expected_fighters[injured_index]['current']['hp'] -= injured_hp

        # Check that everything is as it should be

        assert len(expected_fighters) == len(fighters)
        assert self.__are_equal(expected_fighters[0], fighters[0]['details'])
        assert self.__are_equal(expected_fighters[1], fighters[1]['details'])
        assert self.__are_equal(expected_fighters[2], fighters[2]['details'])
        assert self.__are_equal(expected_fighters[3], fighters[3]['details'])
        assert self.__are_equal(expected_fighters[4], fighters[4]['details'])


    def test_ranged_to_hit(self):
        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)

        vodou_priest = gm.Fighter('Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset,
                                  self.__window_manager)
        requested_weapon_index = 0
        vodou_priest.draw_weapon_by_index(requested_weapon_index)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index
        mock_fight_handler = MockFightHandler()

        # ranged to-hit should be skill + acc (if aimed) + 1 (if braced)
        #   + size modifier + range/speed modifier + special conditions

        # aim for 1 turn += acc, 2 turns += 1, 3+ turns += 1
        # brace += 1

        # no aim, no posture

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        vodou_priest.reset_aim()
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})

        self.__ruleset.do_action(vodou_priest,
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit

        # aim / not braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc)
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit

        # no aim, posture (posture doesn't matter for ranged attacks: B551)

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'crawling'})
        vodou_priest.reset_aim()
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, posture (posture not counted for ranged attacks: B551)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                                                + self.__colt_pistol_acc # aim
                                                +1) # braced
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'crawling'})
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit


        # aim / not braced, posture (no posture minus for ranged attacks: B551)

        vodou_priest.reset_aim()
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc) # aim
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'crawling'})
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit

        # --- Opponents w/ posture ---

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        vodou_priest.reset_aim()
        tank = gm.Fighter('Tank',
                          'group',
                          copy.deepcopy(self.__tank_fighter),
                          self.__ruleset,
                          self.__window_manager)

        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})

        # Picking opponent doesn't change things
        self.__ruleset._change_posture({'fighter': tank,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, tank, weapon)
        assert to_hit == expected_to_hit

        # change posture of thief (-2)
        self.__ruleset._change_posture({'fighter': tank,
                                        'posture': 'crawling'}) # -2
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, tank, weapon)
        assert to_hit == (expected_to_hit - 2)

        # change posture of thief (back to standing)
        self.__ruleset._change_posture({'fighter': tank,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, tank, weapon)
        assert to_hit == expected_to_hit


    def test_messed_up_aim(self):
        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = gm.Fighter('Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset,
                                  self.__window_manager)
        requested_weapon_index = 0
        vodou_priest.draw_weapon_by_index(requested_weapon_index)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # Regular, no aim - for a baseline

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        vodou_priest.reset_aim()
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # Damage _would_ ruin aim except for successful Will roll

        vodou_priest.reset_aim()

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # adjust_hp but MADE Will roll
        damage = -1
        self.__window_manager.set_menu_response('roll <= WILL (13) or lose aim',
                                                True)

        self.__ruleset.do_action(vodou_priest,
                                 {'name': 'adjust-hp', 'adj': damage},
                                 mock_fight_handler)

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        # aiming for 3 rounds + shock
        assert to_hit == expected_to_hit + 2 + damage

        self.__ruleset.end_turn(vodou_priest) # to clear out shock

        # Damage ruins aim -- miss will roll

        vodou_priest.reset_aim()

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest,
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # adjust_hp and MISSES Will roll
        self.__window_manager.set_menu_response('roll <= WILL (13) or lose aim',
                                                False)
        damage = -1
        self.__ruleset.do_action(vodou_priest,
                                 {'name': 'adjust-hp', 'adj': damage},
                                 mock_fight_handler)

        # 3 rounds (well, 1 round)
        self.__ruleset.do_action(vodou_priest,
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + damage # aiming for 1 round + shock

        self.__ruleset.end_turn(vodou_priest) # to clear out shock

        # Draw weapon ruins aim

        vodou_priest.reset_aim()

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        self.__ruleset.do_action(vodou_priest,
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # Draw weapon
        self.__ruleset._draw_weapon({'fighter': vodou_priest,
                                     'weapon':  requested_weapon_index})

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit # aiming for 1 round

        # Posture ruins aim

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        vodou_priest.reset_aim()
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # Change posture
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'lying'})

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit # aiming for 1 round

        # Defense ruins aim

        vodou_priest.reset_aim()
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # Defend
        self.__ruleset._do_defense({'fighter': vodou_priest})

        # 3 rounds
        self.__ruleset.do_action(vodou_priest, 
                                 {'name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit # aiming for 3 rounds

        # Last One is Regular - shows nothing carries over

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        vodou_priest.reset_aim()
        self.__ruleset._change_posture({'fighter': vodou_priest,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit


    def test_melee_to_hit(self):
        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)
        mock_fight_handler = MockFightHandler()

        thief = gm.Fighter('Thief',
                           'group',
                           copy.deepcopy(self.__thief_fighter),
                           self.__ruleset,
                           self.__window_manager)
        requested_weapon_index = 1 # Knife
        thief.draw_weapon_by_index(requested_weapon_index)
        weapon, actual_weapon_index = thief.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # melee to-hit should be skill + special conditions

        # no posture
        expected_to_hit = self.__thief_knife_skill
        self.__ruleset._change_posture({'fighter': thief,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

        # posture
        expected_to_hit = (self.__thief_knife_skill
                                                + self.__crawling_attack_mod)
        self.__ruleset._change_posture({'fighter': thief,
                                        'posture': 'crawling'})
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

        # --- Opponents w/ posture (shouldn't change melee attack) ---

        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset,
                                  self.__window_manager)

        self.__ruleset._change_posture({'fighter': thief,
                                        'posture': 'standing'})

        # Picking opponent doesn't change things
        expected_to_hit = self.__thief_knife_skill
        self.__ruleset._change_posture({'fighter': tank_fighter,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(thief, tank_fighter, weapon)
        assert to_hit == expected_to_hit

        # change posture of tank (opponent)
        self.__ruleset._change_posture({'fighter': tank_fighter,
                                        'posture': 'crawling'}) # -2
        to_hit, why = self.__ruleset.get_to_hit(thief, tank_fighter, weapon)
        assert to_hit == expected_to_hit

        # change posture of thief (back to standing)
        self.__ruleset._change_posture({'fighter': tank_fighter,
                                        'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(thief, tank_fighter, weapon)
        assert to_hit == expected_to_hit

        # --- Aiming does not help ---

        thief.reset_aim()
        expected_to_hit = self.__thief_knife_skill
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)

        # 1 round
        self.__ruleset.do_action(thief, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        self.__ruleset.do_action(thief, 
                                 {'name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

    def test_timers(self):
        # TODO: timers should get their own class separated from the Fighter
        #       class.

        fighter = gm.Fighter('Tank',
                             'group',
                             copy.deepcopy(self.__tank_fighter),
                             self.__ruleset,
                             self.__window_manager)

        # Test a standard timer

        timer_id = 0
        round_count = 3
        timer_text = '%d' % timer_id
        fighter.add_timer(round_count, timer_text)

        for i in range(round_count):
            assert len(fighter.details['timers']) == 1
            assert fighter.details['timers'][0]['string'] == timer_text
            # At the _end_ of a fighter's turn, we remove all his expired
            # timers.  That causes the timer expiring this round to be shown.
            fighter.remove_expired_kill_dying_timers()
            fighter.decrement_timers()

        fighter.remove_expired_kill_dying_timers()
        assert len(fighter.details['timers']) == 0

        # Test 3 timers simultaneously

        timer_id = 0
        round_count = [1, 2, 3]
        timer_count = 3

        for i in range(timer_count):
            timer_text = '%d' % timer_id
            timer_id += 1
            fighter.add_timer(round_count[i], timer_text)

        # round 0
        fighter.remove_expired_kill_dying_timers()
        fighter.decrement_timers()
        assert len(fighter.details['timers']) == 3
        expected = ['0', '1', '2']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        # round 1
        fighter.remove_expired_kill_dying_timers()
        fighter.decrement_timers()
        assert len(fighter.details['timers']) == 2
        expected = ['1', '2']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        # round 2
        fighter.remove_expired_kill_dying_timers()
        fighter.decrement_timers()
        assert len(fighter.details['timers']) == 1
        expected = ['2']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        fighter.remove_expired_kill_dying_timers()
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
        fighter.add_timer(round_count, timer0_text)

        # start turn -- decrement 1-turn timer, timer = 0, keep it this turn
        fighter.decrement_timers()
        fighter.remove_expired_keep_dying_timers()

        # assert 1 timer -- didn't kill the 1-turn timer
        assert len(fighter.details['timers']) == 1
        assert fighter.details['timers'][0]['string'] == timer0_text

        # add 0.9 timer -- shown through this turn, killed before next turn
        timer_id = 1
        round_count = 0.9
        timer1_text = '%d' % timer_id
        fighter.add_timer(round_count, timer1_text)

        # assert 2 timers -- right: both timers are there
        assert len(fighter.details['timers']) == 2
        expected = ['0', '1']
        for timer in fighter.details['timers']:
            assert timer['string'] in expected
            expected.remove(timer['string'])

        # end turn -- kills 1 turn timer
        fighter.remove_expired_kill_dying_timers()

        # assert 1 timer -- show that the 1-turn timer was killed
        assert len(fighter.details['timers']) == 1
        assert fighter.details['timers'][0]['string'] == timer1_text

        # start turn - kills 0.9 timer before the next turn's stuff is shown
        fighter.decrement_timers()
        fighter.remove_expired_keep_dying_timers()

        # assert 0 timers -- yup, 0.9 timer is now gone
        assert len(fighter.details['timers']) == 0


    def test_save(self):
        base_world_dict = copy.deepcopy(self.base_world_dict)

        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)

        # Test that leaving a fight moves the bad guys to the dead monster
        # list
        # print '\n----------- LEAVE FIGHT -----------\n'

        world_obj = BaseWorld(base_world_dict)
        world = gm.World(world_obj, self.__window_manager)

        fight_handler = gm.FightHandler(self.__window_manager,
                                        world,
                                        "Dima's Crew", 
                                        self.__ruleset,
                                        "None", # used for bug reporting
                                        "filename") # used for display

        assert "Dima's Crew" in world_obj.read_data['fights']
        assert not self.__is_in_dead_monsters(world_obj, "Dima's Crew")
        assert world_obj.read_data['current-fight']['saved'] == False

        self.__window_manager.set_char_response(ord('q'))
        self.__window_manager.set_menu_response('Leaving Fight', {'doit':None})

        fight_handler.handle_user_input_until_done()
                                     
        assert "Dima's Crew" not in world_obj.read_data['fights']
        assert self.__is_in_dead_monsters(world_obj, "Dima's Crew")
        assert world_obj.read_data['current-fight']['saved'] == False

        #
        # test that SAVING the fight works
        #
        # print '\n----------- SAVE FIGHT -----------\n'

        world_obj = BaseWorld(base_world_dict)
        world = gm.World(world_obj, self.__window_manager)

        assert world_obj.read_data['current-fight']['monsters'] != "Dima's Crew"

        fight_handler = gm.FightHandler(self.__window_manager,
                                        world,
                                        "Dima's Crew", 
                                        self.__ruleset,
                                        "None", # used for bug reporting
                                        "filename") # used for display

        assert "Dima's Crew" in world_obj.read_data['fights']
        assert not self.__is_in_dead_monsters(world_obj, "Dima's Crew")
        assert world_obj.read_data['current-fight']['saved'] == False

        self.__window_manager.set_char_response(ord('q'))
        # It's a stack so I'm putting things in reverse order
        self.__window_manager.set_menu_response('Leaving Fight', {'doit':None})
        self.__window_manager.set_menu_response(
                    'Leaving Fight', {'doit': fight_handler.simply_save})


        fight_handler.handle_user_input_until_done()
                                     
        assert "Dima's Crew" in world_obj.read_data['fights']
        assert not self.__is_in_dead_monsters(world_obj, "Dima's Crew")
        assert world_obj.read_data['current-fight']['saved'] == True
        assert world_obj.read_data['current-fight']['monsters'] == "Dima's Crew"

        #
        # test that KEEPING the fight works
        #
        # print '\n----------- KEEP FIGHT -----------\n'

        world_obj = BaseWorld(base_world_dict)
        world = gm.World(world_obj, self.__window_manager)

        fight_handler = gm.FightHandler(self.__window_manager,
                                        world,
                                        "Dima's Crew", 
                                        self.__ruleset,
                                        "None", # used for bug reporting
                                        "filename") # used for display

        assert "Dima's Crew" in world_obj.read_data['fights']
        assert not self.__is_in_dead_monsters(world_obj, "Dima's Crew")
        assert world_obj.read_data['current-fight']['saved'] == False

        # It's a stack so I'm putting things in reverse order
        self.__window_manager.set_char_response(ord('q'))
        self.__window_manager.set_char_response(ord('k'))
        self.__window_manager.set_menu_response('Leaving Fight', {'doit':None})

        fight_handler.handle_user_input_until_done()
                                     
        assert "Dima's Crew" in world_obj.read_data['fights']
        assert not self.__is_in_dead_monsters(world_obj, "Dima's Crew")
        assert world_obj.read_data['current-fight']['saved'] == False

    def test_add_equipment(self):
        fighter = gm.Fighter('Tank',
                             'group',
                             copy.deepcopy(self.__tank_fighter),
                             self.__ruleset,
                             self.__window_manager)

        original_item = fighter.details['stuff'][
                                        self.__tank_fighter_pistol_index]
        current_count = len(fighter.details['stuff'])
        original_stuff = copy.deepcopy(fighter.details['stuff'])

        # Same item

        assert original_item['count'] == 1
        same_item = copy.deepcopy(original_item)
        same_item['count'] = 2
        fighter.add_equipment(same_item, 'test')
        assert original_item['count'] == 3

        # Similar item

        similar_item = copy.deepcopy(original_item)
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
                          "reload": 3,
                          "skill": "Guns (Pistol)",
                          "count": 1,
                          "owners": None,
                          "notes": ""
                         }

        assert len(fighter.details['stuff']) == current_count
        fighter.add_equipment(different_item, 'test')
        current_count += 1
        assert len(fighter.details['stuff']) == current_count

        # Make sure we only add to the end

        for i, original_item in enumerate(original_stuff):
            # We've changed the count on the fighter's pistol
            if i != self.__tank_fighter_pistol_index:
                assert self.__are_equal(original_item,
                                        fighter.details['stuff'][i])

    #def test_random_seed(self):
    #    for i in range(10):
    #        random.seed() # randomize
    #        new_seed = random.randint(1, 10000)
    #
    #        print '\nseed: %d' % new_seed
    #        for j in range(10):
    #            random.seed(new_seed)
    #            for k in range(5):
    #                print random.randint(1, 6),
    #            print ''

    def test_redirects(self):
        base_world_dict = copy.deepcopy(self.base_world_dict)
        world_obj = BaseWorld(base_world_dict)
        world = gm.World(world_obj, self.__window_manager)

        # Verify that redirect that's in the World object works the way I
        # expect it to.

        source_char = world.get_creature_details('One More Guy', 'NPCs')
        dest_char = world.get_creature_details('One More Guy', 'Dima\'s Crew')
        assert self.__are_equal(source_char, dest_char)

    def test_redirects_2(self):
        init_world_dict = copy.deepcopy(self.init_world_dict)
        world_obj = BaseWorld(init_world_dict)
        world = gm.World(world_obj, self.__window_manager)

        # random.randint(1, 6) should generate: 1 2 4 4 4 4 5 6 4 4
        random.seed(9001) # 9001 is an arbitrary number

        #expected = [{'name': 'Famine',     'group': 'horsemen'}, # 5.75, 12, 4
        monster_famine_index = 0
        #            {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
        pc_jack_index = 1
        #            {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
        pc_moe_index = 2
        #            {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 4
        monster_pestilence_index = 3
        #            {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1
        pc_manny_index = 4

        fight_handler = gm.FightHandler(self.__window_manager,
                                        world,
                                        "horsemen",
                                        self.__ruleset,
                                        "None", # used for bug reporting
                                        "filename") # used for display

        

        # FightHandler.__promote_to_NPC - check good change
        fight_handler.set_viewing_index(monster_pestilence_index)
        fight_handler.promote_to_NPC()
        # There should now be an NPC named pestilence
        source_char = world.get_creature_details('Pestilence','horsemen')
        dest_char = world.get_creature_details('Pestilence','NPCs')
        assert self.__are_equal(source_char, dest_char)

        # TODO: FightHandler.__promote_to_NPC - check already an NPC
        #fight_handler.set_viewing_index(new_index):
        #fight_handler.promote_to_NPC()

        # TODO: need to instrument 'error' to ckeck
        # self._window_manager.error(['%s is already an NPC' % new_NPC.name])

        #assert self.__are_equal(original_item, new_guy)

        # TODO: FightHandler.__NPC_joins_monsters
        # TODO: FightHandler.__NPC_joins_PCs



if __name__ == '__main__':
    PP = pprint.PrettyPrinter(indent=3, width=150)
    unittest.main() # runs all tests in this file

