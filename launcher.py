import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.request as request
from math import log10, ceil
from typing import Union, Optional
import re as regex


class Download:
	url: str
	sha1: str
	size: int
	file_name: str

	def __init__(self, *args, **kwargs):
		self.url = kwargs.get("url")
		self.file_name = self.url.split("/")[-1]
		self.size = kwargs.get("size")
		self.sha1 = kwargs.get("sha1")

	def __str__(self):
		return f"filename: {self.file_name}\tsize: {self.size}"


class AssetIndex(Download):
	id: str
	total_size: int

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.total_size = kwargs.get("totalSize")
		self.id = kwargs.get("id")


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
		self.id = kwargs.get("id")
		self.version_type = kwargs.get("type")
		self.manifest_url = kwargs.get("url")
		self.manifest_sha1 = kwargs.get("sha1")
		self.compliance_level = kwargs.get("complianceLevel")

	# self.load_manifest()

	def __str__(self):
		return f"{self.version_type}: {self.id}"

	def load_manifest(self):
		print(f"loading manifest for version {self.id}")
		self.manifest_loaded |= True
		self.manifest = json.load(request.urlopen(self.manifest_url))
		self.asset_index = AssetIndex(**self.manifest.get("assetIndex"))
		for entry in self.manifest.get("downloads"):
			self.downloads.__setitem__(entry, Download(**self.manifest.get("downloads").get(entry)))
		try:
			self.arguments = self.manifest["arguments"]
		except:
			pass

	def download(self, download_type: Optional[str] = "server", directory: Optional[Union[str, os.PathLike]] = None):
		if not directory:
			directory = self.id
		if not self.manifest_loaded:
			self.load_manifest()
		if self.downloads.__contains__(download_type):
			download = self.downloads.get(download_type)
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
							if sha1.hexdigest() == self.downloads.get("server").sha1:
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
							print(rf"\033[2K\033[1A %{ceil(log10(file_size_dl))}d  [%3.2f%%]" % (
								file_size_dl, file_size_dl * 100 / file_size))
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
				eula.write(f"""#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://account.mojang.com/documents/minecraft_eula).
#{time.asctime(time.gmtime())}
eula=true""")
		finally:
			print("EULA agreed.")
		print("starting the server")
		os.system("java -jar server.jar")


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

	def __init__(self, url, **kwargs):
		super().__init__(**kwargs)
		self.url = url


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
		self.latest_release_id = latest.get("release")
		self.latest_snapshot_id = latest.get("snapshot")
		for version in kwargs.get("versions"):
			# print(f"parsing version manifest for version {version.get('id')}")
			self.minecraft_versions[version.get('id')] = MinecraftVersion(**version)
		print(
			f"found {len(self.minecraft_versions)} versions ({len([v for v in self.minecraft_versions if self.minecraft_versions[v].version_type == 'release'])} releases)")

	def load_fabric(self, installer_versions: Union[dict, list[dict]], loader_versions: Union[dict, list[dict]]):
		print(installer_versions)
		for installer_version in installer_versions:
			if not self.latest_fabric_installer and installer_version["stable"]:
				self.latest_fabric_installer = installer_version["version"]
			self.fabric_installer_versions[installer_version["version"]] = FabricInstaller(**installer_version)
		print(loader_versions)
		for loader_version in loader_versions:
			if not self.latest_fabric_loader and loader_version["stable"]:
				self.latest_fabric_loader = loader_version["version"]
			self.fabric_loader_versions[loader_version["version"]] = FabricLoader(**loader_version)

	def get_latest_release(self):
		return self.get_version(self.latest_release_id)

	def get_latest_snapshot(self):
		return self.get_version(self.latest_snapshot_id)

	def get_version(self, version):
		return self.minecraft_versions.get(version) if not version == 'latest' else self.get_latest_release()


version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
fabric_installer_url = "https://meta.fabricmc.net/v2/versions/installer"
fabric_loader_url = "https://meta.fabricmc.net/v2/versions/loader"
version_manifest = VersionStorage(**json.load(request.urlopen(version_manifest_url)))
version_manifest.load_fabric(json.load(request.urlopen(fabric_installer_url)),
							 json.load(request.urlopen(fabric_loader_url)))
print("latest release:", version_manifest.latest_release_id)
print("latest installer:", version_manifest.latest_fabric_installer)
print("latest loader:", version_manifest.latest_fabric_loader)

snapshots_enabled: bool = False
fabric_enabled: bool = False
unrecognized_options: list[str] = []
installer_options: list[str] = []
server_options: list[str] = []
jvm_options: list[str] = []
version: str = 'latest'
parsed_args: int = 0


def help():
	print("""
	--fabric\tlaunches server with fabric
	--snapshot\tenables snapshots
	--version v\tspecifies which version to use, latest by default
	""")


def check_version():
	if (version_manifest.get_version(version).version_type == 'snapshot' and not regex.match('1\\.\\d+(\\.\\d+)?', version)) and not snapshots_enabled:
		raise Exception("to enable snapshots")


print("all          >", sys.argv)

while len(sys.argv) > 1:
	if (popped := sys.argv.pop()) == '--snapshot':
		installer_options.append("--snapshot")
		snapshots_enabled = True
	elif popped == '--fabric':
		fabric_enabled = True
	elif popped == '--version':
		version = unrecognized_options.pop()
		if (not regex.match("[ab]?1\\.\\d{1,2}(\\.\\d+(_\\d+)?)?(-(rc|pre)\\d+)?|\\d{2,}w\\d{2}([a-z]|infinite)|"
							"3D Shareware v1\\.34|"
							"1\\.RV-Pre1|"
							"inf-20100618|"
							"c0\\.3?0[_.]\\d+[ac](_03)?|"
							"rd-\\d+", version)) or not version_manifest.minecraft_versions.get(version):
			raise Exception("invalid version string")
	elif popped == '--fabric-options':
		while len(sys.argv) > 1 and (next := sys.argv.pop()) != "--server-options":
			installer_options.append(next)
		else:
			if next == "--server-options" or next == "--jvm-options":
				sys.argv.append(next)
	elif popped == '--server-options':
		while len(sys.argv) > 1 and (next := sys.argv.pop()) != "--fabric-options":
			installer_options.append(next)
		else:
			if next == "--fabric-options" or next == "--jvm-options":
				sys.argv.append(next)
	elif popped == '--jvm-options':
		while len(sys.argv) > 1 and (next := sys.argv.pop()) != "--fabric-options":
			installer_options.append(next)
		else:
			if next == "--fabric-options" or next == "--server-options":
				sys.argv.append(next)
	elif popped == "--help":
		help()
	else:
		unrecognized_options.append(popped)

print("fabric       >", fabric_enabled)
print("snapshot     >", snapshots_enabled)
print("version      >", version)
print("jvm          >", jvm_options)
print("installer    >", installer_options)
print("server       >", server_options)
print("unrecognized >", unrecognized_options)
if version == 'latest':
	if snapshots_enabled:
		version = version_manifest.latest_snapshot_id
	else:
		version = version_manifest.latest_release_id
print(server := version_manifest.get_version(version))
server.start_server()

# version_manifest.get_latest_release().start_server()

# subprocess.call(["java", "-jar", "server.jar"])
