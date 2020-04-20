#! /usr/bin/python

import copy
import curses

class Timer(object):
    '''
    Embodies a timer that counts down with fight rounds.  There's optional
    text associated with it (that's shown while the timer is counting down)
    and there's optional actions when the timer actually reaches zero.  This
    is an object built around data that is intended to be kept in the Game File
    data file but that's not strictly required for this object to work.
    '''
    round_count_string = '%d Rnds: '  # assume rounds takes same space as '%d'
    len_timer_leader = len(round_count_string)
    announcement_margin = 0.1  # time removed from an announcement timer so that
                               #   it'll go off at the beginning of a round
                               #   rather than the end

    def __init__(self,
                 details    # dict from the Game File, contains timer's info
                 ):
        self.details = details  # This needs to actually be from the Game File
        self.__complete_me()

    def decrement(self):
        self.details['rounds'] -= 1

    def fire(self,
             owner,          # ThingsInFight object to receive timer action
             window_manager  # GmWindowManager object -- for display
             ):
        ''' Fires the timer. '''

        result = None   # If there's a timer to be added back into the list,
                        #   this will be used to return it

        if 'state' in self.details['actions']:
            owner.details['state'] = self.details['actions']['state']

        if 'announcement' in self.details['actions']:
            window_manager.display_window(
                       ('Timer Fired for %s' % self.details['parent-name']),
                        [[{'text': self.details['actions']['announcement'],
                           'mode': curses.A_NORMAL }]])

        if 'timer' in self.details['actions']:
            result = self.details['actions']['timer']

        return result

    def from_pieces(self,
                    pieces,  # { 'parent-name': <text>, string describing the
                             #                          thing calling the timer
                             #   'rounds': <number>,    rounds until timer fires
                             #                          (3.0 rounds fires at end
                             #                          of 3 rounds; 2.9 rounds
                             #                          fires at beginning of 3
                             #                          rounds).
                             #   'string': <text> or [<text>, <text>, ...],
                             #                          string to display (in
                             #                          fighter's notes) while
                             #                          timer is running
                             #   'actions': {'state': <text>,
                             #                          string describing new
                             #                          state of fighter (see
                             #                          Fighter.conscious_map)
                             #               'announcement': <text>},
                             #                          string to display (in
                             #                          its own window) when
                             #                          timer fires
                             # }
                    ):
        '''
        Creates a new timer from scratch (rather than from data that's already
        in the Game File).
        '''
        self.details = copy.deepcopy(pieces)
        self.__complete_me()

    def get_description(self):
        '''
        Returns a long description of the timer to show the user.
        '''
        result = []  # List of strings, one per line of output
        this_line = []

        rounds = self.details['rounds']

        if ('announcement' in self.details['actions'] and
                        self.details['actions']['announcement'] is not None):
            # Add back in the little bit we shave off of an announcement so
            # that the timer will announce as the creature's round starts
            # rather than at the end.
            rounds += Timer.announcement_margin

        round_count_string = Timer.round_count_string % (rounds +
                                                    Timer.announcement_margin)
        this_line.append(round_count_string)
        if 'announcement' in self.details['actions']:
            this_line.append('[%s]' % self.details['actions']['announcement'])
            result.append(''.join(this_line))
            this_line = []

        if ('state' in self.details['actions'] and
                            self.details['actions']['state'] is not None):
            this_line.append('<%s>' % self.details['actions']['state'])
            result.append(''.join(this_line))
            this_line = []

        if ('string' in self.details and self.details['string'] is not None
                                        and len(self.details['string']) > 0):
            if type(self.details['string']) is list:
                for substring in self.details['string']:
                    this_line.append('%s' % (substring))
                    result.append(''.join(this_line))
                    this_line = []
            else:
                this_line.append('%s' % (self.details['string']))
                result.append(''.join(this_line))
                this_line = []

        if len(this_line) > 0:
            this_line.append('<<UNNAMED TIMER>>')
            result.append(''.join(this_line))

        return result

    def get_one_line_description(self):
        '''
        Returns a short desctiption of the timer to show the user.
        '''
        this_line = []

        rounds = self.details['rounds']

        if ('announcement' in self.details['actions'] and
                        self.details['actions']['announcement'] is not None):
            # Add back in the little bit we shave off of an announcement so
            # that the timer will announce as the creature's round starts
            # rather than at the end.
            rounds += Timer.announcement_margin

        round_count_string = Timer.round_count_string % (rounds +
                                                    Timer.announcement_margin)
        this_line.append(round_count_string)

        needs_headline = True
        if 'announcement' in self.details['actions']:
            this_line.append('[%s]' %
                                    self.details['actions']['announcement'][0])
            needs_headline = False

        if ('string' in self.details and self.details['string'] is not None
                                        and len(self.details['string']) > 0):
            if type(self.details['string']) is list:
                this_line.append('%s' % (self.details['string'][0]))
            else:
                this_line.append('%s' % (self.details['string']))
            needs_headline = False

        if needs_headline:
            this_line.append('<<UNNAMED TIMER>>')

        return ' '.join(this_line)

    def mark_owner_as_busy(self,
                           is_busy = True):
        self.details['busy'] = is_busy

    def __complete_me(self):
        '''
        Fills-in any missing parts of the timer.
        '''
        if self.details is None:
            self.details = {}
        if 'parent-name' not in self.details:
            self.details['parent-name'] = '<< Unknown Parent >>'
        if 'busy' not in self.details:
            self.mark_owner_as_busy(is_busy = False)
        if 'rounds' not in self.details:
            self.details['rounds'] = 1
        if 'actions' not in self.details:
            self.details['actions'] = {}


