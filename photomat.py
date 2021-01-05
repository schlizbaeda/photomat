#!/usr/bin/python3

# photomat.py 
# Copyright (C) 2020 schlizbaeda
#
# photomat.py is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#             
# photomat.py is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with photomat.py. If not, see <http://www.gnu.org/licenses/>.
#
#
# Contributions:
# --------------
# <t.b.d.>
# 
#
# photomat.py uses the following modules:
# ---------------------------------------
#
# * python-omxplayer-wrapper V0.3.3                           LGPL v3
#


import time, random
import os      # getpid(): Get current process id
import sys     # argv[], exitcode
#from omxplayer.player import OMXPlayer
import omxplayer.player
import gpiozero



OMXCOUNT = 4
OMXINSTANCE_NONE = -1 # Error
OMXINSTANCE_IDLE1 = 0
OMXINSTANCE_IDLE2 = 1
OMXINSTANCE_CNTDN = 2 # Countdown
OMXINSTANCE_APPL = 3 # Applause
OMXLAYER = [1, 2, 4, 3]

VID_INDEX = 0
VID_FILENAM = 1


STATE_EXIT = 0
STATE_ERROR = 1

STATE_SELECT_IDLE_VIDEO = 9

STATE_START_IDLE1_VIDEO = 10
STATE_PLAY_IDLE1_VIDEO = 11

STATE_START_IDLE2_VIDEO = 20
STATE_PLAY_IDLE2_VIDEO = 21

STATE_SELECT_CNTDN_VIDEO = 30
STATE_START_CNTDN_VIDEO = 31
STATE_PLAY_CNTDN_VIDEO = 32
STATE_WAIT_CNTDN_VIDEO = 33

	
	
class VideoPlayer:
    def __init__(self, layer):
        self.layer = layer # omxplayer video render layer 
                           # (higher numbers are on top)
        self.fullscreen = '0,0,1919,1079' # TODO: read resolution from system
        self.alpha_start = 0
        self.alpha_start_fadetime = 0
        self.alpha_play = 0
        self.alpha_end = 0
        self.alpha_end_fadetime = 0
        self.last_alpha = 0
        
        self.omxplayer = None
        self.duration = 0 # < 0: An error occurred when examining the duration
        self.position = 0
        self.playback_status = 'None'

    def unload_omxplayer(self):
        if self.omxplayer is not None:
            # Remove current instance of omxplayer even if it is running:
            self.omxplayer.quit()
            self.omxplayer = None
            self.playback_status = 'None'
            ret = 0
        else:
            # The omxplayer instance was already removed:
            ret = 1
        return ret

    def load_omxplayer(self,
                       filenam, args=None,
                       bus_address_finder=None,
                       Connection=None,
                       dbus_name=None,
                       pause=True):
        if self.omxplayer is None:
            # Create a new omxplayer instance:
            try:
                self.omxplayer = omxplayer.player.OMXPlayer(filenam, args,
                                                            bus_address_finder,
                                                            Connection,
                                                            dbus_name,
                                                            pause)
            except:
                ret = 1
            else:
                ret = 0
                self.last_alpha = 0
                try:
                    self.duration = self.omxplayer.duration() # for faster access
                    self.position = 0
                except:
                    # An error occurred when examining the video duration:
                    self.duration = -1
                    ret = 2
        else:
            # The current instance is still running:
            ret = 3
        return ret

    def updt_playback_status(self):
        # returns 'Playing', 'Paused', 'Stopped', 'None', 'Exception <text>'
        if self.omxplayer is None:
            self.playback_status = 'None'
        else:
            try:
                self.position = self.omxplayer.position()
            except Exception as e:
                self.position = -1
                self.playback_status = 'Exception {}: {}'.format(
                                       str(type(e)),
                                       str(e.args[0]))
            else:
                try:
                    # The omxplayer returns 'Playing', 'Paused', 'Stopped':
                    self.playback_status = self.omxplayer.playback_status()
                except Exception as e:
                    self.playback_status = 'Exception {}: {}'.format(
                                           str(type(e)),
                                           str(e.args[0]))
        return self.playback_status

    def set_alpha(self, alpha):
        # Check if change of alpha value is really necessary:
        if alpha < 0: alpha = 0
        if alpha > 255: alpha = 255
        if alpha != self.last_alpha:
            if self.omxplayer is not None:
                try:
                    self.omxplayer.set_alpha(alpha)
                except:
                    pass
                try:
                    self.omxplayer.set_volume(alpha / 255)
                except:
                    pass
            #print('alpha=={}-->volume=={}'.format(alpha, alpha / 255)) # DEBUG!
            self.last_alpha = alpha

    def fade(self):
        if self.omxplayer is None:
            # do nothing!
            pass
        elif self.playback_status == 'Stopped' or \
             self.position >= self.duration:
                alpha = self.alpha_end
                sepperl = 'DEBUG: end reached'
                print(sepperl) # DEBUG!
                self.set_alpha(alpha)
        elif self.playback_status == 'Playing':
            if self.position > (self.duration - self.alpha_end_fadetime):
                # Smooth fading-out at the end of the video sequence:
                tim = 1 - ((self.duration - self.position)
                           / self.alpha_end_fadetime)
                alpha = (self.alpha_play
                         - tim * (self.alpha_play - self.alpha_end)
                        )
                ##sepperl = 'DEBUG: end fade-out: alpha={}'.format(alpha)
                ##print(sepperl) # DEBUG!
            elif self.position < self.alpha_start_fadetime:
                # Smooth fading-in at start of the video sequence:
                
                #tim = self.position / self.alpha_start_fadetime
                # avoid division by zero:
                tim = 1 if self.alpha_start_fadetime == 0 \
                        else self.position / self.alpha_start_fadetime
                alpha = (self.alpha_start 
                         + tim * (self.alpha_play - self.alpha_start)
                        )
                ##sepperl = 'DEBUG: start fade-in: alpha={}'.format(alpha)
                ##print(sepperl) # DEBUG!
            else:
                # current video position somewhere in the middle:
                alpha = self.alpha_play
                ##sepperl = 'DEBUG: else (in the middle)'
                ##print(sepperl) # DEBUG!
            self.set_alpha(alpha)
            

