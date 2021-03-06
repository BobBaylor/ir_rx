#!/usr/bin/python3
"""remote_control.py
   be a remote volume control
"""
import time
import pigpio
from spi_volume import SpiVolume
from ir_rx import IrReceiver

def init_devs(pig=None):
    """init the ir receiver and the volume control
    """
    if not pig:
        pig = pigpio.pi()  # open the pi gpio

    spi_vol = SpiVolume(pig, **{'--baud': 500,
                                # '--mute': 25,
                                '--init': 180, # init at -95 + 180 * 0.5 dB = -5 dB
                                # '--file': '',  # '/home/pi/ir_rx/ir_vol.txt',
                                # '--verbose': False,
                                # '--address': 122,
                               })

    rcvr = IrReceiver(pig, **{'--glitch': 100,
                              '--pin': 3,
                              '--pre': 50,
                              '--file': '',
                              '--post': 15,
                              '--raw': '',
                              '--short': 2,        # ignore codes w/ < 2 events
                              '--tolerance': 15,   # percent deviation from expected periods
                              '--verbose': False,
                             })
    return pig, spi_vol, rcvr


def forever(spi_vol, rcvr):
    """Loop forever, passing ir commands from the ir receiver to the volume control
    """
    while True:
        # each time we rx a complete code, we stop looking
        rcvr.look_for_a_code = True     # keep telling the IrReceiver to look
        for a_cmd in rcvr.get_commands():
            # print(a_cmd)                # tuple of (address, data)
            spi_vol.write_command(a_cmd)
        time.sleep(0.05)

if __name__ == '__main__':
    pig, spi_vol, rcvr = init_devs()
    forever(spi_vol, rcvr)
