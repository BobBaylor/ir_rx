# ir_rx: A raspberry pi IR receiver
Use a raspberry pi and an IR reveiver IC to decode IR transmissions from my old Yamaha remote control and send SPI packets to a stereo volume control IC.
## Why do this?
To add my own functions to my audio setup without adding yet another remote control.
## What do I need to do this?
Not much:
* A raspberry pi. I think any model will do.
* An IR receiver IC such as the TSOP382 from Vishay
* A TI PGA2311 SPI programmable volume control.
* The TI part needs +/- 5 volt power for the analog side. I got the CUI PDME1-S5-D5-S because it's only $5 at digikey.
* Some cabling, bypass capacitors, etc.

The IR receiver IC is designed to work at a specific carrier frequency. My remote control outputs at 40 kHz carrier frequency so that's what I bought. This is the data sheet for the Vishay part:

http://www.vishay.com/docs/82491/tsop382.pdf

It's pretty cool part. It does quite a bit of processing to reject interference. With only 3 pins, it's insanely easy to use:
* power
* ground
* output (open collector with a 30k pull up)

and here's the TI part

http://www.ti.com/lit/ds/symlink/pga2311.pdf

It's got over 100 dB of control range, independent control of left and right gain, a mute pin, and you can get it in a 16 pin DIP so no fancy tools required.

This is the +/-5 volt power supply. 

https://www.cui.com/product/resource/pdme1-s.pdf

It works. That's all I want. Since the pi is powered from a wall wart that easily sources 1A, I just use some of the digital 5V to power the analog power converter. 

pigpio does all real work in a daemon that needs to run for any of this to work. I put a line in `/etc/rc.local` 
```
sudo /usr/bin/pigpiod
```
Eventually, I'll get the remote_control.py script to run in the background automatically at boot, but that part seems to hang the pi WiFi, at the moment.