class StateMachine:
    def __init__(self):
        self.cmdlin_params = sys.argv[1:]
        self.exitcode = 0
        
        #self.videos_idle = ['/home/pi/Videos/Animationen_converted.mp4',
        #                    '/home/pi/Videos/Günter Grünwald - Saupreiß.mp4',
        #                    '/home/pi/Videos/Sprachprobleme im Biergarten.mp4',
        #                    '/home/pi/Videos/Der weiß-blaue Babystrampler.mp4',
        #                   ]
        #self.videos_idle = ['/home/pi/Videos/idle01.mp4',
        #                    '/home/pi/Videos/idle02.mp4',
        #                    '/home/pi/Videos/idle03.mp4',
        #                    '/home/pi/Videos/idle04.mp4',
        #                    '/home/pi/Videos/idle05.mp4',
        #                    '/home/pi/Videos/idle07.mp4',
        #                    '/home/pi/Videos/idle08.mp4',
        #                    '/home/pi/Videos/idle09.mp4']
        
        
        # Test videos with durations from 0:03 to 0:22
        # by www.studioschraut.de from vimeo:
        # Download them from https://vimeo.com/studioschraut.de
        self.videos_idle = ['/home/pi/Videos/01_CD Promo on Vimeo.mp4',
                            '/home/pi/Videos/02_WIDESCREEN SHOW Intro on Vimeo.mp4',
                            #'/home/pi/Videos/03_Messe on Vimeo.mp4',
                            '/home/pi/Videos/04_SFT SPOT TV Commercial on Vimeo.mp4',
                            '/home/pi/Videos/05_Play Vanilla TV Spot on Vimeo.mp4'#,
                            #'/home/pi/Videos/06_PCG PP Commercial on Vimeo.mp4'
                           ]
        self.videos_cntdn = ['/home/pi/Videos/Der weiß-blaue Babystrampler.mp4',
                             '/home/pi/Videos/Sprachprobleme im Biergarten.mp4']
        self.videos_appl = ['/home/pi/Videos/applause00.mp4',
                            '/home/pi/Videos/applause01.mp4',
                            '/home/pi/Videos/applause02.mp4',
                            '/home/pi/Videos/applause03.mp4',
                            '/home/pi/Videos/applause04.mp4',
                            '/home/pi/Videos/applause05.mp4',
                            '/home/pi/Videos/applause06.mp4']

        # Create four instances of omxplayer management:
        self.pl = [None, None, None, None]
        self.pl[OMXINSTANCE_IDLE1] = VideoPlayer(OMXLAYER[OMXINSTANCE_IDLE1])
        self.pl[OMXINSTANCE_IDLE2] = VideoPlayer(OMXLAYER[OMXINSTANCE_IDLE2])
        self.pl[OMXINSTANCE_CNTDN] = VideoPlayer(OMXLAYER[OMXINSTANCE_CNTDN])
        self.pl[OMXINSTANCE_APPL] = VideoPlayer(OMXLAYER[OMXINSTANCE_APPL])
        
        self.pl[OMXINSTANCE_IDLE1].fullscreen = '860,50,1820,590' # DEBUG!
        self.pl[OMXINSTANCE_IDLE2].fullscreen = '900,50,1860,590' # DEBUG!
        self.pl[OMXINSTANCE_CNTDN].fullscreen = '880,70,1840,610' # DEBUG!
        self.pl[OMXINSTANCE_APPL].fullscreen = '800,100,1760,640' # DEBUG!
        

        # Non-video properties:
        self.timeslot = 0.02
        self.debugrandom_idle = 0 # DEBUG!
        self.debugrandom_cntdn = 0 # DEBUG!
        self.debugrandom_appl = 0 # DEBUG!
        
        # GPIO access:
        self.gpio_buzzer = gpiozero.Button(17) # J8 pin 11
        self.gpio_triggerpin = gpiozero.LED(7) # J8 pin 26
        
        # Initialisation of the state machine:
        self.errmsg = ''
        self.state = STATE_SELECT_IDLE_VIDEO

    def state_name(self, state=-1):
        if state == -1:
            state = self.state
        
        if state == STATE_EXIT:
            name = 'STATE_EXIT'
        elif state == STATE_ERROR:
            name = 'STATE_ERROR'
        elif state == STATE_SELECT_IDLE_VIDEO:
            name = 'STATE_SELECT_IDLE_VIDEO'
        elif state == STATE_START_IDLE1_VIDEO:
            name = 'STATE_START_IDLE1_VIDEO'
        elif state == STATE_PLAY_IDLE1_VIDEO:
            name = 'STATE_PLAY_IDLE1_VIDEO'
        elif state == STATE_START_IDLE2_VIDEO:
            name = 'STATE_START_IDLE2_VIDEO'
        elif state == STATE_PLAY_IDLE2_VIDEO:
            name = 'STATE_PLAY_IDLE2_VIDEO'
        elif state == STATE_SELECT_CNTDN_VIDEO:
            name = 'STATE_SELECT_CNTDN_VIDEO'
        elif state == STATE_START_CNTDN_VIDEO:
            name = 'STATE_START_CNTDN_VIDEO'
        elif state == STATE_PLAY_CNTDN_VIDEO:
            name = 'STATE_PLAY_CNTDN_VIDEO'
        elif state == STATE_WAIT_CNTDN_VIDEO:
            name = 'STATE_WAIT_CNTDN_VIDEO'
        else:
            name = '<unknown state>'
        return name

    def random_video(self, instance):
        if instance == OMXINSTANCE_IDLE1 or \
           instance == OMXINSTANCE_IDLE2:
                #index = random.randint(0, len(self.videos_idle) - 1)
                index = self.debugrandom_idle # DEBUG!
                filenam = self.videos_idle[index]
                self.debugrandom_idle += 1 # DEBUG!
                if self.debugrandom_idle >= len(self.videos_idle): # DEBUG!
                    self.debugrandom_idle = 0 # DEBUG!
        elif instance == OMXINSTANCE_CNTDN:
                #index = random.randint(0, len(self.videos_cntdn) - 1)
                index = self.debugrandom_cntdn # DEBUG!
                filenam = self.videos_cntdn[index]
                self.debugrandom_cntdn += 1 # DEBUG!
                if self.debugrandom_cntdn >= len(self.videos_cntdn): # DEBUG!
                    self.debugrandom_cntdn = 0 # DEBUG!
        elif instance == OMXINSTANCE_APPL:
                #index = random.randint(0, len(self.videos_appl) - 1)
                index = self.debugrandom_appl # DEBUG!
                filenam = self.videos_appl[index]
                self.debugrandom_appl += 1 # DEBUG!
                if self.debugrandom_appl >= len(self.videos_appl): # DEBUG!
                    self.debugrandom_appl = 0 # DEBUG!
        else:
                index = -1
                filenam = None
        return [index, filenam]

    def get_idle_instance_waiting(self):
        if self.pl[OMXINSTANCE_IDLE1].playback_status == 'None' or \
           self.pl[OMXINSTANCE_IDLE1].playback_status[0:9] == 'Exception' or \
           self.pl[OMXINSTANCE_IDLE1].playback_status == 'Stopped':
               ret = OMXINSTANCE_IDLE1
        elif self.pl[OMXINSTANCE_IDLE2].playback_status == 'None' or \
             self.pl[OMXINSTANCE_IDLE2].playback_status[0:9] == 'Exception' or \
             self.pl[OMXINSTANCE_IDLE2].playback_status == 'Stopped':
               ret = OMXINSTANCE_IDLE2
        else:
               # There is no free idle-instance to init with a new video file:
               ret = OMXINSTANCE_NONE
        return ret

    def manage_players(self):
        [pl.updt_playback_status() for pl in self.pl]
        #for pl in self.pl[OMXINSTANCE_IDLE1:OMXINSTANCE_APPL + 1]:
        for pl in self.pl:
            # Delete finished omxplayer instances: 
            if pl.playback_status == 'Stopped' or \
               pl.playback_status[0:9] == 'Exception':
                pl.unload_omxplayer()
            # video fading:
            pl.fade()


    #### Common states ####
    def state_error(self):
        print('ERROR: {}'.format(self.errmsg))
        self.state = STATE_EXIT

    #### Idle video states ####
    def state_select_idle_video(self):
        inst = self.get_idle_instance_waiting()
        if inst == OMXINSTANCE_NONE:
            # Do nothing if there is no free idle-instance.
            # Even don't touch the state of the state machine.
            pass
        else:
            # Initialise a new omxplayer instance with a random video file:
            video = self.random_video(inst)
            if video[VID_INDEX] >= 0:
                self.pl[inst].alpha_start = 0
                self.pl[inst].alpha_start_fadetime = 4
                self.pl[inst].alpha_play = 255
                self.pl[inst].alpha_end = 0
                self.pl[inst].alpha_end_fadetime = 4
                self.pl[inst].last_alpha = 0
                
                dbus_path = 'org.mpris.MediaPlayer2.omxplayer{}_{}'\
                            .format(os.getpid(), inst)
                self.pl[inst].load_omxplayer(
                    video[VID_FILENAM],
                    ['--win', self.pl[inst].fullscreen,
                     '--aspect-mode', 'letterbox',
                     '--layer', OMXLAYER[inst],
                     '--alpha', self.pl[inst].last_alpha,
                     '--vol', '-10000'
                    ] + self.cmdlin_params,
                    dbus_name=dbus_path,
                    pause=True)
                ##print('initialised instance {} @ {} with video {} "{}"'.format(
                ##      inst, dbus_path, video[VID_INDEX], video[VID_FILENAM])) # DEBUG!
                print('initialised instance {} with video {} "{}"'.format(
                      inst, video[VID_INDEX], video[VID_FILENAM]))
                if inst == OMXINSTANCE_IDLE1:
                    self.state = STATE_START_IDLE1_VIDEO
                elif inst == OMXINSTANCE_IDLE2:
                    self.state = STATE_START_IDLE2_VIDEO
            else:
                self.errmsg = 'No idle videos available to ' \
                              'initialise instance {}'.format(inst)
                self.state = STATE_ERROR
            
    def state_start_idle_video(self, inst_waiting):
        inst_running = OMXINSTANCE_IDLE1 if inst_waiting != OMXINSTANCE_IDLE1 \
                                         else OMXINSTANCE_IDLE2
        # is the waiting video ...?
        if self.pl[inst_waiting].playback_status == 'None':
            pass
        # is the current video fading out yet?
        if (self.pl[inst_running].duration \
            - self.pl[inst_running].position \
            <= self.pl[inst_running].alpha_end_fadetime \
               + 3 * self.timeslot) or \
           (self.pl[inst_running].playback_status
            in ['None', 'Stopped']): # in-statement checks "no video is running"
                    ##print('fade instance {} to instance {}: fade time {}'.format(
                    ##      inst_running, 
                    ##      inst_waiting,
                    ##      self.pl[inst_running].duration - self.pl[inst_running].position)) # DEBUG!
                    if inst_waiting == OMXINSTANCE_IDLE1:
                        self.state = STATE_PLAY_IDLE1_VIDEO
                    elif inst_waiting == OMXINSTANCE_IDLE2:
                        self.state = STATE_PLAY_IDLE2_VIDEO
                    print('instance {} initiated to start'.format(inst_waiting))
        else:
            # do nothing!
            pass

    def state_play_idle_video(self, inst):
        print('instance {} started to play a video'.format(inst))
        self.pl[inst].omxplayer.set_position(0)
        self.pl[inst].set_alpha(self.pl[inst].alpha_start)
        self.pl[inst].omxplayer.play()
        self.state = STATE_SELECT_IDLE_VIDEO

    #### Countdown video states ####
    def state_select_cntdn_video(self, cntdn_fadetime=2):
        print('STATE_SELECT_CNTDN_VIDEO')
        # Create omxplayer instance for countdown video:
        video = self.random_video(OMXINSTANCE_CNTDN)
        if video[VID_INDEX] >= 0:
            self.pl[OMXINSTANCE_CNTDN].alpha_start = 0
            self.pl[OMXINSTANCE_CNTDN].alpha_start_fadetime = cntdn_fadetime
            self.pl[OMXINSTANCE_CNTDN].alpha_play = 255
            self.pl[OMXINSTANCE_CNTDN].alpha_end = 0
            self.pl[OMXINSTANCE_CNTDN].alpha_end_fadetime = cntdn_fadetime
            self.pl[OMXINSTANCE_CNTDN].last_alpha = 0
                
            dbus_path = 'org.mpris.MediaPlayer2.omxplayer{}_{}'\
                        .format(os.getpid(), OMXINSTANCE_CNTDN)
            self.pl[OMXINSTANCE_CNTDN].load_omxplayer(
                video[VID_FILENAM],
                ['--win', self.pl[OMXINSTANCE_CNTDN].fullscreen,
                 '--aspect-mode', 'letterbox',
                 '--layer', OMXLAYER[OMXINSTANCE_CNTDN],
                 '--alpha', self.pl[OMXINSTANCE_CNTDN].last_alpha,
                 '--vol', '-10000'
                ] + self.cmdlin_params,
                dbus_name=dbus_path,
                pause=True)
            print('initialised instance {} with video {} "{}"'.format(
                  OMXINSTANCE_CNTDN, video[VID_INDEX], video[VID_FILENAM]))
        else:
            self.errmsg = 'No countdown videos available to ' \
                          'initialise instance {}'.format(inst)
            self.state = STATE_ERROR
        self.state = STATE_START_CNTDN_VIDEO

    def state_start_cntdn_video(self, cntdn_fadetime=2):
        print('STATE_START_CNTDN_VIDEO')
        for pl in self.pl[OMXINSTANCE_IDLE1:OMXINSTANCE_IDLE2 + 1]:
            if pl.playback_status == 'Playing' or \
               pl.playback_status == 'Paused':
                # initiate now fading of idle video sequence due to countdown:
                pl.alpha_start_fadetime = 0 # exit from eventually fading-in
                pl.alpha_end_fadetime = cntdn_fadetime
                pl.duration = pl.position + cntdn_fadetime + self.timeslot
        self.state = STATE_PLAY_CNTDN_VIDEO

    def state_play_cntdn_video(self):
        print('instance {} started to play a video'.format(OMXINSTANCE_CNTDN))
        self.pl[OMXINSTANCE_CNTDN].omxplayer.set_position(0)
        self.pl[OMXINSTANCE_CNTDN].set_alpha(
             self.pl[OMXINSTANCE_CNTDN].alpha_start)
        self.pl[OMXINSTANCE_CNTDN].omxplayer.play()
        self.state = STATE_WAIT_CNTDN_VIDEO

    def state_wait_cntdn_video(self):
        print('waiting for end of instance {}: now "{}"'.format(
              OMXINSTANCE_CNTDN,
              self.pl[OMXINSTANCE_CNTDN].playback_status))
        if self.pl[OMXINSTANCE_CNTDN].playback_status == 'Playing' or \
           self.pl[OMXINSTANCE_CNTDN].playback_status == 'Paused':
                remaining = self.pl[OMXINSTANCE_CNTDN].duration \
                            - self.pl[OMXINSTANCE_CNTDN].position
                if remaining - 1 <= 0: # switch off trigger pin (falling slope):
                    if self.gpio_triggerpin.is_lit == True:
                        self.gpio_triggerpin.off()
                elif remaining - 2 <= 0: # switch on trigger pin (rising slope):
                    if self.gpio_triggerpin.is_lit == False:
                        self.gpio_triggerpin.on()
        else: # self.pl[OMXINSTANCE_CNTDN] isn't running
               self.state = STATE_EXIT

    #### Loop of the state machine ####    
    def run(self):
        debug = 0
        lastbuzzer = None
        buzzer_debounce = 0
        while self.state:
            debug += 1
            ##print('\ndebug={}  state={} ({})'.format(debug, self.state,
            ##                                         self.state_name()))

            time.sleep(self.timeslot)
            self.manage_players()
            
            buzzer = self.gpio_buzzer.is_pressed
            if buzzer == lastbuzzer:
                buzzer_debounce += 1
            else:
                buzzer_debounce = 0
            lastbuzzer = buzzer
            if buzzer == True and buzzer_debounce == 2:
                print('buzzer was pressed (stable)')
                self.state = STATE_SELECT_CNTDN_VIDEO



            
            if self.state == STATE_ERROR:
                self.state_error()
            elif self.state == STATE_SELECT_IDLE_VIDEO:
                self.state_select_idle_video()
            elif self.state == STATE_START_IDLE1_VIDEO:
                self.state_start_idle_video(OMXINSTANCE_IDLE1)
            elif self.state == STATE_START_IDLE2_VIDEO:
                self.state_start_idle_video(OMXINSTANCE_IDLE2)
            elif self.state == STATE_PLAY_IDLE1_VIDEO:
                self.state_play_idle_video(OMXINSTANCE_IDLE1)
            elif self.state == STATE_PLAY_IDLE2_VIDEO:
                self.state_play_idle_video(OMXINSTANCE_IDLE2)

            elif self.state == STATE_SELECT_CNTDN_VIDEO:
                self.state_select_cntdn_video()
            elif self.state == STATE_START_CNTDN_VIDEO:
                self.state_start_cntdn_video()
            elif self.state == STATE_PLAY_CNTDN_VIDEO:
                self.state_play_cntdn_video()
            elif self.state == STATE_WAIT_CNTDN_VIDEO:
                self.state_wait_cntdn_video()
        # cleanup all omxplayer instances
        for pl in self.pl:
            pl.unload_omxplayer()

if __name__ == '__main__':
    random.seed()
    statemachine = StateMachine()
    statemachine.run()
    sys.exit(statemachine.exitcode)
#EOF


 
