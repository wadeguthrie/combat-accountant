#! /usr/bin/python
import ca_gui

import json
import traceback

class BytesEncoder(json.JSONEncoder):
    window_manager = None

    '''
    Class to provide default encoding for byte array into a JSON file (there
    isn't an encoding provided).  This class converts to an ASCII string.
    '''
    def set_window_manager(self, window_manager):
        BytesEncoder.window_manager = window_manager

    def default(self, obj):
        if isinstance(obj, bytes):
            if window_manager is not None:
                window_manager.error(['Converting "%r"' % obj])
            return obj.decode('utf-8')
        return json.JSONEncoder.default(self, obj)

class GmJson(object):
    '''
    Context manager that opens and loads a JSON file.  Does so in a context
    manager and does all this in ASCII.  Needs to know about a window manager
    for error reporting.

    NOTE: this solution is for unicode that's encoded into a byte array (and
    the solution is to convert it into ASCII in a string.  There's a better
    solution.  The program could encode unicode directly into strings and no
    'BytesEncoder' class would be necessary.  This solution, I think, needs
    more Python 3 knowledge than I have at this point.  Here are the
    beginnings of my thoughts on the matter.

    From: https://stackoverflow.com/questions/18337407/
          saving-utf-8-texts-with-json-dumps-as-utf8-not-as-u-escape-sequence

    with open('filename', 'w', encoding='utf8') as json_file:
        json.dump(<unicode string>, json_file, ensure_ascii=False)

    '''

    def __init__(self,
                 filename,            # file containing the JSON to be read
                 window_manager=None  # send error messages here
                 ):
        self.__filename = filename
        self.__window_manager = window_manager
        self.found_file = None
        self.read_data = None
        self.write_data = None

    def __enter__(self):
        self.open_read_close()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is IOError:
            print('IOError: %r' % exception_type)
            print('EXCEPTION val: %s' % exception_value)
            traceback.print_exc()  # or traceback.format_exc()
        elif exception_type is not None:
            print('EXCEPTION type: %r' % exception_type)
            print('EXCEPTION val: %s' % exception_value)
            traceback.print_exc()  # or traceback.format_exc()

        self.open_write_close(self.write_data)

        return True

    def open_read_close(self):
        file_will_open = True
        try:
            with open(self.__filename, 'r') as f:
                self.found_file = True
                self.read_data = json.load(f)
                if self.read_data is None:
                    error_array = ['* Could not read JSON file "%s"' %
                                   self.__filename]
                    if error_msg is not None:
                        error_array.append(error_msg)

                    if self.__window_manager is None:
                        print('')
                        for message in error_array:
                            print('%s' % message)
                        print('')
                    else:
                        self.__window_manager.error(error_array)

        except FileNotFoundError:
            self.found_file = False
            file_will_open = False
            message = '** JSON file "%s" does not exist' % self.__filename
            if self.__window_manager is None:
                print(message)
            else:
                self.__window_manager.error([message])
            self.read_data = None
        #except Exception as e:
        #    message = str(e)
        #    if self.__window_manager is None:
        #        print(message)
        #    else:
        #        self.__window_manager.error([message])
        #    self.read_data = None
        return file_will_open

    def open_write_close(self,
                         write_data   # Data to be written to the file
                         ):
        '''
        Dump Python data to the JSON file.
        '''
        if write_data is not None:
            with open(self.__filename, 'w') as f:
                json.dump(write_data, f, indent=2, cls=BytesEncoder) # , ensure_ascii=False)
