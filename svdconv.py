#!/usr/bin/env python3

import sys
import xml.etree.ElementTree as et
from itertools import groupby

svd_file_ext = sys.argv[1]
svd_file     = svd_file_ext.split('.')[0].lower()

header_file  = svd_file + '_mmr.h'
source_file  = svd_file + '_mmr.c'
linker_file  = svd_file + '_mmr.ld'

xml = et.parse(svd_file_ext)
root = xml.getroot()

#*************************************************
class TDevice:
    name = ''
    reg_list = []
    def __init__(self, name):
        self.name = name
        self.reg_list = []

class TRegister:
    def __init__(self, name, addr, size):
        self.name = name
        self.addr = addr
        self.size = size
        self.fields = []

#*************************************************
def parse_register(register, base):
    reg_name   = register.find('name').text
    reg_offset = int(register.find('addressOffset').text, 0)
    reg_size   = int(register.find('size').text, 0)
    reg_addr   = base + reg_offset

    reg = TRegister(reg_name, reg_addr, reg_size)
 
    fields = register.findall('fields')
    if fields != []:
        fields_tree = fields[0].findall('field')
        for field in fields_tree:
            offset = int(field.find('bitOffset').text, 0)
            size   = int(field.find('bitWidth').text, 0)
            if not ((offset == 0) and (size == reg_size)):
                field_name   = field.find('name').text
                field_size   = size
                field_offset = offset
                reg.fields.append((field_offset, field_size, field_name))

    reg.fields.sort(key=lambda x: x[0])
    return reg

#*************************************************
dev_dict = {}
dev_count = 0

def parse_peripheral(device):
    global dev_list
    global dev_count

    dev_name = device.find('name').text
    dev_base = int(device.find('baseAddress').text, 0)

    dev = TDevice(dev_name)
    dev_dict.update({dev_name:dev_count})
    dev_count = dev_count + 1

    if device.attrib == {}:
        registers = device.findall('registers')
        registers_tree = registers[0].findall('register')
        for register in registers_tree:
            result = parse_register(register, dev_base)
            dev.reg_list.append(result)
    else:
        parent = device.attrib['derivedFrom']
        i = dev_dict[parent]
        dev.reg_list = dev_list[i].reg_list

    dev.reg_list.sort(key=lambda x: x.addr)
    return dev

#*************************************************
def fields2struct(reg):
    struct_text = []
    bit_count = 0     

    struct_text.append('struct {\n')

    for field in reg.fields:
        offset = field[0]
        size   = field[1]
        name   = field[2]
        if (offset == bit_count):
            struct_text.append('\tuint%d_t %s :%d;\n' % (reg.size, name, size))
            bit_count = offset + size
        elif (offset > bit_count):
            struct_text.append('\tuint%d_t :%d;\n' % (reg.size, offset - bit_count))
            struct_text.append('\tuint%d_t %s :%d;\n' % (reg.size, name, size))
            bit_count = offset + size

    if (bit_count < reg.size):
        struct_text.append('\tuint%d_t :%d;\n' % (reg.size, reg.size - bit_count))

    struct_text.append('}')

    return struct_text
            
def struct_decl(reg):
    struct = ''
    for s in fields2struct(reg):
        struct += s
    return struct

def union_decl(reg_group):
    union = 'union {\n'
    for reg in reg_group:
        struct_name = reg.name.lower() + '_bits'
        struct = ''
        for s in fields2struct(reg):
            struct += '\t' + s
        union += '%s %s;\n' % (struct, struct_name)
    union += '}'
    return union

#*************************************************
def attributes(dev_name, reg_group):

    if (len(reg_group) == 1):
        reg_name = '%s_%s' % (dev_name, reg_group[0].name)
    else:
        suffix = '_%s' % reg_group[0].name.split('_')[-1]
        group_name = reg_group[0].name.replace(suffix,'')
        reg_name = '%s_%s' % (dev_name, group_name)

    sect_name = '.%s' % reg_name.lower()

    if (len(reg_group) == 1):
        reg = reg_group[0]
        if (reg.fields == []):
            type_name = 'uint%d_t' % reg.size
            type_decl = 'none'
        else:
            type_name = '%s_t' % reg_name.lower()
            type_decl = struct_decl(reg)
    else:
        type_name = '%s_t' % reg_name.lower()
        type_decl = union_decl(reg_group)

    return type_name, type_decl, reg_name, sect_name

#*************************************************
peripherals = root.findall('peripherals')
peripherals_tree  = peripherals[0].findall('peripheral')

dev_list = []

for device in peripherals_tree:
    result = parse_peripheral(device)
    dev_list.append(result)

header_file_fd = open(header_file,'w')
header_file_fd.write('#include <stdint.h>\n\n')

source_file_fd = open(source_file,'w')
source_file_fd.write('#include "%s"\n\n' % header_file)

linker_file_fd = open(linker_file,'w')
linker_file_fd.write('SECTIONS {\n')

for dev in dev_list:
    for addr, group in groupby(dev.reg_list, key=lambda x: x.addr):
        reg_group = list(group)
        type_name, type_decl, reg_name, sect_name = attributes(dev.name, reg_group)

        if (type_decl != 'none'):
            type_def = 'typedef %s %s;' % (type_decl, type_name)
            header_file_fd.write(type_def + '\n\n')

        reg_decl = 'volatile %s %s __attribute__((section("%s")));' % (type_name, reg_name, sect_name)
        source_file_fd.write(reg_decl + '\n')

        sect_cmd = '%s 0x%x (NOLOAD): ALIGN(4) { KEEP(*(%s)) }' % (sect_name, addr, sect_name)
        linker_file_fd.write('\t' + sect_cmd + '\n')

linker_file_fd.write('}')

header_file_fd.close()
source_file_fd.close()
linker_file_fd.close()