#! /usr/bin/python

import copy
import gm
import pprint
import random
import unittest

class MockFightGmWindow(object):
    def __init__(self, ruleset):
        pass

    def start_fight(self):
        pass

class MockWindowManager(object):
    def __init__(self):
        self.__menu_responses = {} # {menu_title: [selection, selection...]

    def error(self, string_array):
        pass

    def set_menu_response(self,
                          title,
                          selection # first part of string_results tuple
                         ):
        if title not in self.__menu_responses:
            self.__menu_responses[title] = []
        self.__menu_responses[title].append(selection)

    def menu(self,
             title,
             strings_results, # array of tuples (string, return value)
             starting_index = 0 # Who is selected when the menu starts
            ):
        if title not in self.__menu_responses:
            print '** didn\'t find menu title "%s" in stored responses'
            assert False
        if len(self.__menu_responses['title']) == 0:
            print '** responses["%s"] is empty, can\'t respond'
            assert False
        selection = self.__menu_responses['title'].pop()
        for string, result in strings_results:
            if string == selection:
                return result
        print '** selection "%s" not found in menu "%s"' % (selection, title)
        assert False
        

    def get_fight_gm_window(self, ruleset):
        return MockFightGmWindow(ruleset)

# Do these first because it seems like an easy way to get the menu mock
# working.  The timer stuff requires an action via a menu so that'll be a
# little more work.

# TODO: test brass knuckles and sap in test_get_unarmed_info
# TODO: need to add opponent & opponent's posture to get_hand_to_hand_info and
#       get_to_hit tests.
# TODO: test that aiming may be disrupted (if will roll is not made) when
#       aimer is injured.
# TODO: test that pick opponent gives you all of the other side and none of
#       the current side
# TODO: test that pick opponent actually selects the opponent that you want
# TODO: test that a non-engaged opponent asks for a two-way and that an
#       engaged one does not

# TODO: test that a timer works
# TODO: test that a 0.9 timer works as expected
# TODO: test that looting bodies works:
#           * moving something from one body to another works properly
#           * only loot unconscious and dead monsters
# TODO: test that notes are saved properly
# TODO: test that quitting a fight offers to loot and save when appropriate
#       and not when not:
#       (4 tests: loot, save; loot, no save; no loot, save; no loot, no save)

# TODO: test that saving a fight and starting up again doesn't change the
#       fight (pending actions, injuries, fight order)

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

