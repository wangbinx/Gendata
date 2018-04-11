#!/usr/bin/python
import re,os,datetime,thread
from optparse import OptionParser

statement='''[SkuIds]
  0|DEFAULT              # The entry: 0|DEFAULT is reserved and always required.

[DefaultStores]
  0|STANDARD             # UEFI Standard default  0|STANDARD is reserved.
  1|MANUFACTURING        # UEFI Manufacturing default 1|MANUFACTURING is reserved.
'''

SECTION='PcdsDynamicHii'
PCD_NAME='gStructPcdTokenSpaceGuid.Pcd'

class parser_lst(object):

	def __init__(self,filelist):
		self.file=filelist
		self.text=self.megre_lst()

	def megre_lst(self):
		alltext=''
		for file in self.file:
			with open(file,'r') as f:
				read =f.read()
			alltext += read
		return alltext

	def struct(self):
		_ignore=['EFI_HII_REF', 'EFI_HII_TIME', 'EFI_STRING_ID', 'EFI_HII_DATE', 'BOOLEAN', 'UINT8', 'UINT16', 'UINT32', 'UINT64']
		name_format = re.compile(r'(?<!typedef)\s+struct (\w+) {.*?;', re.S)
		name_re = re.compile('(\w+)')
		info = {}
		name=name_format.findall(self.text)
		if name:
			#name=[L for L in name if L not in _ignore]
			name=list(set(name).difference(set(_ignore)))
			for struct in name:
				struct_format = re.compile(r'struct %s {.*?;' % struct, re.S)
				content = struct_format.search(self.text)
				if content:
					tmp_dict = {}
					text = content.group().split('+')
					for line in text[1:]:
						line = name_re.findall(line)
						if line:
							if len(line) == 5:
								offset = int(line[0], 10)
								name = line[2] + '[0]'
								tmp_dict[offset] = name
								uint = int(re.search('\d+', line[4]).group(0), 10)
								bit = uint / 8
								for i in range(1, int(line[3], 10)):
									offset += bit
									name = line[2] + '[%s]' % i
									tmp_dict[offset] = name
							else:
								offset = int(line[0], 10)
								name = line[2]
								tmp_dict[offset] = name
					info[struct]=tmp_dict
		else:
			print "No struct name found in %s"%self.file
		return info

	def efivarstore_parser(self):
		efivarstore_format = re.compile(r'efivarstore.*?;', re.S)
		struct_re = re.compile(r'efivarstore(.*?),',re.S)
		name_re = re.compile(r'name=(\w+)')
		efivarstore_dict={}
		efitxt = efivarstore_format.findall(self.text)
		for i in efitxt:
			struct = struct_re.findall(i.replace(' ',''))
			name = name_re.findall(i.replace(' ',''))
			if struct and name:
				efivarstore_dict[name[0]]=struct[0]
			else:
				print "Can't find Struct or name in lst file, please check have this format:efivarstore XXXX, name=xxxx"
		return efivarstore_dict

class mainprocess(object):

	def __init__(self,Guid,Config,Lst,Output):
		self.Guid = Guid
		self.Config = Config
		self.Lst = Lst
		self.Output = Output
		self.attribute_dict = {'0x3': 'NV, BS', '0x7': 'NV, BS, RT'}
		self.guid = GUID(self.Guid)

	def main(self):
		conf=Config(self.Config)
		config_dict=conf.config_parser() #get {'00':[offset,name,guid,value,attribute]...,'10':....}
		lst=parser_lst(self.Lst)
		guid = GUID(self.Guid)
		efi_dict=lst.efivarstore_parser() #get {name:struct} form lst file
		keys=sorted(config_dict.keys())
		all_struct=lst.struct()
		title_list=[]
		info_list=[]
		for id in keys:
			tmp_id=[id] #['00',[(struct,[name...]),(struct,[name...])]]
			tmp_info={} #{name:struct}
			for section in config_dict[id]:
				c_offset,c_name,c_guid,c_value,c_attribute = section
				if efi_dict.has_key(c_name):
					struct = efi_dict[c_name]
					title='%s%s|L"%s"|%s|0x00|%s\n'%(PCD_NAME,c_name,c_name,guid.guid_parser(c_guid),self.attribute_dict[c_attribute])
					#struct_dict = lst.struct_parser(struct) #get{offset:offset_name}
					if all_struct.has_key(struct):
						struct_dict=all_struct[struct]
					else:
						print "Struct %s can found in lst file" %struct
					if struct_dict.has_key(c_offset):
						offset_name=struct_dict[c_offset]
						info = "%s%s.%s|%s\n"%(PCD_NAME,c_name,offset_name,c_value)
						tmp_info[info]=title
					else:
						print "Can't find offset %s with name %s in %s"%(c_offset,c_name,self.Lst)
				else:
					print "Can't find name %s in %s"%(c_name,self.Lst)
			tmp_id.append(self.reverse_dict(tmp_info).items())
			id,tmp_title_list,tmp_info_list = self.read_list(tmp_id)
			title_list +=tmp_title_list
			info_list.append(tmp_info_list)
		title_all=list(set(title_list))
		info_list = self.del_repeat(info_list)
		return keys,title_all,info_list


	def write_all(self):
		title_flag=1
		info_flag=1
		write = write2file(self.Output)
		write.add2file(statement)
		conf = Config(self.Config)
		ids,title,info=self.main()
		for id in ids:
			write.add2file(conf.eval_id(id))
			if title_flag:
				write.add2file(title)
				title_flag=0
			if len(info) == 1:
				write.add2file(info)
			elif len(info) == 2:
				if info_flag:
					write.add2file(info[0])
					info_flag =0
				else:
					write.add2file(info[1])

	def del_repeat(self,list):
		if len(list) == 1:
			return list
		elif len(list) == 2:
			return [list[0],self.__del(list[0],list[1])]

	def __del(self,list1,list2):
		return list(set(list2).difference(set(list1)))

	def reverse_dict(self,dict):
		data={}
		for i in dict.items():
			if i[1] not in data.keys():
				data[i[1]]=[i[0]]
			else:
				data[i[1]].append(i[0])
		return data

	def read_list(self,list):
		title_list=[]
		info_list=[]
		for i in list[1]:
			title_list.append(i[0])
			for j in i[1]:
				info_list.append(j)
		return list[0],title_list,info_list

