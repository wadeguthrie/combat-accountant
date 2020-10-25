#! /usr/bin/python

import curses

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
                      new_item,    # dict describing new equipment
                      source=None  # string: from where did equipment come
                      ):
        '''
        Accept a new item of equipment and put it in the list.

        Returns the new index of the equipment (for testing).
        '''
        return self.equipment.add(new_item, source)

    def ask_how_many(self,
                     item_index,    # index into fighter's stuff list
                     count=None     # number to remove (None if 'ask')
                     ):
        '''
        Determine how many items to remove.
        '''
        item = self.equipment.get_item_by_index(item_index)
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

    def remove_equipment(self,
                         item_index,    # index into fighter's stuff list
                         count=None     # number to remove (None if 'ask')
                         ):
        '''
        Discards an item from the Fighter's/Venue's equipment list.

        Returns: the discarded item
        '''
        count = self.ask_how_many(item_index, count)
        return self.equipment.remove(item_index, count)

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

    def get_long_summary_string(self):
        '''
        Returns a string that contains a short (but not the shortest)
        description of the state of the Fighter or Venue.
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

    def get_short_summary_string(self,
                                 fight_handler  # FightHandler, ignored
                                 ):
        '''
        Returns a string that contains the shortest description of the Fighter.
        '''
        return '%s' % self.name

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
                  world,          # World object - unused
                  fight_handler   # FightHandler object
                  ):
        '''
        Perform the post-fight cleanup.  Remove all the timers, that sort of
        thing.

        Returns nothing.
        '''
        self.timers.clear_all()

    def start_fight(self):
        '''
        Configures the Fighter or Venue to start a fight.

        Returns nothing.
        '''
        pass

    #
    # Protected
    #

    def _explain_numbers(self,
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

    def get_description(self,
                        char_detail,  # recepticle for character detail.
                                      #     [[{'text','mode'},...],  # line 0
                                      #      [...],               ]  # line 1..
                        ):
        '''
        Provides a text description of all of the components of a Venue.

        Returns: nothing -- output is written to the |char_detail| variable
        '''

        # stuff

        mode = curses.A_NORMAL
        char_detail.append([{'text': 'Equipment',
                             'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'stuff' in self.details:
            for item in sorted(self.details['stuff'], key=lambda x: x['name']):
                found_one = True
                ca_equipment.EquipmentManager.get_description(item,
                                                              [],
                                                              char_detail)

        if not found_one:
            char_detail.append([{'text': '  (None)', 'mode': mode}])

        # Timers

        mode = curses.A_NORMAL
        char_detail.append([{'text': 'Timers', 'mode': mode | curses.A_BOLD}])

        found_one = False
        timers = self.timers.get_all()  # objects
        for timer in timers:
            found_one = True
            text = timer.get_description()
            leader = '  '
            for line in text:
                char_detail.append([{'text': '%s%s' % (leader, line),
                                     'mode': mode}])
                leader = '    '

        if not found_one:
            char_detail.append([{'text': '  (None)', 'mode': mode}])

        # Notes

        mode = curses.A_NORMAL
        char_detail.append([{'text': 'Notes', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in self.details:
            for note in self.details['notes']:
                found_one = True
                char_detail.append([{'text': '  %s' % note, 'mode': mode}])

        if not found_one:
            char_detail.append([{'text': '  (None)', 'mode': mode}])

    def get_short_summary_string(self,
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

    conscious_map = {
        'alive': ALIVE,
        'unconscious': UNCONSCIOUS,
        'dead': DEAD,
        'Absent': ABSENT,  # Capitalized for menus
        'fight': FIGHT,
    }

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
        pass

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
                      new_item,   # dict describing new equipment
                      source=None  # string: from where did equipment came
                      ):
        '''
        Accept a new item of equipment and put it in the list.

        Returns the new index of the equipment.
        '''
        index = self.equipment.add(new_item, source)
        return index

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
                             index  # Index of weapon in fighter's 'stuff'
                                    # list.  'None' removes current weapon.
                             ):
        '''Draws or removes weapon from sheath or holster.'''
        # NOTE: call this from the ruleset if you want the ruleset to do its
        # due dilligence (i.e., stop the aim).

        # if we're holstering a weapon and there's a natural weapon, pick that
        # one up.
        if index is None:
            for item_index, item in enumerate(self.details['stuff']):
                if 'natural-weapon' in item and item['natural-weapon']:
                    index = item_index
                    break

        self.details['weapon-index'] = index

    def end_fight(self,
                  world,          # World object (for options)
                  fight_handler   # FightHandler object (for do_action)
                  ):
        '''
        Perform the post-fight cleanup.  Remove all the timers, reload if the
        option is set.  Sheathe the weapon.

        Returns nothing.
        '''
        super(Fighter, self).end_fight(world, fight_handler)
        if ('reload-after-fight' in world.details['options'] and
                world.details['options']['reload-after-fight'] and
                self.group == 'PCs'):
            self._ruleset.do_action(self,
                                    {'action-name': 'reload',
                                     'comment': 'Reloading after fight',
                                     'notimer': True,
                                     'quiet': True},
                                    fight_handler)
        self.details['weapon-index'] = None

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

    def get_current_weapon(self):
        '''
        Gets the weapon that the Fighter is holding.

        Returns a tuple:
            1) Weapon object
            2) index of the weapon
        '''
        if 'weapon-index' not in self.details:
            return None, None
        weapon_index = self.details['weapon-index']
        if weapon_index is None:
            return None, None
        weapon = self.equipment.get_item_by_index(weapon_index)
        return ca_equipment.Weapon(weapon), weapon_index

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

    def get_weapon_by_name(self,                # Public to support testing
                           name
                           ):
        '''
        Draw weapon from sheath or holster.

        Just used in testing.

        Returns index, Weapon object
        '''
        index, item = self.equipment.get_item_by_name(name)
        if index is not None:
            self.details['weapon-index'] = index
        return index, ca_equipment.Weapon(item)

    def print_me(self):
        print '-- Fighter (%s, %s) --' % (self.name, self.group)
        PP.pprint(self.details)

    def remove_equipment(self,
                         index_to_remove,  # <int> index into Equipment list
                         count=None     # number to remove (None if 'ask')
                         ):
        '''
        Discards an item from the Fighter's equipment list.

        Returns: the discarded item
        '''
        item = self.equipment.get_item_by_index(index_to_remove)
        if 'natural-weapon' in item and item['natural-weapon']:
            return None  # can't remove a natural weapon

        if 'natural-armor' in item and item['natural-armor']:
            return None  # can't remove a natural armor

        before_item_count = self.equipment.get_item_count()
        count = self.ask_how_many(index_to_remove, count)
        item = self.equipment.remove(index_to_remove, count)
        after_item_count = self.equipment.get_item_count()

        # Adjust indexes into the list if the list changed.

        if before_item_count != after_item_count:
            if index_to_remove == self.details['weapon-index']:
                self.details['weapon-index'] = None
            elif index_to_remove < self.details['weapon-index']:
                self.details['weapon-index'] -= 1

            for index, item in enumerate(self.details['armor-index']):
                if index_to_remove == item:
                    self.details['armor-index'].remove(item)
                elif index_to_remove < item:
                    self.details['armor-index'][index] -= 1

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

    def get_description(self,
                        output,  # recepticle for character detail.
                                 #  [[{'text','mode'},...],  # line 0
                                 #   [...],               ]  # line 1...
                        ):
        '''
        Provides a text description of a Fighter including all of the
        attributes (current and permanent), equipment, etc.

        Returns: nothing.  The output is written to the |output| variable.
        '''
        self._ruleset.get_character_description(self, output)

    def get_long_summary_string(self):
        '''
        Returns a string that contains a short (but not the shortest)
        description of the state of the Fighter.
        '''
        # TODO: this is ruleset-based
        fighter_string = '%s HP: %d/%d FP: %d/%d' % (
                                    self.name,
                                    self.details['current']['hp'],
                                    self.details['permanent']['hp'],
                                    self.details['current']['fp'],
                                    self.details['permanent']['fp'])
        return fighter_string

    def get_notes(self):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.)
        '''
        notes = self._ruleset.get_fighter_notes(self)
        return notes

    def get_short_summary_string(self,
                                 fight_handler  # FightHandler, ignored
                                 ):
        '''
        Returns a string that contains the shortest description of the Fighter.
        '''
        # TODO: this is ruleset based
        fighter_string = '%s HP:%d/%d' % (self.name,
                                          self.details['current']['hp'],
                                          self.details['permanent']['hp'])

        if self.is_dead():
            fighter_string += ' - DEAD'

        if self.timers.is_busy():
            fighter_string += ' - BUSY'

        if fight_handler.is_fighter_holding_init(self.name, self.group):
            fighter_string += ' - HOLDING INIT'

        return fighter_string

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
                          conscious_number  # <int> See Fighter.conscious_map
                          ):
        '''
        Sets the state (alive, unconscious, dead, absent, etc.) of the
        Fighter.

        Returns nothing.
        '''

        for state_name, state_num in Fighter.conscious_map.iteritems():
            if state_num == conscious_number:
                self.details['state'] = state_name
                break

        if not self.is_conscious():
            self.details['opponent'] = None  # unconscious men fight nobody
            self.draw_weapon_by_index(None)  # unconscious men don't hold stuff

    def start_fight(self):
        '''
        Configures the Fighter to start a fight.

        Returns nothing.
        '''
        # NOTE: we're allowing health to still be messed-up, here
        # NOTE: person may go around wearing armor -- no need to reset
        self.details['opponent'] = None
        if (self.group == 'PCs' and 'fight-notes' in self.details and
                self.details['fight-notes'] is not None):
            self.details['fight-notes'] = []
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

    def _explain_numbers(self,
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

        why_opponent = fight_handler.get_opponent_for(self)
        weapon, holding_weapon_index = self.get_current_weapon()

        lines = []

        unarmed_skills = self._ruleset.get_weapons_unarmed_skills(weapon)

        if unarmed_skills is not None:
            unarmed_info = self._ruleset.get_unarmed_info(self,
                                                          why_opponent,
                                                          weapon,
                                                          unarmed_skills)
            lines = [[{'text': x,
                       'mode': curses.A_NORMAL}] for x in unarmed_info['why']]
        else:
            if weapon.details['skill'] in self.details['skills']:
                ignore, to_hit_why = self._ruleset.get_to_hit(self,
                                                              why_opponent,
                                                              weapon)
                lines = [[{'text': x,
                           'mode': curses.A_NORMAL}] for x in to_hit_why]

                # Damage

                ignore, damage_why = self._ruleset.get_damage(self, weapon)
                lines.extend([[{'text': x,
                                'mode': curses.A_NORMAL}] for x in damage_why])

            if weapon.notes() is not None:
                lines.extend([[{'text': 'Weapon: "%s"' % weapon.name,
                               'mode': curses.A_NORMAL}]])
                lines.extend([[{'text': '  %s' % weapon.notes(),
                               'mode': curses.A_NORMAL}]])

        ignore, defense_why = self.get_defenses_notes(why_opponent)
        if defense_why is not None:
            lines = [[{'text': x,
                       'mode': curses.A_NORMAL}] for x in defense_why] + lines

        return lines
