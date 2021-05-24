#! /usr/bin/python

import argparse
import copy
import datetime
import glob
import json
import os
import pprint
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET

import ca_json

# TODO: spells don't deal with more points than 24 or 28
# TODO: include 'count' in equipment

class MyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


class Skills(object):
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

    # Technique Cost Table
    # Your Final Difficulty of Technique
    # Skill Level* Average    Hard
    # Default      0 points   0 points
    # Default+1    1 point    2 points
    # Default+2    2 points   3 points
    # Default+3    3 points   4 points
    # Default+4    4 points   5 points
    # +1           +1 point   +1 point
    technique_cost = {
            # put <index> points into an 'A' technique and the skill is
            # ['A'][points] + default
            'A': [0, 1, 2, 3, 4],

            'H': [0, 0, 1, 2, 3, 4],
    ]
    # TODO: techniques
    # For the Dual-Weapon Attack technique, below:
    #   skill = technique_cost[<difficulty>][<points>] +
    #       <default><skill><specialization> + <default><modifier> =
    #   technique_cost['H'][2] + 'Beam Weapons'(Pistol) -4 =
    #   1 + <skill in Beam Weapons (pistol)> -4

    # <technique version="3" limit="0">
    #   <name>Dual-Weapon Attack</name>
    #   <difficulty>H</difficulty>
    #   <points>2</points>
    #   <reference>B230,MA83</reference>
    #   <default>
    #       <type>Skill</type>
    #       <name>Beam Weapons</name>
    #       <specialization>Pistol</specialization>
    #       <modifier>-4</modifier>
    #   </default>
    #   <categories>
    #       <category>Cinematic Techniques</category>
    #       <category>Combat/Weapon</category>
    #       <category>Ranged Combat</category>
    #   </categories>
    # </technique>

    techniques = {
            'Disarming' : {'diff':'H'},
            'Death from Above' : {'diff':'H'},
            'Dual-Weapon Attack' : {'diff':'H'},
            'Off-Hand Weapon Training' : {'diff':'H'},
    }

    @staticmethod
    def get_gcs_level(char,       # Character object
                      skill_name, # name of skill
                      cost        # points spent on skill
                     ):
        # TODO: the following skills are augmented by stuff
        #   - axe/mace: ?
        #   - armory: good quality equipment and ?
        #   - fast draw ammo: ?
        if skill_name not in Skills.skills:
            if skill_name in Skills.techniques:
                print '** "%s" is a GURPS Technique and is not yet in gcs-check.py' % skill_name
            else:
                print '** Need to add "%s" to gcs-check.py' % skill_name
            return 0
        skill = Skills.skills[skill_name]   # {'attr':'DX', 'diff':'E', 'default':-4}
        if skill['attr'] not in char.char['permanent']:
            print '** Required attribute "%s" not supplied' % skill['attr']
            return 0

        # Return a default value
        if cost == 0:
            if skill['default'] is None:
                print '** No default for skill "%s"' % skill_name
                return 0
            return char.char['permanent'][skill['attr']] + skill['default']

        # Adjust cost down if someone has extra points in a skill
        while cost not in Skills.level_from_cost and cost > 1:
            cost -= 1
        if cost < 1 and not default:
            print '** Cost %d invalid for skill %s' % (cost, skill_name)
            return 0

        # Calculate the skill level
        level = Skills.level_from_cost[cost]
        level += Skills.difficulty_offset[skill['diff']]
        level += char.char['permanent'][skill['attr']]

        # Add modifiers due to equipment
        if 'equip' in skill:
            for looking_for, plus in skill['equip'].iteritems():
                if looking_for.lower() in char.stuff:
                    level += plus
        if 'advantage' in skill:
            for looking_for, plus in skill['advantage'].iteritems():
                if looking_for in char.char['advantages']:
                    level += plus

        return level


