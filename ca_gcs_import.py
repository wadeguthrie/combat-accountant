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
import xml.etree.ElementTree as ET

# Examples of how ET works
#
# <melee_weapon>
#   foo
#   <damage type="cut" st="sw" base="-2"/>
#
# element = element.find('melee_weapon') or element.findall('melee_weapon')
# element.text is 'foo'
# element.attrib = {'type': 'cut', 'st': 'sw', 'base': '-2'}

# TODO: Doesn't seem to flatten containers (and remove contents of containers) on update
# For Import, keep containers
# For Update, flatten all containers -- put new items at top level


import ca_json

# TODO: spenser's & Alan's laser rifle says ACC 9 when I have 8
# TODO: karen's laser pistol says ACC 2 when I have 3 (I may have just messed up)
# TODO: erik's & Alans's laser rifle says BULK -4 when I have -5
# TODO: damage type should be 'pi' by default
# TODO: erik's Blaster Pistol, Sig Sauer D65 doesn't show as same weapon in GCS
# TODO: alan's Colt Series 170D shows reload of 2 when I have 3

# TODO: fast-draw(knife) doesn't include +1 from combat reflexes

# TODO: spells don't deal with more points than 24 or 28
# TODO: build a list of everything that changes (for 'update', not 'import')

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
    #   level_from_cost[cost] = base level
    #   difficulty_offset[difficulty] : add to base-level
    #   attribute : add to base-level
    level_from_cost = {1:0, 2:1, 4:2, 8:3, 12:4, 16:5, 20:6, 24:7, 28:5}
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
        'Camouflage':           {'attr':'iq', 'diff':'E', 'default':-4},
        'Climbing':             {'attr':'dx', 'diff':'A', 'default':-5},
        'Computer Hacking':     {'attr':'iq', 'diff':'VH', 'default':None},
        'Computer Operation':   {'attr':'iq', 'diff':'E', 'default':-4},
        'Computer Programming': {'attr':'iq', 'diff':'H', 'default':None},
        'Connoisseur':          {'attr':'iq', 'diff':'A', 'default':-5},
        'Cryptography':         {'attr':'iq', 'diff':'H', 'default':None},
        'Current Affairs':      {'attr':'iq', 'diff':'E', 'default':-4},
        'Detect Lies':          {'attr':'per', 'diff':'H', 'default':-6,
                                 'advantage': {'Empathy': 3,
                                               'empathy (sensitive)': 1}},
        'Diagnosis':            {'attr':'iq', 'diff':'H', 'default':-6},
        'Diplomacy':            {'attr':'iq', 'diff':'H', 'default':-6},
        'Electronics Operation':{'attr':'iq', 'diff':'A', 'default':-5},
        'Electronics Repair':   {'attr':'iq', 'diff':'A', 'default':-5},
        'Expert Skill':         {'attr':'iq', 'diff':'H', 'default':None},
        'Explosives':           {'attr':'iq', 'diff':'A', 'default':-5},
        'Engineer':             {'attr':'iq', 'diff':'H', 'default':None},
        'Environment Suit':     {'attr':'dx', 'diff':'A', 'default':-5},
        'Escape':               {'attr':'dx', 'diff':'H', 'default':-6},
        'Fast-Draw':            {'attr':'dx', 'diff':'E', 'default':None},
        'Fast-Talk':            {'attr':'iq', 'diff':'A', 'default':-5},
        'Filch':                {'attr':'dx', 'diff':'A', 'default':-5},
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
        'Leadership':           {'attr':'iq', 'diff':'A', 'default':-5},
        'Lip Reading':          {'attr':'per', 'diff':'A', 'default':-10},
        'Lockpicking':          {'attr':'iq', 'diff':'A', 'default':-5},
        'Mathematics':          {'attr':'iq', 'diff':'H', 'default':-6},
        'Mechanic':             {'attr':'iq', 'diff':'A', 'default':-5},
        'Observation':          {'attr':'per', 'diff':'A', 'default':-5},
        'Poisons':              {'attr':'iq', 'diff':'H', 'default':-6},
        'Physician':            {'attr':'iq', 'diff':'H', 'default':-7},
        'Physics':              {'attr':'iq', 'diff':'VH', 'default':-6},
        'Pickpocket':           {'attr':'dx', 'diff':'H', 'default':-6},
        'Piloting':             {'attr':'dx', 'diff':'A', 'default':None},
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
    def tech_plus_from_pts(difficulty, # 'H' or 'A'
                           points   # int
                           ):
        table = Skills.tech_plus_from_pts_table[difficulty]
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

    @staticmethod
    def get_gcs_level(window_manager,   # ca_gui.GmWindowManager object
                      char,             # Character object
                      skill_name,       # name of skill
                      cost              # points spent on skill
                     ):
        # TODO: the following skills are augmented by stuff
        #   - axe/mace: ?
        #   - armory: good quality equipment and ?
        #   - fast draw ammo: ?
        if skill_name not in Skills.skills:
            #if skill_name in Skills.techniques:
            #    print '** "%s" is a GURPS Technique and is not yet in gcs-check.py' % skill_name
            #else:
            window_manager.error(['Need to add "%s" to ca_gcs_import' %
                skill_name])
            return 0
        skill = Skills.skills[skill_name]   # {'attr':'DX', 'diff':'E', 'default':-4}
        if skill['attr'] not in char.char['permanent']:
            window_manager.error([
                'Required attribute "%s" not supplied' % skill['attr']
                        ])
            return 0

        # Return a default value
        if cost == 0:
            if skill['default'] is None:
                window_manager.error([
                    'No default for skill "%s"' % skill_name
                            ])
                return 0
            return char.char['permanent'][skill['attr']] + skill['default']

        # Adjust cost down if someone has extra points in a skill
        while cost not in Skills.level_from_cost and cost > 1:
            cost -= 1
        if cost < 1 and not default:
            window_manager.error([
                'Cost %d invalid for skill %s' % (cost, skill_name)
                        ])
            return 0

        # Calculate the skill level
        level = Skills.level_from_cost[cost]
        level += Skills.difficulty_offset[skill['diff']]
        level += char.char['permanent'][skill['attr']]

        # Add modifiers due to equipment
        if 'equip' in skill:
            PP = pprint.PrettyPrinter(indent=3, width=150) # Do Not Remove
            for looking_for, plus in skill['equip'].iteritems():
                if Skills.is_item_in_equipment(looking_for, char.stuff):
                    level += plus
        if 'advantage' in skill:
            for looking_for, plus in skill['advantage'].iteritems():
                if looking_for in char.char['advantages']:
                    level += plus

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