class EventTestCase(unittest.TestCase): # Derive from unittest.TestCase
    def setUp(self):
        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        self.__crawling_attack_mod = -4
        self.__crawling_defense_mod = -3

        self.__colt_pistol_acc = 3
        self.__vodou_priest_fighter_pistol_skill = 15
        self.__vodou_priest_fighter = {
            "shock": 0, 
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                       {"name": "pistol, Colt 170D",
                        "type": "ranged weapon",
                        "damage": {"dice": "1d+4"},
                        "acc": self.__colt_pistol_acc,
                        "ammo": {"name": "C Cell",
                                 "shots_left": 9,
                                 "shots": 9},
                        "reload": 3,
                        "skill": "guns (pistol)",
                        "count": 1,
                        "notes": ""
                       },
                       {"name": "C Cell",
                        "type": "misc",
                        "count": 5,
                        "notes": ""
                       }
                      ],
            "skills": {"guns (pistol)":
                                    self.__vodou_priest_fighter_pistol_skill,
                       "brawling": 12},
            "advantages": {"combat reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
            "current": {
                "fp": 12, "iq": 13, "hp": 10, "ht": 11, "st": 10, "dx": 11, 
                "basic-speed": 5.5
            }, 
            "permanent": {
                "fp": 12, "iq": 13, "hp": 10, "ht": 11, "st": 10, "dx": 11, 
                "basic-speed": 5.5
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
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                       {"name": "pistol, Colt 170D",
                        "type": "ranged weapon",
                        "damage": {"dice": "1d+4"},
                        "acc": 3,
                        "ammo": {"name": "C Cell",
                                 "shots_left": 9,
                                 "shots": 9},
                        "reload": 3,
                        "skill": "guns (pistol)",
                        "count": 1,
                        "notes": ""
                       },
                       {"name": "C Cell",
                        "type": "misc",
                        "count": 5,
                        "notes": ""
                       }
                      ],
            "skills": {"guns (pistol)": 15,
                       "brawling": 12},
            "advantages": {"combat reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
            "current": {
                "fp": 12, "iq": 13, "hp": 10, "ht": 11, "st": 10, "dx": 12, 
                "basic-speed": 5.5
            }, 
            "permanent": {
                "fp": 12, "iq": 13, "hp": 10, "ht": 11, "st": 10, "dx": 12, 
                "basic-speed": 5.5
            }, 
            "timers": [], 
            "check_for_death": False, 
            "opponent": None
        } 
        self.__bokor_fighter = {
            "shock": 0, 
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                       {"name": "pistol, Kalashnikov Makarov",
                        "type": "ranged weapon",
                        "damage": {"dice": "1d+3"},
                        "acc": 2,
                        "ammo": {"name": "C Cell",
                                 "shots_left": 8,
                                 "shots": 8},
                        "reload": 3,
                        "skill": "guns (pistol)",
                        "count": 1,
                        "notes": ""
                       },
                       {"name": "C Cell",
                        "type": "misc",
                        "count": 5,
                        "notes": ""
                       }
                      ],
            "skills": {"guns (pistol)": 13,
                       "brawling": 12},
            "advantages": {"combat reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
            "current": {
                "fp": 11, "iq": 12, "hp": 10, "ht": 11, "st": 10, "dx": 10, 
                "basic-speed": 5.25
            }, 
            "permanent": {
                "fp": 11, "iq": 12, "hp": 10, "ht": 11, "st": 10, "dx": 10, 
                "basic-speed": 5.25
            }, 
            "timers": [], 
            "check_for_death": False, 
            "opponent": None
        } 
        self.__tank_fighter = {
            "shock": 0, 
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                       {"name": "pistol, Sig D65",
                        "type": "ranged weapon",
                        "damage": {"dice": "1d+4"},
                        "acc": 4,
                        "ammo": {"name": "C Cell",
                                 "shots_left": 9,
                                 "shots": 9},
                        "reload": 3,
                        "skill": "guns (pistol)",
                        "count": 1,
                        "notes": ""
                       },
                       {"name": "sick stick",
                        "type": "melee weapon",
                        "damage": {"dice": "1d+1 fat"},
                        "skill": "axe/mace",
                        "count": 1,
                        "notes": ""
                       },
                       {"name": "C Cell",
                        "type": "misc",
                        "count": 5,
                        "notes": ""
                       }
                      ],
            "skills": {"guns (pistol)": 16,
                       "brawling": 16,
                       "axe/mace": 14},
            "advantages": {"combat reflexes": 15},
            "state" : "alive",
            "posture" : "standing",
            "current": {
                "st": 10, "dx": 12, "iq": 12, "ht": 11, "fp": 11, "hp": 11, 
                "basic-speed": 5.75
            }, 
            "permanent": {
                "fp": 11, "iq": 12, "hp": 11, "ht": 11, "st": 10, "dx": 12, 
                "basic-speed": 5.75
            }, 
            "timers": [], 
            "check_for_death": False, 
            "opponent": None
        } 

        self.__thief_knife_skill = 14

        self.__thief_fighter = {
            "shock": 0, 
            "did_action_this_turn": False,
            "aim": {"rounds": 0, "braced": False},
            "weapon-index" : None,
            "stuff": [
                       {"name": "pistol, Baretta DX 192",
                        "type": "ranged weapon",
                        "damage": {"dice": "1d+4"},
                        "acc": 2,
                        "ammo": {"name": "C Cell",
                                 "shots_left": 8,
                                 "shots": 8},
                        "reload": 3,
                        "skill": "guns (pistol)",
                        "count": 1,
                        "notes": ""
                       },
                       {"name": "knife, large",
                        "type": "melee weapon",
                        "damage": {"dice": "1d-2",
                                   "type": "imp"},
                        "skill": "knife",
                        "parry": -1,
                        "count": 1,
                        "notes": ""
                       },
                       {"name": "C Cell",
                        "type": "misc",
                        "count": 5,
                        "notes": ""
                       }
                      ],
            "skills": {"guns (pistol)": 12,
                       "brawling": 14,
                       "knife": self.__thief_knife_skill},
            "advantages": {},
            "state" : "alive",
            "posture" : "standing",
            "current": {
                "fp": 11, "iq": 12, "hp": 12, "ht": 11, "st": 10, "dx": 12, 
                "basic-speed": 5.75
            }, 
            "permanent": {
                "fp": 11, "iq": 12, "hp": 12, "ht": 11, "st": 10, "dx": 12, 
                "basic-speed": 5.75
            }, 
            "timers": [], 
            "check_for_death": False, 
            "opponent": None
        }
        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)
    
    def tearDown(self):
        pass

    def test_get_dodge_skill(self):
        # Deepcopy so that we don't taint the original
        vodou_priest = gm.Fighter('Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset)

        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'standing'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == 9

        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'crawling'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == (9 + self.__crawling_defense_mod)

        # Next guy

        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)

        self.__ruleset.change_posture({'fighter': bokor_fighter,
                                       'posture': 'standing'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == 9

        self.__ruleset.change_posture({'fighter': bokor_fighter,
                                       'posture': 'crawling'})
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == (9 + self.__crawling_defense_mod)

        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(tank_fighter)
        assert dodge_skill == 9

        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(thief_fighter)
        assert dodge_skill == 8

    def test_get_block_skill(self):
        # TODO: need non-trivial block tests
        vodou_priest_fighter = gm.Fighter(
                                  'Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset)
        block_skill, block_why = self.__ruleset.get_block_skill(
                                                        vodou_priest_fighter,
                                                        None)
        assert block_skill == None

        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)
        block_skill, block_why = self.__ruleset.get_block_skill(bokor_fighter,
                                                                None)
        assert block_skill == None

        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        block_skill, block_why = self.__ruleset.get_block_skill(tank_fighter,
                                                                None)
        assert block_skill == None

        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
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
                                    self.__ruleset)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(
                                                    vodou_priest_fighter,
                                                    weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(bokor_fighter,
                                                                weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Armed (sick stick)
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        weapon_index, weapon  = tank_fighter.get_weapon_by_name('sick stick')
        tank_fighter.draw_weapon_by_index(weapon_index)

        self.__ruleset.change_posture({'fighter': tank_fighter,
                                       'posture': 'standing'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == 11

        self.__ruleset.change_posture({'fighter': tank_fighter,
                                       'posture': 'crawling'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == (11 + self.__crawling_defense_mod)

        # Unarmed
        weapon = None
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill is None # None w/weapon; still OK hand-to-hand

        # Armed (knife)
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
        weapon_index, weapon = thief_fighter.get_weapon_by_name('knife, large')
        thief_fighter.draw_weapon_by_index(weapon_index)

        self.__ruleset.change_posture({'fighter': thief_fighter,
                                       'posture': 'standing'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == 9

        self.__ruleset.change_posture({'fighter': thief_fighter,
                                       'posture': 'crawling'})
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == (9 + self.__crawling_defense_mod)

    def test_get_unarmed_info(self):
        # Vodou Priest
        #PP = pprint.PrettyPrinter(indent=3, width=150)  # TODO: remove
        unarmed_skills = self.__ruleset.get_weapons_unarmed_skills(None)
        vodou_priest_fighter = gm.Fighter(
                                    'Vodou Priest',
                                    'group',
                                    copy.deepcopy(self.__vodou_priest_fighter),
                                    self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(
                                                vodou_priest_fighter,
                                                None,
                                                None,
                                                unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage'] == '1d-3'
        assert hand_to_hand_info['kick_skill'] == 10
        assert hand_to_hand_info['kick_damage'] == '1d-2'
        assert hand_to_hand_info['parry_skill'] == 10

        # Bokor
        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(bokor_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        # PP.pprint(hand_to_hand_info)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage'] == '1d-2'
        assert hand_to_hand_info['kick_skill'] == 10   # thr-1, st=10
        assert hand_to_hand_info['kick_damage'] == '1d-1'
        assert hand_to_hand_info['parry_skill'] == 10

        # Tank
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(tank_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1'
        assert hand_to_hand_info['parry_skill'] == 12

        # Thief
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == '1d-2'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1'
        assert hand_to_hand_info['parry_skill'] == 10

        # Thief with posture additions

        self.__ruleset.change_posture({'fighter': thief_fighter,
                                       'posture': 'crawling'})
        hand_to_hand_info = self.__ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None,
                                                            unarmed_skills)
        assert hand_to_hand_info['punch_skill'] == (14
                                                + self.__crawling_attack_mod)
        assert hand_to_hand_info['punch_damage'] == '1d-2'
        assert hand_to_hand_info['kick_skill'] == (12
                                                + self.__crawling_attack_mod)
        assert hand_to_hand_info['kick_damage'] == '1d-1'
        assert hand_to_hand_info['parry_skill'] == (10
                                                + self.__crawling_defense_mod)


    def test_initiative_order(self):
        random_debug_filename = 'foo'

        world = {
            # Don't need templates, dead-monsters, equipment, names
            'PCs': {
                # 5.25, 10, rand=1
                'Manny' : copy.deepcopy(self.__bokor_fighter),

                # 5.75, 12, rand=2
                'Jack' : copy.deepcopy(self.__tank_fighter),

                # 5.5, 12, rand=4
                'Moe' : copy.deepcopy(self.__one_more_guy),
            },
            'monsters': {
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
        }

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
                                            filename='*INTERNAL*',
                                            maintain_json=False
                                           )
            fighters = fight_handler.get_fighters()

            # Check the order against the one that I expect

            for index, ignore in enumerate(fighters):
                assert fighters[index]['name'] == expected[index]['name']
                assert fighters[index]['group'] == expected[index]['group']

        # test that modify index wraps
        # test that cycling a whole round goes to each fighter in order

        expected_index = 0
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 1
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        injured_fighter = current_fighter
        injured_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 2
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        unconscious_fighter = current_fighter
        unconscious_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 3
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        dead_fighter = current_fighter
        dead_index = expected_index
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 4
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 0 # wraps
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # test that an unconscious fighter is not skipped but a dead one is

        injured_hp = 3 # arbitrary amount
        injured_fighter.details['current']['hp'] -= injured_hp
        unconscious_fighter.bump_consciousness()
        dead_fighter.bump_consciousness()   # once to unconscious
        dead_fighter.bump_consciousness()   # twice to dead

        assert injured_fighter.get_state() == gm.Fighter.INJURED
        assert unconscious_fighter.get_state() == gm.Fighter.UNCONSCIOUS
        assert dead_fighter.get_state() == gm.Fighter.DEAD

        expected_index = 0
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # This is the injured fighter -- should still see this one
        fight_handler.modify_index(1)
        expected_index = 1
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # This is the unconscious fighter -- should still see this one
        fight_handler.modify_index(1)
        expected_index = 2
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        # Should skip the dead fighter

        fight_handler.modify_index(1)
        expected_index = 4
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        assert current_fighter.name == expected[expected_index]['name']
        assert current_fighter.group == expected[expected_index]['group']

        fight_handler.modify_index(1)
        expected_index = 0 # wraps
        assert world['current-fight']['index'] == expected_index
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
        assert expected_fighters[0] == fighters[0]['details']
        assert expected_fighters[1] == fighters[1]['details']
        assert expected_fighters[2] == fighters[2]['details']
        assert expected_fighters[3] == fighters[3]['details']
        assert expected_fighters[4] == fighters[4]['details']

    def test_initiative_order_again(self):
        '''
        This is just like test_initiative_order_again except the fighters are
        reordered randomly and a different random seed is used.
        '''

        random_debug_filename = 'foo'

        world = {
            # Don't need templates, dead-monsters, equipment, names
            'PCs': {
                # 5.5, 11, rand=2
                'Bob' : copy.deepcopy(self.__vodou_priest_fighter),

                # 5.75, 12, rand=3
                'Ted' : copy.deepcopy(self.__tank_fighter),
            },
            'monsters': {
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
        }

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
                                            filename='*INTERNAL*',
                                            maintain_json=False
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
        world = {
            # Don't need templates, dead-monsters, equipment, names
            'PCs': {
                # 5.25, 10, rand=1
                'Manny' : copy.deepcopy(self.__bokor_fighter),

                # 5.75, 12, rand=2
                'Jack' : copy.deepcopy(self.__tank_fighter),

                # 5.5, 12, rand=4
                'Moe' : copy.deepcopy(self.__one_more_guy),
            },
            'monsters': {
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
        }

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
                                        filename='*INTERNAL*',
                                        maintain_json=False
                                       )
        fighters = fight_handler.get_fighters()

        expected_index = 0
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Make fighter 0 fight figher 2
        current_fighter.details['opponent'] = {'group': 'PCs', 'name': 'Moe'}

        # Move ahead to fighter 1
        fight_handler.modify_index(1)
        expected_index = 1
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Wound fighter 2
        fighters[injured_index]['details']['current']['hp'] -= injured_hp

        # Cycle around to fighter 0

        fight_handler.modify_index(1)
        expected_index = 2
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        unconscious_fighter = current_fighter
        unconscious_index = expected_index

        fight_handler.modify_index(1)
        expected_index = 3
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        dead_fighter = current_fighter
        dead_index = expected_index

        fight_handler.modify_index(1)
        expected_index = 4
        assert world['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()

        fight_handler.modify_index(1)
        expected_index = 0 # wraps
        assert world['current-fight']['index'] == expected_index
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
        assert world['current-fight']['index'] == expected_index

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
        assert expected_fighters[0] == fighters[0]['details']

        self.__are_equal(expected_fighters[1], fighters[1]['details'])

        assert expected_fighters[1] == fighters[1]['details']

        assert expected_fighters[2] == fighters[2]['details']
        assert expected_fighters[3] == fighters[3]['details']
        assert expected_fighters[4] == fighters[4]['details']


    def test_ranged_to_hit(self):
        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)

        vodou_priest = gm.Fighter('Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset)
        requested_weapon_index = 0
        vodou_priest.draw_weapon_by_index(requested_weapon_index)
        weapon, actual_weapon_index = vodou_priest.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # ranged to-hit should be skill + acc (if aimed) + 1 (if braced)
        #   + size modifier + range/speed modifier + special conditions

        # aim for 1 turn += acc, 2 turns += 1, 3+ turns += 1
        # brace += 1

        # no aim, no posture

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        vodou_priest.reset_aim()
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'standing'})
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit

        # aim / not braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc)
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'standing'})
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit

        # no aim, posture

        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                                                + self.__crawling_attack_mod)
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'crawling'})
        vodou_priest.reset_aim()
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
                                                + self.__colt_pistol_acc # aim
                                                +1 # braced
                                                + self.__crawling_attack_mod)
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'crawling'})
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit


        # aim / not braced, posture

        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc # aim
            + self.__crawling_attack_mod)
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'crawling'})
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, None, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit


    def test_melee_to_hit(self):
        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)

        thief = gm.Fighter('Thief',
                           'group',
                           copy.deepcopy(self.__thief_fighter),
                           self.__ruleset)
        requested_weapon_index = 1 # Knife
        thief.draw_weapon_by_index(requested_weapon_index)
        weapon, actual_weapon_index = thief.get_current_weapon()
        assert actual_weapon_index == requested_weapon_index

        # melee to-hit should be skill + special conditions

        # no posture
        expected_to_hit = self.__thief_knife_skill
        self.__ruleset.change_posture({'fighter': thief,
                                       'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

        # posture
        expected_to_hit = (self.__thief_knife_skill
                                                + self.__crawling_attack_mod)
        self.__ruleset.change_posture({'fighter': thief,
                                       'posture': 'crawling'})
        to_hit, why = self.__ruleset.get_to_hit(thief, None, weapon)
        assert to_hit == expected_to_hit

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

    def __are_equal(self, lhs, rhs):
        PP = pprint.PrettyPrinter(indent=3, width=150)
        if isinstance(lhs, dict):
            if not isinstance(rhs, dict):
                print '** lhs is a dict but rhs is not'
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                return False
            for key in rhs.iterkeys():
                if key not in rhs:
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



if __name__ == '__main__':
    unittest.main() # runs all tests in this file

