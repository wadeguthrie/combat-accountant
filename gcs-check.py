#! /usr/bin/python

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

    char_xml = ET.parse('sample.gcs').getroot()
    #PP.pprint(char_xml)

    json_chars = None
    filename = 'persephone.json'
    with GmJson(filename, window_manager=None) as campaign:
        json_chars = campaign.read_data


    json_char = json_chars['PCs']['mama V - Karen']

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
    #for child in char_xml:
    #    print '%r %r' % (child.tag, child.attrib)


    #for child in advantages:
    #    print '\n---'
    #    for info in child:
    #        print '%r %r %r' % (info.tag, info.attrib, info.text)
    attributes = [ 'HP', 'FP', 'ST', 'DX', 'IQ', 'HT' ]
    for attribute in attributes:
        attr = char_xml.find(attribute)
        print '  %r %r' % (attribute, attr.text)

    print '\n-- Skill List -----'
    skills = char_xml.find('skill_list')
    for child in skills:
        name = child.find('name')
        # TODO: will need to have a table of skills to look-up the point
        # cost versus the resulting value
        cost = child.find('points')
        print '  %r %r' % (name.text, 0 if cost is None else cost.text)

    print '\n-- Advantages -----'
    advantages = char_xml.find('advantage_list')
    for child in advantages:
        name = child.find('name')
        cost = child.find('base_points')
        print '  %r %r' % (name.text, 0 if cost is None else cost.text)

    spells = char_xml.find('spell_list')
    if spells is not None:
        print '\n-- Spell List -----'
        for child in spells:
            name = child.find('name')
            # TODO: figure out how the difficulty is stored
            print '  %r' % name.text
