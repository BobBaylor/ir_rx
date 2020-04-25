# ir_rx.py
# receive IR remote transmisions and (eventually) operate a volume control
"""Notes:
    I've flipped the mark-space terminology bc the bit information is actually in the spaces
    and that seems backwards to me.

    We use the pigpio callback and timeout features to capture tranmissions.

    Internally, time is in us and frequencey in MHz to make easy conversions.

    I see a lot of repeat codes. I need to be carefull to not mute/unmute/mute/unmute;
    volume up/down probably doesn't matter if I get a repeat
"""

import time

import docopt
import pigpio

usage_text = """
 Usage:
  ir_rx  [--glitch <G>] [--pin <I>] [--pre <E>] [--file <F>] [--post <O>] [--raw <R>] [--short <S>] [--tolerance <T>] [--verbose]
  ir_rx -h | --help

 Options:
  -h --help               Show this screen.
  -f --file <F>           File to append codes
  -g --glitch <G>         Glitch in us [default: 100]
  -i --pin <I>            The Broadcom gpio number to use (not J8 pin) [default: 3]
  -o --post <O>           Postamble in ms [default: 15]
  -e --pre <E>            Preamble in ms [default: 50]
  -r --raw <R>            File to append raw cycles
  -s --short <S>          Short code length [default: 2]
  -t --tolerance <T>      Tolerance [default: 15]
  -v --verbose            Print stuff
    """


