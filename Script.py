#!/usr/bin/python
import re
from optparse import OptionParser


guidfile = "Guid.xref"
#Parser .map file,return list[Pcd_name,struct,name,guid]
def map_parser(filename):
	mapinfo=[];block_dict={}
	sub_re=re.compile('# (\w.*)')
	sub2_re=re.compile('(\S*])')
	block_re=re.compile('(\S*)\]')
	name_re=re.compile('(\d)\|(\S*)?')
	with open(filename,'r') as text:
		read=text.read()
	read=sub_re.sub(' ',read)
	block=read.split('[')
	for i in block:
		infolist = [];id={}
		block_name=block_re.findall(i)
		num_name=name_re.findall(i)
		if block_name:
			if num_name:
				for m in num_name:
					id[m[0]]= m[1]
				block_dict[block_name[0]] = id
			else:
				infolist.append(block_name[0])
				moduleinfo=sub2_re.sub(' ',i)
				one=moduleinfo.split('\n')
				for n in one:
					if n != ' 'and n !='':
						info=n.split('|')
						Pcd_name=info[0];struct=info[1];name=info[2];guid=info[3]
						text =Pcd_name,struct,name,guid
						infolist.append(text)
				mapinfo.append(infolist)
	return	block_dict,mapinfo

#Parser .lst file,return dict{offset:filename}
def lst_parser(filename, value):
	name_re = re.compile('(\w+)')
	struct_format = re.compile(r'%s {.*?;' % value, re.S)
	info = {};text = ''
	for y in filename:
		with open(y, 'r') as f:
			read = f.read()
		text +=read
	context = struct_format.search(text)
	if context:
		text = context.group().split('+')
		for line in text[1:]:
			line = name_re.findall(line)
			if line:
				if len(line) == 5:
					offset = int(line[0], 10);name = line[2]+'[0]'
					info[offset] = name
					uint=int(re.search('\d+',line[4]).group(0),10)
					bit=uint/8
					for i in range(1,int(line[3], 10)):
						offset += bit;name = line[2]+'[%s]'%i
						info[offset] = name
				else:
					offset = int(line[0], 10);name = line[2]
					info[offset] = name
	return info

#Parser .config file,return list[offset,name,guid,value,help]
def config_parser(filename):
	ids_re =re.compile('_ID:(.*)')
	id_re= re.compile('\s+')
	info = []
	with open(filename, 'r') as text:
		read = text.read()
	if 'DEFAULT_ID:' in read:
		all = read.split('DEFAULT')
		for i in all[1:]:
			id = [];part = [] #save all infomation for DEFAULT_ID
			ids = ids_re.findall(i)
			for m in ids:
				tmp=id_re.sub('',m)
				id.append(tmp)
			part.append(id)
			section = i.split('\nQ') #split with '\nQ ' to get every block
			part +=section_parser(section)
			info.append(part)
	else:
		part = []
		id=('0','0')
		part.append(id)
		section = read.split('\nQ')
		part +=section_parser(section)
		info.append(part)
	return info

def section_parser(section):
	offset_re = re.compile(r'offset = (.*)')
	name_re = re.compile(r'name = (.*)')
	guid_re = re.compile(r'guid = (.*)')
	help_re = re.compile(r'help = (.*)')
	value_re = re.compile(r'(//.*)')
	part = []
	for x in section[1:]:
			line=x.split('\n')[0]
			line=value_re.sub('',line) #delete \\... in "Q...." line
			list1=line.split(' ')
			value=value_parser(list1)
			offset = offset_re.findall(x)
			name = name_re.findall(x)
			guid = guid_re.findall(x)
			if offset and name and guid and value:
				offset = int(offset[0], 16)
				help = help_re.findall(x)
				text = offset, name[0], guid[0], value,help[0]
				part.append(text)
	return(part)	

def guid_parser(guidfile):
	guiddict={}
	with open(guidfile,'r') as guid:
		lines = guid.readlines()
	for line in lines:
		list=line.strip().split(' ')
		if list:
			if len(list)>1:
				guiddict[list[0].upper()]=list[1]
			elif list[0] != ''and len(list)==1:
				print "Error:line %s can't be parser in %s"%(line.strip(),guidfile)
	return guiddict

