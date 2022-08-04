#! /usr/bin/python

import copy
import curses
import datetime
import glob
import json
import os
import pprint
import re
import shutil
import sys
import traceback
import unicodedata

import ca_equipment
import ca_gui
import ca_json

# TODO: ammo should default to None.  Merging None with not None should be not
#   None.  The code should handle None as something that doesn't take ammo
#   (even if it's a missile weapon).
# TODO: damage type should be 'pi' by default
# TODO: fast-draw(knife) doesn't include +1 from combat reflexes
# TODO: spells don't deal with more points than 24 or 28

class Skills(object):
    # Techniques:
    # Your Final      Difficulty of Technique
    # Skill Level*    Average     Hard
    # Default         0 points    0 points
    # Default+1       1 point     2 points
    # Default+2       2 points    3 points
    # Default+3       3 points    4 points
    # Default+4       4 points    5 points
    # +1              +1 point    +1 point

    tech_plus_from_pts_table = { 'A': [0, 1, 2], 'H': [0, 0, 1]}

    # Skills:
    # To go from (cost, difficulty, attribute) to skill-level:
    #   level_from_cost[points put into spell] = base skill level
    #   difficulty_offset[difficulty] : add to base-level (Easy/Ave/Hard/VH)
    #   attribute : add to base-level

    # This is for easy skills.  More difficult skills are found using the
    # |difficulty_offset|
    level_from_cost = {1:0, 2:1, 4:2, 8:3, 12:4, 16:5, 20:6, 24:7, 28:8}
    difficulty_offset = {'E':0, 'A':-1, 'H':-2, 'VH':-3}
    skills = {
        'Acrobatics':           {'attr':'dx', 'diff':'H', 'default':-6},
        'Acting':               {'attr':'iq', 'diff':'A', 'default':-5},
        'Administration':       {'attr':'iq', 'diff':'A', 'default':-5},
        'Area Knowledge':       {'attr':'iq', 'diff':'E', 'default':-4},
        'Armoury':              {'attr':'iq', 'diff':'A', 'default':-5},
        'Axe/Mace':             {'attr':'dx', 'diff':'A', 'default':None},
        'Beam Weapons':         {'attr':'dx', 'diff':'E', 'default':-4,
                                 'equip': {'laser sight': 1}},
        # Bartender is really a professional skill
        'Bartender':            {'attr':'iq', 'diff':'A', 'default':-5},
        'Biology':              {'attr':'iq', 'diff':'VH', 'default':-6},
        'Brawling':             {'attr':'dx', 'diff':'E', 'default':None},
        'Broadsword':           {'attr':'dx', 'diff':'A', 'default':None},
        'Camouflage':           {'attr':'iq', 'diff':'E', 'default':-4},
        'Carousing':            {'attr':'ht', 'diff':'E', 'default':-4},
        'Climbing':             {'attr':'dx', 'diff':'A', 'default':-5},
        'Computer Hacking':     {'attr':'iq', 'diff':'VH', 'default':None,
                                 'equip': {'Hacking Equipment +1': 1}},
        'Computer Operation':   {'attr':'iq', 'diff':'E', 'default':-4},
        'Computer Programming': {'attr':'iq', 'diff':'H', 'default':None},
        'Connoisseur':          {'attr':'iq', 'diff':'A', 'default':-5},
        'Cryptography':         {'attr':'iq', 'diff':'H', 'default':None},
        'Current Affairs':      {'attr':'iq', 'diff':'E', 'default':-4},
        'Detect Lies':          {'attr':'per', 'diff':'H', 'default':-6,
                                 'advantage': {'Empathy': 3,
                                               'Empathy (sensitive)': 1}},
        'Diagnosis':            {'attr':'iq', 'diff':'H', 'default':-6},
        'Diplomacy':            {'attr':'iq', 'diff':'H', 'default':-6},
        'Electronics Operation':{'attr':'iq', 'diff':'A', 'default':-5},
        'Electronics Repair':   {'attr':'iq', 'diff':'A', 'default':-5},
        'Expert Skill':         {'attr':'iq', 'diff':'H', 'default':None},
        'Explosives':           {'attr':'iq', 'diff':'A', 'default':-5},
        'Engineer':             {'attr':'iq', 'diff':'H', 'default':None},
        'Environment Suit':     {'attr':'dx', 'diff':'A', 'default':-5},
        'Escape':               {'attr':'dx', 'diff':'H', 'default':-6},
        'Fast-Draw':            {'attr':'dx', 'diff':'E', 'default':None,
                                 # TODO: doesn't handle 'Fast-Draw (knife)'
                                 'advantage': {'Combat Reflexes': 1}},
        'Fast-Talk':            {'attr':'iq', 'diff':'A', 'default':-5},
        'Filch':                {'attr':'dx', 'diff':'A', 'default':-5},
        'Finance':              {'attr':'iq', 'diff':'H', 'default':None},
        'First Aid':            {'attr':'iq', 'diff':'E', 'default':-4,
                                 'equip': {'first aid kit': 1}},
        'Forensics':            {'attr':'iq', 'diff':'H', 'default':-6},
        'Forgery':              {'attr':'iq', 'diff':'H', 'default':-6},
        'Forward Observer':     {'attr':'iq', 'diff':'A', 'default':-5},
        'Gambling':             {'attr':'iq', 'diff':'A', 'default':-5},
        'Gesture':              {'attr':'iq', 'diff':'E', 'default':-4},
        'Gunner':               {'attr':'dx', 'diff':'E', 'default':-4},
        'Guns':                 {'attr':'dx', 'diff':'E', 'default':-4},
        'Hazardous Materials':  {'attr':'iq', 'diff':'A', 'default':-5},
        'Hiking':               {'attr':'ht', 'diff':'A', 'default':-5},
        'Holdout':              {'attr':'iq', 'diff':'A', 'default':-5},
        'Interrogation':        {'attr':'iq', 'diff':'A', 'default':-5},
        'Intimidation':         {'attr':'wi', 'diff':'A', 'default':-5},
        'Jumping':              {'attr':'dx', 'diff':'E', 'default':None},
        'Karate':               {'attr':'dx', 'diff':'H', 'default':None},
        'Knife':                {'attr':'dx', 'diff':'E', 'default':None},
        'Law':                  {'attr':'iq', 'diff':'H', 'default':-6},
        'Leadership':           {'attr':'iq', 'diff':'A', 'default':-5,
                                 'advantage': {'Charisma': 1}},
        'Lip Reading':          {'attr':'per', 'diff':'A', 'default':-10},
        'Lockpicking':          {'attr':'iq', 'diff':'A', 'default':-5},
        'Mathematics':          {'attr':'iq', 'diff':'H', 'default':-6},
        'Mechanic':             {'attr':'iq', 'diff':'A', 'default':-5},
        'Observation':          {'attr':'per', 'diff':'A', 'default':-5},
        'Panhandling':          {'attr':'iq', 'diff':'E', 'default':-4,
                                 'advantage': {'Charisma': 1}},
        'Persuade':             {'attr':'wi', 'diff':'H', 'default':None},
        'Poisons':              {'attr':'iq', 'diff':'H', 'default':-6},
        'Politics':             {'attr':'iq', 'diff':'A', 'default':-5},
        'Physician':            {'attr':'iq', 'diff':'H', 'default':-7},
        'Physics':              {'attr':'iq', 'diff':'VH', 'default':-6},
        'Pickpocket':           {'attr':'dx', 'diff':'H', 'default':-6},
        'Piloting':             {'attr':'dx', 'diff':'A', 'default':None},
        'Public Speaking':      {'attr':'iq', 'diff':'A', 'default':-5,
                                 'advantage': {'Charisma': 1}},
        'Running':              {'attr':'ht', 'diff':'A', 'default':-5},
        'Savoir-Faire':         {'attr':'iq', 'diff':'E', 'default':-4},
        'Scrounging':           {'attr':'per', 'diff':'E', 'default':-4},
        'Search':               {'attr':'per', 'diff':'A', 'default':-5},
        'Shadowing':            {'attr':'iq', 'diff':'A', 'default':-5},
        'Smuggling':            {'attr':'iq', 'diff':'A', 'default':-5},
        'Soldier':              {'attr':'iq', 'diff':'A', 'default':-5},
        'Stealth':              {'attr':'dx', 'diff':'A', 'default':-5},
        'Streetwise':           {'attr':'iq', 'diff':'A', 'default':-5},
        'Surgery':              {'attr':'iq', 'diff':'VH', 'default':None},
        'Survival':             {'attr':'per', 'diff':'A', 'default':None},
        'Tactics':              {'attr':'iq', 'diff':'H', 'default':-6},
        'Theology':             {'attr':'iq', 'diff':'H', 'default':-6},
        'Throwing':             {'attr':'dx', 'diff':'A', 'default':-3},
        'Thrown Weapon':        {'attr':'dx', 'diff':'E', 'default':-4},
        'Traps':                {'attr':'iq', 'diff':'A', 'default':-5},
        'Urban Survival':       {'attr':'per', 'diff':'A', 'default':-5},
    }

    @staticmethod
    def get_gcs_level(window_manager,   # ca_gui.GmWindowManager object
                      char,             # Character object
                      skill_gcs,        # dict: skill from GCS
                      skill_name,       # name of skill
                      cost              # points spent on skill
                     ):
        # TODO: the following skills are augmented by stuff
        #   - axe/mace: ?
        #   - armory: good quality equipment and ?
        #   - fast draw ammo: ?

        '''
        skill_gcs
        {
           'name': 'Beam Weapons',
           'specialization': 'Pistol',
           'defaulted_from': {'adjusted_level': 16, 'level': 16, 'modifier': -4,
                              'name': 'Beam Weapons', 'points': 8,
                              'type': 'Skill'},
           'defaults': [  {'modifier': -4, 'type': 'DX'},
                          {'modifier': -4, 'name': 'Beam Weapons',
                           'type': 'Skill'},
                          {'modifier': -4, 'name': 'Guns',
                           'specialization': 'Pistol', 'type': 'Skill'}],
           'difficulty': 'DX/E',
           'points': 0}
        '''

        # print('\n=== %s ===' % skill_name) # TODO: remove
        if skill_name not in Skills.skills:
            # print('NAME NOT IN SKILLS') # TODO: remove
            # Get the skill info from GCS
            if 'difficulty' not in skill_gcs:
                # print('** "difficulty" not in skill_gcs') # TODO: remove
                return 0
            match = re.match(
                    '(?P<attrib>[A-Za-z]+)(?P<slash>/)' +
                    '(?P<difficulty>[A-Za-z]+)',
                    skill_gcs['difficulty'])
            if match is None:
                # print('** match is None') # TODO: remove
                return 0
            skill_native = {'attr': match.group('attrib').lower(),
                            'diff': match.group('difficulty').upper()}
            # PP = pprint.PrettyPrinter(indent=3, width=150) # TODO: remove
            # PP.pprint(skill_native) # TODO: remove
        else:
            # {'attr':'dx', 'diff':'E', 'default':-4}
            skill_native = Skills.skills[skill_name]

        if skill_native['attr'] not in char.char['permanent']:
            window_manager.error([
                'Required attribute "%s" not supplied' % skill_native['attr']
                        ])
            return 0

        # Return a default value
        if cost == 0:
            # Easiest way to go -- GCS already calculated it and put it in
            # the skill.
            if ('defaulted_from' in skill_gcs and
                    'level' in skill_gcs['defaulted_from']):
                return skill_gcs['defaulted_from']['level']

            # Well crap, we have to use our own default calculation, then.
            if skill_native['default'] is None:
                window_manager.error([
                    'No default for skill "%s"' % skill_name
                            ])
                return 0
            return char.char['permanent'][skill_native['attr']] + skill_native['default']

        # If the user has more points than we have in our table, adjust
        # upwards.  Each level from the top costs 4 more than the previous.

        highest_cost = 0
        for cost_in_table in Skills.level_from_cost.keys():
            if highest_cost < cost_in_table:
                highest_cost = cost_in_table
                highest_level = Skills.level_from_cost[highest_cost]

        while cost > highest_cost:
            # print('expanding skill cost table') # TODO: remove
            highest_cost += 4
            highest_level += 1
            Skills.level_from_cost[highest_cost] = highest_level

        # Adjust cost down if someone has extra points (more spent points
        # than required for one skill level but not enough to get to the next
        # one) in a skill
        while cost not in Skills.level_from_cost and cost > 1:
            # print('reducing points spent because it is in between levels') # TODO: remove
            cost -= 1
        # print('spent points: %d' % cost) # TODO: remove
        if cost < 1 and not default:
            window_manager.error([
                'Cost %d invalid for skill %s' % (cost, skill_name)
                        ])
            return 0

        # Calculate the skill level
        level = char.char['permanent'][skill_native['attr']]
        # print('attribute (%s) = %d' % (skill_native['attr'], level)) # TODO: remove
        level += Skills.level_from_cost[cost]
        # print('add %d points for cost %d' % (Skills.level_from_cost[cost], cost)) # TODO: remove
        # print('level if it were an easy skill: %d' % level) # TODO: remove
        level += Skills.difficulty_offset[skill_native['diff']]
        # print('level at difficulty %s: %d' % (skill_native['diff'], level)) # TODO: remove

        # Add modifiers due to equipment
        if 'equip' in skill_native:
            PP = pprint.PrettyPrinter(indent=3, width=150) # Do Not Remove
            for looking_for, plus in skill_native['equip'].items():
                if Skills.is_item_in_equipment(looking_for, char.stuff):
                    level += plus
        if 'advantage' in skill_native:
            for looking_for, plus in skill_native['advantage'].items():
                if looking_for in char.char['advantages']:
                    level += plus

        # print('final level %d' % level) # TODO: remove

        return level

    @staticmethod
    def is_item_in_equipment(looking_for, # string
                             equipment    # list of dict, maybe w/containers
                             ):
        looking_for_lower = looking_for.lower()
        for item in equipment:
            if looking_for_lower == item['name'].lower():
                return True
            if 'container' in item['type']:
                result = Skills.is_item_in_equipment(looking_for,
                                                     item['stuff'])
                if result == True:
                    return result
        return False

    @staticmethod
    def tech_plus_from_pts(difficulty, # 'H' or 'A'
                           points   # int
                           ):
        table = Skills.tech_plus_from_pts_table[difficulty.upper()]
        if points < len(table):
            plus = table[points]
        else:
            # 4 points into a hard technique should get you:
            #   table[len(table) - 1] = table[2] = 1
            #   + points + 1 = 5
            #   - len(table) = -3
            #   = 1 + 5 - 3 = 3 (check against table on B230 = 3)
            plus = table[len(table) - 1] + points + 1 - len(table)
        return plus

