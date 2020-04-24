# ir_rx: A raspberry pi IR receiver
Use a raspberry pi and an IR reveiver IC to decode IR transmissions from my old Yamaha remote control.
## Why do this?
To add my own functions to my audio setup without adding yet another remote control.
## What do I need to do this?
Not much:
* A raspberry pi. I think any model will do.
* An IR receiver IC such as the TSOP382 from Vishay


I'm using an IR rx IC tuned to the 40 kHz carrier frequency that my Yamaha amp uses. This is the data sheet for the Vishay part:

http://www.vishay.com/docs/82491/tsop382.pdf

It's pretty cool part. It does quite a bit of processing to reject interference. With only 3 pins, it's insanely easy to use:
* power
* ground
* output (open collect with a 30k pull up)

Python libraries you will need:
* pigpio
* docopt
docopt is only needed for the CLI to test my IrReceiver class. 
pigpio does all real work in a daemon that needs to run for any of this to work. I put a line in `/etc/rc.local` 
```
sudo /usr/bin/pigpiod
```
It's all explained in the pigpio docs.
