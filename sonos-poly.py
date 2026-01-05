#!/usr/bin/env python3
"""
Sonos NodeServer for UDI Polyglot v2
by Einstein.42 (James Milne) milne.james@gmail.com
"""

import udi_interface
import sys
import soco
import requests
import json
#add re library
import re

LOGGER = udi_interface.LOGGER
# DD need to get custom params
Custom = udi_interface.Custom

with open('server.json') as data:
    SERVERDATA = json.load(data)
    data.close()
try:
    VERSION = SERVERDATA['credits'][0]['version']
except (KeyError, ValueError):
    LOGGER.info('Version not found in server.json.')
    VERSION = '0.0.0'

class Controller(udi_interface.Node):

    id = 'controller'
    def __init__(self, polyglot, primary, address, name):
        super(Controller, self).__init__(polyglot, primary, address, name)
        # DD net to get custom params / add controller node
        self.poly = polyglot
        self.discovery = False
        self.Params = Custom(polyglot, 'customparams')
        self.join_mapping = {}
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        polyglot.subscribe(polyglot.DISCOVER, self.discover)
        polyglot.ready()
        #self.start()
        polyglot.addNode(self, conn_status="ST")
				
    #def start(self):
    #    LOGGER.info('Starting Sonos Polyglot v3 NodeServer version {}, udi_interface: {}'.format(VERSION, udi_interface.__version__))
    #    self.discover()

    # DD add routine to load parameters
    def parameterHandler(self, params):
        LOGGER.info("running parameterHandler")
        self.Params.load(params)
        self.discover()

        
	## strip special characters from names	
    def get_valid_node_name(self, name):
        name = bytes(name, 'utf-8').decode('utf-8','ignore')
        return re.sub(r"[<>'~!@#$%^&*(){}[\]?/\\;:\"']+","",name)

    def discover(self, command = None):
        LOGGER.info('Starting Speaker Discovery...')
        polyglot.Notices.clear()
        self.discovery = True
        netscan = False 
        kwargs = {}

        if self._add_manually("only_(.*)"):
            polyglot.Notices['only'] = 'Added speakers from config, skipping auto discovery.'
            self._update_NLS()
            self.discovery = False
            return

        for netparam in self.Params:
            LOGGER.info('Starting network scan')
            match = re.match( "networks_to_scan", netparam, re.I)
            if match is not None:
                netscanlist = self.Params[netparam].split(",")
                kwargs = {"networks_to_scan": netscanlist}
                netscan = True

        speakers = soco.discover(5,False,None,"Sonos",netscan,**kwargs)

        if speakers:
            LOGGER.info('Found {} Speaker(s)'.format(len(speakers)))
            idx = 1
            for speaker in speakers:
                address = speaker.uid[8:22].lower()
                self.join_mapping[idx] = speaker.player_name
                if not polyglot.getNode(address):
                    polyglot.addNode(Speaker(polyglot,"sonosctrl", address, speaker.player_name, speaker.ip_address))
                else:
                    LOGGER.info('Speaker {} already configured.'.format(speaker.player_name))
                idx = idx + 1
        else:
            LOGGER.info('No Speakers found. Are they powered on?')
            polyglot.Notices['error'] = 'No speakers found. Make sure they are powered on and try Disover again.'

            self._add_manually("sonos_(.*)")

        '''
        After discovery, create a mapping of index to speaker name. 

        Use this to update the NLS mapping and pass this mapping to
        each speaker node.  

        When a speaker executes a join() command, map the incoming
        index to this mapping to get the speaker name that we want
        to join with (or whatever we need to pass to the join()
        command).
        '''

        self._update_NLS()

        self.discovery = False
    
    def _add_manually(self, key):
        # DD - Add manual nodes
        LOGGER.info('add speakers from custom parameters')
        addit = False
        idx = 1
        #
        for param in self.Params:
            # Look for customParam starting with sonos_
            match = re.match( key, param, re.I)
            LOGGER.info('param={} match={}'.format(param,match))
            if match is not None:
                # The Sonos address is everything following the sonos_
                address = match.group(1).lower()
                LOGGER.info('process param={0} address={1}'.format(param,address))
                # Get the customParam value which is json code
                #  { "name": "Sonos FamilyRoom", "host": "192.168.1.86" }
                cfg = self.Params[param]
                cfgd = None
                try:
                    cfgd = json.loads(cfg)
                except:
                    err = sys.exc_info()[0]
                    LOGGER.error('failed to parse cfg={0} Error: {1}'.format(cfg,err))
                if cfgd is not None:
                    # Check that name and host are defined.
                    addit = True
                    if not 'name' in cfgd:
                        LOGGER.error('No name in customParam {0} value={1}'.format(param,cfg))
                        addit = False
                    if not 'host' in cfgd:
                        LOGGER.error('No host in customParam {0} value={1}'.format(param,cfg))
                        addit = False
                    if addit:
                        sonos_name = self.get_valid_node_name(cfgd['name'])
                        sonos_ip = self.get_valid_node_name(cfgd['host'])
                        self.join_mapping[idx] = sonos_name
                        if not polyglot.getNode(address): 
                            polyglot.addNode(Speaker(polyglot, "sonosctrl", address, sonos_name, sonos_ip))
                        else:
                            LOGGER.info('Speaker {} already configured.'.format(sonos_name))
                        idx = idx + 1
        return addit


    def _update_NLS(self):
        # Open NLS file for writing
        try:
            LOGGER.debug('Writing new NLS file')
            nls = open("profile/nls/en_us.txt", "w")
        # Write base NLS
            nls.write("# controller\n")
            nls.write("ND-controller-NAME = Sonos Controller\n")
            nls.write("ND-controller-ICON = GenericCtl\n")
            nls.write("ST-ctl-ST-NAME = NodeServer Online\n")
            nls.write("CMD-ctl-DISCOVER-NAME = Re-Discover\n")

            nls.write("# Controller Status\n")
            nls.write("CST-0 = Disconnected\n")
            nls.write("CST-1 = Connected\n")
            nls.write("CST-2 = Failed\n")

            nls.write("# Sonos Speakers\n")
            nls.write("ND-sonosspeaker-NAME = Sonos Speaker\n")
            nls.write("ND-sonosspeaker-ICON = GenericRsp\n")
            nls.write("ST-sspk-ST-NAME = Status\n")
            nls.write("ST-sspk-SVOL-NAME = Volume\n")
            nls.write("ST-sspk-GV1-NAME = Bass\n")
            nls.write("ST-sspk-GV2-NAME = Treble\n")
            nls.write("ST-sspk-GV3-NAME = Muted\n")

            nls.write("CMD-sspk-PLAY-NAME = Play\n")
            nls.write("CMD-sspk-PAUSE-NAME = Pause\n")
            nls.write("CMD-sspk-STOP-NAME = Stop\n")
            nls.write("CMD-sspk-PREVIOUS-NAME = Previous\n")
            nls.write("CMD-sspk-NEXT-NAME = Next\n")
            nls.write("CMD-sspk-MUTE-NAME = Mute\n")
            nls.write("CMD-sspk-UNMUTE-NAME = UnMute\n")
            nls.write("CMD-sspk-PARTYMODE-NAME = Party Mode\n")
            nls.write("CMD-sspk-VOLUME-NAME = Volume\n")
            nls.write("CMD-sspk-BASS-NAME = Bass\n")
            nls.write("CMD-sspk-TREBLE-NAME = Treble\n")
            nls.write("CMD-sspk-JOIN-NAME = Join\n")

            nls.write("PLAY_MODE-0 = Playing\n")
            nls.write("PLAY_MODE-1 = Transitioning\n")
            nls.write("PLAY_MODE-2 = Paused\n")
            nls.write("PLAY_MODE-3 = Stopped\n")

        # Write speaker mapping
            for s in self.join_mapping:
                LOGGER.debug('Adding {} to NLS'.format(self.join_mapping[s]))
                nls.write("SPEAKER-{} = {}\n".format(s, self.join_mapping[s]))

        # Close NLS file
            nls.close()
        except:
            LOGGER.error('Failed to write out updated NLS file.')

        # update profile files
        self.poly.updateProfile()

    def getName(self, index):
        return self.join_mapping[index]

    def _cmd_discover(self, control):
        self.discover()

    drivers = [{'driver': 'ST', 'value': 1, 'uom': '25'}]


    commands = {  'DISCOVER': _cmd_discover}

