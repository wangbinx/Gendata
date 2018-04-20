#!/usr/bin/python
import re,os,datetime
from optparse import OptionParser

dscstatement='''[Defines]
  VPD_TOOL_GUID                  = 8C3D856A-9BE6-468E-850A-24F7A8D38E08

[SkuIds]
  0|DEFAULT              # The entry: 0|DEFAULT is reserved and always required.

[DefaultStores]
  0|STANDARD             # UEFI Standard default  0|STANDARD is reserved.
  1|MANUFACTURING        # UEFI Manufacturing default 1|MANUFACTURING is reserved.

[PcdsDynamicExVpd.common.DEFAULT]
  gEfiMdeModulePkgTokenSpaceGuid.PcdNvStoreDefaultValueBuffer|*
'''

decstatement = '''[Guids]
  gStructPcdTokenSpaceGuid = {0x3f1406f4, 0x2b, 0x487a, {0x8b, 0x69, 0x74, 0x29, 0x1b, 0x36, 0x16, 0xf4}}

[PcdsFixedAtBuild,PcdsPatchableInModule,PcdsDynamic,PcdsDynamicEx]
'''

infstatement = '''[Pcd]
'''

SECTION='PcdsDynamicHii'
PCD_NAME='gStructPcdTokenSpaceGuid.Pcd'

error=[]

