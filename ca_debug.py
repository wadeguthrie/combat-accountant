#! /usr/bin/python

import datetime
import pprint

class Debug(object):

    filename = 'debug.txt'
    did_output = False

    def __init__(self,
                 filename=None
                 ):
        if filename is not None:
            Debug.filename = filename
        self.PP = pprint.PrettyPrinter(indent=3, width=150)

    def finish_up(self):
        if Debug.did_output:
            print('\n>>> Debug information in %s' % Debug.filename)

    def header1(self,
                string
                ):
        self.print('\n==== %s ====' % string)

    def header2(self,
                string
                ):
        self.print('\n---- %s ----' % string)

    def header3(self,
                string
                ):
        self.print('\n~~ %s ~~' % string)

    def print(self,
              string # string to be output
              ):
        if not Debug.did_output:
            fmt = '%Y-%m-%d %H:%M:%S'
            date = datetime.datetime.now().strftime(fmt).format()
            with open(Debug.filename, 'w') as f:
                f.write('Debug session started: %s\n' % date)

        Debug.did_output = True
        with open(Debug.filename, 'a') as f:
            f.write(string)
            f.write('\n')

    def pprint(self,
               thing # the thing to be pretty printed
               ):
        string = self.PP.pformat(thing)
        self.print(string)