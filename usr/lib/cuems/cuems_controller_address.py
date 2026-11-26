# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""Where the cluster's controller is.

One rule for every helper that needs its address, in the order the engine uses
(cuems-engine, BaseEngine.get_controller_ip):

1. the name `controller.local` (mDNS, or a line in /etc/hosts), unless it
   answers with a loopback or unspecified address, which is how a box sees its
   own name;
2. the <ip> of the controller's entry in network_map.xml.

A node's map need not list its controller for the first to work.
"""

import ipaddress
import socket
import xml.etree.ElementTree as ET

CONTROLLER_NAME = 'controller.local'
MAP_ENTRY = "./node_list/node[node_type='NodeType.master']/ip"


def from_name(resolve):
    """The address the name gives, or None when it is of no use."""
    try:
        address = ipaddress.ip_address(resolve(CONTROLLER_NAME))
    except (OSError, ValueError):
        return None
    if address.is_loopback or address.is_unspecified:
        return None
    return str(address)


def controller_address(network_map, resolve=socket.gethostbyname):
    """The controller's address; LookupError saying why when there is none."""
    address = from_name(resolve)
    if address:
        return address
    why = f'{CONTROLLER_NAME} gives no usable address'
    try:
        root = ET.parse(network_map).getroot()
    except OSError:
        raise LookupError(f'{why}, and {network_map} cannot be read') from None
    except ET.ParseError as e:
        raise LookupError(f'{why}, and {network_map} cannot be parsed: {e}') from None
    element = root.find(MAP_ENTRY)
    address = (element.text or '').strip() if element is not None else ''
    if not address:
        first = list(root)[0].tag if list(root) else '<none>'
        raise LookupError(f'{why}, and {network_map} has no controller address (searched '
                          f'{MAP_ENTRY}; root {root.tag!r}, first child {first!r})')
    return address
