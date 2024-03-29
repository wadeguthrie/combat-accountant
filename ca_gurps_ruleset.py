#! /usr/bin/python

import copy
import curses
import pprint
import random
import re

import ca_debug
import ca_fighter
import ca_equipment
import ca_gcs_import
import ca_gui
import ca_json
import ca_ruleset
import ca_timers

# The JSON source to a "ranged weapon", "swung weapon", "thrust weapon",
#   "natural weapon", "armor" or "natural armor" is expected to look like this:
#
# {
#      "name": "<name of the item>"
#      "count": <number of items>,
#      "notes": "<whatever>",
#      "owners": [ <list of strings> ],
#      "type": { <type> : <value> },
# }
#
# <type> is one of:
#   o armor
#   o natural armor
#       "type": { "armor":         { "dr": <int: damage resistance> } },
#       "type": { "natural armor": { "dr": <int: damage resistance> } },
#
#       neither of these have extra entries in the object dict
#
#   o thrown weapon -- TBS
#   o shield -- TBS
#
#   o swung weapon
#   o thrust weapon
#       "type": {"swung weapon": {<skill>, <damage>}
#       "type": {"thrust weapon": {<skill>, <damage>}
#
#           <skill> (see below)
#           <damage> is "damage": { "type": <damage type>,
#                                   "plus": <int: plus value>,
#                                   "st": <st type> }
#               <damage type> is one of "cr", "imp", ...
#               <st type> is one of "sw" (for swing damage),
#                                   "thr" (for thrust damage)
#       these require an additional entry in the dict:
#           "parry": <int: plus to parry due to this weapon>
#
#   o ranged weapon
#       "type": {"ranged weapon": {<skill>, <damage>} }
#
#           <skill> (see below)
#           <damaage> is "damaage": { "dice": {"num_dice": <num dice>,
#                                              "plus": <plus>,
#                                              "type": <type>} }
#               <num dice> is number of 6-sided dice to roll
#               <plus> is value added to die roll
#               <type> is "pi", "pi+", "imp", etc.
#
#       this requires the following additional entries:
#
#           "acc": <int: acc> -- GURPS acc value
#           "reload": <int: reload> -- GURPS reload value (rounds to reload)
#           "bulk": <int: bulk> -- GURPS bulk value
#           "reload_type": <int: reload type>
#               0 = Equipment.RELOAD_NONE # for a thrown dagger or suriken,
#                                           no reloads
#               1 = Equipment.RELOAD_ONE  # for a shotgun or grenade launcher,
#                                           loaded one shell or grenade at a
#                                           time
#               2 = Equipment.RELOAD_CLIP # for weapons that are reloaded one
#                                           magazine at a time
#           "clip": <clip> -- externally loaded magazine containing shots
#               <clip> is { "type": { "misc": 1 },
#                           "name": <string>,
#                           "shots": <int: shots in this magazine>,
#                           "shots_left": <int: shots remaining before empty> }
#
#           "ammo": <ammo> -- describes a magazine
#               <ammo> is { "count": <int: ignored>,
#                           "name": <name of external object to find / load>,
#                           "shots": <int: number of shots in a magazine> }
#           "shots_per_round": <int: rate of fire of machine gun> -- optional
#           "pellets_per_shot": <int: pellets in shotgun shell> -- optional
#
#   o natural weapon
#       "type": {"natural weapon": {<skill>, <damage>}
#
#           <skill> (see below)
#           <damaage> (see damage from 'ranged weapon', 'thrust weapon', or
#                      'swung weapon', as appropriate)
#
#   <skill> is "skill": {<skill name>: <skill minus>, ... }
#       <skill name> is a list of skills that may apply to using this
#           weapon.
#       <skill minus> is the penalty for using this skill if you're not
#           using the weapon's primary skill.  This value is 0 for the
#           weapon's primary skill.


