# photomat
yet another omxplayer wrapper which plays random videos for intended usage on
photobooth equipment.

## Attention!
Please don't use this repository any longer because it's so buggy!  
There is an improved version of this software in my repository
[`ravidplay`](https://github.com/schlizbaeda/ravidplay)

## GPIO connections
* GPIO17 (pin 11): buzzer push button
* GPIO7 (pin 26): trigger signal for external camera
* GPIO23 (pin 16): a small and hidden switch to exit the software

## Description
This program uses the `omxplayer` software on the Raspberry Pi to show (short)
videos in a random order. To achieve a smooth fading between two videos this
program uses multiple instances of `omxplayer`.

This software starts a loop which manages the video playback by using two
`omxplayer` instances to show some so-called _idle videos_ which should arouse
attention from the audience.  
Further a _countdown video_ will be played if the input GPIO17 is tied to GND.
Two seconds before the countdown video will end, an impulse is provided at 
GPIO7. It takes about one second. This signal may be used to trigger another
device taking a photo. While the countdown video is playing any further ties
to GND of GPIO17 will be ignored. This behaviour avoids errors due to multiple
pushes of the buzzer pushbutton.  
After the countdown video has finished an _applause video_ will be selected and
started. It is internally handled like an idle video. The idle loop keeps on
runnung until GPIO17 is tied to GND again. Now there is a fading between the
countdown video and the applause video

if GPIO23 is tied to GND the video loop will end and the software therefore
exits.

## Not yet implemented
* issue: Select random applause video earlier to get a better fading behaviour.
* get video parameters like transparency, fade times from cfg resp. meta files


## Software Installation on the Raspberry Pi
Clone this repository onto the Raspberry Pi and start the installation
shell script [`setup.sh`](https://github.com/schlizbaeda/photomat/blob/main/photomat-setup.sh)
in an LXTerminal:
```shell
cd /home/pi
git clone https://github.com/schlizbaeda/photomat
cd photomat
./photomat-setup.sh
```
