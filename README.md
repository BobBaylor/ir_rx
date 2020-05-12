# ir_rx: A raspberry pi IR receiver
Use a raspberry pi and an IR reveiver IC to decode IR transmissions from my old Yamaha remote control and send SPI packets to a stereo volume control IC.
## Why do this?
To add my own functions to my audio setup without adding yet another remote control.
## What do I need to do this?
Not much:
* A raspberry pi. I think any model will do.
* An IR receiver IC such as the [TSOP382 from Vishay](http://www.vishay.com/docs/82491/tsop382.pdf)
* A [TI PGA2311](http://www.ti.com/lit/ds/symlink/pga2311.pdf) SPI programmable volume control.
* The TI part needs +/- 5 volt power for the analog side. I got the [CUI PDME1-S5-D5-S](https://www.cui.com/product/resource/pdme1-s.pdf) because it's only $5 at digikey.
* Some cabling, bypass capacitors, etc.

The IR receiver IC is designed to work at a specific carrier frequency. My remote control outputs at 40 kHz carrier frequency so that's what I bought. It's pretty cool part. It does quite a bit of processing to reject interference. With only 3 pins, it's insanely easy to use:
* power
* ground
* output (open collector with a 30k pull up)

The TI part has over 100 dB of control range, independent control of left and right gain, a mute pin, and you can get it in a 16 pin DIP so no fancy tools required. The gain = -95 dB + gain_value *.5 dB so a gain_value of 180 (decimal) results in -5 dB gain.

Since the pi is powered from a wall wart that easily sources 1A, I just use some of the digital 5V to power the analog power converter.

pigpio does all real work in a daemon that needs to run for any of this to work. I put a line in `/etc/rc.local`
```
sudo /usr/bin/pigpiod
```
To get the remote_control.py script to run in the background automatically at boot, I put a line in crontab
```
@reboot sudo /home/pi/ir_rx/remote_control.py > /home/pi/ir_rx/rem.log
```
and that seems to do the trick. Of course, remote_control.py needs to be made executable by running chmod +x