def value_parser(list1):
	list1 = [t for t in list1 if t != ''] #remove '' form list
	first_num=int(list1[0],16)
	if list1[first_num+1]=='STRING':  #parser STRING
		value='L%s'%list1[-1]
	elif list1[first_num+1]=='ORDERED_LIST': #parser ORDERED_LIST
		value_total=int(list1[first_num+2])
		list2= list1[-value_total:]
		tmp = [];line=''
		for i in list2:
			if len(i)%2 == 0 and len(i) !=2:
				for m in range(0,len(i)/2):
					tmp.append('0x%02x' % (int('0x%s' % i, 16) >> m*8 & 0xff))
			else:
				tmp.append('0x%s'%i)
		for i in tmp:
			line +='%s,'%i
		value='{%s}'%line[:-1]
	else:
		value = "0x%01x"%int(list1[-1], 16)
#		value = hex(int(list1[-1], 16))  #parser Others
	return value
	
#output the result
def output(mapfile,lstfile,configfile,outputfile):
	config_value = config_parser(configfile)
	map_value = map_parser(mapfile)
	name_format = re.compile(r'(\w+)')
	guiddict = guid_parser(guidfile)
	notmatch= []
	tmplist=[];
	id_dict=map_value[0]
	for i in map_value[1]:
		all=[]
		module=i[0]
		for mapinfo in i[1:]:
			pcdname = mapinfo[0];struct = mapinfo[1];name = mapinfo[2];guid = guiddict[mapinfo[3].upper()]
			dict_lst = lst_parser(lstfile, struct)
			for section in config_value:
				tmp = '';default_info=[];info=[]
				DefaultStores = section[0][0];SkuIds = section[0][1]
				if 'DefaultStores' in id_dict.keys() and 'SkuIds' in id_dict.keys():
					plat_info = []
					for x in DefaultStores:
						default_info.append(id_dict['DefaultStores'][x])
					for y in SkuIds:
						plat_info.append(id_dict['SkuIds'][y])
				for i in range(len(plat_info)):
					txt= '%s.common.%s.%s,'%(module,plat_info[i],default_info[i])
					tmp +=txt
				line='\n[%s]\n'%tmp[0:-1]
				info.append(line)
				line1 = '%s|%s|%s|0x00\n' % (pcdname, name, guid)
				info.append(line1)
				for c_offset, c_name, c_guid, c_value, c_help in section[1:]:
					if (name_format.findall(name)[1] == c_name) and (guid == guiddict[c_guid.upper()]):
						if c_offset in dict_lst.keys():
							line = '%s.%s|%s\n' % (pcdname, dict_lst[c_offset], c_value)
#							try:
#								int(c_value,16)
#								line = '%s.%s|%s\n' % (pcdname, dict_lst[c_offset], c_value)
#							except ValueError,e:
#								line = '%s.%s|%s\n' % (pcdname, dict_lst[c_offset][:-3], c_value)
							info.append(line)
						else:
							line = 'offset=%d | help=%s\n' % (c_offset, c_help)
							notmatch.append(line)
				all.append(info)
	writefile(all,notmatch,outputfile)

def writefile(match,notmatch,outputfile):
	for m in range(len(match)):
		for n in range(len(match)):
			if match[m][1]==match[n][1] and m != n:
				for a in match[m][2:]:
					for b in match[n][2:]:
						if a == b:
							del match[n][match[n].index(b)]
	Data = {}
	for item in match:
		if item[0] not in Data:
			Data[item[0]] = []
		for data in item[1:]:
			Data[item[0]].append(data)
	if Data:
		output = open(outputfile, 'wb')
		for line in Data:
			output.write(line)
			for x in Data[line]:
				output.write(x)
		output.close()
		print "%s for the result" % outputfile
	else:
		print 'No data have beed collected'
	if notmatch:
		print "Some offset not match,please check the 'Not_Match.txt':\n"
		not_match_file = open('Not_Match.txt', 'wb')
		for line in notmatch:
			not_match_file.write(line)
		not_match_file.close()

def main():
	usage="Script.py [-m <map file>][-l <lst file>/<lst file list>][-c <config file>][-o <output file>]"
	parser = OptionParser(usage)
	parser.add_option('-m','--map',metavar='FILENAME',dest='map',help="Input the '.map' file")
	parser.add_option('-l','--lst',metavar='FILENAME',action='append',dest='lst',help="Input the '.lst' file, if multiple files, please use ',' to split")
	parser.add_option('-c','--config',metavar='FILENAME',dest='config',help="Input the '.config' file")
	parser.add_option('-o','--output',metavar='FILENAME',dest='output')
	(options,args)=parser.parse_args()
	if options.map:
		if options.lst:
			if options.config:
				if options.output:
					output(options.map,options.lst,options.config,options.output)
				else:
					print 'Error command, use -h for help'
			else:
				print 'Error command, use -h for help'
		else:
			print 'Error command, use -h for help'
	else:
		print 'Error command, use -h for help'

if __name__=='__main__':
	main()