class Config(object):

	def __init__(self,Config):
		self.config=Config

	#Parser .config file,return list[offset,name,guid,value,help]
	def config_parser(self):
		ids_re =re.compile('_ID:(\d+)',re.S)
		id_re= re.compile('\s+')
		info = []
		info_dict={}
		with open(self.config, 'r') as text:
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
				part +=self.section_parser(section)
				info_dict[str_id] = self.section_parser(section)
				#print info_dict
				info.append(part)
		else:
			part = []
			id=('0','0')
			str_id='00'
			part.append(id)
			section = read.split('\nQ')
			part +=self.section_parser(section)
			info_dict[str_id] = self.section_parser(section)
			info.append(part)
		return info_dict

	def eval_id(self,id):
		default_id=id[0:len(id)/2]
		platform_id=id[len(id)/2:]
		text=''
		for i in range(len(default_id)):
			text +="%s.common.%s.%s,"%(SECTION,self.ID_name(platform_id[i],'PLATFORM'),self.ID_name(default_id[i],'DEFAULT'))
		return '\n[%s]\n'%text[:-1]

	def ID_name(self,ID, flag):
		platform_dict = {'0': 'DEFAULT'}
		default_dict = {'0': 'STANDARD', '1': 'MANUFACTURING'}
		if flag == "PLATFORM":
			try:
				value = platform_dict[ID]
			except KeyError:
				value = 'SKUID%s' % ID
		elif flag == 'DEFAULT':
			try:
				value = default_dict[ID]
			except KeyError:
				value = 'DEFAULTID%s' % ID
		return value

	def section_parser(self,section):
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
				value=self.value_parser(list1)
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

	def value_parser(self,list1):
		list1 = [t for t in list1 if t != '']  # remove '' form list
		first_num = int(list1[0], 16)
		if list1[first_num + 1] == 'STRING':  # parser STRING
			value = 'L%s' % list1[-1]
		elif list1[first_num + 1] == 'ORDERED_LIST':  # parser ORDERED_LIST
			value_total = int(list1[first_num + 2])
			list2 = list1[-value_total:]
			tmp = [];
			line = ''
			for i in list2:
				if len(i) % 2 == 0 and len(i) != 2:
					for m in range(0, len(i) / 2):
						tmp.append('0x%02x' % (int('0x%s' % i, 16) >> m * 8 & 0xff))
				else:
					tmp.append('0x%s' % i)
			for i in tmp:
				line += '%s,' % i
			value = '{%s}' % line[:-1]
		else:
			value = "0x%01x" % int(list1[-1], 16)
		# value = hex(int(list1[-1], 16))  #parser Others
		return value

#parser Guid file, get guid name form guid value
class GUID(object):

	def __init__(self,guidfile):
		self.guidfile=guidfile
		self.guiddict = self.guid_dict()

	def guid_dict(self):
		guiddict={}
		with open(self.guidfile,'r') as file:
			lines = file.readlines()
		guidinfo=lines
		for line in guidinfo:
			list=line.strip().split(' ')
			if list:
				if len(list)>1:
					guiddict[list[0].upper()]=list[1]
				elif list[0] != ''and len(list)==1:
					print "Error:line %s can't be parser in %s"%(line.strip(),self.guidfile)
			else:
				print "No data in %s" %self.guidfile
		return guiddict

	def guid_parser(self,guid):
		if self.guiddict.has_key(guid.upper()):
			return self.guiddict[guid.upper()]
		else:
			print  "GUID %s not found in file %s"%(guid, self.guidfile)
			return guid

class write2file(object):

	def __init__(self,Output):
		self.output=Output
		self.text=''
		if os.path.exists(self.output):
			os.remove(self.output)

	def add2file(self,content):
		self.text = ''
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

class duration(object):

	def stamp(self):
		return datetime.datetime.now()

	def dtime(self,start,end,id=None):
		if id:
			pass
			print "%s time:%s" % (id,str(end - start))
		else:
			pass
			print "Total time:%s" %str(end-start)[:-7]

def main():
	stamp=duration()
	start=stamp.stamp()
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
					run=mainprocess(options.guid,options.config,options.lst,options.output)
					run.write_all()
				else:
					print 'Error command, use -h for help'
			else:
				print 'Error command, use -h for help'
		else:
			print 'Error command, use -h for help'
	else:
		print 'Error command, use -h for help'
	end=stamp.stamp()
	stamp.dtime(start,end)

if __name__=='__main__':
	main()