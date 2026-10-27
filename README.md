# Sonos V2

An eisy plugin to control and monitor Sonos devices on your network.

By default, the plugin will attempt to discover the Sonos devices on 
your network. It will only find devices if they are on the same 
subnet as your eisy.

Configuration options allow specifying Sonos devices by IP address
if the discovery process is unable to find some or all of your
devices.

The plugin will create a node that represents each device. That
node will have the following information:

<table>
<tr><td>ST</td><td>Transport State (0=stoped, 1=playing, 2=paused, 3=transitioning)</td></tr>
<tr><td>GV0</td><td>Volume</td></tr>
<tr><td>GV1</td><td>Muted</td></tr>
<tr><td>GV2</td><td>Shuffle</td></tr>
<tr><td>GV3</td><td>Repeat (0=off, 1=all, 2=one)</td></tr>
<tr><td>GV4</td><td>Crossfade</td></tr>
<tr><td>GV5</td><td>Source (0=none, 1=queue, 2=radio/stream, 3=TV, 4=line-in, 5=other</td></tr>
<tr><td>GV6</td><td>Queue postion</td></tr>
<tr><td>GV7</td><td>Grouped with other speakers</td></tr>
</table>

The node can send the following command to the device:

<ul>
<li>PLAY</li>
<li>PAUSE</li>
<li>STOP</li>
<li>NEXT</li>
<li>PREV</li>
<li>SET_VOL</li>
<li>VOL_UP</li>
<li>VOL_DN</li>
<li>SET_MUTE</li>
<li>TOGGLE_MUTE</li>
<li>SET_SHUFFLE</li>
<li>SET_REPEAT</li>
<li>SET_XFADE</li>
<li>JOIN</li>
<li>UNJOIN</li>
<li>PLAY_URI</li>
</ul>

