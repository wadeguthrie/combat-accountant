#! /usr/bin/python

import datetime
import pprint

class Debug(object):

    filename = 'debug.txt'
    did_output = False
    quiet = False

    def __init__(self,
                 quiet=False,   # Way to shut down all output easily
                 filename=None
                 ):
        Debug.quiet = quiet
        if filename is not None:
            Debug.filename = filename
        self.PP = pprint.PrettyPrinter(indent=3, width=150)

    def finish_up(self):
        if Debug.did_output:
            print('\n>>> Debug information in %s' % Debug.filename)

    def header1(self,
                string
                ):
        if Debug.quiet:
            return
        self.print('\n==== %s ====' % string)

    def header2(self,
                string
                ):
        if Debug.quiet:
            return
        self.print('\n---- %s ----' % string)

    def header3(self,
                string
                ):
        if Debug.quiet:
            return
        self.print('\n~~ %s ~~' % string)

    def print(self,
              string # string to be output
              ):
        if Debug.quiet:
            return

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
        if Debug.quiet:
            return
        string = self.PP.pformat(thing)
        self.print(string)
