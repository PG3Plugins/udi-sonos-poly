#!/usr/bin/env python3
"""
Sonos NodeServer for UDI Polyglot v2
by Einstein.42 (James Milne) milne.james@gmail.com
"""

import udi_interface
import sys
import backend
import json
import re

LOGGER = udi_interface.LOGGER
Custom = udi_interface.Custom

VERSION = '4.0.0'

class Controller(udi_interface.Node):

    id = 'controller'
    def __init__(self, polyglot, primary, address, name):
        super(Controller, self).__init__(polyglot, primary, address, name)
        # DD net to get custom params / add controller node
        self.poly = polyglot
        self.discovery = False
        self.speakers = []
        self.kwargs = {}
        self.netscan = False 
        self.params = []
        self.Params = Custom(polyglot, 'customparams')

        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        polyglot.subscribe(polyglot.DISCOVER, self.discover)
        polyglot.subscribe(polyglot.POLL, self.poll)

        LOGGER.info("Starting Sonos eisy plugin version {}".format(VERSION))

        polyglot.ready()
        polyglot.addNode(self, conn_status="ST")
				
    #def start(self):
    #    LOGGER.info('Starting Sonos Polyglot v3 NodeServer version {}, udi_interface: {}'.format(VERSION, udi_interface.__version__))
    #    self.discover()

    # DD add routine to load parameters
    def parameterHandler(self, params):
        LOGGER.info("running parameterHandler")
        self.Params.load(params)

        # Get parameters for alternate networks to scan
        self.netscan = False 
        self.kwargs = {}
        for netparam in self.Params:
            match = re.match( "networks_to_scan", netparam, re.I)
            if match is not None:
                netscanlist = self.Params[netparam].split(",")
                self.kwargs = {"networks_to_scan": netscanlist}
                self.netscan = True

        # Get parameters for user defined speakers
        for param in self.Params:
            # Look for customParam starting with sonos_
            match = re.match( "sonos_(.*)", param, re.I)
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
                        self.params.append({'address':address, 'name': sonos_name, 'ip': sonos_ip})

        self.discover()

        
	## strip special characters from names	
    def get_valid_node_name(self, name):
        name = bytes(name, 'utf-8').decode('utf-8','ignore')
        return re.sub(r"[<>'~!@#$%^&*(){}[\]?/\\;:\"']+","",name)

    def discover(self, command = None):
        if self.discovery:
            LOGGER.debug('discover called while when it is currently running')
            return

        LOGGER.info('Starting Speaker Discovery...')
        polyglot.Notices.clear()
        self.discovery = True
        
        try:
            devices = backend.discover_devices(self.params, self.netscan, self.kwargs)
            LOGGER.info('Discovered {} devices(s)'.format(len(devices)))

            for zone in devices:
                node = self.poly.getNode(zone['address'])
                if node is None:
                    # add it
                    LOGGER.info("Adding zone {} {}".format(zone['name'], zone['address']))
                    node = Speaker(self.poly, self.address, zone['address'], zone['name'])
                    self.poly.addNode(node)
                node.bind(zone['device'])
                node.update()

            if len(devices) == 0:
                polyglot.Notices['error'] = 'No speakers found. Make sure they are powered on and try Disover again.'
        except Exception as ex:
            LOGGER.error("Discovery failed: {}".format(ex), exc_info=True)
            polyglot.Notices['error'] = 'Speaker/zone discovery failed.'
            self.discovery = False
            return

        self.discovery = False
    
    def _cmd_discover(self, control):
        self.discover()

    def poll(self, polltype):
        if polltype == 'longPoll':
            self.discover() # pickup devices add/removed since last poll
        else:
            for node in self.poly.nodes():
                if node.address != self.address and hasattr(node, 'update'):
                    node.update()

    drivers = [{'driver': 'ST', 'value': 1, 'uom': '25'}]
    commands = {  'DISCOVER': _cmd_discover}

