# photomat
yet another omxplayer wrapper which plays random videos for intended usage on
photobooth equipment.

## Description
This program uses the `omxplayer` software on the Raspberry Pi to show (short)
videos in a random order. To achieve a smooth fading between two videos this
program uses multiple instances of `omxplayer`.

At the moment there is a loop which manages the video playback by using two
`omxplayer` instances to show some so-called _idle videos_ which should arouse
attention from the audience.  
Further a _countdown video_ will be played if the input GPIO17 (pin 11) is tied
to GND. Two seconds before the countdown video will end, an impulse is provided
at GPIO 7 (pin 26). It takes about one second. This signal may be used to
trigger another device taking a photo.  
After the countdown video has finished an _applause video_ will be selected and
started. It is internally handled like an idle video. The idle loop keeps on
runnung until GPIO17 is tied to GND agin.

## Not yet implemented
* unload idle videoplayer instance after fade-out when countdown is running  
* ignore further pushes on buzzer pushbutton when countdown is running  
* Add fading feature when switching from countdown to applause sequence  
* Exit software when second push button (GPIO23, pin 16) is pressed  
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


