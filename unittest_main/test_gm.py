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

from .test_common import GmTestCaseCommon
from .test_common import MockFightHandler
from .test_common import MockProgram
from .test_common import MockWindowManager
from .test_common import TestPersonnelHandler
from .test_common import TestRuleset
from .test_common import WorldData

class GmTestCase(GmTestCaseCommon):
    '''
    These tests are general tests that don't need a specific ruleset.
    '''

    def test_change_opponents(self):
        '''
        Test that changing opponents from one that's damaged doesn't affect
        any of the fighters (except that the opponent was changed).  This
        mirrors a bug that I thought I saw a while ago.
        '''
        #if ARGS.verbose:
        #    print('\n=== test_change_opponents ===\n')

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
        expected = [
                    {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 3
                    {'name': 'Famine',     'group': 'horsemen'}, # 5.75, 12, 1
                    {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 3
                    {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 5
                    {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1

        injured_hp = 3  # This is arbitrary
        injured_index = 2

        random.seed(9001)  # 9001 is an arbitrary number
        fight_handler = ca.FightHandler(self._window_manager,
                                        world,
                                        'horsemen',
                                        None,  # Playback history
                                        save_snapshot=False)
        fighters = fight_handler.get_fighters()

        expected_index = 0
        assert world_data.read_data['current-fight']['index'] == expected_index
        current_fighter = fight_handler.get_current_fighter()
        # Make fighter 0 fight figher 2

        self._ruleset.do_action(current_fighter,
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
        self._ruleset.do_action(current_fighter,
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

        # {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 3 -- _tank_fighter
        # {'name': 'Famine',     'group': 'horsemen'}, # 5.75, 12, 1 -- _thief_fighter
        # {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 3 -- _one_more_guy
        # {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 5 -- _vodou_priest_fighter
        # {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1 -- _bokor_fighter

        expected_fighters = [
            copy.deepcopy(self._tank_fighter),
            copy.deepcopy(self._thief_fighter),
            copy.deepcopy(self._one_more_guy),
            copy.deepcopy(self._vodou_priest_fighter),
            copy.deepcopy(self._bokor_fighter)]
        expected_fighters[0]['opponent'] = {'group': 'PCs', 'name': 'Jack'}
        expected_fighters[0]['actions_this_turn'] = ['pick-opponent',
                                                     'pick-opponent']
        expected_fighters[injured_index]['current']['hp'] -= injured_hp

        # Check that everything is as it should be

        assert len(expected_fighters) == len(fighters)
        assert self._are_equal(expected_fighters[0], fighters[0]['details'])
        assert self._are_equal(expected_fighters[1], fighters[1]['details'])
        assert self._are_equal(expected_fighters[2], fighters[2]['details'])
        assert self._are_equal(expected_fighters[3], fighters[3]['details'])
        assert self._are_equal(expected_fighters[4], fighters[4]['details'])

    def test_don_doff_armor(self):
        '''
        General test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_don_doff_armor ===\n')

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

        # Don armor

        requested_armor_index = self._vodou_armor_index
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'don-armor',
                                  'armor-index': requested_armor_index},
                                 mock_fight_handler)

        armor_index_list = vodou_priest.get_current_armor_indexes()
        armor_list = vodou_priest.get_items_from_indexes(armor_index_list)

        assert len(armor_index_list) == 1
        assert armor_index_list[0] == requested_armor_index
        assert armor_list[0]['name'] == "Sport coat/Jeans"

        # Doff armor

        armor_index_list = vodou_priest.get_current_armor_indexes()

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'doff-armor',
                                  'armor-index': armor_index_list[0]},
                                 mock_fight_handler)

        armor_index_list = vodou_priest.get_current_armor_indexes()
        assert len(armor_index_list) == 0

        # The effect of the armor is tested in 'hp'

    def test_draw_sheathe_weapon(self):
        '''
        General test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_draw_sheathe_weapon ===\n')

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

        # Draw Weapon

        requested_weapon_index = self._vodou_pistol_index
        mode = "ranged weapon"
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"

        # Sheathe Weapon

        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'holster-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == None

        # The effect of the weapon is tested throughout the testing

    def test_reload(self):
        '''
        General test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_reload ===\n')

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

        # Draw Weapon

        requested_weapon_index = self._vodou_pistol_index
        mode = "ranged weapon"
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"
        assert weapon.shots_left() == self._vodou_priest_initial_shots

        clip = vodou_priest.equipment.get_item_by_index(
                self._vodou_priest_ammo_index)
        # check the number of clips/batteries

        assert clip['count'] == self._vodou_priest_ammo_count

        # A. Fire twice and verify that the shots left went down

        shots_taken = 2
        for shot in range(shots_taken):
            self._ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)
            # To simulate the start of the round
            vodou_priest.details['current-weapon'] = 0

        assert (weapon.shots_left() ==
                (self._vodou_priest_initial_shots - shots_taken))

        # Discard the rest of the shots in the clip

        shots_taken = weapon.shots_left()
        for shot in range(shots_taken):
            self._ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)
            # To simulate the start of the round
            vodou_priest.details['current-weapon'] = 0

        # Now, reload

        self._window_manager.set_menu_response('Reload With What', 1)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert weapon.shots_left() == self._vodou_priest_initial_shots
        assert clip['count'] == (self._vodou_priest_ammo_count - 1)

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
                self._ruleset.do_action(vodou_priest,
                                         {'action-name': 'attack'},
                                         mock_fight_handler)
                # To simulate the start of the round
                vodou_priest.details['current-weapon'] = 0
            self._window_manager.set_menu_response('Reload With What', 1)
            self._ruleset.do_action(vodou_priest,
                                     {'action-name': 'reload'},
                                     mock_fight_handler)

        # C. Shoot a number of times and verify that we have the number of
        #    shots left that we expect (in our last clip).

        shots_taken = 3  # Pick a number at random
        for shot in range(shots_taken):
            self._ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)
            # To simulate the start of the round
            vodou_priest.details['current-weapon'] = 0

        assert (weapon.shots_left() ==
                (self._vodou_priest_initial_shots - shots_taken))

        # D. Reload when there's nothing left with which to reload

        self._window_manager.set_menu_response('Reload With What', None)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert (weapon.shots_left() ==
                (self._vodou_priest_initial_shots - shots_taken))

        throw_away, virtual_clip = vodou_priest.equipment.get_item_by_name(
                'C Cell')
        assert(virtual_clip is None)

    def test_reload_2(self):
        '''
        General test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_reload_2 ===\n')

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

        # Draw Weapon

        requested_weapon_index = self._vodou_pistol_index
        mode = "ranged weapon"
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': requested_weapon_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(vodou_priest)
        assert actual_weapon_index == requested_weapon_index
        assert weapon.details['name'] == "pistol, Colt 170D"
        assert weapon.shots_left() == self._vodou_priest_initial_shots

        clip = vodou_priest.equipment.get_item_by_index(
                self._vodou_priest_ammo_index)

        # check the number of clips/batteries (5)

        assert clip['count'] == self._vodou_priest_ammo_count

        # A. Fire twice and verify that the shots left went down

        shots_taken = 2
        for shot in range(shots_taken):
            self._ruleset.do_action(vodou_priest,
                                     {'action-name': 'attack'},
                                     mock_fight_handler)
            # To simulate the start of the round
            vodou_priest.details['current-weapon'] = 0

        assert (weapon.shots_left() ==
                (self._vodou_priest_initial_shots - shots_taken))

        # Reload and verify that there are two different types of clips (a
        # bunch of full ones and one partially full one)

        self._window_manager.set_menu_response('Reload With What', 1)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert clip['count'] == (self._vodou_priest_ammo_count - 1)

        first_index, virtual_clip = vodou_priest.equipment.get_item_by_name(
                'C Cell')
        assert(virtual_clip is not None)

        second_index, second_clip = vodou_priest.equipment.get_item_by_name(
                'C Cell', first_index)
        assert(second_clip is not None)

        assert(second_clip['shots_left'] == self._vodou_priest_initial_shots
               - shots_taken)

        # Now, try to reload other clips

        # Start off by shooting off one shot so the reload will work
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'attack'},
                                 mock_fight_handler)
        # To simulate the start of the round
        vodou_priest.details['current-weapon'] = 0

        # Reload with the partial (the previously ejected one)
        self._window_manager.set_menu_response('Reload With What',
                                                second_index)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)
        assert (weapon.shots_left() ==
                (self._vodou_priest_initial_shots - shots_taken))

        # Now, reload with a full one
        self._window_manager.set_menu_response('Reload With What',
                                                first_index)
        self._ruleset.do_action(vodou_priest,
                                 {'action-name': 'reload'},
                                 mock_fight_handler)

        assert (weapon.shots_left() == self._vodou_priest_initial_shots)

    def test_stun_and_consciousness(self):
        '''
        MIXED test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_stun_and_consciousness ===\n')

        # Setup

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)

        world_data = WorldData(self.init_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)
        fight_handler = ca.FightHandler(self._window_manager,
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

        self._ruleset.do_action(current_fighter,
                                 {'action-name': 'pick-opponent',
                                  'opponent': {'name': 'Moe', 'group': 'PCs'}},
                                 fight_handler)

        # Test

        new_state = ca_fighter.Fighter.ALIVE
        self._ruleset.do_action(current_fighter,
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
        self._ruleset.do_action(current_fighter,
                                 {'action-name': 'set-consciousness',
                                  'level': new_state},
                                 fight_handler)
        state_number = ca_fighter.Fighter.get_fighter_state(
                current_fighter.details)
        assert state_number == new_state
        opponent = fight_handler.get_opponent_for(current_fighter)
        assert opponent is None

        # Setup Stun Test

        original_hand_to_hand_info = self._ruleset.get_unarmed_info(
                current_fighter,
                None,
                None)
        original_dodge_skill, ignore = self._ruleset.get_dodge_skill(
                current_fighter)

        # Stun

        self._ruleset.do_action(current_fighter,
                                 {'action-name': 'stun', 'stun': True},
                                 fight_handler)

        # Check whether stunned

        hand_to_hand_info = self._ruleset.get_unarmed_info(current_fighter,
                                                            None,
                                                            None)
        stun_penalty = -4
        total_penalty = stun_penalty

        assert (hand_to_hand_info['parry_skill'] ==
                original_hand_to_hand_info['parry_skill'] + total_penalty)

        dodge_skill, ignore = self._ruleset.get_dodge_skill(current_fighter)

        assert dodge_skill == original_dodge_skill + total_penalty

    def test_timers(self):
        '''
        Basic test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_timers ===\n')

        fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)

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
        #if ARGS.verbose:
        #    print('\n=== test_save ===\n')

        base_world_dict = copy.deepcopy(self.base_world_dict)

        self._window_manager = MockWindowManager()
        self._ruleset = TestRuleset(self._window_manager)

        # Test that leaving a fight moves the bad guys to the dead monster
        # list
        #if ARGS.verbose:
        #    print('\n----------- LEAVE FIGHT -----------\n')

        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)

        fight_handler = ca.FightHandler(self._window_manager,
                                        world,
                                        "Dima's Crew",
                                        None,  # Playback history
                                        save_snapshot=False)

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self._is_in_dead_monsters(world_data, "Dima's Crew")
        # assert not world_data.read_data['current-fight']['saved']

        self._window_manager.set_char_response(ord('q'))
        self._window_manager.set_menu_response('Leaving Fight', False)

        fight_handler.handle_user_input_until_done()

        assert "Dima's Crew" not in world_data.read_data['fights']
        assert self._is_in_dead_monsters(world_data, "Dima's Crew")
        assert not world_data.read_data['current-fight']['saved']

        #
        # test that SAVING the fight works
        #
        #if ARGS.verbose:
        #    print('\n----------- SAVE FIGHT -----------\n')

        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)

        assert (world_data.read_data['current-fight']['monsters'] !=
                "Dima's Crew")

        fight_handler = ca.FightHandler(self._window_manager,
                                        world,
                                        "Dima's Crew",
                                        None,  # Playback history
                                        save_snapshot=False)

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self._is_in_dead_monsters(world_data, "Dima's Crew")
        # assert not world_data.read_data['current-fight']['saved']

        self._window_manager.set_char_response(ord('q'))
        self._window_manager.set_menu_response(
                'Leaving Fight', {'doit': fight_handler.save_fight})
        self._window_manager.set_menu_response('Leaving Fight', False)

        fight_handler.handle_user_input_until_done()

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self._is_in_dead_monsters(world_data, "Dima's Crew")
        assert world_data.read_data['current-fight']['saved']
        assert (world_data.read_data['current-fight']['monsters'] ==
                "Dima's Crew")

        #
        # test that KEEPING the fight works
        #
        #if ARGS.verbose:
        #    print('\n----------- KEEP FIGHT -----------\n')

        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)

        fight_handler = ca.FightHandler(self._window_manager,
                                        world,
                                        "Dima's Crew",
                                        None,  # Playback history
                                        save_snapshot=False)

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self._is_in_dead_monsters(world_data, "Dima's Crew")
        # assert not world_data.read_data['current-fight']['saved']

        self._window_manager.set_char_response(ord('q'))
        self._window_manager.set_menu_response(
                'Leaving Fight', {'doit': fight_handler.keep_fight})
        self._window_manager.set_menu_response('Leaving Fight', False)

        fight_handler.handle_user_input_until_done()

        assert "Dima's Crew" in world_data.read_data['fights']
        assert not self._is_in_dead_monsters(world_data, "Dima's Crew")
        assert not world_data.read_data['current-fight']['saved']

    def test_add_remove_equipment(self):
        '''
        Basic test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_add_remove_equipment ===\n')

        fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)
        mock_fight_handler = MockFightHandler()

        original_item = fighter.details['stuff'][
                                        self._tank_fighter_pistol_index]
        current_count = len(fighter.details['stuff'])
        original_stuff = copy.deepcopy(fighter.details['stuff'])

        # Same item - verify that the count goes up

        assert original_item['count'] == 1
        same_item = copy.deepcopy(original_item)
        same_item['count'] = 2

        before_item_count = fighter.equipment.get_item_count()
        ignore = fighter.add_equipment(same_item, 'test')
        after_item_count = fighter.equipment.get_item_count()

        assert original_item['count'] == 3
        assert before_item_count == after_item_count

        # Similar item - verify that it doesn't just bump the count

        similar_item = copy.deepcopy(original_item)
        similar_item['count'] = 1
        similar_item['acc'] = original_item['acc'] + 1

        assert len(fighter.details['stuff']) == current_count
        self._window_manager.set_menu_response(
                'Make pistol, Sig D65 the preferred weapon?',
                False)
        ignore = fighter.add_equipment(similar_item, 'test')

        current_count += 1

        assert len(fighter.details['stuff']) == current_count

        # Different item

        different_item = {
                "name": "pistol, Baretta DX 192",
                "type": {"ranged weapon": {"damage": {"dice": {"plus": 4,
                                                               "num_dice": 1,
                                                               "type": "pi"}},
                                           "skill": {"Guns (Pistol)": 0}}
                                           },
                          "damage": {"dice": "1d+4"},
                          "acc": 2,
                          "ammo": {"name": "C Cell", "shots": 8},
                          "clip": {"name": "C Cell",
                                   "shots_left": 8,
                                   "shots": 8,
                                   "type": {"misc": 1},
                                   "count": 1,
                                   "notes": "",
                                   "owners": None},
                          "reload": 3,
                          "reload_type": 2,
                          "count": 1,
                          "owners": None,
                          "notes": ""}

        assert len(fighter.details['stuff']) == current_count
        self._window_manager.set_menu_response(
                'Make pistol, Baretta DX 192 the preferred weapon?',
                False)
        new_pistol_index = fighter.add_equipment(different_item, 'test')
        current_count += 1
        assert len(fighter.details['stuff']) == current_count

        # Make sure we only add to the end

        for i, original_item in enumerate(original_stuff):
            # We've changed the count on the fighter's pistol
            if i != self._tank_fighter_pistol_index:
                assert self._are_equal(original_item,
                                        fighter.details['stuff'][i])

        # Remove counted item
        self._window_manager.set_input_box_response(
                'How Many Items (3 Available)?', 1)
        fighter.remove_equipment(self._tank_fighter_pistol_index)
        weapon = fighter.equipment.get_item_by_index(
                self._tank_fighter_pistol_index)
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
                                          # in _tank_fighter_pistol_index
              "type": {"ranged weapon": ...},
              "damage": {"dice": "1d+4"},
              "acc": 4,
              "clip": {"name": "C Cell", "shots_left": 9, "shots": 9},
              "reload": 3,
              "reload_type": 2,
              "skill": {"Guns (Pistol)": 0},
              "count": 1, <------------------------------------------- now 2
              "owners": None,
              "notes": ""
             },
         1=> {"name": "sick stick",
              "type": {"melee weapon": ...},
              "damage": {"dice": "1d+1 fat"},
              "skill": {"Axe/Mace": 0},
              "count": 1,
              "owners": None,
              "notes": ""
             },
         2=> {"name": "C Cell", "type": {"misc": 1}, "count": 5, "notes": "",
              "owners": None,
             },
         3=> {"name": "pistol, Sig D65",  # the index of this is stored
                                          # in _tank_fighter_pistol_index
              "type": {"ranged weapon": ...},
              "damage": {"dice": "1d+4"},
              "acc": 4, <---------------------- now 5 -- this is similar item
              "clip": {"name": "C Cell", "shots_left": 9, "shots": 9},
              "reload": 3,
              "reload_type": 2,
              "skill": {"Guns (Pistol)": 0},
              "count": 1,
              "owners": None,
              "notes": ""
             },
         4=> {"name": "pistol, Baretta DX 192", XXXXX--different item-removed
              "type": {"ranged weapon": ...},
              "damage": {"dice": "1d+4"},
              "acc": 2,
              "clip": {"name": "C Cell", "shots_left": 8, "shots": 8},
              "reload": 3,
              "reload_type": 2,
              "skill": {"Guns (Pistol)": 0},
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
        self._ruleset.do_action(fighter,
                                 {'action-name': 'draw-weapon',
                                  'weapon-index': sick_stick_index},
                                 mock_fight_handler)
        weapon, actual_weapon_index = self._get_current_weapon(fighter)
        assert actual_weapon_index == sick_stick_index

        # remove counted item before weapon index

        sig_acc_4_index = 0
        self._window_manager.set_input_box_response(
                'How Many Items (2 Available)?', 1)
        fighter.remove_equipment(sig_acc_4_index) # Should just reduce the count
        weapon = fighter.equipment.get_item_by_index(0)
        assert weapon['name'] == "pistol, Sig D65"
        assert weapon['acc'] == 4
        assert weapon['count'] == 1
        weapon, actual_weapon_index = self._get_current_weapon(fighter)
        assert actual_weapon_index == sick_stick_index

        # remove non-counted item before weapon index
        fighter.remove_equipment(sig_acc_4_index) # Should remove item
        sick_stick_index -= 1
        weapon = fighter.equipment.get_item_by_index(sick_stick_index)
        assert weapon['name'] == "sick stick"
        weapon, actual_weapon_index = self._get_current_weapon(fighter)
        assert weapon.name == "sick stick"
        assert actual_weapon_index == sick_stick_index

        # remove item after weapon index
        sig_acc_5_index = 2
        fighter.remove_equipment(sig_acc_5_index)
        weapon = fighter.equipment.get_item_by_index(sick_stick_index)
        assert weapon['name'] == "sick stick"
        weapon, actual_weapon_index = self._get_current_weapon(fighter)
        assert weapon.name == "sick stick"
        assert actual_weapon_index == sick_stick_index

        # remove item at weapon index
        fighter.remove_equipment(sick_stick_index)
        weapon, actual_weapon_index = self._get_current_weapon(fighter)
        assert weapon is None
        assert actual_weapon_index is None

    def test_preferred_add_remove_weapon(self):
        '''
        Basic test
        '''

        #if ARGS.verbose:
        #    print('\n=== test_preferred_add_remove_weapon ===\n')

        fighter = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)
        '''
            "stuff": [
                 {"name": "pistol, Sig D65",  # the index of this is stored
                                              # in _tank_fighter_pistol_index
                  "type": {"ranged weapon": ...},
                  "damage": {"dice": "1d+4"},
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
                  "skill": {"Guns (Pistol)": 0},
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "sick stick",
                  "type": {"melee weapon": ...},
                  "damage": {"dice": "1d+1 fat"},
                  "skill": {"Axe/Mace": 0},
                  "count": 1,
                  "owners": None,
                  "notes": ""},
                 {"name": "C Cell", "type": {"misc": 1}, "count": 5, "notes": "",
                  "owners": None}
            ],

        '''
        mock_fight_handler = MockFightHandler()

        original_item = fighter.details['stuff'][
                                        self._tank_fighter_pistol_index]
        current_count = len(fighter.details['stuff'])
        original_stuff = copy.deepcopy(fighter.details['stuff'])

        # Adds an identical weapon to an existing one.  Since there isn't a
        # preferred weapon, it should up the count and make it preferred.

        assert len(fighter.details['preferred-weapon-index']) == 0
        assert original_item['count'] == 1

        same_item = copy.deepcopy(original_item)
        same_item['count'] = 2 # 2 items to add
        before_item_count = fighter.equipment.get_item_count()
        ignore = fighter.add_equipment(same_item, 'test')
        after_item_count = fighter.equipment.get_item_count()

        assert original_item['count'] == 3 # we've added 2 new items
        assert before_item_count == after_item_count

        assert len(fighter.details['preferred-weapon-index']) == 1
        new_preferred_weapon_index = fighter.details['preferred-weapon-index'][0]
        assert new_preferred_weapon_index == self._tank_fighter_pistol_index

        # Add the same weapon again and show that we don't get asked to make
        # the newly added weapon a preferred weapon

        before_item_count = fighter.equipment.get_item_count()
        ignore = fighter.add_equipment(same_item, 'fourth')
        after_item_count = fighter.equipment.get_item_count()

        assert original_item['count'] == 5 # we've added 2 MORE new items
        assert before_item_count == after_item_count
        assert len(fighter.details['preferred-weapon-index']) == 1
        new_preferred_weapon_index = fighter.details['preferred-weapon-index'][0]
        assert new_preferred_weapon_index == self._tank_fighter_pistol_index

        # Add weapon to list w/preferred weapon: should ask whether to make
        # new weapon preferred - answer = No

        similar_item = copy.deepcopy(original_item)
        similar_item['count'] = 1
        similar_item['acc'] = original_item['acc'] + 1 # just so it's different
        previous_preferred_weapon = fighter.details['preferred-weapon-index'][0]

        self._window_manager.set_menu_response(
                'Make pistol, Sig D65 the preferred weapon?', False)
        ignore = fighter.add_equipment(similar_item, 'sixth')
        new_preferred_weapon = fighter.details['preferred-weapon-index'][0]

        assert len(fighter.details['preferred-weapon-index']) == 1
        assert new_preferred_weapon == previous_preferred_weapon

        # Add weapon to list w/preferred weapon: should ask whether to make
        # new weapon preferred - answer = Yes, replace existing preference

        similar_item = copy.deepcopy(similar_item)
        similar_item['acc'] += 1
        self._window_manager.set_menu_response(
                'Make pistol, Sig D65 the preferred weapon?',
                ca_fighter.Fighter.REPLACE_PREFERRED)
        self._window_manager.set_menu_response('Replace which weapon?', 0)

        new_index = fighter.add_equipment(similar_item, 'eighth')

        # The current preferred weapon should be the most recently added item
        current_count = len(fighter.details['stuff'])
        new_preferred_weapon = fighter.details['preferred-weapon-index'][0]

        assert len(fighter.details['preferred-weapon-index']) == 1
        assert new_preferred_weapon == current_count - 1
        assert new_index == new_preferred_weapon

        # [  index 0: { 'name': 'pistol, Sig D65', 'acc': 4, 'count': 5},
        #    index 1: { 'name': 'sick stick', 'count': 1 }
        #    index 2: { 'name': 'C Cell' },
        #    index 3: { 'name': 'pistol, Sig D65', 'acc': 5, 'count': 1},
        #    index 4: { 'name': 'pistol, Sig D65', 'acc': 6, 'count': 1} ]

        # Remove preferred weapon, preferred weapon should be none

        old_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        self._window_manager.set_input_box_response(
                'How Many Items (5 Available)?', 5)
        fighter.remove_equipment(old_preferred_weapon)
        assert len(fighter.details['preferred-weapon-index']) == 0

        # Remove weapon before preferred weapon: preferred index should move
        # to continue pointing to preferred weapon

        # [  index 0: { 'name': 'pistol, Sig D65', 'acc': 4, 'count': 5},
        #    index 1: { 'name': 'sick stick', 'count': 1 } <--- PREFERRED
        #    index 2: { 'name': 'C Cell' },
        #    index 3: { 'name': 'pistol, Sig D65', 'acc': 5, 'count': 1}]

        fighter.details['preferred-weapon-index'] = [self._tank_fighter_sickstick_index]
        old_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        index_to_remove = old_preferred_weapon - 1 # index 0
        self._window_manager.set_input_box_response(
                'How Many Items (5 Available)?', 5)
        fighter.remove_equipment(index_to_remove)
        new_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        assert new_preferred_weapon == old_preferred_weapon - 1

        # Remove weapon after preferred weapon: preferred index should
        # remain unchanged and point to preferred weapon

        # [  index 0: { 'name': 'sick stick', 'count': 1 } <- PREFERRED
        #    index 1: { 'name': 'C Cell', 'count': 5 },
        #    index 2: { 'name': 'pistol, Sig D65', 'acc': 5, 'count': 1}]

        old_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        index_to_remove = old_preferred_weapon + 1 # index 1
        self._window_manager.set_input_box_response(
                'How Many Items (5 Available)?', 5)
        fighter.remove_equipment(index_to_remove)
        new_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        assert new_preferred_weapon == old_preferred_weapon

        # Add weapon to empty list: should make weapon preferred

        while len(fighter.details['stuff']) > 0:
            fighter.remove_equipment(0)

        assert len(fighter.details['stuff']) == 0
        assert len(fighter.details['preferred-weapon-index']) == 0

        original_item = self._tank_fighter['stuff'][
                                        self._tank_fighter_pistol_index]
        same_item = copy.deepcopy(original_item)

        new_index = fighter.add_equipment(same_item, 'test')
        assert len(fighter.details['preferred-weapon-index']) == 1
        new_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        assert new_preferred_weapon == new_index

        # [  index 0: { 'name': 'pistol, Sig D65', 'acc': 5, 'count': 1} <- PREFERRED ]

        # Add weapon to list w/preferred weapon: should ask whether to make
        # new weapon preferred - answer = No

        similar_item = copy.deepcopy(similar_item)
        similar_item['name'] = 'Ray Gun'
        similar_item['acc'] += 1
        self._window_manager.set_menu_response(
                'Make Ray Gun the preferred weapon?',
                ca_fighter.Fighter.NOT_PREFERRED)

        old_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        new_index = fighter.add_equipment(similar_item, 'eighth')
        new_preferred_weapon = fighter.details['preferred-weapon-index'][0]

        assert len(fighter.details['preferred-weapon-index']) == 1
        assert new_preferred_weapon == old_preferred_weapon

        # Add weapon to list w/preferred weapon: should ask whether to make
        # new weapon preferred - answer = Yes, add to existing list

        similar_item = copy.deepcopy(similar_item)
        similar_item['name'] = 'Ray Gun 2'
        similar_item['acc'] += 1
        self._window_manager.set_menu_response(
                'Make Ray Gun 2 the preferred weapon?',
                ca_fighter.Fighter.ADD_PREFERRED)

        old_preferred_weapon = fighter.details['preferred-weapon-index'][0]
        new_index = fighter.add_equipment(similar_item, 'eighth')

        assert len(fighter.details['preferred-weapon-index']) == 2
        assert fighter.details['preferred-weapon-index'][0] == old_preferred_weapon
        assert fighter.details['preferred-weapon-index'][1] == new_index


    def test_give_equipment(self):
        '''
        Basic test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_give_equipment ===\n')

        tank = ca_fighter.Fighter(
                'Tank',
                'group',
                copy.deepcopy(self._tank_fighter),
                self._ruleset,
                self._window_manager)

        tank_after_gift = [
                 {"name": "sick stick",
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
                  "owners": None}]

        priest = ca_fighter.Fighter(
                'Priest',
                'group',
                copy.deepcopy(self._vodou_priest_fighter),
                self._ruleset,
                self._window_manager)
        priest_after_gift = [
                 {"name": "pistol, Colt 170D",
                  "type": {"ranged weapon": {"damage": {"dice": {"plus": 4,
                                                                 "num_dice": 1,
                                                                 "type": "pi"}},
                                             "skill": {"Guns (Pistol)": 0}}
                                             },
                  "acc": self._colt_pistol_acc,
                  "ammo": {"name": "C Cell", "shots": self._vodou_priest_initial_shots},
                  "clip": {"name": "C Cell",
                           "shots_left": self._vodou_priest_initial_shots,
                           "shots": self._vodou_priest_initial_shots,
                           "type": {"misc": 1},
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
                  "name": "Sport coat/Jeans"},
                 {"name": "pistol, Sig D65",  # the index of this is stored
                                              # in _tank_fighter_pistol_index
                  "type": {"ranged weapon": {"damage": {"dice": {"plus": 4,
                                                                 "num_dice": 1,
                                                                 "type": "pi"}},
                                             "skill": {"Guns (Pistol)": 0}}
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
            ]

        # Give item from tank to priest
        mock_fight_handler = MockFightHandler()
        mock_fight_handler.set_fighter_object('Priest', 'group', priest)

        self._ruleset.do_action(
                tank,
                {'action-name': 'give-equipment',
                 'item-index': self._tank_fighter_pistol_index,
                 'count': 1,
                 'recipient': {'name': 'Priest', 'group': 'group'},
                 'comment': '%s gave pistol to %s' % (tank.name, priest.name)
                 },
                mock_fight_handler)

        assert self._are_equal(tank_after_gift, tank.details['stuff'])
        assert self._are_equal(priest_after_gift, priest.details['stuff'])

    def test_redirects(self):
        '''
        Basic test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_redirects ===\n')

        base_world_dict = copy.deepcopy(self.base_world_dict)
        world_data = WorldData(base_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)

        # Verify that redirect that's in the World object works the way I
        # expect it to.

        source_char = world.get_creature_details('One More Guy', 'NPCs')
        dest_char = world.get_creature_details('One More Guy', 'Dima\'s Crew')
        assert self._are_equal(source_char, dest_char)

    def test_redirects_promote_to_NPC(self):
        '''
        Basic test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_redirects_promote_to_NPC ===\n')

        init_world_dict = copy.deepcopy(self.init_world_dict)
        world_data = WorldData(init_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)
        self._window_manager.reset_error_state()

        # random.randint(1, 6) should generate: 1 3 3 1 5 3 5 5 5 1
        random.seed(9001)  # 9001 is an arbitrary number

        # expected = [
        #            {'name': 'Jack',       'group': 'PCs'},      # 5.75, 12, 2
        pc_jack_index = 0
        #            {'name': 'Famine',    'group': 'horsemen'}, # 5.75, 12, 4
        monster_famine_index = 1
        #            {'name': 'Moe',        'group': 'PCs'},      # 5.5,  12, 4
        pc_moe_index = 2
        #            {'name': 'Pestilence', 'group': 'horsemen'}, # 5.5,  11, 4
        monster_pestilence_index = 3
        #            {'name': 'Manny',      'group': 'PCs'}]      # 5.25, 10, 1
        pc_manny_index = 4

        fight_handler = ca.FightHandler(self._window_manager,
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
        assert self._are_equal(source_char, dest_char)

        # FightHandler.promote_to_NPC - check destination has an NPC #

        self._window_manager.expect_error(
                ['There\'s already an NPC named Pestilence'])
        fight_handler.set_viewing_index(monster_pestilence_index)
        fight_handler.promote_to_NPC()

        assert(self._window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # TODO: FightHandler.promote_to_NPC - check source already an NPC #

        # if npc_name not in self.__world.details['NPCs']:
        # self._window_manager.error(['%s is already an NPC' %
        #                             new_NPC.name])

    def test_NPC_joins(self):
        '''
        Basic test
        '''
        #if ARGS.verbose:
        #    print('\n=== test_NPC_joins ===\n')

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
        #            'Famine': copy.deepcopy(self._thief_fighter),
        #
        #            # 5.5, 11, rand=4
        #            'Pestilence': copy.deepcopy(self._vodou_priest_fighter),
        #          }
        #        }
        #    },

        init_world_dict = copy.deepcopy(self.init_world_dict)
        world_data = WorldData(init_world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False)
        self._window_manager.set_menu_response('Which Template Group',
                                                'dudes')
        npc_handler = ca.PersonnelHandler(self._window_manager,
                                          world,
                                          ca.PersonnelHandler.NPCs)

        self._window_manager.set_menu_response('Which Template Group',
                                                'dudes')
        pc_handler = ca.PersonnelHandler(self._window_manager,
                                         world,
                                         ca.PersonnelHandler.PCs)

        # PersonnelHandler.NPC_joins_monsters - not an NPC #

        #if ARGS.verbose:
        #    print('\n----------- NPC_joins_monsters - not an NPC -----------\n')

        self._window_manager.reset_error_state()

        pc_handler.set_viewing_index(pc_manny_index)
        fighter = pc_handler.get_obj_from_index()
        self._window_manager.expect_error(['"Manny" not an NPC'])

        self._window_manager.set_menu_response('Join Which Fight', 'horsemen')
        pc_handler.NPC_joins_monsters()

        assert(self._window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # PersonnelHandler.NPC_joins_monsters - works #

        #if ARGS.verbose:
        #    print('\n----------- NPC_joins_monsters - works -----------\n')

        self._window_manager.reset_error_state()

        npc_handler.set_viewing_index(groucho_index)
        fighter = npc_handler.get_obj_from_index()
        assert fighter.name == 'Groucho'

        self._window_manager.set_menu_response('Join Which Fight', 'horsemen')
        npc_handler.NPC_joins_monsters()

        source_char = world.get_creature_details('Groucho', 'NPCs')
        dest_char = world.get_creature_details('Groucho', 'horsemen')
        assert self._are_equal(source_char, dest_char)

        # PersonnelHandler.NPC_joins_monsters - NPC already in fight #

        #if ARGS.verbose:
        #    print('\n--- NPC_joins_monsters - NPC already with monster ---\n')

        npc_handler.set_viewing_index(groucho_index)
        fighter = npc_handler.get_obj_from_index()
        assert fighter.name == 'Groucho'

        self._window_manager.set_menu_response('Join Which Fight', 'horsemen')
        self._window_manager.expect_error(
                ['"Groucho" already in fight "horsemen"'])

        npc_handler.NPC_joins_monsters()

        assert(self._window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # PersonnelHandler.NPC_joins_PCs -- not a PC #

        #if ARGS.verbose:
        #    print('\n----------- NPC_joins_PCs - not a PC -----------\n')

        pc_handler.set_viewing_index(pc_manny_index)
        fighter = pc_handler.get_obj_from_index()
        assert fighter.name == 'Manny'

        self._window_manager.expect_error(['"Manny" not an NPC'])

        pc_handler.NPC_joins_monsters()

        assert(self._window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        # PersonnelHandler.NPC_joins_PCs -- works #

        #if ARGS.verbose:
        #    print('\n----------- NPC_joins_PCs - works -----------\n')

        self._window_manager.reset_error_state()

        # Doing zeppo so he gets put at the end of the alphabetized PC list
        # to make the next test work.
        npc_handler.set_viewing_index(zeppo_index)
        fighter = npc_handler.get_obj_from_index()
        assert fighter.name == 'Zeppo'

        npc_handler.NPC_joins_PCs()

        source_char = world.get_creature_details('Zeppo', 'NPCs')
        dest_char = world.get_creature_details('Zeppo', 'PCs')
        assert self._are_equal(source_char, dest_char)

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

        # self._window_manager.expect_error(['"Zeppo" already a PC'])

        # npc_handler.NPC_joins_monsters()

        # assert(self._window_manager.error_state ==
        #                            MockWindowManager.FOUND_EXPECTED_ERROR)

    def test_new_fight_new_creatures(self):
        '''
        Basic test
        '''
        # CREATE FIGHT -- WORKING #

        #if ARGS.verbose:
        #    print('\n=== test_new_fight_new_creatures ===\n')

        world_dict = copy.deepcopy(self.base_world_dict)
        world_data = WorldData(world_dict)
        mock_program = MockProgram()
        world = ca.World('internal source file',
                         world_data,
                         self._ruleset,
                         mock_program,
                         self._window_manager,
                         save_snapshot=False
                         )

        self._window_manager.clear_menu_responses()
        self._window_manager.set_menu_response('New or Pre-Existing', 'new')
        self._window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self._window_manager.set_input_box_response('New Fight Name',
                                                     'test_new_fight')
        self._window_manager.set_menu_response('Monster', 'VodouCleric')
        self._window_manager.set_input_box_response('Monster Name', 'Horatio')
        self._window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self._window_manager,
                                           world,
                                           ca.PersonnelHandler.MONSTERs)

        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        fights = world.get_fights()
        assert 'test_new_fight' in fights  # verify that fight  exists
        if 'test_new_fight' in fights:
            creatures = world.get_creature_details_list('test_new_fight')
            #if ARGS.verbose:
            #    print('Expect: Room, Horatio:')
            #    PP.pprint(creatures)
            # The 'creatures' should be '<< ROOM >>', '1 - Horatio'
            assert '1 - Horatio' in creatures

        # FIGHT ALREADY EXISTS #

        #if ARGS.verbose:
        #    print('\n--- Test: Fight Already Exists ---\n')

        self._window_manager.reset_error_state()
        self._window_manager.clear_menu_responses()
        self._window_manager.set_menu_response('New or Pre-Existing', 'new')
        self._window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        # This one should error out
        self._window_manager.set_input_box_response('New Fight Name',
                                                     'test_new_fight')
        # This one should work
        self._window_manager.set_input_box_response('New Fight Name', 'foo')

        self._window_manager.expect_error(
                ['Fight name "test_new_fight" already exists'])

        # These are just so that the test finishes.
        self._window_manager.set_menu_response('Monster', 'VodouCleric')
        self._window_manager.set_input_box_response('Monster Name', 'Horatio')
        self._window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self._window_manager,
                                           world,
                                           ca.PersonnelHandler.MONSTERs)

        assert(self._window_manager.error_state ==
               MockWindowManager.FOUND_EXPECTED_ERROR)

        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        # ADD A CREATURE, DELETE A MONSTER -- WORKS #

        #if ARGS.verbose:
        #    print('\n--- Test: Add and Delete Monster ---\n')

        self._window_manager.clear_menu_responses()
        self._window_manager.set_menu_response('New or Pre-Existing',
                                                'existing')
        self._window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self._window_manager.set_menu_response('To Which Group',
                                                'test_new_fight')

        self._window_manager.set_menu_response('Monster', 'VodouCleric')
        self._window_manager.set_input_box_response('Monster Name', 'Ophelia')

        build_fight = TestPersonnelHandler(self._window_manager,
                                           world,
                                           ca.PersonnelHandler.MONSTERs)

        build_fight.set_command_ribbon_input('a')   # Add Ophelia

        # The 'creatures' should be '<< ROOM >>', '1 - Horatio', '2 - Ophelia'
        # Delete Horatio

        build_fight.set_command_ribbon_input(curses.KEY_UP)
        build_fight.set_command_ribbon_input('d')   # Delete Horatio
        self._window_manager.set_menu_response(
                'Delete "1 - Horatio" ARE YOU SURE?', 'yes')
        # finish up the test

        self._window_manager.set_menu_response('What Next', 'quit')
        build_fight.set_command_ribbon_input('q')   # Quit

        build_fight.handle_user_input_until_done()

        fights = world.get_fights()
        assert 'test_new_fight' in fights  # verify that fight  exists
        if 'test_new_fight' in fights:
            creatures = world.get_creature_details_list('test_new_fight')
            assert '1 - Horatio' not in creatures
            assert '2 - Ophelia' in creatures

        # ADD PCs -- WORKS #

        #if ARGS.verbose:
        #    print('\n--- Test: Add PCs ---\n')

        group = 'PCs'
        self._window_manager.clear_menu_responses()
        self._window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self._window_manager.set_menu_response('Monster', 'VodouCleric')
        self._window_manager.set_input_box_response('Monster Name', 'Skippy')
        self._window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self._window_manager,
                                           world,
                                           ca.PersonnelHandler.PCs)

        build_fight.set_command_ribbon_input('a')
        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        creatures = world.get_creature_details_list(group)
        assert 'Skippy' in creatures

        # ADD NPCs #

        #if ARGS.verbose:
        #    print('\n--- Test: Add NPCs ---\n')

        group = 'NPCs'
        self._window_manager.clear_menu_responses()
        self._window_manager.set_menu_response('Which Template Group',
                                                'Arena Combat')
        self._window_manager.set_menu_response('Monster', 'VodouCleric')
        self._window_manager.set_input_box_response('Monster Name', 'Stinky')
        self._window_manager.set_menu_response('What Next', 'quit')

        build_fight = TestPersonnelHandler(self._window_manager,
                                           world,
                                           ca.PersonnelHandler.NPCs)

        build_fight.set_command_ribbon_input('a')
        build_fight.set_command_ribbon_input('q')
        build_fight.handle_user_input_until_done()

        creatures = world.get_creature_details_list(group)
        assert 'Stinky' in creatures

    def test_containers(self):
        '''
        Basic test
        '''
        # CREATE FIGHT -- WORKING #

        #if ARGS.verbose:
        #    print('\n=== test_containers ===\n')

        mock_fight_handler = MockFightHandler()

        fighter_dict = copy.deepcopy(self._thief_fighter)
        # NOTE: containers are always 1st (that way the indexes don't get
        # messed up and I don't have to go around recalculating for the
        # tests.
        fighter_dict['stuff'] =  [
                {"name": "Container 11", "type": {"container": 1}, "count": 1, "notes": "",
                 "owners": None, "stuff": [
                    {"name": "Container 22", "type": {"container": 1}, "count": 1, "notes": "",
                     "owners": None, "stuff": [
                        {"name": "Random Thing 31", "type": {"misc": 1}, "count": 1, "notes": "",
                         "owners": None},
                     ]},
                    {"name": "Random Thing 22", "type": {"misc": 1}, "count": 1, "notes": "",
                     "owners": None},
                 ]},
                 {"name": "Random Thing 12", "type": {"misc": 1}, "count": 1, "notes": "",
                  "owners": None},
                 {"name": "Random Thing 13", "type": {"misc": 1}, "count": 1, "notes": "",
                  "owners": None},
                 ]
        fighter = ca_fighter.Fighter(
                'Thief',
                'group',
                fighter_dict,
                self._ruleset,
                self._window_manager)

        # just checking starting conditions
        # verify: 3 things at top level, 2 things at 2nd level, 1 thing at 3rd
        # 3, 2, 1

        container = fighter.equipment.get_container([])
        assert len(container) == 3
        container = fighter.equipment.get_container([0])
        assert len(container) == 2
        container = fighter.equipment.get_container([0, 0])
        assert len(container) == 1

        # TEST MOVE - move something from level 1 to level 2
        # verify: top level: 2 things, 2nd level: 3 things, 3rd level: 1 thing

        # index is arbitrary but not '1' since that's a container -- nothing
        # wrong with moving a container but that's not what we're testing.
        container = fighter.equipment.get_container([])
        index = 2
        item = container[index]
        self._ruleset.do_action(
                fighter,
                {'action-name': 'move-between-container',
                 'item-index': index,
                 'item-name': item['name'],
                 'destination-index': [0],
                 },
                mock_fight_handler)
        container = fighter.equipment.get_container([])
        assert len(container) == 2
        container = fighter.equipment.get_container([0])
        assert len(container) == 3
        container = fighter.equipment.get_container([0, 0])
        assert len(container) == 1

        # 2, 3, 1
        # TEST OPEN - go to level 2 container

        self._ruleset.do_action(
                fighter,
                {'action-name': 'open-container', 'container-index': 0},
                mock_fight_handler)
        # move a couple things to level 3
        for index in [2, 1]:
            container = fighter.equipment.get_container([0])
            item = container[index]
            self._ruleset.do_action(
                    fighter,
                    {'action-name': 'move-between-container',
                     'item-index': index,
                     'item-name': item['name'],
                     'destination-index': [0, 0],
                     },
                    mock_fight_handler)

        # verify: 2, 1, 3
        container = fighter.equipment.get_container([])
        assert len(container) == 2
        container = fighter.equipment.get_container([0])
        assert len(container) == 1
        container = fighter.equipment.get_container([0, 0])
        assert len(container) == 3

        # 2, 1, 3
        # TEST 2 LEVELS - go to level 3 container

        self._ruleset.do_action(
                fighter,
                {'action-name': 'open-container', 'container-index': 0},
                mock_fight_handler)

        # move one thing back to level 1
        container = fighter.equipment.get_container([0, 0])
        index = 0
        item = container[index]
        self._ruleset.do_action(
                fighter,
                {'action-name': 'move-between-container',
                 'item-index': index,
                 'item-name': item['name'],
                 'destination-index': [],
                 },
                mock_fight_handler)

        # verify: 3, 1, 2
        container = fighter.equipment.get_container([])
        assert len(container) == 3
        container = fighter.equipment.get_container([0])
        assert len(container) == 1
        container = fighter.equipment.get_container([0, 0])
        assert len(container) == 2

        # 3, 1, 2
        # TEST CLOSE - Go back to top, move something to level 3

        # go back to level 1 by closing 2 containers
        self._ruleset.do_action(
                fighter,
                {'action-name': 'close-container'},
                mock_fight_handler)
        self._ruleset.do_action(
                fighter,
                {'action-name': 'close-container'},
                mock_fight_handler)

        # move one thing back to level 3
        container = fighter.equipment.get_container([0, 0])
        index = 1
        item = container[index]
        self._ruleset.do_action(
                fighter,
                {'action-name': 'move-between-container',
                 'item-index': index,
                 'item-name': item['name'],
                 'destination-index': [0,0],
                 },
                mock_fight_handler)

        # verify: 2, 1, 3
        container = fighter.equipment.get_container([])
        assert len(container) == 2
        container = fighter.equipment.get_container([0])
        assert len(container) == 1
        container = fighter.equipment.get_container([0, 0])
        assert len(container) == 3


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

