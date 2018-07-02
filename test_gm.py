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
    def error(string_array):
        pass

    def get_fight_gm_window(self, ruleset):
        return MockFightGmWindow(ruleset)

# TODO: test to-hit with and without aiming
# TODO: posture mods testing

# TODO: test that modify index wraps
# TODO: test that cycling a whole round goes to each fighter in order
# TODO: test that an unconscious fighter is not skipped but a dead one is

# TODO: test that doing damage to one fighter and cycling a round only affects
#       the one fighter
# TODO: test that changing opponents from one that's damaged doesn't affect
#       any of the fighters (except that the opponent was changed)
# TODO: test that saving a fight and starting up again doesn't change the
#       fight (pending actions, injuries, fight order)

# TODO: test that pick opponent gives you all of the other side and none of
#       the current side
# TODO: test that pick opponent actually selects the opponent that you want
# TODO: test that a non-engaged opponent asks for a two-way and that an
#       engaged one does not

# TODO: test that looting bodies works:
#           * moving something from one body to another works properly
#           * only loot unconscious and dead monsters
# TODO: test that notes are saved properly
# TODO: test that quitting a fight offers to loot and save when appropriate
#       and not when not:
#       (4 tests: loot, save; loot, no save; no loot, save; no loot, no save)
# TODO: test that a timer works
# TODO: test that a 0.9 timer works as expected

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
        self.__colt_pistol_acc = 3
        self.__vodou_priest_fighter_pistol_skill = 15
        self.__vodou_priest_fighter = {
            "shock": 0, 
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
        self.__thief_fighter = {
            "shock": 0, 
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

                # Not needed if not saved
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

        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},

        # no aim, no posture

        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        vodou_priest.reset_aim()
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'standing'})
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc
            + 1) # braced
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'standing'})
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit

        # aim / not braced, no posture

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc)
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'standing'})
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit

        # no aim, posture
        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},

        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            -4) # crawling
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'crawling'})
        vodou_priest.reset_aim()
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit

        # aim / braced, posture
        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc # aim
            +1 # braced
            -4 # crawling
            )
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'crawling'})
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=True)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit


        # TODO: aim / not braced, posture
        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        # TODO: 1 round, 2 rounds, 3 rounds, 4 rounds

        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)

        # 1 round
        expected_to_hit = (self.__vodou_priest_fighter_pistol_skill
            + self.__colt_pistol_acc # aim
            -4 # crawling
            )
        self.__ruleset.change_posture({'fighter': vodou_priest,
                                       'posture': 'crawling'})
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit

        # 2 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 1 # aiming for 2 rounds

        # 3 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # aiming for 3 rounds

        # 4 rounds
        vodou_priest.do_aim(braced=False)
        to_hit, why = self.__ruleset.get_to_hit(vodou_priest, weapon)
        assert to_hit == expected_to_hit + 2 # no further benefit


    def test_melee_to_hit(self):
        self.__window_manager = MockWindowManager()
        self.__ruleset = gm.GurpsRuleset(self.__window_manager)

        bokor_fighter = gm.Fighter('Bokor',
                                   'group',
                                   copy.deepcopy(self.__bokor_fighter),
                                   self.__ruleset)

        # melee to-hit should be skill + special conditions

        # 'crawling':  {'attack': -4, 'defense': -3, 'target': -2},

        # no posture
        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset.change_posture({'fighter': bokor_fighter,
                                       'posture': 'standing'})
        hand_to_hand_info = self.__ruleset.get_hand_to_hand_info(bokor_fighter)

        # posture
        expected_to_hit = self.__vodou_priest_fighter_pistol_skill
        self.__ruleset.change_posture({'fighter': bokor_fighter,
                                       'posture': 'crawling'})
        hand_to_hand_info = self.__ruleset.get_hand_to_hand_info(bokor_fighter)

        # TODO: assert to_hit == expected_to_hit



if __name__ == '__main__':
    unittest.main() # runs all tests in this file