class CharacterGcs(object):
    def __init__(self,
                 window_manager,    # ca_gui.GmWindowManager object (for I/O)
                 ruleset,
                 gcs_file   # filename holding GCS information
                ):
        self.__window_manager = window_manager
        self.__ruleset = ruleset
        self.__char_gcs = ET.parse(gcs_file).getroot()
        self.char = {} # JSON-like copy of character

        # Easier to build a separate 'stuff' list given containers and such.
        self.stuff = [] # [{'name':names.lower(), 'count': count, ...},... ]

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
        profile = self.__char_gcs.find('profile')
        player_name_element = profile.find('player_name')
        player_name = (None if player_name_element is None
                       else player_name_element.text)

        character_name_element = profile.find('name')
        character_name = (None if character_name_element is None
                       else character_name_element.text)

        if character_name is None:
           return 'Bob' if  player_name is None else player_name

        if player_name is None:
           return character_name

        return '%s - %s' % (character_name.lower(), player_name)

    def __add_advantage_to_gcs_list(self,
                               advantage_gcs,   # ET item
                               advantages_gcs   # {name: cost, ...
                              ):
        if advantage_gcs.tag == 'advantage_container':
            #print '<< CONTAINER'
            for contents in advantage_gcs.findall('advantage_container'):
                self.__add_advantage_to_gcs_list(contents, advantages_gcs)
            for contents in advantage_gcs.findall('advantage'):
                self.__add_advantage_to_gcs_list(contents, advantages_gcs)
            #print '>> CONTAINER'
        else:
            name = advantage_gcs.find('name')
            cost_gcs = self.__get_advantage_cost(advantage_gcs)

            for modifier in advantage_gcs.findall('modifier'):
                #modifier_name = modifier.find('name')
                #print '-modifier name: "%r"' % modifier_name.text
                #PP.pprint(modifier.attrib)

                if ('enabled' not in modifier.attrib or
                                    modifier.attrib['enabled'] != 'no'):
                    modifier_cost_element = modifier.find('cost')
                    modifier_cost = 0
                    if modifier_cost_element is not None:
                        modifier_cost_text = modifier_cost_element.text
                        if modifier_cost_text is not None:
                            cost_gcs += int(modifier_cost_text)

                    # Spell bonuses from a Lwa (if that applies)

                    spell_bonuses_raw = modifier.findall('spell_bonus')
                    for spell_bonus in spell_bonuses_raw:
                        college_name = spell_bonus.find('college_name')
                        amount = spell_bonus.find('amount')
                        self.__spell_advantages[college_name.text] = (
                                int(amount.text))
            advantages_gcs[name.text] = cost_gcs

    def __add_item_to_gcs_list(self,
                               item,        # ET item
                               stuff_gcs    # list of names of items
                              ):
        '''
        Adds entries into passed-in list for each item (and, recursively, each
        item in containers) in equipment list of a GCS character.
        '''
        new_thing = self.__ruleset.make_empty_item()
        name_element = item.find('description')
        if name_element is not None:
            # This strips all the unicode characters that aren't ASCII out --
            #   it means Atatche' case doesn't cause CURSES to crash
            new_thing['name'] = str(
                    name_element.text.encode('utf-8').decode('ascii', 'ignore'))
        count_element = item.find('quantity')
        if count_element is not None:
            new_thing['count'] = int(count_element.text)

        # Is it armor?
        dr_bonus_element = item.find('dr_bonus')
        if dr_bonus_element is not None:
            new_thing['type'].append('armor')
            dr_element = dr_bonus_element.find('amount')
            new_thing['dr'] = int(dr_element.text)

            blank_item = self.__ruleset.make_empty_armor()
            for key, value in blank_item.iteritems():
                if key not in new_thing:
                    new_thing[key] = value

        # Melee weapon?
        # NOTE: only doing melee weapon _or_ ranged weapon because the data
        #   structures aren't setup to save damage from each, separately
        # TODO: change data structures so that an item can be both a melee
        #   weapon and a ranged weapon
        if item.find('melee_weapon') is not None:
            self.__get_melee_weapon_damaage(new_thing,
                                            item)
        elif item.find('ranged_weapon') is not None:
            weapon_element = item.find('ranged_weapon')
            self.__get_ranged_weapon_damaage(new_thing,
                                             weapon_element)

            shots_element = weapon_element.find('shots')
            if shots_element is not None: # shots: T(1), or 8(3) or 8 (3)
                match = re.match(
                        '(?P<shots>T|[0-9]+) *' +
                        '\( *(?P<reload>[0-9]+)\).*',
                        shots_element.text)
                if match:
                    new_thing['ammo'] = { 'name': '*UNKNOWN*'}
                    if match.group('shots') == 'T': # Thrown
                        new_thing['ammo']['shots'] = 1
                        new_thing['ammo']['shots_left'] = 1
                    else:
                        shots = int(match.group('shots'))
                        new_thing['ammo']['shots'] = shots
                        new_thing['ammo']['shots_left'] = shots

                    new_thing['reload'] = int(match.group('reload'))

                '''
                {
                  "clip": {
                    "count": 2, "notes": "", "type": [ "misc" ], "owners": null, "name": "C Cell"
                  },
                }
                '''

            blank_item = self.__ruleset.make_empty_missile_weapon()
            for key, value in blank_item.iteritems():
                if key not in new_thing:
                    new_thing[key] = value

        # Container?
        if item.tag == 'equipment_container':
            new_thing['type'].append('container')
            new_thing['stuff'] = []
            #print '<< CONTAINER'
            for contents in item.findall('equipment_container'):
                self.__add_item_to_gcs_list(contents, new_thing['stuff'])
            for contents in item.findall('equipment'):
                self.__add_item_to_gcs_list(contents, new_thing['stuff'])
            #print '>> CONTAINER'

        # Now add to the creature
        if len(new_thing['type']) == 0:
            new_thing['type'].append('misc')

        for thing in stuff_gcs:
            if ImportCharacter.is_same_equipment_item(thing, new_thing):
                thing['count'] += new_thing['count']
                new_thing = None
                break

        if new_thing is not None:
            stuff_gcs.append(new_thing)

    def __add_skill_to_weapon(self,
                              weapon_dict,      # dict: creating this weapon
                              weapon_element    # xml.etree.ElementTree element
                              ):
        '''
        Goes through a GURPS Character Sheet description of a weapon and pulls
        out the best skill required to use it.  The result is placed in the
        JSON's description of that weapon.

        Returns nothing.
        '''
        # Skill -- find the first one with skill modifier == 0
        # TODO: modify the data structures to allow multiple skills
        still_need_a_skill = True
        for default_element in weapon_element.findall('default'):
            type_element = default_element.find('type')
            if (type_element is not None and type_element.text == 'Skill'):
                value_element = default_element.find('modifier')
                # Just take the first skill with a 0 modifier (which would be
                # a primary skill rather than a default/fall-back skill)
                if value_element is not None and int(value_element.text) == 0:
                    skill_element = default_element.find('name')
                    specialty_element = default_element.find('specialization')
                    if specialty_element is None:
                        skill = skill_element.text
                    else:
                        skill = '%s (%s)' % (skill_element.text,
                                             specialty_element.text)
                    still_need_a_skill = False
                    weapon_dict['skill'] = skill
                    break
            else:
                # This would be the default attribute (like DX) and would
                # look like:
				# <default>
			    #   <type>DX</type>
				#   <modifier>-4</modifier>
				# </default>
                # TODO: when we handle more than one skill for a weapon,
                # include handling, here
                pass

        if still_need_a_skill:
            weapon_dict['skill'] = '** UNKNOWN **'
            self.__window_manager.error([
                'No skill for "%s" in GCS file -- adding dummy' %
                weapon_dict['name']
                ])

    def __build_advantages(self):
        self.char['advantages'] = {} # name: cost
        self.__spell_advantages = {}

        ## ADVANTAGES #####
        # Checks points spent

        advantages_gcs_raw = self.__char_gcs.find('advantage_list')
        for child in advantages_gcs_raw:
            self.__add_advantage_to_gcs_list(child,
                                             self.char['advantages'])

    def __adjust_attribute(self,
                           cost_per_point,      # int:
                           advantage_name,      # char:
                           disadvantage_name,   # char:
                           adjustment_name      # char:
                           ):
        adjustment = 0

        # Add advantages and disadvantages
        if disadvantage_name in self.char['advantages']:
            adjustment += (self.char['advantages'][disadvantage_name] /
                    cost_per_point)
        if advantage_name in self.char['advantages']:
            adjustment += (self.char['advantages'][advantage_name] /
                    cost_per_point)

        # Add any adjustment
        if adjustment_name is not None:
            adjustment += self.__get_gcs_attribute(adjustment_name)
        return adjustment


    def __build_attribs(self):
        # Depends on advantages being gathered first
        #self.char['advantages'] = {} # name: cost

        self.char['permanent'] = {} # name: value

        # TODO: add move, and speed -- gcs has points spent / json
        # has result
        # JSON names are lower_case, GCS names are upper_case
        attr_names_json_from_gcs = {
                                     'ST': 'st' ,
                                     'DX': 'dx' ,
                                     'IQ': 'iq' ,
                                     'HT': 'ht',
                                   }
        self.attrs = []
        for gcs_name, json_name in attr_names_json_from_gcs.iteritems():
            self.char['permanent'][json_name] = self.__get_gcs_attribute(gcs_name)

        # HP
        self.char['permanent']['hp'] = (self.char['permanent']['st'] +
                self.__get_gcs_attribute('HP'))
        cost_per_hit_point = 2
        self.char['permanent']['hp'] += self.__adjust_attribute(
                cost_per_hit_point,
                'Extra Hit Points',
                'Fewer Hit Points',
                None)

        # FP
        self.char['permanent']['fp'] = (self.char['permanent']['ht'] +
                self.__get_gcs_attribute('FP'))
        cost_per_fatigue_point = 3
        self.char['permanent']['fp'] += self.__adjust_attribute(
                cost_per_fatigue_point,
                'Extra Fatigue Points',
                'Fewer Fatigue Points',
                None)

        # WILL
        self.char['permanent']['wi'] = self.char['permanent']['iq']
        cost_per_will_point = 5
        self.char['permanent']['wi'] += self.__adjust_attribute(
                cost_per_will_point,
                'Increased Will',
                'Decreased Will',
                'will')

        # PERCEPTION
        self.char['permanent']['per'] = self.char['permanent']['iq']
        cost_per_perception_point = 5
        self.char['permanent']['per'] += self.__adjust_attribute(
                cost_per_perception_point,
                'Increased Perception',
                'Decreased Perception',
                'perception')

        # BASIC-SPEED
        self.char['permanent']['basic-speed'] = (self.char['permanent']['ht'] +
                self.char['permanent']['dx']) / 4.0
        cost_per_basic_speed = 5
        self.char['permanent']['basic-speed'] += self.__adjust_attribute(
                cost_per_basic_speed,
                'Increased Basic Speed',
                'Decreased Basic Speed',
                'speed') * 0.25

        # BASIC-MOVE
        self.char['permanent']['basic-move'] = int(
                self.char['permanent']['basic-speed'])
        cost_per_basic_move = 5
        self.char['permanent']['basic-move'] += self.__adjust_attribute(
                cost_per_basic_move,
                'Increased Basic Move',
                'Decreased Basic Move',
                'move')

    def __build_equipment(self):
        ## EQUIPMENT #####
        # Build the equipment list up front so that skills may make use of it
        stuff_gcs = self.__char_gcs.find('equipment_list')
        if stuff_gcs is not None:
            for child in stuff_gcs:
                self.__add_item_to_gcs_list(child, self.stuff)

    def __build_skills(self):
        self.char['skills'] = {} # name: skill-level, ...
        self.char['techniques'] = [] # {"name":...,"default":[...],"value":#}

        # Checks skill cost
        # NOTE: Must run |__build_advantages| and |__build_equipment| before
        #   this because some skills are affected by advantages and equipment
        #   (a scope for a rifle, for instance).

        skills_gcs = self.__char_gcs.find('skill_list')

        for skill_gcs in skills_gcs:
            if skill_gcs.tag == 'skill':
                base_name = skill_gcs.find('name').text
                specs = []
                for specialization in skill_gcs.findall('specialization'):
                    specs.append(specialization.text)
                if len(specs) > 0:
                    name_text = '%s (%s)' % (base_name, ','.join(specs))
                else:
                    name_text = base_name

                cost_gcs_text = skill_gcs.find('points')
                cost_gcs = 0 if cost_gcs_text is None else int(cost_gcs_text.text)
                level_gcs = Skills.get_gcs_level(
                        self.__window_manager, self, base_name, cost_gcs)
                self.char['skills'][name_text] = level_gcs
            elif skill_gcs.tag == 'technique':
                base_name = skill_gcs.find('name').text
                difficulty = skill_gcs.find('difficulty').text # 'H', 'A'

                cost_gcs_text = skill_gcs.find('points')
                cost_gcs = 0 if cost_gcs_text is None else int(cost_gcs_text.text)
                plus = Skills.tech_plus_from_pts(difficulty, cost_gcs)

                default = []
                for default_gcs in skill_gcs.findall('default'):
                    base = default_gcs.find('name').text
                    if base is not None:
                        spec = default_gcs.find('specialization')
                        if spec is None:
                            default.append(base)
                        else:
                            default.append('%s (%s)' % (base, spec.text))
                    skill_base_text = default_gcs.find('modifier').text
                    skill_base = (0 if skill_base_text is None
                        else int(skill_base_text))

                technique = {
                    'name': base_name,
                    'default': default,
                    'value': plus + skill_base
                    }
                self.char['techniques'].append(technique)

    def __build_spells(self):
        ## SPELLS #####

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

        spells_gcs = self.__char_gcs.find('spell_list')

        if spells_gcs is None:
            return

        # NOTE: I only add 'spell's if the character has some.

        self.char['spells'] = [] # {'name': xx, 'skill': xx}, ...
        for child in spells_gcs:
            name = child.find('name')
            skill_gcs = self.char['permanent']['iq']

            # Spell difficulty
            difficulty = ('hard' if 'very_hard' not in child.attrib
                          else 'very_hard')

            # Points they put into this spell
            points_string = child.find('points')
            points = 1 if points_string is None else int(points_string.text)

            # College
            college = None
            if child.find('college') is not None:
                college = child.find('college').text

            if college in self.__spell_advantages:
                skill_gcs += self.__spell_advantages[college]

            # Get the skill level
            # TODO: doesn't deal with more points than 24 or 28
            for lookup in skill_add_to_iq[difficulty]:
                if points >= lookup['points']:
                    skill_gcs += lookup['add_to_iq']
                    break
            self.char['spells'].append({'name': name.text, 'skill': skill_gcs})

    def __get_advantage_cost(self,
                             advantage_gcs # element from xml.etree.ElementTree
                            ):
        cost_text_gcs = advantage_gcs.find('base_points')
        cost_gcs = 0 if cost_text_gcs is None else int(cost_text_gcs.text)
        levels_element = advantage_gcs.find('levels')
        if levels_element is not None:
            levels = int(levels_element.text)
            points_per_level_element = advantage_gcs.find('points_per_level')
            if points_per_level_element is not None:
                levels *= int(points_per_level_element.text)
                cost_gcs += levels
        return cost_gcs

    def __get_gcs_attribute(self,
                            attr_name # string
                            ):
        attr_gcs_element = self.__char_gcs.find(attr_name)
        attr_gcs_text = attr_gcs_element.text
        attr_gcs = int(attr_gcs_text)
        return attr_gcs

    def __get_melee_weapon_damaage(self,
                                   new_thing,   # dict for item
                                   item         # xml.etree equipment element
                                   ):
        new_thing['type'].append('melee weapon')
        new_thing['damage'] = {}

        for melee_weapon_element in item.findall('melee_weapon'):
            damage_element = melee_weapon_element.find('damage')

            # The damage seems to be stored in one of two ways (maybe it's
            # a version thing?):
            #   .text could be 'sw-2 cut' or 'thr imp'
            #   .attrib could be type=cut st=sw base=-2 or type=fat base=1d+1

            _st = ''
            _type = ''
            _base = ''
            if damage_element.text is not None and len(damage_element.text) > 0:
                # For strength-based damage (like a knife): sw-3 cut
                match = re.match(
                        '(?P<st>[a-zA-Z]+)' +
                        '(?P<base>[+-]?[0-9]*) *' +
                        '(?P<type>[a-zA-Z]+).*',
                        damage_element.text)
                if match is not None: # NOTE: sick stick has damage 1d+1 fat
                    _st = match.group('st')
                    _type = match.group('type')
                    _base = (0 if len(match.group('base')) == 0
                             else int(match.group('base')))
                    new_thing['damage'][_st] = {'plus': _base, 'type': _type}
                else:
                    # For non-strength-based damage (like a sick stick): 1d1+1 fat
                    match = re.match(
                            '(?P<dice>[0-9]*)(?P<d>d?)' +
                            '(?P<sign>[+-]?)(?P<plus>[0-9]*) *' +
                            '(?P<type>[a-zA-Z]*)',
                            damage_element.text)
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
                                 if (match.group('type') is None or
                                     len(match.group('type')) == 0) else
                                     match.group('type'))
                        new_thing['damage']['dice'] = {
                                'num_dice': _num_dice,
                                'plus': _plus,
                                'type': _type}

            elif 'st' in damage_element.attrib: # 1d+4 or -2 or 3d
                _st = damage_element.attrib['st']
                _base = (0 if 'base' not in damage_element.attrib else
                        int(damage_element.attrib['base']))
                _type = ('pi' # random but after-armor damage is x1
                        if 'type' not in damage_element.attrib else
                        damage_element.attrib['type'])
                new_thing['damage'][_st] = {'plus': _base, 'type': _type}

            elif 'base' in damage_element.attrib: # 1d+4 or -2 or 3d
                _type = ('pi' # random but after-armor damage is x1
                        if 'type' not in damage_element.attrib else
                        damage_element.attrib['type'])
                match = re.match(
                        '(?P<dice>[0-9]*)(?P<d>d?)' +
                        '(?P<sign>[+-]?)(?P<plus>[0-9]*) *',
                        damage_element.attrib['base'])
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

                new_thing['damage']['dice'] = {'num_dice': _num_dice,
                                               'plus': _plus,
                                               'type': _type}

            self.__add_skill_to_weapon(new_thing, melee_weapon_element)

        parry_element = melee_weapon_element.find('parry')
        if (parry_element is not None and parry_element.text is not None
                and len(parry_element.text) > 0):
            parry = int(parry_element.text)
            new_thing['parry'] = parry

        blank_item = self.__ruleset.make_empty_melee_weapon()
        for key, value in blank_item.iteritems():
            if key not in new_thing:
                new_thing[key] = value

    def __get_ranged_weapon_damaage(
            self,
            new_thing,      # dict for item
            weapon_element  # xml.etree ranged_weapon element
            ):
        new_thing['type'].append('ranged weapon')

        # Skill -- find the first one with skill modifier == 0
        # TODO: modify the data structures to allow multiple skills
        self.__add_skill_to_weapon(new_thing, weapon_element)
        bulk_element = weapon_element.find('bulk')
        if bulk_element is not None:
            new_thing['bulk'] = int(bulk_element.text)

        # accuracy x+y where |x| is the accuracy of the weapon and |y| is
        # the accuracy of the built-in scope

        accuracy_element = weapon_element.find('accuracy')
        new_thing['acc'] = 0
        if accuracy_element is not None:
            values_string = accuracy_element.text.replace('+', ' ')
            values = values_string.split()
            for value in values:
                new_thing['acc'] += int(value)

        damage_element = weapon_element.find('damage')
        if damage_element is not None:
            new_thing['damage'] = {'dice': {}}
            # ignoring armor_divisor
            if 'type' in damage_element.attrib:
                new_thing['damage']['dice']['type'] = (
                        damage_element.attrib['type'])
            damage_text = None
            if 'base' in damage_element.attrib: # 1d+4 or -2 or 3d
                damage_text = damage_element.attrib['base']
            elif damage_element.text is not None and len(damage_element.text) > 0:
                damage_text = damage_element.text

            if damage_text is not None:
                new_thing['damage']['dice']['num_dice'] = 0
                new_thing['damage']['dice']['plus'] = 0
                new_thing['damage']['dice']['type'] = '* UNKNOWN *'
                match = re.match(
                        '(?P<dice>[0-9]*)(?P<d>d?)' +
                        '(?P<sign>[+-]?)(?P<plus>[0-9]*).*',
                        damage_text)
                if match:
                    if len(match.group('dice')) > 0:
                        if len(match.group('d')) == 0:
                            window_manager.error([
                                'Problem parsing base damage "%s" for %s' %
                                (damage_text, new_thing['name'])
                                ])
                        else:
                            new_thing['damage']['dice']['num_dice'] = (
                                    int(match.group('dice')))

                    if (len(match.group('sign')) == 0 or
                            match.group('sign') == '+'):
                        sign = 1
                    elif match.group('sign') == '-':
                        sign = -1

                    if len(match.group('plus')) > 0:
                        new_thing['damage']['dice']['plus'] = (
                                int(match.group('plus')) * sign)
                else:
                    window_manager.error([
                        'Problem parsing base info "%s" for %s' %
                        (damage_text, new_thing['name'])
                        ])


