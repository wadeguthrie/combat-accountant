#! /usr/bin/python

import copy
import curses
import pprint

import ca_debug
import ca_equipment
import ca_timers

# The section in the JSON file describing 'fights' should look like this:
#
# 'fights': {
#   <fight name>: { 'monsters': { <monster name>: { <creature-description> },
#                                 ... }},
#   ... }
#
# where:
#   <fight name> is a unique string describing the fight
#   <monster name> is a string that is unique under the 'fight name'.  One
#       name every fight has is '<< ROOM >>'.  This allows the room to contain
#       objects that can be transferred to the PCs, notes that can be read to
#       the PCs, and timers that aren't specific to any creature.
#   <creature-description> is a structure that is the same as the top-level
#       JSON section 'PCs' in ca.py

class ThingsInFight(object):
    '''
    Base class to manage timers, equipment, and notes for Fighters and Venues.
    '''
    def __init__(self,
                 name,           # string, name of the thing
                 group,          # string to index into world['fights']
                 rawdata,        # world.rawdata['fights'][name] (world is
                                 #   a World object)
                 ruleset,        # Ruleset object
                 window_manager  # GmWindowManager object for reporting errors
                 ):
        self.name = name
        self.detailed_name = self.name
        self.group = group
        self.rawdata = rawdata
        self._ruleset = ruleset
        self._window_manager = window_manager

        # Equipment

        if 'stuff' not in self.rawdata:     # Public to facilitate testing
            self.rawdata['stuff'] = []

        self.equipment = ca_equipment.Equipment(self.name,
                                                self.rawdata['stuff'])

        # Timers

        if 'timers' not in rawdata:
            rawdata['timers'] = []
        self.timers = ca_timers.Timers(self.rawdata['timers'],
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
            fight_handler   # FightHandler object
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
                 rawdata,        # world.rawdata['fights'][name] (world is
                                 #   a World object)
                 ruleset,        # Ruleset object
                 window_manager  # GmWindowManager object for error reporting
                 ):
        super(Venue, self).__init__(Venue.name,
                                    group,
                                    rawdata,
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
        if 'stuff' in self.rawdata:
            for item in sorted(self.rawdata['stuff'], key=lambda x: x['name']):
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
        if 'notes' in self.rawdata:
            for note in self.rawdata['notes']:
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

        if 'stuff' in self.rawdata and len(self.rawdata['stuff']) > 0:
            fighter_string += ' - EQUIP'

        if 'timers' in self.rawdata and len(self.rawdata['timers']) > 0:
            fighter_string += ' - TIMERS'

        if 'notes' in self.rawdata and len(self.rawdata['notes']) > 0:
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
     FIGHT) = list(range(6))

    MAX_WEAPONS = 2 # because we only have 2 arms

    # When adding a new weapon, make it preferred?
    NOT_PREFERRED, ADD_PREFERRED, REPLACE_PREFERRED = list(range(3))

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
    def get_fighter_state(rawdata):
        '''
        Returns the fighter state number.  Note that Fighter.INJURED needs to
        be calculated -- we don't store that in the Fighter as a separate
        state.
        '''
        conscious_number = Fighter.conscious_map[rawdata['state']]
        if (conscious_number == Fighter.ALIVE and
                rawdata['current']['hp'] < rawdata['permanent']['hp']):
            return Fighter.INJURED
        return conscious_number

    @staticmethod
    def get_name_from_state_number(number):
        for name, value in Fighter.conscious_map.items():
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
                if len(self.rawdata['preferred-weapon-index']) > 0:
                    if before_item_count != after_item_count:
                        # Only ask if we've added a new weapon and not just
                        # bumped-up the count on a previous weapon
                        replace_preferred_menu = [
                                ('no', Fighter.NOT_PREFERRED),
                                ('replace existing',
                                    Fighter.REPLACE_PREFERRED)]
                        if (len(self.rawdata['preferred-weapon-index']) <
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
                            for index in self.rawdata['preferred-weapon-index']:
                                weapon = self.equipment.get_item_by_index(index)
                                remove_which_menu.append((weapon['name'], index))

                            remove_index, ignore = self._window_manager.menu(
                                    'Replace which weapon?',
                                    remove_which_menu)
                            if remove_index is None:
                                # I guess we're not replacing anything
                                replace_preferred = Fighter.NOT_PREFERRED
                            else:
                                self.rawdata['preferred-weapon-index'].remove(
                                    remove_index)

                        if replace_preferred != Fighter.NOT_PREFERRED:
                            self.rawdata['preferred-weapon-index'].append(
                                    new_item_index)
                else:
                    self.rawdata['preferred-weapon-index'].append(new_item_index)
            if is_armor:
                if len(self.rawdata['preferred-armor-index']) > 0:
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
                            for index in self.rawdata['preferred-armor-index']:
                                item = self.equipment.get_item_by_index(index)
                                remove_which_menu.append((item['name'], index))

                            remove_index, ignore = self._window_manager.menu(
                                    'Replace which piece of armor?',
                                    remove_which_menu)
                            if remove_index is None:
                                # I guess we're not replacing anything
                                replace_preferred = Fighter.NOT_PREFERRED
                            else:
                                self.rawdata['preferred-armor-index'].remove(
                                    remove_index)

                        if replace_preferred != Fighter.NOT_PREFERRED:
                            self.rawdata['preferred-armor-index'].append(
                                    new_item_index)
                else:
                    self.rawdata['preferred-armor-index'].append(new_item_index)
        return new_item_index

    def add_one_ability(
            self,
            param,          # string: Ruleset-defined ability
                            #   category name (like 'skills' or
                            #   'advantages')
            ability_name    # string: name of skill or advantage
            ):

        # The predicate is the body of the skill (or whatever) in the GURPS
        # info ile  It'll take one of several forms...
        # 'name': {'ask': 'number' | 'string' }
        #         {'value': value}
        abilities = self._ruleset.get_creature_abilities()
        if param not in abilities:
            return None
        if ability_name not in abilities[param]:
            return None
        predicate = abilities[param][ability_name]

        result = None
        if 'ask' in predicate:
            if predicate['ask'] == 'number':
                title = 'Value for %s' % ability_name
                width = len(title) + 2  # Margin to make it prettier
            else:
                title = 'String for %s' % ability_name
                lines, cols = self._window_manager.getmaxyx()
                width = int(cols/2)
            height = 1
            adj_string = self._window_manager.input_box(height, width, title)
            if adj_string is None or len(adj_string) <= 0:
                return None

            if predicate['ask'] == 'number':
                result = int(adj_string)
            else:
                result = adj_string

        elif 'value' in predicate:
            result = predicate['value']
        else:
            result = None
            self._window_manager.error(
                    ['unknown predicate "%r" for "%s"' %
                     (predicate, ability_name)])

        if result is not None:
            self.rawdata[param][ability_name] = result

        return result

    def doff_armor_by_index(self,
                            index  # Index of armor in fighter's 'stuff'
                                   # list.  'None' removes current armor.
                           ):
        '''Removes armor.'''

        if index not in self.rawdata['armor-index']:
            return  # Not wearing the armor we want to taking off

        self.rawdata['armor-index'].remove(index)

        # if we're doffing armor and there's natural armor, pick that
        # one up.
        for item_index, item in enumerate(self.rawdata['stuff']):
            if (item_index not in self.rawdata['armor-index'] and
                    'natural-armor' in item and item['natural-armor']):
                self.rawdata['armor-index'].append(item_index)


    def don_armor_by_index(self,
                           index  # Index of armor in fighter's 'stuff'
                                  # list.  'None' removes current armor.
                           ):
        '''Puts on armor.'''

        if index not in self.rawdata['armor-index']:
            self.rawdata['armor-index'].append(index)

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
            self.rawdata['weapon-index'].append(weapon_index)
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
            self.rawdata['weapon-index'].append(index)
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
        Returns: list of indexes
        '''
        if 'armor-index' not in self.rawdata:
            return []
        return self.rawdata['armor-index']

    def get_current_weapon_indexes(self):
        '''
        Gets the weapons the Fighter is wielding.
        Returns: list of indexes
        '''
        if 'weapon-index' not in self.rawdata:
            return []
        return self.rawdata['weapon-index']

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
                               indexes  # list of indexes in self.rawdata.stuff
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

        if len(self.rawdata['preferred-armor-index']) > 0:
            result.extend(self.rawdata['preferred-armor-index'])
        if len(self.rawdata['preferred-weapon-index']) > 0:
            for item in self.rawdata['preferred-weapon-index']:
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
            index = self.rawdata['weapon-index'].index(weapon_index)
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
        # if index == len(self.rawdata['weapon-index']) - 1:
        #     self.rawdata['weapon-index'].pop()
        # else:
        #     self.rawdata['weapon-index'][index] = None

        self.rawdata['weapon-index'].pop(index)

        # If there're no weapons left, add natural weapons (if applicable)
        if len(self.rawdata['weapon-index']) == 0:
            for item_index, item in enumerate(self.rawdata['stuff']):
                if 'natural-weapon' in item and item['natural-weapon']:
                    self.rawdata['weapon-index'].append(item_index)

    #def print_me(self):
    #    print '-- Fighter (%s, %s) --' % (self.name, self.group)
    #    PP.pprint(self.rawdata)

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
                    self.rawdata['weapon-index']):
                if index_to_remove == index_in_stuff:
                    self.rawdata['weapon-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.rawdata['weapon-index'][index_in_weapons] -= 1

            # Remove weapon from preferred weapons list
            for index_in_weapons, index_in_stuff in enumerate(
                    self.rawdata['preferred-weapon-index']):
                if index_to_remove == index_in_stuff:
                    self.rawdata['preferred-weapon-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.rawdata['preferred-weapon-index'][index_in_weapons] -= 1

            # Remove armor from current armor list
            for index_in_armor, index_in_stuff in enumerate(
                    self.rawdata['armor-index']):
                if index_to_remove == index_in_stuff:
                    self.rawdata['armor-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.rawdata['armor-index'][index_in_armor] -= 1

            # Remove armor from preferred armor list
            for index_in_armor, index_in_stuff in enumerate(
                    self.rawdata['preferred-armor-index']):
                if index_to_remove == index_in_stuff:
                    self.rawdata['preferred-armor-index'].remove(index_in_stuff)
                elif index_to_remove < index_in_stuff:
                    self.rawdata['preferred-armor-index'][index_in_armor] -= 1

        return item

    def what_are_we_holding(self):
        weapons = self.get_current_weapons()
        holding = {'ranged': 0,
                   'loaded_ranged': 0,
                   'melee': 0,
                   'natural_weapon': 0,
                   'non_natural_weapon': 0}

        for weapon in weapons:
            if weapon is None:
                continue
            if weapon.is_ranged_weapon():
                holding['ranged'] += 1
                # TODO (now): not?
                if not weapon.uses_ammo() or weapon.shots_left() > 0:
                    holding['loaded_ranged'] += 1
            else:
                holding['melee'] += 1
            if ca_equipment.Equipment.is_natural_weapon(weapon.rawdata):
                holding['natural_weapon'] += 1
            else:
                holding['non_natural_weapon'] += 1

        # If you're not holding anything, you've at least got your fists
        if (not holding['ranged'] and not holding['melee'] and
                not holding['natural_weapon'] and not holding['non_natural_weapon']):
            holding['natural_weapon'] += 1

        return holding

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
            fight_handler   # FightHandler object
            ):
        '''
        Returns a string that contains a short (but not the shortest)
        description of the state of the Fighter.
        '''
        self._ruleset.get_fighter_description_medium(output,
                                                     self,
                                                     opponent,
                                                     is_attacker,
                                                     fight_handler)

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
        self.timers.fire_expired_timers(ca_timers.Timer.FIRE_ROUND_END)

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
        disallowed_modes = self._ruleset.get_disallowed_modes(self)
        for weapon in weapons:
            if weapon is None:
                continue
            looking_for_weapon = False

            modes = weapon.get_attack_modes()
            for mode in modes:
                if mode not in disallowed_modes:
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
        #if weapon['skill'] in self.rawdata['skills']:
        #    best_skill = weapon['skill']
        #    best_value = self.rawdata['skills'][best_skill]
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
        return Fighter.get_fighter_state(self.rawdata)

    def is_absent(self):
        return True if self.rawdata['state'] == 'Absent' else False

    def is_conscious(self):
        # NOTE: 'injured' is not stored in self.rawdata['state']
        return True if self.rawdata['state'] == 'alive' else False

    def is_dead(self):
        return True if self.rawdata['state'] == 'dead' else False

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

        for state_name, state_num in Fighter.conscious_map.items():
            if state_num == conscious_number:
                self.rawdata['state'] = state_name
                break

        if not self.is_conscious():
            self.rawdata['opponent'] = None  # unconscious men fight nobody
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
        self.rawdata['opponent'] = None
        if self.group == 'PCs':
            if ('fight-notes' in self.rawdata and
                    self.rawdata['fight-notes'] is not None):
                self.rawdata['fight-notes'] = []

            if ('label' in self.rawdata and self.rawdata['label'] is not None):
                self.rawdata['label'] = None

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
        self.timers.fire_expired_timers(ca_timers.Timer.FIRE_ROUND_START)
        for timer in self.timers.get_all():
            if 'busy' in timer.rawdata and timer.rawdata['busy']:
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
                self.rawdata['actions_this_turn'].append('busy')
                fight_handler.add_to_history(
                        {'comment': '(%s) is busy this round' % self.name})

    def toggle_absent(self):
        '''
        Toggles the consciousness state between absent and alive.

        Returns nothing.
        '''

        if self.rawdata['state'] == 'Absent':
            self.rawdata['state'] = 'alive'
        else:
            self.rawdata['state'] = 'Absent'

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
        debug = ca_debug.Debug()
        debug.header2('__explain_one_weapon_numbers')

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
            if self.get_best_skill_for_weapon(weapon.rawdata,
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
        #if weapon['skill'] in self.rawdata['skills']:
        #    best_skill = weapon['skill']
        #    best_value = self.rawdata['skills'][best_skill]
        #else:
        #    return None

        '''
        Finds the best skill for this fighter and this weapon.

        Returns None if no skill matching the given weapon was found, else
            dict: {'name': best_skill, 'value': best_value}
        '''
        best_skill = None
        best_value = None
        for skill_camel, value in weapon['type'][mode]['skill'].items():
            skill_lower = skill_camel.lower()
            found_skill = False
            if skill_camel in self.rawdata['skills']:
                value += self.rawdata['skills'][skill_camel]
                found_skill = True
            elif skill_lower in self.rawdata['current']:
                value += self.rawdata['current'][skill_lower]
                found_skill = True
            if found_skill and (best_value is None or value > best_value):
                best_value = value
                best_skill = skill_camel

        if best_skill is None or best_value is None:
            return None

        return {'name': best_skill, 'value': best_value}

