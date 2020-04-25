# ir_volume.py
"""
        Communication is a 16 bit tranfer R7, R6.. R0, L7, L6.. L0
            CS asserts low
            device SDI is latched on the rising edge of clock
            device SDO changes on the falling edge
            CS de-asserts high

        21 20 19 18 17 16 15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
         b  b  b  b  b  b  R  T  n  n  n  n  W  A u2 u1 u0 p2 p1 p0  m  m
         0  0  0  0  0  0  0  0  0  0  0  0  0  0  1  1  0  0  0  0  0  0
            0           0           0           0           C           0

        mm defines the SPI mode.
        Mode POL PHA
        0    0   0
        1    0   1
        2    1   0
        3    1   1

        px is 0 if CEx is active low (default) and 1 for active high.

        ux is 0 if the CEx GPIO is reserved for SPI (default) and 1 otherwise.

        A is 0 for the main SPI, 1 for the auxiliary SPI.

        W is 0 if the device is not 3-wire, 1 if the device is 3-wire. Main SPI only.

        nnnn defines the number of bytes (0-15) to write before switching the MOSI line to
        MISO to read data. This field is ignored if W is not set. Main SPI only.

        T is 1 if the least significant bit is transmitted on MOSI first, the default (0) shifts
        the most significant bit out first. Auxiliary SPI only.

        R is 1 if the least significant bit is received on MISO first, the default (0) receives
        the most significant bit first. Auxiliary SPI only.

        bbbbbb defines the word size in bits (0-32). The default (0) sets 8 bits per word.
        Auxiliary SPI only.

                GPIO       pin  pin    GPIO
                3V3         1    2      5V
                2 (SDA)     3    4      5V
                3 (SCL)     5    6      0V
                4           7    8      14 (TXD)
                0V          9   10      15 (RXD)
                17 (ce1)   11   12      18 (ce0)
                27         13   14      0V
                22         15   16      23
                3V3        17   18      24
                10 (MOSI)  19   20      0V
                9 (MISO)   21   22      25
                11 (SCLK)  23   24      8 (CE0)
                0V         25   26      7 (CE1)
        Init with a dict of all the options when using it stand-alone.
            opts = {
                    '--address': 120,
                    '--baud': 500,
                    '--mute': 25,
                    '--verbose': False,
                   }
"""

import time
import docopt
import pigpio

usage_text = """
 Usage:
  ir_volume  [--address <A>] [--baud <B>] [--mute <M>] [--verbose]
  ir_volume -h | --help

 Options:
  -h --help               Show this screen.
  -a --address <A>        The Yamaha address code we respopns to [default: 122]
  -b --baud <B>           The baud in kbps [default: 100]
  -m --mute <M>           Mute pin GPIO. [default: 25]
  -v --verbose            Print stuff
    """


class SpiVolume():
    """ A class to encapsulate the SPI controlled volume IC
    """
    def __init__(self, pig, opts):
        self.opts = opts
        self.pig = pig
        self.my_address = int(opts['--address'])
        self.mute_pin_bar = int(opts['--mute'])
        self.gain = 0   # same gain is sent to L and R channels

        self.spi_ifc = pig.spi_open(0, int(opts['--baud'])*1000, 0x00C0)
        self.pig.set_mode(self.mute_pin_bar, pigpio.OUTPUT)
        self.mute(False)

        if self.opts['--verbose']:
            hdw_ver = self.pig.get_hardware_revision()
            print('Found hardware ver %06x and using %s kbaud'%(hdw_ver, opts['--baud']))


    def write(self, data):
        if self.opts['--verbose']:
            print('write', data)
        self.pig.spi_xfer(self.spi_ifc, data)


    def mute(self, b_mute=None):
        # no arg to toggle. Otherwise set mute
        mute_bar = self.pig.read(self.mute_pin_bar)
        if b_mute is None:
            self.pig.write(self.mute_pin_bar, 0 if mute_bar else 1)     # toggle
        else:
            self.pig.write(self.mute_pin_bar, 0 if b_mute else 1)     # invert arg


    def is_muted(self):
        return 0 if self.pig.read(self.mute_pin_bar) else 1 # inverted


    def write_command(self, ir_cmd):
        # we only care about 3 commands: volume up, down, and mute
        if ir_cmd[0] != self.my_address:
            return      # ignore nec commands to another address
        if ir_cmd[1] == 27:     # volume up
            if self.is_muted():
                self.mute(False)
            else:
                self.gain += 1
                self.write(bytes([self.gain,self.gain,]))
        elif ir_cmd[1] == 28:   # volume down
            if self.is_muted():
                self.mute(False)
            else:
                self.gain -= 1
                self.write(bytes([self.gain,self.gain,]))
        elif ir_cmd[1] == 26:   # mute (toggle)
            self.mute()         # toggle


def test(opts):
    """ Test the SpiVolume class.
        opts is a dict of command line options
    """
    pig = pigpio.pi()  # open the pi gpio
    spi_vol = SpiVolume(pig, opts)

    t_start = time.time()
    done = False                        # loop until our 10 seconds elapses
    dir = 1                         # start going up
    switched = False
    spi_vol.gain = 64   # start at -95 + 64*.5 dB = -63 dB
    while not done:
        if dir == 1:
            spi_vol.write_command((122, 27))  # volume up
        else:
            spi_vol.write_command((122, 28))  # volume down

        if not switched and time.time() > t_start + 5:  # then go down
            dir = -dir              # -95 + 173*0.5 dB = -8.5 dB
            switched = True

        if time.time() > t_start + 10:  # don't run forever
            done = True
        time.sleep(0.1)

    spi_vol.pig.stop() # Disconnect from Pi.



if __name__ == '__main__':
    opts = docopt.docopt(usage_text, version='0.0.3')
    test(opts)
    if opts['--verbose']:
        print('done')














































