#! /usr/bin/python

import copy
import curses
import datetime
import pprint
import random

import ca_equipment
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
    timing_headings = ['name', 'group', 'time', 'action', 'state', 'round']

    def __init__(self,
                 window_manager  # GmWindowManager object for menus and errors
                 ):
        self._window_manager = window_manager
        self.sort_init_descending = True # Higher numbered inits go first
        self.options = None
        self.active_actions = []

        self._timing_file = None
        self._char_being_timed = None

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
                        fight_handler   # FightHandler object (ignored)
                        ):
        return True

    def do_action(self,
                  fighter,          # Fighter object
                  action,           # {'action-name': <action>, parameters...}
                  fight_handler,    # FightHandler object.  Used mostly to
                                    #   interact with other beings in the fight.
                  logit=True        # Log into history and 'actions_this_turn'
                                    #   because the action is not a side-effect
                                    #   of another action
                  ):
        '''
        Executes an action for a Fighter then records that action.

        Returns nothing.
        '''

        #print '\n--- do_action for %s ---' % fighter.name
        #PP = pprint.PrettyPrinter(indent=3, width=150)
        #PP.pprint(action)

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

        weapons = fighter.get_current_weapons()
        holding_ranged = False
        holding_loaded_ranged = False
        holding_melee = False
        holding_natural_weapon = False
        holding_non_natural_weapon = False

        for weapon in weapons:
            if weapon is None:
                continue
            if weapon.is_ranged_weapon():
                holding_ranged = True
                if weapon.shots_left() > 0:
                    holding_loaded_ranged = True
            else:
                holding_melee = True
            if ca_equipment.Weapon.is_natural_weapon(weapon.details):
                holding_natural_weapon = True
            else:
                holding_non_natural_weapon = True

        weapon_indexes = fighter.get_current_weapon_indexes()

        # ATTACK #

        if holding_melee or holding_loaded_ranged:
            # Can only attack if there's someone to attack
            action_menu.extend([
                ('attack',          {'action':
                                     {'action-name': 'attack'}}),
                ('attack, all out', {'action':
                                     {'action-name': 'all-out-attack'}})
            ])

        # USER-DEFINED #

        action_menu.append(('User-defined',
                            {'action': {'action-name': 'user-defined'}}))

        # OPEN CONTAINER

        container_stack = fighter.details['open-container']
        container = fighter.equipment.get_container(container_stack)
        if container is None:
            return None # Error condition -- top-level should be []

        open_container_menu = []
        containers = []
        for index, item in enumerate(container):
            if 'container' in item['type']:
                containers.append((index, item['name']))
                verbose_option = self.get_option('verbose')
                if verbose_option is not None and verbose_option:
                    entry_name = '%d: %s' % (index, item['name'])
                else:
                    entry_name = '%s' % item['name']

                open_container_menu.append(
                        (entry_name,
                         {'action':
                             {'action-name': 'open-container',
                              'container-index': index
                             }}
                         ))
        open_container_menu = sorted(open_container_menu,
                                     key=lambda x: x[0].upper())

        found_container = False
        if len(open_container_menu) == 1:
            found_container = True
            action_menu.append(
                (('Open %s' % open_container_menu[0][0]),
                 {'action': {
                    'action-name': 'open-container',
                    'container-index':
                    open_container_menu[0][1]['action']['container-index']}}
                 ))

        elif len(open_container_menu) > 1:
            found_container = True
            action_menu.append(('Open Container', {'menu': open_container_menu}))

        # Move item INTO container & FROM container

        # containers = [(index, name), ...]
        # container = current container
        for container_index, container_name in containers:
            move_into_menu = []
            for index, item in enumerate(container):
                if index == container_index:
                    continue # Don't ask to move an item into itself
                name = item['name']
                verbose_option = self.get_option('verbose')
                if verbose_option is not None and verbose_option:
                    name = '%d: %s' % (index, item['name'])

                move_into_menu.append(
                        (name,
                         {'action': {'action-name': 'move-between-container',
                                     'item-index': index,
                                     'item-name': item['name'],
                                     'destination-index': container_stack + [container_index],
                                     }}
                         ))
            move_into_menu = sorted(move_into_menu, key=lambda x: x[0].upper())

            # 'Move' menus - they're the same length because they're the size
            # of the number of items at this container level.

            if len(move_into_menu) == 1:
                action_menu.append(
                    ('move %s into %s' % (move_into_menu[0][0], container_name),
                     {'action': {'action-name': 'move-between-container',
                                 'item-index':
                                 move_into_menu[0][1]['action']['item-index'],
                                 'container-index': container_stack + [container_index]}
                      }))

            elif len(move_into_menu) > 1:
                action_menu.append((('move item to %s' % container_name),
                                    {'menu': move_into_menu}))

        # Move item FROM container

        if len(container_stack) > 0:
            move_from_menu = []
            for index, item in enumerate(container):
                #if index == container_index:
                #    continue # Don't ask to move an item into itself
                name = item['name']
                verbose_option = self.get_option('verbose')
                if verbose_option is not None and verbose_option:
                    name = '%d: %s' % (index, item['name'])
                move_from_menu.append(
                        (name,
                         {'action': {'action-name': 'move-between-container',
                                     'item-index': index,
                                     'item-name': item['name'],
                                     'destination-index': [],
                                     }}
                         ))
            move_from_menu = sorted(move_from_menu, key=lambda x: x[0].upper())

            # 'Move' menus - they're the same length because they're the size
            # of the number of items at this container level.

            if len(move_from_menu) == 1:
                action_menu.append(
                    ('move %s to top-level' % move_from_menu[0][0],
                     {'action': {'action-name': 'move-between-container',
                                 'item-index':
                                 move_from_menu[0][1]['action']['item-index'],
                                 'destination-index': []}
                      }))

            elif len(move_from_menu) > 1:
                action_menu.append(('move item to top-level',
                                    {'menu': move_from_menu}))

        # Can't don/doff/draw/holster armor/weapons while a container is open

        if len(fighter.details['open-container']) > 0:
            # Close Container
            item = fighter.equipment.get_item_by_index(
                    fighter.details['open-container'][-1],
                    fighter.details['open-container'][:-1])
            name = ('container' if item is None or 'name' not in item else
                    item['name'])

            action_menu.append((('Close %s' % name),
                                {'action': {'action-name': 'close-container'}}))
            return  # No need to return action menu since it was a parameter

        # ARMOR #

        # Armor SUB-menu

        armor_indexes = fighter.get_current_armor_indexes()

        don_armor_menu = []   # list of armor that may be donned this turn
        for index, item in enumerate(fighter.details['stuff']):
            if 'armor' in item['type']:
                if index not in armor_indexes:
                    verbose_option = self.get_option('verbose')
                    if verbose_option is not None and verbose_option:
                        entry_name = '%d: %s' % (index, item['name'])
                    else:
                        entry_name = '%s' % item['name']

                    don_armor_menu.append(
                            (entry_name,
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

        armor_list = fighter.get_items_from_indexes(armor_indexes)
        for index, armor in zip(armor_indexes, armor_list):
            if ('natural-armor' not in armor or not armor['natural-armor']):
                action_menu.append(
                        (('Doff %s' % armor['name']),
                         {'action': {'action-name': 'doff-armor',
                                     'armor-index': index}}
                         ))

        # DRAW OR HOLSTER WEAPON #

        if holding_non_natural_weapon:
            for index, weapon in enumerate(weapons):
                weapon_index = weapon_indexes[index]
                if not ca_equipment.Weapon.is_natural_weapon(weapon.details):
                    action_menu.append(
                            (('holster/sheathe %s' % weapon.details['name']),
                             {'action': {'action-name': 'holster-weapon',
                                         'weapon-index': weapon_index}
                              }))

        if len(weapons) < ca_fighter.Fighter.MAX_WEAPONS:
            # Draw weapon SUB-menu

            draw_weapon_menu = []   # weapons that may be drawn this turn
            for index, item in enumerate(fighter.details['stuff']):
                if (ca_equipment.Weapon.is_weapon(item) and
                        index not in weapon_indexes):
                    verbose_option = self.get_option('verbose')
                    if verbose_option is not None and verbose_option:
                        entry_name = '%d: %s' % (index, item['name'])
                    elif index in fighter.details['preferred-weapon-index']:
                        # Add a leading space so it's sorted to the top
                        entry_name = ' %s (preferred)' % item['name']
                    else:
                        entry_name = '%s' % item['name']

                    draw_weapon_menu.append(
                        (entry_name,
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

        if holding_ranged and len(weapons) == 1:
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

            verbose_option = self.get_option('verbose')
            if verbose_option is not None and verbose_option:
                name = '%d: %s' % (index, name)

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

        reload_option = self.get_option('reload-on-heal')
        if (reload_option is not None and reload_option and
                fighter.group == 'PCs'):
            weapon_indexes = fighter.get_current_weapon_indexes()
            for index, item in enumerate(fighter.details['stuff']):
                if 'ranged weapon' in item['type']:
                    self.do_action(fighter,
                                   {'action-name': 'draw-weapon',
                                    'weapon-index': index,
                                    'notimer': True},
                                   None)
                    self.do_action(fighter,
                                   {'action-name': 'reload',
                                    'comment': 'Reloading on heal',
                                    'notimer': True,
                                    'quiet': True},
                                   None)
            for original_weapon_index in weapon_indexes:
                self.do_action(fighter,
                               {'action-name': 'draw-weapon',
                                'weapon-index': original_weapon_index,
                                'notimer': True},
                               None)


    def is_creature_consistent(self,
                               name,     # string: creature's name
                               creature, # dict from Game File
                               fight_handler=None
                               ):
        '''
        Make sure creature's information makes sense.
        '''
        result = True

        # Don't need to check if the room is consistent.
        if name == ca_fighter.Venue.name:
            return True

        # TODO: remove <<<
        # This is just a shim to let pre-2-weapon crash files work (for
        # testing).  If we get a 'draw' action with None weapon, we'll turn
        # it into a 'holster' action for all of the weapons we're carrying.
        #print('\n\n====== MODIFYING %s ======\n' % name)
        #PP = pprint.PrettyPrinter(indent=3, width=150)
        #PP.pprint(creature)
        if type(creature['weapon-index']) is not list:
            new_stuff = [creature['weapon-index']]
            creature['weapon-index'] = new_stuff
        if ("preferred-weapon-index" in creature and
                type(creature['preferred-weapon-index']) is not list):
            new_stuff = ([] if creature['preferred-weapon-index'] is None
                         else [creature['preferred-weapon-index']])
            creature['preferred-weapon-index'] = new_stuff
        # TODO: remove >>>

        fighter = ca_fighter.Fighter(name,
                                     'dummy group',  # unused
                                     creature,
                                     self,
                                     self._window_manager)

        # First, let's make sure that they have all the required parts.

        for key, value in ca_fighter.Fighter.strawman.iteritems():
            if key not in creature:
                creature[key] = value

        # Next, check that their preferred armor / weapons agrees with what
        # they're carrying

        playing_back = (False if fight_handler is None else
                        fight_handler.world.playing_back)

        if not playing_back:
            self.__configure_armor_weapons(fighter, is_armor=True)  # Armor
            self.__configure_armor_weapons(fighter, is_armor=False) # Weapons

        return result

    def make_empty_creature(self):
        '''
        Builds the minimum legal character detail (the dict that goes into the
        Game File).  You can feed this to the constructor of a Fighter.  First,
        however, you need to install it in the World's Game File so that it's
        backed-up and recognized by the rest of the software.

        Returns: the dict.
        '''
        return {'actions_this_turn': [],
                'armor-index': [], # can wear multiple armors over each other
                'current': {},
                'fight-notes': [],
                'notes': [],
                'opponent': None,
                'permanent': {},
                'preferred-armor-index': [],
                'preferred-weapon-index': [],
                'state': 'alive',
                'stuff': [],
                'timers': [],
                'weapon-index': None,
                'current-weapon': 0,    # Indexes into 'weapon-index'.
                'open-container': []
                }

    def search_one_thing(self,
                         name,        # string containing the name
                         group,       # string containing the group
                         thing,       # dict describing a thing
                         look_for_re  # compiled Python regex
                         ):
        result = []
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
        if 'container' in thing['type']:
            for sub_thing in thing['stuff']:
                sub_result = self.search_one_thing(name,
                                                   group,
                                                   sub_thing,
                                                   look_for_re)
                result.extend(sub_result)
        return result

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
                sub_result = self.search_one_thing(name,
                                                   group,
                                                   thing,
                                                   look_for_re)
                result.extend(sub_result)

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

    def set_timing_file(self,
                        file_handle,
                        is_new=False
                        ):
        self._timing_file = file_handle
        if self._timing_file is not None and is_new:
            for heading in Ruleset.timing_headings:
                self._timing_file.write('"%s", ' % heading)
            self._timing_file.write('\n')

    def start_turn(self,
                   fighter,         # Fighter object
                   fight_handler    # FightHandler object
                   ):
        '''
        Performs all of the stuff required for a Fighter to start his/her
        turn.  Does all the consciousness/death checks, etc.

        Returns: nothing
        '''
        pass

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
                   fight_handler,    # FightHandler object (ignored)
                   ):
        '''
        Action handler for Ruleset.

        Adjust the Fighter's hit points.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.details['current']['hp'] += action['adj']
        return Ruleset.HANDLED_OK


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
        attr_type = action['attr-type']
        attr = action['attribute']
        new_value = action['new-value']
        fighter.details[attr_type][attr] = new_value
        return Ruleset.HANDLED_OK

    def __show_weapons_armor(self,
                             fighter,
                             is_armor):
        '''
        Displays the current state of the fighter's weapons or armor.
        FOR DEBUGGING ONLY
        '''
        if is_armor:
            index_list = fighter.get_current_armor_indexes()
            preferred_index = 'preferred-armor-index'
            action_index = 'armor-index'
            item_string = 'armor'
            items_string = 'armor'
            natural_item = 'natural-armor'
        else:
            index_list = fighter.get_current_weapon_indexes()
            preferred_index = 'preferred-weapon-index'
            action_index = 'weapon-index'
            item_string = 'weapon'
            items_string = 'weapons'
            natural_item = 'natural-weapon'

        print '\n--- %s\'s %s ---' % (fighter.name, items_string)
        for index in index_list:
            item = fighter.equipment.get_item_by_index(index)
            name = '<None>' if item is None else item['name']
            print '  %d: %s' % (index, name)

        print '--- in use %s ---' % items_string
        for index in fighter.details[action_index]:
            item = fighter.equipment.get_item_by_index(index)
            name = '<None>' if item is None else item['name']
            print '  %d: %s' % (index, name)

        print '--- preferred %s ---' % items_string
        for index in fighter.details[preferred_index]:
            item = fighter.equipment.get_item_by_index(index)
            name = '<None>' if item is None else item['name']
            print '  %d: %s' % (index, name)

    def __configure_armor_weapons(self,
                                  fighter,      # Fighter object
                                  is_armor=True # If False, configure weapons
                                  ):
        '''
        Asks to remove armor/weapons from current list if it's not in preferred
            list.
        Asks to add armor/weapons to current list if it is in preferred list.
        Removes any 'current' armor/weapons that's not actually armor/weapons
        If, after all that, there's no armor/weapons being worn but there's
            natural armor/weapons, wear that.
        '''
        if is_armor:
            index_list = fighter.get_current_armor_indexes()
            preferred_index = 'preferred-armor-index'
            on_action = 'don-armor'
            off_action = 'doff-armor'
            action_index = 'armor-index'
            item_string = 'armor'
            items_string = 'armor'
            natural_item = 'natural-armor'
        else:
            index_list = fighter.get_current_weapon_indexes()
            preferred_index = 'preferred-weapon-index'
            on_action = 'draw-weapon'
            off_action = 'holster-weapon'
            action_index = 'weapon-index'
            item_string = 'weapon'
            items_string = 'weapons'
            natural_item = 'natural-weapon'

        # Dump non-armor/weapon being worn as armor/weapon

        item_list = []
        for item_index in index_list:
            item = fighter.equipment.get_item_by_index(item_index)
            item_list.append(item)

        for index, item in zip(index_list, item_list):
            if item is None:
                self._window_manager.error([
                    'Creature "%s"' % fighter.name,
                    '  is using a weird %s "<None>". Fixing.' % item_string])
                self.do_action(fighter,
                               {'action-name': off_action,
                                action_index: index,
                                'notimer': True},
                               None)
                result = False
            elif ((is_armor and 'armor' not in item['type']) or
                    (not is_armor and
                        not ca_equipment.Weapon.is_weapon(item))):
                self._window_manager.error([
                    ('Creature "%s"' % fighter.name),
                    ('  is using a weird %s "%s". Fixing.' %
                        (item_string, item['name']))
                    ])
                self.do_action(fighter,
                               {'action-name': off_action,
                                action_index: index,
                                'notimer': True},
                               None)
                result = False

        # Dump non-armor/weapon that is preferred armor/weapon

        preferred_item_list = []
        preferred_index_list = fighter.details[preferred_index]

        for item_index in preferred_index_list:
            item = fighter.equipment.get_item_by_index(item_index)
            if item is not None:
                preferred_item_list.append(item)

        for index, item in zip(preferred_index_list, preferred_item_list):
            if item is None:
                self._window_manager.error([
                    'Creature "%s"' % fighter.name,
                    '  is preferring a weird %s "<None>". Fixing.' %
                    item_string])
                fighter.details[preferred_index].remove(index)
                result = False
            elif ((is_armor and 'armor' not in item['type']) or
                    (not is_armor and
                        not ca_equipment.Weapon.is_weapon(item))):
                self._window_manager.error([
                    ('Creature "%s"' % fighter.name),
                    ('  is preferring a weird %s "%s". Fixing.' %
                        (item_string, item['name']))
                    ])
                fighter.details[preferred_index].remove(index)
                result = False

        # Check to see if they have preferred armor/weapon at all

        if len(fighter.details[preferred_index]) == 0:
            owned_item_count = 0
            item_index = None
            for index, item in enumerate(fighter.details['stuff']):
                if ((is_armor and 'armor' in item['type']) or
                        (not is_armor and
                            ca_equipment.Weapon.is_weapon(item))):
                    owned_item_count += 1
                    item_index = index # only useful w/just 1 owned armor
            if owned_item_count == 0:
                pass
            elif owned_item_count == 1:
                fighter.details[preferred_index] = [item_index]
            else: # owns more than one piece of armor
                self._window_manager.error([
                    'Creature "%s" has no preferred %s' %
                    (fighter.name, item_string)])

        # Next, remove non-preferred weapon/armor

        keep_asking = True
        while keep_asking:
            index_list = (fighter.get_current_armor_indexes() if is_armor else
                fighter.get_current_weapon_indexes())
            item_list_menu = []
            for item_index in index_list:
                if item_index not in fighter.details[preferred_index]:
                    item = fighter.equipment.get_item_by_index(
                            item_index)
                    item_list_menu.append(('stop using %s' % item['name'],
                                            ('stop', item_index)))
                    # If the preferred list is not full, ask user if s/he wants
                    # to add _this_ item to the preferred list.
                    if (not is_armor or
                            len(fighter.details[preferred_index])
                            < ca_fighter.Fighter.MAX_WEAPONS):
                        item_list_menu.append(('prefer %s' % item['name'],
                                                ('prefer', item_index)))
            if len(item_list_menu) == 0:
                keep_asking = False
            else:
                item_list_menu.append(
                        (('done dealing with non-preferred %s' % items_string),
                            None))
                title = 'Stop using %s\'s non-preferred %s?' % (fighter.name,
                                                                 item_string)
                item_index, ignore = self._window_manager.menu(title,
                                                               item_list_menu)
                if item_index is None:
                    keep_asking = False
                elif item_index[0] == 'stop':
                    self.do_action(fighter,
                                   {'action-name': off_action,
                                    action_index: item_index[1],
                                    'notimer': True},
                                   None)
                elif item_index[0] == 'prefer':
                    fighter.details[preferred_index].append(item_index[1])

        # Now, add preferred armor/weapon

        keep_asking = True
        while keep_asking:
            index_list = (fighter.get_current_armor_indexes() if is_armor else
                fighter.get_current_weapon_indexes())
            item_list_menu = []
            for preferred_item_index in fighter.details[preferred_index]:
                if preferred_item_index not in index_list:
                    item = fighter.equipment.get_item_by_index(
                            preferred_item_index)
                    item_list_menu.append(
                        ('use %s' % item['name'],
                            ('use', preferred_item_index)))
                    item_list_menu.append(
                        ('Un-prefer %s' % item['name'],
                            ('unprefer', preferred_item_index)))
            if len(item_list_menu) == 0:
                keep_asking = False
            else:
                item_list_menu.append(
                    (('done dealing with preferred %s' % items_string), None))
                preferred_item_index, ignore = self._window_manager.menu(
                        'Use %s\'s preferred %s?' % (fighter.name,
                                                     item_string),
                        item_list_menu)
                if preferred_item_index is None:
                    keep_asking = False
                elif preferred_item_index[0] == 'use':
                    self.do_action(fighter,
                                   {'action-name': on_action,
                                    action_index: preferred_item_index[1],
                                    'notimer': True},
                                   None)
                elif preferred_item_index[0] == 'unprefer':
                    fighter.details[preferred_index].remove(preferred_item_index[1])

        # Add natural weapon/armor if they're not wearing any other kind -- ok, I think

        # TODO (now): natural ARMOR should _always_ be selected, not just if
        # there's no other armor.

        if len(index_list) == 0:
            for index, item in enumerate(fighter.details['stuff']):
                if natural_item in item and item[natural_item]:
                    self.do_action(fighter,
                                   {'action-name': on_action,
                                    action_index: index,
                                    'notimer': True},
                                   None)

        # Make sure that all missile weapons have their associated ammo.

        if not is_armor:    # Just weapons (just ranged weapons, actually)
            for weapon in fighter.details['stuff']:
                if 'ranged weapon' not in weapon['type']:
                    continue
                clip_name = weapon['ammo']['name']
                found_clip = False
                for clip in fighter.details['stuff']:
                    if clip['name'] == clip_name:
                        found_clip = True
                        break
                if not found_clip:
                    self._window_manager.error([
                        '"%s"' % fighter.name,
                        '  is carrying a weapon (%s) with no ammo (%s).' % (
                            weapon['name'], clip_name)])

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

        weapons = fighter.get_current_weapons()

        action['weapon-index'] = None
        if len(weapons) == 0:
            return Ruleset.HANDLED_OK

        # 'current-weapon' indexes into 'weapon-index' and points to the weapon
        # in the hand that's attacking right now.
        if fighter.details['current-weapon'] >= len(weapons):
            return Ruleset.HANDLED_OK
        weapon = weapons[fighter.details['current-weapon']]
        if weapon is None:
            return Ruleset.HANDLED_OK
        action['weapon-index'] = fighter.details['current-weapon']

        # Used for a fighter with two weapons.  Advance the index of the weapon
        # being used for the next attack in the same round.  We're advancing it
        # a little early to get out ahead of early returns.  We've already used
        # it's value so it's ok to advance it, here.

        # Wrap around so that you can attack more than once in a round (in
        # order to fix mistakes during battle).
        fighter.details['current-weapon'] = (
                (fighter.details['current-weapon'] + 1) % len(weapons))

        if not weapon.uses_ammo():
            return Ruleset.HANDLED_OK

        clip = weapon.get_clip()
        if weapon.use_one_ammo():
            clip = weapon.get_clip()
            if (clip is not None and 'notes' in clip and
                    clip['notes'] is not None and len(clip['notes']) > 0):
                self._window_manager.display_window(
                    'Shot Fired',
                    [[{'text': ('%s' % clip['notes']),
                   'mode': curses.A_NORMAL}]])
            return Ruleset.HANDLED_OK

        # out of ammo
        clip_name = ('Clip' if clip is None or 'name' not in clip
                     else clip['name'])
        self._window_manager.error([
            'You\'re empty mister',
            'No shots left in %s' % clip_name])

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
        # You can't reload if both hands are full.
        weapons = fighter.get_current_weapons()
        if weapons is None or len(weapons) != 1:
            return Ruleset.HANDLED_ERROR

        weapon = weapons[0]
        if weapon is None:
            return Ruleset.HANDLED_OK

        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part of the action
            # actually perfoms all the GurpsRuleset-specific actions and
            # side-effects of reloading the Fighter's current weapon.  Note
            # that a lot of the obvious part is done by the base class Ruleset.

            # If there's no new clip to load, just bail out
            if 'clip-index' not in action:
                return Ruleset.HANDLED_OK

            # xxx

            infinite_clips_option = self.get_option('infinite-clips')
            infinite_clips = True if (infinite_clips_option is not None and
                    infinite_clips_option) else False

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

            if not weapon.uses_ammo():
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

            if len(clip_menu) == 0:
                self._window_manager.error([
                    'No clips of type %s available for %s' % (clip_name,
                                                              weapon.name)])

            clip_index, ignore = self._window_manager.menu('Reload With What',
                                                           clip_menu)
            if clip_index is None:
                # TODO (eventually): there should be a way to tell the derived
                #   ruleset that we're aborting early.
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
                    fight_handler,    # FightHandler object (ignored)
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
                    fight_handler,    # FightHandler object (ignored)
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
                      fight_handler,    # FightHandler object (ignored)
                      ):
        '''
        Action handler for Ruleset.

        Draws a specific weapon for the Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        # TODO: remove <<<
        # This is just a shim to let pre-2-weapon crash files work (for
        # testing).  If we get a 'draw' action with None weapon, we'll turn
        # it into a 'holster' action for all of the weapons we're carrying.
        if action['weapon-index'] is None:
            weapon_indexes = fighter.get_current_weapon_indexes()
            for weapon_index in weapon_indexes:
                new_action = copy.deepcopy(action)
                new_action['action-name'] = 'holster-weapon'
                new_action['weapon-index'] = weapon_index
                self.do_action(fighter, new_action, fight_handler)
            return Ruleset.HANDLED_ERROR # Just so the derived class does nothing
        # TODO: remove >>>

        # TODO (eventually): draw weapon from counted item (that takes clips)
        #   makes a copy
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

        if self._char_being_timed is None:
            pass # TODO: error
        elif (fighter.name != self._char_being_timed['name'] or
                fighter.group != self._char_being_timed['group']):
            pass # TODO: error
        else:
            self._char_being_timed['end'] = datetime.datetime.now()
            self._char_being_timed['time'] = (self._char_being_timed['end'] -
                          self._char_being_timed['start']).total_seconds()
            if self._timing_file is not None:
                for heading in Ruleset.timing_headings:
                    if heading in self._char_being_timed:
                        self._timing_file.write('"%s", ' %
                                self._char_being_timed[heading])
                    else:
                        self._timing_file.write(', ')
                self._timing_file.write('\n')

        if fight_handler is not None:
            fighter.end_turn(fight_handler)
            fight_handler.modify_index(1)
        return Ruleset.HANDLED_OK

    def get_option(self,
                    option_name     # string: name of option to get
                    ):
        if self.options is None:
            return None
        return self.options.get_option(option_name)

    def __give_equipment(self,
                         fighter,          # Fighter object
                         action,           # {'action-name': 'end-turn',
                                           #  'item-index': item_index,
                                           #  'count': number of items to tive,
                                           #  'recipient': to_fighter_info
                                           #  'comment': <string> # optional
                         fight_handler,    # FightHandler object
                         ):
        '''
        Action handler for Ruleset.

        Gives an item from fighter to another.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)

        '''
        if fight_handler is None:
            #NOTE: got no 'world' or I could do this:
            # if action['recipient']['group'] == 'PCs':
            #     recipient = self.world.get_creature(to_fighter_info, 'PCs')
            # else:
            self._window_manager.error([
                'You can only give equipment during a fight'])
            return Ruleset.HANDLED_ERROR
        else:
            ignore, recipient = fight_handler.get_fighter_object(
                                            action['recipient']['name'],
                                            action['recipient']['group'])

        item = fighter.remove_equipment(action['item-index'], action['count'])
        if item is None:
            self._window_manager.error(['No item to transfer'])
            return Ruleset.HANDLED_ERROR

        identified = False if recipient.group != fighter.group else None

        if fighter.group == 'PCs':
            source = fighter.detailed_name
        else:
            source = '%s:%s' % (fighter.group,
                                fighter.detailed_name)
        ignore = recipient.add_equipment(item, source, identified)
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
        in_place = (True if 'in-place' in action and action['in-place']
                    else False)
        fight_handler.wait_end_action(action['name'],
                                      action['group'],
                                      in_place)
        return Ruleset.HANDLED_OK

    def __holster_weapon(self,
                         fighter,          # Fighter object
                         action,           # {'action-name': 'holster-weapon',
                                           #  'weapon-index': <int> # index in
                                           #       fighter.details['stuff'],
                                           #       None drops weapon
                                           #  'comment': <string> # optional
                         fight_handler,    # FightHandler object (ignored)
                         ):
        '''
        Action handler for Ruleset.

        Draws a specific weapon for the Fighter.  If index in None, it
        holsters the current weapon.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.holster_weapon_by_index(action['weapon-index'])
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
            'adjust-attribute':     {'doit': self.__adjust_attribute},
            'all-out-attack':       {'doit': self.__do_attack},
            'attack':               {'doit': self.__do_attack},
            'close-container':      {'doit': self.__close_container},
            'doff-armor':           {'doit': self.__doff_armor},
            'don-armor':            {'doit': self.__don_armor},
            'draw-weapon':          {'doit': self.__draw_weapon},
            'end-turn':             {'doit': self.__end_turn},
            'give-equipment':       {'doit': self.__give_equipment},
            'holster-weapon':       {'doit': self.__holster_weapon},
            'move-and-attack':      {'doit': self.__do_attack},
            'move-between-container':
                                    {'doit': self.__move_to_container},
            'open-container':       {'doit': self.__open_container},
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

        # Label the action so playback knows who receives it.

        action['fighter'] = {'name': fighter.name,
                             'group': fighter.group}

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

    def __close_container(self,
                        fighter,          # Fighter object
                        action,           # {'action-name': 'close-container',
                                          #  'comment': <string> # optional
                        fight_handler,    # FightHandler object (ignored)
                        ):
        '''
        Action handler for Ruleset.

        Closes the deepest open container.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        fighter.details['open-container'].pop()
        return Ruleset.HANDLED_OK

    def __move_to_container(
            self,
            fighter,          # Fighter object
            action,           # {'action-name': 'move-between-container',
                              #  'item-index': index,
                              #  'item-name': string
                              #  'destination-index': [index, index,...
            fight_handler,    # FightHandler object (ignored)
            ):
        '''
        Action handler for Ruleset.

        Moves all copies of an item from the CURRENT container level into
        another arbitrary container.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        # Put item in container (first, so it doesn't mess-up indexes)
        item = fighter.equipment.get_item_by_index(
                action['item-index'], fighter.details['open-container'])
        ignore = fighter.add_equipment(
                item,
                source=None,
                identified=None,
                container_stack=action['destination-index'])

        # Now, remove item
        count = 1 if 'count' not in item else item['count']
        ignore_item = fighter.remove_equipment(action['item-index'],
                                               count,
                                               fighter.details['open-container'])

        return Ruleset.HANDLED_OK

    def __open_container(self,
                        fighter,          # Fighter object
                        action,           # {'action-name': 'open-container',
                                          #  'container-index': int,
                                          #  'comment': <string> # optional
                        fight_handler,    # FightHandler object (ignored)
                        ):
        '''
        Action handler for Ruleset.

        Opens the designated container from the fighter's stuff (or from the
        currently open container, if there is one)

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''
        fighter.details['open-container'].append(action['container-index'])
        #PP = pprint.PrettyPrinter(indent=3, width=150) # TODO: remove
        #print '\n--- %s: open %d ---' % (fighter.name, action['container-index']) # TODO: remove
        #PP.pprint(fighter.details['open-container']) # TODO: remove
        return Ruleset.HANDLED_OK

    def __pick_opponent(self,
                        fighter,          # Fighter object
                        action,           # {'action-name': 'pick-opponent',
                                          #  'opponent':
                                          #     {'name': opponent_name,
                                          #      'group': opponent_group},
                                          #  'comment': <string> # optional
                        fight_handler,    # FightHandler object (ignored)
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

        # Copy the action name into the timing information

        action_name = (None if 'action-name' not in action else
                action['action-name'])
        if self._char_being_timed is None:
            pass # TODO: error
        elif (fighter.name != self._char_being_timed['name'] or
                fighter.group != self._char_being_timed['group']):
            pass # This happens, e.g., when the opponent loses HP
        elif (action_name is not None and
                action_name in self.active_actions):
            # I know this may overwrite an existing action - that's ok
            self._char_being_timed['action'] = action_name

        return

    def __set_consciousness(self,
                            fighter,          # Fighter object
                            action,           # {'action-name':
                                              #     'set-consciousness',
                                              #  'level': <int> # see
                                              #         Fighter.conscious_map
                                              #  'comment': <string> # optional
                            fight_handler,    # FightHandler object (ignored)
                            ):
        '''
        Action handler for Ruleset.

        Configures the consciousness state of the Fighter.

        Returns: Whether the action was successfully handled or not (i.e.,
        UNHANDLED, HANDLED_OK, or HANDLED_ERROR)
        '''

        fighter.set_consciousness(action['level'], fight_handler)
        return Ruleset.HANDLED_OK

    def __set_timer(self,
                    fighter,          # Fighter object
                    action,           # {'action-name': 'set-timer',
                                      #  'timer': <dict> # see
                                      #                    Timer::from_pieces
                                      #  'comment': <string> # optional
                    fight_handler,    # FightHandler object (ignored)
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
        # The 1st weapon the fighter messes with should be the 1st one in the
        # weapon-index list (i.e., the weapon in the fighter's dominant hand.
        fighter.details['current-weapon'] = 0

        # TODO: if _char_being_timed is None, do whatever we do
        self._char_being_timed = {'name': fighter.name,
                                  'group': fighter.group,
                                  'start': datetime.datetime.now(),
                                  'state': fighter.details['state'],
                                  'round': fight_handler.get_round()}

        fighter.start_turn(fight_handler)

        return Ruleset.HANDLED_OK

    def __use_item(self,
                   fighter,          # Fighter object
                   action,           # {'action-name': 'use-item',
                                     #  'item-index': <int> # index in
                                     #       fighter.details['stuff']
                                     #  'comment': <string>, # optional
                   fight_handler,    # FightHandler object (ignored)
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
