#!/usr/bin/python3

# photomat.py 
# Copyright (C) 2020-2021 schlizbäda
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


# TODO:
# - get video parameters (transparency, fade times) from cfg resp. meta files

import time, random
import os      # getpid(): Get current process id
import sys     # argv[], exitcode
#from omxplayer.player import OMXPlayer
import omxplayer.player
import gpiozero


OMXINSTANCE_ERR_NO_VIDEO = -2 # No video defined for idle/applause
OMXINSTANCE_NONE = -1 # No free omxplayer instance
OMXINSTANCE_IDLE1 = 0
OMXINSTANCE_IDLE2 = 1
OMXINSTANCE_CNTDN = 2 # Countdown
####OMXINSTANCE_APPL = 3 # Applause
OMXLAYER = [2, 1, 3]

VID_INDEX = 0
VID_FILENAM = 1

FADETIME_IDLE_START = 0.75
FADETIME_IDLE_END = 0.75
FADETIME_CNTDN_START = 0.75
FADETIME_CNTDN_END = 0.75


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
STATE_WAIT1_CNTDN_VIDEO = 33
STATE_SELECT_APPL_VIDEO = 34
STATE_WAIT2_CNTDN_VIDEO = 35

VERBOSE_NONE = 0
VERBOSE_ERROR = 1
VERBOSE_STATE = 2
VERBOSE_STATE_PROGRESS = 3
VERBOSE_GPIO = 4
VERBOSE_VIDEOINFO = 5
VERBOSE_ACTION = 6
#VERBOSE_DETAIL = 7
VERBOSITY = VERBOSE_ACTION # todo: CMDLIN_PARAM

def print_verbose(txt, verbosity, newline=True):
    if VERBOSITY >= verbosity:
        if newline: print()
        print(txt, end='', flush=True)	
	
