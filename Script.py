#!/usr/bin/python
import re,os,sys
from optparse import OptionParser

statement='''[SkuIds]
  0|DEFAULT              # The entry: 0|DEFAULT is reserved and always required.

[DefaultStores]
  0|STANDARD             # UEFI Standard default  0|STANDARD is reserved.
  1|MANUFACTURING        # UEFI Manufacturing default 1|MANUFACTURING is reserved.
'''

SECTION='PcdsDynamicHii'
PCD_NAME='gStructPcdTokenSpaceGuid.Pcd'
attribute_dict={'0x3':'NV, BS','0x7':'NV, BS, RT'}

guidfile='Guid.xref'
outflag = 0

class parser_lst(object):

	def __init__(self,filelist):
		self.file=filelist
		self.text=self.megre_lst()
		#self.struct=self.efivarstore_parser().values()

	def megre_lst(self):
		alltext=''
		for file in self.file:
			with open(file,'r') as f:
				read =f.read()
			alltext += read
		return alltext

	def struct_parser(self,struct):
		name_re = re.compile('(\w+)')
		struct_format = re.compile(r'%s {.*?;' % struct, re.S)
		info = {}
		content = struct_format.search(self.text)
		if content:
			text = content.group().split('+')
			for line in text[1:]:
				line = name_re.findall(line)
				if line:
					if len(line) == 5:
						offset = int(line[0], 10)
						name = line[2] + '[0]'
						info[offset] = name
						uint = int(re.search('\d+', line[4]).group(0), 10)
						bit = uint / 8
						for i in range(1, int(line[3], 10)):
							offset += bit
							name = line[2] + '[%s]' % i
							info[offset] = name
					else:
						offset = int(line[0], 10)
						name = line[2]
						info[offset] = name
		return info

	def efivarstore_parser(self):
		efivarstore_format = re.compile(r'efivarstore.*?;', re.S)
		efitxt = efivarstore_format.findall(self.text)
		struct_re = re.compile(r'efivarstore(.*?),',re.S)
		name_re = re.compile(r'name=(\w+)')
		efivarstore_dict={}
		for i in efitxt:
			struct = struct_re.findall(i.replace(' ',''))
			name = name_re.findall(i.replace(' ',''))
			if struct and name:
				efivarstore_dict[name[0]]=struct[0]
			else:
				print "Can't find Struct or name in lst file, please check have this format:efivarstore XXXX, name=xxxx"
		return efivarstore_dict

	def matchoffset(self,offset):
		pass

def mainprocess(Guid,Config,Lst,Output):
	config_dict=config_parser(Config) #get {'00':[offset,name,guid,value,attribute]...,'10':....}
	lst=parser_lst(Lst)
	efi_dict=lst.efivarstore_parser() #get {name:struct} form lst file
	add=write2file(Output)
	add.add2file(statement)
	keys=sorted(config_dict.keys())
	title_list=[]
	info_list=[]
	for id in keys:
		tmp_id=[id] #['00',[(struct,[name...]),(struct,[name...])]]
		tmp_info={} #{name:struct}
		add.add2file(eval_id(id))
		for section in config_dict[id]:
			c_offset,c_name,c_guid,c_value,c_attribute = section
			if efi_dict.has_key(c_name):
				struct = efi_dict[c_name]
				title='%s%s|L"%s"|%s|0x00|%s\n'%(PCD_NAME,c_name,c_name,guid_parser(c_guid,Guid),attribute_dict[c_attribute])
				struct_dict = lst.struct_parser(struct) #get{offset:offset_name}
				if struct_dict.has_key(c_offset):
					offset_name=struct_dict[c_offset]
					info = "%s%s.%s|%s\n"%(PCD_NAME,c_name,offset_name,c_value)
					#print info
					tmp_info[info]=title
				else:
					print "Can't find offset %s with name %s in %s"%(c_offset,c_name,Lst)
			else:
				print "Can't find name %s in %s"%(c_name,Lst)
		tmp_id.append(reverse_dict(tmp_info).items())
		id,tmp_title_list,tmp_info_list = read_list(tmp_id)
		title_list +=tmp_title_list
		info_list.append(tmp_info_list)
	title_all=list(set(title_list))
	add.add2file(title_all)
	add.add2file(info_list)

def reverse_dict(dict):
	data={}
	for i in dict.items():
		if i[1] not in data.keys():
			data[i[1]]=[i[0]]
		else:
			data[i[1]].append(i[0])
	return data

def read_list(list):
	title_list=[]
	info_list=[]
	for i in list[1]:
		title_list.append(i[0])
		for j in i[1]:
			info_list.append(j)
	return list[0],title_list,info_list

#Parser .lst file,return dict{offset:filename}
def lst_parser(filename, struct):
	name_re = re.compile('(\w+)')
	struct_format = re.compile(r'%s {.*?;' % struct, re.S)
	efivarstore_format = re.compile(r'efivarstore.*?;', re.S)
	info = {};alltext = ''
	for y in filename:
		with open(y, 'r') as f:
			read = f.read()
		alltext +=read  #merge all .lst info
	#parser struct
	content = struct_format.search(alltext)
	if content:
		text = content.group().split('+')
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
	ids_re =re.compile('_ID:(\d+)',re.S)
	id_re= re.compile('\s+')
	info = []
	info_dict={}
	with open(filename, 'r') as text:
		read = text.read()
	if 'DEFAULT_ID:' in read:
		all = read.split('DEFAULT')
		for i in all[1:]:
			part = [] #save all infomation for DEFAULT_ID
			str_id=''
			ids = ids_re.findall(i.replace(' ',''))
			for m in ids:
				str_id +=m
			part.append(ids)
			section = i.split('\nQ') #split with '\nQ ' to get every block
			part +=section_parser(section)
			info_dict[str_id] = section_parser(section)
			#print info_dict
			info.append(part)
	else:
		part = []
		id=('0','0')
		str_id='00'
		part.append(id)
		section = read.split('\nQ')
		part +=section_parser(section)
		info_dict[str_id] = section_parser(section)
		info.append(part)
	return info_dict