class CharacterGcs(object):
    def __init__(self,
                 gcs_file   # filename holding GCS information
                ):
        self.__char_gcs = ET.parse(gcs_file).getroot()
        #for node in self.__char_gcs.iter(): # TODO: remove
        #    print node.tag, node.attrib # TODO: remove

        self.char = {} # JSON-like copy of character

        # Easier to build a separate 'stuff' list given containers and such.
        self.stuff = {} # names.lower(): count, ...

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

        # PP.pprint(self.char) # TODO: remove
        #PP.pprint(self.stuff) # TODO: remove

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
        name_entry = item.find('description')
        name = 'none' if name_entry is None else name_entry.text.lower()
        count_entry = item.find('quantity')
        count = 1 if count_entry is None else int(count_entry.text)
        #print 'Stuff name: "%s", count: %r' % (name, count) # TODO: remove
        if name in stuff_gcs:
            stuff_gcs[name] += count
        else:
            stuff_gcs[name] = count
        #print 'adding %s' % name.text
        if item.tag == 'equipment_container':
            #print '<< CONTAINER'
            for contents in item.findall('equipment_container'):
                self.__add_item_to_gcs_list(contents, stuff_gcs)
            for contents in item.findall('equipment'):
                self.__add_item_to_gcs_list(contents, stuff_gcs)
            #print '>> CONTAINER'

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

        # Checks skill cost
        # NOTE: Must run |__build_advantages| and |__build_equipment| before
        #   this because some skills are affected by advantages and equipment
        #   (a scope for a rifle, for instance).

        skills_gcs = self.__char_gcs.find('skill_list')

        for skill_gcs in skills_gcs:
            base_name = skill_gcs.find('name').text
            specs = []
            for specialization in skill_gcs.findall('specialization'):
                specs.append(specialization.text)
            if len(specs) > 0:
                name_text = '%s (%s)' % (base_name, ','.join(specs))
            else:
                name_text = base_name

            cost_text_gcs = skill_gcs.find('points')
            cost_gcs = 0 if cost_text_gcs is None else int(cost_text_gcs.text)
            level_gcs = Skills.get_gcs_level(self, base_name, cost_gcs)
            self.char['skills'][name_text] = level_gcs

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