class ImportCharacter(object):
    equipment_white_list_gcs = {
      "alpaca hat": 1,
      "alpaca lapel pin": 1,
      "alpaca socks": 1,
      "alpaca t-shirt": 1,
      "alpaca wool": 1,
      "antibiotic": 1,
      "antitoxin kit": 1,
      "backpack, small": 1,
      "ballistic gloves":1,
      "ballistic sunglasses":1,
      "bandages": 1,
      "belt": 1,
      "boots": 1,
      "camera": 1,
      "camera, digital, full-sized":1,
      "cigarette lighter (metal refillable)": 1,
      "cigarette lighter":1,
      "conglomerate marshal uniform": 1,
      "drop spindle": 1,
      "duct tape": 1,
      "e-rubles": 1,
      "erubles": 1,
      "electronic cuffs":1,
      "eruble": 1,
      "eyeglasses": 1,
      "fire-starter paste":1,
      "flashlight":1,
      "flashlight, heavy": 1,
      "glowstick":1,
      "holster, belt": 1,
      "holster, shoulder":1,
      "index cards":1,
      "knitting needles, pair": 1,
      "lanyard, woven steel": 1,
      "marker":1,
      "measuring laser":1,
      "medicine bag": 1,
      "messenger bag/shoulder bag": 1,
      "microfiber towel":1,
      "multi-tool with flashlight": 1,
      "multi-tool":1,
      "nitrile gloves":1,
      "plastic bags":1,
      "pocket watch":1,
      "sheath": 1,
      "sheath": 1,
      "sheep skin alpaca": 1,
      "small sheath": 1,
      "snack":1,
      "sunglasses": 1,
      "tactical belt bag": 1,
      "teddy bear": 1,
      "voice synthesizer": 1,
      "web gear":1,
      "weed": 1,
      "whistle": 1,
      "wicking undergarment": 1,
      "wooden alpaca figure": 1,
      "wool": 1,
      "wristwatch": 1,
      "yarn alpaca": 1,
    }
    def __init__(self,
                 window_manager,
                 char_json, # dict for this char directly from the JSON
                 char_gcs   # CharacterGcs object
                ):
        self.__window_manager = window_manager
        self.__char_json = char_json
        self.__char_gcs = char_gcs

    def import_data(self):
        self.__import_attribs()
        self.__import_advantages()
        self.__import_skills()
        self.__import_techniques()
        self.__import_spells()
        self.__import_equipment(squash=False)

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

    @staticmethod
    def is_same_equipment_item(existing_item,   # dict:
                               new_item         # dict:
                               ):
        '''
        Returns True if items are the same; false, otherwise.
        '''
        if existing_item['name'].lower() != new_item['name'].lower():
            return False

        if existing_item['type'] != new_item['type']:
            return False

        # We don't care if the counts, notes, or owners aren't the same

        if 'melee weapon' in existing_item['type']:
            if not ImportCharacter.is_optional_element_equal('parry',
                                                             existing_item,
                                                             new_item):
                return False

            if ('skill' not in existing_item or 'skill' not in new_item or
                    existing_item['skill'] != new_item['skill']):
                return False

        if 'ranged weapon' in existing_item['type']:
            if not ImportCharacter.is_optional_element_equal('bulk',
                                                             existing_item,
                                                             new_item):
                return False

            if not ImportCharacter.is_optional_element_equal('acc',
                                                             existing_item,
                                                             new_item):
                return False

            if not ImportCharacter.is_optional_element_equal('reload',
                                                             existing_item,
                                                             new_item):
                return False

            if ('skill' not in existing_item or 'skill' not in new_item or
                    existing_item['skill'] != new_item['skill']):
                return False

        if 'armor' in existing_item['type']:
            if existing_item['dr'] != new_item['dr']:
                return False

        if 'container' in existing_item['type']:
            new_contents = copy.deepcopy(new_item['stuff'])
            for thing in existing_item['stuff']:
                found_match = False
                for index, new_thing in enumerate(new_contents):
                    if ImportCharacter.is_same_equipment_item(thing,
                                                              new_thing):
                        new_contents.pop(index)
                        found_match = True
                        break
                if not found_match:
                    return False
            if len(new_contents) > 0:
                return False

        return True

    # Private and protected methods

    def __copy_json_equipment_list(self,
                                   equipment,  # list of items
                                   squash      # Bool: do we flatten containers
                                   ):
        '''
        Makes a deep copy of a JSON equipment list.

        This (optionally) flattens (i.e., squashes) nested containers so that
        all of the items are on the same level.  That allows one set of
        containers in GCS and a different set of containers in the JSON.

        This can copy a GCS list so long as it's been JSON-ized.
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
                # allow differnet containers in the GCS than in the JSON.
                #
                # new_item = copy.deepcopy(item)
                # new_item['stuff'] = []
                # new_list.append(new_item)
            else:
                new_item = copy.deepcopy(item)
                new_list.append(new_item)

        return new_list

    def __import_attribs(self):
        '''
        Copies the attributes from GCS to the JSON.  Puts the values in both
        the current and permanent locations.

        Cool for both import and update.

        Returns changes (array of strings describing changes made).
        '''
        attrs_to_check = [ 'st' , 'dx' , 'iq' , 'ht', 'hp', 'fp', 'wi', 'per',
                           'basic-speed', 'basic-move' ]
        changes = []
        for attr_name in attrs_to_check:
            attr_gcs = self.__char_gcs.char['permanent'][attr_name]
            attr_json = self.__char_json['permanent'][attr_name]
            if attr_gcs != attr_json:
                changes.append('%s changed from %r to %r' %
                        (attr_name, attr_json, attr_gcs))
                self.__char_json['permanent'][attr_name] = attr_gcs
                self.__char_json['current'][attr_name] = attr_gcs
        return changes

    def __import_advantages(self):
        return self.__import_heading('advantages', 'advantage')

    def __import_skills(self):
        return self.__import_heading('skills', 'skill')

    def __import_techniques(self):
        # TODO: there's probably a way to combine techniques and skills (since
        # they're both lists as opposed to the dicts examined by
        # |__import_heading|).  The challenge is that skills and techniques look
        # different under the hood so the 'do we copy' stuff needs to be
        # custom.
        changes = []
        if 'techniques' not in self.__char_json:
            self.__char_json['techniques'] = []
        techniques_json = self.__char_json['techniques']

        if 'techniques' in self.__char_gcs.char:
            techniques_gcs = copy.deepcopy(self.__char_gcs.char['techniques'])
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
                                    ', '.join(technique_json['default']))
            else:
                name = technique_json['name']

            if match_gcs is None:
                pass # TODO: take away technique, but warn
                changes.append(
                        '* NOTE: "%s" in JSON (%r) but not in GCS -- UNCHANGED' % (
                            name, technique_json['value']))
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

    def __import_spells(self):
        changes = []
        if 'spells' not in self.__char_json:
            self.__char_json['spells'] = []
        spells_json = self.__char_json['spells']

        if 'spells' in self.__char_gcs.char:
            spells_gcs = copy.deepcopy(self.__char_gcs.char['spells'])
        else:
            spells_gcs = []

        if len(spells_gcs) == 0 and len(spells_json) == 0:
            # Neither has |spells| and that's OK.
            return changes

        for spell_json in spells_json:
            match_gcs = None
            index_gcs = None
            for index, spell_gcs in enumerate(spells_gcs):
                if spell_gcs['name'] == spell_json['name']:
                    match_gcs = spell_gcs
                    index_gcs = index
                    break

            name = spell_json['name']
            if match_gcs is None:
                # TODO: take away spell but warn
                changes.append(
                        '* NOTE: "%s" in JSON (%r) but not in GCS -- UNCHANGED' % (
                            name, spell_json['skill']))
            else:
                if match_gcs['skill'] != spell_json['skill']:
                    if match_gcs['skill'] > spell_json['skill']:
                        changes.append(
                                '%s spell changed from %r to %r' %
                                (spell_json['name'], spell_json['skill'],
                                 match_gcs['skill']))
                    else:
                        changes.append(
                                '%s spell changed from %r to %r -- NOTE: value reduced' %
                                (spell_json['name'], spell_json['skill'],
                                 match_gcs['skill']))
                    spell_json['skill'] = match_gcs['skill']

                del spells_gcs[index_gcs]

        for spell_gcs in spells_gcs:
            changes.append('%s (%d) spell added' %
                           (spell_gcs['name'], spell_gcs['skill']))
            spells_json.append(spell_gcs)

        return changes

    def __import_heading(self,
                        heading,            # string: 'skills', 'advantages', etc
                        heading_singular    # string: 'skill', 'advantage', etc
                        ):
        changes = []

        if heading in self.__char_json:
            things_json = self.__char_json[heading]
        else:
            things_json = {}

        # Make the copy so we can delete matches from the list and not mess up
        # the original character.
        if heading in self.__char_gcs.char:
            things_gcs = copy.deepcopy(self.__char_gcs.char[heading])
        else:
            things_gcs = {}

        if len(things_gcs) == 0 and len(things_json) == 0:
            # Neither has |things|; everything's good
            return changes

        for name in things_json.iterkeys():
            if name not in things_gcs:
                changes.append(
                        '* NOTE: "%s" %s in JSON (%r) but not in GCS -- UNCHANGED' % (
                            name, heading_singular, things_json[name]))
                # TODO: take away from JSON, but warn
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

        for name in things_gcs.iterkeys():
            changes.append('%s (%d) %s added' %
                    (name, things_gcs[name], heading_singular))
            things_json[name] = things_gcs[name]

        return changes

    def __get_stuff_count(self,
                          item
                          ):
        return 1 if 'count' not in item else item['count']

    def __import_equipment(self,
                           squash   # Bool: whether to flatten containers
                           ):
        changes = []
        if 'stuff' not in self.__char_json:
            self.__char_json['stuff'] = []

        stuff_json = self.__copy_json_equipment_list(
                self.__char_json['stuff'], squash)
        stuff_gcs = self.__copy_json_equipment_list(
                self.__char_gcs.stuff, squash)

        PP = pprint.PrettyPrinter(indent=3, width=150) # Do Not Remove

        for item_json in stuff_json:    # item_json is {}
            match_gcs = False
            for index, item_gcs in enumerate(stuff_gcs):
                if ImportCharacter.is_same_equipment_item(item_json,
                                                          item_gcs):
                    stuff_gcs.pop(index)
                    match_gcs = True
                    break

            if not match_gcs:
                # Do a second pass looking for items that are similar
                for index, item_gcs in enumerate(stuff_gcs):
                    if item_json['name'].lower() == item_gcs['name'].lower():
                        # Make the user descide if these are the same item
                        output = []
                        output.append([{'text': ('--- GCS Item: %s ---' % item_gcs['name']),
                                        'mode': curses.A_NORMAL}])
                        string = PP.pformat(item_gcs)
                        strings = string.split('\n')
                        for string in strings:
                            output.append([{'text': string,
                                            'mode': curses.A_NORMAL}])

                        output.append([{'text': '',
                                        'mode': curses.A_NORMAL}])
                        output.append([{'text': ('--- JSON Item: %s ---' % item_json['name']),
                                        'mode': curses.A_NORMAL}])
                        string = PP.pformat(item_json)
                        strings = string.split('\n')
                        for string in strings:
                            output.append([{'text': string,
                                            'mode': curses.A_NORMAL}])

                        self.__window_manager.display_window(
                                'Examine These -- Are They The Same Item?', output)
                        request_menu = [('yes', True), ('no', False)]
                        they_are_the_same, ignore = self.__window_manager.menu(
                                'Well, Are They The Same Item?', request_menu)

                        if they_are_the_same:
                            stuff_gcs.pop(index)
                            match_gcs = True
                            break
                        else:
                            # TODO: take away item but warn
                            changes.append(
                                '* NOTE: "%s" in JSON but not in GCS -- UNCHANGED' %
                                item_json['name'])

        for item_gcs in stuff_gcs:
            name_gcs = item_gcs['name']
            if name_gcs.lower() in ImportCharacter.equipment_white_list_gcs:
                pass
            else:
                changes.append('"%s" equipment item added' % item_gcs['name'])
                self.__char_json['stuff'].append(item_gcs)
        return changes

    def __get_advantage_cost(self,
                             advantage_gcs # element from xml.etree.ElementTree
                            ):
        cost_text_gcs = advantage_gcs.find('base_points')
        cost_gcs = 0 if cost_text_gcs is None else int(cost_text_gcs.text)
        levels_element = advantage_gcs.find('levels')
        if levels_element is not None:
            levels = int(levels_element.text)
            points_per_level_element = advantage_gcs.find('points_per_level')
            if points_per_level_element is not None:
                levels *= int(points_per_level_element.text)
                cost_gcs += levels
        return cost_gcs


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
                        char_json,           # dict contains original creature
                        ruleset,             # ca_ruleset.Ruleset object
                        gcs_filename=None,   # string
                        ):
        '''
        Returns: name of the creature and the dict containing the creature
        '''
        gcs_filename = self.__extract_gcs_filename(char_json, gcs_filename)
        char_gcs = CharacterGcs(self.__window_manager, ruleset, gcs_filename)
        name = char_gcs.get_name()
        character = ImportCharacter(self.__window_manager, char_json, char_gcs)
        character.import_data()
        return name, char_json

    def update_creature(self,
                        char_json,           # dict contains original creature
                        ruleset,             # ca_ruleset.Ruleset object
                        gcs_filename=None,   # string
                        ):
        gcs_filename = self.__extract_gcs_filename(char_json, gcs_filename)
        char_gcs = CharacterGcs(self.__window_manager, ruleset, gcs_filename)
        name = char_gcs.get_name()
        character = ImportCharacter(self.__window_manager, char_json, char_gcs)
        changes = character.update_data()
        return changes

    def __extract_gcs_filename(
            self,
            char_json,           # dict contains original creature
            gcs_filename=None,   # string: in/outuser-supplied
            ):
        '''
        Gets the GCS filename.  Checks the user-supplied value, first, and
        fills with the value in char_json if the former value is None.

        Returns extracted GCS filename.
        '''

        if gcs_filename is None:
            if 'gcs-file' in char_json:
                gcs_filename = char_json['gcs-file']
            else:
                self.__window_manager.error([
                    'Need a GCS filename from which to import'])
                return None

        if ('gcs-file' not in char_json or char_json['gcs-file'] is None or
            len(char_json['gcs-file']) == 0):
            char_json['gcs-file'] = gcs_filename
        elif char_json['gcs-file'] != gcs_filename:
            char_json['gcs-file'] = gcs_filename
            self.__window_manager.display_window(
                    'NOTE',
                    [[{'text': ('Changing gcs-file from %s to %s' %
                                (char_json['gcs-file'], gcs_filename)),
                        'mode': curses.A_NORMAL}]])

        return gcs_filename