class Speaker(udi_interface.Node):
    def __init__(self, polyglot, primary, address, name, ip):
        self.ip = ip
        self.primary = primary
        try:
            self.zone = soco.SoCo(self.ip)
        except:
            # Test code so this doesn't crash on fake speaker
            if self.zone == None:
                self.zone = {'volume':1, 'bass':10, 'treble':5, 'mute':False}

        LOGGER.info('Sonos Speaker: {}@{} Current Volume: {}'\
                    .format(name, ip, self.zone.volume))
        super().__init__(polyglot, primary, address, 'Sonos {}'.format(name))

        polyglot.subscribe(polyglot.START, self.start, address)
        polyglot.subscribe(polyglot.POLL, self.update)

    def start(self):
        LOGGER.info("{} ready to rock!".format(self.name))
        self.update('shortPoll')

    def update(self, pollflag):
        if pollflag == 'shortPoll':
            try:
                self.setDriver('ST', self._get_state())
                self.setDriver('SVOL', self.zone.volume)
                self.setDriver('GV1', self.zone.bass)
                self.setDriver('GV2', self.zone.treble)
                muteval = 1 if self.zone.mute == True else 0 
                self.setDriver('GV3', muteval)
                #LOGGER.info(self.zone.player_name)
                #LOGGER.info('Mute Status %s', self.zone.mute)
            except requests.exceptions.ConnectionError as e:
                LOGGER.error('Connection error to Speaker or ISY.: %s', e)


    def query(self, command=None):
        self.update('shortPoll')
        self.reportDrivers()

    def _get_state(self):
        text = self.zone.get_current_transport_info()['current_transport_state'].upper()
        return {
            'PLAYING': '0',
            'TRANSITIONING': '1',
            'PAUSED_PLAYBACK': '2',
            'STOPPED': '3'
        }.get(text, '3')

    def _play(self, command):
        try:
            self.zone.play()
            self.setDriver('ST', self._get_state())
        except:
            LOGGER.info('Transition not available. This typically means no music is selected.')

    def _stop(self, command):
        try:
            self.zone.stop()
            self.setDriver('ST', self._get_state())
        except:
            LOGGER.info('Transition not available. This typically means no music is selected.')

    def _pause(self, command):
        try:
            self.zone.pause()
            self.setDriver('ST', self._get_state())
        except:
            LOGGER.info('Transition not available. This typically means no music is selected.')

    def _next(self, command):
        try:
            self.zone.next()
        except:
            LOGGER.info('This typically means that the station or mode you are in doesn\'t support it.')

    def _previous(self, command):
        try:
            self.zone.previous()
        except:
            LOGGER.info('This typically means that the station or mode you are in doesn\'t support it.')

    def _partymode(self, command):
        try:
            self.zone.partymode()
        except:
            LOGGER.info('Your Sonos didn\'t like that. Make sure you are doing things correctly.')

    def _mute(self, command):
        self.zone.mute = True
        self.setDriver('GV3', 1)

    def _unmute(self, command):
        self.zone.mute = False
        self.setDriver('GV3', 0)

    def _volume(self, command):
        try:
            val = int(command.get('value'))
        except:
            LOGGER.error('volume: Invalid argument')
        else:
            self.zone.volume = val
            self.setDriver('SVOL', val)

    def _bass(self, command):
        try:
            val = int(command.get('value'))
        except:
            LOGGER.error('bass: Invalid argument')
        else:
            if -10 <= val <= 10:
                self.zone.bass = val
                self.setDriver('GV1', val)

    def _treble(self, command):
        try:
            val = int(command.get('value'))
        except:
            LOGGER.error('treble: Invalid argument')
        else:
            if -10 <= val <= 10:
                self.zone.treble = val
                self.setDriver('GV2', val)

    def _join(self, command):
        # join to another speaker
        try:
            val = int(command.get('value'))
        except:
            LOGGER.error('join: Invalid argument')
        else:
            parent = self.poly.getNode(self.primary)
            name = parent.getName(val)
            LOGGER.error('join to: {} {}'.format(name, val))
            self.zone.join(name)

    drivers = [{'driver': 'GV1', 'value': 0, 'uom': '56'},
                {'driver': 'GV2', 'value': 0, 'uom': '56'},
                {'driver': 'SVOL', 'value': 0, 'uom': '51'},
                {'driver': 'ST', 'value': 0, 'uom': '25'},
                {'driver': 'GV3', 'value': 0, 'uom': '2'}]

    commands = {    'PLAY': _play,
                    'STOP': _stop,
                    'DON': _play,
                    'DOF': _pause,
                    'PAUSE': _pause,
                    'JOIN': _join,
                    'NEXT': _next,
                    'PREVIOUS': _previous,
                    'PARTYMODE': _partymode,
                    'MUTE': _mute,
                    'UNMUTE': _unmute,
                    'BASS': _bass,
                    'TREBLE': _treble,
                    'VOLUME': _volume}

    id = 'sonosspeaker'

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start('3.0.2')
        polyglot.setCustomParamsDoc()
        polyglot.updateProfile()
        Controller(polyglot, "sonosctrl", "sonosctrl", "Sonos Controller")
        

        #polyglot.ready()
        #control.start()

        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
