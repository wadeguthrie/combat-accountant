#! /usr/bin/python

import copy
import curses
import pprint

import ca_debug

# The JSON source to objects in the 'stuff' array is expected to look like
# this:
#
# {
#      "name": "<name of the item>"
#      "count": <number of items>,
#      "notes": "<whatever>",
#      "owners": [ <list of strings> ],
#      "type": { <type> : <value> },
#      "mana": <int> # optional: for powerstones, current mana
#      "max mana": <int> # optional: for powerstones, maximum mana
# }
#
# <type> is one or more of:
#   o misc            - miscellaneous item, value is '1' (arbitrary)
#   o container       - container, value is '1' (arbitrary)
#                       dict contains "stuff": [array of items]
#   o ranged weapon   - see the ruleset file for details
#   o swung weapon    - see the ruleset file for details
#   o thrust weapon   - see the ruleset file for details
#   o natural weapon  - see the ruleset file for details
#   o armor           - see the ruleset file for details
#   o natural armor   - see the ruleset file for details

class Equipment(object):
    (RELOAD_NONE,   # for a thrown dagger or suriken
     RELOAD_ONE,    # for a shotgun or grenade launcher, loaded one at a time
     RELOAD_CLIP) = list(range(3))   # reload_type
    UNKNOWN_STRING = '** UNKNOWN **'
    '''
    Object that manipulates a list of equipment.  The list is assumed to be
    from somewhere in the Game File data but that's not strictly a requirement.
    '''
    def __init__(self,
                 owner_name,    # string, name of owner, for debugging
                 equipment      # self.details['stuff'], list of items
                 ):
        self.owner_name = owner_name
        self.__equipment = equipment

    @staticmethod
    def is_armor(item   # dict from JSON
            ):
        if 'armor' in item['type']:
            return True
        return False

    @staticmethod
    def is_natural_armor(item  # dict from JSON
                  ):
        if not Equipment.is_armor(item):
            return False

        if 'natural-armor' in item and item['natural-armor']:
            return True
        return False

    @staticmethod
    def is_natural_weapon(item  # dict from JSON
                  ):
        if not Weapon.is_weapon(item):
            return False

        if 'natural-weapon' in item and item['natural-weapon']:
            return True
        return False

    def add(self,
            new_item,       # dict describing new equipment
            source=None,    # string describing where equipment came from (None
                            #   for no change)
            container_stack = []
            ):
        '''
        Adds an item to the equipment list.  If a source if given, the source
        string is added to the item's list of owners.

        NOTE: only called from Fighter::add_equipment.

        Returns the current index of the item in the equipment list.
        '''
        container = self.get_container(container_stack)
        if container is None:
            return None # Error condition -- top-level should be []

        # if 'owners' doesn't exist or is None, then it's a mundane item and
        # is indistinguishable from any similar item -- you don't need to know
        # its provenance
        if (source is not None and 'owners' in new_item and
                new_item['owners'] is not None):
            new_item['owners'].append(source)

        for index, item in enumerate(container):
            if item['name'] == new_item['name']:
                if self.__is_same_thing(item, new_item):
                    count = 1 if 'count' not in new_item else new_item['count']
                    if 'count' in item:
                        item['count'] += count
                    else:
                        item['count'] = count
                    return index

        container.append(new_item)

        return len(self.__equipment) - 1  # current index of the added item

    def fix_ammo(self,
                 window_manager  # GmWindowManager object for menus and errors
                 ):
        '''
        Looks through the equipment list and, if there're items that need
        ammo, asks the user which item in the equipment list is the right kind
        of ammo.
        '''
        starting_ammo_index = 0
        ammo_menu = [(' %s' % Equipment.UNKNOWN_STRING,
                      Equipment.UNKNOWN_STRING)]
        for maybe_ammo in self.__equipment:
            if 'misc' in maybe_ammo['type']:
                ammo_menu.append((maybe_ammo['name'], maybe_ammo['name']))
        ammo_menu = sorted(ammo_menu, key=lambda x: x[0].upper())

        for item in self.__equipment:
            if (Weapon.uses_ammo_static(item) and
                    'ammo' in item and 'name' in item['ammo'] and
                    item['ammo']['name'] == Equipment.UNKNOWN_STRING):
                ammo, starting_ammo_index = window_manager.menu(
                        ('Select Ammo For %s' % item['name']),
                        ammo_menu, starting_ammo_index)
                if ammo is not None:
                    item['ammo']['name'] = ammo

    def get_container(self,
                      container_stack   # stack of indexes of containers
                                        #   that're open - None if top level
                      ):
        '''
        Returns the list for a container.  That's either the top-most equipment
        list or an item that can hold other items.  Uses |container_stack| to
        navigate to a specific container (e.g., a coin purse inside a wallet
        inside a purse).
        '''
        current_container = self.__equipment
        if container_stack is None:
            return current_container

        open_container_indexes = copy.deepcopy(container_stack)
        if len(open_container_indexes) > 0:
            # Doing the 1st one out-of-band because self.__equipment doesn't
            # have a 'stuff' member.  The rest of the containers will.
            container_index = open_container_indexes.pop(0)
            if container_index >= len(current_container):
                return None
            current_container = current_container[container_index]['stuff']
            for container_index in open_container_indexes:
                if container_index >= len(current_container):
                    return None
                current_container = current_container[container_index]['stuff']
        return current_container

    def get_container_list(self,
                           container   # list: contains items that may, in turn
                                       #    contain other items
                           ):
        '''
        Returns list of containers (index, name) in item described by
        container_stack.
        '''
        containers = []
        if container is None:
            return containers # Error condition -- top-level should be []

        for index, item in enumerate(container):
            if 'container' in item['type']:
                containers.append((index, item['name']))

        return containers

    def get_item_by_index(self,
                          index,  # integer index into the equipment list
                          container_stack=[]  # stack of indexes of
                                                #   containers that're open
                          ):
        '''
        Returns the dictionary data of the index-th item in the equipment
        list.  Returns None if the item is not found.
        '''

        if index is None:
            return None

        current_container = self.get_container(container_stack)

        return (None if current_container is None or
                index >= len(current_container) else
                current_container[index])

    def get_item_by_name(self,              # Public to facilitate testing
                         name,  # string that matches the name of the thing
                         starting_index=-1    # int
                         ):
        '''
        Returns a tuple that contains index, item (i.e., the dict describing
        the item) of the item (the first one after |starting_index|) in the
        equipment list that has a name that matches the passed-in name.
        Returns None, None if the item is not found.
        '''
        for index, item in enumerate(self.__equipment):
            if index <= starting_index:
                pass  # It's structured like this for debugging
            elif item['name'] == name:
                return index, item
        return None, None  # didn't find one

    def get_item_count(self,
                       container_stack=[]):
        container = self.get_container(container_stack)
        return None if container is None else len(container)

    def mother_up_item(self,
                       check_index  # integer index of item to be mothered-up
                       ):
        '''
        Checks to see if item is essentially the same as another item in the
        list.  If so, remove the passed-in item and up the count of the thing
        that's the same.
        '''
        check_item = self.__equipment[check_index]
        for index, item in enumerate(self.__equipment):
            if check_index == index:
                continue # This is the same exact item
            if item['name'] == check_item['name']:
                if self.__is_same_thing(item, check_item):
                    item['count'] += check_item['count']
                    self.remove(check_index, check_item['count'])
                    return

    def remove(self,
               item_index,      # integer index into the equipment list
               item_count=1,    # number to remove (None if 'ask')
               container_stack=[]
               ):
        '''
        Removes an item (by index) from the list of equipment.

        NOTE: only called from Fighter::remove_equipment (and its parents)

        Returns the removed item.
        '''
        container = self.get_container(container_stack)
        if container is None:
            return None # Error condition -- top-level should be []

        if item_index >= len(container):
            return None

        if item_count <= 0:
            return None

        if Equipment.is_natural_weapon(container[item_index]):
            return None     # Can't remove a natural weapon

        if Equipment.is_natural_armor(container[item_index]):
            return None     # Can't remove a natural armor

        remove_all = False
        if ('count' in container[item_index] and
                container[item_index]['count'] > 1):

            if item_count >= container[item_index]['count']:
                item_count = container[item_index]['count']
                remove_all = True

            # Remove the item(s)

            item = copy.deepcopy(container[item_index])
            item['count'] = item_count
            container[item_index]['count'] -= item_count
        else:
            item = container[item_index]
            remove_all = True

        if remove_all:
            if 'discard-when-empty' in item and not item['discard-when-empty']:
                container[item_index]['count'] = 0
            else:
                container.pop(item_index)

        return item

    def show_equipment(self):
        ''' For debugging purposes. '''
        PP = pprint.PrettyPrinter(indent=3, width=150)
        for index, item in enumerate(self.__equipment):
            print('>>> INDEX %d:' % index)
            PP.pprint(item)

    #
    # Private methods
    #

    def __is_same_thing(self,
                        lhs,     # part of equipment dict (at level=0, is dict)
                        rhs,     # part of equipment dict (at level=0, is dict)
                        level=0  # how far deep in the recursive calls are we
                        ):
        '''
        Checks that two objects contain the same data.  That is harder than it
        seems since dictionaries have non-constant order.  This does look
        recursively down lists, dictionaries, and scalars.

        Returns True if the left-hand-side thing contains the exact same data
        as the right-hand-side thing.  Returns False otherwise.
        '''
        level += 1

        if isinstance(lhs, dict):
            if not isinstance(rhs, dict):
                return False
            for key in rhs.keys():
                if key not in lhs:
                    return False
            for key in lhs.keys():
                if key not in rhs:
                    return False
                elif not self.__is_same_thing(lhs[key], rhs[key], level):
                    # the count doesn't go into the match of item
                    if key != 'count' or level != 1:
                        return False
            return True

        elif isinstance(lhs, list):
            if not isinstance(rhs, list):
                return False
            if len(lhs) != len(rhs):
                return False
            for i in range(len(lhs)):
                if not self.__is_same_thing(lhs[i], rhs[i], level):
                    return False
            return True

        else:
            return True if lhs == rhs else False


