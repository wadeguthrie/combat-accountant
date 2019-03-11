#! /usr/bin/python

import argparse
import copy
import glob
import json
import pprint
import sys
import xml.etree.ElementTree as ET

class MyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2) 

class GmJson(object):
    '''
    Context manager that opens and loads a JSON.  Does so in a context manager
    and does all this in ASCII (for v2.7 Python).  Needs to know about
    a window manager.
    '''

    def __init__(self,
                 filename,             # file containing the JSON to be read
                 window_manager = None # send error messages here
                ):
        self.__filename = filename
        self.__window_manager = window_manager
        self.read_data = None
        self.write_data = None


    def __enter__(self):
        try:
            with open(self.__filename, 'r') as f:
              self.read_data, error_msg = GmJson.__json_load_byteified(f)
              if self.read_data is None:
                    error_array = ['Could not read JSON file "%s"' %
                                                            self.__filename]
                    if error_msg is not None:
                        error_array.append(error_msg)

                    if self.__window_manager is None:
                        print ''
                        for message in error_array:
                            print '%s' % message
                        print ''
                    else:
                        self.__window_manager.error(error_array)

        except:
            if self.__window_manager is not None:
                self.__window_manager.error(['Could not read JSON file "%s"' %
                                                self.__filename])
            self.read_data = None
        return self


    def __exit__ (self, exception_type, exception_value, exception_traceback):
        if exception_type is IOError:
            print 'IOError: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            traceback.print_exc() # or traceback.format_exc()
        elif exception_type is not None:
            print 'EXCEPTION type: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            traceback.print_exc() # or traceback.format_exc()

        if self.write_data is not None:
            with open(self.__filename, 'w') as f:
                json.dump(self.write_data, f, indent=2)
        return True

    # Used to keep JSON load from automatically converting to Unicode.
    # Alternatively, I could have gone to Python 3 (which doesn't have that
    # problem) but I didn't want to install a new version of Python and a new
    # version of Curses.
    #
    # Solution from https://stackoverflow.com/questions/956867/
    #        how-to-get-string-objects-instead-of-unicode-from-json?
    #        utm_medium=organic&utm_source=google_rich_qa&
    #        utm_campaign=google_rich_qa


    @staticmethod
    def __byteify(data, ignore_dicts = False):
        # if this is a unicode string, return its string representation
        if isinstance(data, unicode):
            return data.encode('utf-8')
        # if this is a list of values, return list of byteified values
        if isinstance(data, list):
            return [ GmJson.__byteify(item,
                                      ignore_dicts=True) for item in data ]
        # if this is a dictionary, return dictionary of byteified keys and
        # values but only if we haven't already byteified it
        if isinstance(data, dict) and not ignore_dicts:
            return {
                GmJson.__byteify(key, ignore_dicts=True):
                    GmJson.__byteify(value, ignore_dicts=True)
                    for key, value in data.iteritems()
            }
        # if it's anything else, return it in its original form
        return data


    @staticmethod
    def __json_load_byteified(file_handle):
        error_message = None
        try:
            my_dict = json.load(file_handle, object_hook=GmJson.__byteify)
        except Exception as e:
            return None, 'Couldn\'t read JSON: "%s"' % str(e)

        return GmJson.__byteify(my_dict, ignore_dicts=True), None

def get_gcs_attribute(char_gcs, # Element from the XML file
                      attr_name # string
                     ):
    attr_gcs_element = char_gcs.find(attr_name)
    attr_gcs_text = attr_gcs_element.text
    attr_gcs = int(attr_gcs_text)
    return attr_gcs

