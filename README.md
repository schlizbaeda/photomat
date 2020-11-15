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
It is planned to play a _countdown video_ when a defined event occurs, for
example if a pushbutton connected to a Raspberry Pi's GPIO pin is pressed. When
the countdown is at 0 the program initiates to take a photo.  
Another planned feature is to show an _applause video_ after the photo was
taken successfully. After that the idle loop will continue.

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


