#! /usr/bin/python

import copy
import curses
import pprint

import ca_equipment
import ca_timers


class ThingsInFight(object):
    '''
    Base class to manage timers, equipment, and notes for Fighters and Venues.
    '''
    def __init__(self,
                 name,           # string, name of the thing
                 group,          # string to index into world['fights']
                 details,        # world.details['fights'][name] (world is
                                 #   a World object)
                 ruleset,        # Ruleset object
                 window_manager  # GmWindowManager object for reporting errors
                 ):
        self.name = name
        self.detailed_name = self.name
        self.group = group
        self.details = details
        self._ruleset = ruleset
        self._window_manager = window_manager

        # Equipment

        if 'stuff' not in self.details:     # Public to facilitate testing
            self.details['stuff'] = []

        self.equipment = ca_equipment.Equipment(self.name,
                                                self.details['stuff'])

        # Timers

        if 'timers' not in details:
            details['timers'] = []
        self.timers = ca_timers.Timers(self.details['timers'],
                                       self,
                                       self._window_manager)

    #
    # Equipment related methods
    #

    def add_equipment(self,
                      new_item,         # dict describing new equipment
                      source=None,      # string: from where did equipment come
                      identified=None,  # ignored, here
                      container_stack=[]
                      ):
        '''
        Accept a new item of equipment and put it in the list.

        Returns the new index of the equipment (for testing).
        '''
        return self.equipment.add(new_item, source, container_stack)

    def ask_how_many(self,
                     item_index,    # index into fighter's stuff list
                     count=None,    # number to remove (None if 'ask')
                     container_stack=[]
                     ):
        '''
        Determine how many items to remove.
        '''
        item = self.equipment.get_item_by_index(item_index, container_stack)
        if item is None:
            return 0
        current_item_count = 1 if 'count' not in item else item['count']

        if current_item_count < 1:
            return 0
        if current_item_count == 1:
            return current_item_count
        if count is not None:
            return count

        # Ask how many to remove

        title = 'How Many Items (%d Available)?' % current_item_count
        height = 1
        width = len(title)
        item_count = self._window_manager.input_box_number(height,
                                                           width,
                                                           title)
        if item_count is None:
            return 0

        if item_count > current_item_count:
            item_count = current_item_count

        return item_count

    def get_ruleset(self):
        return self._ruleset

    def remove_equipment(self,
                         item_index,        # index into fighter's stuff list
                         count=None,        # number to remove (None if 'ask')
                         container_stack=[]
                         ):
        '''
        Discards an item from the Fighter's/Venue's equipment list.

        Returns: the discarded item
        '''
        count = self.ask_how_many(item_index, count, container_stack)
        return self.equipment.remove(item_index, count, container_stack)

    #
    # Notes methods
    #

    def get_defenses_notes(self,
                           opponent  # Throw away Fighter object
                           ):
        '''
        Returns a tuple of strings describing:

        1) the current (based on weapons held, armor worn, etc) defensive
           capability of the Fighter, and
        2) the pieces that went into the above calculations

        Or, in the case of the base class, None.
        '''
        return None, None

    def get_description_medium(
            self,
            output,         # [[{'text':...,'mode':...}...
            fighter,        # Fighter object
            opponent,       # Fighter object
            is_attacker,    # True | False
            ):

        '''
        Returns a string that contains a short (but not the shortest)
        description of the state of the Fighter or Venue.
        '''
        return '%s' % self.name

    def get_description_short(self,
                              fight_handler  # FightHandler, ignored
                              ):
        '''
        Returns a string that contains the shortest description of the Fighter.
        '''
        return '%s' % self.name

    def get_notes(self):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.).  There's decidedly less information than that returned by the
        base class.
        '''
        return None

    def get_to_hit_damage_notes(self,
                                opponent  # Throw away Fighter object
                                ):
        '''
        Returns a list of strings describing the current (using the current
        weapon, in the current posture, etc.) fighting capability (to-hit and
        damage) of a fighter.  It does nothing in the base class.
        '''
        return None

    #
    # Miscellaneous methods
    #

    def end_fight(self,
                  fight_handler   # FightHandler object
                  ):
        '''
        Perform the post-fight cleanup.  Remove all the timers, that sort of
        thing.

        Returns nothing.
        '''
        self.timers.clear_all()

    def explain_numbers(self,
                        fight_handler  # FightHandler object, ignored
                        ):
        '''
        Explains how the stuff in the descriptions were calculated.

        Returns [[{'text':x, 'mode':x}, {...}], [], [], ...]
            where the outer array contains lines
            each line is an array that contains a line-segment
            each line segment has its own mode so, for example, only SOME of
               the line is shown in bold
        '''
        return [[{'text': '(Nothing to explain)', 'mode': curses.A_NORMAL}]]

    def start_fight(self):
        '''
        Configures the Fighter or Venue to start a fight.

        Returns nothing.
        '''
        pass


class Venue(ThingsInFight):
    '''
    Incorporates all of the information for a room (or whatever).  This is the
    mechanism whereby items can be distributed in a room.  The data
    is just a pointer to the Game File data so that it's edited in-place.
    '''
    name = '<< ROOM >>'                 # Describes the FIGHT object
    detailed_name = '<< ROOM: %s >>'    # insert the group into the '%s' slot
    empty_venue = {
        'stuff': [],
        'notes': [],
        'timers': []
    }

    def __init__(self,
                 group,          # string to index into world['fights']
                 details,        # world.details['fights'][name] (world is
                                 #   a World object)
                 ruleset,        # Ruleset object
                 window_manager  # GmWindowManager object for error reporting
                 ):
        super(Venue, self).__init__(Venue.name,
                                    group,
                                    details,
                                    ruleset,
                                    window_manager)
        self.detailed_name = Venue.detailed_name % group

    def get_description_long(self,
                             output,  # recepticle for character detail.
                                      #     [[{'text','mode'},...],  # line 0
                                      #      [...],               ]  # line 1..
                             expand_containers   # Bool, ignored in the base class
                             ):
        '''
        Provides a text description of all of the components of a Venue.

        Returns: nothing -- output is written to the |output| variable
        '''

        # stuff

        mode = curses.A_NORMAL
        output.append([{'text': 'Equipment',
                             'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'stuff' in self.details:
            for item in sorted(self.details['stuff'], key=lambda x: x['name']):
                found_one = True
                ca_equipment.EquipmentManager.get_description(
                        item, '', [], False, output)

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # Timers

        mode = curses.A_NORMAL
        output.append([{'text': 'Timers', 'mode': mode | curses.A_BOLD}])

        found_one = False
        timers = self.timers.get_all()  # objects
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

        # Notes

        mode = curses.A_NORMAL
        output.append([{'text': 'Notes', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in self.details:
            for note in self.details['notes']:
                found_one = True
                output.append([{'text': '  %s' % note, 'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

    def get_description_short(self,
                              fight_handler  # FightHandler, ignored
                              ):
        '''
        Returns a string that contains the shortest description of the Fighter.
        '''
        fighter_string = '%s' % self.name

        if 'stuff' in self.details and len(self.details['stuff']) > 0:
            fighter_string += ' - EQUIP'

        if 'timers' in self.details and len(self.details['timers']) > 0:
            fighter_string += ' - TIMERS'

        if 'notes' in self.details and len(self.details['notes']) > 0:
            fighter_string += ' - NOTES'

        return fighter_string

    def get_state(self):
        return Fighter.FIGHT


class Fighter(ThingsInFight):
    '''
    Incorporates all of the information for a PC, NPC, or monster.  The data
    is just a pointer to the Game File data so that it's edited in-place.
    '''
    (ALIVE,
     UNCONSCIOUS,
     DEAD,

     INJURED,  # Injured is separate since it's tracked by HP
     ABSENT,
     FIGHT) = range(6)

    MAX_WEAPONS = 2 # because we only have 2 arms

    # When adding a new weapon, make it preferred?
    NOT_PREFERRED, ADD_PREFERRED, REPLACE_PREFERRED = range(3)

    conscious_map = {
        'alive': ALIVE,
        'unconscious': UNCONSCIOUS,
        'dead': DEAD,
        'Absent': ABSENT,  # Capitalized for menus
        'fight': FIGHT,
    }

    strawman = None

    def __init__(self,
                 name,              # string
                 group,             # string = 'PCs' or some monster group
                 fighter_details,   # dict as in the Game File
                 ruleset,           # a Ruleset object
                 window_manager     # a GmWindowManager object for display
                                    #   windows
                 ):
        super(Fighter, self).__init__(name,
                                      group,
                                      fighter_details,
                                      ruleset,
                                      window_manager)
        if Fighter.strawman is None:
            Fighter.strawman = ruleset.make_empty_creature()

    @staticmethod
    def get_fighter_state(details):
        '''
        Returns the fighter state number.  Note that Fighter.INJURED needs to
        be calculated -- we don't store that in the Fighter as a separate
        state.
        '''
        conscious_number = Fighter.conscious_map[details['state']]
        if (conscious_number == Fighter.ALIVE and
                details['current']['hp'] < details['permanent']['hp']):
            return Fighter.INJURED
        return conscious_number

    @staticmethod
    def get_name_from_state_number(number):
        for name, value in Fighter.conscious_map.iteritems():
            if value == number:
                return name
        return '<unknown>'

    #
    # Equipment related methods
    #

    def add_equipment(self,
                      new_item,         # dict describing new equipment
                      source=None,      # string: from where did equipment
                                        #   come (None for no change)
                      identified=None,  # Bool: no change if |None|
                      container_stack=[]
                      ):
        '''
        Accept a new item of equipment and put it in the list.

        Returns the new index of the equipment.
        '''
        # if 'owners' doesn't exist or is None, then it's a mundane item and
        # is indistinguishable from any similar item -- you don't need to know
        # its provenance and you don't need to identify it.
        if (identified is not None and 'owners' in new_item and
                new_item['owners'] is not None):
            new_item['identified'] = identified

        # If we're adding a weapon or a piece of armor, is it the first of
        # its kind?

        is_weapon = True if ca_equipment.Weapon.is_weapon(new_item) else False
        is_armor = True if 'armor' in new_item['type'] else False
        before_item_count = self.equipment.get_item_count()

        # Add the item
        new_item_index = self.equipment.add(new_item,
                                            source,
                                            container_stack)

        # if we're adding something to a container, then it can't be preferred.
        if len(container_stack) > 0:
            return new_item_index

        # If we're adding the creature's first weapon or armor, make it the
        # preferred weapon or armor.  If it's not the creature's first,
        # ask the user if it should be the creature's preferred.

        if new_item_index is not None:
            after_item_count = self.equipment.get_item_count()
            if is_weapon:
                if len(self.details['preferred-weapon-index']) > 0:
                    if before_item_count != after_item_count:
                        # Only ask if we've added a new weapon and not just
                        # bumped-up the count on a previous weapon
                        replace_preferred_menu = [
                                ('no', Fighter.NOT_PREFERRED),
                                ('replace existing',
                                    Fighter.REPLACE_PREFERRED)]
                        if (len(self.details['preferred-weapon-index']) <
                                Fighter.MAX_WEAPONS):
                            replace_preferred_menu.append(
                                    ('add to existing list',
                                        Fighter.ADD_PREFERRED))
                        replace_preferred, ignore = self._window_manager.menu(
                                'Make %s the preferred weapon?' %
                                new_item['name'],
                                replace_preferred_menu)

                        # If we're replacing an item, which one do we replace?
                        if replace_preferred == Fighter.REPLACE_PREFERRED:
                            remove_which_menu = []
                            for index in self.details['preferred-weapon-index']:
                                weapon = self.equipment.get_item_by_index(index)
                                remove_which_menu.append((weapon['name'], index))

                            remove_index, ignore = self._window_manager.menu(
                                    'Replace which weapon?',
                                    remove_which_menu)
                            if remove_index is None:
                                # I guess we're not replacing anything
                                replace_preferred = Fighter.NOT_PREFERRED
                            else:
                                self.details['preferred-weapon-index'].remove(
                                    remove_index)

                        if replace_preferred != Fighter.NOT_PREFERRED:
                            self.details['preferred-weapon-index'].append(
                                    new_item_index)
                else:
                    self.details['preferred-weapon-index'].append(new_item_index)
            if is_armor:
                if len(self.details['preferred-armor-index']) > 0:
                    if before_item_count != after_item_count:
                        # Only ask if we've added a new item and not just
                        # bumped-up the count on a previous item
                        replace_preferred_menu = [
                                ('no', Fighter.NOT_PREFERRED),
                                ('replace existing',
                                    Fighter.REPLACE_PREFERRED)]
                        replace_preferred_menu.append(
                                ('add to existing list',
                                    Fighter.ADD_PREFERRED))
                        replace_preferred, ignore = self._window_manager.menu(
                                'Make %s the preferred armor?' %
                                new_item['name'],
                                replace_preferred_menu)

                        # If we're replacing an item, which one do we replace?
                        if replace_preferred == Fighter.REPLACE_PREFERRED:
                            remove_which_menu = []
                            for index in self.details['preferred-armor-index']:
                                item = self.equipment.get_item_by_index(index)
                                remove_which_menu.append((item['name'], index))

                            remove_index, ignore = self._window_manager.menu(
                                    'Replace which piece of armor?',
                                    remove_which_menu)
                            if remove_index is None:
                                # I guess we're not replacing anything
                                replace_preferred = Fighter.NOT_PREFERRED
                            else:
                                self.details['preferred-armor-index'].remove(
                                    remove_index)

                        if replace_preferred != Fighter.NOT_PREFERRED:
                            self.details['preferred-armor-index'].append(
                                    new_item_index)
                else:
                    self.details['preferred-armor-index'].append(new_item_index)
        return new_item_index

    def doff_armor_by_index(self,
                            index  # Index of armor in fighter's 'stuff'
                                   # list.  'None' removes current armor.
                           ):
        '''Removes armor.'''

        if index not in self.details['armor-index']:
            return  # Not wearing the armor we want to taking off

        self.details['armor-index'].remove(index)

        # if we're doffing armor and there's natural armor, pick that
        # one up.
        for item_index, item in enumerate(self.details['stuff']):
            if (item_index not in self.details['armor-index'] and
                    'natural-armor' in item and item['natural-armor']):
                self.details['armor-index'].append(item_index)


    def don_armor_by_index(self,
                           index  # Index of armor in fighter's 'stuff'
                                  # list.  'None' removes current armor.
                           ):
        '''Puts on armor.'''

        if index not in self.details['armor-index']:
            self.details['armor-index'].append(index)

    def draw_weapon_by_index(self,
                             weapon_index  # Index of weapon in fighter's 'stuff'
                                           # list.
                             ):
        '''Draws weapon.'''
        # NOTE: ONLY CALLED BY ACTIONS

        if weapon_index is None:
            self._window_manager.error(
                    ['Trying to draw weapon with index <None>'])
            return

        weapon_indexes = self.get_current_weapon_indexes()
        if len(weapon_indexes) < Fighter.MAX_WEAPONS: # [], [x]
            self.details['weapon-index'].append(weapon_index)
        elif weapon_indexes[0] is None:     # [0, x]
            weapon_indexes[0] = weapon_index
        #else:
        #    error

    def draw_weapon_by_name(self,                # Public to support testing
                           name
                           ):
        # NOTE: ONLY USED FOR TESTING
        '''
        Draw weapon from sheath or holster.

        Just used in testing.

        Returns index, Weapon object
        '''
        index, item = self.equipment.get_item_by_name(name)
        if index is not None:
            self.details['weapon-index'].append(index)
        return index, ca_equipment.Weapon(item)

    def end_fight(self,
                  fight_handler   # FightHandler object (for do_action)
                  ):
        '''
        Perform the post-fight cleanup.  Remove all the timers, reload if the
        option is set.  Sheathe the weapon.

        Returns nothing.
        '''
        super(Fighter, self).end_fight(fight_handler)
        reload_after_fight = self._ruleset.get_option('reload-after-fight')
        if (reload_after_fight is not None and reload_after_fight and
                self.group == 'PCs'):
            # Reload EACH weapon the person has.
            before_weapon_indexes = copy.deepcopy(self.get_current_weapon_indexes())
            item_count = self.equipment.get_item_count()
            for item_index in range(item_count):
                # Look at the next item owned by the fighter
                weapon = self.equipment.get_item_by_index(item_index)
                if 'ranged weapon' not in weapon['type']:
                    continue

                # Dump whatever the person is carrying
                weapon_indexes = copy.deepcopy(self.get_current_weapon_indexes())
                for weapon_index in weapon_indexes:
                    self._ruleset.do_action(
                            self,
                            {'action-name': 'holster-weapon',
                             'weapon-index': weapon_index,
                             'notimer': True},
                            fight_handler,
                            logit=False)
                # Now, draw the next ranged weapon and reload it
                self._ruleset.do_action(self,
                                   {'action-name': 'draw-weapon',
                                    'weapon-index': item_index,
                                    'comment': 'Reloading after fight',
                                    'notimer': True,
                                    'quiet': True},
                                    fight_handler,
                                    logit=False)
                self._ruleset.do_action(self,
                                    {'action-name': 'reload',
                                     'comment': 'Reloading after fight',
                                     'all_items': True,
                                     'notimer': True,
                                     'quiet': True},
                                    fight_handler,
                                    logit=False)
            # Holster whatever the person is carrying and, then, re-draw
            # "current" weapon
            after_weapon_indexes = copy.deepcopy(self.get_current_weapon_indexes())
            for weapon_index in after_weapon_indexes:
                self._ruleset.do_action(
                        self,
                        {'action-name': 'holster-weapon',
                         'weapon-index': weapon_index,
                         'notimer': True},
                        fight_handler,
                        logit=False)
            for weapon_index in before_weapon_indexes:
                self._ruleset.do_action(self,
                                   {'action-name': 'draw-weapon',
                                    'weapon-index': weapon_index,
                                    'comment': 'Reloading after fight',
                                    'notimer': True,
                                    'quiet': True},
                                    fight_handler,
                                    logit=False)

    def get_current_armor_indexes(self):
        '''
        Gets the armor the Fighter is wearing.

        Returns a tuple:
            1) a dict (from the Game File)
            2) index of the armor
        '''
        if 'armor-index' not in self.details:
            return []
        return self.details['armor-index']

    def get_current_weapon_indexes(self):
        if 'weapon-index' not in self.details:
            return []
        return self.details['weapon-index']

    def get_current_weapons(self):
        weapon_indexes = self.get_current_weapon_indexes()
        weapon_list = []
        for weapon_index in weapon_indexes:
            if weapon_index is None:
                weapon = self._ruleset.get_unarmed_weapon()
                weapon_list.append(weapon)
            else:
                item = self.equipment.get_item_by_index(weapon_index)
                weapon = ca_equipment.Weapon(item)
                weapon_list.append(weapon)
        return weapon_list

    def get_items_from_indexes(self,
                               indexes  # list of indexes in self.details.stuff
                               ):
        '''
        Gets the items corresponding to indexes into the Fighter's stuff

        Returns a list of a dict (from the Game File)
        '''
        result = []
        for index in indexes:
            item = self.equipment.get_item_by_index(index)
            result.append(item)
        return result

    def get_preferred_item_indexes(self):
        '''
        Returns a list of indexes of preferred weapons and armor.
        '''
        result = []

        if len(self.details['preferred-armor-index']) > 0:
            result.extend(self.details['preferred-armor-index'])
        if len(self.details['preferred-weapon-index']) > 0:
            for item in self.details['preferred-weapon-index']:
                if item not in result:
                    result.append(item)

        return result

    def holster_weapon_by_index(self,
                                weapon_index  # Index of weapon in fighter's 'stuff'
                                       # list.
                                ):
        '''Holsters weapon.'''
        # NOTE: ONLY CALLED FROM AN ACTION

        # Make sure we have the weapon in question
        try:
            index = self.details['weapon-index'].index(weapon_index)
        except ValueError:
            item = self.equipment.get_item_by_index(weapon_index)
            self._window_manager.error(
                    ['Trying to holster non-drawn weapon: %s' % item['name']])
            return

        # Actually remove the weapon
        # NOTE: if you're removing the primary hand weapon, the off-hand weapon
        # is moved to the primary location.  This makes sense unless the
        # primary hand is injured.  This is a weird enough situation and hard
        # enough to handle that I'm not supporting it just now.  If I did, it
        # would look something like this:
        # if index == len(self.details['weapon-index']) - 1:
        #     self.details['weapon-index'].pop()
        # else:
        #     self.details['weapon-index'][index] = None

        self.details['weapon-index'].pop(index)

        # If there're no weapons left, add natural weapons (if applicable)
        if len(self.details['weapon-index']) == 0:
            for item_index, item in enumerate(self.details['stuff']):
                if 'natural-weapon' in item and item['natural-weapon']:
                    self.details['weapon-index'].append(item_index)

    #def print_me(self):
    #    print '-- Fighter (%s, %s) --' % (self.name, self.group)
    #    PP.pprint(self.details)

    def remove_equipment(self,
                         index_to_remove,   # <int> index into Equipment list
                         count=None,        # number to remove (None if 'ask')
                         container_stack=[]
                         ):
        '''
        Discards an item from the Fighter's equipment list.

        Returns: the discarded item
        '''
        item = self.equipment.get_item_by_index(index_to_remove,
                                                container_stack)
        if 'natural-weapon' in item and item['natural-weapon']:
            return None  # can't remove a natural weapon

        if 'natural-armor' in item and item['natural-armor']:
            return None  # can't remove a natural armor

        before_item_count = self.equipment.get_item_count(container_stack)
        count = self.ask_how_many(index_to_remove, count, container_stack)
        item = self.equipment.remove(index_to_remove, count, container_stack)
        after_item_count = self.equipment.get_item_count(container_stack)

        # Adjust indexes into the list if the list changed.

        if len(container_stack) == 0 and before_item_count != after_item_count:
            # Remove weapon from current weapon list
            for index_in_weapons, index_in_stuff in enumerate(
                    self.details['weapon-index']):
                if index_to_remove == index_in_stuff:
                    self.details['weapon-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.details['weapon-index'][index_in_weapons] -= 1

            # Remove weapon from preferred weapons list
            for index_in_weapons, index_in_stuff in enumerate(
                    self.details['preferred-weapon-index']):
                if index_to_remove == index_in_stuff:
                    self.details['preferred-weapon-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.details['preferred-weapon-index'][index_in_weapons] -= 1

            # Remove armor from current armor list
            for index_in_armor, index_in_stuff in enumerate(
                    self.details['armor-index']):
                if index_to_remove == index_in_stuff:
                    self.details['armor-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.details['armor-index'][index_in_armor] -= 1

            # Remove armor from preferred armor list
            for index_in_armor, index_in_stuff in enumerate(
                    self.details['preferred-armor-index']):
                if index_to_remove == index_in_stuff:
                    self.details['preferred-armor-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.details['preferred-armor-index'][index_in_armor] -= 1

        return item

    #
    # Notes related methods
    #

    def get_defenses_notes(self,
                           opponent  # Fighter object
                           ):
        '''
        Returns a tuple of strings describing:

        1) the current (based on weapons held, armor worn, etc) defensive
           capability of the Fighter, and
        2) the pieces that went into the above calculations
        '''
        defense_notes, defense_why = self._ruleset.get_fighter_defenses_notes(
                                                                self,
                                                                opponent)
        return defense_notes, defense_why

    def get_description_long(self,
                             output,  # recepticle for character detail.
                                      #  [[{'text','mode'},...],  # line 0
                                      #   [...],               ]  # line 1...
                             expand_containers   # Bool
                             ):
        '''
        Provides a text description of a Fighter including all of the
        attributes (current and permanent), equipment, etc.

        Returns: nothing.  The output is written to the |output| variable.
        '''
        self._ruleset.get_fighter_description_long(self,
                                                   output,
                                                   expand_containers)

    def get_description_medium(
            self,
            output,         # [[{'text':...,'mode':...}...
            fighter,        # Fighter object
            opponent,       # Fighter object
            is_attacker,    # True | False
            ):
        '''
        Returns a string that contains a short (but not the shortest)
        description of the state of the Fighter.
        '''
        self._ruleset.get_fighter_description_medium(output,
                                                     self,
                                                     opponent,
                                                     is_attacker)

    def get_description_short(self,
                              fight_handler  # FightHandler, ignored
                              ):
        '''
        Returns a string that contains the shortest description of the Fighter.
        '''
        fighter_string = self._ruleset.get_fighter_description_short(
                self, fight_handler)

        return fighter_string

    def get_notes(self):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.)
        '''
        notes = self._ruleset.get_fighter_notes(self)
        return notes

    def get_to_hit_damage_notes(self,
                                opponent  # Fighter object
                                ):
        '''
        Returns a list of strings describing the current (using the current
        weapon, in the current posture, etc.) fighting capability (to-hit and
        damage) of the fighter.
        '''
        notes = self._ruleset.get_fighter_to_hit_damage_notes(self, opponent)
        return notes

    #
    # Miscellaneous methods
    #

    def can_finish_turn(self,
                        fight_handler # FightHandler object
                        ):
        '''
        If a Fighter has done something this turn, we can move to the next
        Fighter.  Otherwise, the Fighter should do something before we go to
        the next Fighter.

        Returns: <bool> telling the caller whether this Fighter needs to do
        something before we move on.
        '''
        return self._ruleset.can_finish_turn(self, fight_handler)

    def end_turn(self,
                 fight_handler  # FightHandler object
                 ):
        '''
        Performs all of the stuff required for a Fighter to end his/her
        turn.

        Returns: nothing
        '''
        self._ruleset.end_turn(self, fight_handler)
        self.timers.remove_expired_kill_dying()

    def explain_numbers(self,
                        fight_handler  # FightHandler object
                        ):
        '''
        Explains how the stuff in the descriptions were calculated.

        Returns [[{'text':x, 'mode':x}, {...}], [], [], ...]
            where the outer array contains lines
            each line is an array that contains a line-segment
            each line segment has its own mode so, for example, only SOME of
               the line is shown in bold
        '''

        weapons = self.get_current_weapons()
        why_opponent = fight_handler.get_opponent_for(self)
        all_lines = []
        looking_for_weapon = True
        for weapon in weapons:
            if weapon is None:
                continue
            looking_for_weapon = False

            modes = weapon.get_attack_modes()
            for mode in modes:
                lines = self.__explain_one_weapon_numbers(weapon,
                                                          mode,
                                                          why_opponent)
                all_lines.extend(lines)

        #if looking_for_weapon:
        #    XXXX - do unarmed stuff

        ignore, defense_why = self.get_defenses_notes(why_opponent)
        if defense_why is not None:
            lines = [[{'text': x,
                       'mode': curses.A_NORMAL}] for x in defense_why]
            all_lines.extend(lines)

        return all_lines

    def get_best_skill_for_weapon(
            self,
            weapon,     # dict
            mode_name=None   # str: 'swung weapon' or ...; None for all modes
            ):
        # skills = [{'name': name, 'modifier': number}, ...]
        #if weapon['skill'] in self.details['skills']:
        #    best_skill = weapon['skill']
        #    best_value = self.details['skills'][best_skill]
        #else:
        #    return None

        '''
        Finds the best skill for this fighter and this weapon.

        Returns None if no skill matching the given weapon was found, else
            dict: {'name': best_skill, 'value': best_value}
        '''
        best_result = None
        if mode_name is None:
            weapon_obj = ca_equipment.Weapon(weapon)
            modes = weapon_obj.get_attack_modes()
            for mode in modes:
                result = self.__get_best_skill_for_weapon_one_modes(weapon,
                                                                    mode)
                if (best_result is None or
                        best_result['value'] < result['value']):
                    best_result = result
        else:
            best_result = self.__get_best_skill_for_weapon_one_modes(weapon,
                                                                     mode_name)

        return best_result

    def get_state(self):
        return Fighter.get_fighter_state(self.details)

    def is_absent(self):
        return True if self.details['state'] == 'Absent' else False

    def is_conscious(self):
        # NOTE: 'injured' is not stored in self.details['state']
        return True if self.details['state'] == 'alive' else False

    def is_dead(self):
        return True if self.details['state'] == 'dead' else False

    def set_consciousness(self,
                          conscious_number,  # <int> See Fighter.conscious_map
                          fight_handler
                          ):
        '''
        Sets the state (alive, unconscious, dead, absent, etc.) of the
        Fighter.

        Returns nothing.
        '''
        # NOTE: ONLY CALLED FROM ACTION OR TESTING

        for state_name, state_num in Fighter.conscious_map.iteritems():
            if state_num == conscious_number:
                self.details['state'] = state_name
                break

        if not self.is_conscious():
            self.details['opponent'] = None  # unconscious men fight nobody
            weapon_indexes = self.get_current_weapon_indexes()
            for index in weapon_indexes:
                # unconscious men don't hold stuff
                self._ruleset.do_action(
                        self,
                        {'action-name': 'holster-weapon',
                         'weapon-index': index,
                         'notimer': True},
                        fight_handler,
                        logit=False)

    def start_fight(self):
        '''
        Configures the Fighter to start a fight.

        Returns nothing.
        '''
        # NOTE: we're allowing health to still be messed-up, here
        # NOTE: person may go around wearing armor -- no need to reset
        self.details['opponent'] = None
        if self.group == 'PCs':
            if ('fight-notes' in self.details and
                    self.details['fight-notes'] is not None):
                self.details['fight-notes'] = []

            if ('label' in self.details and self.details['label'] is not None):
                self.details['label'] = None

        self._ruleset.start_fight(self)

    def start_turn(self,
                   fight_handler    # FightHandler object
                   ):
        '''
        Performs all of the stuff required for a Fighter to start his/her
        turn.  Handles timer stuff.

        Returns: nothing
        '''
        self._ruleset.start_turn(self, fight_handler)
        self.timers.decrement_all()
        self.timers.remove_expired_keep_dying()
        for timer in self.timers.get_all():
            if 'busy' in timer.details and timer.details['busy']:
                window_text = []
                lines = timer.get_description()
                for line in lines:
                    window_text.append([{'text': line,
                                         'mode': curses.A_NORMAL}])
                self._window_manager.display_window(
                                                ('%s is busy' % self.name),
                                                window_text)

                # Allow the fighter to continue without doing anything since
                # s/he's already busy
                self.details['actions_this_turn'].append('busy')
                fight_handler.add_to_history(
                        {'comment': '(%s) is busy this round' % self.name})

    def toggle_absent(self):
        '''
        Toggles the consciousness state between absent and alive.

        Returns nothing.
        '''

        if self.details['state'] == 'Absent':
            self.details['state'] = 'alive'
        else:
            self.details['state'] = 'Absent'

    #
    # Protected and Private Methods
    #

    def __explain_one_weapon_numbers(self,
                                     weapon,         # Weapon object
                                     mode,           # str: 'swung weapon', ...
                                     why_opponent    # Fighter object
                                     ):
        '''
        Explains how the stuff in the descriptions (for only one weapon) were
        calculated.

        Returns [[{'text':x, 'mode':x}, {...}], [], [], ...]
            where the outer array contains lines
            each line is an array that contains a line-segment
            each line segment has its own mode so, for example, only SOME of
               the line is shown in bold
        '''
        lines = []

        if self._ruleset.does_weapon_use_unarmed_skills(weapon):
            unarmed_info = self._ruleset.get_unarmed_info(self,
                                                          why_opponent,
                                                          weapon)
            lines = [[{'text': x,
                       'mode': curses.A_NORMAL}] for x in unarmed_info['why']]
        else:
            #lines.extend([[{'text': 'Weapon: "%s"' % weapon.name,
            #                'mode': curses.A_NORMAL}]])
            if self.get_best_skill_for_weapon(weapon.details,
                                              mode) is not None:
                # To-Hit
                skill, to_hit_why = self._ruleset.get_to_hit(self,
                                                              why_opponent,
                                                              weapon,
                                                              mode,
                                                              None)
                lines.extend([[{'text': x,
                                'mode': curses.A_NORMAL}] for x in to_hit_why])

                # Damage
                ignore, damage_why = self._ruleset.get_damage(self, weapon, mode)
                lines.extend([[{'text': x,
                                'mode': curses.A_NORMAL}] for x in damage_why])

            if weapon.notes() is not None:
                lines.extend([[{'text': '  %s' % weapon.notes(),
                               'mode': curses.A_NORMAL}]])

        return lines

    def __get_best_skill_for_weapon_one_modes(
            self,
            weapon,     # dict
            mode        # str: 'swung weapon' or ...; None for all modes
            ):
        # skills = [{'name': name, 'modifier': number}, ...]
        #if weapon['skill'] in self.details['skills']:
        #    best_skill = weapon['skill']
        #    best_value = self.details['skills'][best_skill]
        #else:
        #    return None

        '''
        Finds the best skill for this fighter and this weapon.

        Returns None if no skill matching the given weapon was found, else
            dict: {'name': best_skill, 'value': best_value}
        '''
        best_skill = None
        best_value = None
        for skill_camel, value in weapon['type'][mode]['skill'].iteritems():
            skill_lower = skill_camel.lower()
            found_skill = False
            if skill_camel in self.details['skills']:
                value += self.details['skills'][skill_camel]
                found_skill = True
            elif skill_lower in self.details['current']:
                value += self.details['current'][skill_lower]
                found_skill = True
            if found_skill and (best_value is None or value > best_value):
                best_value = value
                best_skill = skill_camel

        if best_skill is None or best_value is None:
            return None

        return {'name': best_skill, 'value': best_value}

