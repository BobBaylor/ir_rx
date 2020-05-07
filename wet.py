#!/usr/bin/env python
""" wet.py
    water logger class
"""

import time
from datetime import datetime
import pigpio


class WaterLogger():
    """ A class to encapsulate the water logger
            opts = {'--file': '/home/pi/wet/waterlog.txt',
                    '--meter': 4           # J8-7
                    '--led': 15            # J8-10
                    '--heartbeat': 1.0
                    '--verbose': 0,
                    '--debounce': 0.09
                   }

        Cleanup can print total_ticks since self.time_start
    """

    def __init__(self, pig, opts):
        self.opts = opts
        self.pig = pig
        self.meter_gpio = int(opts['--meter'])
        self.led_gpio = int(opts['--led'])
        self.led_period = float(opts['--heartbeat']) * 0.5  # led state changes each half period
        self.log_file_name = opts['--file']

        self.pig.set_mode(self.led_gpio, pigpio.OUTPUT)
        self.pig.set_mode(self.meter_gpio, pigpio.INPUT)

        if self.opts['--verbose']:
            hdw_ver = self.pig.get_hardware_revision()
            print('Wet found hardware ver %06x'%(hdw_ver))
            print('  and using GPIO%d and GPIO%d'%(self.meter_gpio, self.led_gpio))
        self.meter_state = self.pig.input(self.meter_gpio)
        self.time_start = self.time_meter = self.time_led = datetime.now()
        self.total_ticks = 0
        self.time_debounce = float(opts['--debounce'])


    def time_difference(self, prev, nxt):
        """ return the difference between 2 timestamps down to the the microsecond
        """
        diff_time = time.mktime(nxt.timetuple()) + nxt.microsecond*1e-6 -\
                    time.mktime(prev.timetuple()) + prev.microsecond*1e-6
        return diff_time


    def sample(self):
        """ Called continually by the main loop to service the water meter.
        """
        # capture the water meter state and a timestamp
        meter_now = self.pig.input(self.meter_gpio)
        time_now = datetime.now()

        # flash the LED on a 1 Hz schedule
        if self.time_difference(self.time_led, time_now) > self.led_period:
            self.time_led = time_now
            led_state_next = 0 if self.pig.read(self.led_gpio) else 1
            self.pig.write(self.led_gpio, led_state_next)

        # after a debounce period, check if the water meter state changed
        if self.time_difference(self.time_meter, time_now) > self.time_debounce:
            if self.meter_state != meter_now:
                if self.opts['--verbose']:
                    print(meter_now, end='')
                self.meter_state = meter_now
                self.time_meter = meter_now
                self.total_ticks += 1
                with open(self.log_file_name, 'a') as fout:
                    fout.write('%s\n' % time_now.strftime('%y-%m-%d %H:%M:%S.%f'))
