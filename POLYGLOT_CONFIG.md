In general, the speakers should be auto discovered when the Plugin starts.  However
this only works if the speakers are on the same subnet.  If the speakers are not
on the same subnet, you can add additional subnets to scane and/or specify the
speakers directly.

To add additional subnets create parameters with the key set to "network_to_scan"
and the value set to a common delimited list of subnets.  For example:

network_to_scan : 192.168.20.1/24

or

network_to_scan: 192.168.20.1/24,192.168.30.1/24

You can also set parameters to specify the speakers directly.  Set the key to a
unique ID and the value to the speaker's name and IP address.  For example:

sonos_Living : { "name": "Sonos Living Room", "host": "192.168.1.86" }

or

You can specify that you only want the plug-in to interact with specific
speakers. Set the key to only_<unique> and the value to the speaker's name
and IP address. For example:

only_Living : { "name": "Sonos Living Room", "host": "192.168.1.86" }

This will skip automatic detection and only create the one speaker node
for the living room speaker.  You can specify multiple speakers by using
multiple custom parameters.
