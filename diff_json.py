#! /usr/bin/python
import argparse
import json
import pprint
import traceback


class GmJson(object):
    '''
    Context manager that opens and loads a JSON.  Does so in a context manager
    and does all this in ASCII (for v2.7 Python).  Needs to know about
    a window manager.
    '''

    def __init__(self,
                 filename,            # file containing the JSON to be read
                 window_manager=None  # send error messages here
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
            message = 'Could not read JSON file "%s"' % self.__filename
            if self.__window_manager is None:
                print message
            else:
                self.__window_manager.error([message])
            self.read_data = None
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is IOError:
            print 'IOError: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            traceback.print_exc()  # or traceback.format_exc()
        elif exception_type is not None:
            print 'EXCEPTION type: %r' % exception_type
            print 'EXCEPTION val: %s' % exception_value
            traceback.print_exc()  # or traceback.format_exc()

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
    def __byteify(data, ignore_dicts=False):
        # if this is a unicode string, return its string representation
        if isinstance(data, unicode):
            return data.encode('utf-8')
        # if this is a list of values, return list of byteified values
        if isinstance(data, list):
            return [GmJson.__byteify(item,
                                     ignore_dicts=True) for item in data]
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


def are_equal(lhs, rhs):
    if isinstance(lhs, dict):
        if not isinstance(rhs, dict):
            print '\n---------------------'
            print '** lhs is a dict but rhs is not'
            print '\nlhs'
            PP.pprint(lhs)
            print '\nrhs'
            PP.pprint(rhs)
            return False
        for key in rhs.iterkeys():
            if key not in lhs:
                print '\n---------------------'
                print '** KEY "%s" not in lhs' % key
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                return False
        result = True
        for key in lhs.iterkeys():
            if key not in rhs:
                print '\n---------------------'
                print '** KEY "%s" not in rhs' % key
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                result = False
            elif not are_equal(lhs[key], rhs[key]):
                print '\nSo, lhs[%r] != rhs[%r]' % (key, key)
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                result = False
        return result

    elif isinstance(lhs, list):
        if not isinstance(rhs, list):
            print '\n---------------------'
            print '** lhs is a list but rhs is not'
            print '\nlhs'
            PP.pprint(lhs)
            print '\nrhs'
            PP.pprint(rhs)
            return False
        if len(lhs) != len(rhs):
            print '\n---------------------'
            print '** length lhs=%d != len rhs=%d' % (len(lhs), len(rhs))
            print '\nlhs'
            PP.pprint(lhs)
            print '\nrhs'
            PP.pprint(rhs)
            return False
        result = True
        for i in range(len(lhs)):
            if not are_equal(lhs[i], rhs[i]):
                print '\nSo, lhs[%d] != rhs[%d]' % (i, i)
                print '\nlhs'
                PP.pprint(lhs)
                print '\nrhs'
                PP.pprint(rhs)
                result = False
        return result

    else:
        if lhs != rhs:
            print '\n---------------------'
            print '** lhs=%r != rhs=%r' % (lhs, rhs)
            print '\nlhs'
            PP.pprint(lhs)
            print '\nrhs'
            PP.pprint(rhs)
            return False
        else:
            return True


class MyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


if __name__ == '__main__':
    parser = MyArgumentParser()
    parser.add_argument(
            'filename', nargs=2,
             help='Input JSON file containing characters and monsters')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true',
                        default=False)

    ARGS = parser.parse_args()

    PP = pprint.PrettyPrinter(indent=3, width=150)

    print 'LHS: %s' % ARGS.filename[0]
    print 'RHS: %s' % ARGS.filename[1]
    print ''

    with GmJson(ARGS.filename[0]) as file1:
        with GmJson(ARGS.filename[1]) as file2:
            if are_equal(file1.read_data, file2.read_data):
                print 'files are equal'