class FromGcs(object):
    '''
    Reads the data from the GCS file and converts the data into native format.
    Maintains that data separate from the native data, though.
    '''
    def __init__(self,
                 window_manager,    # ca_gui.GmWindowManager object (for I/O)
                 ruleset,
                 gcs_file           # filename holding GCS information
                ):

        with ca_json.GmJson(gcs_file) as char_file:
            self.__gcs_data = char_file.read_data

        self.__window_manager = window_manager
        self.__ruleset = ruleset
        self.char = {} # JSON-like copy of character

        # Easier to build a separate 'stuff' list given containers and such.
        self.stuff = [] # [{'name':names.lower(), 'count': count, ...},... ]

    def build_character(self):
        # Alphabetical (which works out for required order of execution).
        # Dependencies are as follows:
        #   advantages <- attribs
        #   advantages <- skills
        #   equipment <- skills
        #   advantages <- spells

        self.__build_advantages()
        self.__build_attribs()
        self.__build_equipment()
        self.__build_skills()
        self.__build_spells()

    def get_name(self):
        if 'player_name' in self.__gcs_data['profile']:
            player_name = self.__gcs_data['profile']['player_name']
        else:
            player_name = None

        if 'name' in self.__gcs_data['profile']:
            character_name = self.__gcs_data['profile']['name']
        else:
            character_name = None

        if character_name is None:
           return 'Bob' if  player_name is None else player_name

        if player_name is None:
           return character_name

        return '%s - %s' % (character_name.lower(), player_name)

    def __add_advantage_to_gcs_list(self,
                               advantage_gcs,   # advantage dict
                               advantages_gcs   # {name: cost, ...
                              ):
        if advantage_gcs['type'] == 'advantage_container':
            #print '<< CONTAINER'
            for advantage in advantage_gcs['children']:
                self.__add_advantage_to_gcs_list(advantage, advantages_gcs)
            #print '>> CONTAINER'
        else:
            name = advantage_gcs['name']
            cost_gcs = self.__get_advantage_cost(advantage_gcs)

            if 'modifiers' in advantage_gcs:
                for modifier in advantage_gcs['modifiers']:
                    if 'disabled' in modifier and modifier['disabled']:
                        continue

                    if 'cost' in modifier:
                        if ('cost_type' in modifier and
                                modifier['cost_type'] == 'percentage'):
                            factor = int(modifier['cost']) / 100 # Make it a percentage
                            if factor > 0:
                                factor += 1 # if we're adding 50%, that's 150%
                            else:
                                factor *= -1 # if we're doing -50%, that's 50%
                            cost_gcs *= factor
                            cost_gcs = int(cost_gcs + 0.5)
                        else: # Just assuming cost_type == points
                            cost_gcs += int(modifier['cost'])

                    # Spell bonuses from a Lwa (if that applies)

                    if 'features' in modifier:
                        for feature in modifier['features']:
                            if feature['type'] == 'spell_bonus':
                                college = feature['name']['qualifier']
                                amount = feature['amount']
                                self.__spell_advantages[college] = amount

            advantages_gcs[name] = cost_gcs

    def __add_item_to_gcs_list(self,
                               item,        # ca dict
                               stuff_gcs,   # container of items (each, a dict)
                               container_name   # string (for debugging)
                              ):
        '''
        Adds entries into passed-in list for each item (and, recursively, each
        item in containers) in equipment list of a GCS character.
        '''
        new_thing = self.__ruleset.make_empty_item()
        name = item['description']
        if name is not None:
            new_thing['name'] = name
        count = 1 if 'quantity' not in item else item['quantity']
        new_thing['count'] = count

        if 'notes' in item:
            new_thing['notes'] = item['notes']

        # Is it armor?
        if 'features' in item:
            for feature in item['features']:
                if 'type' in feature:
                    if feature['type'] == 'dr_bonus':
                        amount = feature['amount']
                        # location = feature['location']
                        new_thing['type']['armor'] = {'dr': amount}

                        blank_item = self.__ruleset.make_empty_armor()
                        for key, value in blank_item.items():
                            if key not in new_thing:
                                new_thing[key] = value

        # Is it a weapon?
        if 'weapons' in item:
            for weapon in item['weapons']:
                if weapon['type'] == 'melee_weapon':
                    self.__get_melee_weapon(new_thing, item)

                if weapon['type'] == 'ranged_weapon':
                    self.__get_ranged_weapon(new_thing, item)

        # Container?
        if item['type'] == 'equipment_container' and 'children' in item:
            new_thing['type']['container'] = {}
            new_thing['stuff'] = []
            for contents in item['children']:
                self.__add_item_to_gcs_list(contents, new_thing['stuff'], new_thing['name'])

        # Now add to the creature
        if len(new_thing['type']) == 0:
            new_thing['type']['misc'] = {}

        for thing in stuff_gcs:
            if ToNative.find_differences(thing, new_thing) is None:
                thing['count'] += new_thing['count']
                new_thing = None
                break

        if new_thing is not None:
            stuff_gcs.append(new_thing)

    def __add_skill_to_weapon(self,
                              weapon_dest,      # dict: creating this weapon
                              mode,             # string: 'swung weapon', ...
                              weapon_source     # dict: from .gcs json
                              ):
        '''
        Goes through a GURPS Character Sheet description of a weapon and pulls
        out the best skill required to use it.  The result is placed in CA's
        description of that weapon.

        Returns nothing.
        '''
        weapon_dest['type'][mode]['skill'] = {}

        # Skill -- find the first one with skill modifier == 0
        still_need_a_skill = True
        # 'default' elements each describe a single skill (or attribute) that
        # can be used to use this item.  There're typically several as in:
        # knife (+0), sword (-2), DX (-4)

        if 'defaults' not in weapon_source:
            return # TODO:

        for default in weapon_source['defaults']:
            skill = default['type'] # DX or 'Skill'
            modifier = 0 if 'modifier' not in default else default['modifier']
            if (skill.lower() == 'skill'):
                # Looking for something like this:
                #   "type": "Skill",
                #   "name": "Force Sword",
                #   "modifier": -3

                skill = default['name']
                if 'specialization' in default:
                    skill = '%s (%s)' % (skill, default['specialization'])

                weapon_dest['type'][mode]['skill'][skill] = modifier
                still_need_a_skill = False
            else:
                # Looking for something like this:
				#   <default>
			    #       <type>DX</type>
				#       <modifier>-4</modifier>
				#   </default>

                if skill.lower() in self.char['permanent']:
                    # Then we're talking 'dx' or something as a default
                    weapon_dest['type'][mode]['skill'][skill] = modifier
                    still_need_a_skill = False

        if still_need_a_skill:
            weapon_dest['type'][mode]['skill']['** UNKNOWN **'] = 0
            self.__window_manager.error([
                'No skill for "%s" in GCS file -- adding dummy' %
                weapon_dest['name']
                ])

    def __build_advantages(self):
        self.char['advantages'] = {} # name: cost
        self.__spell_advantages = {}

        ## ADVANTAGES #####
        # Checks points spent

        advantages = self.__gcs_data['advantages']
        for advantage in advantages:
            self.__add_advantage_to_gcs_list(advantage,
                                             self.char['advantages'])

    def __build_attribs(self):
        self.char['permanent'] = {} # name: value

        # TODO: add move, and speed -- gcs has points spent / json
        # has result
        # CA names are lower_case, GCS names are upper_case
        #   'gcs stat' = the base attribute in GCS
        #   'adj' = GCS stat that adds to the native stat
        attrs = [
            # Base attributes
            'st',
            'dx',
            'iq',
            'ht',

            # Derived attributes
            'hp',
            'fp',
            'wi',
            'per',
            'basic-speed',
            'basic-move',
        ]

        for attr_dest in attrs:
            # Get the basic stat
            value = self.__get_old_style_gcs_attribute(attr_dest)
            if value is None:
                value = self.__get_new_style_gcs_attribute(attr_dest)

            self.char['permanent'][attr_dest] = value

    def __build_equipment(self):
        ## EQUIPMENT #####
        # Build the equipment list up front so that skills may make use of it
        if 'equipment' not in self.__gcs_data:
            return
        for item in self.__gcs_data['equipment']:
            self.__add_item_to_gcs_list(item, self.stuff, 'TOP LEVEL')

    def __build_skills(self):
        self.char['skills'] = {} # name: skill-level, ...
        self.char['techniques'] = [] # {"name":...,"default":[...],"value":#}

        # Checks skill cost
        # NOTE: Must run |__build_attribs|, |__build_advantages|, and
        #   |__build_equipment| before |__build_skills| because skills depend
        #   on attributes, some skills are affected by advantages, and
        #   equipment (a scope for a rifle, for instance).

        if 'skills' not in self.__gcs_data:
            return

        for skill_gcs in self.__gcs_data['skills']:
            base_name = skill_gcs['name']
            if 'type' not in skill_gcs:
                pass

            elif skill_gcs['type'] == 'skill':
                if ('specialization' in skill_gcs and
                        len(skill_gcs['specialization']) > 0):
                    name_text = '%s (%s)' % (skill_gcs['name'],
                                             skill_gcs['specialization'])
                else:
                    name_text = skill_gcs['name']

                cost_gcs = 0 if 'points' not in skill_gcs else skill_gcs['points']

                level_gcs = Skills.get_gcs_level(
                        self.__window_manager, self, skill_gcs, base_name, cost_gcs)
                self.char['skills'][name_text] = level_gcs
            elif skill_gcs['type'] == 'technique':
                # print('\n=== Technique: %s ===' % base_name) # TODO: remove
                difficulty = skill_gcs['difficulty'] # 'H', 'A'
                cost_gcs = 0 if 'points' not in skill_gcs else skill_gcs['points']
                plus = Skills.tech_plus_from_pts(difficulty, cost_gcs) ###################33

                default = skill_gcs['default']['name']
                if 'specialization' in skill_gcs['default']:
                    default += (' (%s)' % skill_gcs['default']['specialization'])
                skill_base = (0 if 'modifier' not in skill_gcs['default'] else ####################
                              skill_gcs['default']['modifier'])
                # print('based on %s = %d+%d' % (default, plus, skill_base)) # TODO: remove

                technique = {
                    'name': base_name,
                    'default': default,
                    'value': plus + skill_base
                    }
                self.char['techniques'].append(technique)

    def __build_spells(self):
        ## SPELLS #####
        #print('\n=== SPELLS ===') # TODO: remove

        # takes points
        skill_add_to_iq = {
                'hard' : [
                    {'points': 24, 'add_to_iq': 5},
                    {'points': 20, 'add_to_iq': 4},
                    {'points': 16, 'add_to_iq': 3},
                    {'points': 12, 'add_to_iq': 2},
                    {'points': 8, 'add_to_iq': 1},
                    {'points': 4, 'add_to_iq': 0},
                    {'points': 2, 'add_to_iq': -1},
                    {'points': 1, 'add_to_iq': -2},
                    # +4 for each +1 after this
                    ],

                'very_hard': [
                    {'points': 28, 'add_to_iq': 5},
                    {'points': 24, 'add_to_iq': 4},
                    {'points': 20, 'add_to_iq': 3},
                    {'points': 16, 'add_to_iq': 2},
                    {'points': 12, 'add_to_iq': 1},
                    {'points': 8, 'add_to_iq': 0},
                    {'points': 4, 'add_to_iq': -1},
                    {'points': 2, 'add_to_iq': -2},
                    {'points': 1, 'add_to_iq': -3},
                    # +4 for each +1 after this
                    ]
                    }

        if ('spells' not in self.__gcs_data or
                len(self.__gcs_data['spells']) == 0):
            #print('** gcs data has no spells') # TODO: remove
            return

        # NOTE: Only add 'spell's if the character has some.

        self.char['spells'] = [] # {'name': xx, 'skill': xx}, ...
        for spell_gcs in self.__gcs_data['spells']:
            name = spell_gcs['name']
            #print('\n--- Spell: %s ---' % name) # TODO: remove

            skill_gcs = self.char['permanent']['iq']
            #print('Start with IQ: %d' % skill_gcs) # TODO: remove

            # Spell difficulty
            # 'difficulty' = 'IQ/H' or 'IQ/VH'

            match = re.match(
                    '(?P<attrib>[A-Za-z]+)(?P<slash>/)' +
                    '(?P<difficulty>[A-Za-z]+)',
                    spell_gcs['difficulty'])
            if match is None:
                continue

            difficulty = ('hard' if match.group('difficulty').upper() == 'H'
                          else 'very_hard')

            # Points they need put into this spell to cast
            # match = re.match('^(?P<cost>[0-9]+)$', spell_gcs['casting_cost'])
            # TODO: this should be 'None' or 0
            #points = 1 if match is None else int(match.group('cost'))
            points = 1 if 'points' not in spell_gcs else spell_gcs['points']

            # College
            colleges = [] if 'college' not in spell_gcs else spell_gcs['college']
            best_plus = 0
            for college in colleges:
                if college in self.__spell_advantages:
                    if best_plus < self.__spell_advantages[college]:
                        best_plus = self.__spell_advantages[college]
                        #print('best_plus: %d for college: %s' % (best_plus, college)) # TODO: remove

            skill_gcs += best_plus

            # Get the skill level
            # TODO: doesn't deal with more points than 24 or 28
            for lookup in skill_add_to_iq[difficulty]:
                if points >= lookup['points']:
                    skill_gcs += lookup['add_to_iq']
                    #print('points: %d, plusses: %d' % (points, # TODO: remove
                    #    lookup['add_to_iq'])) # TODO: remove
                    break

            #print('for a total of %d\n' % skill_gcs) # TODO: remove
            self.char['spells'].append({'name': name, 'skill': skill_gcs})

    def __get_advantage_cost(self,
                             advantage_gcs # advantage dict
                            ):

        cost_gcs = (0 if 'base_points' not in advantage_gcs else
                    advantage_gcs['base_points'])
        if 'levels' in advantage_gcs and 'points_per_level' in advantage_gcs:
            cost_gcs += (advantage_gcs['points_per_level'] *
                    int(advantage_gcs['levels']))
        if 'cr' in advantage_gcs:
            # See 'Self-Control for Mental Disadvantages', B120
            self_control = [
                    {'cr': 6,  'multiplier': 2},
                    {'cr': 9,  'multiplier': 1.5},  # truncate, don't round
                    {'cr': 12,  'multiplier': 1},
                    {'cr': 15,  'multiplier': 0.5}, # truncate, don't round
                    ]

            cr = advantage_gcs['cr']
            for entry in self_control:
                if cr <= entry['cr']:
                    cost_gcs = int(cost_gcs * entry['multiplier'])
                    break
        return cost_gcs

    def __get_damage(
            self,
            weapon # dict: the whole weapon
            ):
        _st = ''
        _type = ''
        _base = ''
        damage = {}

        if 'damage' in weapon:
            if 'st' in weapon['damage']:
                # "damage": { "type": "cr", "st": "thr", "base": "-1" },
                # "damage": { "type": "cr", "st": "thr" },
                # "damage": { "type": "cut", "st": "sw", "base": "-2" },
                # "damage": { "type": "imp", "st": "thr" },
                # "damage": { "type": "imp", "st": "thr", "base": "-1" },

                # strength based, like:
                # <damage st="sw" type="cut" base="-2"/>
                # {"damage": {"st": "sw", "type": "cut", "plus": -2}},
                _st = weapon['damage']['st']
                _type = weapon['damage']['type']
                _base = (0 if 'base' not in weapon['damage']
                         else int(weapon['damage']['base']))
                damage = {'st': _st, 'plus': _base, 'type': _type}

            elif 'base' in weapon['damage']:
                # "damage": { "type": "HP", "base": "1d+4" }, # blaster
                # "damage": { "type": "fat", "base": "1d+1" }, # sick stick
                # "damage": { "type": "FP", "base": "1d+3" }, # zip tazer
                # "damage": { "type": "", "base": "2d+4" }, # laser pistol
                # "damage": { "type": "burn", "base": "3d", "armor_divisor": 2 }, # lasor rifle
                # "damage": { "type": "", "base": "3d", "armor_divisor": 3 }, # laser rifle
                #
                # {"damage": {"dice":{"plus":1,"num_dice":1,"type":"fat"}}}
                match = re.match(
                        '(?P<dice>[0-9]*)(?P<d>d?)' +
                        '(?P<sign>[+-]?)(?P<plus>[0-9]*)',
                        weapon['damage']['base'])
                if match is not None:
                    _num_dice = (0 if (match.group('dice') is None or
                                 len(match.group('dice')) == 0) else
                                 int(match.group('dice')))
                    _plus = (0 if (match.group('plus') is None or
                                 len(match.group('plus')) == 0) else
                                 int(match.group('plus')))
                    if (match.group('sign') is not None and
                            len(match.group('sign')) > 0):
                        sign = 1 if match.group('sign') == '+' else -1
                        _plus *= sign
                    _type = ('pi'
                             if ('type' not in weapon['damage'] or
                                 len(weapon['damage']['type']) == 0) else
                                 weapon['damage']['type'])
                    damage['dice'] = {
                            'num_dice': _num_dice,
                            'plus': _plus,
                            'type': _type}
            else:
                # "damage": { "type": "HT-4 aff" }, # tear gas
                pass # TODO

        return damage

    def __get_new_style_gcs_attribute(
            self,
            dest_name,  # string: name in destination
            ):
        attrs = {
            # Base attributes
            'st': 'st',
            'dx': 'dx',
            'iq': 'iq',
            'ht': 'ht',

            # Derived attributes
            'hp': 'hp',
            'fp': 'fp',
            'wi': 'will',
            'per': 'per',
            'basic-speed': 'basic_speed',
            'basic-move': 'basic_move',
        }
        if 'attributes' not in self.__gcs_data:
            return None

        src_name = attrs[dest_name]
        for gcs_attr in self.__gcs_data['attributes']:
            if src_name == gcs_attr['attr_id']:
                return gcs_attr['calc']['value']
        return None

    def __get_old_style_gcs_attribute(
            self,
            dest_name,  # string: name in destination
            ):
        '''
        Gets the specified attribute.  Calculates the attribute if need-be.
        '''
        # CA names are lower_case, GCS names are upper_case
        #   'gcs stat' = the base attribute in GCS
        #   'adj' = GCS stat that adds to the native stat
        attrs = {
            # Base attributes
            'st': {'gcs stat': 'ST',
                   'new_stat':'st',
                   'adj': None,
                   'cost_for_adv': None,
                   'advantage': None,
                   'disadvantage': None},
            'dx': {'gcs stat': 'DX',
                   'new_stat': 'dx',
                   'adj': None,
                   'cost_for_adv': None,
                   'advantage': None,
                   'disadvantage': None},
            'iq': {'gcs stat': 'IQ',
                   'new_stat': 'iq',
                   'adj': None,
                   'cost_for_adv': None,
                   'advantage': None,
                   'disadvantage': None},
            'ht': {'gcs stat': 'HT',
                   'new_stat': 'ht',
                   'adj': None,
                   'cost_for_adv': None,
                   'advantage': None,
                   'disadvantage': None},

            # Derived attributes
            'hp': {'gcs stat': 'ST',
                   'new_stat': 'hp',
                   'adj': ['HP_adj'],
                   'cost_for_adv': 2,
                   'advantage': 'Extra Hit Points',
                   'disadvantage': 'Fewer Hit Points'},
            'fp': {'gcs stat': 'HT',
                   'new_stat': 'fp',
                   'adj': ['FP_adj'],
                   'cost_for_adv': 3,
                   'advantage': 'Extra Fatigue Points',
                   'disadvantage': 'Fewer Fatigue Points'},
            'wi': {'gcs stat': 'IQ',
                   'new_stat': 'will',
                   'adj': ['will_adj'],
                   'cost_for_adv': 5,
                   'advantage': 'Increased Will',
                   'disadvantage': 'Decreased Will'},
            'per': {'gcs stat': 'IQ',
                   'new_stat': 'per',
                   'adj': ['per_adj'],
                   'cost_for_adv': 5,
                   'advantage': 'Increased Perception',
                   'disadvantage': 'Decreased Perception'},
            'basic-speed': {'gcs stat': None,
                   'new_stat': 'basic_speed',
                   'adj': ['speed_adj'],
                   'cost_for_adv': 5,
                   'advantage': 'Increased Basic Speed',
                   'disadvantage': 'Decreased Basic Speed'},
            'basic-move': {'gcs stat': None,  # Derived from basic-speed
                   'new_stat': 'basic_move',
                   'adj': ['speed_adj', 'move_adj'],
                   'cost_for_adv': 5,
                   'advantage': 'Increased Basic Move',
                   'disadvantage': 'Decreased Basic Move'},
        }

        # Get the attribute, itself
        attr = attrs[dest_name]

        if dest_name == 'basic-move' or dest_name == 'basic-speed':
            if 'HT' not in self.__gcs_data or 'DX' not in self.__gcs_data:
                return None
            attr_value = (self.__gcs_data['HT'] + self.__gcs_data['DX']) / 4.0

            # If they've bought up the main attribute, this adds the adjustment
            # Do it before basic-move truncates the value
            if attr['adj'] is not None:
                for adj in attr['adj']:
                    if adj in self.__gcs_data:
                        attr_value += self.__gcs_data[adj]

            if dest_name == 'basic-move':
                attr_value = int(attr_value)

        elif attr['gcs stat'] in self.__gcs_data:
            attr_value = self.__gcs_data[attr['gcs stat']]

            # If they've bought up the main attribute, this adds the adjustment
            if attr['adj'] is not None:
                for adj in attr['adj']:
                    if adj in self.__gcs_data:
                        attr_value += self.__gcs_data[adj]
        else:
            return None


        # Add advantage / disadvantage adjustments
        disadvantage_name = attr['disadvantage']
        cost_per_point = attr['cost_for_adv']
        if (disadvantage_name is not None and
                disadvantage_name in self.char['advantages']):
            attr_value += (self.char['advantages'][disadvantage_name] /
                      cost_per_point)

        advantage_name = attr['advantage']
        if (advantage_name is not None and
                advantage_name in self.char['advantages']):
            attr_value += (self.char['advantages'][advantage_name] /
                      cost_per_point)

        return attr_value

    def __get_melee_weapon(self,
                           new_thing,   # dict for receiving item
                           item         # dict, source for item
                           ):
        type_from_usage = {'Swung': 'swung weapon',
                           'Thrust': 'thrust weapon',
                           'Thrown': 'thrown weapon',
                           }
        if 'type' not in new_thing:
            new_thing['type'] = {}
        damage = {}

        for weapon in item['weapons']:
            if 'type' not in weapon or weapon['type'] != 'melee_weapon':
                continue
            damage = self.__get_damage(weapon)
            usage = 'Swung' if ('usage' not in weapon or
                                len(weapon['usage']) == 0) else weapon['usage']
            item_type = ('unknown weapon' if usage not in type_from_usage else
                         type_from_usage[usage])
            new_thing['type'][item_type] = {'damage': damage}

            self.__add_skill_to_weapon(new_thing, item_type, weapon)

            if ('parry' in weapon and len(weapon['parry']) > 0 and
                    weapon['parry'] != 'no'):
                new_thing['parry'] = int(weapon['parry'])

        blank_item = self.__ruleset.make_empty_melee_weapon()
        for key, value in blank_item.items():
            if key not in new_thing:
                new_thing[key] = value

    def __get_ranged_weapon(self,
                            new_thing,      # dict for receiving item
                            item            # dict, source for item
                            ):
        if 'type' not in new_thing:
            new_thing['type'] = {}
        damage = {}

        for weapon in item['weapons']:
            if 'type' not in weapon or weapon['type'] != 'ranged_weapon':
                continue
            damage = self.__get_damage(weapon)

            new_thing['type']['ranged weapon'] = {'damage': damage}
            self.__add_skill_to_weapon(new_thing, 'ranged weapon', weapon)

            if 'bulk' in weapon:
                new_thing['bulk'] = int(weapon['bulk'])

            # accuracy x+y where |x| is the accuracy of the weapon and |y| is
            # the accuracy of the built-in scope

            new_thing['acc'] = 0
            if 'accuracy' in weapon and len(weapon['accuracy']) > 0:
                accuracy_text = weapon['accuracy']
                accuracy_text = accuracy_text.replace('+', ' ')
                values = accuracy_text.split()
                for value in values:
                    new_thing['acc'] += int(value)

            # shots: T(1), or 8(3) or 8 (3)

            if 'shots' in weapon and len(weapon['shots']) > 0:
                match = re.match(
                        '(?P<shots>T|[0-9]+) *' +
                        '(?P<plus_one>\+1) *' +
                        '\( *(?P<reload>[0-9]+)' +
                        '(?P<individual>i?)\).*',
                        weapon['shots'])
                # TODO: eventually handle 'plus_pne' (one in the chamber)
                if match:
                    if match.group('shots') == 'T': # Thrown
                        new_thing['ammo'] = None
                        new_thing['reload_type'] = (
                                ca_equipment.Equipment.RELOAD_NONE)
                    else:
                        new_thing['ammo'] = { 'name': '*UNKNOWN*'}
                        shots = int(match.group('shots'))
                        new_thing['ammo']['shots'] = shots
                        new_thing['ammo']['shots_left'] = shots
                        if len(match.group('individual')) > 0:
                            new_thing['reload_type'] = (
                                    ca_equipment.Equipment.RELOAD_ONE)
                        else:
                            new_thing['reload_type'] = (
                                    ca_equipment.Equipment.RELOAD_CLIP)

                        new_thing['reload'] = int(match.group('reload'))

            '''
            {
              "clip": {
                "count": 2, "notes": "", "type": [ "misc" ], "owners": null, "name": "C Cell"
              },
            }
            '''

        blank_item = self.__ruleset.make_empty_missile_weapon()
        for key, value in blank_item.items():
            if key not in new_thing:
                new_thing[key] = value