class Skills(object):
    # To go from (cost, difficulty, attribute) to skill-level:
    #   level_from_cost[cost] = base level
    #   difficulty_offset[difficulty] : add to base-level
    #   attribute : add to base-level
    level_from_cost = {1:0, 2:1, 4:2, 8:3, 12:4, 16:5, 20:6, 24:7, 28:5}
    difficulty_offset = {'E':0, 'A':-1, 'H':-2, 'VH':-3}
    skills = {
        'Acting':               {'attr':'IQ', 'diff':'A', 'default':-5},
        'Administration':       {'attr':'IQ', 'diff':'A', 'default':-5},
        'Area Knowledge':       {'attr':'IQ', 'diff':'E', 'default':-4},
        'Armoury':              {'attr':'IQ', 'diff':'A', 'default':-5},
        'Axe/Mace':             {'attr':'DX', 'diff':'A', 'default':None},
        'Beam Weapons':         {'attr':'DX', 'diff':'E', 'default':-4,
                                 'equip': {'Laser Sight': 1}},
        # Bartender is really a professional skill
        'Bartender':            {'attr':'IQ', 'diff':'A', 'default':-5},
        'Brawling':             {'attr':'DX', 'diff':'E', 'default':None},
        'Camouflage':           {'attr':'IQ', 'diff':'E', 'default':-4},
        'Climbing':             {'attr':'DX', 'diff':'A', 'default':-5},
        'Computer Hacking':     {'attr':'IQ', 'diff':'VH', 'default':None},
        'Computer Operation':   {'attr':'IQ', 'diff':'E', 'default':-4},
        'Computer Programming': {'attr':'IQ', 'diff':'H', 'default':None},
        'Connoisseur':          {'attr':'IQ', 'diff':'A', 'default':-5},
        'Cryptography':         {'attr':'IQ', 'diff':'H', 'default':None},
        'Current Affairs':      {'attr':'IQ', 'diff':'E', 'default':-4},
        'Detect Lies':          {'attr':'Per', 'diff':'H', 'default':-6},
        'Diagnosis':            {'attr':'IQ', 'diff':'H', 'default':-6},
        'Diplomacy':            {'attr':'IQ', 'diff':'H', 'default':-6},
        'Electronics Operation':{'attr':'IQ', 'diff':'A', 'default':-5},
        'Electronics Repair':   {'attr':'IQ', 'diff':'A', 'default':-5},
        'Expert Skill':         {'attr':'IQ', 'diff':'H', 'default':None},
        'Explosives':           {'attr':'IQ', 'diff':'A', 'default':-5},
        'Engineer':             {'attr':'IQ', 'diff':'H', 'default':None},
        'Environment Suit':     {'attr':'DX', 'diff':'A', 'default':-5},
        'Escape':               {'attr':'DX', 'diff':'H', 'default':-6},
        'Fast-Draw':            {'attr':'DX', 'diff':'E', 'default':None},
        'Fast-Talk':            {'attr':'IQ', 'diff':'A', 'default':-5},
        'Filch':                {'attr':'DX', 'diff':'A', 'default':-5},
        'First Aid':            {'attr':'IQ', 'diff':'E', 'default':-4,
                                 'equip': {'First Aid Kit': 1}},
        'Forgery':              {'attr':'IQ', 'diff':'H', 'default':-6},
        'Forward Observer':     {'attr':'IQ', 'diff':'A', 'default':-5},
        'Gambling':             {'attr':'IQ', 'diff':'A', 'default':-5},
        'Gesture':              {'attr':'IQ', 'diff':'E', 'default':-4},
        'Gunner':               {'attr':'DX', 'diff':'E', 'default':-4},
        'Guns':                 {'attr':'DX', 'diff':'E', 'default':-4},
        'Hazardous Materials':  {'attr':'IQ', 'diff':'A', 'default':-5},
        'Hiking':               {'attr':'HT', 'diff':'A', 'default':-5},
        'Holdout':              {'attr':'IQ', 'diff':'A', 'default':-5},
        'Interrogation':        {'attr':'IQ', 'diff':'A', 'default':-5},
        'Intimidation':         {'attr':'Will', 'diff':'A', 'default':-5},
        'Jumping':              {'attr':'DX', 'diff':'E', 'default':None},
        'Karate':               {'attr':'DX', 'diff':'H', 'default':None},
        'Knife':                {'attr':'DX', 'diff':'E', 'default':None},
        'Law':                  {'attr':'IQ', 'diff':'H', 'default':-6},
        'Leadership':           {'attr':'IQ', 'diff':'A', 'default':-5},
        'Lip Reading':          {'attr':'Per', 'diff':'A', 'default':-10},
        'Lockpicking':          {'attr':'IQ', 'diff':'A', 'default':-5},
        'Mathematics':          {'attr':'IQ', 'diff':'H', 'default':-6},
        'Mechanic':             {'attr':'IQ', 'diff':'A', 'default':-5},
        'Observation':          {'attr':'Per', 'diff':'A', 'default':-5},
        'Physician':            {'attr':'IQ', 'diff':'H', 'default':-7},
        'Physics':              {'attr':'IQ', 'diff':'VH', 'default':-6},
        'Pickpocket':           {'attr':'DX', 'diff':'H', 'default':-6},
        'Piloting':             {'attr':'DX', 'diff':'A', 'default':None},
        'Running':              {'attr':'HT', 'diff':'A', 'default':-5},
        'Savoir-Faire':         {'attr':'IQ', 'diff':'E', 'default':-4},
        'Scrounging':           {'attr':'Per', 'diff':'E', 'default':-4},
        'Search':               {'attr':'Per', 'diff':'A', 'default':-5},
        'Soldier':              {'attr':'IQ', 'diff':'A', 'default':-5},
        'Stealth':              {'attr':'DX', 'diff':'A', 'default':-5},
        'Streetwise':           {'attr':'IQ', 'diff':'A', 'default':-5},
        'Surgery':              {'attr':'IQ', 'diff':'VH', 'default':None},
        'Survival':             {'attr':'Per', 'diff':'A', 'default':None},
        'Tactics':              {'attr':'IQ', 'diff':'H', 'default':-6},
        'Theology':             {'attr':'IQ', 'diff':'H', 'default':-6},
        'Throwing':             {'attr':'DX', 'diff':'A', 'default':-3},
        'Thrown Weapon':        {'attr':'DX', 'diff':'E', 'default':-4},
        'Traps':                {'attr':'IQ', 'diff':'A', 'default':-5},
        'Urban Survival':       {'attr':'Per', 'diff':'A', 'default':-5},
    }

    @staticmethod
    def get_gcs_level(attribs,    # dict containing HT, IQ, etc.
                      equipment,  # xxx
                      skill_name, # name of skill
                      cost        # points spent on skill
                     ):

        # TODO: the following skills are augmented by stuff
        #   - axe/mace: ?
        #   - armory: good quality equipment and ?
        #   - detect lies: ?
        #   - fast draw ammo: ?
        if skill_name not in Skills.skills:
            print '** Need to add "%s" to gcs-check.py' % skill_name
            return 0
        skill = Skills.skills[skill_name]
        if skill['attr'] not in attribs:
            print '** Required attribute "%s" not supplied' % skill['attr']
            return 0

        # Return a default value
        if cost == 0:
            if skill['default'] is None:
                print '** No default for skill "%s"' % skill_name
                return 0
            return attribs[skill['attr']] + skill['default']

        # Adjust cost down if someone has extra points in a skill
        while cost not in Skills.level_from_cost and cost > 1:
            cost -= 1
        if cost < 1 and not default:
            print '** Cost %d invalid for skill %s' % (cost, skill_name)
            return 0

        # Calculate the skill level
        level = Skills.level_from_cost[cost]
        level += Skills.difficulty_offset[skill['diff']]
        level += attribs[skill['attr']]

        # Add modifiers due to equipment
        if 'equip' in skill:
            for item, plus in skill['equip'].iteritems():
                if item in equipment:
                    level += plus

        return level