class IrReceiver():
    """ A class to encapsulate the reception and decoding process.
        Init with a dict of all the options when using it stand-alone.
            opts = {'--glitch': 100,
                    '--pin': 3,
                    '--pre': 50,
                    '--file': '',
                    '--post': 15,
                    '--raw': '',
                    '--short': 2,
                    '--tolerance': 15,
                    '--verbose': False,
                   }
    """
    def __init__(self, pig, opts):
        self.opts = opts
        self.pin_ir = int(opts['--pin'])
        self.pre_us = int(opts['--pre']) * 1000
        self.post_ms = int(opts['--post'])
        self.tolerance_pct = int(opts['--tolerance'])
        self.glitch_us = int(opts['--glitch'])
        self.short = int(opts["--short"])

        self.pig = pig

        if self.opts['--verbose']:
            hdw_ver = self.pig.get_hardware_revision()
            print('Found hardware version %06x and using GPIO%02d'%(hdw_ver, self.pin_ir))

        # setup the pin, the glitch filter, and add a pullup on the pin
        self.pig.set_mode(self.pin_ir, pigpio.INPUT)
        self.pig.set_glitch_filter(self.pin_ir, int(opts['--glitch'])) # Ignore glitches.
        self.pig.set_pull_up_down(self.pin_ir, pigpio.PUD_UP)
        # install the callback
        cb_func = self.pig.callback(self.pin_ir, pigpio.EITHER_EDGE, self.cbf)
        assert cb_func        # the daemon might not be running

        self.carrier_MHz = 0.04         # 40 kHz - sb a CL arg I guess
        self.last_tick = 0
        self.in_code = False
        self.events = []        # the tranmission we're currently building.
        self.codes = []         # all the transmissions we're storing
        self.look_for_a_code = False   # tell the instance to watch the IR. Cleared when one found
        self.last_code = None   # store the last code for use with "repeat" transmission(s)

    def end_of_code(self):
        """ We think we've captured a code.
        """
        if len(self.events) > self.short:
            # normalise(events)
            self.look_for_a_code = False
            self.codes.append([e[1] for e in self.events])
            if self.opts['--verbose']:
                print('Code Found',self.events[0][0])
            # print('Code Found:','\n'.join(['%r:%5d'%e for e in self.events]))
        else:
            if self.opts['--verbose']:
                print("Short code <", self.short)
        self.events = []


    def cbf(self, gpio, level, tick):
        """ The callback function get called once for each event (edge) detected by the daemon.
            gpio is pi GPIO number (which we don't need).
            level is 1 or 0 indicating the state of the pin *after* the edge
            tick is a timer value (default resolution is 5 us) we use to determine length
                of the burst, or space between bursts.
        """
        if level != pigpio.TIMEOUT:    # here's an edge
            edge = pigpio.tickDiff(self.last_tick, tick)
            self.last_tick = tick

            if self.look_for_a_code:
                if (edge > self.pre_us) and (not self.in_code): # Start of a code.
                    self.in_code = True
                    self.pig.set_watchdog(self.pin_ir, self.post_ms) # Start watchdog.

                elif (edge > self.post_ms * 1000) and self.in_code: # End of a code.
                    self.in_code = False
                    self.pig.set_watchdog(self.pin_ir, 0) # Cancel watchdog.
                    self.end_of_code()

                elif self.in_code:
                    # flip polarity bc hardware low means burst detected
                    self.events.append((0 if level else 1, edge),)

        else:   # timeout. Perhaps we have a code to store
            self.pig.set_watchdog(self.pin_ir, 0) # Cancel watchdog.
            if self.in_code:
                self.in_code = False
                self.end_of_code()


    def compare(self, observed, expected):
        """ Handy function to compare an observed list with a test list
            including a tolerance for error in the timing.
            Returns True if observed matches expected within tolerance.
        """
        for pair in zip(observed, expected):
            if pair[0] < pair[1] * (1.0 - self.tolerance_pct*0.01):
                return False
            if pair[0] > pair[1] * (1.0 + self.tolerance_pct*0.01):
                return False
        return True


    def close(self):
        # cleanup
        self.pig.stop() # Disconnect from Pi.


    def to_cycles(self, a_code):
        """ convert code event timings to floats of the cycle counts.
        """
        return [self.carrier_MHz * event for event in a_code]


    def is_repeat(self, cycles):
        # detect the nec 'repeat' transmission
        return self.compare(cycles, [360, 90, 22.5])


    def has_preample(self, cycles):
        # detect the nec preamble
        return self.compare(cycles, [360, 180,])


    def str_cycles(self, cycles):
        # format length: x0 x1 x2 ...
        m_str =  '%d: '%(len(cycles),) + ' '.join(['%2.0f'%round(c) for c in cycles])
        return m_str


    def one_mark(self, mark):
        """ The nec marks and spaces are defined by their cycle count.
            Return a '1', '0', (or 'x' if it matches neither).
            Used by decode_nec() to make a binary repr of the data
        """
        if self.compare([mark], [21.0]):
            return '0'
        if self.compare([mark], [66.0]):
            return '1'
        return 'x'  # not a 1 or a 0


    def decode_nec(self, marks):
        """ Preamble and spaces have been stripped before calling decode_nec().
            Check that all the remaining events are either a 0 or 1
            Convert to bytes and perform the inversion check
            Return the address and command bytes along with a bool indicating valid
        """
        b_str =  ''.join([self.one_mark(c) for c in marks])[::-1]  # binary, reversed
        if self.opts['--verbose']:
            print('b_str', b_str)
        if 'x' in b_str:
            address, command, b_ok = 0, 0, False    # any 'x' was outside of tolerance
        else:
            # separate into 8 bit blocks and convert to int and reverse again
            i_values = [int(b_str[i:i+8], 2) for i in range(0, 32, 8)][::-1]
            # odd values are the bitwise compliment of evens. Should sum to 255
            add_ok = i_values[0] + i_values[1] == 255
            cmd_ok = i_values[2] + i_values[3] == 255
            if self.opts['--verbose']:
                print('values', i_values)
                print(add_ok, cmd_ok, ['{0:08b}'.format(x) for x in i_values])
            address, command, b_ok = i_values[0], i_values[2], add_ok and cmd_ok
        return address, command, b_ok


    def show_code(self, a_code):
        """ For testing. Use get_commands() to get any new transmissions.

            Print the varous possibilties:
                valid preamble and a code
                valid preamble but garbled code  (inversions don't match)
                valid repeat
                total garbage
        """
        # print('%2d,'%len(a_code),','.join(['%5d'%(edge,) for edge in a_code]))
        cycles = self.to_cycles(a_code)
        if self.opts['--verbose']:
            print('\nall cycles', self.str_cycles(cycles))
        if self.opts['--raw']:
            with open(self.opts['--raw'], 'a') as f_out:
                c_str =  '%d,'%(len(cycles),) + ','.join(['%2.0f'%round(c) for c in cycles])
                f_out.write(c_str+'\n')

        if self.is_repeat(cycles):
            print('repeat')
        elif self.has_preample(cycles):
            # it has a preamble. Check that the spaces are OK
            if self.compare(cycles[2::2], [24.0]*32):
                address, command, b_ok = self.decode_nec(cycles[3::2])
                if b_ok:
                    print('code', address, command, b_ok)
                    if self.opts['--file']:
                        with open(self.opts['--file'], 'a') as f_out:
                            f_out.write(','.join([str(x) for x in (address, command)])+'\n')
                else:
                    print('byte check failed')
            else:
                print('bad spaces')
        else:
            print('preamble fail')


    def get_commands(self):
        """ generator to return each valid decoded code,
            'repeat' code returns a copy of the previous code.
            The function consumes the codes list.
        """
        codes_cpy = self.codes[::-1]
        self.codes = []
        while True:
            try:
                a_code = codes_cpy.pop()
            except IndexError:
                break   # should raise StopIteration() if our copy is empty
            cycles = self.to_cycles(a_code)
            if self.is_repeat(cycles):
                yield self.last_code
            elif self.has_preample(cycles):
                # it has a preamble. Check that the spaces are OK
                if self.compare(cycles[2::2], [24.0]*32):
                    address, command, b_ok = self.decode_nec(cycles[3::2])
                    if b_ok:
                        self.last_code = (address, command,)
                        yield (address, command,)



def test(opts):
    """ Test the IrReceiver class.
        opts is a dict of command line options
    """
    pig = pigpio.pi()  # open the pi gpio
    rcvr = IrReceiver(pig, opts)

    t_start = time.time()
    done = False                        # loop until our 10 seconds elapses
    while not done:
        # each time we rx a complete code, we stop looking
        rcvr.look_for_a_code = True     # keep telling the IrReceiver to look

        for a_cmd in rcvr.get_commands():
            print(a_cmd)                # tuple of (address, data)

        if time.time() > t_start + 10:  # don't run forever
            rcvr.close()
            done = True
        time.sleep(0.1)

    rcvr.pig.stop() # Disconnect from Pi.

    # show what we captured - should be empty bc get_commands() drains codes
    for a_code in rcvr.codes:
        rcvr.show_code(a_code)


if __name__ == '__main__':
    opts = docopt.docopt(usage_text, version='0.0.3')
    test(opts)
    if opts['--verbose']:
        print('done')
