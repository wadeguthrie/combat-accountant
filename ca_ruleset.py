#! /usr/bin/python

import copy
import curses
import pprint
import random

import ca_fighter
import ca_timers


class Ruleset(object):
    '''
    Any ruleset's character's dict is expected to include the following:
    {
        'state' : 'alive' | 'unconscious' | 'dead'
        'opponent': None | <index into current fight's monster list or, if
                            this is for a monster, index into PC list>
        'stuff' : [ <weapon, armor, items> ],
            The format of 'stuff' contents is ruleset-specific
        'timers': [ <list of timers> ],
        'weapon-index': None | <index into 'stuff'>,
    }

    Timer looks like:
    {
        'rounds': rounds,
        'string': text
        'busy': true | false
    }
    '''

    (UNHANDLED, HANDLED_OK, HANDLED_ERROR, DONT_LOG) = range(4)

    has_2_parts = {'reload': True, 'user-defined': True}

    def __init__(self,
                 window_manager  # GmWindowManager object for menus and errors
                 ):
        self._window_manager = window_manager
        self.sort_init_descending = True # Higher numbered inits go first
        self.options = None

    @staticmethod
    def roll(number,  # the number of dice
             dice,    # the type of dice
             plus=0   # a number to add to the total of the dice roll
             ):
        '''Simulates a roll of dice.'''
        result = plus
        for count in range(number):
            result += random.randint(1, dice)
        return result

    #
    # Public Methods
    #

    def can_finish_turn(self,
                        fighter,        # Fighter object
                        fight_handler   # FightHandler object
                        ):
        return True

    def do_action(self,
                  fighter,          # Fighter object
                  action,           # {'action-name': <action>, parameters...}
                  fight_handler,    # FightHandler object
                  logit=True        # Log into history and 'actions_this_turn'
                                    #   because the action is not a side-effect
                                    #   of another action
                  ):
        '''
        Executes an action for a Fighter then records that action.

        Returns nothing.
        '''

        # print '\n=== do_action ==='
        # PP = pprint.PrettyPrinter(indent=3, width=150)
        # PP.pprint(action)

        handled = self._perform_action(fighter, action, fight_handler, logit)
        self._record_action(fighter, action, fight_handler, handled, logit)

    def get_action_menu(self,
                        action_menu,    # menu for user [(name, predicate)...]
                        fighter,        # Fighter object
                        opponent        # Fighter object
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

        # Figure out who we are and what we're holding.

        weapon, weapon_index = fighter.get_current_weapon()
        holding_ranged = (False if weapon is None else
                          weapon.is_ranged_weapon())

        # ARMOR #

        # Armor SUB-menu

        armor_index_list = fighter.get_current_armor_indexes()

        don_armor_menu = []   # list of armor that may be donned this turn
        for index, item in enumerate(fighter.details['stuff']):
            if 'armor' in item['type']:
                if index not in armor_index_list:
                    don_armor_menu.append(
                            (item['name'],
                             {'action': {'action-name': 'don-armor',
                                                        'armor-index': index}}
                             ))
        don_armor_menu = sorted(don_armor_menu, key=lambda x: x[0].upper())

        # Don armor menu

        if len(don_armor_menu) == 1:
            action_menu.append(
                (('Don %s' % don_armor_menu[0][0]),
                 {'action': {
                    'action-name': 'don-armor',
                    'armor-index':
                    don_armor_menu[0][1]['action']['armor-index']}}
                 ))

        elif len(don_armor_menu) > 1:
            action_menu.append(('Don Armor', {'menu': don_armor_menu}))

        # Doff armor menu

        armor_list = fighter.get_items_from_indexes(armor_index_list)
        for index, armor in enumerate(armor_list):
            if ('natural-armor' not in armor or not armor['natural-armor']):
                action_menu.append(
                        (('Doff %s' % armor['name']),
                         {'action': {'action-name': 'don-armor',
                                     'armor-index': armor_index_list[index]}}
                         ))

        # ATTACK #

        if holding_ranged:
            if weapon.shots_left() > 0:
                # Can only attack if there's someone to attack
                action_menu.extend([
                    ('attack',          {'action':
                                         {'action-name': 'attack'}}),
                    ('attack, all out', {'action':
                                         {'action-name': 'all-out-attack'}})
                ])
        else:
            action_menu.extend([
                    ('attack',          {'action':
                                         {'action-name': 'attack'}}),
                    ('attack, all out', {'action':
                                         {'action-name': 'all-out-attack'}})
            ])

        # DRAW OR HOLSTER WEAPON #

        must_holster = True
        if (weapon is None or ('natural-weapon' in weapon.details and
                               weapon.details['natural-weapon'])):
            must_holster = False

        if must_holster:
            action_menu.append(
                    (('holster/sheathe %s' % weapon.details['name']),
                     {'action': {'action-name': 'draw-weapon',
                                 'weapon-index': None}
                      }))
        else:
            # Draw weapon SUB-menu

            draw_weapon_menu = []   # weapons that may be drawn this turn
            for index, item in enumerate(fighter.details['stuff']):
                if ('ranged weapon' in item['type'] or
                        'melee weapon' in item['type'] or
                        'shield' in item['type']):
                    if weapon is None or weapon_index != index:
                        draw_weapon_menu.append(
                            (item['name'],
                             {'action': {'action-name': 'draw-weapon',
                                         'weapon-index': index}
                              }))
            draw_weapon_menu = sorted(draw_weapon_menu,
                                      key=lambda x: x[0].upper())

            # Draw menu

            if len(draw_weapon_menu) == 1:
                action_menu.append(
                    (('draw (ready, etc.; B325, B366, B382) %s' %
                        draw_weapon_menu[0][0]),
                     {'action':
                         {'action-name': 'draw-weapon',
                          'weapon-index':
                          draw_weapon_menu[0][1]['action']['weapon-index']}
                      }))

            elif len(draw_weapon_menu) > 1:
                action_menu.append(('draw (ready, etc.; B325, B366, B382)',
                                    {'menu': draw_weapon_menu}))

        # RELOAD #

        if holding_ranged:
            action_menu.append(('reload (ready)',
                               {'action': {'action-name': 'reload'}}))

        # USE ITEM #

        # Use SUB-menu

        use_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if 'count' in item and item['count'] != 1:
                name = '%s (%d remaining)' % (item['name'], item['count'])
            else:
                name = item['name']

            use_menu.append((name,
                             {'action': {'action-name': 'use-item',
                                         'item-index': index,
                                         'item-name': item['name']}}
                             ))
        use_menu = sorted(use_menu, key=lambda x: x[0].upper())

        # Use menu

        if len(use_menu) == 1:
            action_menu.append(
                (('use %s' % use_menu[0][0]),
                 {'action': {'action-name': 'use-item',
                             'item-index':
                             use_menu[0][1]['action']['item-index']}
                  }))

        elif len(use_menu) > 1:
            action_menu.append(('use item', {'menu': use_menu}))

        # USER-DEFINED #

        action_menu.append(('User-defined',
                            {'action': {'action-name': 'user-defined'}}))

        return  # No need to return action menu since it was a parameter

    def get_sample_items(self):
        '''
        Returns a list of sample equipment for creating new game files.
        '''
        return []

    def get_sections_in_template(self):
        '''
        This returns an array of the Fighter section headings that are
        expected (well, not _expected_ but any headings that aren't in this
        list should probably not be there) to be in a template.
        '''

        return ['stuff']  # permanent is handled specially

        # Transitory sections, not used in template:
        #   armor-index, state, weapon-index, opponent
        #
        # Not part of template:
        #   notes, fight-notes, current, timers

        return sections

    def heal_fighter(self,
                     fighter,   # Fighter object
                     world      # World object
                     # TODO: prefs - for reload-on-heal
                     ):
        '''
        Removes all injury (and their side-effects) from a fighter.

        Returns: nothing.
        '''
        if 'permanent' not in fighter.details:
            return

        for stat in fighter.details['permanent'].iterkeys():
            fighter.details['current'][stat] = (
                                        fighter.details['permanent'][stat])
        if fighter.details['state'] != 'fight':
            fighter.details['state'] = 'alive'

        if (self.options is not None and
                self.options.get_option('reload-on-heal') and
                fighter.group == 'PCs'):
            throw_away, original_weapon_index = fighter.get_current_weapon()
            for index, item in enumerate(fighter.details['stuff']):
                if 'ranged weapon' in item['type']:
                    fighter.draw_weapon_by_index(index)
                    self.do_action(fighter,
                                   {'action-name': 'reload',
                                    'comment': 'Reloading on heal',
                                    'notimer': True,
                                    'quiet': True},
                                   None)
            fighter.draw_weapon_by_index(original_weapon_index)

    def is_creature_consistent(self,
                               name,     # string: creature's name
                               creature  # dict from Game File
                               ):
        '''
        Make sure creature's information makes sense.
        '''
        result = True

        fighter = ca_fighter.Fighter(name,
                                     'dummy group',  # unused
                                     creature,
                                     self,
                                     self._window_manager)

        armor_index_list = fighter.get_current_armor_indexes()
        armor_list = fighter.get_items_from_indexes(armor_index_list)

        # Dump non-armor being worn as armor

        for index, armor in enumerate(armor_list):
            if armor is None:
                self._window_manager.error([
                    'Creature "%s"' % name,
                    '  is wearing weird armor "<None>". Fixing.'])
                self.do_action(fighter,
                               {'action-name': 'doff-armor',
                                'armor-index': armor_index_list[index],
                                'notimer': True},
                               None)
                result = False
            elif 'armor' not in armor['type']:
                self._window_manager.error([
                    'Creature "%s"' % name,
                    '  is wearing weird armor "%s". Fixing.' % armor['name']])
                self.do_action(fighter,
                               {'action-name': 'doff-armor',
                                'armor-index': armor_index_list[index],
                                'notimer': True},
                               None)
                result = False

        # Add natural armor if they're not wearing any other kind

        armor_index_list = fighter.get_current_armor_indexes()

        if len(armor_index_list) == 0:
            for index, item in enumerate(fighter.details['stuff']):
                if 'natural-armor' in item and item['natural-armor']:
                    self.do_action(fighter,
                                   {'action-name': 'don-armor',
                                    'armor-index': index,
                                    'notimer': True},
                                   None)

        weapon, throw_away = fighter.get_current_weapon()
        if weapon is not None:
            if not weapon.is_ranged_weapon() and not weapon.is_melee_weapon():
                self._window_manager.error([
                    'Creature "%s"' % name,
                    '  is wielding weird weapon "%s". Fixing.' %
                    weapon.details['name']])
                self.do_action(fighter,
                               {'action-name': 'draw-weapon',
                                'weapon-index': None,
                                'notimer': True},
                               None)
                result = False

        weapon, throw_away = fighter.get_current_weapon()
        if weapon is None:
            # If they're not holding anything and they have natural weapons,
            # use those weapons.
            for index, item in enumerate(fighter.details['stuff']):
                if 'natural-weapon' in item and item['natural-weapon']:
                    self.do_action(fighter,
                                   {'action-name': 'draw-weapon',
                                    'weapon-index': index,
                                    'notimer': True},
                                   None)
                    break


        return result

    def make_empty_creature(self):
        '''
        Builds the minimum legal character detail (the dict that goes into the
        Game File).  You can feed this to the constructor of a Fighter.  First,
        however, you need to install it in the World's Game File so that it's
        backed-up and recognized by the rest of the software.

        Returns: the dict.
        '''
        return {'stuff': [],
                'weapon-index': None,
                'armor-index': [], # can wear multiple armors over each other
                'permanent': {},
                'current': {},
                'state': 'alive',
                'timers': [],
                'opponent': None,
                'notes': [],
                'fight-notes': [],
                }

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
        result = []

        if look_for_re.search(name):
            result.append({'name': name,
                           'group': group,
                           'location': 'name',
                           'notes': name})

        if 'stuff' in creature:
            for thing in creature['stuff']:
                if look_for_re.search(thing['name']):
                    result.append({'name': name,
                                   'group': group,
                                   'location': 'stuff["name"]',
                                   'notes': thing['name']})
                if 'notes' in thing and look_for_re.search(thing['notes']):
                    result.append({'name': name,
                                   'group': group,
                                   'location': '%s["notes"]' % thing['name'],
                                   'notes': thing['notes']})

        if 'notes' in creature:
            for line in creature['notes']:
                if look_for_re.search(line):
                    result.append({'name': name,
                                   'group': group,
                                   'location': 'notes'})
                    break  # Don't want an entry for each time it's in notes

        if 'fight-notes' in creature:
            for line in creature['fight-notes']:
                if look_for_re.search(line):
                    result.append({'name': name,
                                   'group': group,
                                   'location': 'fight-notes',
                                   'notes': creature['fight-notes']})

        return result

    def set_options(self,
                    options # Options object
                    ):
        '''Saves the options.'''
        self.options = options

    #
    # Private and Protected Methods
    #

    def _adjust_hp(self,
                   fighter,          # Fighter object
                   action,           # {'action-name': 'adjust-hp',
                                     #  'adj': <int> # add to HP
                                     #  'comment': <string>, # optional
                                     #  'quiet': <bool> # use defaults for all
                                     #                    user interactions --
                                     #                    optional
                                     # }
                   fight_handler,    # FightHandler object
                   ):
        '''
        Action handler for Ruleset.

        Adjust the Fighter's hit points.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.details['current']['hp'] += action['adj']
        return Ruleset.HANDLED_OK

    def __do_attack(self,
                    fighter,          # Fighter object
                    action,           # {'action-name':
                                      #     'attack' | 'all-out-attack' |
                                      #     'move-and-attack'
                                      #  'comment': <string>, # optional
                    fight_handler     # FightHandler object
                    ):
        '''
        Action handler for Ruleset.

        Performs an attack action for the Fighter.  Picks an opponent if the
        fighter doesn't have one.  Reduces the ammo if the Fighter's weapon
        takes ammunition.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        if (fighter.details['opponent'] is None and
                fight_handler is not None and
                not fight_handler.world.playing_back):
            fight_handler.pick_opponent()

        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or not weapon.uses_ammo():
            return Ruleset.HANDLED_OK

        if weapon.use_one_ammo():
            clip = weapon.get_clip()
            if (clip is not None and 'notes' in clip and
                    clip['notes'] is not None and len(clip['notes']) > 0):
                self._window_manager.display_window(
                    'Shot Fired',
                    [[{'text': ('%s' % clip['notes']),
                   'mode': curses.A_NORMAL}]])
            return Ruleset.HANDLED_OK
        return Ruleset.HANDLED_ERROR

    def __do_custom_action(self,
                           fighter,          # Fighter object
                           action,           # {'action-name': 'user-defined',
                                             #  'comment': <string>, # optional
                           fight_handler,    # FightHandler object
                           ):
        '''
        Action handler for Ruleset.

        Allows the user to describe some action that wasn't in the Ruleset or
        the derived Ruleset.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.   We're here just so
            # part 2 of the action can get logged.
            return Ruleset.HANDLED_OK

        else:
            # This is the 1st part of a 2-part action.  This part of
            # the action asks questions of the user and sends the
            # second part.  The 1st part isn't executed when playing
            # back.

            # Don't do the first part when playing back.
            if (fight_handler is not None and
                    fight_handler.world.playing_back):
                return Ruleset.HANDLED_OK

            height = 1
            title = 'What Action Is Performed'
            width = self._window_manager.getmaxyx()
            comment_string = self._window_manager.input_box(height,
                                                            width,
                                                            title)

            # Send the action for the second part

            # Do a deepcopy for the second part to copy the comment --
            # that's what gets displayed for the history command.

            new_action = copy.deepcopy(action)
            new_action['part'] = 2

            if 'comment' in new_action:
                new_action['comment'] = '%s -- ' % action['comment']
            new_action['comment'] += comment_string

            self.do_action(fighter, new_action, fight_handler)

            return Ruleset.DONT_LOG

    def __do_reload(self,
                    fighter,          # Fighter object
                    action,           # {'action-name': 'reload',
                                      #  'comment': <string>, # optional
                                      #  'notimer': <bool>, # whether to
                                      #                       return a timer
                                      #                       for the fighter
                                      #                       -- optional
                                      #  'clip-index': <int>  # index of clip
                                      #                       # in equipment
                                      #  'quiet': <bool>    # use defaults for
                                      #                       all user
                                      #                       interactions
                                      #                       -- optional
                                      # }
                    fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for Ruleset.

        Reloads the Fighter's current weapon.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part of the action
            # actually perfoms all the GurpsRuleset-specific actions and
            # side-effects of reloading the Fighter's current weapon.  Note
            # that a lot of the obvious part is done by the base class Ruleset.

            weapon, weapon_index = fighter.get_current_weapon()

            # If there's no new clip to load, just bail out
            if 'clip-index' not in action:
                return Ruleset.HANDLED_OK

            # xxx

            infinite_clips = True if (self.options is not None and
                    self.options.get_option('infinite-clips')) else False

            # Prepare the new clip -- I know this is backwards but the
            # clip index (for the new clip) is still valid until the old clip
            # is added to the equipment list

            if infinite_clips:
                clip = copy.deepcopy(fighter.equipment.get_item_by_index(
                    action['clip-index']))
            else:
                clip = fighter.remove_equipment(action['clip-index'], 1)

            # Put a non-zero count clip back in equipment list
            if weapon.shots_left() > 0:
                old_clip = weapon.remove_old_clip()
                if (old_clip is not None and not infinite_clips):
                    if (old_clip['shots_left'] > 0 or
                            ('discard-when-empty' in old_clip and
                             not old_clip['discard-when-empty'])):
                        ignore_item = fighter.add_equipment(old_clip)

            # And put the new clip in the weapon
            weapon.load(clip)

            return Ruleset.HANDLED_OK

        else:
            # This is the 1st part of a 2-part action.  This part of
            # the action asks questions of the user and sends the
            # second part.  The 1st part isn't executed when playing
            # back.

            weapon, weapon_index = fighter.get_current_weapon()
            if weapon is None or not weapon.uses_ammo():
                return Ruleset.HANDLED_ERROR

            clip_name = weapon.details['ammo']['name']

            # Get a list of clips that fit this weapon, ask the user which one

            clip_menu = []
            clip_name = weapon.details['ammo']['name']
            for index, item in enumerate(fighter.details['stuff']):
                if item['name'] == clip_name:
                    if 'notes' in item and len(item['notes']) > 0:
                        text = '%s -- %s' % (item['name'], item['notes'])
                    else:
                        text = item['name']

                    if 'shots' in item and 'shots_left' in item:
                        text += ', (%d/%d shots left)' % (item['shots_left'],
                                                          item['shots'])

                    clip_menu.append((text, index))

            clip_index, ignore = self._window_manager.menu('Reload With What',
                                                           clip_menu)
            if clip_index is None:
                return Ruleset.DONT_LOG

            # Is the clip good?

            clip = fighter.equipment.get_item_by_index(clip_index)
            if clip is None:
                return Ruleset.DONT_LOG

            # Do a deepcopy for the second part to copy the comment --
            # that's what gets displayed for the history command.

            action['clip-index'] = clip_index

            # --- THIS IS NOT CALLED in GurpsRuleset ---
            # If the derived class is a two-parter, it'll be responsible for
            # launching part-2 of the action (since the base class -- us --
            # is called first).  That action will be based on _this_ action
            # so anything we add to it, here, will carry-over.  If the derived
            # class is a one-parter, then we can launch the second part, here.
            if not action['two_part_derived']:
                action['part'] = 2
                self.do_action(fighter, new_action, fight_handler)

            return Ruleset.DONT_LOG

    def __don_armor(self,
                    fighter,          # Fighter object
                    action,           # {'action-name': 'don-armor',
                                      #  'armor-index': <int> # index in
                                      #         fighter.details['stuff',
                                      #         None doffs armor
                                      #  'comment': <string> # optional
                    fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for Ruleset.

        Dons a specific piece of armor for the Fighter.  If the index is None,
        it doffs the current armor.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.don_armor_by_index(action['armor-index'])
        return Ruleset.HANDLED_OK

    def __doff_armor(self,
                     fighter,         # Fighter object
                     action,          # {'action-name': 'doff-armor',
                                      #  'armor-index': <int> # index in
                                      #         fighter.details['stuff',
                                      #         None doffs armor
                                      #  'comment': <string> # optional
                    fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for Ruleset.

        Dons a specific piece of armor for the Fighter.  If the index is None,
        it doffs the current armor.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.doff_armor_by_index(action['armor-index'])
        return Ruleset.HANDLED_OK

    def __draw_weapon(self,
                      fighter,          # Fighter object
                      action,           # {'action-name': 'draw-weapon',
                                        #  'weapon-index': <int> # index in
                                        #       fighter.details['stuff'],
                                        #       None drops weapon
                                        #  'comment': <string> # optional
                      fight_handler,    # FightHandler object
                      ):
        '''
        Action handler for Ruleset.

        Draws a specific weapon for the Fighter.  If index in None, it
        holsters the current weapon.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        # TODO: draw weapon from counted item (that takes clips) makes a copy
        fighter.draw_weapon_by_index(action['weapon-index'])
        return Ruleset.HANDLED_OK

    def __end_turn(self,
                   fighter,          # Fighter object
                   action,           # {'action-name': 'end-turn',
                                     #  'comment': <string> # optional
                   fight_handler,    # FightHandler object
                   ):
        '''
        Action handler for Ruleset.

        Does all of the shut-down operations for a Fighter to complete his
        turn.  Moves to the next Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        if fight_handler is not None:
            fighter.end_turn(fight_handler)
            fight_handler.modify_index(1)
        return Ruleset.HANDLED_OK

    def __hold_init(self,
                    fighter,          # Fighter object
                    action,           # {'action-name': 'hold-init',
                                      #  'item-index': <int> # index in
                                      #       fighter.details['stuff']
                                      #  'comment': <string>, # optional
                    fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for Ruleset.

        Use and discard a specific item (decrements its count).

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        fight_handler.wait_action(action['name'], action['group'])
        return Ruleset.HANDLED_OK

    def __hold_init_complete(self,
                             fighter,       # Fighter object
                             action,        # {'action-name':
                                            #       'hold-init-complete',
                                            #  'item-index': <int> # ndx in
                                            #       fighter.details['stuff']
                                            #  'comment': <string>, # opt'l
                             fight_handler, # FightHandler object
                             ):
        '''
        Action handler for Ruleset.

        Use and discard a specific item (decrements its count).

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        fight_handler.wait_end_action(action['name'], action['group'])
        return Ruleset.HANDLED_OK

    def _perform_action(self,
                        fighter,          # Fighter object
                        action,           # {'action-name':
                                          #     <action>, parameters...}
                        fight_handler,    # FightHandler object
                        logit=True        # Log into history and
                                          #  'actions_this_turn' because the
                                          #  action is not a side-effect of
                                          #  another action
                        ):
        '''
        This routine delegates actions to routines that perform the action.
        The 'doit' routines return whether the action was successfully handled
        or not (i.e., UNHANDLED, HANDLED_OK, or HANDLED_ERROR) and that is, in
        turn, returned to the calling routine.

        Default, non-ruleset related, action handling.  Good for drawing
        weapons and such.

        ONLY to be used for fights (otherwise, there's no fight handler to log
        the actions).

        This is called directly from the child ruleset (which is called from
        do_action because _perform_action is overridden by the child class.

        Returns: nothing
        '''

        actions = {
            'adjust-hp':            {'doit': self._adjust_hp},
            'all-out-attack':       {'doit': self.__do_attack},
            'attack':               {'doit': self.__do_attack},
            'doff-armor':           {'doit': self.__doff_armor},
            'don-armor':            {'doit': self.__don_armor},
            'draw-weapon':          {'doit': self.__draw_weapon},
            'end-turn':             {'doit': self.__end_turn},
            'move-and-attack':      {'doit': self.__do_attack},
            'pick-opponent':        {'doit': self.__pick_opponent},
            'previous-turn':        {'doit': self.__previous_turn},
            'reload':               {'doit': self.__do_reload},
            'set-consciousness':    {'doit': self.__set_consciousness},
            'set-timer':            {'doit': self.__set_timer},
            'start-turn':           {'doit': self.__start_turn},
            'use-item':             {'doit': self.__use_item},
            'user-defined':         {'doit': self.__do_custom_action},
            'hold-init':            {'doit': self.__hold_init},
            'hold-init-complete':   {'doit': self.__hold_init_complete},
        }

        handled = Ruleset.UNHANDLED
        if 'action-name' in action:
            if action['action-name'] in actions:
                action_info = actions[action['action-name']]
                if action_info['doit'] is not None:
                    handled = action_info['doit'](fighter,
                                                  action,
                                                  fight_handler)
        else:
            handled = Ruleset.HANDLED_OK  # No name? It's just a comment.

        return handled

    def __pick_opponent(self,
                        fighter,          # Fighter object
                        action,           # {'action-name': 'pick-opponent',
                                          #  'opponent':
                                          #     {'name': opponent_name,
                                          #      'group': opponent_group},
                                          #  'comment': <string> # optional
                        fight_handler,    # FightHandler object
                        ):
        '''
        Action handler for Ruleset.

        Establishes a Fighter's opponent for future actions.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.details['opponent'] = {'group': action['opponent']['group'],
                                       'name': action['opponent']['name']}
        return Ruleset.HANDLED_OK

    def __previous_turn(self,
                   ignored_fighter,  # Fighter object - ignored
                   action,           # {'action-name': 'previous-turn',
                                     #  'comment': <string> # optional
                   fight_handler,    # FightHandler object
                   ):
        '''
        Action handler for Ruleset.

        When the GM goes to the next turn by accident, he uses this to go back.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        if fight_handler is not None:
            fight_handler.modify_index(-1)
        return Ruleset.HANDLED_OK

    def _record_action(self,
                       fighter,          # Fighter object
                       action,           # {'action-name':
                                         #      <action>, parameters...}
                       fight_handler,    # FightHandler object
                       handled,          # bool: whether/how the action was
                                         #   handled
                       logit=True        # Log into history and
                                         #  'actions_this_turn' because the
                                         #  action is not a side-effect of
                                         #  another action
                       ):
        '''
        Logs a performed 'action' in the fight's history.

        Returns: nothing.
        '''

        if fight_handler is not None and logit and handled != Ruleset.DONT_LOG:
            fight_handler.add_to_history(action)

        return

    def __set_consciousness(self,
                            fighter,          # Fighter object
                            action,           # {'action-name':
                                              #     'set-consciousness',
                                              #  'level': <int> # see
                                              #         Fighter.conscious_map
                                              #  'comment': <string> # optional
                            fight_handler,    # FightHandler object
                            ):
        '''
        Action handler for Ruleset.

        Configures the consciousness state of the Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.set_consciousness(action['level'])
        return Ruleset.HANDLED_OK

    def __set_timer(self,
                    fighter,          # Fighter object
                    action,           # {'action-name': 'set-timer',
                                      #  'timer': <dict> # see
                                      #                    Timer::from_pieces
                                      #  'comment': <string> # optional
                    fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for Ruleset.

        Attaches a Timer to the Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        timer_obj = ca_timers.Timer(None)
        timer_obj.from_pieces(action['timer'])
        fighter.timers.add(timer_obj)
        return Ruleset.HANDLED_OK

    def __start_turn(self,
                     fighter,          # Fighter object
                     action,           # {'action-name': 'start-turn',
                                       #  'comment': <string> # optional
                     fight_handler,    # FightHandler object
                     ):
        '''
        Action handler for Ruleset.

        Action to do all the preparatory work for a Fighter to start his/her
        turn.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        fighter.start_turn(fight_handler)
        return Ruleset.HANDLED_OK

    def __use_item(self,
                   fighter,          # Fighter object
                   action,           # {'action-name': 'use-item',
                                     #  'item-index': <int> # index in
                                     #       fighter.details['stuff']
                                     #  'comment': <string>, # optional
                   fight_handler,    # FightHandler object
                   ):
        '''
        Action handler for Ruleset.

        Use and discard a specific item (decrements its count).

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        item = fighter.equipment.get_item_by_index(action['item-index'])
        if 'count' in item and item['count'] == 0:
            self._window_manager.error(['Item is empty, you cannot use it'])

        ignore_item = fighter.remove_equipment(action['item-index'], 1)

        return Ruleset.HANDLED_OK
