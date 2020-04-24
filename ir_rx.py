# ir_rx.py
# receive IR remote transmisions and operate a volume control


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
    def __init__(self, opts):
        self.opts = opts
        self.pin_ir = int(opts['--pin'])
        self.pig = pigpio.pi()
        if self.opts['--verbose']:
            hdw_ver = self.pig.get_hardware_revision()
            print('Found hardware version %06x and using GPIO%02d'%(hdw_ver, self.pin_ir))

        self.pig.set_mode(self.pin_ir, pigpio.INPUT)
        self.pig.set_glitch_filter(self.pin_ir, int(opts['--glitch'])) # Ignore glitches.
        self.pig.set_pull_up_down(self.pin_ir, pigpio.PUD_UP)
        self.carrier_MHz = 0.04         # 40 kHz - sb a CL arg
        self.last_tick = 0
        self.in_code = False
        self.code = []
        self.codes = []
        self.fetching_code = False
        self.pre_us = int(opts['--pre']) * 1000
        self.post_ms = int(opts['--post'])
        self.tolerance_pct = int(opts['--tolerance'])
        self.glitch_us = int(opts['--glitch'])
        self.short = int(opts["--short"])
        self.last_code = None

    def end_of_code(self):
        if len(self.code) > self.short:
            # normalise(code)
            self.fetching_code = False
            self.codes.append([e[1] for e in self.code])
            if self.opts['--verbose']:
                print('Code Found',self.code[0][0])
            # print('Code Found:','\n'.join(['%r:%5d'%e for e in self.code]))
        else:
            if self.opts['--verbose']:
                print("Short code, probably a repeat, try again")
        self.code = []


    def cbf(self, gpio, level, tick):
        if level != pigpio.TIMEOUT:
            edge = pigpio.tickDiff(self.last_tick, tick)
            self.last_tick = tick

            if self.fetching_code:
                if (edge > self.pre_us) and (not self.in_code): # Start of a code.
                    self.in_code = True
                    self.pig.set_watchdog(self.pin_ir, self.post_ms) # Start watchdog.

                elif (edge > self.post_ms * 1000) and self.in_code: # End of a code.
                    self.in_code = False
                    self.pig.set_watchdog(self.pin_ir, 0) # Cancel watchdog.
                    self.end_of_code()

                elif self.in_code:
                    # flip polarity bc hardware low means burst detected
                    self.code.append((0 if level else 1, edge),)

        else:
            self.pig.set_watchdog(self.pin_ir, 0) # Cancel watchdog.
            if self.in_code:
                self.in_code = False
                self.end_of_code()

    def compare(self, observed, expected):
        for pair in zip(observed, expected):
            if pair[0] < pair[1] * (1.0 - self.tolerance_pct*0.01):
                return False
            if pair[0] > pair[1] * (1.0 + self.tolerance_pct*0.01):
                return False
        return True

    def close(self):
        self.pig.stop() # Disconnect from Pi.

    def to_cycles(self, a_code):
        # a_code is a list, in us
        # so cycles is val_us/period_us or val_us*freq_MHz
        # returns list of floats
        return [self.carrier_MHz * event for event in a_code]

    def is_repeat(self, cycles):
        # a_code is in float cycles
        return self.compare(cycles, [360, 90, 22.5])


    def has_preample(self, cycles):
        # a_code is in float cycles
        return self.compare(cycles, [360, 180,])


    def str_cycles(self, cycles):
        # cycles is in float cycles
        m_str =  '%d: '%(len(cycles),) + ' '.join(['%2.0f'%round(c) for c in cycles])
        return m_str


    def one_mark(self, mark):
        # return a '1', a '0', or an 'x' based on the mark (float cycles)
        if self.compare([mark], [21.0]):
            return '0'
        if self.compare([mark], [66.0]):
            return '1'
        return 'x'  # not a 1 or a 0


    def decode_nec(self, marks):
        # marks is in float cycles. Preamble and spaces have been stripped
        b_str =  ''.join([self.one_mark(c) for c in marks])[::-1]  # binary, reversed
        if self.opts['--verbose']:
            print('b_str', b_str)
        if 'x' in b_str:
            address, command, b_ok = 0, 0, False    # any 'x' was outside of tol
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
        """ possibilties:
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
        # generator to return each valid decoded code, including repeats. consumes the codes
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
    rcvr = IrReceiver(opts)
    cb_func = rcvr.pig.callback(rcvr.pin_ir, pigpio.EITHER_EDGE, rcvr.cbf)
    assert cb_func

    t_start = time.time()
    done = False
    while not done:
        rcvr.fetching_code = True
        while rcvr.fetching_code:
            for a_cmd in rcvr.get_commands():
                print(a_cmd)
            if time.time() > t_start + 10:
                rcvr.close()
                done = True
                break
            time.sleep(0.1)

    # show what we captured - should be empty bc get_commands() drains it
    for a_code in rcvr.codes:
        rcvr.show_code(a_code)

    rcvr.pig.stop() # Disconnect from Pi.





if __name__ == '__main__':
    opts = docopt.docopt(usage_text, version='0.0.3')
    test(opts)
    if opts['--verbose']:
        print('done')