class Character(object):
    equipment_white_list_gcs = {
      "Alpaca hat": 1,
      "Alpaca lapel pin": 1,
      "Alpaca socks": 1,
      "Alpaca T-Shirt": 1,
      "Alpaca wool": 1,
      "Antibiotic": 1,
      "Antitoxin Kit": 1,
      "Backpack, Small": 1,
      "Ballistic Gloves":1,
      "Ballistic Sunglasses":1,
      "Bandages": 1,
      "Belt": 1,
      "Boots": 1,
      "Camera": 1,
      "Camera, Digital, Full-Sized":1,
      "Cigarette Lighter (Metal Refillable)": 1,
      "Cigarette Lighter":1,
      "Conglomerate Marshal Uniform": 1,
      "Drop Spindle": 1,
      "Duct Tape": 1,
      "E-Rubles": 1,
      "Electronic Cuffs":1,
      "eRuble": 1,
      "Eyeglasses": 1,
      "Fire-Starter Paste":1,
      "Flashlight":1,
      "Flashlight, Heavy": 1,
      "Glowstick":1,
      "Holster, Belt": 1,
      "Holster, Shoulder":1,
      "Index Cards":1,
      "Knitting Needles, Pair": 1,
      "Lanyard, Woven Steel": 1,
      "Marker":1,
      "Measuring laser":1,
      "Medicine Bag": 1,
      "Messenger Bag/Shoulder Bag": 1,
      "Microfiber Towel":1,
      "Multi-Tool with Flashlight": 1,
      "Multi-Tool":1,
      "Nitrile Gloves":1,
      "Plastic Bags":1,
      "Pocket Watch":1,
      "Sheath": 1,
      "Sheep Skin Alpaca": 1,
      "Small Sheath": 1,
      "Snack":1,
      "Sunglasses": 1,
      "Tactical Belt Bag": 1,
      "Teddy Bear": 1,
      "Voice Synthesizer": 1,
      "Web Gear":1,
      "Weed": 1,
      "Whistle": 1,
      "Wooden Alpaca Figure": 1,
      "Wool": 1,
      "Wristwatch": 1,
      "Yarn Alpaca": 1,
    }
    def __init__(self,
                 char_json, # dict for this char directly from the JSON
                 char_gcs   # results of ET.parse for the GCS file
                ):
        self.char_json = char_json

        '''
        'created_date' {}
        'modified_date' {}
        'profile' {}
        '* HP' {}
        '* FP' {}
        'total_points' {}
        '* ST' {}
        '* DX' {}
        '* IQ' {}
        '* HT' {}
        '* will' {}
        'perception' {}
        '? speed' {}
        '? move' {}
        'include_punch' {}
        'include_kick' {}
        'include_kick_with_boots' {}
        '- advantage_list' {}
        '- skill_list' {}
        '* spell_list' {}
        '? equipment_list' {}
        '''
        self.char_gcs = char_gcs
        self.attrs = {}

        # Build the equipment list up front so that skills may make use of it
        self.stuff_gcs = []
        top_stuff_gcs = self.char_gcs.find('equipment_list')
        if top_stuff_gcs is not None:
            for child in top_stuff_gcs:
                self.__add_item_to_gcs_list(child, self.stuff_gcs)

    def check_for_consistency(self):
        self.check_attribs()

        print '\n-- Skills -----'
        self.check_skills()

        print '\n-- Advantages -----'
        self.check_advantages()

        if 'spells' in self.char_json:
            print '\n-- Spell List -----'
            self.check_spells()

        print '\n-- Equipment -----'
        self.check_equipment()

    def check_attribs(self):
        # TODO: add move, will, and speed -- gcs has points spent / json
        # has result
        attr_names_json_from_gcs = {
                                     'ST': 'st' ,
                                     'DX': 'dx' ,
                                     'IQ': 'iq' ,
                                     'HT': 'ht'
                                   }
        for attr_name in attr_names_json_from_gcs:
            attr_gcs = get_gcs_attribute(self.char_gcs, attr_name)
            self.attrs[attr_name] = attr_gcs
            attr_json = self.char_json['permanent'][
                                        attr_names_json_from_gcs[attr_name]]
            if attr_gcs != attr_json:
                print '   ** %s = %r in GCS but %r in JSON' % (attr_name,
                                                               attr_gcs,
                                                               attr_json)
            else:
                print '  %s: %r' % (attr_name, attr_gcs)

        # HP
        attr_gcs = self.attrs['ST']
        attr_gcs += get_gcs_attribute(self.char_gcs, 'HP')
        attr_json = self.char_json['permanent']['hp']
        if attr_gcs != attr_json:
            print '   ** HP = %r in GCS but %r in JSON' % (attr_gcs, attr_json)
        else:
            print '  HP: %r' % attr_gcs

        # FP
        attr_gcs = self.attrs['HT']
        attr_gcs += get_gcs_attribute(self.char_gcs, 'FP')
        attr_json = self.char_json['permanent']['fp']
        if attr_gcs != attr_json:
            print '   ** FP = %r in GCS but %r in JSON' % (attr_gcs, attr_json)
        else:
            print '  FP: %r' % attr_gcs

        # WILL
        # TODO:
        attr_gcs = self.attrs['IQ']
        # TODO: do I need to multiply by 5 (the cost for a Will point?)
        #attr_gcs += get_gcs_attribute(self.char_gcs, 'will')
        #attr_json = self.char_json['permanent']['Per']
        #if attr_gcs != attr_json:
        #    print '   ** Will = %r in GCS but %r in JSON' % (attr_gcs,
        #                                                    attr_json)
        #else:
        #    print '  Per: %r' % attr_gcs
        self.attrs['Will'] = attr_gcs

        # PERCEPTION
        # TODO:
        attr_gcs = self.attrs['IQ']
        # TODO: do I need to multiply by 5 (the cost for a perception point?)
        #attr_gcs += get_gcs_attribute(self.char_gcs, 'perception')
        #attr_json = self.char_json['permanent']['Per']
        #if attr_gcs != attr_json:
        #    print '   ** Per = %r in GCS but %r in JSON' % (attr_gcs, attr_json)
        #else:
        #    print '  Per: %r' % attr_gcs
        self.attrs['Per'] = attr_gcs


    def check_skills(self):
        # Checks skill cost

        skills_gcs = self.char_gcs.find('skill_list')

        if 'skills' in self.char_json:
            skills_json = copy.deepcopy(self.char_json['skills'])
        else:
            skills_json = {}

        for skill_gcs in skills_gcs:
            base_name = skill_gcs.find('name').text
            #print 'SKILL BASE NAME: "%r"' % base_name # TODO: remove
            specs = []
            for specialization in skill_gcs.findall('specialization'):
                specs.append(specialization.text)
            if len(specs) > 0:
                name_text = '%s (%s)' % (base_name, ','.join(specs))
            else:
                name_text = base_name
            #print '  "%r"' % name_text # TODO: remove

            cost_text_gcs = skill_gcs.find('points')
            cost_gcs = 0 if cost_text_gcs is None else int(cost_text_gcs.text)
            level_gcs = Skills.get_gcs_level(self.attrs,
                                             self.stuff_gcs,
                                             base_name,
                                             cost_gcs)
            if name_text not in skills_json:
                print '   **GCS> "%s" in GCS (%r) but not in JSON' % (name_text,
                                                                     level_gcs)
            else:
                if level_gcs != skills_json[name_text]:
                    print '   ** %s = %r in GCS but %r in JSON' % (
                        name_text, level_gcs, skills_json[name_text])
                else:
                    print '  %s: %r' % (name_text, level_gcs)

                del(skills_json[name_text])
        for skill_json in skills_json:
            print '   **JSON> "%s" in JSON but not in GCS' % skill_json

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

            #print 'ADVANTAGE NAME: "%r"' % name.text # TODO: remove
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
            advantages_gcs[name.text] = cost_gcs


    def check_advantages(self):
        ## ADVANTAGES #####
        # Checks points spent

        advantages_gcs_raw = self.char_gcs.find('advantage_list')

        if 'advantages' in self.char_json:
            advantages_json = copy.deepcopy(self.char_json['advantages'])
        else:
            advantages_json = {}

        advantages_gcs_raw = self.char_gcs.find('advantage_list')
        advantages_gcs = {}
        for child in advantages_gcs_raw:
            self.__add_advantage_to_gcs_list(child, advantages_gcs)

        for name in advantages_gcs:
            #print 'ADVANTAGE NAME: "%r"' % name # TODO: remove
            if name not in advantages_json:
                print '   **GCS> "%s" in GCS but not in JSON' % name
            else:
                if advantages_gcs[name] != advantages_json[name]:
                    print '   ** %s = %r in GCS but %r in JSON' % (
                        name, advantages_gcs[name], advantages_json[name])
                else:
                    print '  %s: %r' % (name, advantages_gcs[name])

                del(advantages_json[name])
        for advantage_json in advantages_json:
            print '   **JSON> "%s" in JSON but not in GCS' % advantage_json

    def check_spells(self):
        ## SPELLS #####
        # TODO: need to include difficulty level
        # TODO: should do a better job of making sure that both files either 
        #   DO have spells or DON'T have spells

        spells_gcs = self.char_gcs.find('spell_list')
        if spells_gcs is not None:
            if 'spells' in self.char_json:
                spells_json = {k['name']: k['skill'] 
                                            for k in self.char_json['spells']}
            else:
                spells_json = {}
            for child in spells_gcs:
                name = child.find('name')
                # TODO: figure out how the difficulty is stored
                if name.text not in spells_json:
                    print '   **GCS> "%s" in GCS but not in JSON' % name.text
                else:
                    print '  %s' % name.text
                    # TODO: compare skill levels
                    del(spells_json[name.text])
            for child in spells_json:
                print '   **JSON> "%s" in JSON but not in GCS' % child

    def __add_item_to_gcs_list(self,
                               item,        # ET item
                               stuff_gcs    # list of names of items
                              ):
        name = item.find('description')
        stuff_gcs.append(name.text)
        #print 'adding %s' % name.text
        if item.tag == 'equipment_container':
            #print '<< CONTAINER'
            for contents in item.findall('equipment_container'):
                self.__add_item_to_gcs_list(contents, stuff_gcs)
            for contents in item.findall('equipment'):
                self.__add_item_to_gcs_list(contents, stuff_gcs)
            #print '>> CONTAINER'

    def check_equipment(self):
        ## EQUIPMENT #####
        if 'stuff' in self.char_json:
            #PP.pprint(self.char_json['stuff'])
            stuff_json = {k['name']:1 for k in self.char_json['stuff']}
        else:
            stuff_json = {}

        for name in self.stuff_gcs:
            if name in Character.equipment_white_list_gcs:
                pass
            elif name not in stuff_json:
                print '   **GCS> "%s" in GCS but not in JSON' % name
            else:
                print '  %s' % name
                del(stuff_json[name])
        for thing in stuff_json:
            print '   **JSON> "%s" in JSON but not in GCS' % thing

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

if __name__ == '__main__':
    parser = MyArgumentParser()
    parser.add_argument('json_filename',
             help='Input JSON file containing characters')
    parser.add_argument('gcs_filename',
             help='Input GCS file containing characters (may use wildcards)')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)

    ARGS = parser.parse_args()
    PP = pprint.PrettyPrinter(indent=3, width=150)

    chars_json = []
    with GmJson(ARGS.json_filename, window_manager=None) as campaign:
        data_json = campaign.read_data
        chars_json = [k for k in data_json['PCs'].keys()]

    for gcs_file in glob.glob(ARGS.gcs_filename):
        char_gcs = ET.parse(gcs_file).getroot()
        print '\nWhich character goes with "%s":' % gcs_file
        for i, char_name_json in enumerate(chars_json):
            print '  %d) %s' % (i, char_name_json)
        char_number_json = input('Number: ')

        print '\n== CHARACTER NAME "%s" =====' % chars_json[char_number_json]
        char_json = data_json['PCs'][chars_json[char_number_json]]
        character = Character(char_json, char_gcs)
        character.check_for_consistency()

