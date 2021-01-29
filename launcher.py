import hashlib
import json
import os
import pathlib
import re as regex
import sys
import time
import urllib.request as request
from math import log10, ceil
from typing import Union, Optional


class Download:
	url: str
	sha1: str
	size: int
	file_name: str

	def __init__(self, *args, **kwargs):
		self.url = kwargs["url"]
		self.file_name = self.url.split("/")[-1]
		self.size = kwargs["size"]
		self.sha1 = kwargs["sha1"]

	def __str__(self):
		return f"filename: {self.file_name}\tsize: {self.size}"


class AssetIndex(Download):
	id: str
	total_size: int

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.total_size = kwargs["totalSize"]
		self.id = kwargs["id"]


class MinecraftVersion:
	id: str
	version_type: str
	manifest_url: str
	manifest_sha1: str
	arguments: dict[str, list[str]] = {}
	asset_index: AssetIndex
	compliance_level: int
	downloads: dict[str: Download] = {}
	manifest: dict
	manifest_loaded: bool = False

	def __init__(self, **kwargs):
		self.id = kwargs["id"]
		self.version_type = kwargs["type"]
		self.manifest_url = kwargs["url"]
		self.manifest_sha1 = kwargs["sha1"]
		self.compliance_level = kwargs["complianceLevel"]

	# self.load_manifest()

	def __str__(self):
		return f"{self.version_type}: {self.id}"

	def load_manifest(self):
		print(f"loading manifest for version {self.id}")
		self.manifest_loaded |= True
		self.manifest = json.load(request.urlopen(self.manifest_url))
		self.asset_index = AssetIndex(**self.manifest["assetIndex"])
		for entry in self.manifest["downloads"]:
			self.downloads[entry] = Download(**self.manifest["downloads"][entry])
		try:
			self.arguments = self.manifest["arguments"]
		except KeyError:
			pass

	def download(self, download_type: Optional[str] = "server", directory: Optional[Union[str, os.PathLike]] = None):
		if not directory:
			directory = self.id
		if not self.manifest_loaded:
			self.load_manifest()
		if self.downloads.__contains__(download_type):
			download = self.downloads[download_type]
			if isinstance(directory, str):
				rundir = pathlib.Path(pathlib.Path(__file__, ).parent.absolute(), directory)
			else:
				rundir = directory
			created_folder = False
			while True:
				try:
					os.chdir(rundir)
					with open(download.file_name, "rb") as f:
						u = request.urlopen(download.url)
						file_size = int(u.length)
						block_sz = 8192
						if os.path.getsize(download.file_name) == file_size:
							sha1 = hashlib.sha1()
							while True:
								data = f.read(block_sz)
								if not data:
									break
								sha1.update(data)
							if sha1.hexdigest() == self.downloads["server"].sha1:
								print("server file appears to be in place and correct")
								break
						f = open(download.file_name, 'wb')
						print("Downloading: %s Bytes: %s" % (download.file_name, file_size))
						file_size_dl = 0

						while True:
							buffer = u.read(block_sz)
							if not buffer:
								break

							file_size_dl += len(buffer)
							f.write(buffer)
							# noinspection PyStringFormat
							print(rf"Downloading %{ceil(log10(file_size / 1024))}dKB/{file_size // 1024}KB  [%3.2f%%]" % (
								file_size_dl // 1024, file_size_dl * 100 / file_size))
					break
				except FileNotFoundError:
					try:
						os.makedirs(rundir)
						print(f"server folder for version {self.id} is not found creating")
						created_folder = True
					except FileExistsError:
						open(download.file_name, "x").close()
						if not created_folder:
							print(f"server jar for version {self.id} is not found creating")
		else:
			raise AttributeError

	def start_server(self, directory: Optional[Union[str, os.PathLike]] = None):
		print("checking server jar")
		self.download(directory=directory)
		try:
			print("checking EULA")
			with open("eula.txt", "r") as eula:
				if len((lines := eula.readlines())) == 3:
					if lines[1 + 1] == "eula=false":
						lines[1 + 1] = "eula=true"
						eula.close()
						eula = open("eula.txt", "w")
						eula.writelines(lines)
		except FileNotFoundError:
			with open("eula.txt", "w") as eula:
				eula.write("""#By changing the setting below to TRUE you are indicating your agreement"""
						f""" to our EULA (https://account.mojang.com/documents/minecraft_eula).
#{time.asctime(time.gmtime())}
eula=true""")
		finally:
			print("EULA agreed.")
		print("starting the server")
		os.system("java -jar server.jar")

	def start_fabric_server(self, directory: Optional[Union[str, os.PathLike]] = None):
		pass


class FabricVersion:
	maven: str
	stable: bool
	version: str

	def __init__(self, maven, stable, version):
		self.stable = stable
		self.maven = maven
		self.version = version


class FabricInstaller(FabricVersion):
	url: str
	file_name: str

	def __init__(self, url, **kwargs):
		super().__init__(**kwargs)
		self.url = url
		self.file_name = self.url.split("/")[-1]


class FabricLoader(FabricVersion):
	build: int
	separator: str

	def __init__(self, build, separator, **kwargs):
		super().__init__(**kwargs)
		self.build = build
		self.separator = separator


class VersionStorage:
	latest_release_id: str
	latest_snapshot_id: str
	latest_fabric_installer: str = None
	latest_fabric_loader: str = None
	minecraft_versions: dict[str, MinecraftVersion] = {}
	fabric_installer_versions: dict[str, FabricInstaller] = {}
	fabric_loader_versions: dict[str, FabricLoader] = {}

	def __init__(self, *args, latest, **kwargs):
		if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
			kwargs = args[0]
		self.latest_release_id = latest["release"]
		self.latest_snapshot_id = latest["snapshot"]
		for version in kwargs["versions"]:
			# print(f"parsing version manifest for version {version['id')}")
			self.minecraft_versions[version['id']] = MinecraftVersion(**version)
		print(
			f"found {len(self.minecraft_versions)} versions ({len([v for v in self.minecraft_versions if self.minecraft_versions[v].version_type == 'release'])} releases)")

	def load_fabric(self, versions: Union[dict, list[dict]]):
		print(versions["installer"])
		for installer_version in versions["installer"]:
			if not self.latest_fabric_installer and installer_version["stable"]:
				self.latest_fabric_installer = installer_version["version"]
			self.fabric_installer_versions[installer_version["version"]] = FabricInstaller(**installer_version)
		for loader_version in versions["loader"]:
			if not self.latest_fabric_loader and loader_version["stable"]:
				self.latest_fabric_loader = loader_version["version"]
			self.fabric_loader_versions[loader_version["version"]] = FabricLoader(**loader_version)

	def get_latest_release(self):
		return self.get_version(self.latest_release_id)

	def get_latest_snapshot(self):
		return self.get_version(self.latest_snapshot_id)

	def get_version(self, version):
		return self.minecraft_versions[version] if not version == 'latest' else self.get_latest_release()

	def load_installer_version(self, directory: Optional[Union[str, os.PathLike]] = None, version: str = "latest"):
		if version == "latest":
			version = self.latest_fabric_installer
		download = self.fabric_installer_versions[version]
		if isinstance(directory, str):
			rundir = pathlib.Path(pathlib.Path(__file__, ).parent.absolute(), directory)
		elif isinstance(directory, pathlib.Path):
			rundir = directory
		else:
			rundir = pathlib.Path(pathlib.Path(__file__, ).parent.absolute())
		created_folder = False
		while True:
			try:
				os.chdir(rundir)
				with open(download.file_name, "rb") as file:
					u = request.urlopen(download.url)
					_sha1 = request.urlopen(download.url + ".sha1").read().decode()
					file_size = int(u.length)
					block_sz = 8192
					if os.path.getsize(download.file_name) == file_size:
						sha1 = hashlib.sha1()
						while True:
							data = file.read(block_sz)
							if not data:
								break
							sha1.update(data)
						if sha1.hexdigest() == _sha1:
							print("fabric installer appears to be in place and correct")
							break
					file.close()
					file = open(download.file_name, 'wb')
					print("Downloading: %s Bytes: %s" % (download.file_name, file_size))
					file_size_dl = 0

					while True:
						buffer = u.read(block_sz)
						if not buffer:
							break

						file_size_dl += len(buffer)
						file.write(buffer)
						# noinspection PyStringFormat
						print(rf"Downloading %{ceil(log10(file_size / 1024))}dKB/{file_size // 1024}KB  [%3.2f%%]" % (
							file_size_dl // 1024, file_size_dl * 100 / file_size))
				break
			except FileNotFoundError:
				try:
					os.makedirs(rundir)
					print(f"installer folder not found creating")
					created_folder = True
				except FileExistsError:
					open(download.file_name, "x").close()
					if not created_folder:
						print(f"installer jar for version {version} is not found creating")

	def check_fabric_installer(self):
		self.load_installer_version()

	def enable_fabric(self):
		self.check_fabric_installer()


version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
fabric_versions_url = "https://meta.fabricmc.net/v2/versions"
fabric_loader_url = "https://meta.fabricmc.net/v2/versions/loader"
version_manifest = VersionStorage(**json.load(request.urlopen(version_manifest_url)))
version_manifest.load_fabric(json.load(request.urlopen(fabric_versions_url)))
print("latest release:", version_manifest.latest_release_id)
print("latest installer:", version_manifest.latest_fabric_installer)
print("latest loader:", version_manifest.latest_fabric_loader)

snapshots_enabled: bool = False
fabric_enabled: bool = False
unrecognized_options: list[str] = []
installer_options: list[str] = []
server_options: list[str] = []
jvm_options: list[str] = []
minecraft_version: str = 'latest'
parsed_args: int = 0


def help():
	print("""
	--fabric\tlaunches server with fabric
	--snapshot\tenables snapshots
	--version v\tspecifies which version to use, latest by default
	""")


def check_version():
	if (version_manifest.get_version(minecraft_version).version_type == 'snapshot' and not regex.match(
			'1\\.\\d+(\\.\\d+)?', minecraft_version)) and not snapshots_enabled:
		raise Exception("to enable snapshots")


print("all          >", sys.argv)

while len(sys.argv) > 1:
	token = None
	if (popped := sys.argv.pop()) == '--snapshot':
		installer_options.append("--snapshot")
		snapshots_enabled = True
	elif popped == '--fabric':
		version_manifest.enable_fabric()
		fabric_enabled = True
	elif popped == '--version':
		minecraft_version = unrecognized_options.pop()
		if (not regex.match("[ab]?1\\.\\d{1,2}(\\.\\d+(_\\d+)?)?(-(rc|pre)\\d+)?|\\d{2,}w\\d{2}([a-z]|infinite)|"
							"3D Shareware v1\\.34|"
							"1\\.RV-Pre1|"
							"inf-20100618|"
							"c0\\.3?0[_.]\\d+[ac](_03)?|"
							"rd-\\d+", minecraft_version)) or not version_manifest.minecraft_versions[
			minecraft_version]:
			raise Exception("invalid version string")
	elif popped == '--fabric-options':
		while len(sys.argv) > 1 and (token := sys.argv.pop()) != "--server-options":
			installer_options.append(token)
		else:
			if token == "--server-options" or token == "--jvm-options":
				sys.argv.append(token)
	elif popped == '--server-options':
		while len(sys.argv) > 1 and (token := sys.argv.pop()) != "--fabric-options":
			installer_options.append(token)
		else:
			if token == "--fabric-options" or token == "--jvm-options":
				sys.argv.append(token)
	elif popped == '--jvm-options':
		while len(sys.argv) > 1 and (token := sys.argv.pop()) != "--fabric-options":
			installer_options.append(token)
		else:
			if token == "--fabric-options" or token == "--server-options":
				sys.argv.append(token)
	elif popped == "--help":
		help()
	else:
		unrecognized_options.append(popped)

print("fabric       >", fabric_enabled)
print("snapshot     >", snapshots_enabled)
print("version      >", minecraft_version)
print("jvm          >", jvm_options)
print("installer    >", installer_options)
print("server       >", server_options)
print("unrecognized >", unrecognized_options)
if minecraft_version == 'latest':
	if snapshots_enabled:
		minecraft_version = version_manifest.latest_snapshot_id
	else:
		minecraft_version = version_manifest.latest_release_id

if fabric_enabled:
	version_manifest.check_fabric_installer()
exit(0)
print(server := version_manifest.get_version(minecraft_version))
server.start_server()

# version_manifest.get_latest_release().start_server()

# subprocess.call(["java", "-jar", "server.jar"])