class VideoPlayer:
    def __init__(self, layer):
        self.layer = layer # omxplayer video render layer 
                           # (higher numbers are on top)
        self.fullscreen = '0,0,1919,1079' # TODO: read resolution from system
        self.fadetime_start = 0
        self.fadetime_end = 0
        self.alpha_start = 0
        self.alpha_play = 0
        self.alpha_end = 0
        self.gpio_pin = None
        self.gpio_on = 0
        self.gpio_off = 0
        
        self.last_alpha = 0
        
        self.omxplayer = None
        self.duration = 0 # < 0: An error occurred when examining the duration
        self.position = 0
        self.playback_status = 'None'
        self.is_fading = False

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
                    # store video sequence duration in the class property
                    # self.duration to get faster access on repeated calls:
                    self.duration = self.omxplayer.duration()
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
        # Returns 'Playing', 'Paused', 'Stopped', 'None', 'Exception <text>'
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
            self.last_alpha = alpha

    def fade(self):
        if self.omxplayer is None:
            # do nothing!
            self.is_fading = False
        elif self.playback_status == 'Stopped' or \
             self.position >= self.duration:
                # End of video sequence reached:
                alpha = self.alpha_end
                self.set_alpha(alpha)
                self.is_fading = False
        elif self.playback_status == 'Playing':
            if self.position > (self.duration - self.fadetime_end):
                # Smooth fading-out at the end of the video sequence:
                tim = 1 - ((self.duration - self.position)
                           / self.fadetime_end)
                alpha = (self.alpha_play
                         - tim * (self.alpha_play - self.alpha_end)
                        )
                self.is_fading = True
            elif self.position < self.fadetime_start:
                # Smooth fading-in at start of the video sequence:
                
                #tim = self.position / self.fadetime_start
                # avoid division by zero:
                tim = 1 if self.fadetime_start == 0 \
                        else self.position / self.fadetime_start
                alpha = (self.alpha_start 
                         + tim * (self.alpha_play - self.alpha_start)
                        )
                self.is_fading = True
            else:
                # current video position somewhere in the middle:
                alpha = self.alpha_play
                self.is_fading = False
            self.set_alpha(alpha)
            
            # Check GPIO signaling:
            if type(self.gpio_pin) == gpiozero.output_devices.LED:
                remaining = self.duration - self.position
                if remaining - self.gpio_off <= 0:
                    # switch off trigger pin (falling slope)
                    if self.gpio_pin.is_lit == True:
                        self.gpio_pin.off()
                        print_verbose(
                             '    -> camera trigger signal via GPIO stopped. ',
                             VERBOSE_GPIO)
                elif remaining - self.gpio_on <= 0:
                    # switch on trigger pin (rising slope):
                    if self.gpio_pin.is_lit == False:
                        self.gpio_pin.on()
                        print_verbose(
                             '    -> camera trigger signal via GPIO started. ',
                             VERBOSE_GPIO)



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
        # Download them from https://vimeo.com/studioschraut
        self.videos_idle = ['/home/pi/Videos/01_CD Promo on Vimeo.mp4',
                            '/home/pi/Videos/02_WIDESCREEN SHOW Intro on Vimeo.mp4',
                            #'/home/pi/Videos/03_Messe on Vimeo.mp4',
                            '/home/pi/Videos/04_SFT SPOT TV Commercial on Vimeo.mp4',
                            '/home/pi/Videos/05_Play Vanilla TV Spot on Vimeo.mp4'#,
                            #'/home/pi/Videos/06_PCG PP Commercial on Vimeo.mp4'
                           ]
        #self.videos_cntdn = ['/home/pi/Videos/Der weiß-blaue Babystrampler.mp4',
        #                     '/home/pi/Videos/Sprachprobleme im Biergarten.mp4']
        self.videos_cntdn = ['/home/pi/Videos/Disturbed_LandOfConfusion16s.mp4']
        self.videos_appl = ['/home/pi/Videos/AlanWalker_Spectre15s.mp4']
        #self.videos_appl = ['/home/pi/Videos/applause00.mp4',
        #                    '/home/pi/Videos/applause01.mp4',
        #                    '/home/pi/Videos/applause02.mp4',
        #                    '/home/pi/Videos/applause03.mp4',
        #                    '/home/pi/Videos/applause04.mp4',
        #                    '/home/pi/Videos/applause05.mp4',
        #                    '/home/pi/Videos/applause06.mp4']

        # Create three instances of omxplayer management:
        self.manage_instance = 0
        self.pl = [None, None, None]
        self.pl[OMXINSTANCE_IDLE1] = VideoPlayer(OMXLAYER[OMXINSTANCE_IDLE1])
        self.pl[OMXINSTANCE_IDLE2] = VideoPlayer(OMXLAYER[OMXINSTANCE_IDLE2])
        self.pl[OMXINSTANCE_CNTDN] = VideoPlayer(OMXLAYER[OMXINSTANCE_CNTDN])
        
        self.pl[OMXINSTANCE_IDLE1].fullscreen = '760,50,1720,590' # DEBUG!
        self.pl[OMXINSTANCE_IDLE2].fullscreen = '770,50,1730,590' # DEBUG!
        self.pl[OMXINSTANCE_CNTDN].fullscreen = '780,70,1740,610' # DEBUG!
        
        # GPIO access:
        self.gpio_buzzer = gpiozero.Button(17) # J8 pin 11
        self.gpio_triggerpin = gpiozero.LED(7) # J8 pin 26
        self.gpio_exitbtn = gpiozero.Button(23) # J8 pin 16
        
        # Non-video properties:
        self.timeslot = 0.02 # todo: CMDLIN_PARAM
        
        self.randomindex_idle = 0  # -1 random selection 0 continuous selection
        self.randomindex_cntdn = 0 # -1 random selection 0 continuous selection
        self.randomindex_appl = 0  # -1 random selection 0 continuous selection
        
        # Initialisation of the state machine:
        self.errmsg = ''
        self.state = STATE_SELECT_IDLE_VIDEO
        self.buzzer_enabled = True

    def state_name(self, state=-1):
        if state == -1:
            state = self.state
        
        if state == STATE_EXIT:
            name = 'STATE_EXIT'
        elif state == STATE_ERROR:
            name = 'STATE_ERROR'
        elif state == STATE_SELECT_APPL_VIDEO:
            name = 'STATE_SELECT_APPL_VIDEO'
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
        elif state == STATE_WAIT1_CNTDN_VIDEO:
            name = 'STATE_WAIT1_CNTDN_VIDEO'
        elif state == STATE_WAIT2_CNTDN_VIDEO:
            name = 'STATE_WAIT2_CNTDN_VIDEO'
        else:
            name = '<unknown state>'
        return name

    def random_video(self, instance, applause):
        if instance == OMXINSTANCE_IDLE1 or \
           instance == OMXINSTANCE_IDLE2:
                if applause == False: # select an idle video sequence:
                    if self.randomindex_idle < 0:
                        # random selection:
                        index = random.randint(0, len(self.videos_idle) - 1)
                    else:
                        # continuous selection:
                        index = self.randomindex_idle
                        filenam = self.videos_idle[index]
                        self.randomindex_idle += 1
                        if self.randomindex_idle >= len(self.videos_idle):
                            self.randomindex_idle = 0
                else: # select an applause video sequence:
                    if self.randomindex_appl < 0:
                        # random selection:
                        index = random.randint(0, len(self.videos_appl) - 1)
                    else:
                        # continuous selection:
                        index = self.randomindex_appl
                        filenam = self.videos_appl[index]
                        self.randomindex_appl += 1
                        if self.randomindex_appl >= len(self.videos_appl):
                            self.randomindex_appl = 0
        elif instance == OMXINSTANCE_CNTDN:
                if self.randomindex_cntdn < 0:
                    # random selection:
                    index = random.randint(0, len(self.videos_cntdn) - 1)
                else:
                    # continuous selection:
                    index = self.randomindex_cntdn
                    filenam = self.videos_cntdn[index]
                    self.randomindex_cntdn += 1
                    if self.randomindex_cntdn >= len(self.videos_cntdn):
                        self.randomindex_cntdn = 0
        else:
                index = -1
                filenam = None
        return [index, filenam]

    def get_idle_instance_waiting(self):
        if self.pl[OMXINSTANCE_IDLE1].playback_status == 'None' or \
           self.pl[OMXINSTANCE_IDLE1].playback_status == 'Stopped' or \
           self.pl[OMXINSTANCE_IDLE1].playback_status[0:9] == 'Exception':
               inst = OMXINSTANCE_IDLE1
        elif self.pl[OMXINSTANCE_IDLE2].playback_status == 'None' or \
             self.pl[OMXINSTANCE_IDLE2].playback_status == 'Stopped' or \
             self.pl[OMXINSTANCE_IDLE2].playback_status[0:9] == 'Exception':
               inst = OMXINSTANCE_IDLE2
        else:
               # There is no free idle-instance to init with a new video file:
               inst = OMXINSTANCE_NONE
        return inst

    def select_video(self, fadetime):
        inst = self.get_idle_instance_waiting()
        if inst == OMXINSTANCE_NONE:
            # Do nothing if there is no free idle-instance.
            # Even don't touch the state of the state machine.
            pass
        else:
            # Initialise a new omxplayer instance with a random video file:
            video = self.random_video(inst,
                                      self.state == STATE_SELECT_APPL_VIDEO)
            if video[VID_INDEX] >= 0:
                self.pl[inst].fadetime_start = fadetime
                self.pl[inst].fadetime_end = fadetime
                self.pl[inst].alpha_start = 0
                self.pl[inst].alpha_play = 255
                self.pl[inst].alpha_end = 0
                self.pl[inst].last_alpha = 0
                
                dbus_path = 'org.mpris.MediaPlayer2.omxplayer{}_{}'\
                            .format(os.getpid(), inst)
                ## Error-Gaudi:
                #print_verbose('#Error-Gaudi: wait for 0.25sec', VERBOSE_ERROR)
                #time.sleep(0.25) # Error-Gaudi
                
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

                ## Error-Gaudi:
                #print_verbose('#Error-Gaudi: wait for 0.05sec', VERBOSE_ERROR)
                #time.sleep(0.05) # Error-Gaudi
                
                ## Error-Gaudi:
                #if self.pl[inst].omxplayer is None: # Error-Gaudi
                #    print_verbose(
                #      '#Error-Gaudi: self.select_video:\n'
                #      '#Error-Gaudi: load_omxplayer() results in None!\n'
                #      '#Error-Gaudi: videofile=={}'.format(video[VID_FILENAM]), 
                #      VERBOSE_ERROR) # Error-Gaudi

                print_verbose(
                    '    instance[{}] initialised with video[{}] "{}" '.format(
                    inst, video[VID_INDEX], video[VID_FILENAM]),
                    VERBOSE_VIDEOINFO)
            else:
                inst = OMXINSTANCE_ERR_NO_VIDEO
        return inst

    def manage_players(self):
        self.pl[self.manage_instance].updt_playback_status()
        # Delete finished omxplayer instance: 
        if self.pl[self.manage_instance].playback_status == 'Stopped' or \
           self.pl[self.manage_instance].playback_status[0:9] == 'Exception':
            self.pl[self.manage_instance].unload_omxplayer()
            # ---- Moved from self.state_play_idle_video() to here! ----
            # Enable buzzer if countdown video has been completely
            # finished and unloaded:
            if self.manage_instance == OMXINSTANCE_CNTDN:
                self.buzzer_enabled = True
        # video fading:
        self.pl[self.manage_instance].fade()

        self.manage_instance += 1
        if self.manage_instance >= len(self.pl):
            self.manage_instance = 0


    #### Common states ####
    def state_error(self):
        print('ERROR: {}'.format(self.errmsg))
        self.state = STATE_EXIT

    #### Idle video states ####
    def state_select_idle_video(self, idle_fadetime=FADETIME_IDLE_START):
        if False == \
           self.pl[OMXINSTANCE_IDLE1].is_fading or \
           self.pl[OMXINSTANCE_IDLE2].is_fading or \
           self.pl[OMXINSTANCE_CNTDN].is_fading:
                inst = self.select_video(idle_fadetime)
                if inst == OMXINSTANCE_NONE:
                    # Do nothing if there is no free idle-instance.
                    # Even don't touch the state of the state machine.

                    ## Error-Gaudi:
                    #print_verbose('#Error-Gaudi: OMXINSTANCE_NONE!', 
                    #         VERBOSE_ERROR) # Error-Gaudi
                    pass
                elif inst == OMXINSTANCE_IDLE1:
                    self.state = STATE_START_IDLE1_VIDEO \
                                 if self.state != STATE_SELECT_APPL_VIDEO \
                                 else STATE_WAIT2_CNTDN_VIDEO
                elif inst == OMXINSTANCE_IDLE2:
                    self.state = STATE_START_IDLE2_VIDEO \
                                 if self.state != STATE_SELECT_APPL_VIDEO \
                                 else STATE_WAIT2_CNTDN_VIDEO
                else: # OMXINSTANCE_ERR_NO_VIDEO
                    self.errmsg = 'No idle videos available to ' \
                                  'initialise instance {}'.format(inst)
                    self.exitcode = 1
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
            <= self.pl[inst_running].fadetime_end \
               + 3 * self.timeslot) \
           or \
           (self.pl[inst_running].playback_status
            in ['None', 'Stopped']): # in-command checks "no video is running"
                    if inst_waiting == OMXINSTANCE_IDLE1:
                        self.state = STATE_PLAY_IDLE1_VIDEO
                    elif inst_waiting == OMXINSTANCE_IDLE2:
                        self.state = STATE_PLAY_IDLE2_VIDEO
        else:
            # do nothing!
            pass

    def state_play_idle_video(self, inst):
        if self.pl[inst].omxplayer is None:
            ## Error-Gaudi:
            #print_verbose('#Error-Gaudi: state_play_idle_video\n'
            #              '#Error-Gaudi: self.pl[inst].omxplayer is None'
            #              '(inst=={})'.format(inst),
            #              VERBOSE_ERROR) # Error-Gaudi
            
            # On isNone-error set state machine to select a new video:
            self.state = STATE_SELECT_IDLE_VIDEO
        else:    
            self.pl[inst].omxplayer.set_position(0)
            self.pl[inst].set_alpha(self.pl[inst].alpha_start)
            self.pl[inst].omxplayer.play()
            # Important -- This command was moved:
            #self.buzzer_enabled = True # moved to method self.manage_players()
            self.state = STATE_SELECT_IDLE_VIDEO

    #### Countdown video states ####
    def state_select_cntdn_video(self, cntdn_fadetime=FADETIME_CNTDN_START):
        if False == \
           self.pl[OMXINSTANCE_IDLE1].is_fading or \
           self.pl[OMXINSTANCE_IDLE2].is_fading or \
           self.pl[OMXINSTANCE_CNTDN].is_fading:
        
            # Create omxplayer instance for countdown video:
            video = self.random_video(OMXINSTANCE_CNTDN, False)
            if video[VID_INDEX] >= 0:
                self.pl[OMXINSTANCE_CNTDN].fadetime_start = cntdn_fadetime
                self.pl[OMXINSTANCE_CNTDN].fadetime_end = cntdn_fadetime
                self.pl[OMXINSTANCE_CNTDN].alpha_start = 0
                self.pl[OMXINSTANCE_CNTDN].alpha_play = 255
                self.pl[OMXINSTANCE_CNTDN].alpha_end = 0
                self.pl[OMXINSTANCE_CNTDN].gpio_pin = self.gpio_triggerpin
                self.pl[OMXINSTANCE_CNTDN].gpio_on = 2 # todo: METAFILE
                self.pl[OMXINSTANCE_CNTDN].gpio_off = 1 # todo: METAFILE

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
                print_verbose(
                    '    instance[{}] initialised with video[{}] "{}" '.format(
                    OMXINSTANCE_CNTDN, video[VID_INDEX], video[VID_FILENAM]),
                    VERBOSE_VIDEOINFO)
            else:
                self.errmsg = 'No countdown videos available to ' \
                              'initialise instance {}'.format(inst)
                self.exitcode = 1
                self.state = STATE_ERROR
            self.state = STATE_START_CNTDN_VIDEO

    def state_start_cntdn_video(self):
        for pl in self.pl[OMXINSTANCE_IDLE1:OMXINSTANCE_IDLE2 + 1]:
            if pl.playback_status == 'Playing' or \
               pl.playback_status == 'Paused':
                # initiate now fading of idle video sequence due to countdown:
                pl.fadetime_start = 0 # exit from eventually fading-in
                # adjust the fade-out time of the running idle video sequence
                # to the defined fade-out time of the planned countdown video
                # sequence:
                pl.fadetime_end = self.pl[OMXINSTANCE_CNTDN].fadetime_end
                # shorten the duration of the running idle video sequence
                # to "now" + fade_out time of countdown video sequence:
                pl.duration = pl.position + pl.fadetime_end + self.timeslot
        self.state = STATE_PLAY_CNTDN_VIDEO

    def state_play_cntdn_video(self):
        if self.pl[OMXINSTANCE_CNTDN].omxplayer is None:
            ## Error-Gaudi:
            #print_verbose('#Error-Gaudi: self.state_play_cntdn_video:\n'
            #              '#Error-Gaudi: self.pl[OMXINSTANCE_CNTDN].omxplayer'
            #              ' is None!', 
            #              VERBOSE_ERROR) # Error-Gaudi
            self.state = STATE_SELECT_CNTDN_VIDEO
            ## Error-Gaudi:
            #print_verbose('#Error-Gaudi: state was set to {} again due to'
            #              ' isNone-error!'.format(
            #              self.state_name()),
            #              VERBOSE_ERROR) # Error-Gaudi
        else:
            self.pl[OMXINSTANCE_CNTDN].omxplayer.set_position(0)
            self.pl[OMXINSTANCE_CNTDN].set_alpha(
                 self.pl[OMXINSTANCE_CNTDN].alpha_start)
            self.pl[OMXINSTANCE_CNTDN].omxplayer.play()
            self.state = STATE_WAIT1_CNTDN_VIDEO

    def state_wait_cntdn_video(self):
        if self.pl[OMXINSTANCE_CNTDN].playback_status == 'Playing' or \
           self.pl[OMXINSTANCE_CNTDN].playback_status == 'Paused':
            if self.state == STATE_WAIT1_CNTDN_VIDEO and \
               self.pl[OMXINSTANCE_CNTDN].position \
               > self.pl[OMXINSTANCE_CNTDN].fadetime_start:
                   # Unload the idle instances as soon as possible:
                   print_verbose('    unload the idle video instances!',
                                 VERBOSE_ACTION)
                   self.pl[OMXINSTANCE_IDLE1].unload_omxplayer()
                   self.pl[OMXINSTANCE_IDLE2].unload_omxplayer()
                   # Load the first idle instance with applause video:
                   self.state = STATE_SELECT_APPL_VIDEO
                
            # DEBUG! -- check if necessary any longer!!!
            remaining = self.pl[OMXINSTANCE_CNTDN].duration \
                        - self.pl[OMXINSTANCE_CNTDN].position
            if remaining <= self.pl[OMXINSTANCE_CNTDN].fadetime_end:
                # change state of state machine:
                self.state = STATE_START_IDLE1_VIDEO
        else: # self.pl[OMXINSTANCE_CNTDN] isn't running
                self.state = STATE_START_IDLE1_VIDEO

    #### Loop of the state machine ####    
    def run(self):
        last_state = STATE_EXIT

        last_buzzer = None
        buzzer_debounce = 0
        
        last_exitbtn = None
        exitbtn_debounce = 0
        
        while self.state:
            time.sleep(self.timeslot)
            self.manage_players()

            # Print current state of the state machine:
            if self.state != last_state:
                print_verbose('STATE=={}: "{}" '.format(self.state,
                                                        self.state_name()),
                              VERBOSE_STATE)
            else:
                print_verbose('.',
                              VERBOSE_STATE_PROGRESS,
                              newline=False)
            last_state = self.state
            
            # Check for buzzer button
            # and ignore it if it has been already pressed:
            if self.buzzer_enabled:
                buzzer = self.gpio_buzzer.is_pressed
                if buzzer == last_buzzer:
                    buzzer_debounce += 1
                else:
                    buzzer_debounce = 0
                last_buzzer = buzzer
                if buzzer == True and buzzer_debounce == 2:
                    print_verbose('    <= buzzer has been tied to GND' 
                                  ' (debounced) ',
                                  VERBOSE_GPIO)
                    self.buzzer_enabled = False
                    self.state = STATE_SELECT_CNTDN_VIDEO
            
            # Check for exit button:
            exitbtn = self.gpio_exitbtn.is_pressed
            if exitbtn == last_exitbtn:
                exitbtn_debounce += 1
            else:
                exitbtn_debounce = 0
            last_exitbtn = exitbtn
            if exitbtn == True and exitbtn_debounce == 2:
                print_verbose('    <= exitpin has been tied to GND'
                              + ' (debounced) ',
                              VERBOSE_GPIO)
                self.state = STATE_EXIT # exit the state machine loop


            # Check the current state:
            if self.state == STATE_ERROR:
                self.state_error()
            elif self.state == STATE_SELECT_APPL_VIDEO or \
                 self.state == STATE_SELECT_IDLE_VIDEO:
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
            elif self.state == STATE_WAIT1_CNTDN_VIDEO or \
                 self.state == STATE_WAIT2_CNTDN_VIDEO:
                self.state_wait_cntdn_video()
        # cleanup all omxplayer instances
        for pl in self.pl:
            pl.unload_omxplayer()
        if VERBOSITY >= VERBOSE_STATE:
            print()

if __name__ == '__main__':
    random.seed()
    statemachine = StateMachine()
    statemachine.run()
    sys.exit(statemachine.exitcode)
#EOF
