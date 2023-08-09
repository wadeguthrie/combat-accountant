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

import ca_debug
import ca_equipment
import ca_gui
import ca_gurps_ruleset
import ca_json

# This code converts a Gurps Character Sheet (GCS v4.37.1) file to the local format.

# TODO: damage type should be 'pi' by default
# TODO: fast-draw(knife) doesn't include +1 from combat reflexes
# TODO: spells don't deal with more points than 24 or 28

class SkillsCalcs(object):
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
    skills = {}

    # SkillsCalcs:
    # To go from (cost, difficulty, attribute) to skill-level:
    #   level_from_cost[points put into spell] = base skill level
    #   difficulty_offset[difficulty] : add to base-level (Easy/Ave/Hard/VH)
    #   attribute : add to base-level

    # This is for easy skills.  More difficult skills are found using the
    # |difficulty_offset|
    level_from_cost = {1:0, 2:1, 4:2, 8:3, 12:4, 16:5, 20:6, 24:7, 28:8}
    difficulty_offset = {'E':0, 'A':-1, 'H':-2, 'VH':-3}
    # Bartender is really a professional skill

    def __init__(self,
                 window_manager):
        self.__ruleset = ca_gurps_ruleset.GurpsRuleset(window_manager)
        # load up the skills in the ruleset
        with self.__ruleset as g:
            pass
        abilities = self.__ruleset.get_creature_abilities()
        SkillsCalcs.skills = abilities['skills']

    def get_gcs_skill_level(self,
                            window_manager,   # ca_gui.GmWindowManager object
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
        debug = ca_debug.Debug(quiet=GcsImport.QUIET_SKILLS)

        if skill_name not in SkillsCalcs.skills:
            # Get the skill info from GCS
            if 'difficulty' not in skill_gcs:
                return 0
            match = re.match(
                    '(?P<attrib>[A-Za-z]+)(?P<slash>/)' +
                    '(?P<difficulty>[A-Za-z]+)',
                    skill_gcs['difficulty'])
            if match is None:
                return 0
            skill_native = {'attr': match.group('attrib').lower(),
                            'diff': match.group('difficulty').upper()}
        else:
            # {'attr':'dx', 'diff':'E', 'default':-4}
            skill_native = SkillsCalcs.skills[skill_name]

        if skill_native['attr'] not in char.char['permanent']:
            window_manager.error([
                'Required attribute "%s" not supplied' % skill_native['attr']
                        ])
            return 0

        # Return a default value if the player didn't buy this skill.
        if cost == 0:
            debug.print('** DEFAULT **')
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
        for cost_in_table in SkillsCalcs.level_from_cost.keys():
            if highest_cost < cost_in_table:
                highest_cost = cost_in_table
                highest_level = SkillsCalcs.level_from_cost[highest_cost]

        while cost > highest_cost:
            highest_cost += 4
            highest_level += 1
            SkillsCalcs.level_from_cost[highest_cost] = highest_level

        # Adjust cost down if someone has extra points (more spent points
        # than required for one skill level but not enough to get to the next
        # one) in a skill
        while cost not in SkillsCalcs.level_from_cost and cost > 1:
            cost -= 1
        if cost < 1 and not default:
            window_manager.error([
                'Cost %d invalid for skill %s' % (cost, skill_name)
                        ])
            return 0

        # Calculate the skill level
        # NOTE: don't use "calc" entry in the GCS sheet because they may
        #   include a laser sight for 'beam weapons' skill -- this code applies
        #   that the laser sight benefit later.
        level = char.char['permanent'][skill_native['attr']]
        debug.print('  %s = %d' % (skill_native['attr'], level)) # TODO: remove
        level += SkillsCalcs.level_from_cost[cost]
        level += SkillsCalcs.difficulty_offset[skill_native['diff']]
        debug.print('  %s (paid %d) = %d' % (skill_native['diff'],
                                             cost,
                                             level))

        # Add modifiers due to equipment
        plus = self.__get_equipment_bonuses(char.stuff, 'skill', skill_name)
        level += plus
        debug.print('  equipment +%d = %d' % (plus, level)) # TODO: remove

        #if 'equip' in skill_native:
        #    PP = pprint.PrettyPrinter(indent=3, width=150) # Do Not Remove
        #    for looking_for, plus in skill_native['equip'].items():
        #        if SkillsCalcs.is_item_in_equipment(looking_for, char.stuff):
        #            level += plus
        if 'advantage' in skill_native:
            for looking_for, plus in skill_native['advantage'].items():
                if looking_for in char.char['advantages']:
                    level += plus
        debug.print('  after advantages: %d' % level) # TODO: remove

        return level

    '''
    TODO: get skill
			"features": []

                {
					"type": "skill_bonus",
					"amount": 1,
					"selection_type": "skills_with_name",
					"name": {
						"compare": "starts_with",
						"qualifier": "navigation"
					}
				}
            	{
					"type": "skill_bonus",
					"amount": 2,
					"selection_type": "skills_with_name",
					"name": {
						"compare": "is",
						"qualifier": "First Aid"
					}
				}
                {
					"type": "skill_bonus",
					"amount": 1,
					"selection_type": "skills_with_name",
					"name": {
						"compare": "is",
						"qualifier": "Disguise"
					}
				}
				{ "type": "attribute_bonus", "amount": 3, "attribute": "dodge" },
				{ "type": "attribute_bonus", "amount": 3, "attribute": "parry" },
				{ "type": "attribute_bonus", "amount": 3, "attribute": "block" }
				{
					"type": "skill_bonus",
					"amount": -5,
					"selection_type": "skills_with_name",
					"name": {
						"compare": "is",
						"qualifier": "Escape"
					}
				}
				{
					"type": "skill_bonus",
					"amount": 1,
					"selection_type": "skills_with_name",
					"name": {
						"compare": "starts_with",
						"qualifier": "navigation"
					}
                }

                ---

                'bonus' : [{'type': 'skill' / 'attribute',
                            'amount': <number>,
                            'name': '<regex>'}, ...

    '''
    def __get_equipment_bonuses(self,
                                equipment,   # list of dict, maybe w/containers
                                type_name, # 'attribute' or 'skill'
                                skill_name,
                                #must_be_in_use=False # weapons or armor
                                ):
        # These equipment bonuses are handled differently.  Instead of giving,
        # for example, bonuses on all beam weapons when you have a laser
        # sight, this program requires that you attach a laser sight to a
        # specific beam weapon in order to get the plus.
        dont_get_bonuses_for_these_skills = ['Beam Weapons (Pistol)',
                                             'Beam Weapons (Rifle)'
                                             ]
        if skill_name in dont_get_bonuses_for_these_skills:
            return 0

        # Figure out what items are currently in use.  This is for currently
        # held weapons and armor.

        # NOTE: this is probably not used when importing characters.

        #in_use_items = []

        #armor_index_list = character.get_current_armor_indexes()
        #armor_list = character.get_items_from_indexes(armor_index_list)

        #for armor_in_use in armor_list:
        #    in_use_items.append(armor_in_use)
        #weapons = character.get_current_weapons()

        #for weapon_in_use in weapons:
        #    if weapon_in_use is None:
        #        continue
        #    in_use_items.append(weapon_in_use.details)

        # Look through each item of equipment for bonuses

        #'bonus' : [{'type': 'skill' / 'attribute',
        #            'amount': <number>,
        #            'name': '<regex>'}, ...

        total_bonus = 0
        for item in equipment:
            #if must_be_in_use and item not in in_use_items:
            #    continue

            if 'bonus' in item:
                for bonus in item['bonus']:
                    if bonus['type'] != type_name:
                        continue
                    # NOTE:  bonus['name'] is a regex
                    if re.match(bonus['name'], skill_name, re.IGNORECASE):
                        total_bonus += bonus['amount']

            if 'stuff' in item:
                total_bonus += self.__get_equipment_bonuses(
                        item['stuff'], type_name, skill_name)

        return total_bonus

    #@staticmethod
    #def is_item_in_equipment(looking_for, # string
    #                         equipment    # list of dict, maybe w/containers
    #                         ):
    #    looking_for_lower = looking_for.lower()
    #    for item in equipment:
    #        if looking_for_lower == item['name'].lower():
    #            return True
    #        if 'container' in item['type']:
    #            result = SkillsCalcs.is_item_in_equipment(looking_for,
    #                                                 item['stuff'])
    #            if result == True:
    #                return result
    #    return False

    @staticmethod
    def tech_plus_from_pts(difficulty, # 'H' or 'A'
                           points   # int
                           ):
        table = SkillsCalcs.tech_plus_from_pts_table[difficulty.upper()]
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

        debug = ca_debug.Debug(quiet=GcsImport.QUIET_IMPORT)
        debug.header1('FromGcs: %s' % gcs_file)
        debug.pprint(self.__gcs_data)

        self.__window_manager = window_manager
        self.__ruleset = ruleset
        self.char = {} # JSON-like copy of character

        # Easier to build a separate 'stuff' list given containers and such.
        self.stuff = [] # [{'name':names.lower(), 'count': count, ...},... ]

    def __map_attrib(self,
                     attrib   # string
                     ):
        attrib_gcs_to_native = {
                'will' : 'wi'
                }
        if attrib not in attrib_gcs_to_native:
            return attrib
        return attrib_gcs_to_native[attrib]

    def build_advantage_list(
            self,
            window_manager, # ca_gui.GmWindowManager obj (errors)
            ):
        native_advantages = {}

        if 'rows' not in self.__gcs_data:
            window_manager.error(['No "rows" element in file'])
            return native_skills

        for gcs_advantage in self.__gcs_data['rows']:
            if gcs_advantage['type'] != 'advantage':
                continue
            if 'name' not in gcs_advantage:
                continue
            name = gcs_advantage['name']
            if name in gcs_advantage:
                window_manager.error([
                    'Advantage %s in %s multiple times' % (name,
                                                           gcs_filename)])
                continue

            native_advantage = { }
            if 'points_per_level' in gcs_advantage:
                native_advantage['ask'] = 'string'
            if 'base_points' in gcs_advantage:
                native_advantage['value'] = gcs_advantage['base_points']
            if ('modifiers' in gcs_advantage or
                    'points_per_level' in gcs_advantage):
                native_advantage['ask'] = 'number'


            notes = ''
            if 'reference' in gcs_advantage:
                notes = notes + gcs_advantage['reference']

            if len(notes) > 0:
                native_advantage['notes'] = notes

            native_advantages[name] = native_advantage

        return native_advantages

    def build_equipment_list(
            self,
            window_manager, # ca_gui.GmWindowManager obj (errors)
            ):
        native_equipment = []

        if 'rows' not in self.__gcs_data:
            window_manager.error(['No "rows" element in file'])
            return native_skills

        for item in self.__gcs_data['rows']:
            if (item['type'] != 'equipment' and
                    item['type'] != 'equipment_container'):
                continue

            self.__convert_and_store_equipment_item(item, # source
                                                    native_equipment, # dest
                                                    'TOP LEVEL')
        return native_equipment

    def build_skill_list(self,
                         window_manager, # ca_gui.GmWindowManager obj (errors)
                         ):
        native_skills = {}
        if 'rows' not in self.__gcs_data:
            window_manager.error(['No "rows" element in file'])
            return native_skills

        for gcs_skill in self.__gcs_data['rows']:
            if gcs_skill['type'] != 'skill':
                continue
            if 'name' not in gcs_skill:
                continue
            name = gcs_skill['name']
            if 'specialization' in gcs_skill:
                name = '%s (%s)' % (name, gcs_skill['specialization'])
            if name in native_skills:
                window_manager.error([
                    'Skill %s in input file multiple times' % name])
                continue

            native_skill = {
                    'ask': 'number',
                    'attr': 'iq',
                    'diff': 'E',
                    'default': None,
                    # 'equip': { 'first aid kit': 1 } # optional
                    # 'advantage': { xxx } # optional
                    }
            if 'difficulty' in gcs_skill:
                # attribute / difficulty
                match = re.match(
                        '(?P<attrib>[A-Za-z]+)(?P<slash>/)' +
                        '(?P<difficulty>[A-Za-z]+)',
                        gcs_skill['difficulty'])
                if match is not None:
                    native_skill['attr'] = self.__map_attrib(
                                match.group('attrib').lower())
                    native_skill['diff'] = match.group('difficulty').upper()

            if 'reference' in gcs_skill:
                native_skill['notes'] = gcs_skill['reference']

            if 'defaults' in gcs_skill:
                for default in gcs_skill['defaults']:
                    if 'type' in default:
                        default_type = self.__map_attrib(default['type'])
                        if default_type == native_skill['attr']:
                            native_skill['default'] = default['modifier']
                            break

            native_skills[name] = native_skill

        return native_skills

    def build_spell_list(self,
                         window_manager, # ca_gui.GmWindowManager obj (errors)
                         ):
        native_spells = {}

        if 'rows' not in self.__gcs_data:
            window_manager.error(['No "rows" element in file'])
            return native_skills

        for gcs_spell in self.__gcs_data['rows']:
            if gcs_spell['type'] != 'spell':
                continue
            if 'name' not in gcs_spell:
                continue
            name = gcs_spell['name']
            if name in native_spells:
                window_manager.error([
                    'Spell %s in %s multiple times' % (name,
                                                       gcs_filename)])
                continue

            native_spell = {
                    'range': 'regular',
                    'cost': None,
                    'maintain': None,
                    'casting time': None,
                    'duration': None,
                    'notes': '',
                    'save': [] # not in GCS
                    }
            if 'difficulty' in gcs_spell:
                native_spell['difficulty'] = gcs_spell['difficulty'] # "IQ/H"
            if 'spell_class' in gcs_spell:
                gcs_range = gcs_spell['spell_class'].lower()
                # Used in code: block, missile, area, melee
                if gcs_range in ['blocking', 'regular/blocking',
                        'blocking/special', 'regular blocking']:
                    native_spell['range'] = 'block'
                elif gcs_range in ['missile', 'missile/special']:
                    native_spell['range'] = 'missile'
                elif gcs_range in ['area', 'area/info', 'regular/area',
                        'info/area', 'special/area']:
                    native_spell['range'] = 'area'
                elif gcs_range in ['melee']:
                    native_spell['range'] = 'melee'
                else: # regular, enchantment, info, special
                    native_spell['range'] = gcs_range

            if 'casting_cost' in gcs_spell:
                match = re.match('^ *(?P<cost>[0-9]+) *(?P<extra>([Mm]inimum)?) *$',
                     gcs_spell['casting_cost'])
                if match is None:
                    native_spell['cost'] = (0
                            if gcs_spell['casting_cost'] == 'None' # ironic
                            else None) # special / ask
                else:
                    try:
                        # for area spells, this is the base cost
                        native_spell['cost'] = int(match.group('cost'))
                    except ValueError:
                        native_spell['cost'] = None # special / ask
            if 'maintenance_cost' in gcs_spell:
                try:
                    native_spell['maintain'] = int(gcs_spell['maintenance_cost'])
                except ValueError:
                    native_spell['maintain'] = None # Can't be maintained
            if 'casting_time' in gcs_spell:
                native_spell['casting time'] = FromGcs.get_seconds_from_time_string(
                        gcs_spell['casting_time'])
            if 'duration' in gcs_spell:
                # None = special
                # 0 = instantaneous / permanent
                if gcs_spell['duration'] in ['Permanent', 'Instant', '-']:
                    native_spell['duration'] = 0
                else:
                    # returns None if no match
                    native_spell['duration'] = FromGcs.get_seconds_from_time_string(
                            gcs_spell['duration'])


            notes = ''
            if 'reference' in gcs_spell:
                notes = notes + gcs_spell['reference']

            if (native_spell['casting time'] is None and
                    gcs_spell['casting_time'] != '-'):
                '; '.join([notes,
                          gcs_spell['casting_time']])
            if (native_spell['duration'] is None and
                    gcs_spell['duration'] != '-'):
                '; '.join([notes,
                           gcs_spell['duration']])
            if len(notes) > 0:
                native_spell['notes'] = notes

            native_spells[name] = native_spell

        return native_spells

    @staticmethod
    def get_seconds_from_time_string(string):
        if string is None:
            return None

        if string.lower() == 'instant':
            return 0

        match = re.match('^ *(?P<count>[0-9]+) *(?P<units>[A-Za-z]+) *$',
                         string)

        if match is None:
            # This can be anything from '-' (which means, depending on the
            # spell, 'instantaneous' or 'ask') to sec=cost, 1 min/pt, 1-3
            # secs, min=cost, Varies, or 2/4/6 sec.  In all these cases, we
            # just want to ask the caster.
            return None

        multiplier = None
        if (match.group('units').lower() == 'sec' or
                match.group('units').lower() == 'secs'):
            multiplier = 1
        elif (match.group('units').lower() == 'min' or
                match.group('units').lower() == 'mins'):
            multiplier = 60
        elif (match.group('units').lower() == 'hr' or
                match.group('units').lower() == 'hrs' or
                match.group('units').lower() == 'hour' or
                match.group('units').lower() == 'hours'):
            multiplier = 3600
        elif (match.group('units').lower() == 'day' or
                match.group('units').lower() == 'days'):
            multiplier = 86400
        elif (match.group('units').lower() == 'week' or
                match.group('units').lower() == 'weeks'):
            multiplier = 604800

        if multiplier is None:
            return None

        result = int(match.group('count')) * multiplier
        return result

    def convert_character(self):
        '''
        Converts a GCS-formatted character to our native format.
        '''
        # Alphabetical (which works out for required order of execution).
        # Dependencies are as follows:
        #   advantages <- attribs
        #   advantages <- skills
        #   equipment <- skills
        #   advantages <- spells

        debug = ca_debug.Debug(quiet=GcsImport.QUIET_IMPORT)
        name = self.get_name()
        debug.header1('convert_character: %s' % name)

        self.__convert_advantages()
        self.__convert_attribs()
        self.__convert_equipment()
        self.__convert_skills()
        self.__convert_spells()

    def build_skill_descriptions(self):
        '''
        Builds a local equipment list from the JSON extracted from a GCS
        .eqp file.
        '''
        skills, techniques = self.__build_skill_descriptions('rows')
        return skills, techniques


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
        debug = ca_debug.Debug(quiet=GcsImport.QUIET_ADVANTAGES)
        debug.header3('__add_advantage_to_gcs_list: %s' % advantage_gcs['name'])

        debug.print('OK so far')
        if advantage_gcs['type'] == 'trait_container':
            debug.print('CONTAINER')
            #print '<< CONTAINER'
            for advantage in advantage_gcs['children']:
                self.__add_advantage_to_gcs_list(advantage, advantages_gcs)
            #print '>> CONTAINER'
        else:
            debug.print('regular advantage (not container)')
            name = advantage_gcs['name']
            cost_gcs = self.__get_advantage_cost(advantage_gcs)
            debug.print('cost: %r' % cost_gcs)

            #if 'tags' not in advantage_gcs:
            #    return
            #if ('Disadvantage' not in advantage_gcs['tags'] and
            #        'Advantage' not in advantage_gcs['tags'] and
            #        'Quirk' not in advantage_gcs['tags'] and
            #        'Perk' not in advantage_gcs['tags']):
            #    return

            if 'modifiers' in advantage_gcs:
                for modifier in advantage_gcs['modifiers']:
                    if 'disabled' in modifier and modifier['disabled']:
                        debug.print('** DISABLED: %s **' % name)
                        continue

                    if 'calc' in advantage_gcs and 'points' in advantage_gcs['calc']:
                        pass # Already calculated all modifiers
                    elif 'cost' in modifier:
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

                        debug.print('modified cost: %r' % cost_gcs)

                    # Spell bonuses from a Lwa (if that applies)

                    if 'features' in modifier:
                        for feature in modifier['features']:
                            if feature['type'] == 'spell_bonus':
                                if feature['match'] == 'all_colleges':
                                    self.__spell_advantage_global += (
                                            feature['amount'])
                                else:
                                    college = feature['name']['qualifier']
                                    amount = feature['amount']
                                    self.__spell_advantages[college] = amount

            advantages_gcs[name] = cost_gcs
            debug.print('DONE: advantage[%s] = %r' % (name, cost_gcs))

    def __convert_and_store_equipment_item(
            self,
            item,           # source (dict) equipment item in GCS format
            stuff_gcs,      # dest container (list) of native items (dict)
            container_name  # string (for debugging)
            ):
        '''
        Converts a single item of equipment from  GCS format to our native
        format.  If the item is a container, this routine calls itself
        recursively for the items in the container.

        Native-formatted results are added to the passed-in list.
        '''
        debug = ca_debug.Debug(quiet=GcsImport.QUIET_EQUIPMENT)

        new_thing = self.__ruleset.make_empty_item()
        #if ('features' in item and 'type' in item['features'][0] and
        #        'amount' in item['features'][0]):
        #    name = '%s (%s: %d)' % (item['description'],
        #                            item['features'][0]['type'],
        #                            item['features'][0]['amount'])
        #else:
        name = item['description']
        if name is not None:
            new_thing['name'] = name

        debug.header2('__convert_and_store_equipment_item: %r' % name)
        debug.pprint(item)

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
                    elif feature['type'] == 'skill_bonus':
                        #{
                        #    "type": "skill_bonus",
                        #    "amount": 1,
                        #    "selection_type": "skills_with_name",
                        #    "name": {
                        #        "compare": "starts_with",
                        #        "qualifier": "navigation"
                        #    }
                        #}

                        #'bonus' : [{'type': 'skill' / 'attribute',
                        #        'amount': <number>,
                        #        'name': '<regex>'}, ...
                        if 'bonus' not in new_thing:
                            new_thing['bonus'] = []
                        name = feature['name']['qualifier']
                        compare = feature['name']['compare']
                        name_regex = (('%s.*' % name)
                                if compare == 'starts_with' else name)
                        bonus = {'type': 'skill',
                                 'amount': feature['amount'],
                                 'name': name_regex}
                        new_thing['bonus'].append(bonus)

                    # The following is only for shields and cloaks, does not
                    # apply to firearms, and only from the front or side --
                    # not a priority since there're no mechanics for most of
                    # this.
                    #
                    #elif feature['type'] == 'attribute_bonus':
				    #    # { "type": "attribute_bonus", "amount": 3, "attribute": "dodge" },
                    #    # TODO: fill this in

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
                self.__convert_and_store_equipment_item(contents,
                                                        new_thing['stuff'],
                                                        name)

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
        debug = ca_debug.Debug(quiet=GcsImport.QUIET_EQUIPMENT)
        debug.header4('__add_skill_to_weapon')

        weapon_dest['type'][mode]['skill'] = {}

        # Skill -- find the first one with skill modifier == 0
        still_need_a_skill = True
        # 'default' elements each describe a single skill (or attribute) that
        # can be used to use this item.  There're typically several as in:
        # knife (+0), sword (-2), DX (-4)

        if 'defaults' not in weapon_source:
            return

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
				#   {
                #       "type": "dx",
                #       "modifier": -4
				#   }

                if ('permanent' not in self.char or
                        skill.lower() in self.char['permanent']):
                    # Then we're talking 'dx' or something as a default
                    weapon_dest['type'][mode]['skill'][skill.lower()] = modifier
                    still_need_a_skill = False

        if still_need_a_skill:
            weapon_dest['type'][mode]['skill'][
                    ca_equipment.Equipment.UNKNOWN_STRING] = 0
            self.__window_manager.error([
                'No skill for "%s" in GCS file -- adding dummy' %
                weapon_dest['name']
                ])

    def __convert_advantages(self):
        '''
        Converts GCS-formatted advantages that are owned by a character to our
        native format.
        '''
        self.char['advantages'] = {} # name: cost
        self.__spell_advantages = {}

        ## ADVANTAGES #####
        # Checks points spent

        debug = ca_debug.Debug(quiet=GcsImport.QUIET_ADVANTAGES)

        advantages = self.__gcs_data['traits']

        debug.header2('__convert_advantages: gcs')
        debug.pprint(advantages)

        self.__spell_advantage_global = 0
        for advantage in advantages:
            self.__add_advantage_to_gcs_list(advantage,
                                             self.char['advantages'])

        debug.header2('__convert_advantages: native')
        debug.pprint(self.char['advantages'])

    def __convert_attribs(self):
        '''
        Converts GCS-formatted attributes that are owned by a character to our
        native format.
        '''
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

    def __convert_equipment(self,
                            heading='equipment' # where in file is equipment found
                            ):
        '''
        Converts GCS-formatted equipment that is owned by a character into our
        native format.
        '''
        if heading not in self.__gcs_data:
            return
        for item in self.__gcs_data[heading]:
            self.__convert_and_store_equipment_item(item,
                                                    self.stuff,
                                                    'TOP LEVEL')

    def __build_skill_descriptions(self):
        skills_result = {} # name: skill-level, ...
        techniques_result = [] # {"name":...,"default":[...],"value":#}

        if 'skills' not in self.__gcs_data:
            return skills_result, techniques_result

        skills = SkillsCalcs(self.__window_manager)

        for skill_gcs in self.__gcs_data['skills']:
            base_name = skill_gcs['name']

            if 'type' not in skill_gcs:
                pass

            elif skill_gcs['type'] == 'skill':
                '''
                {
                    "type": "skill",
                    "id": "c699cfb8-f28b-4996-a990-66ab6a1fd3cd",
                    "name": "Guns",
                    "reference": "B198",
                    "specialization": "Grenade Launcher",
                    "tech_level": "",
                    "difficulty": "dx/e",
                    "points": 1,
                    "defaults": [
                        { "type": "dx", "modifier": -4 },
                        { "type": "skill", "name": "Guns", "modifier": -4 }
                    ],
                    "categories": [
                        "Combat/Weapon",
                        "Ranged Combat"
                    ]
                },

                "Beam Weapons": {"ask": "number",
                    "attr":"dx", "diff":"E", "default":-4,
                    "equip": {"laser sight": 1}},
                '''
                skill = {'ask': 'number'}

                # Name
                if ('specialization' in skill_gcs and
                        len(skill_gcs['specialization']) > 0):
                    name_text = '%s (%s)' % (skill_gcs['name'],
                                             skill_gcs['specialization'])
                else:
                    name_text = skill_gcs['name']

                # attribute / difficulty
                match = re.match(
                        '(?P<attrib>[A-Za-z]+)(?P<slash>/)' +
                        '(?P<difficulty>[A-Za-z]+)',
                        skill_gcs['difficulty'])
                if match is None:
                    continue

                skill['attr'] = match.group('attrib').lower()
                skill['diff'] = match.group('difficulty').upper()

                # default
                if 'defaults' not in skill_gcs:
                    skill['default'] = None
                else:
                    for default in skill_gcs['defaults']:
                        if default['type'] == skill['attr']:
                            skill['default'] = int(default['modifier'])
                            break

                # equipment / advantages -- not in GCS skill file

                skills_result[name_text] = skill

            #elif skill_gcs['type'] == 'technique':
            '''
                GCS entry:
                {
                    "type": "technique",
                    "id": "91f80f7e-4757-470e-adab-5b022b920b1d",
                    "name": "Off-Hand Weapon Training",
                    "reference": "B232",
                    "difficulty": "h",
                    "points": 2,
                    "limit": 0,
                    "default": {
                        "type": "skill",
                        "name": "Broadsword",
                        "modifier": -4
                    },
                    "categories": [
                        "Combat/Weapon",
                        "Melee Combat",
                        "Technique"
                    ]
                }

                CA entry:
                "Off-Hand Weapon Training (Knife)": {"ask": "number"},
            '''
            #    # print('\n=== Technique: %s ===' % base_name) # TODO: remove
            #    difficulty = skill_gcs['difficulty'] # 'H', 'A'
            #    cost_gcs = 0 if 'points' not in skill_gcs else skill_gcs['points']
            #    plus = SkillsCalcs.tech_plus_from_pts(difficulty, cost_gcs) ###################33

            #    default = skill_gcs['default']['name']
            #    if 'specialization' in skill_gcs['default']:
            #        default += (' (%s)' % skill_gcs['default']['specialization'])
            #    skill_base = (0 if 'modifier' not in skill_gcs['default'] else ####################
            #                  skill_gcs['default']['modifier'])
            #    # print('based on %s = %d+%d' % (default, plus, skill_base)) # TODO: remove

            #    technique = {
            #        'name': base_name,
            #        'default': default,
            #        'value': plus + skill_base
            #        }
            #    techniques_result.append(technique)
            return skills_result, techniques_result

    def __convert_skills(self):
        '''
        Converts GCS-formatted skills and techniques that are owned by a
        character into our local format.
        '''
        self.char['skills'] = {} # name: skill-level, ...
        self.char['techniques'] = [] # {"name":...,"default":[...],"value":#}

        # Checks skill cost
        # NOTE: Must run |__convert_attribs|, |__convert_advantages|, and
        #   |__convert_equipment| before |__convert_skills| because skills depend
        #   on attributes, some skills are affected by advantages, and
        #   equipment (a scope for a rifle, for instance).

        debug = ca_debug.Debug(quiet=GcsImport.QUIET_SKILLS)
        debug.header2('__convert_skills: gcs')

        if 'skills' not in self.__gcs_data:
            return

        skills = SkillsCalcs(self.__window_manager)

        for skill_gcs in self.__gcs_data['skills']:
            base_name = skill_gcs['name']

            debug.header3(base_name) # TODO: remove

            if 'type' not in skill_gcs:
                pass

            elif skill_gcs['type'] == 'skill':
                if ('specialization' in skill_gcs and
                        len(skill_gcs['specialization']) > 0):
                    name_text = '%s (%s)' % (skill_gcs['name'],
                                             skill_gcs['specialization'])
                    debug.print(' %s' % name_text) # TODO: remove
                else:
                    name_text = skill_gcs['name']

                cost_gcs = 0 if 'points' not in skill_gcs else skill_gcs['points']

                level_gcs = skills.get_gcs_skill_level(
                        self.__window_manager, self, skill_gcs, name_text, cost_gcs)
                self.char['skills'][name_text] = level_gcs
            elif skill_gcs['type'] == 'technique':
                debug.print('\n=== Technique: %s ===' % base_name) # TODO: remove
                difficulty = skill_gcs['difficulty'] # 'H', 'A'
                cost_gcs = 0 if 'points' not in skill_gcs else skill_gcs['points']
                plus = SkillsCalcs.tech_plus_from_pts(difficulty, cost_gcs) ###################33

                default = skill_gcs['default']['name']
                if 'specialization' in skill_gcs['default']:
                    default += (' (%s)' % skill_gcs['default']['specialization'])
                skill_base = (0 if 'modifier' not in skill_gcs['default'] else ####################
                              skill_gcs['default']['modifier'])
                debug.print('based on %s = %d+%d' % (default, plus, skill_base)) # TODO: remove

                technique = {
                    'name': base_name,
                    'default': default,
                    'value': plus + skill_base
                    }
                self.char['techniques'].append(technique)

    def __convert_spells(self):
        '''
        Converts GCS-formatted spells that are owned by a character into our
        local format.
        '''
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

        debug = ca_debug.Debug(quiet=GcsImport.QUIET_SPELLS)

        if ('spells' not in self.__gcs_data or
                len(self.__gcs_data['spells']) == 0):
            return

        debug.header2('__convert_spells')

        # NOTE: Only add 'spell's if the character has some.

        self.char['spells'] = [] # {'name': xx, 'skill': xx}, ...
        for spell_gcs in self.__gcs_data['spells']:
            name = spell_gcs['name']
            debug.header3(name)
            skill_gcs = self.char['permanent']['iq']
            debug.print('start w/iq: %d' % skill_gcs)

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
            debug.print('difficulty: %s' % difficulty)

            # Points they need put into this spell to cast
            # match = re.match('^(?P<cost>[0-9]+)$', spell_gcs['casting_cost'])
            # TODO (now_: this should be 'None' or 0
            #points = 1 if match is None else int(match.group('cost'))
            points = 1 if 'points' not in spell_gcs else spell_gcs['points']

            # College
            colleges = [] if 'college' not in spell_gcs else spell_gcs['college']
            best_plus = 0
            debug.print('spell advantages for colleges:')
            debug.pprint(self.__spell_advantages)
            debug.print('THIS spell is in the following colleges:')
            debug.pprint(colleges)
            for college in colleges:
                if college in self.__spell_advantages:
                    if best_plus < self.__spell_advantages[college]:
                        best_plus = self.__spell_advantages[college]

            skill_gcs += best_plus
            skill_gcs += self.__spell_advantage_global

            debug.print('adding plus: %d and lwa: %d to get %d' %
                    (best_plus, self.__spell_advantage_global, skill_gcs))

            # Get the skill level
            # TODO (now): doesn't deal with more points than 24 or 28
            for lookup in skill_add_to_iq[difficulty]:
                if points >= lookup['points']:
                    skill_gcs += lookup['add_to_iq']
                    debug.print('adding skill: %d' % lookup['add_to_iq'])
                    break

            debug.print('to get: %d' % skill_gcs)
            self.char['spells'].append({'name': name, 'skill': skill_gcs})

    def __get_advantage_cost(self,
                             advantage_gcs # advantage dict
                            ):

        if 'calc' in advantage_gcs and 'points' in advantage_gcs['calc']:
            return advantage_gcs['calc']['points']

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
            name,   # string: for error messages, really
            weapon  # dict: the whole weapon
            ):
        _st = ''
        _type = ''
        _base = ''
        damage = {}

        # 'damage': {'base': '-1', 'st': 'sw', 'type': 'imp'},

        match = None
        if 'base' in weapon['damage']:
            # "damage": { "type": "HP", "base": "1d+4" }, # blaster
            # "damage": { "type": "fat", "base": "1d+1" }, # sick stick
            # "damage": { "type": "FP", "base": "1d+3" }, # zip tazer
            # "damage": { "type": "", "base": "2d+4" }, # laser pistol
            # "damage": { "type": "burn", "base": "3d", "armor_divisor": 2 }, # lasor rifle
            # "damage": { "type": "", "base": "3d", "armor_divisor": 3 }, # laser rifle
            #
            # "damage": { "type": "cut", "st": "sw", "base": "1d"},
            #
            # {"damage": {"dice":{"plus":1,"num_dice":1,"type":"fat"}}}
            match = re.match(
                    '(?P<dice>[0-9]*)(?P<d>d?)' +
                    '(?P<sign>[+-]?)(?P<plus>[0-9]*)',
                    weapon['damage']['base'])

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
                there_is_a_d = (match is not None and
                        match.group('d') is not None and
                        len(match.group('d')) > 0)

                # "damage": { "type": "cut", "st": "sw", "base": "1d"}
                if there_is_a_d:
                    # Not the usual case
                    # TODO: support strength + dice of damage.  It's easy,
                    # here, but it's a little harder in ca_gurps_ruleset.
                    # Such as in:
                    # "damage": { "type": "cut", "st": "sw", "base": "1d"},
                    self.__window_manager.error([
                        'Not currently supporting strength + dice damage',
                        'together.  Weapon %s will be malformed' % name])
                    _base = (0 if 'base' not in weapon['damage']
                             else int(match.group('dice')))
                else:
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
                   'new_stat': 'st',
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
        debug = ca_debug.Debug(quiet=GcsImport.QUIET_EQUIPMENT)
        debug.header3('__get_melee_weapon')
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
            damage = self.__get_damage(new_thing['name'], weapon)
            usage = 'Swung' if ('usage' not in weapon or
                                len(weapon['usage']) == 0) else weapon['usage']
            item_type = ('unknown weapon' if usage not in type_from_usage else
                         type_from_usage[usage])
            new_thing['type'][item_type] = {'damage': damage}

            self.__add_skill_to_weapon(new_thing, item_type, weapon)

            if ('parry' in weapon and len(weapon['parry']) > 0 and
                    weapon['parry'].lower() != 'no'):

                match = re.match(
                        '(?P<value>[+-]?[0-9]*)' +
                        '(?P<modifier>[a-zA-Z]*)',
                        weapon['parry'])
                # Modifier would be 'F' (meaning fencing weapon) or 'U' meaning
                # unbalenced).  See B269.
                # TODO: do something with the modifier here and in the fighting
                # rules.
                if match is not None:
                    new_thing['parry'] = int(match.group('value'))

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
            damage = self.__get_damage(new_thing['name'], weapon)

            new_thing['type']['ranged weapon'] = {'damage': damage}
            self.__add_skill_to_weapon(new_thing, 'ranged weapon', weapon)

            if 'bulk' in weapon:
                int_value = 0 if weapon['bulk'] == '-' else int(weapon['bulk'])
                new_thing['bulk'] = int_value

            # accuracy x+y where |x| is the accuracy of the weapon and |y| is
            # the accuracy of the built-in scope

            new_thing['acc'] = 0
            if 'accuracy' in weapon and len(weapon['accuracy']) > 0:
                accuracy_text = weapon['accuracy']
                accuracy_text = accuracy_text.replace('+', ' ')
                values = accuracy_text.split()
                for value in values:
                    int_value = 0 if value == '-' else int(value)
                    new_thing['acc'] += int_value

            # shots: T(1), or 8(3) or 8 (3)

            if 'shots' in weapon and len(weapon['shots']) > 0:
                match = re.match(
                        '(?P<shots>T|[0-9]+) *' +
                        '(?P<plus_one>\+1)? *' +
                        '\( *(?P<reload>[0-9]+)' +
                        '(?P<individual>i?)\).*',
                        weapon['shots'])
                # TODO: eventually handle 'plus_one' (one in the chamber)
                if match:
                    if match.group('shots') == 'T': # Thrown
                        new_thing['reload_type'] = (
                                ca_equipment.Equipment.RELOAD_NONE)
                    else:
                        new_thing['ammo'] = { 'name':
                                ca_equipment.Equipment.UNKNOWN_STRING}
                        shots = int(match.group('shots'))
                        new_thing['ammo']['shots'] = shots
                        new_thing['ammo']['shots_left'] = shots # TODO: remove?
                        if len(match.group('individual')) > 0:
                            new_thing['reload_type'] = (
                                    ca_equipment.Equipment.RELOAD_ONE)
                        else:
                            new_thing['reload_type'] = (
                                    ca_equipment.Equipment.RELOAD_CLIP)

                        new_thing['reload'] = int(match.group('reload'))

                        # Make it a container so it can include a scope
                        new_thing['stuff'] = []
                        new_thing['type']['container'] = 1

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

    (EQUIP_ADD_ALL,
     EQUIP_ADD_THIS,
     EQUIP_MERGE_THIS,
     EQUIP_REPLACE_THIS) = list(range(4))

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
    def import_advantage_list(
            window_manager,   # ca_gui.WindowManager for errors
            native_data,  # dict: {name: {details}, ...
            gcs_advantages    # dict: {name: {details}, ...
            ):
        '''
        This routine imports the list of advantages from which a character can
        choose to improve the character.
        '''
        # TODO: combine the import functions
        PP = pprint.PrettyPrinter(indent=3, width=150) # Do not remove
        for gcs_name, gcs_advantage in gcs_advantages.items():
            if gcs_name not in native_data:
                native_data[gcs_name] = gcs_advantage
            elif native_data[gcs_name] == gcs_advantage:
                continue # Ignore an exact duplicate
            else:
                native_advantage = native_data[gcs_name]
                same_except_notes = True
                for name, item in gcs_advantage.items():
                    if name not in native_advantage:
                        native_advantage[name] = item
                    if (item != native_advantage[name] and name != 'notes' and
                            name != 'save'):
                        same_except_notes = False
                if not same_except_notes:
                    error_strings = ['Advantage "%s" different in GCS:' % gcs_name]
                    gcs_string = PP.pformat(gcs_advantage)
                    gcs_strings = gcs_string.split('\n')
                    error_strings.extend(gcs_strings)

                    error_strings.append('than stored natively:')
                    native_string = PP.pformat(native_advantage)
                    native_strings = native_string.split('\n')
                    error_strings.extend(native_strings)

                    window_manager.error(error_strings)

    def import_equipment_list(
            self,
            window_manager, # ca_gui.WindowManager for errors
            native_data,    # dict: {name: {details}, ...
            gcs_equipment   # dict: {name: {details}, ...
            ):
        '''
        This routine imports the list of advantages from which a character can
        choose to improve the character.
        '''
        self.__import_equipment(native_data,
                                gcs_equipment,
                                sync=False,
                                squash=False)

    @staticmethod
    def import_skill_list(window_manager,   # ca_gui.WindowManager for errors
                          native_data,  # dict: {name: {details}, ...
                          gcs_skills    # dict: {name: {details}, ...
                          ):
        '''
        This routine imports the list of skills from which a character can
        choose to improve the character.
        '''
        PP = pprint.PrettyPrinter(indent=3, width=150) # Do not remove
        for gcs_name, gcs_skill in gcs_skills.items():
            if gcs_name not in native_data:
                native_data[gcs_name] = gcs_skill
            elif native_data[gcs_name] == gcs_skill:
                continue # Ignore an exact duplicate
            else:
                native_skill = native_data[gcs_name]
                same_except_notes = True
                for name, item in gcs_skill.items():
                    if name not in native_skill:
                        native_skill[name] = item
                    if (item != native_skill[name] and name != 'notes' and
                            name != 'save'):
                        same_except_notes = False
                if not same_except_notes:
                    error_strings = ['Skill "%s" different in GCS:' % gcs_name]
                    gcs_string = PP.pformat(gcs_skill)
                    gcs_strings = gcs_string.split('\n')
                    error_strings.extend(gcs_strings)

                    error_strings.append('than stored natively:')
                    native_string = PP.pformat(native_skill)
                    native_strings = native_string.split('\n')
                    error_strings.extend(native_strings)

                    window_manager.error(error_strings)

    @staticmethod
    def import_spell_list(window_manager,   # ca_gui.WindowManager for errors
                          native_data,  # dict: {name: {details}, ...
                          gcs_spells    # dict: {name: {details}, ...
                          ):
        PP = pprint.PrettyPrinter(indent=3, width=150) # Do not remove
        for gcs_name, gcs_spell in gcs_spells.items():
            if gcs_name not in native_data:
                native_data[gcs_name] = gcs_spell
            elif native_data[gcs_name] == gcs_spell:
                continue # Ignore an exact duplicate
            else:
                native_spell = native_data[gcs_name]
                same_except_notes_save = True
                for name, item in gcs_spell.items():
                    if name not in native_spell:
                        native_spell[name] = item
                    if (item != native_spell[name] and name != 'notes' and
                            name != 'save'):
                        same_except_notes_save = False
                if not same_except_notes_save:
                    error_strings = ['Spell "%s" different in GCS:' % gcs_name]
                    gcs_string = PP.pformat(gcs_spell)
                    gcs_strings = gcs_string.split('\n')
                    error_strings.extend(gcs_strings)

                    error_strings.append('than stored natively:')
                    native_string = PP.pformat(native_spell)
                    native_strings = native_string.split('\n')
                    error_strings.extend(native_strings)

                    window_manager.error(error_strings)

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

        if 'stuff' not in self.__native_data:
            self.__native_data['stuff'] = []

        self.__import_equipment(self.__native_data['stuff'],
                                self.__gcs_data.stuff,
                                sync=True,
                                squash=False)

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

        if 'stuff' not in self.__native_data:
            self.__native_data['stuff'] = []

        changes.extend(self.__import_equipment(self.__native_data['stuff'],
                                               self.__gcs_data.stuff,
                                               sync=True,
                                               squash=True))

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

    def __equip_add_this(self,
                         operation,     # {'op': EQUIP_ADD_THIS,
                                        #  'item_gcs': item_gcs}
                         native_list,
                         gcs_list
                         ):
        item_gcs = operation['item_gcs']
        changes = ['"%s" equipment item added' % item_gcs['name']]
        native_list.append(item_gcs)
        return changes

    def __equip_merge_this(self,
                           operation,   # {'op': EQUIP_MERGE_THIS,
                                        #  'index_native': index_native,
                                        #  'index_gcs': index_gcs,
                                        #  'differences': differences}
                           native_list,
                           gcs_list
                           ):
        PP = pprint.PrettyPrinter(indent=3, width=150) # Do Not Remove

        index_native = operation['index_native']
        item_native = native_list[index_native]
        index_gcs = operation['index_gcs']
        item_gcs = gcs_list[index_gcs]
        differences = operation['differences']

        # Show differences between the items

        output = []
        standout_mode = curses.color_pair(ca_gui.GmWindowManager.YELLOW_BLACK)
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
        output.append([{'text': ('--- CA Item: %s ---' % item_native['name']),
                        'mode': curses.A_NORMAL}])
        string = PP.pformat(item_native)
        strings = string.split('\n')
        for string in strings:
            mode = curses.A_NORMAL
            for difference in differences:
                if string.find(difference) >= 0:
                    mode = standout_mode
            output.append([{'text': string, 'mode': mode}])

        # Merge the GCS and Native items into a new (temporary-ish) item

        new_item = copy.deepcopy(item_native)
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

        # Ask the user what to do about it

        self.__window_manager.display_window(
                ('Examine These %s -- They look really similar' %
                    item_native['name']),
                output)
        request_menu = [('Merge Them', ToNative.EQUIP_MERGE_THIS),
                        ('Replace with the GCS version',
                            ToNative.EQUIP_REPLACE_THIS),
                        ('Keep Both Copies', ToNative.EQUIP_ADD_THIS)]
        what_to_do, ignore = self.__window_manager.menu(
                'What Do You Want To Do?', request_menu)

        # Do what the user asks

        # Ask the user if these are the same item (i.e., accept
        # the merged item)
        if what_to_do == ToNative.EQUIP_MERGE_THIS:
            changes = ['"%s" merged GCS item into Native item' %
                    item_gcs['name']]
            self.__merge_items(item_native, item_gcs) # Result -> item_native

        elif what_to_do == ToNative.EQUIP_REPLACE_THIS:
            changes = self. __equip_replace_this(
                             {'op': ToNative.EQUIP_REPLACE_THIS,
                              'index_native': index_native,
                              'index_gcs': index_gcs},
                             native_list,
                             gcs_list)

        elif what_to_do == ToNative.EQUIP_ADD_THIS:
            changes = self.__equip_add_this(
                         {'op': ToNative.EQUIP_ADD_THIS,
                          'item_gcs': item_gcs},
                         native_list,
                         gcs_list)
        return changes

    def __equip_replace_this(self,
                             operation,     # {'op': EQUIP_REPLACE_THIS,
                                            #  'index_native': index_native,
                                            #  'index_gcs': index_gcs}))
                             native_list,
                             gcs_list
                             ):
        index_native = operation['index_native']
        item_native = native_list[index_native]
        index_gcs = operation['index_gcs']
        item_gcs = gcs_list[index_gcs]

        changes = ['"%s" equipment item replaced with GCS version' % item_native['name']]
        native_list[operation['index_native']] = item_gcs
        return changes

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
                           native_list, # []: contains native data, In/Output
                           gcs_list,    # []: contains GCS data
                           sync,        # Bool: syncing or copying (see below)
                           squash       # Bool: whether to flatten containers
                           ):
        '''
        Merges GCS equipment list with native one.  Discards exact duplicate
        items, merges similar items, and copies unique items into
        |native_list|.

        The |sync| parameter indicates whether we're synchronizing items
        between the native and GCS lists or copying them.  If an item from
        is in the native list but not the GCS list, syncing the lists will
        (optionally) keep the native item where copying will delete the item.

        Returns (in addition to |native_list| being changed) a list of changes
        to show the user.
        '''

        changes = []
        stuff_native = self.__copy_json_equipment_list(native_list, squash)
        stuff_gcs = self.__copy_json_equipment_list(gcs_list, squash)

        equip_menu = [(' - Do All The Things -', {'op': ToNative.EQUIP_ADD_ALL})]
        gcs_indexes_already_handled = []

        # Handle duplicates

        for index_gcs, item_gcs in enumerate(stuff_gcs):
            for index_native, item_native in enumerate(stuff_native):
                # Remove duplicates from GCS list
                differences = ToNative.find_differences(item_native, item_gcs)
                if differences is None:
                    gcs_indexes_already_handled.append(index_gcs)
                    break

                # Merge (maybe) similar items
                elif item_native['name'].lower() == item_gcs['name'].lower():
                    equip_menu.append(
                            ('%s (MERGE?)' % item_native['name'],
                                {'op': ToNative.EQUIP_MERGE_THIS,
                                 'index_gcs': index_gcs,
                                 'index_native': index_native,
                                 'differences': differences}))
                    gcs_indexes_already_handled.append(index_gcs)
                    break

        # Adds in GCS items that aren't already represented by native items
        # into the native item list.

        for index, item_gcs in enumerate(stuff_gcs):
            if index in gcs_indexes_already_handled:
                continue

            name_gcs = item_gcs['name']

            if ('ignored-equipment' in self.__native_data and
                    name_gcs.lower() in self.__native_data['ignored-equipment']):
                changes.append('"%s" equipment IGNORED -- no change' %
                        item_gcs['name'])
            else:
                #if ('features' in item and 'type' in item['features'][0] and
                #        'amount' in item['features'][0]):
                #    name = '%s (%s: %d)' % (item_gcs['description'],
                #                            item_gcs['features'][0]['type'],
                #                            item_gcs['features'][0]['amount'])
                #else:
                name = item_gcs['name']

                equip_menu.append(('%s' % name,
                                   {'op': ToNative.EQUIP_ADD_THIS,
                                    'item_gcs': item_gcs}))

        # Now, ask the user about all of the stuff

        keep_asking = True
        keep_asking_menu = [('yes', True), ('no', False)]
        while keep_asking:
            # TODO (now): I could put the self.__xxx() function in the menu entry
            #   {'doit': self.__whatever, 'param': passed_to_doit_method}

            doit, ignore = self.__window_manager.menu('Add Which Equipment',
                                                      equip_menu)
            if doit is None:
                keep_asking = False

            elif doit['op'] == ToNative.EQUIP_ADD_ALL:
                keep_asking = False
                for (string, operation) in equip_menu:
                    if operation['op'] == ToNative.EQUIP_ADD_THIS:
                        changes.extend(self.__equip_add_this(
                                       operation, native_list, gcs_list))
                    if operation['op'] == ToNative.EQUIP_MERGE_THIS:
                        changes.extend(self.__equip_merge_this(
                                       operation, native_list, gcs_list))
                    if operation['op'] == ToNative.EQUIP_REPLACE_THIS:
                        changes.extend(self.__equip_replace_this(
                                       operation, native_list, gcs_list))
            elif doit['op'] == ToNative.EQUIP_ADD_THIS:
                changes.extend(self.__equip_add_this(
                               operation, native_list))
            elif doit['op'] == ToNative.EQUIP_MERGE_THIS:
                changes.extend(self.__equip_merge_this(
                               operation, native_list, gcs_list))
            elif doit['op'] == ToNative.EQUIP_REPLACE_THIS:
                changes.extend(self.__equip_replace_this(
                               operation, native_list, gcs_list))

            if keep_asking:
                keep_asking, ignore = self.__window_manager.menu(
                    'Continue adding items', keep_asking_menu)

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
                      item_native,    # dict, destination
                      item_gcs      # dict
                      ):
        '''
        Merges equipment item |item_gcs| into |item_native|
        '''
        if item_native == item_gcs or item_gcs is None:
            return
        if isinstance(item_native, dict):
            if not isinstance(item_gcs, dict):
                return # Not worth merging if they're not the same type

            for key, value in item_gcs.items():
                if key not in item_native:
                    item_native[key] = value
                elif item_native[key] != item_gcs[key]:
                    if self.__is_scalar(item_native[key]):
                        if (isinstance(item_gcs[key], str) and
                                isinstance(item_native[key], str)):
                            if len(item_native[key]) == 0:
                                item_native[key] = item_gcs[key]
                        else:
                            item_native[key] = item_gcs[key]
                    else:
                        self.__merge_items(item_native[key], item_gcs[key])

        elif isinstance(item_native, list):
            if not isinstance(item_gcs, list):
                return # Not worth merging if they're not the same type

            for value in item_gcs:
                if value not in item_native:
                    item_native.append(value)

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
    # For debug output
    QUIET_IMPORT = True
    QUIET_SKILLS = True
    QUIET_EQUIPMENT = True
    QUIET_ADVANTAGES = True
    QUIET_ATTRIBUTES = True
    QUIET_SPELLS = True

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

        # Read the GCS file into an intermediate (mostly native) format
        gcs_data = FromGcs(self.__window_manager, ruleset, gcs_filename)
        gcs_data.convert_character()
        name = gcs_data.get_name()

        # Stuff the intermediate format into a native creature
        character = ToNative(self.__window_manager, native_data, gcs_data)
        character.import_character()
        # character.pprint() ######################
        return name, native_data

    def import_advantages_from_file(
            self,
            window_manager,   # ca_gui.WindowManager, or errors
            native_data,      # array = original skill list
            ruleset,          # ca_ruleset.Ruleset object
            gcs_filename=None,# string
            ):
        '''
        Reads the list of spells from a file into the local spell list.

        Reads the data into a local format and then writes the data into the
        local store.

        Returns: Nothing
        '''
        from_gcs = FromGcs(window_manager, ruleset, gcs_filename)
        gcs_advantages = from_gcs.build_advantage_list(window_manager)
        ToNative.import_advantage_list(window_manager,
                                       native_data,
                                       gcs_advantages)
        return

    def import_equipment_from_file(
            self,
            window_manager,   # ca_gui.WindowManager, or errors
            native_data,      # array = original skill list
            ruleset,          # ca_ruleset.Ruleset object
            gcs_filename=None,# string
            ):
        '''
        Reads the list of spells from a file into the local spell list.

        Reads the data into a local format and then writes the data into the
        local store.

        Returns: Nothing
        '''
        from_gcs = FromGcs(window_manager, ruleset, gcs_filename)
        gcs_equipment = from_gcs.build_equipment_list(window_manager)

        to_native = ToNative(window_manager, native_data, None)
        to_native.import_equipment_list(window_manager,
                                        native_data,
                                        gcs_equipment)
        return

    def import_skills_from_file(
            self,
            window_manager,   # ca_gui.WindowManager, or errors
            native_data,      # array = original skill list
            ruleset,          # ca_ruleset.Ruleset object
            gcs_filename=None,# string
            ):
        '''
        Reads the list of spells from a file into the local spell list.

        Reads the data into a local format and then writes the data into the
        local store.

        Returns: Nothing
        '''
        from_gcs = FromGcs(window_manager, ruleset, gcs_filename)
        gcs_skills = from_gcs.build_skill_list(window_manager)
        ToNative.import_skill_list(window_manager, native_data, gcs_skills)
        return

    def import_spells_from_file(
            self,
            window_manager,   # ca_gui.WindowManager, or errors
            native_data,      # array = original spell list
            ruleset,          # ca_ruleset.Ruleset object
            gcs_filename=None,# string
            ):
        '''
        Reads the list of spells from a file into the local spell list.

        Reads the data into a local format and then writes the data into the
        local store.

        Returns: Nothing
        '''
        from_gcs = FromGcs(window_manager, ruleset, gcs_filename)
        gcs_spells = from_gcs.build_spell_list(window_manager)
        ToNative.import_spell_list(window_manager, native_data, gcs_spells)
        return

    def update_creature(self,
                        native_data,           # dict contains original creature
                        ruleset,             # ca_ruleset.Ruleset object
                        gcs_filename=None,   # string
                        ):
        gcs_filename = self.__extract_gcs_filename(native_data, gcs_filename)
        gcs_data = FromGcs(self.__window_manager, ruleset, gcs_filename)
        gcs_data.convert_character()
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