class GurpsRuleset(ca_ruleset.Ruleset):
    '''
    GURPS is a trademark of Steve Jackson Games, and its rules and art are
    copyrighted by Steve Jackson Games. All rights are reserved by Steve
    Jackson Games. This game aid is the original creation of Wade Guthrie and
    is released for free distribution, and not for resale, under the
    permissions granted in the
    <a href="http://www.sjgames.com/general/online_policy.html">Steve Jackson
    Games Online Policy</a>.

    Steve Jackson Games appears to allow the creation of a "Game Aid" which is
    PC-based and not a phone or tablet app.  This is done in
    http://sjgames.com/general/online_policy.html. The relevant text is as
    follows:

        "If you mean [by 'So, does that mean I can...Create a character
        generator or other game aid?] a "game aid" or "player aid" program,
        yes, you certainly can, if it's for a PC-type computer and you
        include the appropriate notices. We currently do not allow "apps"
        for mobile devices to be created using our content or trademarks. [...]

        We want to ENCOURAGE our fans to create these programs, share them
        with the community, and have fun doing it. If you want to charge money
        for a game aid based on our work, the Online Policy does NOT apply
        . . . you must either get a license from us, or sell us the game aid
        for distribution as a regular product, and either way we'll hold you
        to professional standards. Email licensing@sjgames.com with a formal
        proposal letter."

    So, we're not charging, we're not putting this on a mobile device, and the
    appropriate notices are included above, so we _should_ be good.  I've
    included the notice at the beginning of this class because it is my intent
    to compartmentalize all GURPS-specific stuff in this class.  The rest of
    this program is (supposed to be) generic.

    This is a place for all of the ruleset (GURPS, in this case) specific
    stuff.

    In addition to what's required by 'Ruleset', each character's dict is
    expected to look like this:
    {
        'aim': {'rounds': <number>, 'braced': True | False}
        'shock': <number, 0 for 'None'>
        'dodge' : <final dodge value (including things like 'Enhanced Dodge'>
        'skills': {<skill name> : <final skill value>, ...}
        'current': {<attribute name> : <final attribute value>, ...}
            These are: 'fp', 'hp', 'iq', 'ht', 'st', 'dx', and 'basic-speed'
        'permanent': {<same attributes as in 'current'>}
    }

    Weapon looks like:
    {
        TBS
        'type': <thrust weapon> | <swung weapon> | <thrown weapon> |
                <ranged weapon> | <shield>
        'parry': <plus to parry>
    }

    'Final' values include any plusses due to advantages or skills or
    whaterver.  This code doesn't calculate any of the derived values.  This
    may change in the future, however.
    '''

    checked_for_unconscious_string = 'Checked this round for unconsciousness'

    damage_mult = {'burn': 1.0, 'cor': 1.0, 'cr':  1.0, 'cut': 1.5,
                   'imp':  2.0, 'pi-': 0.5, 'pi':  1.0, 'pi+': 1.5,
                   'pi++': 2.0, 'tbb': 1.0, 'tox': 1.0}
    melee_damage = {1:  {'thr': {'num_dice': 1, 'plus': -6},
                         'sw':  {'num_dice': 1, 'plus': -5}},
                    2:  {'thr': {'num_dice': 1, 'plus': -6},
                         'sw':  {'num_dice': 1, 'plus': -5}},
                    3:  {'thr': {'num_dice': 1, 'plus': -5},
                         'sw':  {'num_dice': 1, 'plus': -4}},
                    4:  {'thr': {'num_dice': 1, 'plus': -5},
                         'sw':  {'num_dice': 1, 'plus': -4}},
                    5:  {'thr': {'num_dice': 1, 'plus': -4},
                         'sw':  {'num_dice': 1, 'plus': -3}},
                    6:  {'thr': {'num_dice': 1, 'plus': -4},
                         'sw':  {'num_dice': 1, 'plus': -3}},
                    7:  {'thr': {'num_dice': 1, 'plus': -3},
                         'sw':  {'num_dice': 1, 'plus': -2}},
                    8:  {'thr': {'num_dice': 1, 'plus': -3},
                         'sw':  {'num_dice': 1, 'plus': -2}},
                    9:  {'thr': {'num_dice': 1, 'plus': -2},
                         'sw':  {'num_dice': 1, 'plus': -1}},
                    10: {'thr': {'num_dice': 1, 'plus': -2},
                         'sw':  {'num_dice': 1, 'plus': 0}},
                    11: {'thr': {'num_dice': 1, 'plus': -1},
                         'sw':  {'num_dice': 1, 'plus': +1}},
                    12: {'thr': {'num_dice': 1, 'plus': -1},
                         'sw':  {'num_dice': 1, 'plus': +2}},
                    13: {'thr': {'num_dice': 1, 'plus': 0},
                         'sw':  {'num_dice': 2, 'plus': -1}},
                    14: {'thr': {'num_dice': 1, 'plus': 0},
                         'sw':  {'num_dice': 2, 'plus': 0}},
                    15: {'thr': {'num_dice': 1, 'plus': +1},
                         'sw':  {'num_dice': 2, 'plus': +1}},
                    16: {'thr': {'num_dice': 1, 'plus': +1},
                         'sw':  {'num_dice': 2, 'plus': +2}},
                    17: {'thr': {'num_dice': 1, 'plus': +2},
                         'sw':  {'num_dice': 3, 'plus': -1}},
                    18: {'thr': {'num_dice': 1, 'plus': +2},
                         'sw':  {'num_dice': 3, 'plus': 0}},
                    19: {'thr': {'num_dice': 2, 'plus': -1},
                         'sw':  {'num_dice': 3, 'plus': +1}},
                    20: {'thr': {'num_dice': 2, 'plus': -1},
                         'sw':  {'num_dice': 3, 'plus': +2}},
                    21: {'thr': {'num_dice': 2, 'plus': 0},
                         'sw':  {'num_dice': 4, 'plus': -1}},
                    22: {'thr': {'num_dice': 2, 'plus': 0},
                         'sw':  {'num_dice': 4, 'plus': 0}},
                    23: {'thr': {'num_dice': 2, 'plus': +1},
                         'sw':  {'num_dice': 4, 'plus': +1}},
                    24: {'thr': {'num_dice': 2, 'plus': +1},
                         'sw':  {'num_dice': 4, 'plus': +2}},
                    25: {'thr': {'num_dice': 2, 'plus': +2},
                         'sw':  {'num_dice': 5, 'plus': -1}}
                    }

    # These are specific to the Persephone version of the GURPS ruleset

    abilities = {}
    # skills:
    #   'name': {'ask': 'number' | 'string' }
    #           {'value': value}

    spells = {}
    # Spells:
    #   "range" not in the .spl file#
    #   duration:0 means instant
    #   save:  # NOTE: need to handle "wi-1"

    # Alphabetized for conevenience
    # "Agonize": {
    #   "cost": 8, <-- None means 'ask
    #   "notes": "M40, HT negates", <-- at least give book reference
    #                                   M40 means page 40 in GURPS
    #                                   Magic
    #   "maintain": 6,
    #   "casting time": 1, <-- None or 0 means 'ask
    #   "duration": 60, <-- None means 'ask', 0 means 'Instant'
    # },

    # 'range': block, missile, area, melee.
    # specially mark those with 1 or 2 second cast time
    # 'save': 'wi', 'ht', xxx, (cast a spell dialog needs to show this)

    # Posture: B551; 'attack' is melee, 'target' is ranged
    posture = {
        'standing':  {'attack':  0, 'defense':  0, 'target':  0},
        'crouching': {'attack': -2, 'defense':  0, 'target': -2},
        'kneeling':  {'attack': -2, 'defense': -2, 'target': -2},
        'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        'sitting':   {'attack': -2, 'defense': -2, 'target': -2},
        'lying':     {'attack': -4, 'defense': -3, 'target': -2},
    }

    # This is for the Persephone version of the GURPS ruleset.  It's only for
    # color and does not deal with armoring parts of the body or blowthrough
    # or anything that goes with the non-Lite version of GURPS.
    hit_location_table = {3:  'head',
                          4:  'head',
                          5:  'face',
                          6:  'right thigh',
                          7:  'right calf',
                          8:  'right arm',
                          9:  'stomach',
                          10: 'chest/back',
                          11: 'groin/hip/butt',
                          12: 'left arm',
                          13: 'left calf',
                          14: 'left thigh',
                          15: 'hand',
                          16: 'foot',
                          17: 'neck',
                          18: 'neck'}

    all_unarmed_skills = ['Brawling', 'Boxing', 'Karate']

    (MAJOR_WOUND_SUCCESS,
     MAJOR_WOUND_SIMPLE_FAIL,
     MAJOR_WOUND_BAD_FAIL) = list(range(3))

    (ALL_OUT_DOUBLE_ATTACK,
     ALL_OUT_STRONG_ATTACK,
     ALL_OUT_SUPPRESSION_FIRE,
     ALL_OUT_FEINT,
     ALL_OUT_RANGED_DETERMINED_ATTACK,
     ALL_OUT_MELEE_DETERMINED_ATTACK) = list(range(6))

    all_out_attack_option_strings = {
        ALL_OUT_DOUBLE_ATTACK:              'Double Attack',
        ALL_OUT_STRONG_ATTACK:              'Strong Attack',
        ALL_OUT_SUPPRESSION_FIRE:           'Suppression Fire',
        ALL_OUT_FEINT:                      'Feint',
        ALL_OUT_RANGED_DETERMINED_ATTACK:   'Determined Attack (ranged)',
        ALL_OUT_MELEE_DETERMINED_ATTACK:    'Determined Attack (melee)'}

    def __init__(self,
                 window_manager  # GmWindowManager object for menus and errors
                 ):
        super(GurpsRuleset, self).__init__(window_manager)

        # Read the skills, spells, and attributes from the file

        self.__gurps_info = ca_json.GmJson('gurps_info.json')
        if self.__gurps_info.open_read_close():
            GurpsRuleset.spells = self.__gurps_info.read_data['spells']
            GurpsRuleset.abilities = self.__gurps_info.read_data['abilities']

        # If the fighter does one of these things and the turn is over, he
        # clearly hasn't forgotten to do something.  Other actions are passive
        # and their existence doesn't mean that the fighter has actually tried
        # to do anything.

        self.active_actions.extend([
            'aim',             'all-out-attack',  'attack',
            'cast-spell',      'change-posture',  'concentrate',
            'defend',          'doff-armor',      'don-armor',
            'draw-weapon',     'evaluate',        'feint',
            'holster-weapon',  'maintain-spell',  'move',
            'move-and-attack', 'nothing',         'reload',
            'stun',            'use-item',        'user-defined'
        ])

    # Context manager stuff deals with gurps_info.json, a file that contains
    # spells, skills, advantages, etc.  It's in a context manager so that we
    # can import additional information into these fields from GURPS Character
    # sheet and the new information can be saved on exit.

    def __enter__(self):
        super(GurpsRuleset, self).__enter__()
        return self

    def __exit__ (self, exception_type, exception_value, exception_traceback):
        super(GurpsRuleset, self).__exit__(exception_type,
                                           exception_value,
                                           exception_traceback)
        if exception_type is IOError:
            print('IOError: %r' % exception_type)
            print('EXCEPTION val: %s' % exception_value)
            print('Traceback: %r' % exception_traceback)
        elif exception_type is not None:
            print('EXCEPTION type: %r' % exception_type)
            print('EXCEPTION val: %s' % exception_value)
            print('Traceback: %r' % exception_traceback)
        if self.__gurps_info is not None:
            self.__gurps_info.open_write_close(self.__gurps_info.write_data)
        return True

    #
    # Public Methods
    #

    @staticmethod
    def show_spells(window_manager  # ca_gui.CaWindowManager object
                    ):
                        # Output: recepticle for character
                        # detail.
                        # [[{'text','mode'},...],  # line 0
                        #  [...],               ]  # line 1...
        '''
        Displays the spells in a window

        Returns nothing.
        '''

        spell_info = []

        for spell_name in sorted(GurpsRuleset.spells.keys()):
            spell = GurpsRuleset.spells[spell_name]

            # TODO (now): should be an option
            # Highlight the spells that a bad guy might want to cast during
            # battle.
            mode = (curses.color_pair(ca_gui.GmWindowManager.YELLOW_BLACK)
                    if ((spell['casting time'] is None or
                         spell['casting time'] <= 2) and
                        spell['range'] != 'melee')
                    else curses.A_NORMAL)

            # Top line

            line = [{'text': '%s' % spell_name, 'mode': mode | curses.A_UNDERLINE}]

            texts = ['; %s ' % spell['range']]
            if 'save' in spell and len(spell['save']) > 0:
                texts.append('; resisted by ')
                texts.append(', '.join(spell['save']))

            line.append({'text': ''.join(texts), 'mode': mode})
            spell_info.append(line)

            # Next line

            texts = ['  cost: ']
            if spell['cost'] is None:
                texts.append('special')
            else:
                texts.append('%d' % spell['cost'])

            texts.append(', maintain: ')
            if spell['maintain'] is None:
                texts.append('special (or none)')
            else:
                texts.append('%d' % spell['maintain'])

            texts.append(', casting time: ')
            if spell['casting time'] is None:
                texts.append('special')
            else:
                texts.append('%d second(s)' % spell['casting time'])

            texts.append(', duration: ')
            if spell['duration'] is None:
                texts.append('special')
            elif spell['duration'] == 0:
                texts.append('instantaneous/permanent')
            elif spell['duration'] < 60:
                texts.append('%d second(s)' % spell['duration'])
            elif spell['duration'] < 3660:
                texts.append('%d minute(s)' % (spell['duration'] / 60))
            elif spell['duration'] < 86400:
                texts.append('%d hour(s)' % (spell['duration'] / 3660))
            else:
                texts.append('%d day(s)' % (spell['duration'] / 86400))
            spell_info.append([{'text': ''.join(texts), 'mode': mode}])

            # Notes

            texts = ['  %s' % spell['notes']]
            spell_info.append([{'text': ''.join(texts), 'mode': mode}])

        window_manager.display_window('Spells', spell_info)

    def add_equipment_options(self,
                              fighter   # Fighter object: person being equipped
                              ):
        '''
        Builds a list of ruleset-specific menu options for equipping a
        character.  One example is recharging powerstones.

        Returns array of menu entries.
        '''

        result = []

        for index, item in enumerate(fighter.rawdata['stuff']):
            if ('mana' in item and 'max mana' in item and
                    item['mana'] < item['max mana']):
                result.extend([
                    ('Charge %s (%d/%d)' % (item['name'],
                                            item['mana'],
                                            item['max mana']),
                        {'doit': self.__charge_powerstone,
                         'param': {'fighter': fighter, 'index': index}})
                ])
        return result


    def can_finish_turn(self,
                        fighter,        # Fighter object
                        fight_handler   # FightHandler object
                        ):
        '''
        If a Fighter has done something this turn, we can move to the next
        Fighter.  Otherwise, the Fighter should do something before we go to
        the next Fighter.

        Returns: <bool> telling the caller whether this Fighter needs to do
        something before we move on.
        '''

        for action in fighter.rawdata['actions_this_turn']:
            if action in self.active_actions:
                return True

        if not fighter.is_conscious():
            return True

        if fighter.timers.is_busy():
            return True

        if fight_handler.is_fighter_holding_init(fighter.name,
                                                 fighter.group):
            return True

        return False

    def damage_to_string(self,
                         damages  # list of dict -- returned by 'get_damage'.
                                  # The dict looks like:
                                  #
                                  # {'attack_type': <string> (e.g., 'sw')
                                  #  'num_dice': <int>
                                  #  'plus': <int>
                                  #  'damage_type': <string> (eg, 'crushing')}
                         ):
        '''
        Converts array of dicts returned by get_damage into a string.

        Returns the string.
        '''
        results = []
        for damage in damages:
            string = []
            if damage['attack_type'] is not None:
                string.append('%s: ' % damage['attack_type'])
            string.append('%dd%+d ' % (damage['num_dice'], damage['plus']))
            string.append('(%s)' % damage['damage_type'])
            if 'notes' in damage and damage['notes'] is not None:
                string.append(', %s' % damage['notes'])
            results.append(''.join(string))

        return ', '.join(results)

    def do_save_on_exit(self):
        '''
        Causes the local copy of the Game File data to be written back to the
        file when the program ends.

        Returns nothing.
        '''
        super(GurpsRuleset, self).do_save_on_exit()

        # TODO (eventually): only set the following if BOTH do_save_on_exit
        #   is called _and_ we've added data with an import.
        self.__gurps_info.write_data = self.__gurps_info.read_data

    def does_weapon_use_unarmed_skills(self,
                                       weapon  # Weapon object
                                       ):
        '''
        Determines whether this weapon (which may be None) uses the unarmed
        combat skills.  That's basically a blackjack or brass knuckles but
        there may be more.

        Returns True if this weapon supports unarmed combat (like brass
        knuckles), False otherwise.
        '''

        if weapon is None:
            return True

        modes = weapon.get_attack_modes()
        for mode in modes:
            for skill in weapon.rawdata['type'][mode]['skill'].keys():
                if skill in GurpsRuleset.all_unarmed_skills:
                    return True

        return False

    def dont_save_on_exit(self):
        '''
        Causes the local copy of the Game File data NOT to be written back
        to the file when the program ends.

        Returns nothing.
        '''
        super(GurpsRuleset, self).dont_save_on_exit()
        self.__gurps_info.open_read_close()
        self.__gurps_info.write_data = None

    def end_turn(self,
                 fighter,       # Fighter object
                 fight_handler  # FightHandler object
                 ):
        '''
        Performs all of the stuff required for a Fighter to end his/her
        turn.  Does all the consciousness/death checks, etc.

        Returns: nothing
        '''
        fighter.rawdata['shock'] = 0

        if fighter.rawdata['stunned'] and not fight_handler.world.playing_back:
            stunned_menu = [
                (('Succeeded (roll <= HT (%d))' %
                    fighter.rawdata['current']['ht']), True),
                ('Missed roll', False)]
            recovered_from_stun, ignore = self._window_manager.menu(
                        '%s Stunned (B420): Roll <= HT to recover' %
                        fighter.name,
                        stunned_menu)
            if recovered_from_stun:
                self.do_action(fighter,
                               {'action-name': 'stun', 'stun': False},
                               fight_handler)

    def get_action_menu(self,
                        fighter,    # Fighter object
                        opponent    # Fighter object
                        ):
        '''
        Builds a list of all of the things that this fighter can do this
        round.  This list will be fed to GmWindowManager.menu(), so each
        element is a tuple of

        1) the string to be displayed
        2) a dict that contains one or more of

            'text' - text to go in a timer to show what the Fighter is doing
            'action' - an action to be sent to the ruleset
            'menu' - a menu to be recursively called

        NOTE: all menu items should end, ultimately, in an 'action' because
        then the activity will be logged in the history and can be played-back
        if there's a bug to be reported.

        Returns the menu (i.e., the list)
        '''

        action_menu = []

        if fighter.rawdata['stunned']:
            action_menu.append(
                ('do nothing (stunned)', {'text': ['Do Nothing (Stunned)',
                                                   ' Defense: any @-4',
                                                   ' Move: none'],
                                          'action': {'action-name': 'nothing'}}
                 )
            )
            return action_menu  # No other actions permitted

        # Figure out who we are and what we're holding.

        holding = fighter.what_are_we_holding()

        # Posture SUB-menu

        posture_menu = []
        for posture in GurpsRuleset.posture.keys():
            if posture != fighter.rawdata['posture']:
                posture_menu.append((posture,
                                     {'action':
                                         {'action-name': 'change-posture',
                                          'posture': posture}}))

        # Build the action_menu.  Alphabetical order.  Only allow the things
        # the fighter can do based on zis current situation.

        # ATTACK #

        if (holding['melee'] or holding['loaded_ranged'] or
                holding['natural_weapon'] or holding['non_natural_weapon']):
            action_menu.extend([
                ('attack, all out', {'action':
                                     {'action-name': 'all-out-attack'}})
            ])

        if holding['loaded_ranged']:
            # Aim
            #
            # Ask if we're bracing if this is the first round of aiming
            # B364 (NOTE: Combat Lite on B234 doesn't mention bracing).
            if fighter.rawdata['aim']['rounds'] == 0:
                brace_menu = [
                    ('Bracing (B364)', {'action': {'action-name': 'aim',
                                                   'braced': True}}),
                    ('Not Bracing', {'action': {'action-name': 'aim',
                                                'braced': False}})
                ]
                action_menu.append(('Aim (B324, B364)',
                                    {'menu': brace_menu}))
            else:
                action_menu.append(('Aim (B324, B364)',
                                    {'action': {'action-name': 'aim',
                                                'braced': False}}))

        action_menu.extend([
            ('posture (B551)',         {'menu': posture_menu}),
            ('Concentrate (B366)',     {'action':
                                        {'action-name': 'concentrate'}}),
            ('Defense, all out',       {'action':
                                        {'action-name': 'defend'}}),
        ])

        # Spell casters.

        if 'spells' in fighter.rawdata:

            # Build the 'Cast' menu

            spell_menu = []
            for index, spell in enumerate(fighter.rawdata['spells']):
                menu_item = self.__build_cast_spell_menu_item(spell, index)
                if menu_item is not None:
                    spell_menu.append(menu_item)
            spell_menu = sorted(spell_menu, key=lambda x: x[0].upper())
            action_menu.append(('cast Spell', {'menu': spell_menu}))

            # Build the 'Maintain' menu for currently expiring spells

            # What spells just expired (they're in the 'just fired' timers)
            maintain_spell_menu = []
            for timer in fighter.timers.get_just_fired():
                # ignore the timer if it's not for a spell
                if 'data' not in timer.rawdata:
                    continue
                if 'spell' not in timer.rawdata['data']:
                    continue
                spell_name = timer.rawdata['data']['spell']['name']

                # ignore the spell if there's no maintainence cost
                spell_data = GurpsRuleset.spells[spell_name]
                if 'maintain' not in spell_data:
                    continue
                if spell_data['maintain'] is None:
                    # This _should_ be 'ask' but there was an error in the
                    # spell import code that said 'cannot be maintained' is
                    # None.  Sigh.
                    continue
                if spell_data['maintain'] == 0:
                    continue  # THIS means it can't be maintained

                # Build the menu item

                # Find the spell in the fighter's list
                spell_found = None
                index_found = None
                for index, spell in enumerate(fighter.rawdata['spells']):
                    if spell_name == spell['name']:
                        spell_found = spell
                        index_found = index
                        break

                if spell_found is None or index_found is None:
                    continue # Shouldn't happen; caster should know this spell

                # Build the menu item and add it to the menu
                menu_item = self.__build_cast_spell_menu_item(spell_found,
                                                              index_found,
                                                              maintain=True)
                if menu_item is not None:
                    maintain_spell_menu.append(menu_item)

            if len(maintain_spell_menu) > 0:
                action_menu.append(('maintain Spell',
                                    {'menu': maintain_spell_menu}))

        action_menu.append(('evaluate (B364)',
                            {'action': {'action-name': 'evaluate'}}))

        # Can only feint with a melee weapon
        if holding['melee']:
            action_menu.append(('feint (B365)', {'action':
                                                {'action-name': 'feint'}}))

        # FP: B426
        move = fighter.rawdata['current']['basic-move']
        no_fatigue_penalty = self.get_option('no-fatigue-penalty')
        if ((no_fatigue_penalty is None or not no_fatigue_penalty) and
                fighter.rawdata['current']['fp'] <
                    (fighter.rawdata['permanent']['fp'] / 3)):
            move_string = 'half=%d (FP:B426)' % (move/2)
        else:
            move_string = 'full=%d' % move

        if holding['melee'] or holding['loaded_ranged']:
            action_menu.extend([
                ('Move and attack (B365)',
                    {'action': {'action-name': 'move-and-attack'}}),
            ])

        action_menu.extend([
            ('move (B364) %s' % move_string,
                {'action': {'action-name': 'move'}}),
            ('nothing',
                {'action': {'action-name': 'nothing'}})
        ])

        super(GurpsRuleset, self).get_action_menu(action_menu,
                                                  fighter,
                                                  opponent)

        action_menu = sorted(action_menu, key=lambda x: x[0].upper())
        return action_menu

    def get_block_skill(self,                       # Public to aid in testing.
                        fighter,    # Fighter object
                        weapon      # Weapon object
                        ):
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully block an
               attack
            2) array of strings describing the calculations that went into
               the number
        '''
        skill = None
        if weapon is not None:
            modes = weapon.get_attack_modes()
            for mode in modes:
                if mode == 'ranged weapon' or mode == 'thrown weapon':
                    continue    # can't block with missile weapon
                skill_full = fighter.get_best_skill_for_weapon(weapon.rawdata,
                                                               mode)
                if skill_full is not None:
                    if skill is None or skill_full['value'] > skill:
                        skill = skill_full['value']

        if skill is None:
            return None, None

        block_why = []
        block_skill_modified = False

        block_skill = 3 + int(skill * 0.5)
        block_why.append('Block (B327, B375) w/%s @ (skill(%d)/2)+3 = %d' % (
            weapon.rawdata['name'], skill, block_skill))

        if fighter.rawdata['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.rawdata['advantages']:
            block_skill_modified = True
            block_why.append('  +1 due to combat reflexes (B43)')
            block_skill += 1

        posture_mods = self.get_posture_mods(fighter.rawdata['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            block_skill_modified = True
            block_skill += posture_mods['defense']
            block_why.append('  %+d due to %s posture' %
                             (posture_mods['defense'],
                              fighter.rawdata['posture']))

        if block_skill_modified:
            block_why.append('  ...for a block skill total = %d' % block_skill)

        return block_skill, block_why

    def get_creature_abilities(self):
        '''
        Returns the list of capabilities that, according to the ruleset, a
        creature can have.  See |GurpsRuleset.abilities|
        '''
        return GurpsRuleset.abilities

    def get_damage(self,
                   fighter,   # Fighter object
                   weapon,    # Weapon object
                   mode       # string: 'swung weapon' or ...
                   ):
        '''
        Returns a tuple of:
            1) A list of dict describing the kind of damage that |fighter|
               can do with |weapon|.  A weapon can do multiple types of damage
               (for instance a sword can do swinging damage or thrust damage).
               Each type of damage looks like this:

                {'attack_type': <string> (e.g., 'sw')
                 'num_dice': <int>
                 'plus': <int>
                 'damage_type': <string> (e.g., 'crushing')}

            2) a string describing the calculations that went into the pieces
               of the dict
        '''
        results = []
        why = []

        this_results, this_why = self.__get_damage_one_case(fighter,
                                                            weapon,
                                                            mode)
        results.extend(this_results)
        why.extend(this_why)

        if len(results) == 0:
            return '(None)', why

        return results, why

    def get_disallowed_modes(self,
                             fighter, # Fighter object
                             all_out_option = None
                             ):
        if all_out_option is None:
            all_out_option = self.__get_current_all_out_attack_option(fighter)

        if all_out_option is None:
            return []

        if (all_out_option == GurpsRuleset.ALL_OUT_RANGED_DETERMINED_ATTACK or
                all_out_option == GurpsRuleset.ALL_OUT_SUPPRESSION_FIRE):
            return ['natural weapon', 'swung weapon', 'thrust weapon',
                    'melee weapon']

        if (all_out_option == GurpsRuleset.ALL_OUT_DOUBLE_ATTACK or
                all_out_option == GurpsRuleset.ALL_OUT_STRONG_ATTACK or
                all_out_option == GurpsRuleset.ALL_OUT_FEINT or
                all_out_option == GurpsRuleset.ALL_OUT_MELEE_DETERMINED_ATTACK):
            return ['ranged weapon']

        return []

    def get_dodge_skill(self,                       # Public to aid in testing
                        fighter,        # Fighter object
                        opponent=None   # Fighter object
                        ):  # B326
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully dodge an
               attack
            2) array of strings describing the calculations that went into
               the number
        '''
        dodge_why = []
        dodge_skill_modified = False

        dodge_skill = 3 + int(fighter.rawdata['current']['basic-speed'])
        dodge_why.append('Dodge (B326) @ int(basic-speed(%.1f))+3 = %d' % (
                                fighter.rawdata['current']['basic-speed'],
                                dodge_skill))

        # Targeting laser on opponent's weapon
        # NOTE: I do a bad job of calculating dodge if the opponent is
        # carrying 2 weapons and only one has a targeting laser.  If one
        # weapon has a targeting laser, I calculate the dodge for that.
        if opponent is not None:
            found = False
            for weapon in opponent.get_current_weapons():
                if 'stuff' in weapon.rawdata:
                    for thing in weapon.rawdata['stuff']:
                        if 'to-hit-bonus' in thing:
                            dodge_skill += thing['to-hit-bonus']
                            dodge_why.append('  +1 due to opponent\'s %s' %
                                    thing['name'])
                            found = True
                            break
                if found:
                    break

        if fighter.rawdata['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.rawdata['advantages']:  # B43
            dodge_skill_modified = True
            dodge_why.append('  +1 due to combat reflexes (B43)')
            dodge_skill += 1

        posture_mods = self.get_posture_mods(fighter.rawdata['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            dodge_skill_modified = True
            dodge_skill += posture_mods['defense']
            dodge_why.append('  %+d due to %s posture' %
                             (posture_mods['defense'],
                              fighter.rawdata['posture']))

        # B327
        if (fighter.rawdata['current']['hp'] <
                fighter.rawdata['permanent']['hp']/3.0):
            dodge_skill_modified = True
            dodge_why.append(
                    '  dodge(%d)/2 (round up) due to hp(%d) < perm-hp(%d)/3 (B327)'
                    % (dodge_skill,
                       fighter.rawdata['current']['hp'],
                       fighter.rawdata['permanent']['hp']))
            dodge_skill = int(((dodge_skill)/2.0) + 0.5)

        # B426
        no_fatigue_penalty = self.get_option('no-fatigue-penalty')
        if ((no_fatigue_penalty is None or not no_fatigue_penalty) and
                (fighter.rawdata['current']['fp'] <
                    fighter.rawdata['permanent']['fp']/3.0)):
            dodge_skill_modified = True
            dodge_why.append(
                    '  dodge(%d)/2 (round up) due to fp(%d) < perm-fp(%d)/3 (B426)'
                    % (dodge_skill,
                       fighter.rawdata['current']['fp'],
                       fighter.rawdata['permanent']['fp']))
            dodge_skill = int(((dodge_skill)/2.0) + 0.5)

        if dodge_skill_modified:
            dodge_why.append('  ...for a dodge skill total = %d' % dodge_skill)

        return dodge_skill, dodge_why

    def get_fight_commands(self,
                           fight_handler    # FightHandler object
                           ):
        '''
        Returns fight commands that are specific to the GURPS ruleset.  These
        commands are structured for a command ribbon.  The functions point
        right back to local functions of the GurpsRuleset.
        '''
        return {
            ord('f'): {'name': 'FP damage',
                       'func': self.__damage_FP,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                       'help': 'Removes fatigue points from the currently ' +
                               'selected fighter, or the current opponent ' +
                               '(if nobody is selected), or (if neither ' +
                               'of those) the ' +
                               'fighter that currently has the initiative. ',
                       },
            ord('r'): {'name': 'Roll vs. attrib',
                       'func': self.__roll_vs_attrib_single,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                       'help': 'Causes the selected fighter to be ' +
                               'stunned (GURPS B420)',
                       },
            ord('R'): {'name': 'All roll vs. attrib',
                       'func': self.__roll_vs_attrib_multiple,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                       'help': 'Causes the selected fighter to be ' +
                               'stunned (GURPS B420)',
                       },
            ord('S'): {'name': 'Stun',
                       'func': self.__stun,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                       'help': 'Causes the selected fighter to be ' +
                               'stunned (GURPS B420)',
                       },
            }

    def get_fighter_defenses_notes(self,
                                   fighter,  # Fighter object
                                   opponent  # Fighter object
                                   ):
        '''
        Returns a tuple of strings describing:

        1) the current (based on weapons held, armor worn, etc) defensive
           capability (parry, dodge, block) of the Fighter, and
        2) the pieces that went into the above calculations
        '''
        notes = []
        why = []

        all_out_option = self.__get_current_all_out_attack_option(fighter)
        if all_out_option is not None:
            notes.append('Dodge/Parry/Block: *NONE*')
            why.extend([
                'Dodge/Parry/Block: None',
                '  fighter has chosen an all-out attack',
                '  (%s) and that precludes an active' %
                    GurpsRuleset.all_out_attack_option_strings[all_out_option],
                '  defense (B324)'])
        else:
            # TODO (now): figure out how to pull the unarmed stuff out of the loop
            # TODO (now): this doesn't work if there're no weapons -- unarmed

            dodge_skill, dodge_why = self.get_dodge_skill(fighter, opponent)
            if dodge_skill is not None:
                dodge_string = 'Dodge (B326): %d' % dodge_skill
                why.extend(dodge_why)
                notes.append(dodge_string)

            weapons = fighter.get_current_weapons()
            for weapon in weapons:
                if weapon is None:
                    continue

                if self.does_weapon_use_unarmed_skills(weapon):
                    unarmed_info = self.get_unarmed_info(fighter,
                                                         opponent,
                                                         weapon)
                    # Unarmed Parry
                    notes.append('%s: %d' % (unarmed_info['parry_string'],
                                             unarmed_info['parry_skill']))

                elif weapon.is_shield():  # NOTE: cloaks also have this 'type'
                    block_skill, block_why = self.get_block_skill(fighter,
                                                                  weapon)
                    if block_skill is not None:
                        why.extend(block_why)
                        notes.append('Block (B327, B375): %d' % block_skill)

                elif weapon.is_melee_weapon():
                    parry_skill, parry_why = self.get_parry_skill(fighter,
                                                                  weapon,
                                                                  opponent)
                    if parry_skill is not None:
                        why.extend(parry_why)
                        notes.append('Parry (B327, B376): %d' % parry_skill)

        # Armor

        dr = 0
        dr_text_array = []

        armor_index_list = fighter.get_current_armor_indexes()
        armor_list = fighter.get_items_from_indexes(armor_index_list)

        for armor in armor_list:
            dr += armor['type']['armor']['dr']

            if ca_equipment.Equipment.is_natural_armor(armor):
                dr_text_array.append('%s, natural armor' % armor['name'])
            else:
                dr_text_array.append(armor['name'])

        if 'Damage Resistance' in fighter.rawdata['advantages']:
            # GURPS rules, B46, 5 points per level of DR advantage
            dr += (fighter.rawdata['advantages']['Damage Resistance']/5)
            dr_text_array.append('DR Advantage')

        dr_text = ' + '.join(dr_text_array)

        if dr > 0:
            notes.append('Armor: "%s", DR: %d' % (dr_text, dr))
            why.append('Armor: "%s", DR: %d' % (dr_text, dr))
            for armor in armor_list:
                if 'notes' in armor and len(armor['notes']) != 0:
                    why.append('  %s' % armor['notes'])

        return notes, why

    def get_fighter_description_long(
            self,
            character,          # Fighter object
            output,             # recepticle for character data.
                                # [[{'text','mode'},...], # line 0
                                #  [...],               ] # line 1
            expand_containers   # Bool
            ):
        '''
        Provides a text description of a Fighter including all of the
        attributes (current and permanent), equipment, skills, etc.

        Portions of the character description are ruleset-specific.  That's
        why this routine is in GurpsRuleset rather than in the Fighter class.

        Returns: nothing.  The output is written to the |output| variable.
        '''

        # attributes

        mode = curses.A_NORMAL
        output.append([{'text': 'Attributes', 'mode': mode | curses.A_BOLD}])
        found_one = False
        pieces = []

        first_row = ['st', 'dx', 'iq', 'ht', 'per']
        first_row_pieces = {}
        for row in range(2):
            found_one_this_row = False
            for item_key in character.rawdata['permanent'].keys():
                in_first_row = item_key in first_row
                if row == 0 and not in_first_row:
                    continue
                if row != 0 and in_first_row:
                    continue
                if item_key == 'basic-speed':
                    text = '%s:%.2f/%.2f' % (
                            item_key,
                            character.rawdata['current'][item_key],
                            character.rawdata['permanent'][item_key])
                else:
                    text = '%s:%d/%d' % (
                            item_key,
                            character.rawdata['current'][item_key],
                            character.rawdata['permanent'][item_key])
                if (character.rawdata['current'][item_key] ==
                        character.rawdata['permanent'][item_key]):
                    mode = curses.A_NORMAL
                else:
                    mode = (curses.color_pair(
                            ca_gui.GmWindowManager.YELLOW_BLACK) |
                            curses.A_BOLD)

                if row == 0:
                    # Save the first row as pieces so we can put them in the
                    # proper order, later.
                    first_row_pieces[item_key] = {'text': '%s ' % text,
                                                  'mode': mode}
                else:
                    pieces.append({'text': '%s ' % text, 'mode': mode})
                found_one = True
                found_one_this_row = True

            if found_one_this_row:
                if row == 0:
                    for item_key in first_row:
                        pieces.append(first_row_pieces[item_key])

                pieces.insert(0, {'text': '  ', 'mode': curses.A_NORMAL})
                output.append(copy.deepcopy(pieces))
                del pieces[:]

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # stuff

        mode = curses.A_NORMAL
        output.append([{'text': 'Equipment', 'mode': mode | curses.A_BOLD}])

        in_use_items = []

        armor_index_list = character.get_current_armor_indexes()
        armor_list = character.get_items_from_indexes(armor_index_list)

        for armor_in_use in armor_list:
            in_use_items.append(armor_in_use)
        weapons = character.get_current_weapons()

        for weapon_in_use in weapons:
            if weapon_in_use is None:
                continue
            in_use_items.append(weapon_in_use.rawdata)

        preferred_item_indexes = character.get_preferred_item_indexes()
        preferred_items = character.get_items_from_indexes(
                preferred_item_indexes)

        if len(character.rawdata['open-container']) == 0:
            open_item = None
            sub_items = []
        else:
            sub_items = copy.deepcopy(character.rawdata['open-container'])
            open_item_index = sub_items.pop(0)
            open_items = character.get_items_from_indexes([open_item_index])
            open_item = open_items[0]

        found_one = False
        for item in sorted(character.rawdata['stuff'],
                           key=lambda x: x['name']):
            found_one = True

            in_use_string = ' (in use)' if item in in_use_items else ''
            preferred_string = ' (preferred)' if item in preferred_items else ''
            open_string = ' (OPEN)' if item is open_item else ''

            qualifiers = '%s%s%s' % (in_use_string, preferred_string, open_string)

            ca_equipment.EquipmentManager.get_description(
                    item, qualifiers, sub_items, expand_containers, output)

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # advantages

        mode = curses.A_NORMAL
        output.append([{'text': 'Advantages', 'mode': mode | curses.A_BOLD}])

        found_one = False
        for advantage, value in sorted(
                iter(character.rawdata['advantages'].items()),
                key=lambda k_v: (k_v[0], k_v[1])):
            found_one = True
            output.append([{'text': '  %s: %r' % (advantage, value),
                            'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # skills

        mode = curses.A_NORMAL
        output.append([{'text': 'Skills', 'mode': mode | curses.A_BOLD}])

        skills_dict = copy.deepcopy(character.rawdata['skills'])
        if 'techniques' in character.rawdata:
            for tech in character.rawdata['techniques']:
                default_value = skills_dict.get(tech['default'], 0)
                skills_dict['%s (%s)' % (tech['name'], tech['default'])
                    ] = tech['value'] + default_value

        found_one = False
        for skill, value in sorted(iter(skills_dict.items()),
                                   key=lambda k_v1: (k_v1[0], k_v1[1])):
            found_one = True
            crit, fumble = self.__get_crit_fumble(value)
            output.append([{'text': '  %s: %d --- crit <=%d, fumble >=%d' %
                                (skill, value, crit, fumble),
                            'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # spells

        if 'spells' in character.rawdata:
            mode = curses.A_NORMAL
            output.append([{'text': 'Spells', 'mode': mode | curses.A_BOLD}])

            found_one = False
            for spell in sorted(character.rawdata['spells'],
                                key=lambda x: x['name']):
                if spell['name'] not in GurpsRuleset.spells:
                    self._window_manager.error(
                        ['Spell "%s" not in GurpsRuleset.spells' %
                            spell['name']]
                        )
                    continue
                complete_spell = copy.deepcopy(spell)
                complete_spell.update(GurpsRuleset.spells[spell['name']])
                found_one = True
                output.append(
                        [{'text': '  %s (%d): %s' % (complete_spell['name'],
                                                     complete_spell['skill'],
                                                     complete_spell['notes']),
                          'mode': mode}])

            if not found_one:
                output.append([{'text': '  (None)', 'mode': mode}])

        # timers

        mode = curses.A_NORMAL
        output.append([{'text': 'Timers', 'mode': mode | curses.A_BOLD}])

        found_one = False
        timers = character.timers.get_all()  # objects
        for timer in timers:
            found_one = True
            text = timer.get_description()
            leader = '  '
            for line in text:
                output.append([{'text': '%s%s' % (leader, line),
                                'mode': mode}])
                leader = '    '

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # notes

        mode = curses.A_NORMAL
        output.append([{'text': 'Notes', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in character.rawdata:
            for note in character.rawdata['notes']:
                found_one = True
                output.append([{'text': '  %s' % note, 'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

    def get_fighter_description_medium(
            self,
            output,         # [[{'text':...,'mode':...}...
            fighter,        # Fighter object
            opponent,       # Fighter object
            is_attacker,    # True | False
            fight_handler   # FightHandler object
            ):
        '''
        Returns medium-length description of the fighter
        '''
        fighter_name = (fighter.name if fight_handler is None else
                fight_handler.get_display_name(fighter))
        fighter_string = '%s HP: %d/%d FP: %d/%d' % (
                                    fighter_name,
                                    fighter.rawdata['current']['hp'],
                                    fighter.rawdata['permanent']['hp'],
                                    fighter.rawdata['current']['fp'],
                                    fighter.rawdata['permanent']['fp'])
        fighter_state = fighter.get_state()
        mode = (self._window_manager.get_mode_from_fighter_state(fighter_state)
                | curses.A_BOLD)
        output.append([{'text': fighter_string, 'mode': mode}])

        if fighter_state == ca_fighter.Fighter.FIGHT:
            pass
        elif fighter_state == ca_fighter.Fighter.DEAD:
            output.append([{'text': '** DEAD **', 'mode': mode}])
        elif fighter_state == ca_fighter.Fighter.UNCONSCIOUS:
            output.append([{'text': '** UNCONSCIOUS **', 'mode': mode}])
        elif fighter_state == ca_fighter.Fighter.ABSENT:
            output.append([{'text': '** ABSENT **', 'mode': mode}])
        elif fighter.rawdata['stunned']:
            mode = curses.color_pair(
                    ca_gui.GmWindowManager.MAGENTA_BLACK) | curses.A_BOLD
            output.append([{'text': '** STUNNED **', 'mode': mode}])

        # Defender

        if is_attacker:
            mode = curses.A_NORMAL
        else:
            mode = self._window_manager.color_of_fighter()
            mode = mode | curses.A_BOLD

        notes, ignore = fighter.get_defenses_notes(opponent)
        if notes is not None:
            for note in notes:
                output.append([{'text': note, 'mode': mode}])

        # Attacker

        if is_attacker:
            mode = self._window_manager.color_of_fighter()
            mode = mode | curses.A_BOLD
        else:
            mode = curses.A_NORMAL
        notes = fighter.get_to_hit_damage_notes(opponent)
        if notes is not None:
            for note in notes:
                output.append([{'text': note, 'mode': mode}])

        # Show equipment for the 'room'

        if fighter_state == ca_fighter.Fighter.FIGHT:
            char_info = []
            fighter.get_description_long(char_info, expand_containers=False)

        # now, back to normal
        mode = curses.A_NORMAL
        notes = fighter.get_notes()
        if notes is not None:
            for note in notes:
                output.append([{'text': note, 'mode': mode}])

        # Timers
        for timer in fighter.timers.get_all():
            strings = timer.get_description()
            for string in strings:
                output.append([{'text': string, 'mode': mode}])

        if ('fight-notes' in fighter.rawdata and
                fighter.rawdata['fight-notes'] is not None):
            for note in fighter.rawdata['fight-notes']:
                output.append([{'text': note, 'mode': mode}])

    def get_fighter_description_short(self,
                                      fighter,      # Fighter object
                                      fight_handler # FightHandler object
                                      ):
        fighter_name = (fighter.name if fight_handler is None else
                fight_handler.get_display_name(fighter))
        fighter_string = '%s HP:%d/%d' % (fighter_name,
                                          fighter.rawdata['current']['hp'],
                                          fighter.rawdata['permanent']['hp'])

        if 'label' in fighter.rawdata and fighter.rawdata['label'] is not None:
            fighter_string += ' - %s' % fighter.rawdata['label']

        if fighter.is_dead():
            fighter_string += ' - DEAD'
        elif 'stunned' in fighter.rawdata and fighter.rawdata['stunned']:
            fighter_string += ' - STUNNED'
        else:
            if fighter.timers.is_busy():
                fighter_string += ' - BUSY'

            if fight_handler.is_fighter_holding_init(fighter.name, fighter.group):
                fighter_string += ' - HOLDING INIT'

        return fighter_string

    def get_fighter_notes(self,
                          fighter   # Fighter object
                          ):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.)
        '''
        notes = []

        # Active aim

        if (fighter.rawdata['aim'] is not None and
                fighter.rawdata['aim']['rounds'] != 0):
            notes.append('Aiming')

        # And, now, off to the regular stuff

        if fighter.rawdata['posture'] != 'standing':
            notes.append('Posture: %s' % fighter.rawdata['posture'])
        if fighter.rawdata['shock'] != 0:
            notes.append('DX and IQ are at %d (shock)' %
                         fighter.rawdata['shock'])

        if (fighter.rawdata['current']['hp'] <
                fighter.rawdata['permanent']['hp']/3.0):
            # Already incorporated into Dodge
            notes.append('Dodge/Move are at 1/2')

        return notes

    def get_fighter_to_hit_damage_notes(self,
                                        fighter,    # Fighter object
                                        opponent    # Fighter object
                                        ):
        '''
        Returns a list of strings describing the current (using the current
        weapon, in the current posture, etc.) fighting capability (to-hit and
        damage) of the fighter.
        '''
        debug = ca_debug.Debug()
        debug.header2('get_fighter_to_hit_damage_notes')

        notes = []
        weapons = fighter.get_current_weapons()
        if len(weapons) == 0:
            self.__show_unarmed_info(notes,
                                     fighter,
                                     opponent,
                                     None  # Weapon
                                     )
            return notes

        disallowed_modes = self.get_disallowed_modes(fighter)

        for weapon in weapons:
            if weapon is None:
                continue

            notes.append('%s' % weapon.rawdata['name'])

            if self.does_weapon_use_unarmed_skills(weapon):
                if 'natural weapon' not in disallowed_modes:
                    # i.e., if this weapon uses unarmed skills (brass knuckles
                    # are an example)
                    self.__show_unarmed_info(notes,
                                             fighter,
                                             opponent,
                                             weapon)
            else:
                modes = weapon.get_attack_modes()
                found_weapon_skill = False
                for mode in modes:
                    if mode in disallowed_modes:
                        continue
                    notes.append('  %s' % mode)
                    weapon_skill = fighter.get_best_skill_for_weapon(
                            weapon.rawdata, mode)
                    if weapon_skill is not None:
                        found_weapon_skill = True
                        to_hit, ignore_why = self.get_to_hit(fighter,
                                                             opponent,
                                                             weapon,
                                                             mode,
                                                             None)
                        if to_hit is not None:  # No reason for it to be None
                            debug = ca_debug.Debug(quiet=True)
                            damage, ignore_why = self.get_damage(fighter, weapon, mode)
                            debug.header1('getting DAMAGE')
                            debug.pprint(damage)
                            damage_str = self.damage_to_string(damage)
                            debug.print('string: "%s"' % damage_str)
                            crit, fumble = self.__get_crit_fumble(to_hit)
                            notes.append('    to-hit: %d, crit <= %d, fumble >= %d' %
                                    (to_hit, crit, fumble))
                            notes.append('    damage: %s' % damage_str)

                            # Ranged weapon status

                            if (weapon.is_ranged_weapon() and
                                    'ammo' in weapon.rawdata):
                                if ('shots_per_round' in weapon.rawdata and
                                        'pellets_per_shot' in weapon.rawdata):
                                    notes.append(
                                            '      per pellet (? for more info)')

                                clip_name = weapon.rawdata['ammo']['name']
                                if clip_name is None:
                                    clip_name = ca_equipment.Equipment.UNKNOWN_STRING
                                reloads = 0  # Counts clips, not rounds
                                for item in fighter.rawdata['stuff']:
                                    if item['name'] == clip_name:
                                        reloads += (1 if 'count' not in item
                                                    else item['count'])

                                notes.append('    %d/%d shots, %d reloads' % (
                                                    weapon.shots_left(),
                                                    weapon.shots(),
                                                    reloads))

                        if 'techniques' in fighter.rawdata:
                            for technique in fighter.rawdata['techniques']:
                                # These techniques are handled elsewhere
                                if (technique['name'] == 'Dual-Weapon Attack' or
                                        technique['name'] == 'Off-Hand Weapon Training'):
                                    continue
                                if technique['default'] == weapon_skill['name']:
                                    skill = technique['value'] + weapon_skill['value']
                                    crit, fumble = self.__get_crit_fumble(to_hit)
                                    notes.append(
                                            '    Technique, %s: %d, crit <= %d, fumble >= %d' % (
                                        technique['name'], skill, crit, fumble))


                    weapon_notes = weapon.notes()
                    if weapon_notes is not None and len(weapon_notes) > 0:
                        notes.append("  NOTES: %s" % weapon_notes)

                if not found_weapon_skill:
                    self._window_manager.error(
                            ['%s requires skill "%s" does not have' %
                                (weapon.rawdata['name'],
                                 fighter.name)])
        return notes

    def get_import_commands(self,
                            world   # World object
                            ):
        '''
        Returns fight commands that are specific to the GURPS ruleset.  These
        commands are structured for a command ribbon.  The functions point
        right back to local functions of the GurpsRuleset.
        '''

        return [
            ('advantages',  {'doit': self.import_advantages_from_file}),
            ('equipment',   {'doit': self.import_equipment_from_file,
                             'param': world}),
            ('skills',      {'doit': self.import_skills_from_file}),
            ('Spells',      {'doit': self.import_spells_from_file}),
            ]

    def get_import_creature_file_extension(self):
        ''' Returns the filename extension for files from which to import.'''
        return ['.gcs']

    def get_import_equipment_file_extension(self):
        ''' Returns the filename extension for files from which to import.'''
        return ['.eqp']

    def get_parry_skill(self,                       # Public to aid in testing
                        fighter,        # Fighter object
                        weapon,         # Weapon object
                        opponent=None   # Fighter object
                        ):
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully parry an
               attack
            2) a string describing the calculations that went into the number
        '''
        skill = None
        if weapon is not None:
            modes = weapon.get_attack_modes()
            for mode in modes:
                if mode == 'ranged weapon' or mode == 'thrown weapon':
                    continue    # can't parry with missile weapon
                skill_full = fighter.get_best_skill_for_weapon(weapon.rawdata,
                                                               mode)
                if skill_full is not None:
                    if skill is None or skill_full['value'] > skill:
                        skill = skill_full['value']

        if skill is None:
            return None, None

        parry_why = []
        parry_skill_modified = False

        parry_skill = 3 + int(skill * 0.5)
        parry_why.append('Parry (B327, B376) w/%s @ (skill(%d)/2)+3 = %d' % (
            weapon.rawdata['name'], skill, parry_skill))

        dodge_skill, dodge_why = self.get_dodge_skill(fighter, opponent)
        if fighter.rawdata['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'parry' in weapon.rawdata:
            parry_skill += weapon.rawdata['parry']
            parry_skill_modified = True
            parry_why.append('  %+d due to weapon modifiers' %
                             weapon.rawdata['parry'])

        if 'Combat Reflexes' in fighter.rawdata['advantages']:
            parry_skill_modified = True
            parry_why.append('  +1 due to combat reflexes (B43)')
            parry_skill += 1

        posture_mods = self.get_posture_mods(fighter.rawdata['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            parry_skill_modified = True
            parry_skill += posture_mods['defense']
            parry_why.append('  %+d due to %s posture' %
                             (posture_mods['defense'],
                              fighter.rawdata['posture']))
        if parry_skill_modified:
            parry_why.append('  ...for a parry skill total = %d' % parry_skill)

        return parry_skill, parry_why

    def get_posture_mods(self,
                         posture    # string: 'standing' | ...
                         ):
        '''
        Returns a dict with the attack, defense, and target minuses for the
        given posture.
        '''
        return (None if posture not in GurpsRuleset.posture else
                GurpsRuleset.posture[posture])

    def get_sample_items(self):
        '''
        Returns a list of sample equipment for creating new game files.
        '''
        sample_items = [
            {
                "count": 1,
                "notes": "1d for HT+1d hrs unless other healing",
                "type": { "misc": 1 },
                "owners": [],
                "name": "Patch: light heal"
            },
            {
                "count": 1,
                "owners": [ "Renata" ],
                "type": {
                    "armor": { "dr": 3 }
                },
                "notes": "Some combination of ballistic, ablative, and disruptor.",
                "name": "Armor, Light Street"
            },
            {
                "count": 1,
                "owners": [],
                "name": "Tonfa",
                "notes": "",
                "parry": 0,
                "type": {
                    "swung weapon": {
                        "skill": { "Tonfa": 0 },
                        "damage": { "type": "cr", "plus": 0, "st": "sw" }
                    },
                    "thrust weapon": {
                        "skill": { "Tonfa": 0 },
                        "damage": { "type": "cr", "plus": 1, "st": "thr" }
                    }
                }
            },
            {
                "acc": 2,
                "count": 1,
                "owners": [],
                "name": "pistol, Baretta DX 192",
                "clip": {
                    "type": { "misc": 1 },
                    "name": "C Cell",
                    "shots": 8,
                    "shots_left": 8
                },
                "reload": 3,
                "notes": "",
                "bulk": -2,
                "reload_type": 2,
                "type": {
                    "ranged weapon": {
                        "skill": { "Beam Weapons (Pistol)": 0 },
                        "damage": {
                            "dice": { "plus": 4, "num_dice": 1, "type": "pi" }
                            }
                    }
                },
                "ammo": { "count": 1, "name": "C Cell", "shots": 8 }
            },
            {
                "count": 1,
                "notes": "",
                "type": { "misc": 1 },
                "owners": None,
                "name": "C Cell"
            }
            ]
        return sample_items

    def get_sections_in_template(self):
        '''
        This returns an array of the Fighter section headings that are
        expected (well, not _expected_ but any headings that aren't in this
        list should probably not be there) to be in a template.
        '''
        sections = ['skills', 'advantages', 'spells']
        sections.extend(super(GurpsRuleset, self).get_sections_in_template())

        # Transitory sections, not used in template:
        #   aim, stunned, shock, posture, actions_this_turn,

        return sections

    def get_unarmed_weapon(self):
        item = {
          "count": 1,
          "owners": null,
          "name": "unarmed",
          "notes": "",
          "parry": 0,
          "type": {
            "punch": {"damage": {"st": "sw", "plus": -2, "type": "cut"},
                             "skill": {"Karate": 0,
                                       "Boxing": 0,
                                       "Brawling": 0,
                                       "DX": 0}
                             },
            "kick": {"damage": {"st": "thr", "plus": 0, "type": "imp"},
                             "skill": {"Karate": 0,
                                       "Boxing": 0,
                                       "Brawling": 0,
                                       "DX": 0}
                              }
          }
        }
        return None

    def get_to_hit(
            self,
            fighter,             # Fighter object
            opponent,            # Fighter object
            weapon,              # Weapon object
            mode,                # string: 'swung weapon', or ...
            shots_fired,         # int: how many shots taken (1 unless RoF>1).
                                 #       None means 'use max'
            moving=False,        # bool: ignore timers/we attack during move
            all_out_option=None  # int: GurpsRuleset.ALL_OUT_xxx values
            ):
        '''
        Figures out the total to-hit for this fighter on this opponent with
        this weapon.  Includes situational stuff (posture, aiming, two-weapon
        attacks).

        Returns tuple (skill, why) where:
            'skill' (number) is the value the attacker needs to roll to-hit
                    the target.
            'why'   is an array of strings describing why the to-hit numbers
                    are what they are.
        '''
        debug = ca_debug.Debug()
        weapon_name = '<Unarmed>' if weapon is None else weapon.name
        debug.header2('get_to_hit: %s' % weapon_name)

        skill_full = None
        if weapon is not None:
            skill_full = fighter.get_best_skill_for_weapon(weapon.rawdata,
                                                           mode)

        if skill_full is None:
            return None, None
        skill = skill_full['value']

        why = []
        why.append('Weapon %s, %s' % (weapon.rawdata['name'], mode))
        why.append('  %s: skill = %d' % (skill_full['name'], skill))
        skill_modifier = weapon.rawdata['type'][mode]['skill'][skill_full['name']]
        if skill_modifier < 0:
            why.append('  ...using default skill at %d (already included)' %
                    skill_modifier)

        # Dual-Weapon Attacking
        # TODO (now): break this section out into its own function so that it
        #   can be used unarmed
        weapons = fighter.get_current_weapons()
        if len(weapons) == ca_fighter.Fighter.MAX_WEAPONS:
            weapon_1ary = weapons[0]
            weapon_2ary = weapons[1]
            techniques = (None if 'techniques' not in fighter.rawdata else
                    fighter.rawdata['techniques'])

            # Dual-weapon fighting (B230, B417)
            skill_full = fighter.get_best_skill_for_weapon(weapon.rawdata,
                                                           mode)
            skill = skill_full['value']
            skill_1ary_name = skill_full['name']

            # 2nd weapon
            skill_full = fighter.get_best_skill_for_weapon(weapon_2ary.rawdata)
            skill_2ary = skill_full['value']
            skill_2ary_name = skill_full['name']

            if skill == skill_2ary:
                defaults = [skill_1ary_name]
            else:
                defaults = [skill_1ary_name, skill_2ary_name]

            technique = self.__get_technique(
                    techniques, 'Dual-Weapon Attack', defaults)

            if technique is not None:
                skill += technique['value']
                why.append('  %+d due to Dual-Weapon Fighting technique' %
                           technique['value'])
            else:
                skill -= 4
                why.append('  -4 due to dual-weapon fighting (B230, B417)')

            # Off-hand weapon fighting (B417)

            found_match = False # Found a rule to override default 2-weapon?

            # This method is called once for each hand.  If this is called for
            # the off-hand, what we're holding is identically equal to the
            # second weapon.  The code, below, is for that case.
            if weapon.rawdata is weapon_2ary.rawdata:
                if 'Ambidexterity' in fighter.rawdata['advantages']:
                    found_match = True
                    skill -= 0
                    why.append('  no off-hand penalty due to ambidexterity')
                else:
                    technique = self.__get_technique(
                            techniques,
                            'Off-Hand Weapon Training',
                            [skill_2ary_name])
                    if technique is not None:
                        found_match = True
                        skill += technique['value']
                        why.append(
                                '  %+d due to Off-Hand Weapon Training technique' %
                                technique['value'])

                if not found_match:
                    skill -= 4
                    why.append('  -4 due to off-hand weapon (B417)')

        # Attack while Moving

        if not moving:
            timers = fighter.timers.get_all()
            for timer in timers:
                if ('move-and-attack' in timer.rawdata and
                        timer.rawdata['move-and-attack']):
                 moving = True
                 break

        if moving:
            skill, why = self.__move_and_attack_mods(fighter,
                                                     opponent,
                                                     weapon,
                                                     mode,
                                                     skill,
                                                     why)

        # Targeting Laser

        if 'stuff' in weapon.rawdata:
            for thing in weapon.rawdata['stuff']:
                if 'to-hit-bonus' in thing:
                    skill += thing['to-hit-bonus']
                    why.append('  +1 due to %s' % thing['name'])

        # Aiming

        if 'acc' in weapon.rawdata:
            if fighter.rawdata['aim']['rounds'] > 0:
                why.append('  +%d due to aiming for 1' % weapon.rawdata['acc'])
                skill += weapon.rawdata['acc']
                if fighter.rawdata['aim']['braced']:
                    why.append('  +1 due to bracing')
                    skill += 1
            if fighter.rawdata['aim']['rounds'] == 2:
                why.append('  +1 due to one more round of aiming')
                skill += 1

            elif fighter.rawdata['aim']['rounds'] > 2:
                why.append('  +2 due to 2 or more additional rounds of aiming')
                skill += 2

        # Shotgun? - B373
        if 'shots_per_round' in weapon.rawdata:
            pellets_per_shot = (1 if 'pellets_per_shot' not in weapon.rawdata
                    else weapon.rawdata['pellets_per_shot'])
            to_hit_bonus = [
                    {'shots': 4, 'bonus': +0},
                    {'shots': 8, 'bonus': +1},
                    {'shots': 12, 'bonus': +2},
                    {'shots': 16, 'bonus': +3},
                    {'shots': 24, 'bonus': +4},
                    {'shots': 49, 'bonus': +5},
                    {'shots': 99, 'bonus': +6},
                    # TODO (now): each x2, +1 to hit
                    ]

            # If shots_fired is None, check to see if we've already done an
            # action that has set the number of shots fired.

            if shots_fired is None:
                timers = fighter.timers.get_all()
                for timer in timers:
                    if ('info' in timer.rawdata and
                        'shots_fired' in timer.rawdata['info']):
                        shots_fired = timer.rawdata['info']['shots_fired']

            if shots_fired is None:
                shots_fired = weapon.rawdata['shots_per_round']

            total_shots = shots_fired * pellets_per_shot
            for entry in to_hit_bonus:
                if total_shots <= entry['shots']:
                    skill += entry['bonus']
                    if pellets_per_shot <= 1:
                        why.append('  %+d for %d shots (B373)' %
                                (entry['bonus'], shots_fired))
                    else:
                        why.append('  %+d for %d shots x %d pellets (B373)' %
                                (entry['bonus'],
                                 shots_fired,
                                 pellets_per_shot))
                    break

        # Shock

        if fighter.rawdata['shock'] != 0:
            why.append('  %+d due to shock' % fighter.rawdata['shock'])
            skill += fighter.rawdata['shock']

        # All-out attack

        debug.print('checking all_out_attack')

        if all_out_option is None:
            all_out_option = self.__get_current_all_out_attack_option(fighter)

        if all_out_option is None:
            debug.print('<No All Out Attack Option>')
        else:
            debug.print(GurpsRuleset.all_out_attack_option_strings[all_out_option])

        if all_out_option == GurpsRuleset.ALL_OUT_RANGED_DETERMINED_ATTACK:
            skill += 1
            why.append('  +1 due to all-out attack, determined (ranged)')
        elif all_out_option == GurpsRuleset.ALL_OUT_MELEE_DETERMINED_ATTACK:
            skill += 4
            why.append('  +4 due to all-out attack, determined (melee)')

        # Posture

        posture_mods = self.get_posture_mods(fighter.rawdata['posture'])
        if posture_mods is not None and posture_mods['attack'] != 0:
            if weapon.is_melee_weapon():
                why.append('  %+d due %s posture' % (
                        posture_mods['attack'], fighter.rawdata['posture']))
                skill += posture_mods['attack']
            else:
                why.append('  NOTE: %s posture doesn\'t matter for ranged' %
                           fighter.rawdata['posture'])
                why.append('    attacks (B551).')

        # Opponent's posture

        if opponent is not None:
            opponent_posture_mods = self.get_posture_mods(
                                                opponent.rawdata['posture'])
            if opponent_posture_mods is not None:
                if weapon.is_ranged_weapon():
                    skill += opponent_posture_mods['target']
                    why.append('  %+d for opponent\'s %s posture' %
                               (opponent_posture_mods['target'],
                                opponent.rawdata['posture']))

        why.append('  ...for a total = %d' % skill)

        return skill, why

    def get_unarmed_info(self,
                         fighter,        # Fighter object
                         opponent,       # Fighter object
                         weapon          # Weapon object.  Maybe brass knuckles
                         ):
        '''
        Makes sense of the cascade of unarmed skills (brawling, boxing,
        karate).  Takes into account posture and other states to determine
        to-hit and damage for hand-to-hand and kicking.

        Returns: dict with all the information
          {
            'punch_skill': <int> number the attacker needs to hit the target
                             while punching (for best of DX, brawling, etc.)
            'punch_string': <string> describing amount and type of damage
            'punch_damage': <dict> {'num_dice': <int>, 'plus': <int>}

            'kick_skill': <int> number the attacker needs to hit the target
                                while kicking (for best of DX, boxing, etc.)
            'kick_string': <string> describing amount and type of damage
            'kick_damage': <dict> {'num_dice': <int>, 'plus': <int>}

            'parry_skill': <int> number the defender needs to parry an attack
                                 (for best of DX, brawling, etc.)
            'parry_string': <string> describing type of parry

            'why': [] strings describing how each of the above values were
                      determined
          }
        '''

        # Assumes 'dx' is the minimum
        result = {
            'punch_skill': fighter.rawdata['current']['dx'],
            'punch_string': 'Punch (DX) (B271, B370)',
            'punch_damage': None,   # String: nd+m

            'kick_skill': 0,
            'kick_string': 'Kick (DX-2) (B271, B370)',
            'kick_damage': None,    # String: nd+m

            'parry_skill': fighter.rawdata['current']['dx'],
            'parry_string': 'Unarmed Parry (B376)',

            'why': []
        }

        # Using separate arrays so that I can print them out in a different
        # order than I calculate them.
        punch_why = []
        punch_damage_why = []
        kick_why = []
        kick_damage_why = []
        parry_why = []

        plus_per_die_of_thrust = 0
        plus_per_die_of_thrust_string = None

        if weapon is None:
            # If you're unarmed, there's no weapon to change the skill
            weapon = ca_equipment.Weapon(
                    {'delete me': True,    # Used to stop using this, later
                      'name': '*Unarmed*',
                      'type': {'unarmed': {'damage': {1},
                                           'skill': {"DX": 0,
                                                     "Boxing": 0,
                                                     "Brawling": 0,
                                                     "Karate": 0 }}
                                }
                    })

        # This is going to make a mish-mash of skills that span the weapon
        # modes.  Maybe one of the modes includes karate and the others don't
        # but do include boxing.  This will include both karate and boxing.
        # Still, a weapon with those traits would be REALLY weird.
        modes = weapon.get_attack_modes()
        weapon_skills = {}
        for mode in modes:
            skills = weapon.rawdata['type'][mode]['skill']
            for name, value in skills.items():
                if name in weapon_skills:
                    if value > weapon_skills[name]:
                        weapon_skills[name] = value
                else:
                    weapon_skills[name] = value

        # boxing, brawling, karate, dx
        if ('Brawling' in fighter.rawdata['skills'] and
                'Brawling' in weapon_skills):
            skill = fighter.rawdata['skills']['Brawling'] + weapon_skills['Brawling']
            if result['punch_skill'] <= skill:
                result['punch_string'] = 'Brawling Punch (B182, B271, B370)'
                result['punch_skill'] = skill
                result['kick_string'] = 'Brawling Kick (B182, B271, B370)'
                # Brawling: @DX+2 = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.rawdata['current']['dx']+2:
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Brawling(%d) @DX(%d)+2 = +1/die of thrusting damage' %
                        (result['punch_skill'],
                         fighter.rawdata['current']['dx']))
            if result['parry_skill'] <= skill:
                result['parry_skill'] = skill
                result['parry_string'] = 'Brawling Parry (B182, B376)'
        if ('Karate' in fighter.rawdata['skills'] and
                'Karate' in weapon_skills):
            skill = fighter.rawdata['skills']['Karate'] + weapon_skills['Karate']
            if result['punch_skill'] <= skill:
                result['punch_string'] = 'Karate Punch (B203, B271, B370)'
                result['kick_string'] = 'Karate Kick (B203, B271, B370)'
                result['punch_skill'] = skill
                # Karate: @DX+1+ = +2 per die of thrusting damage
                # Karate: @DX = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.rawdata['current']['dx']+1:
                    plus_per_die_of_thrust = 2
                    plus_per_die_of_thrust_string = (
                        'Karate(%d) @DX(%d)+1 = +2/die of thrusting damage' %
                        (result['punch_skill'],
                         fighter.rawdata['current']['dx']))
                elif result['punch_skill'] >= fighter.rawdata['current']['dx']:
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Karate(%d) @DX(%d) = +1/die of thrusting damage' %
                        (result['punch_skill'],
                         fighter.rawdata['current']['dx']))
                else:
                    plus_per_die_of_thrust = 0
                    plus_per_die_of_thrust_string = None
            if result['parry_skill'] <= skill:
                result['parry_skill'] = skill
                result['parry_string'] = 'Karate Parry (B203, B376)'

        # (brawling, karate, dx) - 2
        result['kick_skill'] = result['punch_skill'] - 2
        kick_why.append('%s = %s (%d) -2 = to-hit: %d' % (
                                                    result['kick_string'],
                                                    result['punch_string'],
                                                    result['punch_skill'],
                                                    result['kick_skill']))

        if ('Boxing' in fighter.rawdata['skills'] and
                'Boxing' in weapon_skills):
            # TODO (eventually): if skills are equal, boxing should be used in
            # favor of brawling or DX but NOT in favor of karate.  It's placed
            # here because the kick skill isn't improved by boxing.
            skill = fighter.rawdata['skills']['Boxing'] + weapon_skills['Boxing']
            if result['punch_skill'] < skill:
                result['punch_string'] = 'Boxing Punch (B182, B271, B370)'
                result['punch_skill'] = skill
                # Boxing: @DX+2+ = +2 per die of thrusting damage
                # Boxing: @DX+1 = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.rawdata['current']['dx']+2:
                    plus_per_die_of_thrust = 2
                    plus_per_die_of_thrust_string = (
                        'Boxing(%d) @DX(%d)+2 = +2/die of thrusting damage' %
                        (result['punch_skill'],
                         fighter.rawdata['current']['dx']))
                elif (result['punch_skill'] >=
                        fighter.rawdata['current']['dx']+1):
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Boxing(%d) @DX(%d)+1 = +1/die of thrusting damage' %
                        (result['punch_skill'],
                            fighter.rawdata['current']['dx']))
                else:
                    plus_per_die_of_thrust = 0
                    plus_per_die_of_thrust_string = None
            if result['parry_skill'] < skill:
                result['parry_skill'] = skill
                result['parry_string'] = 'Boxing Parry (B182, B376)'

        punch_why.append('%s, to-hit: %d' % (result['punch_string'],
                                             result['punch_skill']))

        # Shock

        if fighter.rawdata['shock'] != 0:
            result['punch_skill'] += fighter.rawdata['shock']
            result['kick_skill'] += fighter.rawdata['shock']

            punch_why.append('  %+d due to shock' % fighter.rawdata['shock'])
            kick_why.append('  %+d due to shock' % fighter.rawdata['shock'])

        # Posture

        posture_mods = self.get_posture_mods(fighter.rawdata['posture'])
        if posture_mods is not None and posture_mods['attack'] != 0:
            result['punch_skill'] += posture_mods['attack']
            result['kick_skill'] += posture_mods['attack']

            punch_why.append('  %+d due to %s posture' %
                             (posture_mods['attack'],
                              fighter.rawdata['posture']))
            kick_why.append('  %+d due to %s posture' %
                            (posture_mods['attack'],
                             fighter.rawdata['posture']))

        # Opponent's posture only for ranged attacks -- not used, here

        parry_raw = result['parry_skill']
        parry_damage_modified = False

        # Brawling, Boxing, Karate, DX: Parry int(skill/2) + 3
        result['parry_skill'] = 3 + int(result['parry_skill']/2)
        parry_why.append('%s @ (punch(%d)/2)+3 = %d' % (result['parry_string'],
                                                        parry_raw,
                                                        result['parry_skill']))
        # Stunned
        if fighter.rawdata['stunned']:
            result['parry_skill'] -= 4
            parry_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.rawdata['advantages']:
            parry_damage_modified = True
            result['parry_skill'] += 1
            parry_why.append('  +1 due to combat reflexes (B43)')

        if posture_mods is not None and posture_mods['defense'] != 0:
            result['parry_skill'] += posture_mods['defense']

            parry_why.append('  %+d due to %s posture' %
                             (posture_mods['defense'],
                              fighter.rawdata['posture']))

        # Final 'why' results

        if parry_damage_modified:
            parry_why.append('  ...for a parry total = %d' %
                             result['parry_skill'])
        punch_why.append('  ...for a punch total = %d' % result['punch_skill'])
        kick_why.append('  ...for a kick total = %d' % result['kick_skill'])

        # Damage

        punch_damage = None  # Expressed as dice
        kick_damage = None   # Expressed as dice
        st = fighter.rawdata['current']['st']

        # Base damage

        kick_damage_why.append('Kick damage(B271)=thr')

        damage_modified = False
        kick_damage = copy.deepcopy(GurpsRuleset.melee_damage[st]['thr'])
        kick_damage_why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                               (st,
                                kick_damage['num_dice'],
                                kick_damage['plus']))

        if 'delete me' in weapon.rawdata:
            weapon = None

        # TODO (eventually): maybe I want to make everything use damage_array
        # instead of making it a special case for brass knuckles.
        damage_array = None
        if weapon is None:
            punch_damage = copy.deepcopy(GurpsRuleset.melee_damage[st]['thr'])
            punch_damage_why.append('Punch damage(B271) = thr-1')
            punch_damage_why.append(
                    '  plug ST(%d) into table on B16 = %dd%+d' %
                    (st, punch_damage['num_dice'], punch_damage['plus']))
            punch_damage['plus'] -= 1
            punch_damage_why.append('  -1 (damage is thr-1) = %dd%+d' %
                                    (punch_damage['num_dice'],
                                     punch_damage['plus']))
        else:
            modes = weapon.get_attack_modes()
            for mode in modes:
                damage_array_1, why = self.get_damage(fighter, weapon, mode)
                punch_damage_why.extend(why)
                if damage_array is None:
                    damage_array = damage_array_1
                else:
                    damage_array.extend(damage_array_1)

        # Plusses to damage

        if plus_per_die_of_thrust != 0:
            damage_modified = True
            kick_damage['plus'] += (kick_damage['num_dice'] *
                                    plus_per_die_of_thrust)
            kick_damage_why.append('  %+d/die due to %s' % (
                                                plus_per_die_of_thrust,
                                                plus_per_die_of_thrust_string))
            if damage_array is not None:
                for damage in damage_array:
                    if damage['attack_type'] == 'thr':
                        damage['plus'] += (damage['num_dice'] *
                                           plus_per_die_of_thrust)
            else:
                punch_damage['plus'] += (punch_damage['num_dice'] *
                                         plus_per_die_of_thrust)

            punch_damage_why.append('  %+d/die of thrust due to %s' % (
                                                plus_per_die_of_thrust,
                                                plus_per_die_of_thrust_string))

        # Show the 'why'
        if damage_modified:
            kick_damage_why.append('  ...for a kick damage total = %dd%+d' % (
                                            kick_damage['num_dice'],
                                            kick_damage['plus']))
            if damage_array is not None:
                damage_str = self.damage_to_string(damage_array)
                punch_damage_why.append('  ...for a punch damage total = %s' %
                                        damage_str)
            else:
                punch_damage_why.append(
                                '  ...for a punch damage total = %dd%+d' % (
                                                punch_damage['num_dice'],
                                                punch_damage['plus']))

        # Assemble final damage and 'why'

        # NOTE: doesn't handle fangs and such which have a damage type of
        # impaling, etc.
        damage_type_str = self.__get_damage_type_str('cr')

        if damage_array is None:
            damage_array = [{
                'attack_type': None,
                'num_dice': punch_damage['num_dice'],
                'plus': punch_damage['plus'],
                'damage_type': damage_type_str
            }]
        result['punch_damage'] = self.damage_to_string(damage_array)

        if kick_damage is not None:
            damage_array = [{
                'attack_type': None,
                'num_dice': kick_damage['num_dice'],
                'plus': kick_damage['plus'],
                'damage_type': damage_type_str
            }]
            result['kick_damage'] = self.damage_to_string(damage_array)

        # Using this order because that's the order the data is shown in the
        # regular window.
        result['why'].extend(parry_why)
        result['why'].extend(punch_why)
        result['why'].extend(punch_damage_why)
        result['why'].extend(kick_why)
        result['why'].extend(kick_damage_why)

        return result

    def heal_fighter(self,
                     fighter,   # Fighter object
                     world      # World object
                     ):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        super(GurpsRuleset, self).heal_fighter(fighter, world)
        fighter.rawdata['shock'] = 0
        self.do_action(fighter,
                       {'action-name': 'stun',
                        'stun': False,
                        'comment': ('(%s) got healed and un-stunned' %
                            fighter.name)},
                       None) # No fight_handler

    def import_creature_from_file(self,
                                  filename  # string
                                  ):
        # Get the base, empty, creature so we'll have all the important bits
        # that may not be in the file

        ignore_name, creature = super(GurpsRuleset,
                self).import_creature_from_file(filename)

        gcs_import = ca_gcs_import.GcsImport(self._window_manager)
        name, creature = gcs_import.import_creature(creature, self, filename)
        return name, creature

    def import_advantages_from_file(self,
                                    throw_away
                                    ):
        '''
        The GURPS Ruleset method imports equipment from a GURPS Character
        Sheet (GCS) file.

        Returns nothing.
        '''
        # Get the source file
        filename_window = ca_gui.GetFilenameWindow(self._window_manager)
        filename = filename_window.get_filename(['.adq'])
        if filename is None:
            return True

        gcs_import = ca_gcs_import.GcsImport(self._window_manager)
        gcs_import.import_advantages_from_file(
                self._window_manager,
                self.__gurps_info.read_data['abilities']['advantages'],
                self,
                filename)
        return True

    def import_equipment_from_file(self,
                                   world # world object
                                   ):
        '''
        The GURPS Ruleset method imports equipment from a GURPS Character
        Sheet (GCS) file.

        Returns nothing.
        '''
        # Get the source file
        filename_window = ca_gui.GetFilenameWindow(self._window_manager)
        filename = filename_window.get_filename(['.eqp'])
        if filename is None:
            return True

        gcs_import = ca_gcs_import.GcsImport(self._window_manager)
        gcs_import.import_equipment_from_file(
                self._window_manager,
                world.rawdata['stuff'],  # From the world's json file
                self,
                filename)
        return True

    def import_skills_from_file(self,
                                throw_away
                                ):
        '''
        The GURPS Ruleset method imports equipment from a GURPS Character
        Sheet (GCS) file.

        Returns nothing.
        '''
        # Get the source file
        filename_window = ca_gui.GetFilenameWindow(self._window_manager)
        filename = filename_window.get_filename(['.skl'])
        if filename is None:
            return True

        gcs_import = ca_gcs_import.GcsImport(self._window_manager)
        gcs_import.import_skills_from_file(
                self._window_manager,
                self.__gurps_info.read_data['abilities']['skills'],
                self,
                filename)
        return True

    def import_spells_from_file(self,
                                throw_away
                                ):
        '''
        The GURPS Ruleset method imports spells from a GURPS Character
        Sheet spell list (spl) file.

        Returns nothing.
        '''
        # Get the source file
        filename_window = ca_gui.GetFilenameWindow(self._window_manager)
        filename = filename_window.get_filename(['.spl'])
        if filename is None:
            return True

        gcs_import = ca_gcs_import.GcsImport(self._window_manager)
        gcs_import.import_spells_from_file(
                self._window_manager,
                self.__gurps_info.read_data['spells'],
                self,
                filename)
        return True

    def initiative(self,
                   fighter, # Fighter object
                   fighters # list of Fighter objects
                   ):
        '''
        Generates a tuple of numbers for a creature that determines the order
        in which the creatures get to act in a fight.  Sorting creatures by
        their tuples (1st sorting key on the 1st element of the tuple, ...)
        will put them in the proper order.

        Returns: the 'initiative' tuple
        '''
        # Combat reflexes (B43) adds 1 to the initiative of every member of
        # the party
        combat_reflexes_bonus = 0
        for creature in fighters:
            if (creature.group == fighter.group and
                    'Combat Reflexes' in creature.rawdata['advantages']):
                # Technically, you're supposed to add 2 if the person with
                # combat reflexes is the leader but I don't have a mechanic
                # for designating the leader.
                combat_reflexes_bonus = 1
                break
        value = (fighter.rawdata['current']['basic-speed'] +
                 combat_reflexes_bonus)
        return (value,
                fighter.rawdata['current']['dx'],
                ca_ruleset.Ruleset.roll(1, 6)
                )

    def offer_to_add_dependencies(self,
                                  world,    # World object, contains store
                                  fighter,  # Fighter object
                                  new_item      # dict just added to fighter's stuff
                                  ):
        '''
        Asks the user if he wants to add ammo and skills required for a
        recently added weapon.
        '''

        # Ammo

        missing_ammo = self._get_missing_ammo_names(fighter, new_item)
        missing_ammo_menu = [(item, item) for item in missing_ammo]
        missing_ammo_menu.append(('Do not add', None))
        ammo_name, ignore = self._window_manager.menu('Add necessary ammo',
                                                      missing_ammo_menu)
        if ammo_name is not None:
            added_ammo = False
            for item in world.rawdata['stuff']:
                if ammo_name == item['name']:
                    item_copy = copy.deepcopy(item)
                    source = None
                    if (item_copy['owners'] is not None and
                            len(item_copy['owners']) == 0):
                        source = 'the store'

                    title = 'How many %s do you want to add?' % ammo_name
                    count = self._window_manager.input_box_number(1,
                                                                  len(title),
                                                                  title)
                    if count is not None:
                        item_copy['count'] = count

                    ignore = fighter.add_equipment(item_copy, source)
                    added_ammo = True
                    break
            if not added_ammo:
                self._window_manager.error(['Could not find ammo %s' % ammo_name])

        # Skills

        debug = ca_debug.Debug()
        debug.header1('offer_to_add_dependencies: skills')
        missing_skills = self._get_missing_skill_names(fighter, new_item)
        debug.print('missing_skills')
        debug.pprint(missing_skills)
        missing_skills_menu = [(item, item) for item in missing_skills]
        debug.print('missing_skills_menu')
        missing_skills_menu.append(('Do not add', None))
        debug.pprint(missing_skills_menu)
        skills_name, ignore = self._window_manager.menu('Add necessary skills',
                                                        missing_skills_menu)
        debug.print('Skills name: %r' % skills_name)

        if skills_name is not None:
            skills_value = fighter.add_one_ability('skills', skills_name)
            debug.print('skills_value: %r' % skills_value)
            if skills_value is None:
                self._window_manager.error(['Could not find skills %s' % skills_name])


    def check_creature_consistent(self,
                                  name,     # string: creature's name
                                  creature, # dict from Game File
                                  check_weapons_and_armor=True,  # bool
                                  fight_handler=None
                                  ):
        '''
        Make sure creature has skills for all their stuff.  Trying to make
        sure that one or the other of the skills wasn't entered incorrectly.
        '''
        debug = ca_debug.Debug(quiet=True)

        result = super(GurpsRuleset,
                       self).check_creature_consistent(name,
                                                       creature,
                                                       check_weapons_and_armor,
                                                       fight_handler)
        if 'skills' not in creature:
            return result

        for item in creature['stuff']:
            # NOTE: if the skill is one of the unarmed skills, then the skill
            # defaults to DX and that's OK -- we don't have to tell the user
            # about this.

            found_skill = False
            skills = {}
            if (ca_equipment.Equipment.is_natural_weapon(item) or
                    ca_equipment.Equipment.is_natural_armor(item)):
                found_skill = True # you can always use your natural items
            elif 'skill' in item:
                for item_skill in item['skill'].keys():
                    if item_skill.lower() not in creature['current']:
                        skills[item_skill] = 1
                    if (item_skill.lower() not in creature['current'] and
                            item_skill in creature['skills']):
                        found_skill = True
            elif ca_equipment.Weapon.is_weapon(item):
                weapon = ca_equipment.Weapon(item)
                debug.header1('check_creature_consistent: %s' % weapon.name)
                modes = weapon.get_attack_modes()
                debug.print('modes:')
                debug.pprint(modes)
                debug.print('item:')
                debug.pprint(item)
                for mode in modes:
                    debug.header2(mode)
                    if found_skill:
                        break
                    if mode == 'misc':
                        continue
                    for item_skill in item['type'][mode]['skill'].keys():
                        if item_skill.lower() not in creature['current']:
                            skills[item_skill] = 1
                        if (item_skill.lower() not in creature['current'] and
                                item_skill in creature['skills']):
                            found_skill = True
                            break
            else:
                found_skill = True # Not really, but just so we don't error

            if not found_skill:
                if len(skills) == 0:
                    skill_list_string = '** NONE **'
                skill_list_string = ', '.join(iter(skills.keys()))
                self._window_manager.error([
                    'Creature "%s"' % name,
                    '  has item "%s"' % item['name'],
                    '  but none of the skills to use it:',
                    '  %s' % skill_list_string])
                #result = False
        if 'spells' in creature:
            duplicate_check = {}
            for spell in creature['spells']:
                if spell['name'] in duplicate_check:
                    self._window_manager.error([
                        'Creature "%s"' % name,
                        '  has two copies of spell "%s"' % spell['name']])
                else:
                    duplicate_check[spell['name']] = 1

                if spell['name'] not in GurpsRuleset.spells:
                    self._window_manager.error([
                        'Creature "%s"' % name,
                        '  has spell "%s" that is not in ruleset' %
                        spell['name']])
        return result

    def make_empty_armor(self):
        '''
        Builds the minimum legal armor (the dict that goes into the
        Game File).

        Returns: the dict.
        '''
        item = super(GurpsRuleset, self).make_empty_armor()
        item['type'] = {'armor': {'dr': 0 }}
        return item

    def make_empty_creature(self):
        '''
        Builds the minimum legal character detail (the dict that goes into the
        Game File).  You can feed this to the constructor of a Fighter.  First,
        however, you need to install it in the World's Game File so that it's
        backed-up and recognized by the rest of the software.

        Returns: the dict.
        '''
        to_monster = super(GurpsRuleset, self).make_empty_creature()
        to_monster.update({'advantages': {},
                           'aim': {'braced': False, 'rounds': 0},
                           'check_for_death': False,
                           'gcs-file': None, # Not required but useful
                           'posture': 'standing',
                           'shock': 0,
                           'skills': {},
                           'stunned': False,
                           })
        to_monster['permanent'] = copy.deepcopy({'fp': 10,
                                                 'iq': 10,
                                                 'hp': 10,
                                                 'wi': 10,
                                                 'st': 10,
                                                 'ht': 10,
                                                 'dx': 10,
                                                 'basic-move': 5,
                                                 'basic-speed': 5,
                                                 'per': 10})
        to_monster['current'] = copy.deepcopy(to_monster['permanent'])
        return to_monster

    def make_empty_melee_weapon(self):
        '''
        Builds the minimum legal melee weapon (the dict that goes into the
        Game File).

        Returns: the dict.
        '''
        item = super(GurpsRuleset, self).make_empty_melee_weapon()
        strawman = {
                #"damage": {
                #    "sw": { "plus": -4, "type": "cut" },
                #    "thr": { "plus": -4, "type": "imp" }
                # },
                "parry": -4,
                #"skill": {"*UNKNOWN*": 0},
        }

        for key, value in strawman.items():
            if key not in item:
                item[key] = value

        return item

    def make_empty_missile_weapon(self):
        '''
        Builds the minimum legal missile weapon (the dict that goes into the
        Game File).

        Returns: the dict.
        '''
        item = super(GurpsRuleset, self).make_empty_missile_weapon()
        strawman = {
                "acc": 0,
                #"damage": {"dice": { "plus": 0, "num_dice": 0, "type": "pi" }},
                "bulk": -10,
                # "reload": 10,
                # ca_equipment.Equipment.RELOAD_CLIP
                #"skill": {"*UNKNOWN*": 0},
                #"ammo": { "name": "*UNKNOWN*", "shots": 1, "shots_left": 1 }
                # clip is not required
        }

        for key, value in strawman.items():
            if key not in item:
                item[key] = value

        return item

    def reset_aim(self,                         # Public to support testing
                  fighter           # Fighter object
                  ):
        '''
        Resets the aim for the Fighter.

        Returns: nothing.
        '''
        fighter.rawdata['aim']['rounds'] = 0
        fighter.rawdata['aim']['braced'] = False

    def search_one_creature(self,
                            name,        # string containing the name
                            group,       # string containing the group
                            creature,    # dict describing the creature
                            look_for_re  # compiled Python regex
                            ):
        '''
        Looks through a creature for the regular expression |look_for_re|.

        Returns: dict: with name, group, location (where in the character the
        regex was found), and notes (text for display to the user).
        '''

        result = super(GurpsRuleset, self).search_one_creature(name,
                                                               group,
                                                               creature,
                                                               look_for_re)

        if 'advantages' in creature:
            for advantage in creature['advantages']:
                if look_for_re.search(advantage):
                    result.append(
                        {'name': name,
                         'group': group,
                         'location': 'advantages',
                         'notes': '%s=%d' % (
                                        advantage,
                                        creature['advantages'][advantage])})

        if 'skills' in creature:
            for skill in creature['skills']:
                if look_for_re.search(skill):
                    result.append(
                            {'name': name,
                             'group': group,
                             'location': 'skills',
                             'notes': '%s=%d' % (skill,
                                                 creature['skills'][skill])})

        return result

    def start_fight(self,
                    fighter  # Fighter object
                    ):
        '''
        Removes all the ruleset-related stuff from the old fight except injury.
        '''
        fighter.rawdata['shock'] = 0
        fighter.rawdata['stunned'] = False
        fighter.rawdata['posture'] = 'standing'
        self.reset_aim(fighter)

    def start_turn(self,
                   fighter,         # Fighter object
                   fight_handler    # FightHandler object
                   ):
        '''
        Performs all of the stuff required for a Fighter to start his/her
        turn.  Does all the consciousness/death checks, etc.

        Returns: nothing
        '''
        playing_back = (False if fight_handler is None else
                        fight_handler.world.playing_back)
        # B426 - FP check for consciousness
        if fighter.is_conscious() and not playing_back:
            if fighter.rawdata['current']['fp'] <= 0:
                pass_out_menu = [(('roll <= WILL (%s), or did nothing' %
                                  fighter.rawdata['current']['wi']), True),
                                 ('did NOT make WILL roll', False)]
                made_will_roll, ignore = self._window_manager.menu(
                    ('%s: roll <= WILL or pass out due to FP (B426)' %
                        fighter.name),
                    pass_out_menu)
                if not made_will_roll:
                    self.do_action(fighter,
                                   {'action-name': 'set-consciousness',
                                    'level': ca_fighter.Fighter.UNCONSCIOUS},
                                   fight_handler)

        # B327 -- checking on each round whether the fighter is still
        # conscious

        self.__check_for_unconscious(fighter, fight_handler) # Ignore return

        # Let the user know if this fighter is stunned.

        if fighter.is_conscious() and fighter.rawdata['stunned']:
            window_text = [
                [{'text': 'Stunned, stunned, really stunned',
                  'mode': curses.A_NORMAL}]
                           ]
            self._window_manager.display_window(
                            ('%s is currently **STUNNED**' % fighter.name),
                            window_text)

        fighter.rawdata['actions_this_turn'] = []

    def update_creature_from_file(self,
                                  fighter_dict,  # dict describing fighter
                                  filename       # string
                                  ):
        # Get the base, empty, creature so we'll have all the important bits
        # that may not be in the file
        '''
        Returns list of strings describing what's changed.
        '''

        changes = super(GurpsRuleset, self).update_creature_from_file(
                fighter_dict, filename)

        gcs_import = ca_gcs_import.GcsImport(self._window_manager)
        new_changes = gcs_import.update_creature(fighter_dict, self, filename)
        changes.extend(new_changes)
        return changes

    #
    # Protected and Private Methods
    #

    def __adjust_attribute(self,
                           fighter,         # Fighter object
                           action,          # {'action-name':
                                            #       'adjust-attribute',
                                            #  'attr-type': 'current' or
                                            #       'permanent'
                                            #  'attribute': name of the
                                            #       attribute to change
                                            #  'new-value': the new value
                                            #  'comment': <string>, # optional
                                            #  'quiet': <bool>
                                            #       # use defaults for all
                                            #       # user interactions --
                                            #       # optional
                                            # }
                           fight_handler,   # FightHandler object (ignored)
                           ):
        '''
        Action handler for Ruleset.

        Adjust any of the Fighter's attributes.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part of the action
            # actually perfoms all the GurpsRuleset-specific actions and
            # side-effects of aiming the Fighter's current weapon.

            # This does nothing -- everything interesting was done in the
            # first part, before the base class had a chance to modify the
            # attribute.

            return None # No timer

        else:
            # This is the 1st part of a 2-part action.  This part of the
            # action slips in before the base class can modify the
            # attribute.

            attr_type = action['attr-type']
            attr = action['attribute']
            new_value = action['new-value']

            if (self.get_option('conscious-on-heal') and
                    not fighter.is_conscious() and
                    attr == 'hp' and
                    new_value > fighter.rawdata[attr_type][attr] and
                    attr_type == 'current'):
                self.do_action(fighter,
                               {'action-name': 'set-consciousness',
                                'level': ca_fighter.Fighter.ALIVE},
                               fight_handler)
                if fighter.rawdata['current']['fp'] <= 0:
                    fighter.rawdata['current']['fp'] = 1

            # Send the action for the second part

            new_action = copy.deepcopy(action)
            new_action['part'] = 2
            self.do_action(fighter, new_action, fight_handler)

            return None  # No timer

    def _adjust_hp(self,
                   fighter,         # Fighter object
                   action,          # {'action-name': 'adjust-hp',
                                    #  'adj': <number (usually < 0) HP change>,
                                    #  'comment': <string>, # optional
                                    #  'quiet': <bool - use defaults for all
                                    #            user interactions.> }
                   fight_handler    # FightHandler object
                   ):
        '''
        Action handler for GurpsRuleset.

        NOTE: This is a huge tangle because, for the GurpsRuleset, we need to
        ask questions (i.e., whether or not to subtract DR from the HP).
        Because of that, there are 2 events: 1) adjust-hp asks the question
        and generates the 2nd event adjust-hp-really EXCEPT for replay mode,
        where it does nothing.  2) adjust-hp-really contains the post-DR
        adjustment and actually reduces the HP.

        ON TOP OF THAT, adjust-hp is handled differently than the rest of the
        actions.  Normally, there's a Ruleset.__xxx and a GurpsRuleset.__xxx
        and they're called in a cascaded manner:

                            GurpsRuleset       Ruleset
                                 |                |
                                 -                -
                    do_action ->| |- do_action ->| |- __xxx -+
                                | |              | |         |
                                | |              | ||<-------+
                                | |<- - - - - - -| |
                                | |- __xxx -+     -
                                | |         |     |
                                | ||<-------+     |
                                 -                |
                                 |                |

        _adjust_hp, though, is PROTECTED (not private) so Ruleset::do_action
        actually calls GurpsRuleset::_xxx and Ruleset::_xxx is overridden:

                            GurpsRuleset         Ruleset
                                 |                  |
                                 -                  -
                    do_action ->| |-- do_action -->| |- _adjust_hp --+
                                | |                | |               |
                                | ||<- _adjust_hp -------------------+
                                | ||- - - - - - - >| |
                                | |                | |
                                | |<- - - - - - - -| |
                                 -                  -
                                 |                  |

        Ruleset::_adjust_hp never gets called for the adjust-hp action.
        Ruleset's function gets called, directly, by the 2nd (GurpsRulest-
        specific) action.

        We do things this way because a) GurpsRuleset::_adjust_hp modifies the
        adj (in the case of armor) so we can't call the Ruleset's version
        first (it has bad data) and b) we can't ask questions in an action
        during playback.
        '''

        if fight_handler.world.playing_back:
            # This is called from Ruleset::do_action so we have to have a
            # return value that works, there.
            return ca_ruleset.Ruleset.HANDLED_OK

        adj = action['adj']
        dr_comment = None
        quiet = False if 'quiet' not in action else action['quiet']
        still_conscious = True

        # Reducing HP
        if adj < 0:
            hit_location_flavor = self.get_option('hit-location-flavor')
            if hit_location_flavor is not None and hit_location_flavor:
                # Hit location (just for flavor, not for special injury)
                table_lookup = (random.randint(1, 6) +
                                random.randint(1, 6) +
                                random.randint(1, 6))
                hit_location = GurpsRuleset.hit_location_table[table_lookup]

                window_text = [
                    [{'text': ('...%s\'s %s' % (fighter.name, hit_location)),
                      'mode': curses.A_NORMAL}],
                    [{'text': '', 'mode': curses.A_NORMAL}]
                               ]
            else:
                window_text = [
                    [{'text': ('...%s' % fighter.name),
                      'mode': curses.A_NORMAL}],
                    [{'text': '', 'mode': curses.A_NORMAL}]
                               ]

            # Adjust for armor
            dr = 0
            dr_text_array = []
            use_armor = False

            armor_index_list = fighter.get_current_armor_indexes()
            armor_list = fighter.get_items_from_indexes(armor_index_list)

            for armor in armor_list:
                dr += armor['type']['armor']['dr']
                dr_text_array.append(armor['name'])

            if 'Damage Resistance' in fighter.rawdata['advantages']:
                # GURPS rules, B46, 5 points per level of DR advantage
                dr += (fighter.rawdata['advantages']['Damage Resistance']/5)
                dr_text_array.append('DR Advantage')

            if not quiet and dr != 0:
                use_armor_menu = [('yes', True), ('no', False)]
                use_armor, ignore = self._window_manager.menu(
                        'Use Armor\'s DR?', use_armor_menu)
            if use_armor:
                if dr >= -adj:
                    window_text = [
                        [{'text': 'The armor absorbed all the damage',
                          'mode': curses.A_NORMAL}]
                    ]
                    self._window_manager.display_window(
                                    ('Did *NO* damage to %s' % fighter.name),
                                    window_text)
                    return ca_ruleset.Ruleset.HANDLED_OK

                original_adj = adj

                adj += dr
                action['adj'] = adj

                dr_text = '; '.join(dr_text_array)
                window_text.append(
                    [{'text': ('%s was wearing %s (total dr:%d)' % (
                                                              fighter.name,
                                                              dr_text,
                                                              dr)),
                      'mode': curses.A_NORMAL}]
                                  )
                window_text.append(
                    [{'text': ('so adj(%d) - dr(%d) = damage (%d)' % (
                                                              -original_adj,
                                                              dr,
                                                              -adj)),
                      'mode': curses.A_NORMAL}]
                                  )

                dr_comment = ' (%d HP after dr)' % -adj
            self._window_manager.display_window(
                                ('Did %d hp damage to...' % -adj),
                                window_text)

            # Check for Death (B327)
            adjusted_hp = fighter.rawdata['current']['hp'] + adj

            if adjusted_hp <= -(5 * fighter.rawdata['permanent']['hp']):
                # hp < -5*HT
                self.do_action(fighter,
                               {'action-name': 'set-consciousness',
                                'level': ca_fighter.Fighter.DEAD},
                               fight_handler)
                still_conscious = False # Dead
            else:
                # hp < -1*HT or -2*HT, ...
                threshold = -fighter.rawdata['permanent']['hp']
                while fighter.rawdata['current']['hp'] <= threshold:
                    threshold -= fighter.rawdata['permanent']['hp']
                if adjusted_hp <= threshold:
                    dead_menu = [
                        (('roll <= HT (%d)' %
                            fighter.rawdata['current']['ht']), True),
                        ('did NOT make HT roll', False)]
                    made_ht_roll, ignore = self._window_manager.menu(
                        ('%s: roll <= HT or DIE (B327)' % fighter.name),
                        dead_menu)

                    if not made_ht_roll:
                        self.do_action(fighter,
                                       {'action-name': 'set-consciousness',
                                        'level': ca_fighter.Fighter.DEAD},
                                       fight_handler)
                        still_conscious = False # Dead

            # Check for Unconscious (House Rule)
            if still_conscious and self.get_option('pass-out-immediately'):
                if self.__check_for_unconscious(fighter,
                                                fight_handler,
                                                adjusted_hp):
                    alread_checked_timer = ca_timers.Timer(None)
                    alread_checked_timer.from_pieces(
                            {'parent-name': fighter.name,
                             'rounds': 0.9,
                             'string':
                                GurpsRuleset.checked_for_unconscious_string
                             })
                    fighter.timers.add(alread_checked_timer)
                    still_conscious = fighter.is_conscious()

            # Check for Major Injury (B420)
            if (still_conscious and
                    -adj > (fighter.rawdata['permanent']['hp'] / 2)):
                (SUCCESS, SIMPLE_FAIL, BAD_FAIL) = list(range(3))
                total = fighter.rawdata['current']['ht']

                no_knockdown = self.get_option('no-knockdown')
                stunned_string = 'Stunned and Knocked Down' if (
                        no_knockdown is None or not no_knockdown) else 'Stunned'

                if 'High Pain Threshold' in fighter.rawdata['advantages']:
                    total = fighter.rawdata['current']['ht'] + 3
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT+3 (%d) or be %s'
                        % (total, stunned_string))
                # elif 'Low Pain Threshold' in fighter.rawdata['advantages']:
                #    total = fighter.rawdata['current']['ht'] - 4
                #    menu_title = (
                #      'Major Wound (B420): Roll vs. HT-4 (%d) or be %s' %
                #      (total, stunned_string))
                else:
                    total = fighter.rawdata['current']['ht']
                    menu_title = (
                            'Major Wound (B420): Roll vs HT (%d) or be %s'
                            % (total, stunned_string))

                stunned_menu = [
                   ('Succeeded (roll <= HT (%d))' % total,
                    GurpsRuleset.MAJOR_WOUND_SUCCESS),
                   ('Missed roll by < 5 (roll < %d) -- %s' % (total+5,
                       stunned_string),
                    GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL),
                   ('Missed roll by >= 5 (roll >= %d -- Unconscious)' %
                       (total+5),
                    GurpsRuleset.MAJOR_WOUND_BAD_FAIL),
                   ]
                stunned_results, ignore = self._window_manager.menu(
                        menu_title, stunned_menu)
                if stunned_results == GurpsRuleset.MAJOR_WOUND_BAD_FAIL:
                    self.do_action(fighter,
                                   {'action-name': 'set-consciousness',
                                    'level': ca_fighter.Fighter.UNCONSCIOUS},
                                   fight_handler)
                elif stunned_results == GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL:
                    # B420 - major wounds cause stunning and knockdown
                    self.do_action(fighter,
                                   {'action-name': 'stun',
                                    'stun': True},
                                   fight_handler)

                    if no_knockdown is None or not no_knockdown:
                        self.do_action(fighter,
                                       {'action-name': 'change-posture',
                                        'posture': 'lying'},
                                       fight_handler)
                        # Technically, dropping a weapon should leave the
                        # weapon in the room but it's easier for game play to
                        # just holster it.  This assumes a nice game where the
                        # GM just assumes the character (or one of his/her
                        # party members) picks up the gun.
                        indexes = fighter.get_current_weapon_indexes()
                        for index in indexes:
                            self.do_action(fighter,
                                           {'action-name': 'holster-weapon',
                                            'weapon-index': index},
                                           fight_handler,
                                           logit=False)

        # B59
        if (still_conscious and
                'High Pain Threshold' not in fighter.rawdata['advantages']):
            # Shock (B419) is cumulative but only to a maximum of -4
            # Note: 'adj' is negative
            shock_level = fighter.rawdata['shock'] + adj
            if shock_level < -4:
                shock_level = -4
            self.do_action(fighter,
                           {'action-name': 'shock', 'value': shock_level},
                           fight_handler)

        # WILL roll or lose aim
        if still_conscious and fighter.rawdata['aim']['rounds'] > 0:
            aim_menu = [('made WILL roll', True),
                        ('did NOT make WILL roll', False)]
            made_will_roll, ignore = self._window_manager.menu(
                ('roll <= WILL (%d) or lose aim' %
                    fighter.rawdata['current']['wi']),
                aim_menu)
            if not made_will_roll:
                self.do_action(fighter,
                               {'action-name': 'reset-aim'},
                               fight_handler)

        # Have to copy the action because using the old one confuses the
        # do_action routine that called this function.
        new_action = copy.deepcopy(action)

        if dr_comment is not None and 'comment' in new_action:
            new_action['comment'] += dr_comment
        new_action['action-name'] = 'adjust-hp-really'
        self.do_action(fighter, new_action, fight_handler)
        return ca_ruleset.Ruleset.DONT_LOG

    def __adjust_hp_really(self,
                           fighter,         # Fighter object
                           action,          # {'action-name':
                                            #  'adjust-hp-really',
                                            #  'comment': <string>, # optional
                                            #  'adj': <number = HP change>,
                                            #  'quiet': <bool - use defaults
                                            #            for all user
                                            #            interactions.> }
                           fight_handler    # FightHandler object
                           ):
        '''
        Action handler for GurpsRuleset.

        This is the 2nd part of a 2-part action.  This action
        ('adjust-hp-really') actually perfoms all the actions and
        side-effects of changing the hit-points.  See
        |GurpsRuleset::_adjust_hp| for an idea of how this method is used.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        pre_adjust_hp = fighter.rawdata['current']['hp']
        super(GurpsRuleset, self)._adjust_hp(fighter, action, fight_handler)
        post_adjust_hp = fighter.rawdata['current']['hp']

        # NOTE: House rule for healing an unconscious person
        # TODO (now): use adjust-attribute's solution to this
        if (pre_adjust_hp < post_adjust_hp and post_adjust_hp > 0 and
                not fighter.is_conscious() and not fighter.is_dead()):
            self.do_action(fighter,
                           {'action-name': 'set-consciousness',
                            'level': ca_fighter.Fighter.ALIVE},
                           fight_handler)

        return None  # No timers

    def __build_cast_spell_menu_item(
            self,
            spell, # dict from fighter's list
            index, # int: index of spell in fighter's list
            maintain=False
            ):
        if spell['name'] not in GurpsRuleset.spells:
            self._window_manager.error(
                ['Spell "%s" not in GurpsRuleset.spells' %
                    spell['name']])
            return None

        complete_spell = copy.deepcopy(spell)
        complete_spell.update(GurpsRuleset.spells[spell['name']])

        cast_text_array = ['%s -' % complete_spell['name']]

        for piece in ['cost',
                      'skill',
                      'casting time',
                      'duration',
                      'notes',
                      'range',
                      'save']:
            if piece in complete_spell:
                if piece == 'save': # array needs to be handled
                    amalgam = ', '.join(complete_spell[piece])
                    cast_text_array.append('%s:%r' %
                                           (piece,
                                            amalgam))
                else:
                    cast_text_array.append('%s:%r' %
                                           (piece,
                                            complete_spell[piece]))
        cast_text = ' '.join(cast_text_array)
        if maintain:
            result = (cast_text,
                      {'action': {'action-name': 'maintain-spell',
                                  'spell-index': index,
                                  'complete spell': complete_spell}})
        else:
            result = (cast_text,
                      {'action': {'action-name': 'cast-spell',
                                  'spell-index': index}})
        return result

    def __cast_spell(self,
                     fighter,       # Fighter object
                     action,        # {'action-name': 'cast-spell'
                                    #  'spell-index': <index in 'spells'>,
                                    #  'complete spell': <dict> # this
                                    #     is a combination of the spell
                                    #     in the character rawdata and
                                    #     the same spell from the
                                    #     ruleset
                                    #  'comment': <string>, # optional
                                    #  'part': 2 # optional
                     fight_handler  # FightHandler object
                     ):
        '''
        Action handler for GurpsRuleset.

        Handles the action of casting a magic spell.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  The 2nd part of this
            # action actually perfoms all the actions and side-effects of
            # casting a spell.  This is mostly a bunch of timers.

            complete_spell = action['complete spell']

            # Charge the spell caster for the spell.

            cost = complete_spell['cost']
            if cost > 0:
                # Powerstone
                if 'source' in complete_spell:
                    item = fighter.rawdata['stuff'][complete_spell['source']]
                    from_powerstone = (cost if cost <= item['mana']
                            else item['mana'])
                    item['mana'] -= from_powerstone
                    cost -= from_powerstone

                # Fatigue / HP
                if cost > 0:
                    self.do_action(fighter,
                                   {'action-name': 'adjust-fp',
                                    'adj': -cost,
                                    'ignore-dr': True},
                                   fight_handler,
                                   logit=False)

            # Duration Timer

            # If the spell lasts any time at all, put a timer up so that we see
            # that it's active

            duration_timer = None
            if complete_spell['duration'] > 0:
                duration_timer = ca_timers.Timer(None)
                duration_timer.from_pieces(
                           {'parent-name': fighter.name,
                            'rounds': complete_spell['duration'],
                            'string': ('CAST SPELL (%s) ACTIVE' %
                                       complete_spell['name']),
                            'fire_when': ca_timers.Timer.FIRE_ROUND_START,
                            'data': {'spell': complete_spell}
                            })

            # Casting Timer

            casting_timer = None
            if (complete_spell['casting time'] > 0 and
                    complete_spell['range'] != 'block'):
                casting_timer = ca_timers.Timer(None)
                text = [('Casting (%s) @ skill (%d): %s' % (
                                                        complete_spell['name'],
                                                        complete_spell['skill'],
                                                        complete_spell['notes'])),
                        ' Defense: none',
                        ' Move: none']

                actions = {}
                if duration_timer is not None:
                    actions['timer'] = duration_timer.rawdata

                if complete_spell['duration'] == 0:
                    actions['announcement'] = ('CAST SPELL (%s) FIRED' %
                                               complete_spell['name'])

                casting_timer.from_pieces(
                        {'parent-name': fighter.name,
                         'rounds': complete_spell['casting time'],
                         'string': text,
                         'actions': actions,
                         'fire_when': ca_timers.Timer.FIRE_ROUND_START
                         })
                casting_timer.mark_owner_as_busy()  # When casting, owner is busy

                # "Zombie Summoning": {
                #   "cost": 5,
                #   "notes": "M151",
                #   "maintain": 2,
                #   "casting time": 4,
                #   "duration": 60,
                #   "range": 'special',
                #   "save": [],
                # }

            # Opponent's Timers

            if 'opponent' in action and fight_handler is not None:
                ignore, opponent = fight_handler.get_fighter_object(
                                                action['opponent']['name'],
                                                action['opponent']['group'])
                spell_timer = None
                if complete_spell['duration'] > 0:
                    spell_timer = ca_timers.Timer(None)
                    spell_timer.from_pieces(
                             {'parent-name': opponent.name,
                              'rounds': complete_spell['duration'],
                              'string': ('SPELL "%s" AGAINST ME' %
                                         complete_spell['name']),
                              'fire_when': ca_timers.Timer.FIRE_ROUND_START
                              })

                delay_timer = ca_timers.Timer(None)

                actions = {}
                if spell_timer is not None:
                    actions['timer'] = spell_timer.rawdata
                if complete_spell['duration'] == 0:
                    actions['announcement'] = ('SPELL (%s) AGAINST ME FIRED' %
                                               complete_spell['name'])

                # Add 1 to the timer because the first thing the opponent will
                # see is a decrement (the caster only sees the decrement on the
                # _next_ round)
                delay_timer.from_pieces(
                         {'parent-name': opponent.name,
                          'rounds': (1 + complete_spell['casting time']),
                          'string': ('Waiting for "%s" spell to take affect' %
                                     complete_spell['name']),
                          'actions': actions,
                          'fire_when': ca_timers.Timer.FIRE_ROUND_START
                          })

                opponent.timers.add(delay_timer)

            return casting_timer
        else:
            # This is the 1st part of a 2-part action.  This 1st part of this
            # action asks questions of the user and sends the second part.
            # The 1st part isn't executed when playing back.

            if fight_handler is not None and fight_handler.world.playing_back:
                return None  # No timers

            # Assemble the spell from the ruleset's copy of it and the
            # Fighter's copy of it.

            spell_index = action['spell-index']
            spell = fighter.rawdata['spells'][spell_index]

            if spell['name'] not in GurpsRuleset.spells:
                self._window_manager.error(
                    ['Spell "%s" not in GurpsRuleset.spells' % spell['name']]
                )
                return None  # No timers
            complete_spell = copy.deepcopy(spell)
            complete_spell.update(GurpsRuleset.spells[spell['name']])

            # Duration

            if complete_spell['duration'] is None:
                title = 'Duration for (%s) - see (%s) ' % (
                        complete_spell['name'], complete_spell['notes'])
                height = 1
                width = len(title)
                duration = None
                while duration is None:
                    duration = self._window_manager.input_box_number(height,
                                                                     width,
                                                                     title)
                complete_spell['duration'] = duration

            # Cost

            if complete_spell['cost'] is None:
                # Assumes that area is built into cost that the user enters
                title = 'Cost to cast (%s) - see (%s) ' % (
                        complete_spell['name'], complete_spell['notes'])
                height = 1
                width = len(title)
                cost = None
                while cost is None:
                    cost = self._window_manager.input_box_number(height,
                                                                 width,
                                                                 title)
                complete_spell['cost'] = cost
            elif complete_spell['range'] == 'area':
                # Range for area spells
                #
                # NOTE: B236: Calculate the entire cost for a spell (for
                # instance, by multiplying cost for the size of the subject or
                # the area affected) before applying energy cost reductions for
                # high skill.

                title = 'Radius of spell effect (%s) in yards' % (
                        complete_spell['name'])
                height = 1
                width = len(title)
                diameter = None
                while diameter is None:
                    diameter = self._window_manager.input_box_number(height,
                                                                     width,
                                                                     title)
                complete_spell['cost'] *= diameter

            # Source For Power

            debug = ca_debug.Debug()
            debug.header1('Casting %s for %d' % (complete_spell['name'],
                                                 complete_spell['cost']))
            debug.print('Fighter stuff:')
            debug.pprint(fighter.rawdata['stuff'])

            if complete_spell['cost'] > 0:
                power_source_menu = []
                for index, item in enumerate(fighter.rawdata['stuff']):
                    if 'mana' in item and item['mana'] > 0:
                        debug.print('item %s has %d mana' % (item['name'],
                                                             item['mana']))
                        name = '%s (%d/%d mana)' % (item['name'],
                                                    item['mana'],
                                                    item['max mana'])
                        power_source_menu.append((name, index))
                if len(power_source_menu) > 0:
                    power_source_menu.append(('your fp', None))
                    power_source, ignore = self._window_manager.menu(
                        'Power Source For Spell',
                        power_source_menu)
                    if power_source is not None:
                        complete_spell['source'] = power_source

            # Casting time

            if (complete_spell['casting time'] is None or
                    complete_spell['casting time'] == 0):
                title = 'Seconds to cast (%s) - see (%s) ' % (
                                                    complete_spell['name'],
                                                    complete_spell['notes'])
                height = 1
                width = len(title)
                casting_time = None
                while casting_time is None:
                    casting_time = self._window_manager.input_box_number(
                            height, width, title)
                complete_spell['casting time'] = casting_time

            # Adjust cost and time for skill (M8, M9).  This loop looks at
            # modifications for skill level 15-19, 20-24, 25-29, etc.
            #
            # TODO (now): the effective skill includes a + for magery level
            skill = complete_spell['skill'] - 15
            maintenance_cost = (None if 'maintain' not in complete_spell else
                                complete_spell['maintain'])
            first_time = True
            while skill >= 0:
                if complete_spell['range'] != 'block':
                    complete_spell['cost'] -= 1
                    if maintenance_cost is not None:
                        maintenance_cost -= 1
                    skill -= 5
                # |first_time| is used because there's no time modification
                # for skill from 15-19 (i.e., the first time through this
                # loop).
                if first_time:
                    first_time = False
                elif complete_spell['range'] != 'missile':
                    # M8, under 'Magic Rituals' - Note: time reduction does
                    # not apply to missile spells.
                    casting_time = (complete_spell['casting time']/2.0) + 0.5
                    complete_spell['casting time'] = int(casting_time)
            if complete_spell['cost'] <= 0:
                complete_spell['cost'] = 0

            if maintenance_cost is not None:
                if maintenance_cost <= 0:
                    maintenance_cost = 0
                complete_spell['maintain'] = maintenance_cost

            if complete_spell['skill'] <= 9:
                complete_spell['casting time'] *= 2

            # Opponent?

            opponent = None
            if fight_handler is not None:
                opponent = fight_handler.get_opponent_for(fighter)

            spell_worked_on_opponent = False if opponent is None else True

            # Melee and Missile spells

            if complete_spell['range'] == 'melee':
                attack_menu = [('Success', True), ('Failure', False)]
                successful_attack, ignore = self._window_manager.menu(
                    'Make a Melee Attack', attack_menu)
                if not successful_attack:
                    spell_worked_on_opponent = False
            elif complete_spell['range'] == 'missile':
                # TODO (now): should be an option to use 'Innate Attack' skill
                # (default DX-4) or just regular attack.
                attack_menu = [('Success', True), ('Failure', False)]
                successful_attack, ignore = self._window_manager.menu(
                    'Make a Ranged Attack', attack_menu)
                if not successful_attack:
                    spell_worked_on_opponent = False

            # Save for opponent

            if spell_worked_on_opponent and len(complete_spell['save']) > 0:
                best_save = -100 # arbitrary but unlikely to show up
                roll_against = None
                for save in complete_spell['save']:
                    if (save in opponent.rawdata['current'] and
                            opponent.rawdata['current'][save] > best_save):
                        best_save = opponent.rawdata['current'][save]
                        roll_against = save
                if roll_against is not None:
                    save_menu = [(('SUCCESS: %s <= %d - margin of spell skill' % (
                                    roll_against, best_save)), True),
                                 (('FAILIRE: %s > %d - margin of spell skill' % (
                                    roll_against, best_save)), False)]
                    made_save, ignore = self._window_manager.menu(
                        ('%s must roll %s save against %s (skill %d)' % (
                            opponent.name,
                            roll_against,
                            complete_spell['name'],
                            complete_spell['skill'])),
                        save_menu)
                    if made_save:
                        spell_worked_on_opponent = False

            # Mark opponent?

            if spell_worked_on_opponent:
                opponent_timer_menu = [('yes', True), ('no', False)]
                timer_for_opponent, ignore = self._window_manager.menu(
                                        ('Mark %s with spell' % opponent.name),
                                        opponent_timer_menu)
                if not timer_for_opponent:
                    opponent = None

            # Send the action for the second part

            new_action = copy.deepcopy(action)
            new_action['complete spell'] = complete_spell
            new_action['part'] = 2

            if opponent is not None and spell_worked_on_opponent:
                new_action['opponent'] = {'name': opponent.name,
                                          'group': opponent.group}

            self.do_action(fighter, new_action, fight_handler)

            return None  # No new timers

    def __charge_powerstone(self,
                            param_dict  # dict: {'fighter': <fighter object>,
                                        #        'index': int, index into
                                        #                 'stuff' of powerstone
                            ):

        fighter = param_dict['fighter']
        index = param_dict['index']
        item = fighter.rawdata['stuff'][index]

        title = 'Add how much mana  to %s (%d/%d)' % (item['name'],
                                                      item['mana'],
                                                      item['max mana'])
        height = 1
        width = len(title)
        adj = self._window_manager.input_box_number(height, width, title)
        if adj is not None:
            item['mana'] += adj
            if item['mana'] > item['max mana']:
                item['mana'] = item['max mana']

    def __maintain_spell(self,
                         fighter,       # Fighter object
                         action,        # {'action-name': 'maintain-spell'
                                        #  'spell-index': <index in 'spells'>,
                                        #  'complete spell': <dict> # this
                                        #     is a combination of the spell
                                        #     in the character rawdata and
                                        #     the same spell from the
                                        #     ruleset
                                        #  'comment': <string>, # optional
                                        #  'part': 2 # optional
                         fight_handler  # FightHandler object
                         ):
        '''
        Action handler for GurpsRuleset.

        Handles the action of casting a magic spell.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        complete_spell = action['complete spell']

        # Charge the spell caster for the spell.

        if complete_spell['maintain'] > 0:
            self.do_action(fighter,
                           {'action-name': 'adjust-fp',
                            'adj': -complete_spell['maintain'],
                            'ignore-dr': True},
                           fight_handler,
                           logit=False)

        # Duration Timer

        # If the spell lasts any time at all, put a timer up so that we see
        # that it's active

        duration_timer = None
        if complete_spell['duration'] > 0:
            duration_timer = ca_timers.Timer(None)
            duration_timer.from_pieces(
                       {'parent-name': fighter.name,
                        'rounds': complete_spell['duration'],
                        'string': ('MAINTAIN SPELL (%s) ACTIVE' %
                                   complete_spell['name']),
                        'fire_when': ca_timers.Timer.FIRE_ROUND_START,
                        'data': {'spell': complete_spell}
                        })

        # Opponent's Timers

        if 'opponent' in action and fight_handler is not None:
            ignore, opponent = fight_handler.get_fighter_object(
                                            action['opponent']['name'],
                                            action['opponent']['group'])
            spell_timer = None
            if complete_spell['duration'] > 0:
                spell_timer = ca_timers.Timer(None)
                spell_timer.from_pieces(
                         {'parent-name': opponent.name,
                          'rounds': complete_spell['duration'],
                          'string': ('SPELL "%s" AGAINST ME' %
                                     complete_spell['name']),
                          'fire_when': ca_timers.Timer.FIRE_ROUND_START
                          })

            delay_timer = ca_timers.Timer(None)

            actions = {}
            if spell_timer is not None:
                actions['timer'] = spell_timer.rawdata
            if complete_spell['duration'] == 0:
                actions['announcement'] = ('SPELL (%s) AGAINST ME FIRED' %
                                           complete_spell['name'])

            # Add 1 to the timer because the first thing the opponent will
            # see is a decrement (the caster only sees the decrement on the
            # _next_ round)
            delay_timer.from_pieces(
                     {'parent-name': opponent.name,
                      'rounds': (1 + complete_spell['casting time']),
                      'string': ('Waiting for "%s" spell to take affect' %
                                 complete_spell['name']),
                      'actions': actions,
                      'fire_when': ca_timers.Timer.FIRE_ROUND_START
                      })

            opponent.timers.add(delay_timer)

        return duration_timer

    def __change_posture(self,
                         fighter,          # Fighter object
                         action,           # {'action-name': 'change-posture',
                                           #  'posture': <string> # posture
                                           #        from GurpsRuleset.posture
                                           #  'comment': <string>, # optional
                         fight_handler     # FightHandler object (ignored)
                         ):
        '''
        Action handler for GurpsRuleset.

        Changes the posture of the Fighter.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.rawdata['posture'] = action['posture']
        self.reset_aim(fighter)

        # Timer

        timer = ca_timers.Timer(None)

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1,
                           'string': ['Change posture',
                                      ' NOTE: crouch 1st action = free',
                                      '       crouch->stand = free',
                                      '       kneel->stand = step',
                                      ' Defense: any',
                                      ' Move: none'],
                           'fire_when': ca_timers.Timer.FIRE_ROUND_START
                           })

        return timer


    def __check_for_unconscious(self,
                                fighter,            # Fighter object
                                fight_handler,      # FightHandler object
                                adjusted_hp=None    # int: HP to use to check
                                ):
        '''
        Checks to see if a Fighter should go unconscious
        Returns: True if we checked, False otherwise
        '''

        if adjusted_hp is None:
            adjusted_hp = fighter.rawdata['current']['hp']

        if fighter.timers.found_timer_string(
                GurpsRuleset.checked_for_unconscious_string):
            return False

        playing_back = (False if fight_handler is None else
                        fight_handler.world.playing_back)

        if (fighter.is_conscious() and adjusted_hp <= 0 and not playing_back):
            unconscious_roll = fighter.rawdata['current']['ht']
            if 'High Pain Threshold' in fighter.rawdata['advantages']:
                unconscious_roll += 3

                menu_title = (
                    '%s: HP < 0: roll <= HT+3 (%d) or pass out (B327,B59)' %
                    (fighter.name, unconscious_roll))
            else:
                menu_title = (
                    '%s: HP < 0: roll <= HT (%d) or pass out (B327)' %
                    (fighter.name, unconscious_roll))

            pass_out_menu = [
                    ('Succeeded (roll <= %d) - NOT unconscious' %
                        unconscious_roll, True),
                    ('Failed (roll > %d) - unconscious' %
                        unconscious_roll, False)]
            made_ht_roll, ignore = self._window_manager.menu(menu_title,
                                                             pass_out_menu)

            if not made_ht_roll:
                self.do_action(fighter,
                               {'action-name': 'set-consciousness',
                                'level': ca_fighter.Fighter.UNCONSCIOUS},
                               fight_handler)
            return True

        return False

    def __damage_FP(self,
                    param    # {'view': xxx, 'view-opponent': xxx,
                             #  'current': xxx, 'current-opponent': xxx,
                             #  'fight_handler': <fight handler> } where
                             # xxx are Fighter objects
                    ):
        '''
        Command ribbon method.

        Figures out from whom to remove fatigue points and removes them (via
        an action).

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if param is None:
            return True
        elif param['view'] is not None:
            fp_recipient = param['view']
        elif param['current-opponent'] is not None:
            fp_recipient = param['current-opponent']
        elif param['current'] is not None:
            fp_recipient = param['current']
        else:
            return True

        title = 'Reduce (%s\'s) FP By...' % fp_recipient.name
        height = 1
        width = len(title)
        adj = self._window_manager.input_box_number(height, width, title)
        if adj is None:
            return True
        adj = -adj  # NOTE: SUBTRACTING the adjustment

        if adj < 0:
            comment = '(%s) lost %d FP' % (fp_recipient.name, -adj)
        else:
            comment = '(%s) regained %d FP' % (fp_recipient.name, adj)

        fight_handler = (None if 'fight_handler' not in param
                         else param['fight_handler'])
        self.do_action(fp_recipient,
                       {'action-name': 'adjust-fp',
                        'adj': adj,
                        'comment': comment},
                       fight_handler)

        return True  # Keep going

    def __do_adjust_fp(self,
                       fighter,       # Fighter object
                       action,        # {'action-name': 'adjust-fp',
                                      #  'adj': <int> # number to add to FP
                                      #  'comment': <string>, # optional
                                      #  'ignore-dr': <bool> # optional
                       fight_handler  # FightHandler object (for logging)
                       ):
        '''
        Action handler for GurpsRuleset.

        Adjusts the fatigue points of a Fighter and manages all of the side-
        effects associated therewith.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part of the action
            # actually perfoms all the GurpsRuleset-specific actions and
            # side-effects of aiming the Fighter's current weapon.

            # See B426 for consequences of loss of FP
            adj = action['adj']  # Adj is likely negative

            # If FP go below zero, you lose HP along with FP (B328)
            fp_adj = 0
            if adj < 0 and -adj > fighter.rawdata['current']['fp']:
                fp_adj = adj
                if fighter.rawdata['current']['fp'] > 0:
                    fp_adj += fighter.rawdata['current']['fp']

            if fp_adj < 0:
                self.do_action(fighter,
                               {'action-name': 'adjust-hp',
                                'adj': fp_adj,
                                'quiet': True},
                               fight_handler,
                               logit=False)

            fighter.rawdata['current']['fp'] += adj

            # (B328)
            if (fighter.rawdata['current']['fp'] <=
                    -fighter.rawdata['permanent']['fp']):
                self.do_action(fighter,
                               {'action-name': 'set-consciousness',
                                'level': ca_fighter.Fighter.UNCONSCIOUS},
                               fight_handler,
                               logit=False)
            return None  # No timer

        else:
            # This is the 1st part of a 2-part action.  This part of the
            # action asks questions of the user and sends the second part
            # The 1st part isn't executed when playing back.

            # Adjust for armor
            dr = 0
            dr_text_array = []
            use_armor = False
            adj = action['adj']  # Adj is likely negative
            quiet = False if 'quiet' not in action else action['quiet']

            if 'ignore-dr' not in action or not action['ignore-dr']:
                armor_index_list = fighter.get_current_armor_indexes()
                armor_list = fighter.get_items_from_indexes(armor_index_list)
                window_text = [
                    [{'text': ('...%s' % fighter.name),
                      'mode': curses.A_NORMAL}],
                    [{'text': '', 'mode': curses.A_NORMAL}]
                               ]

                for armor in armor_list:
                    dr += armor['type']['armor']['dr']
                    dr_text_array.append(armor['name'])

                if 'Damage Resistance' in fighter.rawdata['advantages']:
                    # GURPS rules, B46, 5 points per level of DR advantage
                    dr += (fighter.rawdata['advantages']['Damage Resistance']/5)
                    dr_text_array.append('DR Advantage')

                if not quiet and dr != 0:
                    use_armor_menu = [('yes', True), ('no', False)]
                    use_armor, ignore = self._window_manager.menu(
                            'Use Armor\'s DR?', use_armor_menu)

                if use_armor:
                    if dr >= -adj:
                        window_text = [
                            [{'text': 'The armor absorbed all the damage',
                              'mode': curses.A_NORMAL}]
                        ]
                        self._window_manager.display_window(
                                ('Did *NO* damage to %s' % fighter.name),
                                window_text)
                        return ca_ruleset.Ruleset.HANDLED_OK

                    original_adj = adj

                    adj += dr
                    action['adj'] = adj

                    dr_text = '; '.join(dr_text_array)
                    window_text.append(
                        [{'text': ('%s was wearing %s (total dr:%d)' % (
                                                                  fighter.name,
                                                                  dr_text,
                                                                  dr)),
                          'mode': curses.A_NORMAL}]
                                      )
                    window_text.append(
                        [{'text': ('so adj(%d) - dr(%d) = damage (%d)' % (
                                                                  -original_adj,
                                                                  dr,
                                                                  -adj)),
                          'mode': curses.A_NORMAL}]
                                      )

                self._window_manager.display_window(
                                    ('Did %d fp damage to...' % -adj),
                                    window_text)

            # Send the action for the second part

            new_action = copy.deepcopy(action)
            new_action['part'] = 2
            self.do_action(fighter, new_action, fight_handler)

            return None  # No timer

    def __do_adjust_shock(self,
                          fighter,       # Fighter object
                          action,        # {'action-name': 'shock',
                                         #  'value': <int> # new shock level
                                         #  'comment': <string>, # optional
                          fight_handler  # FightHandler object (ignored)
                          ):
        '''
        Action handler for GurpsRuleset.

        Changes the Fighter's shock value.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.rawdata['shock'] = action['value']
        return None  # No timer

    def __do_aim(self,
                 fighter,       # Fighter object
                 action,        # {'action-name': 'aim',
                                #  'braced': <bool> # see B364
                                #  'comment': <string>, # optional
                                #  'part': 2          # optional }
                 fight_handler  # FightHandler object
                 ):
        '''
        Action handler for GurpsRuleset.

        Peforms the 'aim' action.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part of the action
            # actually perfoms all the GurpsRuleset-specific actions and
            # side-effects of aiming the Fighter's current weapon.

            rounds = fighter.rawdata['aim']['rounds']
            if rounds == 0:
                fighter.rawdata['aim']['braced'] = action['braced']
                fighter.rawdata['aim']['rounds'] = 1
            elif rounds < 3:
                fighter.rawdata['aim']['rounds'] += 1

            # Timer

            timer = ca_timers.Timer(None)
            timer.from_pieces(
                    {'parent-name': fighter.name,
                     'rounds': 1,
                     'string': [('Aim%s' % (' (braced)' if action['braced']
                                            else '')),
                                ' Defense: any loses aim',
                                ' Move: step'],
                     'fire_when': ca_timers.Timer.FIRE_ROUND_START
                     })

            return timer

        else:
            # This is the 1st part of a 2-part action.  This part of the
            # action asks questions of the user and sends the second part
            # The 1st part isn't executed when playing back.

            if fight_handler is not None and fight_handler.world.playing_back:
                return None  # No timers

            if fight_handler is not None:
                if fighter.rawdata['opponent'] is None:
                    fight_handler.pick_opponent()

            # Send the action for the second part

            new_action = copy.deepcopy(action)
            new_action['part'] = 2
            self.do_action(fighter, new_action, fight_handler)

            return None  # No timer

    def __do_attack(self,
                    fighter,        # Fighter object
                    action,         # {'action-name': 'attack' |
                                    #   'all-out-attack' | 'move-and-attack'
                                    #  'weapon-index': <int> or None
                                    #  'comment': <string>, # optional
                    fight_handler   # FightHandler object
                    ):
        '''
        Action handler for GurpsRuleset.

        Does the ruleset-specific stuff for an attack.  MOSTLY, that's just
        creating the timer, though, since I don't currently have the code roll
        anything (putting this in a comment will come back to bite me when I
        inevitably add that capability to the code but not read and repair the
        comments).

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        debug = ca_debug.Debug()
        debug.header1('__do_attack')
        debug.pprint(action)

        weapons = fighter.get_current_weapons()
        weapon = (None if fighter.rawdata['current-weapon'] >= len(weapons) else
                  weapons[fighter.rawdata['current-weapon']])

        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part
            # actually perfoms all the GurpsRuleset-specific actions
            # and side-effects of doing whatever.

            self.reset_aim(fighter)

            # Get some rawdata

            if weapon is None:
                return None  # No timer

            # Move

            move = fighter.rawdata['current']['basic-move']
            move_strings = []
            move_string = None
            move_and_attack = False

            # Fatigue points: B426
            no_fatigue_penalty = self.get_option('no-fatigue-penalty')
            if ((no_fatigue_penalty is None or not no_fatigue_penalty) and
                    (fighter.rawdata['current']['fp'] <
                        (fighter.rawdata['permanent']['fp'] / 3))):
                move_strings.append('half (FP:B426)')
                move /= 2

            # Getting down to brass tacks...

            if action['action-name'] == 'attack':
                title = 'Attack'
                defense = 'any'
                move_string = 'step'
                move = 0
            elif action['action-name'] == 'all-out-attack':
                title = 'All out attack'
                defense = 'NONE'
                move_strings.append('half, BEFORE attack and only FORWARD (all-out-attack)')
                move /= 2
            elif action['action-name'] == 'move-and-attack':
                title = 'Move & Attack'
                defense = 'Dodge,block'
                move_strings.append('half (move-and-attack)')
                move /= 2
                move_and_attack = True
            else:
                title = '<UNKNOWN ACTION %s>' % action['action-name']
                defense = '<UNKNOWN>'
                move_string = '<UNKNOWN>'

            if move_string is None:
                move_string = ' + '.join(move_strings)
                move_string = ' %s = %d' % (move_string, move)

            text = ['%s' % title,
                    ' Defense: %s' % defense,
                    ' Move: %s' % move_string]

            # To-Hit, etc.

            opponent = (None if fight_handler is None else
                    fight_handler.get_opponent_for(fighter))

            disallowed_modes = self.get_disallowed_modes(
                    fighter, action['all-out-option'])
            for weapon in weapons:
                modes = weapon.get_attack_modes()
                for mode in modes:
                    if mode in disallowed_modes:
                        continue
                    text.append(' %s' % mode)
                    shots_fired = (None if 'shots_fired' not in action else
                                   action['shots_fired'])

                    to_hit, ignore_why = self.get_to_hit(
                            fighter,
                            opponent,
                            weapon,
                            mode,
                            shots_fired,
                            moving=move_and_attack,
                            all_out_option=action['all-out-option'])

                    crit, fumble = self.__get_crit_fumble(to_hit)
                    text.append('  %s to-hit: %d, crit <= %d, fumble >= %d' % (
                        weapon.rawdata['name'], to_hit, crit, fumble))

            # Damage mods

            if action['all-out-option'] == GurpsRuleset.ALL_OUT_SUPPRESSION_FIRE:
                text.append('NOTE: See B410 for rawdata of suppression fire')
            elif action['all-out-option'] == GurpsRuleset.ALL_OUT_FEINT:
                text.extend = ['FEINT:',
                               ' Contest of melee skill vs melee/unarmed/',
                               '   cloak/shield skilli.  Subtract margin',
                               '   of victory from opponent\'s defense']

            # Timer

            timer = ca_timers.Timer(None)
            # TODO (now): Mods are actual total values.  They _should_ be delta
            #   values but one of the mods caps the to-hit to 9.

            timer.from_pieces({'parent-name': fighter.name,
                               'rounds': 1,
                               'string': text,
                               'fire_when': ca_timers.Timer.FIRE_ROUND_START
                               })
            if 'shots_fired' in action:
                timer.rawdata['info'] = {'shots_fired': action['shots_fired']}
            if action['action-name'] == 'move-and-attack':
                timer.rawdata['move-and-attack'] = True
            # TODO: should put this isn rawdata['data']['all-out-option']
            if 'all-out-option' in action:
                timer.rawdata['all-out-option'] = action['all-out-option']

            debug.print('Sending this timer')
            debug.pprint(timer.rawdata)

            return timer

        else:
            # This is the 1st part of a 2-part action.  This part of
            # the action asks questions of the user and sends the
            # second part.  The 1st part isn't executed when playing
            # back.
            # Don't do the first part when playing back.
            if (fight_handler is not None and
                    fight_handler.world.playing_back):
                return None  # No timers

            if fight_handler is not None:
                if fighter.rawdata['opponent'] is None:
                    fight_handler.pick_opponent()

            shots_fired = self.__get_shots_fired(fighter)
            debug.print('shots fired: %d' % shots_fired)

            # All-out attack (B324)

            all_out_option = None
            debug.print('weapon: %s' % ('NONE' if weapon is None else weapon.name))
            if weapon is not None and action['action-name'] == 'all-out-attack':
                holding = fighter.what_are_we_holding()
                debug.print('Holding:')
                debug.pprint(holding)

                all_out_menu = [ ]

                # TODO (now): I haven't modeled 2 weapon attacks well.  For
                #   missile weapons, you need extra attack or dual weapon
                #   attack.  For melee attacks, you need all-out attack or
                #   rapid strike.  Extra Attack allows 2 attacks.  Add dual
                #   weapon attack, you can exchange one normal attack for a DWA
                #   (or a Rapid Strike in the case of a melee attack). You
                #   could fire with both revolvers with a DWA by spending one
                #   of your attacks and then kick a target with your other
                #   attack.

                number_of_hands = 2
                if (holding['melee'] + holding['natural_weapon']) >= number_of_hands:
                    # NOTE: both weapons have to be ready but I don't model that.
                    debug.print('adding double')
                    all_out_menu.append(
                            ('double',
                             GurpsRuleset.ALL_OUT_DOUBLE_ATTACK))
                if weapon.is_melee_strength_based_weapon():
                    debug.print('adding strong')
                    all_out_menu.append(
                            ('strong',
                             GurpsRuleset.ALL_OUT_STRONG_ATTACK))
                if shots_fired >= 5:
                    debug.print('adding suppression fire')
                    all_out_menu.append(
                            ('suppression fire',
                             GurpsRuleset.ALL_OUT_SUPPRESSION_FIRE))
                if weapon.is_melee_weapon():
                    debug.print('adding feint')
                    all_out_menu.append(('feint',GurpsRuleset.ALL_OUT_FEINT))
                if weapon.is_ranged_weapon():
                    debug.print('adding determined range')
                    all_out_menu.append(
                            ('determined (ranged: %s)' % weapon.name,
                             GurpsRuleset.ALL_OUT_RANGED_DETERMINED_ATTACK))
                if weapon.is_melee_weapon():
                    debug.print('adding determined melee')
                    all_out_menu.append(
                            ('determined (melee: %s)' % weapon.name,
                             GurpsRuleset.ALL_OUT_MELEE_DETERMINED_ATTACK))

                all_out_menu = sorted(all_out_menu, key=lambda x: x[0].upper())
                title = 'What All-Out Attack Mode Are You Using?'
                all_out_option, ignore = self._window_manager.menu(title,
                                                                   all_out_menu)

            # TODO (eventually): In other event, maybe, show the tables and such

            # Send the action for the second part

            # Do a deepcopy for the second part to copy the comment --
            # that's what gets displayed for the history command.

            new_action = copy.deepcopy(action)
            if shots_fired > 1:
                new_action['shots_fired'] = shots_fired
            if all_out_option is not None:
                new_action['bonus'] = all_out_option
            new_action['all-out-option'] = all_out_option
            new_action['part'] = 2
            self.do_action(fighter, new_action, fight_handler)

            return None # No timers for part 1

    def __do_nothing(self,
                     fighter,      # Fighter object
                     action,       # {'action-name': 'concentrate' |
                                   #    'evaluate' |
                                   #    'feint' | 'move' | 'nothing' |
                                   #    'pick-opponent' | 'use-item' |
                                   #    'user-defined',
                                   #  'comment': <string>, # optional
                                   #
                                   # NOTE: Some actions have other
                                   # parameters used buy |Ruleset|
                                   #
                     fight_handler  # FightHandler object (ignored)
                     ):
        '''
        Action handler for GurpsRuleset.

        Does nothing but create the appropriate timer for the action.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        # Timer

        timer = ca_timers.Timer(None)

        if 'action-name' not in action:
            return None

        if action['action-name'] == 'nothing':
            text = ['Do nothing', ' Defense: any', ' Move: none']

        elif action['action-name'] == 'move':
            self.reset_aim(fighter)

            move = fighter.rawdata['current']['basic-move']
            no_fatigue_penalty = self.get_option('no-fatigue-penalty')
            if ((no_fatigue_penalty is None or not no_fatigue_penalty) and
                    (fighter.rawdata['current']['fp'] <
                        (fighter.rawdata['permanent']['fp'] / 3))):
                move_string = 'half=%d (FP:B426)' % (move/2)
            else:
                move_string = 'full=%d' % move
            text = ['Move', ' Defense: any', ' Move: %s' % move_string]

        elif action['action-name'] == 'feint':
            self.reset_aim(fighter)
            text = ['Feint',
                    ' Contest of melee weapon or DX',
                    '   subtract score from opp',
                    '   active defense next turn',
                    '   (for both, if all-out-attack)',
                    ' Defense: any, parry *',
                    ' Move: step']

        elif action['action-name'] == 'evaluate':
            text = ['Evaluate', ' Defense: any', ' Move: step']

        elif action['action-name'] == 'concentrate':
            text = ['Concentrate', ' Defense: any w/will roll', ' Move: step']

        elif action['action-name'] == 'use-item':
            self.reset_aim(fighter)
            if 'item-name' in action:
                text = [('Use %s' % action['item-name']),
                        ' Defense: (depends)',
                        ' Move: (depends)']
            else:
                text = ['Use item',
                        ' Defense: (depends)',
                        ' Move: (depends)']

        elif action['action-name'] == 'user-defined':
            self.reset_aim(fighter)
            text = ['User-defined action']

        elif action['action-name'] == 'pick-opponent':
            self.reset_aim(fighter)
            return None

        else:
            text = ['<<UNHANDLED ACTION: %s' % action['action-name']]

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1,
                           'string': text,
                           'fire_when': ca_timers.Timer.FIRE_ROUND_START
                           })

        return timer

    def __do_reload(self,
                    fighter,  # Fighter object
                    action,   # {'action-name': 'reload',
                              #  'notimer': <bool>, # whether to
                              #                       return a timer
                              #                       for the fighter
                              #                       -- optional
                              #  'comment': <string>, # optional
                              #  'quiet': <bool>    # use defaults for
                              #                       all user
                              #                       interactions
                              #                       -- optional
                              #  'time': <duration>
                              #  'part': 2          # optional }
                              # }
                    fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for GurpsRuleset.

        Handles reloading a weapon.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part of the action
            # actually perfoms all the GurpsRuleset-specific actions and
            # side-effects of reloading the Fighter's current weapon.  Note
            # that a lot of the obvious part is done by the base class Ruleset.

            self.reset_aim(fighter)

            # Timer

            timer = ca_timers.Timer(None)
            timer.from_pieces(
                {'parent-name': fighter.name,
                 'rounds': action['time'],
                 'string': 'RELOADING',
                 'fire_when': ca_timers.Timer.FIRE_ROUND_START
                 })

            timer.mark_owner_as_busy()  # When reloading, the owner is busy

            return timer
        else:
            # This is the 1st part of a 2-part action.  This part of the
            # action asks questions of the user and sends the second part
            # The 1st part isn't executed when playing back.

            if fight_handler is not None and fight_handler.world.playing_back:
                return None  # No timer

            weapons = fighter.get_current_weapons()
            # You need to only have 1 weapon if you're reloading (you need an
            # empty hand to reload)
            if weapons is None or len(weapons) != 1:
                return None  # No timer

            weapon = weapons[0]
            if not weapon.uses_ammo():
                return None  # No timer

            # If we can reload, how long will it take?

            reload_time = weapon.rawdata['reload']

            quiet = False if 'quiet' not in action else action['quiet']
            if not quiet:
                # B194: fast draw
                if 'Fast-Draw (Ammo)' in fighter.rawdata['skills']:
                    skill_menu = [('made SKILL roll', True),
                                  ('did NOT make SKILL roll', False)]

                    # B43: combat reflexes
                    if 'Combat Reflexes' in fighter.rawdata['advantages']:
                        title = (
                            'roll <= %d (fast-draw skill + combat reflexes)' %
                            fighter.rawdata['skills']['Fast-Draw (Ammo)'] + 1)
                    else:
                        title = (
                            'roll <= fast-draw skill (%d)' %
                            fighter.rawdata['skills']['Fast-Draw (Ammo)'])

                    made_skill_roll, ignore = self._window_manager.menu(
                            title, skill_menu)

                    if made_skill_roll:
                        reload_time -= 1

            new_action = copy.deepcopy(action)
            new_action['time'] = reload_time
            new_action['part'] = 2
            if 'notimer' in action:
                new_action['notimer'] = action['notimer']

            # TODO (eventually): the action should be launched by a timer
            self.do_action(fighter, new_action, fight_handler)

            return None  # No timer

    def __draw_weapon(self,
                      fighter,          # Fighter object
                      action,           # {'action-name': 'draw-weapon',
                                        #  'weapon-index': <int> # index in
                                        #       fighter.rawdata['stuff'],
                                        #       None drops weapon
                                        #  'comment': <string>, # optional
                      fight_handler,    # FightHandler object (ignored)
                      ):
        '''
        Action handler for GurpsRuleset.

        Does the ruleset-specific stuff to draw or holster a weapon.  The
        majority of the work for this is actually done in the base class.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = ca_timers.Timer(None)

        # TODO (now): make this a 2-part action where the fast-draw is checked
        # in the first part and the draw (and timer) is done in the second part.
        #
        # if 'Fast-Draw (Pistol)' in fighter.rawdata['skills']:
        #    skill_menu = [('made SKILL roll', True),
        #                  ('did NOT make SKILL roll', False)]
        #            # B43: combat reflexes
        #            if 'Combat Reflexes' in fighter.rawdata['advantages']:
        #                title = (
        #                    'roll <= %d (fast-draw skill + combat reflexes)' %
        #                    fighter.rawdata['skills']['Fast-Draw (Ammo)'] + 1)
        #            else:
        #                title = (
        #                    'roll <= fast-draw skill (%d)' %
        #                    fighter.rawdata['skills']['Fast-Draw (Ammo)'])
        #    made_skill_roll, ignore = self._window_manager.menu(
        #        ('roll <= fast-draw skill (%d)' %
        #                fighter.rawdata['skills']['Fast-Draw (Ammo)']),
        #        skill_menu)
        #
        #    if made_skill_roll:
        #        ...

        item = fighter.equipment.get_item_by_index(action['weapon-index'])
        weapon = ca_equipment.Weapon(item)
        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1,
                           'string': ['Draw %s' % weapon.rawdata['name'],
                                      ' Defense: any',
                                      ' Move: step'],
                           'fire_when': ca_timers.Timer.FIRE_ROUND_START
                           })
        return timer

    def __get_current_all_out_attack_option(self,
                                            fighter # Fighter objet
                                            ):

        debug = ca_debug.Debug()
        debug.header3('__get_current_all_out_attack_option for %s' %
                fighter.name)

        all_out_option = None
        timers = fighter.timers.get_all()
        # NOTE: if there's more than one timer with this option, it'll pick
        #   up the last one.  That makes sense -- it's the most recent option
        for timer in timers:
            debug.pprint(timer.rawdata)
            if 'all-out-option' in timer.rawdata:
                all_out_option = timer.rawdata['all-out-option']
        return all_out_option

    def __get_crit_fumble(self,
                          skill_level   # int
                          ):
        '''
        returns tuple: (crit, fumble) which are the rolls below (or equal to)
        establishes a critical success and above (or equal to) establishes a
        critical failure
        '''
        # B347
        if skill_level >= 16:
            crit = 6
        elif skill_level >= 15:
            crit = 5
        else:
            crit = 4

        if skill_level >= 16:
            fumble = 18
        elif skill_level >= 7:
            fumble = 17
        else:
            fumble = skill_level + 10

        return crit, fumble

    def __get_damage_one_case(
            self,
            fighter,    # Fighter object
            weapon,     # Weapon object
            mode,       # string: 'thrust weapon', 'swung weapon', ...
            ):
        debug = ca_debug.Debug()
        debug.header1('__get_damage_one_case: %s' % weapon.name)
        '''
        Damage is described in the following ways:

        {'type': {'swung_weapon': {'damage': {'st': 'sw', 'plus':#, 'type': 'cut' or ...
        {'type': {'thrust weapon': {'damage': {'st': 'thr', 'plus':#, 'type': 'imp' or ...

        # laser pistol, bite, sick stick
        {'damage': {'dice': {'plus':#, 'num_dice':#, 'type': 'pi' or ...
        {'clip': {'damage': {...}

        if there's a clip, use that damage else use the intrinsic damage of
        the weapon

        knife: damage next to skill whether swung, thrust, or thrown
        gun: damage next to skill unless clip, then use that
        brass knuckles: damage is thrust only
        sick stick: damage is dice

        '''
        results = []
        why = []

        # Get the method of calculating the damage
        damage, notes = weapon.get_damage_next_shot(mode)
        debug.print('Damage formula')
        debug.pprint(damage)

        if 'st' in damage:
            debug.print('found ST')

            st = fighter.rawdata['current']['st']

            attack_type = damage['st']  # 'sw' or 'thr'
            # This is 'cut', 'imp', 'pi' or ...
            damage_type_str = self.__get_damage_type_str(damage['type'])
            results.append(
                {'attack_type': attack_type, # 'thr', 'sw'
                 'num_dice':
                    GurpsRuleset.melee_damage[st][attack_type]['num_dice'],
                 'plus': GurpsRuleset.melee_damage[st][attack_type]['plus'] +
                    damage['plus'],
                 'damage_type': damage_type_str,
                 'notes': notes})

            why.append('Weapon %s, %s' % (weapon.rawdata['name'], mode))
            why.append('  Damage: %s%+d' % ( attack_type, damage['plus']))
            why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                       (st,
                        GurpsRuleset.melee_damage[st][attack_type]['num_dice'],
                        GurpsRuleset.melee_damage[st][attack_type]['plus']))
            if damage['plus'] != 0:
                # TODO (eventually): attack_type = 'sw' and there's none of that in |damage|
                why.append('  %+d for the weapon' % damage['plus'])

            # All-Out Attack can affect damage
            # a "strong" attack does the better of +2 damage or +1 per die

            all_out_option = self.__get_current_all_out_attack_option(fighter)
            debug.print('all_out_option: %r' % all_out_option)
            all_out_attack_plus = 0
            if (all_out_option is not None and
                    all_out_option == GurpsRuleset.ALL_OUT_STRONG_ATTACK):
                num_dice_damage = (
                        GurpsRuleset.melee_damage[st][attack_type]['num_dice'])
                all_out_attack_plus = (
                        num_dice_damage if num_dice_damage > 2 else 2)
                why.append('  %+d for all-out attack, strong' %
                        all_out_attack_plus)

            # Final tally

            why.append('  ...damage: %dd%+d' %
                       (GurpsRuleset.melee_damage[st][attack_type]['num_dice'],
                        GurpsRuleset.melee_damage[st][attack_type]['plus'] +
                        damage['plus'] +
                        all_out_attack_plus))
        elif 'dice' in damage:
            # if we're here, the damage is based on the weapon and not the
            # capabilities of the wielder.  Therefore, the damage may be a
            # function of the ammo in the clip.  Check that.

            # {'damage': {'dice': {'plus':#, 'num_dice':#, 'type': 'pi' or ...
            debug.print('found DICE')
            damage_type_str = self.__get_damage_type_str(
                    damage['dice']['type'])
            results.append(
                {'attack_type': None,
                 'num_dice': damage['dice']['num_dice'],
                 'plus': damage['dice']['plus'],
                 'damage_type': damage_type_str,
                 'notes': notes})
            why.append('Weapon %s, %s' % (weapon.rawdata['name'], mode))
            why.append('  Damage: %dd%+d' % (damage['dice']['num_dice'],
                                             damage['dice']['plus']))

            # Shotguns need more explanation B373
            # TODO (now): B373 - one hit per multiple of 'rcl'.  We're treating rcl as 1,
            #   here.
            debug.print('is ranged?')
            if weapon.is_ranged_weapon():
                debug.print('*IS* ranged')
                pellets_per_shot = weapon.get_param('pellets_per_shot',
                                                    'ranged weapon')
                if pellets_per_shot is None:
                    pellets_per_shot = 1
                debug.print('pellets_per_shot: %d' % pellets_per_shot)
                if pellets_per_shot > 1:
                    # shotgun
                    mult_factor = int(pellets_per_shot / 2)

                    why.append('    Shotgun range is 50/125 (so 5 yards for CLOSE range)')
                    why.append('    Farther than 5 yards, number of pellets that hit is')
                    why.append('      1 (on hit success) + margin of HIT success')
                    why.append('    Closer than 5 yards, DR *= %d, but...' % mult_factor)
                    why.append('      ...Damage: %dd%+d per shot taken' % (
                        (mult_factor * damage['dice']['num_dice']),
                        (mult_factor * damage['dice']['plus'])))
                    why.append('    Dodge success removes 1 pellet + 1 pellet per margin ')
                    why.append('      of success (closer than 5 yards, it\'s the shot,')
                    why.append('      not the pellet that\'s dodged)')
                    why.append('    See B409, B373 (rapid fire), and B375 (dodge)')
                elif ('shots_per_round' in weapon.rawdata and
                        weapon.rawdata['shots_per_round'] > 1):
                    # automatic weapon
                    why.append('    Number of bullets that hit is 1 (on hit success)')
                    why.append('      + margin of HIT success')
                    why.append('    Dodge success removes 1 pellet + 1 pellet per margin ')
                    why.append('      of success')
                    why.append('    See B373 (rapid fire) and B375 (dodge)')

        return results, why

    def __get_damage_type_str(self,
                              damage_type   # <string> key in
                                            #   GurpsRuleset.damage_mult
                              ):
        '''
        Expands the short-hand version of damage type with the long form (that
        includes the damage multiplier).

        Returns the long form string.
        '''
        if damage_type in GurpsRuleset.damage_mult:
            damage_type_str = '%s=x%.1f' % (
                                        damage_type,
                                        GurpsRuleset.damage_mult[damage_type])
        else:
            damage_type_str = '%s' % damage_type
        return damage_type_str


    def _get_missing_skill_names(self,
                                 fighter,   # Fighter object
                                 weapon     # dict: item in Fighter's equipment
                                 ):
        '''
        If the fighter doesn't have SOME skill in at least one of the modes
        that this weapon has, this method returns the name of at least one good
        skill for the fighter to have.
        '''
        debug = ca_debug.Debug()
        debug.header1('_get_missing_skill_names')
        debug.print('weapon:')
        debug.pprint(weapon)
        missing_skills = []

        if not ca_equipment.Weapon.is_weapon(weapon):
            debug.print('** Not a weapon **')
            return missing_skills

        # Just going to add the easiest skill name

        weapon_obj = ca_equipment.Weapon(weapon)
        best_skill = None
        for mode in weapon_obj.get_attack_modes():
            if mode not in weapon['type']:
                continue
            if 'skill' not in weapon['type'][mode]:
                continue
            for name, value in weapon['type'][mode]['skill'].items():
                if name.lower() in fighter.rawdata['current']:
                    continue # not interested if it's an attribute (e.g., DX)

                if name in fighter.rawdata['skills']:
                    best_skill = None
                    break # not interested if fighter has ANY skill in weapon

                if best_skill is None or value > best_skill['value']:
                    best_skill = {'name': name, 'value': value}

        # Add all skills that are equal to the best

        if best_skill is not None:
            for mode in weapon_obj.get_attack_modes():
                if mode not in weapon['type']:
                    continue
                if 'skill' not in weapon['type'][mode]:
                    continue
                for name, value in weapon['type'][mode]['skill'].items():
                    if name in missing_skills:
                        continue # only add a skill once

                    if name.lower() in fighter.rawdata['current']:
                        continue # not interested if it's an attribute (e.g., DX)

                    if name in fighter.rawdata['skills']:
                        break # not interested if fighter has ANY skill in weapon

                    if value == best_skill['value']:
                        missing_skills.append(name)

        return missing_skills

    def __get_shots_fired(self,
                          fighter   # Fighter object
                          ):
        debug = ca_debug.Debug()

        # Get the current weapon
        weapons = fighter.get_current_weapons()
        weapon = None # current weapon

        # Multiple shots per round describes machine guns or shotguns
        weapon_needs_multiple_shot_handling = True

        if (weapons is None or
                fighter.rawdata['current-weapon'] >= len(weapons)):
            return 1    # only one shot possible

        weapon = weapons[fighter.rawdata['current-weapon']]
        if weapon is None:
            return 1    # only one shot possible

        # Does the weapon shoot multiple rounds?
        debug.header1('do_attack: %s' % weapon.name)
        if 'shots_per_round' not in weapon.rawdata:
            #debug.print('shots_per_round: %d' % weapon.rawdata['shots_per_round'])
            return 1    # weapon can only shoot 1 round

        max_shots_this_round = weapon.rawdata['shots_per_round']
        debug.print('max_shots_this_round: %d' % max_shots_this_round)
        if max_shots_this_round <= 1:
            return 1    # weapon can only shoot 1 round

        # Do we have more than 1 round in the clip?
        clip = weapon.get_clip()
        debug.print('clip:')
        debug.pprint(clip)
        if clip is None:
            return 1    # no clip, only 1 round possible

        shots_left = weapon.shots_left()
        debug.print('shots left: %d' % shots_left)
        if shots_left < max_shots_this_round:
            max_shots_this_round = shots_left
            if max_shots_this_round <= 0:
                return 1    # no shots left in clip

        # Ask how many rounds we want to expend
        shots_fired = 1 if shots_left == 1 else None
        while shots_fired is None:
            shots_fired = self._window_manager.input_box_number(
                    1, 20,
                    'Fire how many rounds (%d max)?' %
                        max_shots_this_round)
            if shots_fired > max_shots_this_round or shots_fired < 0:
                self._window_manager.error(
                    ['Gotta shoot between 0 and %d shots' %
                        max_shots_this_round]
                )
                shots_fired = None

        return shots_fired

    def __get_technique(self,
                        techniques,     # list from Fighter.rawdata
                        technique_name, # string
                        defaults        # list of skill names (in order) we're
                                        #  using for this weapon
                        ):
        '''
        Finds a technique that matches the input parameters.
        Returns matching technique (None if no match).
        '''
        if techniques is None or len(techniques) == 0:
            return None

        for technique in techniques:
            if (technique['name'] != technique_name or
                    technique['default'] not in defaults):
                continue
            found_match = False # We've found a match so far but we're scheptical
            for default in defaults:
                if default == technique['default']:
                    found_match = True
                    break
            if found_match:
                return technique
        return None

    def __holster_weapon(self,
                         fighter,          # Fighter object
                         action,           # {'action-name': 'holster-weapon',
                                           #  'weapon-index': <int> # index in
                                           #       fighter.rawdata['stuff'],
                                           #       None drops weapon
                                           #  'comment': <string>, # optional
                         fight_handler,    # FightHandler object (ignored)
                         ):
        '''
        Action handler for GurpsRuleset.

        Does the ruleset-specific stuff to draw or holster a weapon.  The
        majority of the work for this is actually done in the base class.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = ca_timers.Timer(None)
        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1,
                           'string': ['Holster weapon',
                                      ' Defense: any',
                                      ' Move: step'],
                           'fire_when': ca_timers.Timer.FIRE_ROUND_START
                           })
        return timer

    def __move_and_attack_mods(self,
                               fighter,
                               opponent,
                               weapon,
                               mode,
                               to_hit,
                               why
                               ):
        to_hit_penalty = 0
        MOVE_ATTACK_MELEE_MINUS = -4
        MOVE_ATTACK_RANGED_MINUS = -2

        if weapon is None:
            return

        if why is None:
            why = []

        # FP: B426
        # TODO (now): do unarmed move and attack
        '''
        if self.does_weapon_use_unarmed_skills(weapon):
            unarmed_info = self.get_unarmed_info(fighter,
                                                 opponent,
                                                 weapon)
            to_hit_penalty = MOVE_ATTACK_MELEE_MINUS
            to_hit = unarmed_info['punch_skill'] + to_hit_penalty

            if to_hit > 9:
                why.append('  = 9, move and melee (punch) attacks capped (B365)')
                to_hit = 9
            else:
                why.append('  -4 for move and melee (punch) attack (B365)')
            crit, fumble = self.__get_crit_fumble(to_hit)


            text.append(' Punch to-hit: %d, crit <= %d, fumble >= %d' % (
                to_hit, crit, fumble))

            to_hit_penalty = MOVE_ATTACK_MELEE_MINUS
            to_hit = unarmed_info['kick_skill'] + to_hit_penalty
            if to_hit > 9:
                why.append('  =9, move an melee (kick) attacks capped (B365)')
                to_hit = 9
            else:
                why.append(' -4 for move and melee (kick) attack (B365)')
            crit, fumble = self.__get_crit_fumble(to_hit)


            text.append(' Kick to-hit: %d, crit <= %d, fumble >= %d' % (
                to_hit, crit, fumble))
        else:
        '''

        if weapon.is_ranged_weapon():
            to_hit_penalty = MOVE_ATTACK_RANGED_MINUS
            if ('bulk' in weapon.rawdata and
                    weapon.rawdata['bulk'] < to_hit_penalty):
                why.append( '  %+d for move and ranged attack (bulk of %s) (B365)'
                        % (weapon.rawdata['bulk'], weapon.name))
                to_hit += weapon.rawdata['bulk']
            else:
                why.append('  -2 for move and ranged attack (B365)')
                to_hit += to_hit_penalty
        else:
            to_hit_penalty = MOVE_ATTACK_MELEE_MINUS
            to_hit += to_hit_penalty
            if to_hit > 9:
                why.append('  = 9, move and melee attacks are capped (B365)')
                to_hit = 9
            else:
                why.append('  -4 for move and melee attack (B365)')

        return to_hit, why


    def _perform_action(self,
                        fighter,        # Fighter object
                        action,         # {'action-name': <action>, params...}
                        fight_handler,  # FightHandler object
                        logit=True      # Log into history and
                                        #  'actions_this_turn' because the
                                        #  action is not a side-effect of
                                        #  another action
                        ):
        '''
        This routine delegates actions to routines that perform the action.
        The action routine may return a timer.  _this_ routine adds the timer
        to the Fighter.  That timer is there, primarily, to keep track of what
        the Fighter did but it can also mark the Fighter as busy for a
        multi-round action.

        IN ORDER TO DO A 2 PART ACTION, DO THE FOLLOWING:

            * add action name to |has_2_parts| here or in the base class,
            * build your action handler as follows:

            def __do_whatever(self,
                              fighter,       # Fighter object
                              action,
                              fight_handler  # FightHandler object
                              ):
                if 'part' in action and action['part'] == 2:
                    # This is the 2nd part of a 2-part action.  This part
                    # actually perfoms all the GurpsRuleset-specific actions
                    # and side-effects of doing whatever.

                    # DO THE ACTUAL WORK WITHOUT ANY USER INTERFACE

                    # MAKE THE TIMER, HERE, TO SHOW THE ACTION ON THE
                    # FIGHTER'S DISPLAY.

                    return timer
                else:

                    # This is the 1st part of a 2-part action.  This part of
                    # the action asks questions of the user and sends the
                    # second part.  The 1st part isn't executed when playing
                    # back.

                    # Don't do the first part when playing back.
                    if (fight_handler is not None and
                            fight_handler.world.playing_back):
                        return None  # No timers

                    # DO ANY USER-INTERFACE STUFF

                    # Send the action for the second part

                    # Do a deepcopy for the second part to copy the comment --
                    # that's what gets displayed for the history command.

                    new_action = copy.deepcopy(action)
                    new_action['part'] = 2
                    self.do_action(fighter, new_action, fight_handler)

                    return None # No timers for part 1

        Returns: nothing
        '''

        # PP = pprint.PrettyPrinter(indent=3, width=150)
        # PP.pprint(action)

        # The 2-part actions are used when an action needs to ask questions
        # of the user.  The original action asks the questions and sends the
        # 'part 2' action with all of the answers.  When played back, the
        # original action just returns.  That way, there are no questions on
        # playback and the answers are the same as they were the first time.

        has_2_parts = {
                       'adjust-attribute': True,
                       'adjust-fp': True,
                       'aim': True,
                       'attack': True,
                       'all-out-attack': True,
                       'cast-spell': True,
                       'move-and-attack': True,
                       'reload': True}

        # Call base class' perform_action FIRST because GurpsRuleset depends on
        # the actions of the base class.  It (usually) makes no sense for the
        # base class' actions to depend on the child class'.
        #
        # If there're two parts to an action (the first part asks questions
        # and the second part does the actual deed), only call the base class
        # on the second part.

        # Is this a 2-part action in either the base class (Ruleset) or the
        # derived class (GurpsRuleset)?

        action['two_part_base'] = False
        action['two_part_derived'] = False

        if 'action-name' in action:
            action_name = action['action-name']
            action['two_part_base'] = True if (
                action_name in ca_ruleset.Ruleset.has_2_parts) else False
            action['two_part_derived'] = True if (
                action_name in has_2_parts) else False

        # Figure out when to call the base class / derived class for which
        # parts.

        call_base_class = False
        call_derived_class = False

        part = 2 if 'part' in action and action['part'] == 2 else 1

        if part == 1:
            # Don't log a multi-part action until its last part.  If this is
            # a single-part action, the base class will be called and
            # |handled| will be overwritten by that call.
            handled = ca_ruleset.Ruleset.DONT_LOG

        # NOTE: the base class can modify the action and we'll see it, here.
        # That's a way for the base class' first part to modify the 2nd part
        # of the action.

        if action['two_part_base'] and action['two_part_derived']:
            call_base_class = True
            call_derived_class = True
        elif action['two_part_base'] and not action['two_part_derived']:
            if part == 1:
                call_base_class = True
                call_derived_class = False
            else:
                call_base_class = True
                call_derived_class = True
        elif not action['two_part_base'] and action['two_part_derived']:
            if part == 1:
                call_base_class = False
                call_derived_class = True
            else:
                call_base_class = True
                call_derived_class = True
        else:  # not action['two_part_base'] and not action['two_part_derived']
            if part == 1:
                call_base_class = True
                call_derived_class = True
            else:
                call_base_class = False
                call_derived_class = False
                self._window_manager.error(
                        ['action "%s" not expected to have a part 2' %
                         action['action-name']])
                handled = ca_ruleset.Ruleset.HANDLED_ERROR

        # Now, call the base class if required.

        if call_base_class:
            handled = super(GurpsRuleset, self)._perform_action(fighter,
                                                                action,
                                                                fight_handler)

        if not call_derived_class:
            return handled

        actions = {
            'adjust-attribute':     {'doit': self.__adjust_attribute},
            'adjust-fp':            {'doit': self.__do_adjust_fp},
            'adjust-hp-really':     {'doit': self.__adjust_hp_really},
            'aim':                  {'doit': self.__do_aim},
            'all-out-attack':       {'doit': self.__do_attack},
            'attack':               {'doit': self.__do_attack},
            'cast-spell':           {'doit': self.__cast_spell},
            'change-posture':       {'doit': self.__change_posture},
            'concentrate':          {'doit': self.__do_nothing},
            'defend':               {'doit': self.__reset_aim},
            'doff-armor':           {'doit': self.__reset_aim},
            'don-armor':            {'doit': self.__reset_aim},
            'draw-weapon':          {'doit': self.__draw_weapon},
            'holster-weapon':       {'doit': self.__holster_weapon},
            'evaluate':             {'doit': self.__do_nothing},
            'feint':                {'doit': self.__do_nothing},
            'maintain-spell':       {'doit': self.__maintain_spell},
            'move':                 {'doit': self.__do_nothing},
            'move-and-attack':      {'doit': self.__do_attack},
            'nothing':              {'doit': self.__do_nothing},
            'pick-opponent':        {'doit': self.__do_nothing},
            'reload':               {'doit': self.__do_reload},
            'reset-aim':            {'doit': self.__reset_aim},
            'set-consciousness':    {'doit': self.__set_consciousness},
            'shock':                {'doit': self.__do_adjust_shock},
            'stun':                 {'doit': self.__stun_action},
            'use-item':             {'doit': self.__do_nothing},
            'user-defined':         {'doit': self.__do_nothing},
        }

        if 'action-name' not in action:
            return handled

        if handled == ca_ruleset.Ruleset.HANDLED_ERROR:
            return handled

        if action['action-name'] in actions:
            timer = None
            action_info = actions[action['action-name']]
            if action_info['doit'] is not None:
                timer = action_info['doit'](fighter, action, fight_handler)

            # TODO (eventually): this block should be a gurps_ruleset function
            #   that is called from each of the 'doit' modules.  The 'doit'
            #   modules should each return 'handled' like the base class 'doit'
            #   modules do.

            # If the base class has asked us not to log, we'll honor that.
            if handled != ca_ruleset.Ruleset.DONT_LOG:
                handled = ca_ruleset.Ruleset.HANDLED_OK

                if timer is not None and logit:
                    if 'notimer' not in action or not action['notimer']:
                        fighter.timers.add(timer)

        return handled

    def __pick_attrib(self,
                      fighter # Fighter object (see NOTE, below)
                      ):
        # TODO (now): this can go into the generic ruleset
        # TODO (now): attribute (edit) should use this
        '''
        NOTE: this doesn't have to be the fighter that is being modified but
        we get the list of attributes from a single fighter.
        '''
        # Current or permanent
        perm_current_menu = [('current', 'current'),
                             ('permanent', 'permanent')]
        current_perm, ignore = self._window_manager.menu(
                ('%s: Choose What Type Of Attribute' %
                    fighter.name), perm_current_menu)

        # Which attribute
        attr_menu = [(attr, attr)
                     for attr in list(fighter.rawdata[current_perm].keys())]

        attr, ignore = self._window_manager.menu(
                'Select Attribute', attr_menu)
        if attr is None:
            return None

        return current_perm, attr

    def _record_action(self,
                       fighter,          # Fighter object
                       action,           # {'action-name': <action>, params...}
                       fight_handler,    # FightHandler object
                       handled,          # bool: whether/how the action was
                                         #   handled
                       logit=True        # Log into history and
                                         #  'actions_this_turn' because the
                                         #  action is not a side-effect of
                                         #  another action
                       ):
        '''
        Saves a performed 'action' in the Fighter's did-it-this-round list.

        Returns: nothing.
        '''
        if (handled == ca_ruleset.Ruleset.DONT_LOG or
                'action-name' not in action):
            return

        super(GurpsRuleset, self)._record_action(fighter,
                                                 action,
                                                 fight_handler,
                                                 handled,
                                                 logit)

        if handled == ca_ruleset.Ruleset.HANDLED_OK:
            if logit and 'action-name' in action:
                # This is mostly for actions (like 'set_timer') on a <ROOM>
                if 'actions_this_turn' not in fighter.rawdata:
                    fighter.rawdata['actions_this_turn'] = []
                fighter.rawdata['actions_this_turn'].append(
                        action['action-name'])
        elif handled == ca_ruleset.Ruleset.UNHANDLED:
            self._window_manager.error(
                            ['action "%s" is not handled by any ruleset' %
                             action['action-name']])

        # Don't deal with HANDLED_ERROR

    def __reset_aim(self,
                    fighter,          # Fighter object
                    action,           # {'action-name': 'defend' | 'don-armor'
                                      #          | 'reset-aim' |
                                      #          'set-consciousness',
                                      #  'comment': <string>, # optional
                    fight_handler     # FightHandler object (ignored)
                    ):
        '''
        Action handler for GurpsRuleset.

        Resets any ongoing aim that the Fighter may have had.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = None
        if action['action-name'] == 'defend':
            timer = ca_timers.Timer(None)
            timer.from_pieces(
                    {'parent-name': fighter.name,
                     'rounds': 1,
                     'string': ['All out defense',
                                ' Defense: double',
                                ' Move: step'],
                     'fire_when': ca_timers.Timer.FIRE_ROUND_START
                     })

        elif action['action-name'] == 'doff-armor':
            timer = ca_timers.Timer(None)
            armor_index = action['armor-index']
            armor = fighter.equipment.get_item_by_index(armor_index)

            if armor is not None:
                title = 'Doff %s' % armor['name']
                timer.from_pieces(
                        {'parent-name': fighter.name,
                         'rounds': 1,
                         'string': [title, ' Defense: none', ' Move: none'],
                         'fire_when': ca_timers.Timer.FIRE_ROUND_START
                         })
        elif action['action-name'] == 'don-armor':
            timer = ca_timers.Timer(None)
            armor_index = action['armor-index']
            armor = fighter.equipment.get_item_by_index(armor_index)
            if armor is not None:
                title = 'Don %s' % armor['name']
                timer.from_pieces(
                        {'parent-name': fighter.name,
                         'rounds': 1,
                         'string': [title, ' Defense: none', ' Move: none'],
                         'fire_when': ca_timers.Timer.FIRE_ROUND_START
                         })

        return timer

    def __roll_vs_attrib(self,
                         attrib # string: name of attribute
                         ):
        # ignore 'attrib'
        return ca_ruleset.Ruleset.roll(3, 6)

    def __roll_vs_attrib_multiple(self,
                                  param    # {'view': xxx, 'view-opponent': xxx,
                                           #  'current': xxx, 'current-opponent': xxx,
                                           #  'fight_handler': <fight handler> } where
                                           # xxx are Fighter objects
                                  ):
        '''
        Command ribbon method.

        Figures out whom to stun and stuns them.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        selected_fighter = (param['view']
                   if 'view' in param and param['view'] is not None
                   else param['current'])
        if selected_fighter is None:
            return True

        fight_handler = param['fight_handler']
        if fight_handler is None:
            return True

        # Get list of fighters in the current group
        fighters = fight_handler.get_fighters()
        fighter_objects = []
        for fighter_dict in fighters:
            if fighter_dict['group'] == selected_fighter.group:
                index, fighter = fight_handler.get_fighter_object(
                        fighter_dict['name'], fighter_dict['group'])

                if (fighter.name != ca_fighter.Venue.name and
                        fighter.is_conscious()):
                    fighter_objects.append(fighter)

        # Get the attribute against which to roll
        current_perm, attr_string = self.__pick_attrib(selected_fighter)
        window_text = []

        # Roll for each of the fighters in the selected group
        for fighter in fighter_objects:
            window_line = []
            roll = self.__roll_vs_attrib(attr_string)
            attr = fighter.rawdata[current_perm][attr_string]
            if roll <= attr:
                mode = curses.color_pair(ca_gui.GmWindowManager.GREEN_BLACK)
                window_line.append(
                    {'text': ('%s SUCCEDED by %d' % (fighter.name,
                                                     (attr - roll))),
                      'mode': mode})
            else:
                mode = curses.color_pair(ca_gui.GmWindowManager.RED_BLACK)
                window_line.append(
                    {'text': ('%s FAILED by %d' % (fighter.name,
                                                   (roll - attr))),
                      'mode': mode})

            window_line.append(
                {'text': (', %s = %d' % (attr_string, attr)), 'mode': mode})
            window_line.append(
                {'text': (', roll = %d' % roll), 'mode': mode})

            window_text.append(window_line)

        self._window_manager.display_window(
                ('Group roll vs. %s' % attr_string),
                window_text)

        return True

    def __roll_vs_attrib_single(self,
                                param    # {'view': xxx, 'view-opponent': xxx,
                                         #  'current': xxx, 'current-opponent': xxx,
                                         #  'fight_handler': <fight handler> } where
                                         # xxx are Fighter objects
                                ):
        '''
        Command ribbon method.

        Figures out whom to stun and stuns them.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''
        fighter = (param['view']
                   if 'view' in param and param['view'] is not None
                   else param['current'])

        if fighter is None:
            return True

        current_perm, attr_string = self.__pick_attrib(fighter)
        window_text = []
        window_line = []
        roll = self.__roll_vs_attrib(attr_string)
        attr = fighter.rawdata[current_perm][attr_string]
        if roll <= attr:
            mode = curses.color_pair(ca_gui.GmWindowManager.GREEN_BLACK)
            window_line.append(
                {'text': ('SUCCEDED by %d' % (attr - roll)),
                  'mode': mode})
        else:
            mode = curses.color_pair(ca_gui.GmWindowManager.RED_BLACK)
            window_line.append(
                {'text': ('FAILED by %d' % (roll - attr)),
                  'mode': mode})

        window_line.append(
            {'text': (', %s = %d' % (attr_string, attr)), 'mode': mode})
        window_line.append(
            {'text': (', roll = %d' % roll), 'mode': mode})

        window_text = [window_line]
        self._window_manager.display_window(
                ('%s roll vs. %s' % (fighter.name, attr_string)),
                window_text)

        return True

    def __set_consciousness(self,
                            fighter,          # Fighter object
                            action,           # {'action-name':
                                              #     'set-consciousness',
                                              #  'level': <int> # see
                                              #     Fighter.conscious_map
                                              #  'comment': <string> # optional
                            fight_handler,    # FightHandler object
                            ):
        '''
        Action handler for GurpsRuleset.

        Sets the consciousness level (and deals with the side-effects) of the
        fighter.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        timer = self.__reset_aim(fighter,
                                 action,
                                 fight_handler)

        if ('level' in action and (
                action['level'] == ca_fighter.Fighter.UNCONSCIOUS
                or action['level'] == ca_fighter.Fighter.DEAD)):
            self.do_action(fighter,
                           {'action-name': 'stun',
                            'stun': False,
                            'comment': ('(%s) got stunned' % fighter.name)},
                           fight_handler)

            # if holding initiative, this releases it
            self.do_action(fighter,
                           {'action-name': 'hold-init-complete',
                            'name': fighter.name,
                            'group': fighter.group,
                            'in-place': True},
                           fight_handler)

        return timer

    def __show_unarmed_info(self,
                            notes,
                            fighter,        # Fighter object
                            opponent,       # Fighter object
                            weapon          # Weapon object.  Maybe brass knuckles
                            ):
        unarmed_info = self.get_unarmed_info(fighter, opponent, weapon)

        notes.append(unarmed_info['punch_string'])
        crit, fumble = self.__get_crit_fumble(
                unarmed_info['punch_skill'])
        notes.append(
                '  to-hit: %d, crit <= %d, fumble >= %d, damage: %s' %
            (unarmed_info['punch_skill'],
             crit,
             fumble,
             unarmed_info['punch_damage']))

        notes.append(unarmed_info['kick_string'])
        crit, fumble = self.__get_crit_fumble(
                unarmed_info['kick_skill'])
        notes.append(
                '  to-hit: %d, crit <= %d, fumble >= %d, damage: %s' %
            (unarmed_info['kick_skill'],
             crit,
             fumble,
             unarmed_info['kick_damage']))

    def __stun(self,
               param    # {'view': xxx, 'view-opponent': xxx,
                        #  'current': xxx, 'current-opponent': xxx,
                        #  'fight_handler': <fight handler> } where
                        # xxx are Fighter objects
               ):
        '''
        Command ribbon method.

        Figures out whom to stun and stuns them.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if param is None:
            return True
        elif param['view'] is not None:
            stunned_dude = param['view']
        elif param['current-opponent'] is not None:
            stunned_dude = param['current-opponent']
        elif param['current'] is not None:
            stunned_dude = param['current']
        else:
            return True

        fight_handler = (None if 'fight_handler' not in param
                         else param['fight_handler'])

        # Toggle stunned
        if 'stunned' not in stunned_dude.rawdata:
            stunned_dude.rawdata['stunned']= False
        do_stun = False if stunned_dude.rawdata['stunned'] else True

        self.do_action(stunned_dude,
                       {'action-name': 'stun',
                        'stun': do_stun,
                        'comment': ('(%s) got stunned' % stunned_dude.name)},
                       fight_handler)

        return True  # Keep going

    def __stun_action(self,
                      fighter,          # Fighter object
                      action,           # {'action-name': 'stun',
                                        #  'stun': True / False}
                                        #  'comment': <string>, # optional
                      fight_handler,    # FightHandler object (ignored)
                      ):
        '''
        Action handler for GurpsRuleset.

        Marks the Fighter as stunned.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.rawdata['stunned'] = action['stun']

        return None  # No timer