class ToNative(object):
    '''
    Objects of this class transfer items from the GCS data into a native
    database.
    '''
    def __init__(self,
                 window_manager,
                 native_data,   # dict for this char directly from CA
                 gcs_data       # FromGcs object from file
                ):
        self.__window_manager = window_manager
        self.__native_data = native_data
        self.__gcs_data = gcs_data

    @staticmethod
    def find_differences(existing_item,   # dict:
                         new_item         # dict:
                         ):
        '''
        Returns list of differences, None if none were found.
        '''
        found_differences = False
        differences = []
        if existing_item['name'].lower() != new_item['name'].lower():
            found_differences = True
            differences.append('name')
            return differences

        if existing_item['type'] != new_item['type']:
            found_differences = True
            differences.append('type')
            return differences

        # We don't care if the counts, notes, or owners aren't the same

        if ('melee weapon' in existing_item['type'] or
            'swung weapon' in existing_item['type'] or
            'thrust weapon' in existing_item['type']):
            if not ToNative.is_optional_element_equal('parry',
                                                      existing_item,
                                                      new_item):
                found_differences = True
                differences.append('parry')

        if 'ranged weapon' in existing_item['type']:
            if not ToNative.is_optional_element_equal('bulk',
                                                      existing_item,
                                                      new_item):
                found_differences = True
                differences.append('bulk')

            if not ToNative.is_optional_element_equal('acc',
                                                      existing_item,
                                                      new_item):
                found_differences = True
                differences.append('acc')

            if not ToNative.is_optional_element_equal('reload',
                                                      existing_item,
                                                      new_item):
                found_differences = True
                differences.append('reload')

        if 'armor' in existing_item['type']:
            existing_armor = existing_item['type']['armor']
            new_armor = new_item['type'].get('armor', None)
            if (new_armor is None or 'dr' not in new_armor or
                    existing_armor['dr'] != new_armor['dr']):
                found_differences = True
                differences.append('dr')

        if 'container' in existing_item['type']:
            new_contents = copy.deepcopy(new_item['stuff'])
            for thing in existing_item['stuff']:
                found_match = False
                for index, new_thing in enumerate(new_contents):
                    new_differences = ToNative.find_differences(
                            thing, new_thing)
                    if new_differences is None:
                        new_contents.pop(index)
                        found_match = True
                        break
                    else:
                        differences.extend(new_differences)
                if not found_match:
                    found_differences = True
            if len(new_contents) > 0:
                found_differences = True

        return differences if found_differences else None

    @staticmethod
    def is_optional_element_equal(element,          # string: comaring this
                                  existing_item,    # dict
                                  new_item          # dict
                                  ):
        if element in existing_item:
            if element not in new_item:
                return False
            if existing_item[element] != new_item[element]:
                return False
        elif element in new_item:
            return False

        return True

    def import_character(self):
        self.__import_attribs()
        self.__import_advantages()
        self.__import_skills()
        self.__import_techniques()
        self.__import_spells()
        self.__import_equipment(squash=False)

    def import_equipment_list(self):
        '''
        "rows": [
            {
                "type": "equipment",
                "id": "a5863dd4-b9f3-41a0-bd99-fae58e552c67",
                "quantity": 1,
                "description": "Antibiotic",
                "tech_level": "6",
                "value": "20",
                "weight": "0 lb",
                "reference": "B289",
                "calc": {
                    "extended_value": "20",
                    "extended_weight": "0 lb"
                },
                "notes": "Prevents or cures (in 1d days) infections.",
                "categories": [
                    "Medical Gear"
                ]
            },
            {
                "type": "equipment",
                "id": "4f2a9783-adb2-4c52-abdd-fa5d112b8a9b",
                "quantity": 1,
        '''
        xxx
        while xxx:
            self.__import_equipment(squash=False)

    def pprint(self):
        print('\n=== Import Creature ===')
        PP = pprint.PrettyPrinter(indent=3, width=150) # Do Not Remove
        PP.pprint(self.__native_data)

    def update_data(self):
        changes = []
        changes.extend(self.__import_attribs())
        changes.extend(self.__import_advantages())
        changes.extend(self.__import_skills())
        changes.extend(self.__import_techniques())
        changes.extend(self.__import_spells())
        changes.extend(self.__import_equipment(squash=True))

        if len(changes) == 0:
            changes.append('Character up to date -- no changes')

        return changes

    # Private and protected methods

    def __copy_json_equipment_list(self,
                                   equipment,  # list of items
                                   squash      # Bool: do we flatten containers
                                   ):
        '''
        Makes a deep copy of a JSON equipment list.

        This (optionally) flattens (i.e., squashes) nested containers so that
        all of the items are on the same level.  That allows one set of
        containers in GCS and a different set of containers in the CA.

        This can copy a GCS list so long as it's been CA-ized.
        '''
        new_list = []
        for item in equipment:
            if squash and ('container' in item['type']):
                # Copy the contents
                sub_list = self.__copy_json_equipment_list(item['stuff'],
                                                           squash)
                new_list.extend(sub_list)
                # I don't think I want to copy the container without its
                # contents because the whole purpose of squashing is to
                # allow differnet containers in the GCS than in the CA.
                #
                # new_item = copy.deepcopy(item)
                # new_item['stuff'] = []
                # new_list.append(new_item)
            else:
                #new_item = copy.deepcopy(item)
                #new_list.append(new_item)
                new_list.append(item)

        return new_list

    def __get_stuff_count(self,
                          item
                          ):
        return 1 if 'count' not in item else item['count']

    def __import_advantages(self):
        return self.__import_heading('advantages', 'advantage')

    def __import_attribs(self):
        '''
        Copies the attributes from GCS to CA.  Puts the values in both
        the current and permanent locations.

        Cool for both import and update.

        Returns changes (array of strings describing changes made).
        '''
        attrs_to_check = [ 'st' , 'dx' , 'iq' , 'ht', 'hp', 'fp', 'wi', 'per',
                           'basic-speed', 'basic-move' ]
        changes = []
        for attr_name in attrs_to_check:
            attr_gcs = self.__gcs_data.char['permanent'][attr_name]
            attr_json = self.__native_data['permanent'][attr_name]
            if attr_gcs != attr_json:
                changes.append('%s changed from %r to %r' %
                        (attr_name, attr_json, attr_gcs))
                self.__native_data['permanent'][attr_name] = attr_gcs
                self.__native_data['current'][attr_name] = attr_gcs
        return changes

    def __import_equipment(self,
                           squash   # Bool: whether to flatten containers
                           ):
        changes = []
        if 'stuff' not in self.__native_data:
            self.__native_data['stuff'] = []

        stuff_json = self.__copy_json_equipment_list(
                self.__native_data['stuff'], squash)
        stuff_gcs = self.__copy_json_equipment_list(
                self.__gcs_data.stuff, squash)

        PP = pprint.PrettyPrinter(indent=3, width=150) # Do Not Remove
        standout_mode = curses.color_pair(ca_gui.GmWindowManager.YELLOW_BLACK)

        for item_json in stuff_json:    # item_json is {}
            match_gcs = False
            for index, item_gcs in enumerate(stuff_gcs):
                if ToNative.find_differences(item_json,
                                             item_gcs) is None:
                    stuff_gcs.pop(index)
                    match_gcs = True
                    break

            if not match_gcs:
                # Do a second pass looking for items that are similar
                for index, item_gcs in enumerate(stuff_gcs):
                    if item_json['name'].lower() == item_gcs['name'].lower():

                        differences = ToNative.find_differences(
                                item_json, item_gcs)

                        # Make the user descide if these are the same item
                        output = []
                        output.append([{'text': ('--- GCS Item: %s ---' % item_gcs['name']),
                                        'mode': curses.A_NORMAL}])
                        string = PP.pformat(item_gcs)
                        strings = string.split('\n')
                        for string in strings:
                            mode = curses.A_NORMAL
                            for difference in differences:
                                if string.find(difference) >= 0:
                                    mode = standout_mode
                            output.append([{'text': string, 'mode': mode}])

                        output.append([{'text': '',
                                        'mode': curses.A_NORMAL}])
                        output.append([{'text': ('--- CA Item: %s ---' % item_json['name']),
                                        'mode': curses.A_NORMAL}])
                        string = PP.pformat(item_json)
                        strings = string.split('\n')
                        for string in strings:
                            mode = curses.A_NORMAL
                            for difference in differences:
                                if string.find(difference) >= 0:
                                    mode = standout_mode
                            output.append([{'text': string, 'mode': mode}])

                        # Merged
                        new_item = copy.deepcopy(item_json)
                        self.__merge_items(new_item, item_gcs)
                        output.append([{'text': '',
                                        'mode': curses.A_NORMAL}])
                        output.append([{'text': ('--- MERGED Item: %s ---' % new_item['name']),
                                        'mode': curses.A_NORMAL}])
                        string = PP.pformat(new_item)
                        strings = string.split('\n')
                        for string in strings:
                            mode = curses.A_NORMAL
                            for difference in differences:
                                if string.find(difference) >= 0:
                                    mode = standout_mode
                            output.append([{'text': string, 'mode': mode}])
                        #

                        self.__window_manager.display_window(
                                ('Examine These %s -- Are They The Same Item?' %
                                    item_json['name']),
                                output)
                        request_menu = [('yes', True), ('no', False)]
                        they_are_the_same, ignore = self.__window_manager.menu(
                                'Well, Are They The Same Item?', request_menu)

                        if they_are_the_same:
                            stuff_gcs.pop(index)
                            match_gcs = True
                            # TODO: copy unmatched things from GCS to CA
                            self.__merge_items(item_json, item_gcs)
                            break
                        else:
                            remove_menu = [('yes', True), ('no', False)]
                            remove, ignore = self.__window_manager.menu(
                                'Remove "%s" (in CA) but NOT in GCS' %
                                item_json['name'], remove_menu)
                            if remove:
                                changes.append('"%s" equipment item removed' %
                                        item_json['name'])
                                # remove removes a list element by value
                                self.__native_data['stuff'].remove(item_json['name'])

        for item_gcs in stuff_gcs:
            name_gcs = item_gcs['name']

            if ('ignored-equipment' in self.__native_data and
                    name_gcs.lower() in self.__native_data['ignored-equipment']):
                changes.append('"%s" equipment IGNORED -- no change' %
                        item_gcs['name'])
            else:
                changes.append('"%s" equipment item added' % item_gcs['name'])
                self.__native_data['stuff'].append(item_gcs)

        return changes

    def __import_heading(self,
                        heading,            # string: 'skills', 'advantages', etc
                        heading_singular    # string: 'skill', 'advantage', etc
                        ):
        changes = []

        if heading in self.__native_data:
            things_json = self.__native_data[heading]
        else:
            things_json = {}

        # Make the copy so we can delete matches from the list and not mess up
        # the original character.
        if heading in self.__gcs_data.char:
            things_gcs = copy.deepcopy(self.__gcs_data.char[heading])
        else:
            things_gcs = {}

        if len(things_gcs) == 0 and len(things_json) == 0:
            # Neither has |things|; everything's good
            return changes

        items_to_remove = []
        for name in things_json.keys():
            if name not in things_gcs:
                remove_menu = [('yes', True), ('no', False)]
                remove, ignore = self.__window_manager.menu(
                        'Remove "%s" %s (in CA=%r) but NOT in GCS' % (
                            name, heading_singular, things_json[name]),
                        remove_menu)
                if remove:
                    changes.append('"%s" %s removed' % (name,
                                                        heading_singular))
                    items_to_remove.append(name)
            else:
                if things_gcs[name] != things_json[name]:
                    if things_gcs[name] > things_json[name]:
                        changes.append('%s %s changed from %r to %r' %
                                (name, heading_singular, things_json[name],
                                 things_gcs[name]))
                    else:
                        changes.append(
                                '%s %s changed from %r to %r -- NOTE: value reduced' %
                                (name, heading_singular, things_json[name],
                                 things_gcs[name]))
                    things_json[name] = things_gcs[name]
                del(things_gcs[name])

        while len(items_to_remove) > 0:
            name = items_to_remove.pop()
            # del removes a dict item
            del self.__native_data[heading][name]

        for name in things_gcs.keys():
            changes.append('%s (%d) %s added' %
                    (name, things_gcs[name], heading_singular))
            things_json[name] = things_gcs[name]

        return changes

    def __import_skills(self):
        return self.__import_heading('skills', 'skill')

    def __import_spells(self):
        changes = []
        if 'spells' not in self.__native_data:
            self.__native_data['spells'] = []
        spells_json = self.__native_data['spells']

        if 'spells' in self.__gcs_data.char:
            spells_gcs = copy.deepcopy(self.__gcs_data.char['spells'])
        else:
            spells_gcs = []

        if len(spells_gcs) == 0 and len(spells_json) == 0:
            # Neither has |spells| and that's OK.
            return changes

        spells_to_remove = []
        for spell_json in spells_json:
            # Find the GCS equivalent
            match_gcs = None
            for index, spell_gcs in enumerate(spells_gcs):
                if spell_gcs['name'] == spell_json['name']:
                    match_gcs = spell_gcs
                    del spells_gcs[index]
                    break

            name = spell_json['name']
            if match_gcs is None:
                remove_menu = [('yes', True), ('no', False)]
                remove, ignore = self.__window_manager.menu(
                        'Remove "%s" spell (in CA=%r) but NOT in GCS' % (
                            name, spell_json['skill']), remove_menu)
                if remove:
                    changes.append('"%s" spell removed' % name)
                    spells_to_remove.append(name)
            else:
                if match_gcs['skill'] != spell_json['skill']:
                    if match_gcs['skill'] > spell_json['skill']:
                        changes.append(
                                '%s spell changed from %r to %r' %
                                (spell_json['name'], spell_json['skill'],
                                 match_gcs['skill']))
                    elif match_gcs['skill'] < spell_json['skill']:
                        changes.append(
                                '%s spell changed from %r to %r -- NOTE: value reduced' %
                                (spell_json['name'], spell_json['skill'],
                                 match_gcs['skill']))
                    spell_json['skill'] = match_gcs['skill']

        for spell_name in spells_to_remove:
            for index, spell_json in enumerate(spells_json):
                if spell_name == spell_json['name']:
                    del spells_json[index]
                    break

        for spell_gcs in spells_gcs:
            changes.append('%s (%d) spell added' %
                           (spell_gcs['name'], spell_gcs['skill']))
            spells_json.append(spell_gcs)

        return changes

    def __import_techniques(self):
        # TODO: there's probably a way to combine techniques and skills (since
        # they're both lists as opposed to the dicts examined by
        # |__import_heading|).  The challenge is that skills and techniques look
        # different under the hood so the 'do we copy' stuff needs to be
        # custom.
        changes = []
        if 'techniques' not in self.__native_data:
            self.__native_data['techniques'] = []
        techniques_json = self.__native_data['techniques']

        if 'techniques' in self.__gcs_data.char:
            techniques_gcs = copy.deepcopy(self.__gcs_data.char['techniques'])
        else:
            techniques_gcs = []

        if len(techniques_gcs) == 0 and len(techniques_json) == 0:
            # Neither has |techniques| and that's OK.
            return changes

        for technique_json in techniques_json:
            match_gcs = None
            index_gcs = None
            for index, technique_gcs in enumerate(techniques_gcs):
                if (technique_gcs['name'] == technique_json['name'] and
                        technique_gcs['default'] == technique_json['default']):
                    match_gcs = technique_gcs
                    index_gcs = index
                    break

            if ('default' in technique_json and
                    len(technique_json['default']) != 0):
                name = '%s (%s)' % (technique_json['name'],
                                    technique_json['default'])
            else:
                name = technique_json['name']

            if match_gcs is None:
                remove_menu = [('yes', True), ('no', False)]
                remove, ignore = self.__window_manager.menu(
                        'Remove "%s" technique (in CA=%r) but NOT in GCS' % (
                            name, technique_json['value']), remove_menu)
                if remove:
                    changes.append('"%s" technique removed' % name)
                    self.__native_data['techniques'].remove(technique_json)
            else:
                if match_gcs['value'] != technique_json['value']:
                    if match_gcs['value'] > technique_json['value']:
                        changes.append(
                                '%s technique changed from %r to %r' %
                                (name, technique_json['value'], match_gcs['value']))
                    else:
                        changes.append(
                                '%s technique changed from %r to %r -- NOTE: value reduced' %
                                (name, technique_json['value'], match_gcs['value']))
                    technique_json['value'] = match_gcs['value']

                del techniques_gcs[index_gcs]

        for technique_gcs in techniques_gcs:
            if ('default' in technique_gcs and
                    len(technique_gcs['default']) != 0):
                name = '%s (%s)' % (technique_gcs['name'],
                                    ', '.join(technique_gcs['default']))
            else:
                name = technique_gcs['name']

            changes.append('%s (%d) technique added' %
                           (name, technique_gcs['value']))
            techniques_json.append(technique_gcs)

        return changes

    def __merge_items(self,
                      item_json,    # dict, destination
                      item_gcs      # dict
                      ):
        '''
        Merges equipment item |item_gcs| into |item_json|
        '''
        if item_json == item_gcs or item_gcs is None:
            return
        if isinstance(item_json, dict):
            if not isinstance(item_gcs, dict):
                return # Not worth merging if they're not the same type

            for key, value in item_gcs.items():
                if key not in item_json:
                    item_json[key] = value
                elif item_json[key] != item_gcs[key]:
                    if self.__is_scalar(item_json[key]):
                        # TODO: |str| instead of |basestring| in python 3
                        if (isinstance(item_gcs[key], str) and
                                isinstance(item_json[key], str)):
                            if len(item_json[key]) == 0:
                                item_json[key] = item_gcs[key]
                        else:
                            item_json[key] = item_gcs[key]
                    else:
                        self.__merge_items(item_json[key], item_gcs[key])

        elif isinstance(item_json, list):
            if not isinstance(item_gcs, list):
                return # Not worth merging if they're not the same type

            for value in item_gcs:
                if value not in item_json:
                    item_json.append(value)

    def  __is_scalar(self,
                     item
                     ):
        if isinstance(item, dict):
            return False
        if isinstance(item, list):
            return False
        # set, tuple, <class>, str, int, float
        return True