class parser_lst(object):

	def __init__(self,filelist):
		self._ignore=['EFI_HII_REF', 'EFI_HII_TIME', 'EFI_STRING_ID', 'EFI_HII_DATE', 'BOOLEAN', 'UINT8', 'UINT16', 'UINT32', 'UINT64']
		self.file=filelist
		self.text=self.megre_lst()[0]
		self.content=self.megre_lst()[1]

	def megre_lst(self):
		alltext=''
		content={}
		for file in self.file:
			with open(file,'r') as f:
				read =f.read()
			alltext += read
			content[file]=read
		return alltext,content

	def struct_lst(self):#{struct:lst file}
		structs_file={}
		name_format = re.compile(r'(?<!typedef)\s+struct (\w+) {.*?;', re.S)
		for i in self.content.keys():
			structs= name_format.findall(self.content[i])
			if structs:
				for j in structs:
					if j not in self._ignore:
						structs_file[j]=i
			else:
				print "%s"%structs
		return structs_file

	def struct(self):#struct:{offset:name}
		name_re = re.compile('(\w+)')
		name_format = re.compile(r'(?<!typedef)\s+struct (\w+) {.*?;', re.S)
		name=name_format.findall(self.text)
		info={}
		unparse=[]
		if name:
			name=list(set(name).difference(set(self._ignore)))
			for struct in name:
				s_re = re.compile(r'struct %s :(.*?);'% struct, re.S)
				content = s_re.search(self.text)
				if content:
					tmp_dict = {}
					text = content.group().split('+')
					for line in text[1:]:
						line = name_re.findall(line)
						if line:
							if len(line) == 5:
								if line[4] in ['UINT8', 'UINT16', 'UINT32', 'UINT64']:
									offset = int(line[0], 10)
									t_name = line[2] + '[0]'
									tmp_dict[offset] = t_name
									uint = int(re.search('\d+', line[4]).group(0), 10)
									bit = uint / 8
									for i in range(1, int(line[3], 10)):
										offset += bit
										t_name = line[2] + '[%s]' % i
										tmp_dict[offset] = t_name
								else:
									line.append(struct)
									unparse.append(line)
							else:
								offset = int(line[0], 10)
								t_name = line[2]
								tmp_dict[offset] = t_name
					info[struct] = tmp_dict
			if len(unparse) != 0:
				for u in unparse:
					if u[4] in info.keys():
						unpar = self.nameISstruct(u,info[u[4]])
						info[u[5]]= dict(info[u[5]].items()+unpar[u[5]].items())
		else:
			print "ERROR: No struct name found in %s" % self.file
			error.append("ERROR: No struct name found in %s" % self.file)
		return info

	def nameISstruct(self,line,key_dict):
		dict={}
		dict2={}
		s_re = re.compile(r'struct %s :(.*?);' % line[4], re.S)
		size_re = re.compile(r'mTotalSize \[(\S+)\]')
		content = s_re.search(self.text)
		if content:
			s_size = size_re.findall(content.group())[0]
		else:
			print "ERROR: Struct %s not define mTotalSize in lst file" %line[4]
			error.append("ERROR: Struct %s not define mTotalSize in lst file" %line[4])
		size = int(line[0], 10)
		for j in range(0, int(line[3], 10)):
			for k in key_dict.keys():
				offset = size  + k
				name ='%s.%s' %((line[2]+'[%s]'%j),key_dict[k])
				dict[offset] = name
			size = int(s_size,16)+size
		dict2[line[5]] = dict
		return dict2

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
				print "ERROR: Can't find Struct or name in lst file, please check have this format:efivarstore XXXX, name=xxxx"
				error.append("ERROR: Can't find Struct or name in lst file, please check have this format:efivarstore XXXX, name=xxxx")
		return efivarstore_dict

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
			all_txt = read.split('DEFAULT')
			for i in all_txt[1:]:
				part = [] #save all infomation for DEFAULT_ID
				str_id=''
				ids = ids_re.findall(i.replace(' ',''))
				for m in ids:
					str_id +=m
				part.append(ids)
				section = i.split('\nQ') #split with '\nQ ' to get every block
				part +=self.section_parser(section)
				info_dict[str_id] = self.section_parser(section)
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
			text +="%s.common.%s.%s,"%(SECTION,self.id_name(platform_id[i],'PLATFORM'),self.id_name(default_id[i],'DEFAULT'))
		return '\n[%s]\n'%text[:-1]

	def id_name(self,ID, flag):
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
		else:
			value = None
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
					if attribute[0] in ['0x3','0x7']:
						offset = int(offset[0], 16)
						#help = help_re.findall(x)
						text = offset, name[0], guid[0], value, attribute[0]
						part.append(text)
		return(part)

	def value_parser(self, list1):
		list1 = [t for t in list1 if t != '']  # remove '' form list
		first_num = int(list1[0], 16)
		if list1[first_num + 1] == 'STRING':  # parser STRING
			value = 'L%s' % list1[-1]
		elif list1[first_num + 1] == 'ORDERED_LIST':  # parser ORDERED_LIST
			value_total = int(list1[first_num + 2])
			list2 = list1[-value_total:]
			tmp = []
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

	def __init__(self,path):
		self.path = path
		self.guidfile = self.gfile()
		self.guiddict = self.guid_dict()

	def gfile(self):
		for root, dir, file in os.walk(self.path, topdown=True, followlinks=False):
			if 'FV' in dir:
				gfile = os.path.join(root,'Fv','Guid.xref')
				if os.path.isfile(gfile):
					return gfile
				else:
					print "ERROR: Guid.xref file not found"
					error.append("ERROR: Guid.xref file not found")
					exit()

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
					print "Error: line %s can't be parser in %s"%(line.strip(),self.guidfile)
					error.append("Error: line %s can't be parser in %s"%(line.strip(),self.guidfile))
			else:
				print "ERROR: No data in %s" %self.guidfile
				error.append("ERROR: No data in %s" %self.guidfile)
		return guiddict

	def guid_parser(self,guid):
		if self.guiddict.has_key(guid.upper()):
			return self.guiddict[guid.upper()]
		else:
			print "ERROR: GUID %s not found in file %s"%(guid, self.guidfile)
			error.append("ERROR: GUID %s not found in file %s"%(guid, self.guidfile))
			return guid

