#! /usr/bin/python

import copy
import json
import pprint
import xml.etree.ElementTree as ET

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

if __name__ == '__main__':
    PP = pprint.PrettyPrinter(indent=3, width=150)

    char_gcs = ET.parse('sample.gcs').getroot()
    #PP.pprint(char_gcs)

    chars_json = None
    filename = 'persephone.json'
    with GmJson(filename, window_manager=None) as campaign:
        chars_json = campaign.read_data


    char_json = chars_json['PCs']['mama V - Karen']

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
    attributes = [ 'HP', 'FP', 'ST', 'DX', 'IQ', 'HT' ]
    for attribute in attributes:
        attr = char_gcs.find(attribute)
        print '  %r %r' % (attribute, attr.text)

    print '\n-- Skill List -----'
    skills = char_gcs.find('skill_list')
    for child in skills:
        name = child.find('name')
        # TODO: will need to have a table of skills to look-up the point
        # cost versus the resulting value
        cost = child.find('points')
        print '  %r %r' % (name.text, 0 if cost is None else cost.text)


    ## ADVANTAGES #####

    print '\n-- Advantages -----'
    advantages_gcs = char_gcs.find('advantage_list')
    #for advantage_gcs in advantages_gcs:
    #    name = advantage_gcs.find('name')
    #    cost = advantage_gcs.find('base_points')
    #    print '  %r %r' % (name.text, 0 if cost is None else cost.text)

    if 'advantages' in char_json:
        advantages_json = copy.deepcopy(char_json['advantages'])
    else:
        advantages_json = {}

    for advantage_gcs in advantages_gcs:
        name = advantage_gcs.find('name')
        #print 'ADVANTAGE NAME: "%r"' % name.text # TODO: remove
        if name.text not in advantages_json:
            print '  ** %s in GCS but not in JSON' % name.text
        else:
            cost_text_gcs = advantage_gcs.find('base_points')
            cost_gcs = 0 if cost_text_gcs is None else int(cost_text_gcs.text)
            for modifier in advantage_gcs.findall('modifier'):


                #modifier_name = modifier.find('name') # TODO: remove
                #print '-modifier name: "%r"' % modifier_name.text # TODO: remove
                #PP.pprint(modifier.attrib) # TODO: remove


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


    ## SPELLS #####

    spells_gcs = char_gcs.find('spell_list')
    if spells_gcs is not None:
        if 'spells' in char_json:
            spells_json = {k['name']: k['skill'] for k in char_json['spells']}
        else:
            spells_json = {}
        print '\n-- Spell List -----'
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
