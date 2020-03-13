#! /usr/bin/python

import random

import ca_fighter

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

    def __init__(self,
                 window_manager # GmWindowManager object for menus and errors
                ):
        self._window_manager = window_manager

    @staticmethod
    def roll(number, # the number of dice
             dice,   # the type of dice
             plus=0  # a number to add to the total of the dice roll
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
                        fighter # Fighter object
                       ):
        return True


    def do_action(self,
                  fighter,          # Fighter object
                  action,           # {'name': <action>, parameters...}
                  fight_handler,    # FightHandler object
                  logit=True        # Log into history and 'actions_this_turn'
                                    #   because the action is not a side-effect
                                    #   of another action
                 ):
        '''
        Executes an action for a Fighter then records that action.

        Returns nothing.
        '''
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
                                (weapon['type'] == 'ranged weapon'))

        ### Armor ###

        # Armor SUB-menu

        armor, armor_index = fighter.get_current_armor()
        don_armor_menu = []   # list of armor that may be donned this turn
        for index, item in enumerate(fighter.details['stuff']):
            if item['type'] == 'armor':
                if armor is None or armor_index != index:
                    don_armor_menu.append((item['name'],
                                           {'action': {'name': 'don-armor',
                                                       'armor-index': index}}
                                         ))
        don_armor_menu = sorted(don_armor_menu, key=lambda x: x[0].upper())

        # Armor menu

        if len(don_armor_menu) == 1:
            action_menu.append(
                (('Don %s' % don_armor_menu[0][0]),
                 {'action': {
                    'name': 'don-armor',
                    'armor-index': don_armor_menu[0][1]['action']['armor-index']
                  }
                 }))

        elif len(don_armor_menu) > 1:
            action_menu.append(('Don Armor', {'menu': don_armor_menu}))

        if armor is not None:
            action_menu.append((('Doff %s' % armor['name']),
                                 {'action': {'name': 'don-armor',
                                             'armor-index': None}}
                              ))

        ### Attack ###

        if holding_ranged:
            if weapon['ammo']['shots_left'] > 0:
                # Can only attack if there's someone to attack
                action_menu.extend([
                    ('attack',          {'action': {'name': 'attack'}}),
                    ('attack, all out', {'action': {'name': 'all-out-attack'}})
                ])
        else:
            action_menu.extend([
                    ('attack',          {'action': {'name': 'attack'}}),
                    ('attack, all out', {'action': {'name': 'all-out-attack'}})
            ])

        ### Draw or Holster weapon ###

        if weapon is not None:
            action_menu.append((('holster/sheathe %s' % weapon['name']),
                                   {'action': {'name': 'draw-weapon',
                                               'weapon-index': None}
                                   }))
        else:
            # Draw weapon SUB-menu

            draw_weapon_menu = []   # weapons that may be drawn this turn
            for index, item in enumerate(fighter.details['stuff']):
                if (item['type'] == 'ranged weapon' or
                        item['type'] == 'melee weapon' or
                        item['type'] == 'shield'):
                    if weapon is None or weapon_index != index:
                        draw_weapon_menu.append(
                            (item['name'], {'action': {'name': 'draw-weapon',
                                                       'weapon-index': index}
                                           }))
            draw_weapon_menu = sorted(draw_weapon_menu,
                                      key=lambda x: x[0].upper())

            # Draw menu

            if len(draw_weapon_menu) == 1:
                action_menu.append(
                    (('draw (ready, etc.; B325, B366, B382) %s' %
                                                    draw_weapon_menu[0][0]),
                     {'action': {'name': 'draw-weapon',
                                 'weapon-index':
                            draw_weapon_menu[0][1]['action']['weapon-index']}
                     }))

            elif len(draw_weapon_menu) > 1:
                action_menu.append(('draw (ready, etc.; B325, B366, B382)',
                                    {'menu': draw_weapon_menu}))

        ### RELOAD ###

        if holding_ranged:
            action_menu.append(('reload (ready)',
                               {'action': {'name': 'reload'}}
                              ))

        ### Use Item ###

        # Use SUB-menu

        use_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if item['count'] > 0:
                use_menu.append((item['name'],
                                {'action': {'name': 'use-item',
                                            'item-index': index}}
                               ))
        use_menu = sorted(use_menu, key=lambda x: x[0].upper())

        # Use menu

        if len(use_menu) == 1:
            action_menu.append(
                (('use %s' % use_menu[0][0]),
                 {'action': {'name': 'use-item',
                             'item-index':
                                use_menu[0][1]['action']['item-index']}
                 }))

        elif len(use_menu) > 1:
            action_menu.append(('use item', {'menu': use_menu}))

        ### User-defined ###

        action_menu.append(('User-defined',
                            {'action': {'name': 'user-defined'}}
                          ))

        return # No need to return action menu since it was a parameter


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
        #   notes, short-notes, current, timers

        return sections


    # Ruleset
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

        if ('reload-on-heal' in world.details['options'] and
                            world.details['options']['reload-on-heal'] and
                            fighter.group == 'PCs'):
            throw_away, original_weapon_index = fighter.get_current_weapon()
            for index, item in enumerate(fighter.details['stuff']):
                if item['type'] == 'ranged weapon':
                    fighter.draw_weapon_by_index(index)
                    self.do_action(fighter,
                                   {'name': 'reload',
                                    'comment': 'Reloading on heal',
                                    'notimer': True,
                                    'quiet': True},
                                   None)
            fighter.draw_weapon_by_index(original_weapon_index)


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
                'armor-index': None,
                'permanent': {},
                'current': {},
                'state': 'alive',
                'timers': [],
                'opponent': None,
                'notes': [],
                'short-notes': [],
                }


    def search_one_creature(self,
                            name,       # string containing the name
                            group,      # string containing the group
                            creature,   # dict describing the creature
                            look_for_re # compiled Python regex
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
                    break # Don't want an entry for each time it's in notes

        if 'short-notes' in creature:
            for line in creature['short-notes']:
                if look_for_re.search(line):
                    result.append({'name': name,
                                   'group': group,
                                   'location': 'short-notes',
                                   'notes': creature['short-notes']})

        return result

    #
    # Private and Protected Methods
    #


    def _adjust_hp(self,
                   fighter,          # Fighter object
                   action,           # {'name': 'adjust-hp',
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
                    action,           # {'name': 'attack' | 'all-out-attack' |
                                      #          'move-and-attack'
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

        # TODO: this should be in two parts like cast_spell since the user can
        # be asked to pick an opponent.
        if (fighter.details['opponent'] is None and
                                        fight_handler is not None and
                                        not fight_handler.world.playing_back):
            fight_handler.pick_opponent()

        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return Ruleset.HANDLED_OK

        weapon['ammo']['shots_left'] -= 1
        return Ruleset.HANDLED_OK


    def __do_custom_action(self,
                           fighter,          # Fighter object
                           action,           # {'name': 'user-defined',
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
            return Ruleset.HANDLED_OK   # We're here just so the new action can
                                        # get logged
        height = 1
        title = 'What Action Is Performed'
        width = self._window_manager.getmaxyx()
        comment_string = self._window_manager.input_box(height, width, title)

        new_action = {'name': 'user-defined',
                      'part': 2}

        if 'comment' in action:
            new_action['comment'] = '%s -- ' % action['comment']
        new_action['comment'] += comment_string

        self.do_action(fighter, new_action, fight_handler)

        return Ruleset.DONT_LOG


    def __do_reload(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'reload',
                                      #  'comment': <string>, # optional
                                      #  'notimer': <bool>, # whether to
                                      #                       return a timer
                                      #                       for the fighter
                                      #                       -- optional
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
        weapon, weapon_index = fighter.get_current_weapon()
        if weapon is None or 'ammo' not in weapon:
            return Ruleset.HANDLED_ERROR

        clip_name = weapon['ammo']['name']
        for item in fighter.details['stuff']:
            if item['name'] == clip_name and item['count'] > 0:
                weapon['ammo']['shots_left'] = weapon['ammo']['shots']
                item['count'] -= 1
                return Ruleset.HANDLED_OK
        return Ruleset.HANDLED_ERROR


    def __don_armor(self,
                    fighter,          # Fighter object
                    action,           # {'name': 'don-armor',
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


    def __draw_weapon(self,
                      fighter,          # Fighter object
                      action,           # {'name': 'draw-weapon',
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

        fighter.draw_weapon_by_index(action['weapon-index'])
        return Ruleset.HANDLED_OK


    def __end_turn(self,
                   fighter,          # Fighter object
                   action,           # {'name': 'end-turn',
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


    def _perform_action(self,
                        fighter,          # Fighter object
                        action,           # {'name': <action>, parameters...}
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
            'don-armor':            {'doit': self.__don_armor},
            'draw-weapon':          {'doit': self.__draw_weapon},
            'end-turn':             {'doit': self.__end_turn},
            'pick-opponent':        {'doit': self.__pick_opponent},
            'reload':               {'doit': self.__do_reload},
            'set-consciousness':    {'doit': self.__set_consciousness},
            'set-timer':            {'doit': self.__set_timer},
            'start-turn':           {'doit': self.__start_turn},
            'use-item':             {'doit': self.__use_item},
            'user-defined':         {'doit': self.__do_custom_action},
        }

        handled = Ruleset.UNHANDLED
        if 'name' in action:
            if action['name'] in actions:
                action_info = actions[action['name']]
                if action_info['doit'] is not None:
                    handled = action_info['doit'](fighter,
                                                  action,
                                                  fight_handler)
        else:
            handled = Ruleset.HANDLED_OK  # No name? It's just a comment.

        return handled


    def __pick_opponent(self,
                        fighter,          # Fighter object
                        action,           # {'name': 'pick-opponent',
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


    def _record_action(self,
                       fighter,          # Fighter object
                       action,           # {'name': <action>, parameters...}
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
                            action,           # {'name': 'set-consciousness',
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
                    action,           # {'name': 'set-timer',
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
                     action,           # {'name': 'start-turn',
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
                   action,           # {'name': 'use-item',
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
        if item is not None and 'count' in item:
            item['count'] -= 1
        return Ruleset.HANDLED_OK