class Speaker(udi_interface.Node):
    _POLL_MAP = {
            'ST': 'transport_state',
            'SVOL': 'volume',
            'GV1': 'bass',
            'GV2': 'treble',
            'GV3': 'muted',
            'GV4': 'shuffle', 
            'GV5': 'repeat', 
            'GV6': 'crossfade', 
            'GV7': 'source', 
            'GV8': 'queue_position', 
            'GV9': 'grouped', 
    }

    def __init__(self, polyglot, primary, address, name):
        super().__init__(polyglot, primary, address, 'Sonos {}'.format(name))
        self.device = None
        self.flip = 0

        #polyglot.subscribe(polyglot.START, self.start, address)
        #polyglot.subscribe(polyglot.POLL, self.update)

    def start(self):
        LOGGER.info("{} ready to rock!".format(self.name))
        self.update('shortPoll')

    def bind(self, zone):
        self.device = zone

    def update(self):
        if self.device is None:
            return

        try:
            state = backend.poll_device(self.device)
            LOGGER.error('STATE: {}'.format(state))
            for driver_id, key in self._POLL_MAP.items():
                if state.get(key) is not None:
                    LOGGER.debug('Setting {} to {}'.format(driver_id, state[key]))
                    self.setDriver(driver_id, state[key])
                else:
                    LOGGER.error('Skipping {} no state info'.format(driver_id))

            LOGGER.debug('MEDIA_INFO: {}'.format(state.get('media')))
            LOGGER.debug('TRACK_INFO: {}'.format(state.get('track')))

            if self.flip == 0:
                self.flip == 1

            if state.get('track')['title']:
                self.setDriver('GV10', self.flip, text=state.get('track')['title'])
            if state.get('track')['artist']:
                self.setDriver('GV11', self.flip, text=state.get('track')['artist'])
            if state.get('track')['album']:
                self.setDriver('GV12', self.flip, text=state.get('track')['album'])


        except Exception as ex:
            LOGGER.error('Poll failed for (): ()'.format(self.name, ex), exc_info=True)



    def query(self, command=None):
        self.reportDrivers()

    def _play(self, command):
        if self.device is not None:
            backend.play(self.device)
            self.update()

    def _stop(self, command):
        if self.device is not None:
            backend.stop(self.device)
            self.update()

    def _pause(self, command):
        if self.device is not None:
            backend.pause(self.device)
            self.update()

    def _next(self, command):
        if self.device is not None:
            backend.next_track(self.device)
            self.update()

    def _previous(self, command):
        if self.device is not None:
            backend.previous_track(self.device)
            self.update()

    def _partymode(self, command):
        if self.device is not None:
            backend.partymode(self.device)
            self.update()

    def _mute(self, command):
        if self.device is not None:
            backend.set_mute(self.device, command.get('value'))
            self.update()

    def _unmute(self, command):
        if self.device is not None:
            backend.set_mute(self.device, 0)
            self.update()

    def _volume(self, command):
        if self.device is not None:
            backend.set_volume(self.device, command.get('value'))
            self.update()

    def _bass(self, command):
        if self.device is not None:
            backend.set_bass(self.device, command.get('value'))
            self.update()

    def _treble(self, command):
        if self.device is not None:
            backend.set_treble(self.device, command.get('value'))
            self.update()

    def _shuffle(self, command):
        if self.device is not None:
            backend.set_shuffle(self.device, command.get('value'))
            self.update()

    def _repeat(self, command):
        if self.device is not None:
            backend.set_repeat(self.device, command.get('value'))
            self.update()

    def _xfade(self, command):
        if self.device is not None:
            backend.set_crossfade(self.device, command.get('value'))
            self.update()

    def _join(self, command):
        if self.device is not None:
            backend.join_group(self.device, command.get('value'))
            self.update()

    def _source(self, command):
        if self.device is not None:
            backend.set_source(self.device, command.get('value'))
            self.update()

    def _unjoin(self, command):
        if self.device is not None:
            backend.leave_group(self.device, command.get('value'))
            self.update()

    def _play_uri(self, command):
        if self.device is not None:
            backend.play_uri(self.device, command.get('value'))
            self.update()

    drivers = [{'driver': 'GV1', 'value': 0, 'uom': '56', 'name': 'Bass'},
               {'driver': 'GV2', 'value': 0, 'uom': '56', 'name': 'Treble'},
               {'driver': 'SVOL', 'value': 0, 'uom': '51', 'name': 'Volume'},
               {'driver': 'ST', 'value': 0, 'uom': '25', 'name': 'Transport State'},
               {'driver': 'GV3', 'value': 0, 'uom': '2', 'name': 'Mute'},
               {'driver': 'GV4', 'value': 0, 'uom': '2', 'name': 'Shuffle'},
               {'driver': 'GV5', 'value': 0, 'uom': '25', 'name': 'Repeat'},
               {'driver': 'GV6', 'value': 0, 'uom': '2', 'name': 'Cross Fade'},
               {'driver': 'GV7', 'value': 0, 'uom': '25', 'name': 'Source'},
               {'driver': 'GV8', 'value': 0, 'uom': '56', 'name': 'Queue Position'},
               {'driver': 'GV9', 'value': 0, 'uom': '2', 'name': 'Grouped'},
               {'driver': 'GV10', 'value': 0, 'uom': '2', 'name': 'Title'},
               {'driver': 'GV11', 'value': 0, 'uom': '2', 'name': 'Artist'},
               {'driver': 'GV12', 'value': 0, 'uom': '2', 'name': 'Album'},
               ]

    commands = {    'PLAY': _play,
                    'STOP': _stop,
                    'DON': _play,
                    'DOF': _pause,
                    'PAUSE': _pause,
                    'NEXT': _next,
                    'PREVIOUS': _previous,
                    'PARTYMODE': _partymode,
                    'MUTE': _mute,
                    'UNMUTE': _unmute,
                    'BASS': _bass,
                    'TREBLE': _treble,
                    'VOLUME': _volume,
                    'SHUFFLE': _shuffle,
                    'REPEAT': _repeat,
                    'SOURCE': _source,
                    'CROSS_FADE': _xfade,
                    'JOIN': _join,
                    'UNJOIN': _unjoin,
                    'PLAY_URI': _play_uri,
                }


    id = 'sonosspeaker'

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start(VERSION)
        polyglot.setCustomParamsDoc()
        polyglot.updateProfile()
        Controller(polyglot, "sonosctrl", "sonosctrl", "Sonos Controller")
        

        #polyglot.ready()
        #control.start()

        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)

    commands = {    'PLAY': _play,
                    'STOP': _stop,
                    'DON': _play,
                    'DOF': _pause,
                    'PAUSE': _pause,
                    'NEXT': _next,
                    'PREVIOUS': _previous,
                    'PARTYMODE': _partymode,
                    'MUTE': _mute,
                    'UNMUTE': _unmute,
                    'BASS': _bass,
                    'TREBLE': _treble,
                    'VOLUME': _volume,
                    'VOLUME': _shuffle,
                    'VOLUME': _repeat,
                    'VOLUME': _xfade,
                    'VOLUME': _join,
                    'VOLUME': _unjoin,
                    'VOLUME': _play_uri,
                }


    id = 'sonosspeaker'

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start(VERSION)
        polyglot.setCustomParamsDoc()
        polyglot.updateProfile()
        Controller(polyglot, "sonosctrl", "sonosctrl", "Sonos Controller")
        

        #polyglot.ready()
        #control.start()

        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