class TimersWidget(object):
    '''
    Consolodated GUI widget for creating timers.
    '''

    def __init__(self,
                 timers,         # Timers object
                 window_manager  # GmWindowManager object for menus and error
                                 #   reporting
                 ):
        self.__timers = timers
        self.__window_manager = window_manager

    def make_timer(self,
                   timer_recipient_name  # string
                    ):
        '''
        Makes a timer object and adds it to the Timers list.

        Returns: nothing
        '''

        timer_dict = self.make_timer_dict(timer_recipient_name)

        if timer_dict is not None:
            timer_obj = Timer(None)
            timer_obj.from_pieces(timer_dict)
            self.__timers.add(timer_obj)

    def make_timer_dict(self,
                        timer_recipient_name,  # string
                        ):
        '''
        Builds the data dictionary describing a new timer.  Asks all the
        questions necessary to provide the dict with the data it needs.

        Returns: the dict for the new timer.
        '''

        # How long is the timer?

        title = 'Rounds To Wait...'
        height = 1
        width = len(title)
        adj_string = self.__window_manager.input_box(height, width, title)
        if adj_string is None or len(adj_string) <= 0:
            return None
        rounds = int(adj_string)
        if rounds <= 0:
            return None

        # What does the timer do?

        keep_asking_menu = [('yes', True), ('no', False)]
        param = {'announcement': None,
                 'continuous_message': None,
                 'state': None}
        actions_menu = [('message (continuous)',
                                {'doit': self.__continuous_message_action,
                                 'param': param}),
                        ('announcement',
                                {'doit': self.__announcement_action,
                                 'param': param}),
                        #('state change',
                        #        {'doit': self.__new_state_action,
                        #         'param': param})
                        ]
        keep_asking = True
        while keep_asking:
            result = self.__window_manager.menu('Timer Action', actions_menu)
            if result is None:
                return None
            keep_asking = self.__window_manager.menu('Pick More Actions',
                                                     keep_asking_menu)
            if keep_asking is None:
                keep_asking = True

        # Install the timer.

        if 'announcement' in param and param['announcement'] is not None:
            # Shave a little off the time so that the timer will announce
            # as his round starts rather than at the end.
            rounds -= Timer.announcement_margin

        timer_dict = { 'parent-name': timer_recipient_name,
                       'rounds': rounds,
                       'string': param['continuous_message'],
                       'actions': {} }

        if param['announcement'] is not None:
            timer_dict['actions']['announcement'] = param['announcement']
        if param['state'] is not None:
            timer_dict['actions']['state'] = param['state']

        return timer_dict

    # Private and Protected Methods

    def __announcement_action(self,
                              param    # dict passed by the menu handler --
                                       #   contains the announcement text
                                       #   associated with the timer
                              ):
        '''
        Handler for the timer's 'what do I do with this timer' entry.

        Sets the timer up to display a window containing text when the timer
        fires.

        Returns: True -- just so it's not None
        '''
        title = 'Enter the Announcement'
        height = 1
        width = (curses.COLS - 4) - Timer.len_timer_leader
        announcement = self.__window_manager.input_box(height, width, title)
        if announcement is not None and len(announcement) <= 0:
            announcement = None
        param['announcement'] = announcement
        return True

    def __continuous_message_action(self,
                                    param   # dict passed by the menu
                                            #  handler -- contains the text
                                            #  associated with the timer
                                    ):
        '''
        Handler for the timer's 'what do I do with this timer' entry.

        Sets the timer up to display the provided text when the timer is
        displayed.

        Returns: True -- just so it's not None
        '''
        title = 'Enter the Continuous Message'
        height = 1
        width = (curses.COLS - 4) - Timer.len_timer_leader
        string = self.__window_manager.input_box(height, width, title)
        if string is not None and len(string) <= 0:
            string = None
        param['continuous_message'] = string
        return True


    #def __new_state_action(self,
    #                       param    # dict passed by the menu handler --
    #                                #   contains the destination state of the
    #                                #   Fighter associated with the timer
    #                       ):
    #    '''
    #    Handler for the timer's 'what do I do with this timer' entry.

    #    Sets the timer up to change the consciousness state of it's associated
    #    object when the timer fires.

    #    Returns: True -- just so it's not None
    #    '''
    #    state_menu = [(x, x) for x in Fighter.conscious_map.keys()
    #                                                        if x != 'fight']
    #    state_menu = sorted(state_menu, key=lambda x: x[0].upper())
    #    state = self.__window_manager.menu('Which State', state_menu)
    #    if state is not None:
    #        param['state'] = state
    #    return True