class EquipmentManager(object):
    def __init__(self,
                 world,          # World object
                 window_manager  # GmWindowManager object for menus and errors
                 ):
        '''
        Manages equipment lists.  Meant to be embedded in a Fighter or a Venue.
        '''
        self.__world = world
        self.__window_manager = window_manager

    @staticmethod
    def get_description(
            item,                   # Input: dict for a 'stuff' item from
                                    #   Game File
            qualifiers,             # String describing item
            open_sub_containers,    # list of indexes of open sub-items
                                    #   (recursive) if this is a container.
                                    #   NOTE: CAN destroy this list
            expand_containers,      # Bool
            char_detail,            # Output: recepticle for character
                                    # detail.
                                    # [[{'text','mode'},...],  # line 0
                                    #  [...],               ]  # line 1...
            indent=''               # String pre-pended to all the desctiptions
                                    #   (for containers)
            ):
        '''
        This is kind-of messed up.  Each type of equipment should have its own
        class that has its own 'get_description'.  In lieu of that, though,
        I'm going to centralize it.

        Puts data in |char_detail|.

        Returns nothing.
        '''

        mode = curses.A_NORMAL

        name = (('[ %s ]' % item['name']) if 'container' in item['type']
                else item['name'])

        texts = ['  %s%s%s' % (indent, name, qualifiers)]

        if 'shots' in item and 'shots_left' in item:
            texts.append(' (%d/%d shots left)' % (item['shots_left'],
                                                  item['shots']))

        if 'count' in item and item['count'] != 1:
            texts.append(' (%d)' % item['count'])

        if 'parry' in item:
            texts.append(' parry: %d' % item['parry'])

        if ('notes' in item and item['notes'] is not None and
                (len(item['notes']) > 0)):
            texts.append(': %s' % item['notes'])

        if 'identified' in item and not item['identified']:
            texts.append(' [UNIDENTIFIED]')

        char_detail.append([{'text': ''.join(texts), 'mode': mode}])

        for type_name, item_type in item['type'].items():
            if not isinstance(item_type, dict):
                continue

            if 'damage' in item_type:
                damage = item_type['damage']
                texts = []
                if 'dice' in damage:
                    texts.append('dam(%s): %dd%+d' % (
                                                  damage['dice']['type'],
                                                  damage['dice']['num_dice'],
                                                  damage['dice']['plus']))
                elif 'st' in damage:
                    texts.append('dam(%s): %s%+d' % (damage['st'],
                                                     damage['type'],
                                                     damage['plus']))

                if 'reload' in item:
                    if item['reload_type'] == Equipment.RELOAD_ONE:
                        texts.append('reload: %d(i)' % item['reload'])
                    else:
                        texts.append('reload: %d' % item['reload'])
                if 'acc' in item:
                    texts.append('acc: %d' % item['acc'])
                if 'bulk' in item:
                    texts.append('bulk: %d' % item['bulk'])

                if len(texts) > 0:
                    leader = '     %s' % indent
                    char_detail.append([{'text': (leader + ', '.join(texts)),
                                         'mode': mode}])

            elif 'armor' in type_name:
                texts = []
                # TODO (eventually): ruleset-specific
                texts.append('dr: %d' % item_type['dr'])
                leader = '     %s' % indent
                char_detail.append([{'text': (leader + ', '.join(texts)),
                                     'mode': mode}])

        if ('owners' in item and item['owners'] is not None and
                len(item['owners']) > 0):
            texts = ['     %sOwners: ' % indent]
            texts.append('%s' % '->'.join(item['owners']))
            char_detail.append([{'text': ''.join(texts),
                                 'mode': mode}])

        # Only show contents of open container
        if 'container' in item['type'] and (
                expand_containers or qualifiers.find('(OPEN)') >= 0):
            open_index = (None if len(open_sub_containers) == 0 else
                open_sub_containers.pop(0))
            indent += '   '
            for index, sub_item in enumerate(item['stuff']):
                qualifiers = ' (OPEN)' if open_index == index else ''
                EquipmentManager.get_description(
                        sub_item, qualifiers, open_sub_containers,
                        expand_containers, char_detail, indent)

    #
    # Public Methods
    #

    def add_equipment_from_store(
            self,
            ruleset,              # Ruleset object
            fighter,              # Fighter object
            starting_index = 0    # index into the store's list of equipment.
                                  #     Multiple calls can go to the same spot
                                  #     in that list as the last call.
            ):
        '''
        Ask user which item to transfer from the store to a fighter and
        transfer it.

        Returns nothing.
        '''
        if fighter is None:
            return None

        # Pick an item off the shelf

        # Rebuild this every time in case there are unique items in the
        # equipment list
        item_menu = [(item['name'], item)
                     for item in self.__world.details['stuff']]
        item_menu = sorted(item_menu, key=lambda x: x[0].upper())
        item, starting_index = self.__window_manager.menu(
                'Item to Add', item_menu, starting_index)
        if item is not None:
            source = None
            if item['owners'] is not None and len(item['owners']) == 0:
                source = 'the store'

            ignore = fighter.add_equipment(copy.deepcopy(item), source)
            ruleset.offer_to_add_dependencies(self.__world, fighter, item)

        return starting_index

    def remove_equipment(self,
                         fighter,               # Fighter object
                         count=None,            # int
                         container_stack = []   # [index, index, ...]
                         ):
        '''
        Ask the user which piece of equipment to discard and remove it.

        Returns the removed piece of equipment.
        '''
        item_index = self.select_item_index(fighter)
        return self.remove_equipment_by_index(fighter,
                                              item_index,
                                              count)

    def remove_equipment_by_index(self,
                                  fighter,      # Fighter object
                                  item_index,   # int index to be removed
                                  count=None    # int
                                  ):
        '''
        Ask the user which piece of equipment to discard and remove it.

        Returns the removed piece of equipment.
        '''
        if item_index is None:
            return None

        return fighter.remove_equipment(item_index, count)

    def select_item_index(self,
                          fighter,                  # Fighter object
                          limit_to_removable=True   # bool
                          ):
        '''
        Ask the user to select an item possessed by the fighter.

        If 'limit_to_removable' is True, only present items that the fighter
        can separate from his/her body (i.e., not natural weapons or armor).

        Returns index of the selected item.
        '''
        if fighter is None:
            return None

        item_menu = []
        for index, item in enumerate(fighter.details['stuff']):
            if limit_to_removable:
                if Equipment.is_natural_weapon(item):
                    continue  # Can't remove natural weapons
                if Equipment.is_natural_armor(item):
                    continue  # Can't remove natural armor
            output = []
            EquipmentManager.get_description(item, '', [], False, output)
            # output looks like:
            # [[{'text','mode'},...],  # line 0
            #  [...],               ]  # line 1...
            pieces = []
            for piece in output[0]: # the first line of the output
                pieces.append(piece['text'])
            description = ''.join(pieces)

            item_menu.append((description, index))

        item_menu = sorted(item_menu, key=lambda x: x[0].upper())
        item_index, ignore = self.__window_manager.menu('Item to Remove',
                                                        item_menu)

        return item_index # This may be 'None'


