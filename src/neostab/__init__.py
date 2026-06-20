import grp
import os.path
import pwd
import shutil
import urllib.parse
from enum import Enum

STABS_DIR = '/etc/neostab.d'
FSTAB_PATH = '/etc/fstab'


class ConfigFields(Enum):
	SECTION = 1
	FLAG = 2
	MAPPING = 3
	BLOCK = 4
	DEFINE = 5


def config_read_dict(fp):

	hierarchy = list()
	output = dict()
	output['DEFINES'] = dict()

	for command in config_read_mnemonics(fp):
		# command: (ConfigFields, ...)
		field_type = command[0]
		if field_type == ConfigFields.SECTION:
			# command: (SECTION, section_name)
			section = command[1]  # section name
			output[section] = dict()
			hierarchy = [output[section]]
		elif field_type == ConfigFields.FLAG:
			# command: (FLAG, indent, flag_name)
			depth = command[1]
			while depth < len(hierarchy):
				hierarchy.pop()
			flag_name = command[2]
			hierarchy[-1][flag_name] = True
		elif field_type == ConfigFields.MAPPING:
			# command: (MAPPING, depth, key, value)
			depth = command[1]
			while depth < len(hierarchy):
				hierarchy.pop()
			key = command[2]
			value = command[3]
			hierarchy[-1][key] = value
		elif field_type == ConfigFields.BLOCK:
			# command: (BLOCK, depth, block_name)
			depth = command[1]
			while depth < len(hierarchy):
				hierarchy.pop()
			block_name = command[2]
			hierarchy[-1][block_name] = dict()
			hierarchy.append(hierarchy[-1][block_name])
		elif field_type == ConfigFields.DEFINE:
			# command: (DEFINE, key, value)
			key = command[1]
			value = command[2]
			output['DEFINES'][key] = value

	return output


def config_read_mnemonics(fp):
	indentation = None
	signature_found = False

	for line_no, line in enumerate(fp):
		# remove newline character
		if line[-1] == '\n':
			line = line[:-1]

		if line_no == 0:
			if line == '#neostab':
				signature_found = True
				continue
			else:
				raise Exception('#neostab signature not found')

		if len(line) == 0 or line.startswith(';'):
			continue

		if line[0] == '#':
			key, _cs, val = line[1:].partition(': ')
			yield (ConfigFields.DEFINE, key, val)
			continue

		if not line[0].isspace():
			# 'top level' text may only be a section name
			# in my config format
			yield (ConfigFields.SECTION, line.strip('\t\n '))

		else:
			# learn indentation from first indented block
			if indentation is None:
				indentation = ''
				# loop through each character until a non-
				# whitespace character is found to learn
				# how many tabs/spaces the user wants to
				# use to indicate depth
				for character in line:
					if character.isspace():
						indentation += character
					else:
						break

			line, indent_level = count_and_remove_indent(line, indentation)

			key_name, colon, value = line.partition(':')
			if colon == '':
				yield (ConfigFields.FLAG, indent_level, key_name)
			elif value == '':
				yield (ConfigFields.BLOCK, indent_level, key_name)
			else:
				if value[0] == ' ':
					value = value[1:]
				else:
					raise Exception(
						f'expected whitespace at beginning of value at line {line_no}'
					)
				yield (ConfigFields.MAPPING, indent_level, key_name, value)

	if not signature_found:
		raise Exception('#neostab signature not found')


def count_and_remove_indent(line, indentation):

	buffer = ''
	indent_level = 0
	for char in line:
		buffer += char
		if buffer == indentation:
			indent_level += 1
			buffer = ''
	return (buffer, indent_level)


def listdir_full_names(top):

	for file in sorted(os.listdir(top)):
		p = os.path.join(top, file)
		if os.path.isfile(p):
			yield p


def create_fstab_entries(config):

	for mountpoint in config:
		if mountpoint == 'DEFINES':
			continue
		output_options = dict()
		init_section(output_options, config, mountpoint)
		if len(output_options) != 0:
			yield output_options


def init_section(output_options, config, name, extending=False):

	options = config[name]
	if 'phony' in options and not extending:
		return

	if 'options' not in output_options:
		output_options['options'] = dict()

	if 'extends' in options:
		# print(name, "extending", options["extends"])
		init_section(output_options, config, options['extends'], extending=True)

	# print(name)

	if 'options' in options:
		for option in options['options']:
			# not-flags remove the flag if it was there
			if option.startswith('!'):
				if 'options' in output_options:
					if option[1:] in output_options['options']:
						del output_options['options'][option[1:]]
				continue

			output_options['options'][option] = options['options'][option]

	def copy_if_exists(n):
		if n in options:
			output_options[n] = options[n]
			return True
		else:
			return False

	def flag_to_value(f, v):
		if output_options[f] is True:
			output_options[f] = v

	copy_if_exists('mkdir')
	copy_if_exists('group')
	copy_if_exists('user')
	copy_if_exists('mode')

	if 'check' in output_options:
		flag_to_value('check', 1)
	else:
		if not copy_if_exists('check'):
			output_options['check'] = 0

	if 'dump' in output_options:
		flag_to_value('dump', 1)
	else:
		if not copy_if_exists('dump'):
			output_options['dump'] = 0

	if 'device' not in output_options and not copy_if_exists('device'):
		if not extending:
			raise Exception(f'section {name} does not have a device specified')

	if 'type' not in output_options and not copy_if_exists('type'):
		if not extending:
			raise Exception(
				f'section {name} does not have a filesystem type specified'
			)

	output_options['mountpoint'] = name