def timeStamped(fname,  # <string> Base filename
                tag,    # <string> Sepecial tag to add to the end of a filename
                ext,    # <string> Filename extnesion
                fmt='{fname}-%Y-%m-%d-%H-%M-%S{tag}.{ext}'
                ):
    '''
    Builds a time-stamped filename.
    '''
    tag = '' if tag is None else ('-%s' % tag)
    return datetime.datetime.now().strftime(fmt).format(fname=fname,
                                                        tag=tag,
                                                        ext=ext)

def get_dest_filename(json_filename):
    '''
    Generates a destination filename to which to copy json_filename.  The
    destination filename will be unique.
    '''
    keep_going = True

    root_filename = os.path.splitext(json_filename)[0]

    count = 0
    while keep_going:
        counted_tag = '%d' % count
        dest_filename = timeStamped(root_filename, counted_tag, 'json')
        if os.path.exists(dest_filename):
            count += 1
        else:
            keep_going = False
    return dest_filename

class GcsImport(object):
    def __init__(self,
                 window_manager,    # ca_gui.GmWindowManager object
                 ):
        self.__window_manager = window_manager

    def import_creature(self,
                        native_data,         # dict = empty creature
                        ruleset,             # ca_ruleset.Ruleset object
                        gcs_filename=None,   # string
                        ):
        '''
        Returns: name of the creature and the dict containing the creature

        |native_data| contains a template that fills-in stuff that the ruleset
        needs but may not be provided by the imported creature.
        '''
        gcs_filename = self.__extract_gcs_filename(native_data, gcs_filename)

        gcs_data = FromGcs(self.__window_manager, ruleset, gcs_filename)
        gcs_data.build_character()
        name = gcs_data.get_name()

        character = ToNative(self.__window_manager, native_data, gcs_data)
        character.import_character()
        # character.pprint() ######################
        return name, native_data

    def import_equipment(self,
                         native_data,         # array = original equipment list
                         ruleset,             # ca_ruleset.Ruleset object
                         gcs_filename=None,   # string
                         ):
        '''
        Returns: array containing the equipment list
        '''
        gcs_filename = self.__extract_gcs_filename(native_data, gcs_filename)

        gcs_data = FromGcs(self.__window_manager, ruleset, gcs_filename)
        gcs_data.build_equipment()

        equipment = ToNative(self.__window_manager, native_data, gcs_data)
        equipment.import_equipment_list()
        # equipment.pprint() ######################
        return native_data

    def update_creature(self,
                        native_data,           # dict contains original creature
                        ruleset,             # ca_ruleset.Ruleset object
                        gcs_filename=None,   # string
                        ):
        gcs_filename = self.__extract_gcs_filename(native_data, gcs_filename)
        gcs_data = FromGcs(self.__window_manager, ruleset, gcs_filename)
        name = gcs_data.get_name()
        character = ToNative(self.__window_manager, native_data, gcs_data)
        changes = character.update_data()
        return changes

    def __extract_gcs_filename(
            self,
            native_data,        # dict contains original creature
            gcs_filename=None,  # string: in/outuser-supplied
            ):
        '''
        Gets the GCS filename.  Checks the user-supplied value, first, and
        fills with the value in native_data if the former value is None.

        Returns extracted GCS filename.
        '''

        if gcs_filename is None:
            if 'gcs-file' in native_data:
                gcs_filename = native_data['gcs-file']
            else:
                self.__window_manager.error([
                    'Need a GCS filename from which to import'])
                return None

        if ('gcs-file' not in native_data or native_data['gcs-file'] is None or
            len(native_data['gcs-file']) == 0):
            native_data['gcs-file'] = gcs_filename
        elif native_data['gcs-file'] != gcs_filename:
            native_data['gcs-file'] = gcs_filename
            self.__window_manager.display_window(
                    'NOTE',
                    [[{'text': ('Changing gcs-file from %s to %s' %
                                (native_data['gcs-file'], gcs_filename)),
                        'mode': curses.A_NORMAL}]])

        return gcs_filename