class Weapon(object):
    @staticmethod
    def is_item_melee_weapon(item  # dict from JSON
                             ):
        if 'melee weapon' in item['type']:
            return True
        if 'swung weapon' in item['type']:
            return True
        if 'thrust weapon' in item['type']:
            return True
        return False

    @staticmethod
    def is_item_ranged_weapon(item  # dict from JSON
                              ):
        if 'ranged weapon' in item['type']:
            return True
        return False

    @staticmethod
    def is_item_natural_weapon(item  # dict from JSON
                              ):
        if 'natural weapon' in item['type']:
            return True
        return False

    @staticmethod
    def is_weapon(item  # dict from JSON
                  ):
        if Weapon.is_item_melee_weapon(item):
            return True
        if Weapon.is_item_ranged_weapon(item):
            return True
        if Weapon.is_item_natural_weapon(item):
            return True
        return False

    @staticmethod
    def uses_ammo_static(item  # dict
                         ):
        return (True if 'reload_type' in item and
                item['reload_type'] != Equipment.RELOAD_NONE
                else False)

    def __init__(self,
                 weapon_details    # dict from world file
                 ):
        self.details = weapon_details
        self.name = self.details['name']

    def get_attack_modes(self):
        modes = [mode for mode in self.details['type'].keys()
                 if mode != 'container']
        return modes

    def get_clip(self):
        clip = None if 'clip' not in self.details else self.details['clip']
        return clip

    def get_damage_next_shot(self,
                             mode   # string: how is the weapon used?
                             ):
        # weapon[type][mode]: swung weapon, thrust weapon, thrown weapon,
        #                      missile weapon
        #
        # returns (damage dict, notes (scalar string) for this shot)

        debug = ca_debug.Debug()
        debug.header2('get_damage_next_shot')
        damage = self.get_param('damage', mode)
        notes = self.get_param('notes', mode)
        return damage, notes

    def get_param(self,
                  param, # string: parameter being retrieved
                  mode   # string: how is the weapon used?
                  ):
        '''
        Gets a named parameter from the weapon.  It tries to get the parameter
        from the next bullet (if the weapon has bullets).  If not, it tries to
        get the parameter from the weapon's clip (if the weapon takes clips).
        If not, it tries to get the parameter from the weapon.  If not, it
        returns None.
        '''
        # weapon[type][mode]: swung weapon, thrust weapon, thrown weapon,
        #                      missile weapon
        #debug = ca_debug.Debug()
        #debug.header2('get_param: %s, %s' % (param, mode))

        # start with the weapon's inherent value
        #debug.print('details:')
        #debug.pprint(self.details)
        result = None
        if param in self.details:
            result = self.details[param]

        # check mode-specific information
        if mode in self.details['type'] and param in self.details['type'][mode]:
            result = self.details['type'][mode][param]

        #debug.print('type[%r] = "%r"' % (mode, self.details['type'][mode]))

        # check the clip (and bullets therein)
        if mode == 'ranged weapon':
            clip = self.get_clip()
            #debug.print('  it is a ranged weapon, clip:')
            #debug.pprint(clip)
            if clip is None:
                return result

            if param in clip:
                result = clip[param]

            if 'stuff' in clip: # bullets contained in clip
                #debug.print('stuff is in clip')
                bullet = clip['stuff'][0] # next bullet to be fired
                if param in bullet:
                    result = bullet[param]

        return result

    def is_melee_weapon(self):
        return Weapon.is_item_melee_weapon(self.details)

    def is_melee_strength_based_weapon(self):
        if not self.is_melee_weapon():
            return False
        for mode in self.details['type']:
            full_mode = self.details['type'][mode]
            if ('damage' in full_mode and 'st' in full_mode['damage'] and
                    (full_mode['damage']['st'] == 'sw' or
                     full_mode['damage']['st'] == 'thr')):
                return True
        return False

    def is_natural_weapon(self):
        return Weapon.is_item_natural_weapon(self.details)

    def is_ranged_weapon(self):
        return Weapon.is_item_ranged_weapon(self.details)

    def is_shield(self):
        # NOTE: cloaks also have this 'type'
        return True if 'shield' in self.details['type'] else False

    def load(self,
             clip,      # dict: from character file
             load_type  # int: RELOAD_NONE, RELOAD_ONE, or RELOAD_CLIP
             ):

        if clip is None:
            return

        if load_type == Equipment.RELOAD_NONE:
            return

        elif load_type == Equipment.RELOAD_ONE:
            if self.details['clip'] is None:
                self.details['clip'] = clip
                # storing the total number of shots in clip as a convenience
                self.details['clip']['shots'] = self.details['ammo']['shots']
                self.details['clip']['shots_left'] = 1
            elif (self.details['clip']['shots_left'] <
                    self.details['clip']['shots']):
                self.details['clip']['shots_left'] += 1
        else: # load_type == Equipment.or RELOAD_CLIP
            self.details['clip'] = clip

            if 'ammo' not in self.details:
                return

        # Shotgun or battery needs this stored in ammo:
        if 'shots' in self.details['ammo']:
            clip['shots'] = self.details['ammo']['shots']

        if 'shots_left' not in clip:
            clip['shots_left'] = clip['shots']

    def notes(self):
        weapon_notes = (None if 'notes' not in self.details
                        or len(self.details) == 0 else self.details['notes'])

        clip = self.get_clip()

        ammo_notes = (None if clip is None
                      or 'notes' not in clip
                      or len(clip) == 0 else clip['notes'])

        if weapon_notes is None:
            if ammo_notes is None:
                notes = ''
            else:
                notes = ammo_notes
        else:
            if ammo_notes is None:
                notes = weapon_notes
            else:
                notes = '%s - %s' % (weapon_notes, ammo_notes)

        return notes

    def remove_old_clip(self):
        if not self.uses_ammo():
            return None

        old_clip = None
        if 'clip' in self.details:
            old_clip = self.details['clip']
        self.details['clip'] = None
        self.shots_left(0)
        return old_clip

    def shots(self):
        clip = self.get_clip()
        if clip is None or 'shots' not in clip:
            return 0
        return clip['shots']

    def shots_left(self,
                   new_value=None):
        clip = self.get_clip()
        if clip is None or 'shots_left' not in clip:
            return 0

        if new_value is not None:
            clip['shots_left'] = new_value

        return clip['shots_left']

    def use_one_ammo(self,
                     rounds=1   # Number of rounds to take
                     ):
        '''
        Returns True if successful, False otherwise
        '''
        debug = ca_debug.Debug(quiet=True)
        debug.print('use_one_ammo')
        if not self.uses_ammo():
            debug.print('  DOES NOT USE AMMO')
            return True
        clip = self.get_clip()
        if clip is None:
            return False

        if self.shots_left() < rounds:
            return False
        debug.print('  clip is not none')
        for round in range(rounds):
            clip['shots_left'] -= 1
            debug.pprint(clip)
            if 'stuff' in clip:
                if len(clip['stuff']) <= 0:
                    debug.print('  LEN(STUFF) <= 0')
                    return False
                debug.print('  ** POPPED **')
                clip['stuff'].pop(0)
        return True

    def uses_ammo(self):
        return Weapon.uses_ammo_static(self.details)
