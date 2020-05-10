"""remote_control.py
   be a remote volume control
"""
import pigpio
from ir_volume import SpiVolume
from ir_rx import IrReceiver

def init_devs(pig=None):
    """init the ir receiver and the volume control
    """
    if not pig:
        pig = pigpio.pi()  # open the pi gpio
    vol_opts = {'--address': 120,
                '--baud': 500,
                '--mute': 25,
                '--file': 'ir_vol.txt',
                '--verbose': True,
                '--address': 122,
               }
    spi_vol = SpiVolume(pig, vol_opts)
    ir_opts = {'--glitch': 100,
               '--pin': 3,
               '--pre': 50,
               '--file': '',
               '--post': 15,
               '--raw': '',
               '--short': 2,        # ignore codes w/ < 2 events
               '--tolerance': 15,   # percent deviation from expected periods
               '--verbose': False,
              }
    rcvr = IrReceiver(pig, ir_opts)
    return pig, spi_vol, rcvr


def forever(spi_vol, rcvr):
    """Loop forever, passing ir commands from the ir receiver to the volume control
    """
    while True :
        # each time we rx a complete code, we stop looking
        rcvr.look_for_a_code = True     # keep telling the IrReceiver to look
        for a_cmd in rcvr.get_commands():
            # print(a_cmd)                # tuple of (address, data)
            spi_vol.write_command(a_cmd)


if __name__ == '__main__':
    pig, spi_vol, rcvr = init_devs()
    forever(spi_vol, rcvr)
