#! /usr/bin/python

import copy
import random
import unittest

import ca
import ca_debug
import ca_fighter
import ca_gurps_ruleset

from .test_common import GmTestCaseCommon
from .test_common import MockFightHandler
from .test_common import MockProgram
from .test_common import MockWindowManager
from .test_common import TestRuleset
from .test_common import WorldData

class GmTestCaseGurps(GmTestCaseCommon):
    '''
    These tests address the GURPS ruleset.
    '''
    def test_get_dodge_skill(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_get_dodge_skill ===\n')

        # Deepcopy so that we don't taint the original
        mock_fight_handler = MockFightHandler()
        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self._ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == 9

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self._ruleset.get_dodge_skill(vodou_priest)
        assert dodge_skill == (9 + self._crawling_defense_mod)

        # Next guy

        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self._bokor_fighter),
                self._ruleset,
                self._window_manager)

        self._ruleset.do_action(bokor_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self._ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == 9

        self._ruleset.do_action(bokor_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        dodge_skill, dodge_why = self._ruleset.get_dodge_skill(bokor_fighter)
        assert dodge_skill == (9 + self._crawling_defense_mod)

        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)
        dodge_skill, dodge_why = self._ruleset.get_dodge_skill(tank_fighter)
        assert dodge_skill == 9

        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self._thief_fighter),
                self._ruleset,
                self._window_manager)
        dodge_skill, dodge_why = self._ruleset.get_dodge_skill(thief_fighter)
        assert dodge_skill == 8

    def test_get_block_skill(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_get_block_skill ===\n')

        # TODO: need non-trivial block tests
        vodou_priest_fighter = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        block_skill, block_why = self._ruleset.get_block_skill(
                vodou_priest_fighter, None)
        assert block_skill is None

        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self._bokor_fighter),
                self._ruleset,
                self._window_manager)
        block_skill, block_why = self._ruleset.get_block_skill(bokor_fighter,
                                                                None)
        assert block_skill is None

        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)
        block_skill, block_why = self._ruleset.get_block_skill(tank_fighter,
                                                                None)
        assert block_skill is None

        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self._thief_fighter),
                self._ruleset,
                self._window_manager)
        block_skill, block_why = self._ruleset.get_block_skill(thief_fighter,
                                                                None)
        assert block_skill is None

    def test_get_parry_skill(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_get_parry_skill ===\n')

        # Unarmed
        weapon = None
        mock_fight_handler = MockFightHandler()
        vodou_priest_fighter = ca_fighter.Fighter(
                'Vodou Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        parry_skill, parry_why = self._ruleset.get_parry_skill(
                vodou_priest_fighter, weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self._bokor_fighter),
                self._ruleset,
                self._window_manager)
        parry_skill, parry_why = self._ruleset.get_parry_skill(bokor_fighter,
                                                                weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Unarmed
        weapon = None
        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)
        parry_skill, parry_why = self._ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Armed (sick stick)
        tank_fighter = ca_fighter.Fighter(
                                'Tank',
                                'group',
                                copy.deepcopy(self._tank_fighter),
                                self._ruleset,
                                self._window_manager)
        weapon_index, weapon = tank_fighter.draw_weapon_by_name('sick stick')
        #self._ruleset.do_action(tank_fighter,
        #                         {'action-name': 'draw-weapon',
        #                          'weapon-index': weapon_index},
        #                         mock_fight_handler)

        self._ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        parry_skill, parry_why = self._ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == 11

        self._ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        parry_skill, parry_why = self._ruleset.get_parry_skill(tank_fighter,
                                                                weapon)
        assert parry_skill == (11 + self._crawling_defense_mod)

        # Unarmed
        weapon = None
        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self._thief_fighter),
                self._ruleset,
                self._window_manager)
        parry_skill, parry_why = self._ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill is None  # None w/weapon; still OK hand-to-hand

        # Armed (Knife)
        thief_fighter = ca_fighter.Fighter(
                                'Thief',
                                'group',
                                copy.deepcopy(self._thief_fighter),
                                self._ruleset,
                                self._window_manager)
        weapon_index, weapon = thief_fighter.draw_weapon_by_name('Large Knife')
        #self._ruleset.do_action(tank_fighter,
        #                         {'action-name': 'draw-weapon',
        #                          'weapon-index': weapon_index},
        #                         mock_fight_handler)
        self._ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        parry_skill, parry_why = self._ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == 9

        self._ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        parry_skill, parry_why = self._ruleset.get_parry_skill(thief_fighter,
                                                                weapon)
        assert parry_skill == (9 + self._crawling_defense_mod)

    def test_get_unarmed_info(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_get_unarmed_info ===\n')

        # Vodou Priest
        mock_fight_handler = MockFightHandler()
        vodou_priest_fighter = ca_fighter.Fighter(
                'Vodou Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        hand_to_hand_info = self._ruleset.get_unarmed_info(
                vodou_priest_fighter,
                None,
                None)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage'] == '1d-3 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 10
        assert hand_to_hand_info['kick_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # Bokor
        bokor_fighter = ca_fighter.Fighter(
                'Bokor',
                'group',
                copy.deepcopy(self._bokor_fighter),
                self._ruleset,
                self._window_manager)
        hand_to_hand_info = self._ruleset.get_unarmed_info(bokor_fighter,
                                                            None,
                                                            None)
        # debug.pprint(hand_to_hand_info)
        assert hand_to_hand_info['punch_skill'] == 12
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 10   # thr-1, st=10
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # Tank
        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)
        hand_to_hand_info = self._ruleset.get_unarmed_info(tank_fighter,
                                                            None,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

        # Thief
        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self._thief_fighter),
                self._ruleset,
                self._window_manager)
        hand_to_hand_info = self._ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # Thief with posture additions

        self._ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        hand_to_hand_info = self._ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == (
                14 + self._crawling_attack_mod)
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == (
                12 + self._crawling_attack_mod)
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == (
                10 + self._crawling_defense_mod)

        # Thief w/o brass knuckles
        thief_fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self._thief_fighter),
                self._ruleset,
                self._window_manager)
        hand_to_hand_info = self._ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # w/brass knuckles -- Note: that the punch damage is +1

        ignore, weapon = thief_fighter.draw_weapon_by_name('brass knuckles')
        if self._ruleset.does_weapon_use_unarmed_skills(weapon):
            hand_to_hand_info = self._ruleset.get_unarmed_info(thief_fighter,
                                                                None,
                                                                weapon)

        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == 'thr: 1d-1 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # back to unarmed
        hand_to_hand_info = self._ruleset.get_unarmed_info(thief_fighter,
                                                            None,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == 14
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 12
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 10

        # --- Opponents w/ posture ---

        self._ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # Picking opponent doesn't change things
        hand_to_hand_info = self._ruleset.get_unarmed_info(tank_fighter,
                                                            thief_fighter,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

        # change posture of thief (opponent) -- note: posture of opponent does
        # not modify melee attacks

        self._ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},  # -2
                                 mock_fight_handler)
        hand_to_hand_info = self._ruleset.get_unarmed_info(tank_fighter,
                                                            thief_fighter,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

        # change posture of thief (back to standing)
        self._ruleset.do_action(thief_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        hand_to_hand_info = self._ruleset.get_unarmed_info(tank_fighter,
                                                            thief_fighter,
                                                            None)
        assert hand_to_hand_info['punch_skill'] == 16
        assert hand_to_hand_info['punch_damage'] == '1d-2 (cr=x1.0)'
        assert hand_to_hand_info['kick_skill'] == 14
        assert hand_to_hand_info['kick_damage'] == '1d-1 (cr=x1.0)'
        assert hand_to_hand_info['parry_skill'] == 12

    def test_ranged_to_hit(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_ranged_to_hit ===\n')

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        requested_weapon_index = self._vodou_pistol_index
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == requested_weapon_index

        # ranged to-hit should be skill + acc (if aimed) + 1 (if braced)
        #   + size modifier + range/speed modifier + special conditions

        # aim for 1 turn += acc, 2 turns += 1, 3+ turns += 1
        # brace += 1

        # no aim, no posture

        expected_to_hit = self._vodou_priest_fighter_pistol_skill
        self._ruleset.reset_aim(vodou_priest)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        mode = "ranged weapon"
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # aim / braced, no posture

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # aim / not braced, no posture

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # no aim, posture (posture doesn't matter for ranged attacks: B551)

        expected_to_hit = self._vodou_priest_fighter_pistol_skill
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        self._ruleset.reset_aim(vodou_priest)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # aim / braced, posture (posture not counted for ranged attacks: B551)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc  # aim
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # aim / not braced, posture (no posture minus for ranged attacks: B551)

        self._ruleset.reset_aim(vodou_priest)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc)  # aim
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # aiming for 3 rounds

        # 4 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 2  # no further benefit

        # --- Opponents w/ posture ---

        expected_to_hit = self._vodou_priest_fighter_pistol_skill
        self._ruleset.reset_aim(vodou_priest)
        tank = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # Picking opponent doesn't change things
        self._ruleset.do_action(tank,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, tank, weapon, mode, None)
        assert to_hit == expected_to_hit

        # change posture of thief (-2)
        self._ruleset.do_action(tank,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},  # -2
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, tank, weapon, mode, None)
        assert to_hit == (expected_to_hit - 2)

        # change posture of thief (back to standing)
        self._ruleset.do_action(tank,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, tank, weapon, mode, None)
        assert to_hit == expected_to_hit

    def test_messed_up_aim(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_messed_up_aim ===\n')

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        requested_weapon_index = self._vodou_pistol_index
        mode = "ranged weapon"
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == requested_weapon_index

        # Regular, no aim - for a baseline

        expected_to_hit = self._vodou_priest_fighter_pistol_skill
        self._ruleset.reset_aim(vodou_priest)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # Damage _would_ ruin aim except for successful Will roll

        self._ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # adjust_hp but MADE Will roll
        # action['action-name'] == 'adjust-hp':
        damage = -1
        self._window_manager.set_menu_response(
                'roll <= WILL (13) or lose aim', True)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)

        # aiming for 3 rounds (1st round+brace already in expected_to_hit)
        #   + shock
        assert to_hit == expected_to_hit + 2 + damage

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        # Damage ruins aim -- miss will roll

        self._ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # adjust_hp and MISSES Will roll
        self._window_manager.set_menu_response(
                'roll <= WILL (13) or lose aim', False)
        damage = -1
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds (well, 1 round)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + damage  # aiming for 1 round + shock

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        # Draw weapon ruins aim

        self._ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Move to spoil the aim
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'move'},
                                 mock_fight_handler)

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)

        assert to_hit == expected_to_hit  # aiming for 1 round

        # Posture ruins aim

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.reset_aim(vodou_priest)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Change posture
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'lying'},
                                 mock_fight_handler)

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit  # aiming for 1 round

        # Defense ruins aim

        self._ruleset.reset_aim(vodou_priest)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Defend
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'defend'},
                                 mock_fight_handler)

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit  # aiming for 3 rounds

        # Last One is Regular - shows nothing carries over

        expected_to_hit = self._vodou_priest_fighter_pistol_skill
        self._ruleset.reset_aim(vodou_priest)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

    def test_melee_to_hit(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_melee_to_hit ===\n')

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)
        mock_fight_handler = MockFightHandler()

        thief = ca_fighter.Fighter(
                'Thief',
                'group',
                copy.deepcopy(self._thief_fighter),
                self._ruleset,
                self._window_manager)
        requested_weapon_index = 1  # Knife
        mode = "swung weapon"
        self._ruleset.do_action(thief,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(thief)
        assert actual_weapon_index == requested_weapon_index

        # melee to-hit should be skill + special conditions

        # no posture
        expected_to_hit = self._thief_knife_skill
        self._ruleset.do_action(thief,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(thief, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # posture
        expected_to_hit = (self._thief_knife_skill
                           + self._crawling_attack_mod)
        self._ruleset.do_action(thief,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(thief, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # --- Opponents w/ posture (shouldn't change melee attack) ---

        tank_fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)

        self._ruleset.do_action(thief,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        # Picking opponent doesn't change things
        expected_to_hit = self._thief_knife_skill
        self._ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(thief, tank_fighter, weapon, mode, None)
        assert to_hit == expected_to_hit

        # change posture of tank (opponent)
        self._ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'crawling'},  # -2
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(thief, tank_fighter, weapon, mode, None)
        assert to_hit == expected_to_hit

        # change posture of thief (back to standing)
        self._ruleset.do_action(tank_fighter,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(thief, tank_fighter, weapon, mode, None)
        assert to_hit == expected_to_hit

        # --- Aiming does not help ---

        self._ruleset.reset_aim(thief)
        expected_to_hit = self._thief_knife_skill
        to_hit, why = self._ruleset.get_to_hit(thief, None, weapon, mode, None)

        # 1 round
        self._ruleset.do_action(thief,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(thief, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(thief,
                                 {'action-name': 'aim', 'braced': False},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(thief, None, weapon, mode, None)
        assert to_hit == expected_to_hit

    def test_adjust_hp(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_adjust_hp ===\n')

        # Setup

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)

        requested_weapon_index = self._vodou_pistol_index
        mode = "ranged weapon"
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"

        requested_armor_index = 2
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'don-armor',
                                  'armor-index': requested_armor_index},
                                 mock_fight_handler)


        armor_index_list = vodou_priest.get_current_armor_indexes()
        armor_list = vodou_priest.get_items_from_indexes(armor_index_list)

        assert len(armor_index_list) == 1
        assert armor_index_list[0] == requested_armor_index
        assert armor_list[0]['name'] == "Sport coat/Jeans"

        original_to_hit, ignore = self._ruleset.get_to_hit(vodou_priest,
                                                            None,
                                                            weapon, mode, None)

        original_hand_to_hand_info = self._ruleset.get_unarmed_info(
                vodou_priest,
                None,
                None)

        original_dodge_skill, ignore = self._ruleset.get_dodge_skill(
                vodou_priest)

        # Test that the HP are reduced withOUT DR adjustment

        damage_1st = -3
        self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        original_hp = vodou_priest.details['current']['hp']

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage_1st},
                                 mock_fight_handler)

        modified_hp = vodou_priest.details['current']['hp']
        assert modified_hp == original_hp + damage_1st

        # Shock (B419)

        to_hit, ignore = self._ruleset.get_to_hit(vodou_priest,
                                                   None,
                                                   weapon, mode, None)
        assert to_hit == original_to_hit + damage_1st  # damage is less than 4

        hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None)
        assert (hand_to_hand_info['punch_skill'] ==
                original_hand_to_hand_info['punch_skill'] + damage_1st)
        assert (hand_to_hand_info['kick_skill'] ==
                original_hand_to_hand_info['kick_skill'] + damage_1st)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        # Test that the HP are NOT reduced WITH DR adjustment

        damage_2nd = -1
        self._window_manager.set_menu_response('Use Armor\'s DR?', True)
        original_hp = vodou_priest.details['current']['hp']

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage_2nd},
                                 mock_fight_handler)

        modified_hp = vodou_priest.details['current']['hp']
        assert modified_hp == original_hp  # No damage because of DR

        # Shock (B419) is only from the 1st attack since this did no damage
        # -hp to DX/IQ (not defense) on your next turn

        to_hit, ignore = self._ruleset.get_to_hit(vodou_priest,
                                                   None,
                                                   weapon, mode, None)
        assert to_hit == original_to_hit + damage_1st  # damage is less than 4

        hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None)
        assert (hand_to_hand_info['punch_skill'] ==
                original_hand_to_hand_info['punch_skill'] + damage_1st)
        assert (hand_to_hand_info['kick_skill'] ==
                original_hand_to_hand_info['kick_skill'] + damage_1st)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        # Test that the HP ARE reduced WITH DR adjustment

        expected_damage = -2
        pre_armor_damage = expected_damage - self._vodou_priest_armor_dr
        self._window_manager.set_menu_response('Use Armor\'s DR?', True)
        original_hp = vodou_priest.details['current']['hp']

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': pre_armor_damage},
                                 mock_fight_handler)

        modified_hp = vodou_priest.details['current']['hp']
        assert modified_hp == original_hp + expected_damage

        # Shock is capped at -4

        max_shock = -4

        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)

        assert to_hit == original_to_hit + max_shock

        hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None)
        assert (hand_to_hand_info['punch_skill'] ==
                original_hand_to_hand_info['punch_skill'] + max_shock)
        assert (hand_to_hand_info['kick_skill'] ==
                original_hand_to_hand_info['kick_skill'] + max_shock)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        #
        # Let's heal the guy
        #

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)

        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])

        # Major wound (B420) - Make HT roll (no knockdown or stun)

        # +1 to make sure that the damage is more than half
        major_damage = - ((vodou_priest.details['permanent']['hp'] / 2) + 1)

        self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        # TODO: clear the 'pass-out-immediately' flag for this.  make a
        #   separate test for 'pass-out-immediately'.  Remember to put the
        #   original value back into that flag.
        self._window_manager.set_menu_response(
                ('Major Wound (B420): Roll vs HT (%d) or be Stunned and Knocked Down' %
                 self._vodou_priest_ht),
                ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SUCCESS)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None)
        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'])  # no shock

        dodge_skill, ignore = self._ruleset.get_dodge_skill(vodou_priest)

        assert dodge_skill == original_dodge_skill  # shock
        assert vodou_priest.details['posture'] == 'standing'

        # Major wound (B420) - miss HT roll (knockdown and stunned)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])

        self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        self._window_manager.set_menu_response(
                ('Major Wound (B420): Roll vs HT (%d) or be Stunned and Knocked Down' %
                 self._vodou_priest_ht),
                ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None)
        stun_penalty = -4
        posture_penalty = -3
        total_penalty = stun_penalty + posture_penalty

        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'] + total_penalty)

        dodge_skill, ignore = self._ruleset.get_dodge_skill(vodou_priest)

        assert dodge_skill == original_dodge_skill + total_penalty
        assert vodou_priest.details['posture'] == 'lying'

        # End of the turn -- check for stun (B420) to be over

        self._window_manager.set_menu_response(
                'Priest Stunned (B420): Roll <= HT to recover',
                True)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None)

        # Stun should be over -- now there's only the posture penalty

        posture_penalty = -3
        total_penalty = posture_penalty

        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'] + total_penalty)

        dodge_skill, ignore = self._ruleset.get_dodge_skill(vodou_priest)

        assert dodge_skill == original_dodge_skill + total_penalty
        assert vodou_priest.details['posture'] == 'lying'

        # Check for death, check for unconscious
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)

        # Major wound (B420) - bad fail (unconscious)

        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])

        self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        self._window_manager.set_menu_response(
                ('Major Wound (B420): Roll vs HT (%d) or be Stunned and Knocked Down' %
                 self._vodou_priest_ht),
                ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_BAD_FAIL)

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        assert not vodou_priest.is_conscious()

        # # # # # # # # # # # # # # # #

        # Aim (B324) on injury, will roll or lose aim

        # fail will roll #

        # Start by healing him up

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        #

        self._ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # Take damage, fail will roll

        self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        self._window_manager.set_menu_response(
                "roll <= WILL (13) or lose aim", False)

        damage = -1
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + damage  # aiming for 1 round + shock

        # make will roll #

        # Start by healing him up

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock
        # Check for death, check for unconscious
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        self._ruleset.reset_aim(vodou_priest)

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        expected_to_hit += 1  # aiming for 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # Take damage, make will roll

        expected_to_hit += 1  # aiming for 3 rounds
        self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        self._window_manager.set_menu_response(
                "roll <= WILL (13) or lose aim", True)

        damage = -1
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': damage},
                                 mock_fight_handler)

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + damage  # aiming for 1 round + shock

        # B327
        # TODO: if adjusted_hp <= -(5 * fighter.details['permanent']['hp']):
        #        fighter.details['state'] = 'dead'

        # Start by healing him up
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'end-turn'},
                                 mock_fight_handler)  # clear out shock

        # Check for death, check for unconscious
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'start-turn'},
                                 mock_fight_handler)
        vodou_priest.details['current']['hp'] = (
                vodou_priest.details['permanent']['hp'])
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'change-posture',
                                  'posture': 'standing'},
                                 mock_fight_handler)

        self._ruleset.reset_aim(vodou_priest)

    def test_adjust_hp_2(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_adjust_hp_2 ===\n')

        # Setup

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)

        del vodou_priest.details['advantages']['Combat Reflexes']

        original_hand_to_hand_info = self._ruleset.get_unarmed_info(
                vodou_priest,
                None,
                None)

        original_dodge_skill, ignore = self._ruleset.get_dodge_skill(
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

        self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        high_pain_thrshold_margin = 3
        stun_roll = self._vodou_priest_ht + high_pain_thrshold_margin
        self._window_manager.set_menu_response(
            ('Major Wound (B420): Roll vs. HT+3 (%d) or be Stunned and Knocked Down' %
             stun_roll),
            ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL)

        # failed the high stun roll so knockdown & stun is still in effect

        # +1 to make sure that the damage is more than half
        major_damage = - ((vodou_priest.details['permanent']['hp'] / 2) + 1)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'adjust-hp',
                                  'adj': major_damage},
                                 mock_fight_handler)

        hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
                                                            None,
                                                            None)

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

        dodge_skill, ignore = self._ruleset.get_dodge_skill(vodou_priest)

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

        # self._window_manager.set_menu_response('Use Armor\'s DR?', False)
        # high_pain_thrshold_margin = 3
        # stun_roll = self._vodou_priest_ht + high_pain_thrshold_margin
        # self._window_manager.set_menu_response(
        #    ('Major Wound (B420): Roll vs. HT+3 (%d) or be Stunned and Knocked Down' %
        #                                                        stun_roll),
        #    ca_gurps_ruleset.GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL)

        # # failed the high stun roll so knockdown & stun is still in effect

        # # +1 to make sure that the damage is more than half
        # major_damage = - ((vodou_priest.details['permanent']['hp'] / 2) + 1)
        # self._ruleset.do_action(vodou_priest,
        #                         {'action-name': 'adjust-hp',
        #                          'adj': major_damage},
        #                         mock_fight_handler)

        # hand_to_hand_info = self._ruleset.get_unarmed_info(vodou_priest,
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

        # dodge_skill, ignore = self._ruleset.get_dodge_skill(vodou_priest)

        # assert dodge_skill == original_dodge_skill + total_penalty
        # assert vodou_priest.details['posture'] == 'lying'

    def test_spell_casting(self):
        '''
        GURPS-specific test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_spell_casting ===\n')

        # Setup

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        opponent = ca_fighter.Fighter(
                'Opponent',
                'other_group',
                copy.deepcopy(self._one_more_guy),
                self._ruleset,
                self._window_manager)

        mock_fight_handler.set_opponent_for(vodou_priest, opponent)
        mock_fight_handler.set_fighter_object('Priest',
                                              'group',
                                              vodou_priest)
        mock_fight_handler.set_fighter_object('Opponent',
                                              'other_group',
                                              opponent)

        trials = [
          {'name': "Animate Shadow",
           'cost': 4,
           'casting time': 2,
           'skill': 16,
           'skill-bonus': -1,
           'duration': 5,
           'notes': "M154, Subject's shadow attacks them",
           'range': 'reguar',
           'save': ['ht']},
          # opponent must roll save
          # mark opponent with spell

          {'name': "Awaken",
           'cost': 1,
           'casting time': 1,
           'skill': 18,
           'skill-bonus': -1,
           'duration': 0,
           'notes': "M90",
           'range': 'area',
           'save': []},
          # Radius of spell effect
          # Mark opponent with spell

          {'name': "Death Vision",
           'cost': 2,
           'casting time': 3,
           'skill': 16,
           'skill-bonus': -1,
           'duration': 1,
           'notes': "M149, until IQ roll made",
           'range': 'reguar',
           'save': []},
          # Mark opponent with spell

          {'name': "Explosive Lightning",
           'cost': 2,
           'casting time': 3,
           'skill': 16,
           'skill-bonus': -1,
           'duration': 0,
           'notes': "M196, cost 2-mage level, damage 1d-1 /2",
           'range': 'missile',
           'save': []},
          # Cost to cast
          # Seconds to cast
          # Make a Ranged Attack
          # Mark samuel - Erik with

          {'name': "Itch",
           'cost': 2,
           'casting time': 1,
           'skill': 12,
           'skill-bonus': 0,
           'duration': 2,
           'notes': "M35",
           'range': 'regular',
           'save': ['ht']},
          # duration
        ]

        original_fp = vodou_priest.details['current']['fp']

        assert original_fp == vodou_priest.details['permanent']['fp']

        # Just to load the spells from the file
        with (ca_gurps_ruleset.GurpsRuleset(self._window_manager)
                as gurps_ruleset):
            pass

        for trial in trials:
            opponent.timers.clear_all()

            vodou_priest.timers.clear_all()
            vodou_priest.details['current']['fp'] = original_fp

            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['range'] == 'area'):
                self._window_manager.set_input_box_response(
                    'Radius of spell effect (%s) in yards' % trial['name'],
                    trial['cost'])

            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['cost'] is None):
                self._window_manager.set_input_box_response(
                    'Cost to cast (%s) - see (%s) ' % (trial['name'],
                                                       trial['notes']),
                    trial['cost'])
            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['casting time'] is None):
                self._window_manager.set_input_box_response(
                    'Seconds to cast (%s) - see (%s) ' % (trial['name'],
                                                          trial['notes']),
                    trial['casting time'])
            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['duration'] is None):
                self._window_manager.set_input_box_response(
                    'Duration for (%s) - see (%s) ' % (trial['name'],
                                                       trial['notes']),
                    trial['duration'])
            if (ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['range'] == 'missile'):
                self._window_manager.set_menu_response(
                    'Make a Ranged Attack', True)

            # TODO: need to deal with the ONE spell (Evisceration) that has
            # two saves
            if (len(ca_gurps_ruleset.GurpsRuleset.spells[
                    trial['name']]['save']) > 0):
                self._window_manager.set_menu_response(
                        ('%s must roll %s save against %s (skill %d)' % (
                            opponent.name,
                            trial['save'][0],
                            trial['name'],
                            trial['skill'])),
                        False) # False: they didn't save

            self._window_manager.set_menu_response(
                    'Mark %s with spell' % opponent.name, True)
            action = {
                'action-name': 'cast-spell',
                'spell-index': self._vodou_priest_spell_index[trial['name']]
                     }

            self._ruleset.do_action(vodou_priest, action, mock_fight_handler)

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
                self._ruleset.do_action(vodou_priest,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)
                self._ruleset.do_action(vodou_priest,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

                # For the opponent, you need to do start-turn, check, then
                # end-turn because they get affected after the caster does
                # their thing.

                self._ruleset.do_action(opponent,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

                assert len(opponent.details['timers']) == 1
                assert (opponent.details['timers'][0]['string'] ==
                        opponent_casting_text)

                self._ruleset.do_action(opponent,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)

            # One extra round for the opponent so that the timers get deleted.
            # Note the proper progression of start-turn / end-turn from the
            # casting loop through this through the duration loop.

            self._ruleset.do_action(opponent,
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
                self._ruleset.do_action(vodou_priest,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)
                self._ruleset.do_action(vodou_priest,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

                # Opponent

                assert len(opponent.details['timers']) == 1
                assert (opponent.details['timers'][0]['string'] ==
                        opponent_active_text)

                self._ruleset.do_action(opponent,
                                         {'action-name': 'end-turn'},
                                         mock_fight_handler)
                self._ruleset.do_action(opponent,
                                         {'action-name': 'start-turn'},
                                         mock_fight_handler)

            # Make sure that all of the timers are dead

            assert len(vodou_priest.details['timers']) == 0
            assert len(opponent.details['timers']) == 0

    def test_defend(self):
        '''
        GURPS test
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_defend ===\n')

        # Setup

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)
        mock_fight_handler = MockFightHandler()

        vodou_priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        requested_weapon_index = self._vodou_pistol_index
        mode = "ranged weapon"
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == requested_weapon_index

        # The only way you can see a 'defend' action is because aim is lost.

        # 1 round
        expected_to_hit = (self._vodou_priest_fighter_pistol_skill
                           + self._colt_pistol_acc
                           + 1)  # braced
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit

        # 2 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit + 1  # aiming for 2 rounds

        # DEFEND, LOSE AIM #

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'defend'},
                                 mock_fight_handler)

        # 3 rounds
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'aim', 'braced': True},
                                 mock_fight_handler)
        to_hit, why = self._ruleset.get_to_hit(vodou_priest, None, weapon, mode, None)
        assert to_hit == expected_to_hit  # aiming for 1 round

    def test_initiative_order(self):
        '''
        Partially GURPS-specific test
        '''
        debug = ca_debug.Debug()
        if ARGS.verbose:
            debug.print('\n=== test_initiative_order ===\n')

        world_data = WorldData(self.init_world_dict)
        mock_program = MockProgram()
        world = ca.World("internal_source_file",
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)

        # Famine and Jack have the same basic speed and dx -- it's up to rand
        # Pestilence and Moe have same basic speed but different dx

        # Start with:
        #   'Manny':        5.25, 10, rand=1
        #   'Jack':         5.75, 12, rand=3
        #   'Moe':          5.5,  12, rand=3
        #   'Famine':       5.75, 12, rand=1
        #   'Pestilence':   5.5,  11, rand=5

        expected = [
                    {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 3
                    {'name': 'Famine',     'group': 'horsemen'}, # 5.75, 12, 1
                    {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 3
                    {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 5
                    {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1

        # Do this multiple times just to verify that the random stuff works
        for i in range(10):
            # random.randint(1, 6) should generate: 1 3 3 1 5 3 5 5 5 1
            random.seed(9001)  # 9001 is an arbitrary number
            fight_handler = ca.FightHandler(self._window_manager,
                                            world,
                                            'horsemen',
                                            None,  # replay history
                                            save_snapshot=False)
            fighters = fight_handler.get_fighters()

            # Check the order against the one that I expect

            for fighter, expected_value in zip(fighters, expected):
                assert fighter['name'] == expected_value['name']
                assert fighter['group'] == expected_value['group']

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
        unconscious_fighter.set_consciousness(ca_fighter.Fighter.UNCONSCIOUS,
                                              None)
        dead_fighter.set_consciousness(ca_fighter.Fighter.DEAD, None)

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

        # 'Jack': copy.deepcopy(self._tank_fighter),
        # 'Famine': copy.deepcopy(self._thief_fighter),
        # 'Moe': copy.deepcopy(self._one_more_guy),
        # 'Pestilence': copy.deepcopy(self._vodou_priest_fighter),
        # 'Manny': copy.deepcopy(self._bokor_fighter),

        expected_fighters = [
            copy.deepcopy(self._tank_fighter),
            copy.deepcopy(self._thief_fighter),
            copy.deepcopy(self._one_more_guy),
            copy.deepcopy(self._vodou_priest_fighter),
            copy.deepcopy(self._bokor_fighter)]

        expected_fighters[injured_index]['current']['hp'] -= injured_hp
        expected_fighters[unconscious_index]['state'] = "unconscious"
        expected_fighters[dead_index]['state'] = "dead"

        # These fighters are in a 'monster' group -- they're numbered
        # alphabetically
        expected_fighters[1]['monster-number'] = 1
        expected_fighters[3]['monster-number'] = 2

        fighters = fight_handler.get_fighters()
        assert len(expected_fighters) == len(fighters)

        assert self._are_equal(expected_fighters[0], fighters[0]['details'])
        assert self._are_equal(expected_fighters[1], fighters[1]['details'])
        assert self._are_equal(expected_fighters[2], fighters[2]['details'])
        assert self._are_equal(expected_fighters[3], fighters[3]['details'])
        assert self._are_equal(expected_fighters[4], fighters[4]['details'])

    def test_initiative_order_again(self):
        '''
        Partially GURPS-specific test

        This is just like test_initiative_order except the fighters are
        reordered randomly and a different random seed is used.
        '''
        debug = ca_debug.Debug()
        #if ARGS.verbose:
        #    debug.print('\n=== test_initiative_order_again ===\n')

        world_data = WorldData(self.init_world_dict_2)
        mock_program = MockProgram()
        world = ca.World("internal_source_file",
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)

        # Start with:
        #   'Bob': 5.5, 11, rand=3
        #   'Ted': 5.75, 12, rand=1
        #   'Groucho': 5.5, 12, rand=4
        #   'Harpo': 5.75, 12, rand=4
        #   'Chico': 5.25, 10, rand=5

        expected = [
                    {'name': 'Harpo',   'group': 'marx'},  # 5.75, 12, 4
                    {'name': 'Ted',     'group': 'PCs'},   # 5.75, 12, 1
                    {'name': 'Groucho', 'group': 'marx'},  # 5.5,  12, 4
                    {'name': 'Bob',     'group': 'PCs'},   # 5.5,  11, 3
                    {'name': 'Chico',   'group': 'marx'},  # 5.25, 10, 5
                   ]

        # Do this multiple times just to verify that the random stuff works
        for i in range(10):
            # random.randint(1, 6) should generate: 3 1 4 4 5
            random.seed(8534)  # 8534 is an arbitrary number
            fight_handler = ca.FightHandler(self._window_manager,
                                            world,
                                            'marx',
                                            None,  # Playback history
                                            save_snapshot=False)
            fighters = fight_handler.get_fighters()

            # Check the order against the one that I expect

            for fighter, expected_value in zip(fighters, expected):
                assert fighter['name'] == expected_value['name']
                assert fighter['group'] == expected_value['group']
