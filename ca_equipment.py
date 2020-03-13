#! /usr/bin/python

import copy
import curses

class Equipment(object):
    '''
    Object that manipulates a list of equipment.  The list is assumed to be
    from somewhere in the Game File data but that's not strictly a requirement.
    '''
    def __init__(self,
                 equipment, # self.details['stuff'], list of items
                ):
        self.__equipment = equipment


    def add(self,
            new_item,   # dict describing new equipment
            source=None # string describing where equipment came from
           ):
        '''
        Adds an item to the equipment list.  If a source if given, the source
        string is added to the item's list of owners.

        Returns the current index of the item in the equipment list.
        '''
        if source is not None and new_item['owners'] is not None:
            new_item['owners'].append(source)

        for item in self.__equipment:
            if item['name'] == new_item['name']:
                if self.__is_same_thing(item, new_item):
                    item['count'] += new_item['count']
                    return
                break

        self.__equipment.append(new_item)

        return len(self.__equipment) - 1 # current index of the added item


    def get_item_by_index(self,
                          index # integer index into the equipment list
                         ):
        '''
        Returns the dictionary data of the index-th item in the equipment
        list.  Returns None if the item is not found.
        '''
        return (None if index >= len(self.__equipment) else
                                                self.__equipment[index])


    def get_item_by_name(self,              # Public to facilitate testing
                         name   # string that matches the name of the thing
                        ):
        '''
        Returns a tuple that contains index, item (i.e., the dict describing
        the item) of the (first) item in the equipment list that has a name
        that matches the passed-in name.  Returns None, None if the item is
        not found.
        '''
        for index, item in enumerate(self.__equipment):
            if item['name'] == name:
                return index, item
        return None, None # didn't find one


    def remove(self,
               item_index   # integer index into the equipment list
              ):
        '''
        Removes an item (by index) from the list of equipment.

        Returns the removed item.
        '''
        # NOTE: This assumes that there won't be any placeholder items --
        # items with a count of 0 (or less).
        if item_index >= len(self.__equipment):
            return None

        if ('count' in self.__equipment[item_index] and
                                self.__equipment[item_index]['count'] > 1):
            item = copy.deepcopy(self.__equipment[item_index])
            item['count'] = 1
            self.__equipment[item_index]['count'] -= 1
        else:
            item = self.__equipment[item_index]
            self.__equipment.pop(item_index)

        return item

    #
    # Private methods
    #

    def __is_same_thing(self,
                        lhs,    # part of equipment dict (at level=0, is dict)
                        rhs,    # part of equipment dict (at level=0, is dict)
                        level=0 # how far deep in the recursive calls are we
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
            for key in rhs.iterkeys():
                if key not in rhs:
                    return False
            for key in lhs.iterkeys():
                if key not in rhs:
                    return False
                elif key == 'count' and level == 1:
                    return True # the count doesn't go into the match of item
                elif not self.__is_same_thing(lhs[key], rhs[key], level):
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
            return False if lhs != rhs else True


class EquipmentManager(object):
    def __init__(self,
                 world,         # World object
                 window_manager # GmWindowManager object for menus and errors
                ):
        '''
        Manages equipment lists.  Meant to be embedded in a Fighter or a Venue.
        '''
        self.__world = world
        self.__window_manager = window_manager

    @staticmethod
    def get_description(
                        item,           # Input: dict for a 'stuff' item from
                                        #   Game File
                        in_use_items,   # List of items that are in use.
                                        #   These should be references so that
                                        #   it will match identically to
                                        #   'item' if it is in use.
                        char_detail     # Output: recepticle for character
                                        # detail.
                                        # [[{'text','mode'},...],  # line 0
                                        #  [...],               ]  # line 1...
                       ):
        '''
        This is kind-of messed up.  Each type of equipment should have its own
        class that has its own 'get_description'.  In lieu of that, though,
        I'm going to centralize it.

        Puts data in |char_detail|.

        Returns nothing.
        '''

        mode = curses.A_NORMAL

        in_use_string = ' (in use)' if item in in_use_items else ''

        texts = ['  %s%s' % (item['name'], in_use_string)]
        if 'count' in item and item['count'] != 1:
            texts.append(' (%d)' % item['count'])

        if ('notes' in item and item['notes'] is not None and
                                                (len(item['notes']) > 0)):
            texts.append(': %s' % item['notes'])
        char_detail.append([{'text': ''.join(texts), 'mode': mode}])

        if item['type'] == 'ranged weapon':
            texts = []
            texts.append('acc: %d' % item['acc'])
            texts.append('dam(%s): %dd%+d' % (
                                          item['damage']['dice']['type'],
                                          item['damage']['dice']['num_dice'],
                                          item['damage']['dice']['plus']))
            texts.append('reload: %d' % item['reload'])
            char_detail.append([{'text': ('     ' + ', '.join(texts)),
                                 'mode': mode}])
        elif item['type'] == 'melee weapon':
            texts = []
            if 'dice' in item['damage']:
                texts.append('dam(%s): %dd%+d' % (
                                          item['damage']['dice']['type'],
                                          item['damage']['dice']['num_dice'],
                                          item['damage']['dice']['plus']))
            if 'sw' in item['damage']:
                texts.append('dam(sw): %s%+d' % (
                                          item['damage']['sw']['type'],
                                          item['damage']['sw']['plus']))
            if 'thr' in item['damage']:
                texts.append('dam(thr): %s%+d' % (
                                          item['damage']['thr']['type'],
                                          item['damage']['thr']['plus']))
            if 'parry' in item:
                texts.append('parry: %d' % item['parry'])

            char_detail.append([{'text': ('     ' + ', '.join(texts)),
                                 'mode': mode}])
        elif item['type'] == 'armor':
            texts = []
            texts.append('dr: %d' % item['dr'])
            char_detail.append([{'text': ('     ' + ', '.join(texts)),
                                 'mode': mode}])

        if ('owners' in item and item['owners'] is not None and
                                                    len(item['owners']) > 0):
            texts = ['     Owners: ']
            texts.append('%s' % '->'.join(item['owners']))
            char_detail.append([{'text': ''.join(texts),
                                 'mode': mode}])

    #
    # Public Methods
    #

    def add_equipment(self,
                      fighter       # Fighter object
                     ):
        '''
        Ask user which item to transfer from the store to a fighter and
        transfer it.

        Returns nothing.
        '''
        if fighter is None:
            return

        # Pick an item off the shelf

        # Rebuild this every time in case there are unique items in the
        # equipment list
        item_menu = [(item['name'], item)
                            for item in self.__world.details['stuff']]
        item_menu = sorted(item_menu, key=lambda x: x[0].upper())
        item = self.__window_manager.menu('Item to Add', item_menu)
        if item is not None:
            source = None
            if item['owners'] is not None and len(item['owners']) == 0:
                source = 'the store'

            fighter.add_equipment(copy.deepcopy(item), source)


    def remove_equipment(self,
                         fighter       # Fighter object
                        ):
        '''
        Ask the user which piece of equipment to discard and remove it.

        Returns the removed piece of equipment.
        '''
        if fighter is None:
            return

        item_menu = [(item['name'], index)
                    for index, item in enumerate(fighter.details['stuff'])]
        item_index = self.__window_manager.menu('Item to Remove', item_menu)
        if item_index is None:
            return None

        return fighter.remove_equipment(item_index)