class PATH(object):

	def __init__(self,path):
		self.path=path
		self.rootdir=self.get_root_dir()
		self.usefuldir=[]
		self.lstinf = {}
		for path in self.rootdir:
			for o_root, o_dir, o_file in os.walk(os.path.join(path, "OUTPUT"), topdown=True, followlinks=False):
				for INF in o_file:
					if os.path.splitext(INF)[1] == '.inf':
						for l_root, l_dir, l_file in os.walk(os.path.join(path, "DEBUG"), topdown=True,
															 followlinks=False):
							for LST in l_file:
								if os.path.splitext(LST)[1] == '.lst':
									self.lstinf[os.path.join(l_root, LST)] = os.path.join(o_root, INF)
									self.usefuldir.append(path)

	def get_root_dir(self):
		rootdir=[]
		for root,dir,file in os.walk(self.path,topdown=True,followlinks=False):
			if "OUTPUT" in root:
				updir=root.split("OUTPUT",1)[0]
				rootdir.append(updir)
		rootdir=list(set(rootdir))
		return rootdir

	def lst_inf(self):
		return self.lstinf

	def package(self):
		package={}
		package_re=re.compile(r'Packages\.\w+]\n(.*)',re.S)
		for i in self.lstinf.values():
			with open(i,'r') as inf:
				read=inf.read()
			section=read.split('[')
			for j in section:
				p=package_re.findall(j)
				if p:
					package[i]=p[0].rstrip()
		return package

	def header(self,struct):
		header={}
		head_re = re.compile(r'} %s;[\s\S\n]+h{1}"'%struct,re.M|re.S)
		head_re2 = re.compile(r'#line[\s\d]+"(\S+)"')
		for i in self.lstinf.keys():
			with open(i,'r') as lst:
				read = lst.read()
			h = head_re.findall(read)
			if h:
				head=head_re2.findall(h[0])
				if head:
					format = head[0].replace('\\\\','/').replace('\\','/')
					name =format.split('/')[-1]
					head = self.makefile(name).replace('\\','/')
					header[struct] = head
		return header

	def makefile(self,filename):
		re_format = re.compile(r'Pkg\\(.*%s)'%filename)
		for i in self.usefuldir:
			with open(os.path.join(i,'Makefile'),'r') as make:
				read = make.read()
			dir = re_format.findall(read)
			if dir:
				return dir[0]

