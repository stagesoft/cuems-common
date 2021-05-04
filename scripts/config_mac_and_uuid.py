from uuid import uuid1
import xmlschema
import xmlschema.converters
import netifaces
from pprint import pprint
import sys
import xml.etree.ElementTree

# Retrieve MAC address from 1st network interface
mac = netifaces.ifaddresses('ethernet0')[netifaces.AF_LINK][0]['addr'].replace(':','').lower()

# Generate a new uuid
uuid = str(uuid1())

print(f'Node info to configure:')
print(f'===============================')
print(f'1st MAC:\t\t{mac}')
print(f'New UUID:\t\t{uuid}')
print('')

write_flag = False

if len(sys.argv) > 1:
    if sys.argv[1] == 'write':
        write_flag = True
    elif sys.argv[1] == 'test':
        write_flag = False
else:
    print('Especify if you just want test local outputs or really write system files!!')
    print(f'use: python {__file__} test or python {__file__} write')
    print(f'\ttest will create local files for you to check changes before applying them')
    print(f'\twrite will modify and/or create files in system and cuems dirs')
    exit()

##### /etc/cuems/settings.xml
print(f'Modifying /etc/cuems/settings.xml')

# xs = xmlschema.XMLSchema11('/etc/cuems/settings.xsd')
# xs.validate('/etc/cuems/settings.xml')

et = xml.etree.ElementTree.parse('/etc/cuems/settings.xml')

root = et.getroot()

for mac_in_xml in root.iter('mac'):
    mac_in_xml.text = mac

for uuid_in_xml in root.iter('uuid'):
    #uuid_in_xml.text = '0367f391-ebf4-48b2-9f26-000000000001'
    uuid_in_xml.text = uuid

if write_flag:
    et.write('/etc/cuems/settings.xml')
else:
    et.write('settings.xml')

# xs.validate('settings.xml')

##### /usr/share/cuems/cuems.service.*
print(f'Modifying /usr/share/cuems/cuems.service.*')

service_files = ['cuems.service.firstrun', 'cuems.service.master', 'cuems.service.slave']

for filename in service_files:
    et = xml.etree.ElementTree.parse(f'/usr/share/cuems/{filename}')

    root = et.getroot()

    for txt_record_in_xml in root.iter('txt-record'):
        if txt_record_in_xml.text[:5] == 'uuid=':
            txt_record_in_xml.text = f'uuid={uuid}'

    if write_flag:
        et.write(f'/usr/share/cuems/{filename}')
    else:
        et.write(f'{filename}')


##### /etc/avahi/avahi-daemon.conf
print(f'Modifying /etc/avahi/avahi-daemon.conf')
with open('/etc/avahi/avahi-daemon.conf', 'r') as configfile:
    lines = configfile.readlines()

for index, line in enumerate(lines.copy()):
    if line[:10] == 'host-name=' or line[:11] == '#host-name=':
        lines[index] = f'host-name={mac}\n'
    elif line[:9] == 'use-ipv4=' or line[:10] == '#use-ipv4=':
        lines[index] = f'use-ipv4=yes\n'
    elif line[:9] == 'use-ipv6=' or line[:10] == '#use-ipv6=':
        lines[index] = f'use-ipv6=no\n'
    elif line[:16] == 'deny-interfaces=' or line[:17] == '#deny-interfaces=':
        lines[index] = f'deny-interfaces=lo\n'

if write_flag:
    with open('/etc/avahi/avahi-daemon.conf', 'w') as writingfile:
        writingfile.writelines(lines)
else:
    with open('avahi-daemon.conf', 'w') as writingfile:
        writingfile.writelines(lines)
    


#####/etc/avahi/sudoers
print(f'Modifying /etc/avahi/sudoers')
with open('/etc/sudoers', 'r') as configfile:
    lines = configfile.readlines()

for index, line in enumerate(lines.copy()):
    if line[:26] == '#includedir /etc/sudoers.d':
        lines[index] = f'includedir /etc/sudoers.d\n'

if write_flag:
    with open('/etc/sudoers', 'w') as writingfile:
        writingfile.writelines(lines)
else:
    with open('sudoers', 'w') as writingfile:
        writingfile.writelines(lines)


#####/etc/hostname
print(f'Modifying /etc/hostname')
with open('/etc/hostname', 'r') as configfile:
    lines = configfile.readlines()

lines[0]=mac

if write_flag:
    with open('/etc/hostname', 'w') as writingfile:
        writingfile.writelines(lines)
else:
    with open('hostname', 'w') as writingfile:
        writingfile.writelines(lines)

#####/etc/hosts
print(f'Modifying /etc/hosts')
with open('/etc/hosts', 'r') as configfile:
    lines = configfile.readlines()

lines[1]=f"127.0.1.1       {mac}"

if write_flag:
    with open('/etc/hosts', 'w') as writingfile:
        writingfile.writelines(lines)
else:
    with open('hosts', 'w') as writingfile:
        writingfile.writelines(lines)
