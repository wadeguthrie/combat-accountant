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

def get_gca_attribute(char_gcs, # Element from the XML file
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
        'Acting':               {'attr':'IQ', 'diff':'A'},
        'Area Knowledge':       {'attr':'IQ', 'diff':'E'},
        'Armoury':              {'attr':'IQ', 'diff':'A'},
        'Axe/Mace':             {'attr':'DX', 'diff':'A'},
        'Beam Weapons':         {'attr':'DX', 'diff':'E'},
        'Brawling':             {'attr':'DX', 'diff':'E'},
        'Camouflage':           {'attr':'IQ', 'diff':'E'},
        'Climbing':             {'attr':'DX', 'diff':'A'},
        'Computer Hacking':     {'attr':'IQ', 'diff':'VH'},
        'Computer Operation':   {'attr':'IQ', 'diff':'E'},
        'Computer Programming': {'attr':'IQ', 'diff':'H'},
        'Connoisseur':          {'attr':'IQ', 'diff':'A'},
        'Cryptography':         {'attr':'IQ', 'diff':'H'},
        'Current Affairs':      {'attr':'IQ', 'diff':'E'},
        'Detect Lies':          {'attr':'Per', 'diff':'H'},
        'Diplomacy':            {'attr':'IQ', 'diff':'H'},
        'Electronics Operation':{'attr':'IQ', 'diff':'A'},
        'Electronics Repair':   {'attr':'IQ', 'diff':'A'},
        'Engineer':             {'attr':'IQ', 'diff':'H'},
        'Escape':               {'attr':'DX', 'diff':'H'},
        'Fast-Draw':            {'attr':'DX', 'diff':'E'},
        'Fast-Talk':            {'attr':'IQ', 'diff':'A'},
        'Filch':                {'attr':'DX', 'diff':'A'},
        'First Aid':            {'attr':'IQ', 'diff':'E'},
        'Forgery':              {'attr':'IQ', 'diff':'H'},
        'Gambling':             {'attr':'IQ', 'diff':'A'},
        'Gesture':              {'attr':'IQ', 'diff':'E'},
        'Gunner':               {'attr':'DX', 'diff':'E'},
        'Guns':                 {'attr':'DX', 'diff':'E'},
        'Hazardous Materials':  {'attr':'IQ', 'diff':'A'},
        'Holdout':              {'attr':'IQ', 'diff':'A'},
        'Interrogation':        {'attr':'IQ', 'diff':'A'},
        'Intimidation':         {'attr':'Will', 'diff':'A'},
        'Karate':               {'attr':'DX', 'diff':'H'},
        'Knife':                {'attr':'DX', 'diff':'E'},
        'Law':                  {'attr':'IQ', 'diff':'H'},
        'Lip Reading':          {'attr':'Per', 'diff':'A'},
        'Lockpicking':          {'attr':'IQ', 'diff':'A'},
        'Mathematics':          {'attr':'IQ', 'diff':'H'},
        'Mechanic':             {'attr':'IQ', 'diff':'A'},
        'Observation':          {'attr':'Per', 'diff':'A'},
        'Physician':            {'attr':'IQ', 'diff':'H'},
        'Physics':              {'attr':'IQ', 'diff':'VH'},
        'Pickpocket':           {'attr':'DX', 'diff':'H'},
        'Piloting':             {'attr':'DX', 'diff':'A'},
        'Running':              {'attr':'HT', 'diff':'A'},
        'Scrounging':           {'attr':'Per', 'diff':'E'},
        'Stealth':              {'attr':'DX', 'diff':'A'},
        'Streetwise':           {'attr':'IQ', 'diff':'A'},
        'Theology':             {'attr':'IQ', 'diff':'H'},
        'Throwing':             {'attr':'DX', 'diff':'A'},
        'Thrown Weapon':        {'attr':'DX', 'diff':'E'},
        'Traps':                {'attr':'IQ', 'diff':'A'},
        'Urban Survival':       {'attr':'Per', 'diff':'A'},
    }

    @staticmethod
    def get_level(attribs,    # dict containing HT, IQ, etc.
                  skill_name, # name of skill
                  cost        # points spent on skill
                 ):
        if skill_name not in Skills.skills:
            print '** No data for skill "%s"' % skill_name
            return 0
        skill = Skills.skills[skill_name]
        while cost not in Skills.level_from_cost and cost > 1:
            cost -= 1
        if cost < 1:
            print '** Cost %d invalid for skill %s' % (cost, skill_name)
            return 0
        level = Skills.level_from_cost[cost]

        level += Skills.difficulty_offset[skill['diff']]

        if skill['attr'] not in attribs:
            print '** Required attribute "%s" not supplied' % skill['attr']
            return 0
        level += attribs[skill['attr']]
        return level