def eval_id(id):
	len_id=len(id)
	default_id=id[0:len(id)/2]
	platform_id=id[len(id)/2:]
	text=''
	#info='%s.common.%s.%s,'%(SECTION,platform_id,default_id)
	for i in range(len(default_id)):
		text +="%s.common.%s.%s,"%(SECTION,ID_name(platform_id[i],'PLATFORM'),ID_name(default_id[i],'DEFAULT'))
	return '\n[%s]\n'%text[:-1]

def section_parser(section):
	offset_re = re.compile(r'offset=(\w+)')
	name_re = re.compile(r'name=(\S+)')
	guid_re = re.compile(r'guid=(\S+)')
#	help_re = re.compile(r'help = (.*)')
	attribute_re=re.compile(r'attribute=(\w+)')
	value_re = re.compile(r'(//.*)')
	part = []
	for x in section[1:]:
			line=x.split('\n')[0]
			line=value_re.sub('',line) #delete \\... in "Q...." line
			list1=line.split(' ')
			value=value_parser(list1)
			offset = offset_re.findall(x.replace(' ',''))
			name = name_re.findall(x.replace(' ',''))
			guid = guid_re.findall(x.replace(' ',''))
			attribute =attribute_re.findall(x.replace(' ',''))
			if offset and name and guid and value and attribute:
				offset = int(offset[0], 16)
#				help = help_re.findall(x)
				text = offset, name[0], guid[0], value, attribute[0]
				part.append(text)
	return(part)	

#parser Guid file, get guid name form guid value
#return guid find info
def guid_parser(guid,guidfile):
	guiddict={}
	with open(guidfile,'r') as file:
		lines = file.readlines()
	for line in lines:
		list=line.strip().split(' ')
		if list:
			if len(list)>1:
				guiddict[list[0].upper()]=list[1]
			elif list[0] != ''and len(list)==1:
				print "Error:line %s can't be parser in %s"%(line.strip(),guidfile)
	if guiddict.has_key(guid.upper()):
		return guiddict[guid.upper()]
	else:
		print  "GUID %s not found in file %s"%(guid, guidfile)
		return guid

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

def ID_name(ID,flag):
	platform_dict={'0':'DEFAULT'}
	default_dict={'0':'STANDARD','1':'MANUFACTURING'}
	if flag == "PLATFORM":
		try:
			value=platform_dict[ID]
		except KeyError:
			value = 'SKUID%s'%ID
	elif flag == 'DEFAULT':
		try:
			value= default_dict[ID]
		except KeyError:
			value = 'DEFAULTID%s'%ID
	return value

class write2file(object):

	def __init__(self,Output):
		self.output=Output
		self.text=''

	def add2file(self,content):
		global outflag
		self.text = ''
		if not outflag:
			if os.path.exists(self.output):
				os.remove(self.output)
				outflag = 1
		with open(self.output,'a+') as file:
			file.write(self.__gen(content))

	def __gen(self,content):
		if type(content) == type(''):
			return content
		elif type(content) == type([0,0])or type(content) == type((0,0)):
			return self.__readlist(content)
		elif type(content) == type({0:0}):
			return self.__readdict(content)

	def __readlist(self,list):
		for i in list:
			if type(i) == type([0,0])or type(i) == type((0,0)):
				self.__readlist(i)
			elif type(i) == type('') :
				self.text +=i
		return self.text

	def __readdict(self,dict):
		content=dict.items()
		return self.__readlist(content)


#output the result
def output(mapfile,lstfile,configfile,outputfile):
	config_value = config_parser(configfile)
	map_value = map_parser(mapfile)
	name_format = re.compile(r'(\w+)')
	guiddict = guid_parser(guidfile)
	notmatch= []
	tmplist=[]
	attribute_dict={'0x3':'NV, BS','0x7':'NV, BS, RT'}
	id_dict=map_value[0]
	for i in map_value[1]:
		all=[]
		module=i[0]
		for mapinfo in i[1:]:
			pcdname = mapinfo[0];struct = mapinfo[1];name = mapinfo[2];guid = guiddict[mapinfo[3].upper()]
			#lst=parser_lst(lstfile,struct)
			dict_lst = lst_parser(lstfile, struct)
			#dict_lst = lst.struct_parser()
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
				line1 = '******%s|%s|%s|0x00\n' % (pcdname, name, guid)
				info.append(line1)
				for c_offset, c_name, c_guid, c_value, c_attribute in section[1:]:
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
							line = 'offset=%d | %s\n' % (c_offset,c_guid)
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
		output.write(statement)
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
	parser.add_option('-g','--guid',metavar='FILENAME',dest='guid',help="Input the guid file")
	parser.add_option('-l','--lst',metavar='FILENAME',action='append',dest='lst',help="Input the '.lst' file, if multiple files, please use ',' to split")
	parser.add_option('-c','--config',metavar='FILENAME',dest='config',help="Input the '.config' file")
	parser.add_option('-o','--output',metavar='FILENAME',dest='output')
	(options,args)=parser.parse_args()
	if options.guid:
		if options.lst:
			if options.config:
				if options.output:
					#output(options.map,options.lst,options.config,options.output)
					mainprocess(options.guid,options.config,options.lst,options.output)
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