class CompareChars(object):
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
                 char_json, # dict for this char directly from the JSON
                 char_gcs   # CharacterGcs object
                ):
        self.__char_json = char_json
        self.__char_gcs = char_gcs

    def check_for_consistency(self):
        changes_in_json = False
        if self.__check_attribs():
            changes_in_json = True
        if self.__check_advantages():
            changes_in_json = True
        if self.__check_skills():
            changes_in_json = True
        if self.__check_spells():
            changes_in_json = True
        if self.__check_equipment():
            changes_in_json = True
        return changes_in_json

    def __check_attribs(self):
        changes_in_json = False
        attrs_to_check = [ 'st' , 'dx' , 'iq' , 'ht', 'hp', 'fp', 'wi', 'per',
                           'basic-speed', 'basic-move' ]
        for attr_name in attrs_to_check:
            attr_gcs = self.__char_gcs.char['permanent'][attr_name]
            attr_json = self.__char_json['permanent'][attr_name]
            if attr_gcs != attr_json:
                print '   ** %s = %r in GCS but %r in JSON' % (attr_name,
                                                               attr_gcs,
                                                               attr_json)
                # If the value is greater in the JSON, this is probably an old
                # GCS file.
                if ARGS.write_json and attr_gcs > attr_json:
                    copy_answer = raw_input('Copy GCS value into the JSON? ')
                    if copy_answer[0].lower() == 'y':
                        self.__char_json['permanent'][attr_name] = attr_gcs
                        changes_in_json = True
            else:
                print '  %s: %r' % (attr_name, attr_gcs)

        return changes_in_json

    def __check_advantages(self):
        return self.__check_heading('advantages', 'Advantages')

    def __check_skills(self):
        return self.__check_heading('skills', 'Skills')

    def __check_spells(self):
        changes_in_json = False
        if 'spells' in self.__char_json:
            spells_json = self.__char_json['spells']
        else:
            spells_json = []

        if 'spells' in self.__char_gcs.char:
            spells_gcs = copy.deepcopy(self.__char_gcs.char['spells'])
        else:
            spells_gcs = []

        if len(spells_gcs) == 0 and len(spells_json) == 0:
            # Neither has |spells|.
            return

        print '\n-- Spell List -----'

        matching_items = 0
        found_errors = False
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
                print '   **GCS> "%s" in JSON (%r) but not in GCS' % (
                        name, spell_json['skill'])
                found_errors = True
            else:
                if match_gcs['skill'] != spell_json['skill']:
                    print '   ** %s = %r in GCS but %r in JSON' % (
                        name, match_gcs['skill'], spell_json['skill'])
                    found_errors = True

                    # Update the JSON
                    # If the value is greater in the JSON, this is probably an old
                    # GCS file.
                    if ARGS.write_json and match_gcs['skill'] > spell_json['skill']:
                        copy_answer = raw_input('Copy GCS skill value into the JSON? ')
                        if copy_answer[0].lower() == 'y':
                            spell_json['skill'] = match_gcs['skill']
                            changes_in_json = True
                else:
                    if ARGS.verbose:
                        print '  %s: %r' % (name, spell_json['skill'])
                    else:
                        matching_items += 1

                del spells_gcs[index_gcs]

        if found_errors:
            print ''

        found_errors = False
        for spell_gcs in spells_gcs:
            print '   **JSON> "%s" in GCS (%r) but not in JSON' % (
                    spell_gcs['name'], spell_gcs['skill'])

            found_errors = True

            # Update the JSON

            if ARGS.write_json:
                copy_answer = raw_input('Copy GCS spell into the JSON? ')
                if copy_answer[0].lower() == 'y':
                    spells_json.append(spell_gcs)
                    changes_in_json = True

        if not ARGS.verbose:
            if found_errors:
                print ''
            print '  %d matching items' % matching_items
        return changes_in_json

    def __check_heading(self,
                        heading,    # string: 'skills', 'advantages', etc
                        printable_heading # string: announce to user
                        ):
        changes_in_json = False
        if heading in self.__char_json:
            things_json = self.__char_json[heading]
        else:
            things_json = {}

        if heading in self.__char_gcs.char:
            things_gcs = copy.deepcopy(self.__char_gcs.char[heading])
        else:
            things_gcs = {}

        if len(things_gcs) == 0 and len(things_json) == 0:
            # Neither has |things|.
            return

        if printable_heading is not None:
            print '\n-- %s -----' % printable_heading

        matching_items = 0
        found_errors = False
        for name in things_json.iterkeys():
            if name not in things_gcs:
                print '   **GCS> "%s" in JSON (%r) but not in GCS' % (
                        name, things_json[name])
                found_errors = True
            else:
                if things_gcs[name] != things_json[name]:
                    print '   ** %s = %r in GCS but %r in JSON' % (
                        name, things_gcs[name], things_json[name])
                    found_errors = True

                    # Update the JSON
                    # If the value is greater in the JSON, this is probably
                    # an old GCS file.
                    if ARGS.write_json and things_gcs[name] > things_json[name]:
                        copy_answer = raw_input('Copy GCS value into the JSON? ')
                        if copy_answer[0].lower() == 'y':
                            things_json[name] = things_gcs[name]
                            changes_in_json = True
                else:
                    if ARGS.verbose:
                        print '  %s: %r' % (name, things_json[name])
                    else:
                        matching_items += 1

                del(things_gcs[name])

        if found_errors:
            print ''

        found_errors = False
        for name in things_gcs.iterkeys():
            if heading != 'skills' or name not in Skills.techniques:
                print '   **JSON> "%s" in GCS (%r) but not in JSON' % (
                        name, things_gcs[name])
                found_errors = True

                # Update the JSON
                if ARGS.write_json:
                    copy_answer = raw_input('Copy GCS %s value into the JSON? ' % heading)
                    if copy_answer[0].lower() == 'y':
                        things_json[name] = things_gcs[name]
                        changes_in_json = True

        if not ARGS.verbose:
            if found_errors:
                print ''
            print '  %d matching items' % matching_items
        return changes_in_json


    def __get_stuff_count(self,
                          item
                          ):
        return 1 if 'count' not in item else item['count']


    def __check_equipment(self):
        changes_in_json = False
        print '\n-- Equipment -----'

        if 'stuff' in self.__char_json:
            stuff_json = self.__char_json['stuff']
        else:
            stuff_json = {}

        stuff_gcs = copy.deepcopy(self.__char_gcs.stuff)

        # TODO: check the count.  It's a huge job because comparing items in
        # the gcs is difficult.  It may not be worth doing.

        matching_items = 0
        found_errors = False
        for item_json in stuff_json:    # item_json is {}
            name = item_json['name'].lower()
            match_gcs = None
            for name_gcs, count in stuff_gcs.iteritems():
                if name_gcs == name:
                    match_gcs = name_gcs
                    break

            if match_gcs is None:
                print '   **GCS> "%s" in JSON but not in GCS' % name
                found_errors = True
                # Can't add item, too many variables
            else:
                if ARGS.verbose:
                    print '  %s' % name
                else:
                    matching_items += 1
                del stuff_gcs[name]

        if found_errors:
            print ''
            found_errors = False

        for name_gcs in stuff_gcs.iterkeys():
            if name_gcs in CompareChars.equipment_white_list_gcs:
                pass
            else:
                print '   **JSON> "%s" in GCS but not in JSON' % name_gcs
                found_errors = True
                # Can't update the JSON -- too many variables

        if not ARGS.verbose:
            if found_errors:
                print ''
            print '  %d matching items' % matching_items
        return changes_in_json

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