class Character(object):
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

    def check_for_consistency(self):
        self.check_attribs()

        print '\n-- Skills -----'
        self.check_skills()

        print '\n-- Advantages -----'
        self.check_advantages()

        if 'spells' in self.char_json:
            print '\n-- Spell List -----'
            self.check_spells()

        self.check_equipment()

    def check_attribs(self):
        # TODO: add move, will, and speed -- gca has points spent / json
        # has result
        attr_names_json_from_gca = {
                                     'ST': 'st' ,
                                     'DX': 'dx' ,
                                     'IQ': 'iq' ,
                                     'HT': 'ht'
                                   }
        for attr_name in attr_names_json_from_gca:
            attr_gcs = get_gca_attribute(self.char_gcs, attr_name)
            self.attrs[attr_name] = attr_gcs
            attr_json = self.char_json['permanent'][
                                        attr_names_json_from_gca[attr_name]]
            if attr_gcs != attr_json:
                print '  ** %s = %r in GCS but %r in JSON' % (attr_name,
                                                              attr_gcs,
                                                              attr_json)
            else:
                print '  %s: %r' % (attr_name, attr_gcs)

        # HP
        attr_gcs = self.attrs['ST']
        attr_gcs += get_gca_attribute(self.char_gcs, 'HP')
        attr_json = self.char_json['permanent']['hp']
        if attr_gcs != attr_json:
            print '  ** HP = %r in GCS but %r in JSON' % (attr_gcs, attr_json)
        else:
            print '  HP: %r' % attr_gcs

        # FP
        attr_gcs = self.attrs['HT']
        attr_gcs += get_gca_attribute(self.char_gcs, 'FP')
        attr_json = self.char_json['permanent']['fp']
        if attr_gcs != attr_json:
            print '  ** FP = %r in GCS but %r in JSON' % (attr_gcs, attr_json)
        else:
            print '  FP: %r' % attr_gcs

        # WILL
        # TODO:
        attr_gcs = self.attrs['IQ']
        # TODO: do I need to multiply by 5 (the cost for a Will point?)
        #attr_gcs += get_gca_attribute(self.char_gcs, 'will')
        #attr_json = self.char_json['permanent']['Per']
        #if attr_gcs != attr_json:
        #    print '  ** Will = %r in GCS but %r in JSON' % (attr_gcs,
        #                                                    attr_json)
        #else:
        #    print '  Per: %r' % attr_gcs
        self.attrs['Will'] = attr_gcs

        # PERCEPTION
        # TODO:
        attr_gcs = self.attrs['IQ']
        # TODO: do I need to multiply by 5 (the cost for a perception point?)
        #attr_gcs += get_gca_attribute(self.char_gcs, 'perception')
        #attr_json = self.char_json['permanent']['Per']
        #if attr_gcs != attr_json:
        #    print '  ** Per = %r in GCS but %r in JSON' % (attr_gcs, attr_json)
        #else:
        #    print '  Per: %r' % attr_gcs
        self.attrs['Per'] = attr_gcs


    def check_skills(self):
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

            if name_text not in skills_json:
                print '  ** "%s" in GCS but not in JSON' % name_text
            else:
                cost_text_gcs = skill_gcs.find('points')
                cost_gcs = 0 if cost_text_gcs is None else int(
                                                            cost_text_gcs.text)

                level_gcs = Skills.get_level(self.attrs, base_name, cost_gcs)
                if level_gcs != skills_json[name_text]:
                    print '  ** %s = %r in GCS but %r in JSON' % (
                        name_text, level_gcs, skills_json[name_text])
                else:
                    print '  %s: %r' % (name_text, level_gcs)

                del(skills_json[name_text])
        for skill_json in skills_json:
            print '  ** "%s" in JSON but not in GCS' % skill_json

    def check_advantages(self):
        ## ADVANTAGES #####
        # Checks points spent

        advantages_gcs = self.char_gcs.find('advantage_list')
        #for advantage_gcs in advantages_gcs:
        #    name = advantage_gcs.find('name')
        #    cost = advantage_gcs.find('base_points')
        #    print '  %r %r' % (name.text, 0 if cost is None else cost.text)

        if 'advantages' in self.char_json:
            advantages_json = copy.deepcopy(self.char_json['advantages'])
        else:
            advantages_json = {}

        for advantage_gcs in advantages_gcs:
            name = advantage_gcs.find('name')
            #print 'ADVANTAGE NAME: "%r"' % name.text # TODO: remove
            if name.text not in advantages_json:
                print '  ** %s in GCS but not in JSON' % name.text
            else:
                cost_text_gcs = advantage_gcs.find('base_points')
                cost_gcs = 0 if cost_text_gcs is None else int(
                                                            cost_text_gcs.text)
                for modifier in advantage_gcs.findall('modifier'):
                    # TODO: remove
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
                if cost_gcs != advantages_json[name.text]:
                    print '  ** %s = %r in GCS but %r in JSON' % (
                        name.text, cost_gcs.text, advantages_json[name.text])
                else:
                    print '  %s: %r' % (name.text, cost_gcs)

                del(advantages_json[name.text])
        for advantage_json in advantages_json:
            print '  ** %s in JSON but not in GCS' % advantage_json

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
                    print '  ** %s in GCS but not in JSON' % name.text
                else:
                    print '  %s' % name.text
                    # TODO: compare skill levels
                    del(spells_json[name.text])
            for child in spells_json:
                print '  ** %s in JSON but not in GCS' % child


    def check_equipment(self):
        ## EQUIPMENT #####
        # TODO: 

        '''
        print '\n-- Equipment -----'
        stuff_gcs = self.char_gcs.find('equipment_list')

        if 'stuff' in self.char_json:
            stuff_json = copy.deepcopy(self.char_json['stuff'])
        else:
            stuff_json = {}

        if stuff_gcs is not None:
            for child in stuff_gcs:
                name = child.find('name')
                if name.text not in spells_json:
                    print '  ** %s in GCS but not in JSON' % name.text
                else:
                    print '  %s' % name.text
                    # TODO: compare skill levels
                    del(spells_json[name.text])
        for thing in spells_json:
            print '  ** %s in JSON but not in GCS' % thing
        '''

if __name__ == '__main__':
    parser = MyArgumentParser()
    parser.add_argument('json_filename',
             help='Input JSON file containing characters')
    parser.add_argument('gca_filename',
             help='Input GCA file containing characters (may use wildcards)')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)

    ARGS = parser.parse_args()
    PP = pprint.PrettyPrinter(indent=3, width=150)

    chars_json = []
    with GmJson(ARGS.json_filename, window_manager=None) as campaign:
        data_json = campaign.read_data
        chars_json = [k for k in data_json['PCs'].keys()]

    for gcs_file in glob.glob(ARGS.gca_filename):
        char_gcs = ET.parse(gcs_file).getroot()
        print 'Which character goes with "%s":' % gcs_file
        for i, char_name_json in enumerate(chars_json):
            print '  %d) %s' % (i, char_name_json)
        char_number_json = input('Number:')

        print '\n== CHARACTER NAME "%s" =====' % chars_json[char_number_json]
        char_json = data_json['PCs'][chars_json[char_number_json]]
        character = Character(char_json, char_gcs)
        character.check_for_consistency()