def fstab_quote(s):

	# anything other than ' ' and '\t' is
	# not exactly well documented. tell me
	# if something seems to fail to escape
	# with neostab.

	return (
		s.replace(' ', '\\040')
		.replace('\t', '\\011')
		.replace('@', '\\101')
		.replace(',', '\\,')
	)


def fstab_line(entry):

	if len(entry) == 0:
		return ''

	options_strs = []

	for key in entry['options']:
		value = entry['options'][key]
		if value is True:
			options_strs.append(key)
		else:
			if key.startswith('x-gvfs'):
				options_strs.append(
					fstab_quote(key + '=' + urllib.parse.quote(value))
				)
			else:
				options_strs.append(fstab_quote(key + '=' + value))

	options_str = ','.join(options_strs)

	mountpoint_str = fstab_quote(entry['mountpoint'])
	device_str = fstab_quote(entry['device'])
	type_str = fstab_quote(entry['type'])

	return '\t'.join(
		[
			device_str,
			mountpoint_str,
			type_str,
			options_str,
			f'{entry["dump"]} {entry["check"]}',
		]
	)


def load_stabs():

	stabs = []

	for file in listdir_full_names(STABS_DIR):
		print('Reading', file)
		with open(file) as fp:
			try:
				stabs.append(config_read_dict(fp))
			except Exception as e:
				if len(e.args) >= 1 and e.args[0] == '#neostab signature not found':
					print('- No #neostab signature. skipping')
					continue
				else:
					raise e

	return sorted(stabs, key=lambda s: -int(s['DEFINES'].get('priority', '0')))


def fstab_lines_from_stabs(stabs):

	for stab in stabs:
		for mount in create_fstab_entries(stab):
			yield fstab_line(mount)


def modestr_to_n(m):

	return int(m, 8)


def group_lookup(g):

	try:
		return int(g)
	except ValueError:
		return grp.getgrnam(g).gr_gid


def user_lookup(g):

	try:
		return int(g)
	except ValueError:
		return pwd.getpwnam(g).pw_uid


def install_stabs(stabs, simulate=False):

	def ensure_mode(path, mode):
		def would_set():
			print('Would set mode:', path, '=', oct(mode))

		if os.path.isdir(path):
			st = os.stat(path)
			if st.st_mode & 0o777 != mode:
				if simulate:
					would_set()
				else:
					print(path, 'mode =', oct(mode))
					os.chmod(path, mode)
		elif simulate:
			would_set()

	def ensure_gu(path, group, user):
		def would_set():
			print('Would set user:group:', path, '=', user, ':', group)

		if os.path.isdir(path):
			st = os.stat(path)
			print(path, st.st_uid, st.st_gid, user, group)
			if st.st_uid != user or st.st_gid != group:
				if simulate:
					would_set()
				else:
					print(path, 'user:group =', user, ':', group)
					os.chown(path, user, group)
		elif simulate:
			would_set()

	fstab = '# Generated by neostab\n\n'
	for stab in stabs:
		for mount in create_fstab_entries(stab):
			mode = modestr_to_n(mount.get('mode', '777'))

			if 'mkdir' in mount and not os.path.isdir(mount['mountpoint']):
				if simulate:
					print('Would make dir:', mount['mountpoint'])
				else:
					print('makedirs', mount['mountpoint'], end='', flush=True)
					try:
						os.makedirs(mount['mountpoint'], mode)
						print()
					except os.FileExistsError:
						print(' -- failed, continuing')

			if 'mode' in mount:
				ensure_mode(mount['mountpoint'], mode)

			if 'group' in mount and 'user' in mount:
				ensure_gu(
					mount['mountpoint'],
					group_lookup(mount['group']),
					user_lookup(mount['user']),
				)

			fstab += fstab_line(mount) + '\n'

	if simulate:
		print('#######')
		print(f'# {FSTAB_PATH} would be overwritten with the content:')
		print('#######')
		print(fstab)
		print('#######')
	else:
		print('Writing', FSTAB_PATH)
		with open(FSTAB_PATH, 'w') as fp:
			fp.write(fstab)

		if shutil.which('systemctl'):
			print('Telling systemd to read our new fstab')
			os.system('systemctl daemon-reload')


def main():
	install_stabs(load_stabs(), simulate=(os.geteuid() != 0))


if __name__ == '__main__':
	main()
