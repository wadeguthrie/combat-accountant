#! /usr/bin/python

import copy
import gm
import pprint
import unittest

class MockWindowManager(object):
    def error(string_array):
        pass

# TODO: test to-hit with and without aiming
# TODO: posture mods testing
# TODO: test initiative order (note: random.seed(9001))

class EventTestCase(unittest.TestCase): # Derive from unittest.TestCase
    def setUp(self):
        self.__vodou_priest_fighter = {
            "shock": 0, 
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
        self.__bokor_fighter = {
            "shock": 0, 
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
        self.__thief_fighter = {
            "shock": 0, 
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
                       "knife": 15},
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

    #def test_adjust_hp(self,
    #              fighter_details,
    #              adj # the number of HP to gain or lose
    #             ):
    #def test_do_maneuver(self):
    #def test_get_action_menu(self,
    #                    fighter_name,
    #                    fighter # dict describing the fighter in question
    #                   ):
    #def test_get_fighter_notes(self,
    #                      fighter_name,
    #                      fighter_details
    #                     ):
    #def test_get_fighter_state(self, fighter_details):
    #def test_heal_fighter(self, fighter_details):
    #def test_initiative(self,
    #               fighter_details # dict for the creature as in the json file
    #              ):
    #def test_make_dead(self):
    #def test_new_fight(self, fighter_details):
    #def test_next_fighter(self, prev_fighter_details):

    def test_get_dodge_skill(self):
        # Deepcopy so that we don't taint the original
        vodou_priest_fighter = gm.Fighter(
                                  'Priest',
                                  'group',
                                  copy.deepcopy(self.__vodou_priest_fighter),
                                  self.__ruleset)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(
                                                        vodou_priest_fighter)
        assert dodge_skill == 9

        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)
        dodge_skill, dodge_why = self.__ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == 9

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
        assert parry_skill is None

        # Unarmed
        weapon = None
        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(bokor_fighter,
                                                                weapon)
        assert parry_skill is None

        # Unarmed
        weapon = None
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill is None

        # Armed (sick stick)
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        weapon_index, weapon  = tank_fighter.get_weapon_by_name('sick stick')
        tank_fighter.draw_weapon_by_index(weapon_index)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == 11

        # Unarmed
        weapon = None
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill is None

        # Armed (knife)
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
        weapon_index, weapon = thief_fighter.get_weapon_by_name('knife, large')
        thief_fighter.draw_weapon_by_index(weapon_index)
        parry_skill, parry_why = self.__ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == 9

    def test_get_hand_to_hand_info(self):
        # Vodou Priest
        #PP = pprint.PrettyPrinter(indent=3, width=150)  # TODO: remove
        vodou_priest_fighter = gm.Fighter(
                                    'Vodou Priest',
                                    'group',
                                    copy.deepcopy(self.__vodou_priest_fighter),
                                    self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_hand_to_hand_info(
                                                vodou_priest_fighter)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage']['num_dice'] == 1
        assert hand_to_hand_info['punch_damage']['plus'] == -3
        assert hand_to_hand_info['kick_skill'] == 10
        assert hand_to_hand_info['kick_damage']['num_dice'] == 1
        assert hand_to_hand_info['kick_damage']['plus'] == -2
        assert hand_to_hand_info['parry_skill'] == 10

        # Bokor
        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_hand_to_hand_info(bokor_fighter)
        # PP.pprint(hand_to_hand_info)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage']['num_dice'] == 1
        assert hand_to_hand_info['punch_damage']['plus'] == -2
        assert hand_to_hand_info['kick_skill'] == 10   # thr-1, st=10
        assert hand_to_hand_info['kick_damage']['num_dice'] == 1
        assert hand_to_hand_info['kick_damage']['plus'] == -1
        assert hand_to_hand_info['parry_skill'] == 10

        # Tank
        tank_fighter = gm.Fighter('Tank',
                                  'group',
                                  copy.deepcopy(self.__tank_fighter),
                                  self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_hand_to_hand_info(tank_fighter)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage']['num_dice'] == 1
        assert hand_to_hand_info['punch_damage']['plus'] == -2
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage']['num_dice'] == 1
        assert hand_to_hand_info['kick_damage']['plus'] == -1
        assert hand_to_hand_info['parry_skill'] == 12

        # Thief
        thief_fighter = gm.Fighter('Thief',
                                   'group',
                                   copy.deepcopy(self.__thief_fighter),
                                   self.__ruleset)
        hand_to_hand_info = self.__ruleset.get_hand_to_hand_info(thief_fighter)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage']['num_dice'] == 1
        assert hand_to_hand_info['punch_damage']['plus'] == -2
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage']['num_dice'] == 1
        assert hand_to_hand_info['kick_damage']['plus'] == -1
        assert hand_to_hand_info['parry_skill'] == 10

if __name__ == '__main__':
    unittest.main() # runs all tests in this file