if __name__ == '__main__':
    parser = MyArgumentParser()
    parser.add_argument('json_filename',
             help='Input JSON file containing characters')
    #parser.add_argument('gcs_filename',
    #         help='Input GCS file containing characters (may use wildcards)')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)
    parser.add_argument('-w', '--write_json',
            help='Write GCS/JSON differences to the JSON file', action='store_true',
            default=False)

    ARGS = parser.parse_args()
    PP = pprint.PrettyPrinter(indent=3, width=150)

    char_names_json = []
    changes_in_json = False
    with ca_json.GmJson(ARGS.json_filename, window_manager=None) as campaign:
        data_json = campaign.read_data
        char_names_json = [k for k in data_json['PCs'].keys()]
        for json_name in char_names_json:
            print '\n====== CHARACTER NAME "%s" ================\n' % json_name
            char_json = data_json['PCs'][json_name]

            # Get the GCS file corresponding to the JSON character

            gcs_file_name = None
            if 'gcs-file' in char_json:
                gcs_file_name = char_json['gcs-file']
                if not os.path.exists(gcs_file_name):
                    print '** File "%s" for PC "%s" does not exist' % (
                            gcs_file_name, json_name)
                    gcs_file_name = None
            if gcs_file_name is None:
                gcs_file_names = []
                for file_name in os.listdir('.'):
                    if file_name.endswith(".gcs"):
                        gcs_file_names.append(file_name)
                if len(gcs_file_names) == 0:
                    print '** No GCS files present'
                    sys.exit(2)

                print '\nWhich GCS file goes to %s' % json_name
                for i, gcs_file_name in enumerate(gcs_file_names):
                    print '  %d) %s' % (i, gcs_file_name)
                print '  %d) <Skip>' % len(gcs_file_names)
                char_number_gcs = input('Number: ')
                if char_number_gcs >= len(gcs_file_names):
                    continue # Skip this character
                gcs_file_name = gcs_file_names[char_number_gcs]
                char_json['gcs-file'] = gcs_file_name
                changes_in_json = True

            print 'Checking against file "%s"' % gcs_file_name
            char_gcs = CharacterGcs(gcs_file_name)

            # Compare the JSON with the GCS

            character = CompareChars(char_json, char_gcs)
            changes_in_this_json = character.check_for_consistency()
            if changes_in_this_json:
                changes_in_json = True

        # Update the JSON file

        if ARGS.write_json and changes_in_json:
            print ''
            copy_answer = raw_input('Write changes to JSON file? ')
            if copy_answer[0].lower() == 'y':
                # Copy the original filename
                dest_filename = get_dest_filename(ARGS.json_filename)
                print 'Backing up %s to %s...' % (ARGS.json_filename,
                                                  dest_filename)
                shutil.copyfile(ARGS.json_filename, dest_filename)

                # Setup to write the changes
                print 'Writing changes to %s' % ARGS.json_filename
                campaign.write_data = campaign.read_data