class Timers(object):
    '''
    Keeps a list of timers.  There are two parallel lists: 'data' keeps the
    actual data (it's a pointer to the spot in the Game File where the ultimate
    data is stored) while 'obj' keeps Timer objects.
    '''
    def __init__(self,
                 timer_details,  # List from Game File containing timers
                 owner,          # ThingsInFight object to receive timer
                                 #   actions.
                 window_manager  # For displaying error messages
                 ):

        # data and obj are parallel arrays.  'data' is just like it is in the
        # Game File (and, in fact, should point to the Game File data) and
        # 'obj' is the Timer object from that data.
        self.__timers = {'data': timer_details,
                         'obj': []}

        self.__owner = owner

        for timer_data in timer_details:
            timer_obj = Timer(timer_data)
            self.__timers['obj'].append(timer_obj)

        self.__window_manager = window_manager

    def add(self,
            timer   # Timer object
            ):
        '''
        Adds a timer to this list's timers.

        Returns the timer right back, again.
        '''
        self.__timers['data'].append(timer.details)
        self.__timers['obj'].append(timer)
        return timer

    def clear_all(self):
        ''' Removes all of this list's timers. '''
        # I think I have to pop the timer data, individually, because setting
        # ['data'] to [] would just remove our pointer to the Game File data
        # without modifying the Game File data.
        while len(self.__timers['data']) > 0:
            self.__timers['data'].pop()
        self.__timers['obj'] = []

    def decrement_all(self):
        ''' Decrements all timers. '''
        for timer_obj in self.__timers['obj']:
            timer_obj.decrement()

    def get_all(self):
        ''' Returns a complete list of this list's Timer objects.  '''
        return self.__timers['obj']

    def is_busy(self):
        '''Returns 'True' if a current timer has the owner marked as busy.'''
        for timer_obj in self.__timers['obj']:
            if timer_obj.details['busy']:
                return True
        return False

    def remove_expired_keep_dying(self):
        '''
        Removes expired timers BUT KEEPS the timers that are dying this
        round.  Call this at the beginning of the round.  Standard timers that
        die this round are kept so that they're shown.

        Returns nothing.
        '''
        remove_these = []
        for index, timer in enumerate(self.__timers['obj']):
            if timer.details['rounds'] < 0:     # < keeps the timers dying
                                                #   this round
                remove_these.insert(0, index)   # largest indexes last

        for index in remove_these:
            self.__fire_timer(self.__timers['obj'][index])
            self.remove_timer_by_index(index)

    def remove_expired_kill_dying(self):
        '''
        Removes expired timers AND REMOVES the timers that are dying this
        round.  Call this at the end of the round to scrape off the timers
        that expire this round.

        Returns nothing.
        '''

        # TODO: should I just reverse the order we go through the timer list?
        remove_these = []
        for index, timer in enumerate(self.__timers['obj']):
            if timer.details['rounds'] <= 0:    # <= kills the timers dying
                                                #   this round
                remove_these.insert(0, index)   # largest indexes last
        for index in remove_these:
            self.__fire_timer(self.__timers['obj'][index])
            self.remove_timer_by_index(index)

    def remove_timer_by_index(self,
                              index  # Index of the timer to be removed
                              ):
        '''
        Removes a timer from the timer list.

        Returns nothing.
        '''
        del self.__timers['data'][index]
        del self.__timers['obj'][index]

    #
    # Private methods
    #

    def __fire_timer(self,
                     timer  # Timer object
                     ):
        '''
        Has the timer do whatever it does when it fires (i.e., when its time
        runs out).

        Returns nothing.
        '''
        new_timer = timer.fire(self.__owner, self.__window_manager)
        if new_timer is not None:
            self.add(Timer(new_timer))