class mainprocess(object):

	def __init__(self,InputPath,Config,OutputPath):
		self.init = 0xFCD00000
		self.inputpath = os.path.abspath(InputPath)
		self.outputpath = os.path.abspath(OutputPath)
		self.LST = PATH(self.inputpath)
		self.lst_dict = self.LST.lst_inf()
		self.Config = Config
		self.attribute_dict = {'0x3': 'NV, BS', '0x7': 'NV, BS, RT'}
		self.guid = GUID(self.inputpath)
		self.header={}

	def main(self):
		conf=Config(self.Config)
		config_dict=conf.config_parser() #get {'00':[offset,name,guid,value,attribute]...,'10':....}
		lst=parser_lst(self.lst_dict.keys())
		efi_dict=lst.efivarstore_parser() #get {name:struct} form lst file
		keys=sorted(config_dict.keys())
		all_struct=lst.struct()
		stru_lst=lst.struct_lst()
		title_list=[]
		info_list=[]
		header_list=[]
		inf_list =[]
		for i in stru_lst:
			tmp = self.LST.header(i)
			self.header.update(tmp)
		for id_key in keys:
			tmp_id=[id_key] #['00',[(struct,[name...]),(struct,[name...])]]
			tmp_info={} #{name:struct}
			for section in config_dict[id_key]:
				c_offset,c_name,c_guid,c_value,c_attribute = section
				if efi_dict.has_key(c_name):
					struct = efi_dict[c_name]
					title='%s%s|L"%s"|%s|0x00||%s\n'%(PCD_NAME,c_name,c_name,self.guid.guid_parser(c_guid),self.attribute_dict[c_attribute])
					if all_struct.has_key(struct):
						lstfile = stru_lst[struct]
						struct_dict=all_struct[struct]
						title2 = '%s%s|{0}|%s|0xFCD00000{\n <HeaderFiles>\n  %s\n <Packages>\n%s\n}\n' % (
						PCD_NAME, c_name, struct, self.header[struct], self.LST.package()[self.lst_dict[lstfile]])
						header_list.append(title2)
					else:
						print "ERROR: Struct %s can't found in lst file" %struct
						error.append("ERROR: Struct %s can't found in lst file" %struct)
					if struct_dict.has_key(c_offset):
						offset_name=struct_dict[c_offset]
						info = "%s%s.%s|%s\n"%(PCD_NAME,c_name,offset_name,c_value)
						inf = "%s%s\n"%(PCD_NAME,c_name)
						inf_list.append(inf)
						tmp_info[info]=title
					else:
						print "ERROR: Can't find offset %s with name %s in %s"%(c_offset,c_name,self.lst_dict.keys())
						error.append("ERROR: Can't find offset %s with name %s in %s"%(c_offset,c_name,self.lst_dict.keys()))
				else:
					print "ERROR: Can't find name %s in lst file"%(c_name)
					error.append("ERROR: Can't find name %s in lst file"%(c_name))
			tmp_id.append(self.reverse_dict(tmp_info).items())
			id,tmp_title_list,tmp_info_list = self.read_list(tmp_id)
			title_list +=tmp_title_list
			info_list.append(tmp_info_list)
		inf_list = self.del_repeat(inf_list)
		header_list = self.plus(self.del_repeat(header_list))
		title_all=list(set(title_list))
		info_list = self.del_repeat(info_list)
		return keys,title_all,info_list,header_list,inf_list


	def write_all(self):
		title_flag=1
		info_flag=1
		if not os.path.isdir(self.outputpath):
			os.makedirs(self.outputpath)
		decwrite = write2file(os.path.join(self.outputpath,'StructurePcd.dec'))
		dscwrite = write2file(os.path.join(self.outputpath,'StructurePcd.dsc'))
		infwrite = write2file(os.path.join(self.outputpath, 'StructurePcd.inf'))
		conf = Config(self.Config)
		ids,title,info,header,inf=self.main()
		decwrite.add2file(decstatement)
		decwrite.add2file(header)
		infwrite.add2file(infstatement)
		infwrite.add2file(inf)
		dscwrite.add2file(dscstatement)
		for id in ids:
			dscwrite.add2file(conf.eval_id(id))
			if title_flag:
				dscwrite.add2file(title)
				title_flag=0
			if len(info) == 1:
				dscwrite.add2file(info)
			elif len(info) == 2:
				if info_flag:
					dscwrite.add2file(info[0])
					info_flag =0
				else:
					dscwrite.add2file(info[1])

	def del_repeat(self,List):
		if len(List) == 1:
			return List
		elif len(List) == 2:
			return [List[0],self.__del(List[0],List[1])]
		else:
			return list(set(List))

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

	def plus(self,list):
		nums=[]
		for i in list:
			self.init += 1
			num = "0x%01x" % self.init
			j=i.replace('0xFCD00000',num.upper())
			nums.append(j)
		return nums

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

def stamp():
	return datetime.datetime.now()

def dtime(start,end,id=None):
	if id:
		pass
		print "%s time:%s" % (id,str(end - start))
	else:
		print "Total time:%s" %str(end-start)[:-7]


def main():
	start = stamp()
	usage = "Script.py [-p <build path>][-c <config file>][-o <output file>]"
	parser = OptionParser(usage)
	parser.add_option('-p', '--path', metavar='PATH', dest='path', help="Input the build path")
	parser.add_option('-c', '--config',metavar='FILENAME', dest='config', help="Input the '.config' file")
	parser.add_option('-o', '--output', metavar='PATH', dest='output', help="Output file PATH")
	(options, args) = parser.parse_args()
	if options.config:
		if options.path:
			if options.output:
				run = mainprocess(options.path, options.config, options.output)
				run.write_all()
				print 'Finished, Output files in directory %s'%os.path.abspath(options.output)
			else:
				print 'Error command, no output path, use -h for help'
		else:
			print 'Error command, no build path input, use -h for help'
	else:
		print 'Error command, no output file, use -h for help'
	if error:
		with open("ERROR.log",'wb') as err:
			for i in error:
				err.write(i+'\n')
		print "Some error find, error log in ERROR.log"
	end = stamp()
	dtime(start, end)

if __name__ == '__main__':
	main()