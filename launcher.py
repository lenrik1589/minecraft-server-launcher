import hashlib
import json
import os
import pathlib
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


class Version:
	id: str
	version_type: str
	manifest_url: str
	manifest_sha1: str
	arguments: dict[str, list[str]]
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
		self.arguments = self.manifest["arguments"]

	def download(self, download_type: Optional[str] = "server", directory: Optional[Union[str, os.PathLike]] = None):
		if not directory:
			directory = self.id
		if not self.manifest_loaded:
			self.load_manifest()
		if self.downloads.__contains__(download_type):
			download = self.downloads.get(download_type)
			rundir = pathlib.Path(pathlib.Path(__file__, ).parent.absolute(), directory)
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
							print(rf"\033[2K\033[1A %{ceil(log10(file_size_dl))}d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100 / file_size))
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
					if lines[1+1] == "eula=false":
						lines[1+1] = "eula=true"
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


class VersionStorage:
	latest_release_id: str
	latest_snapshot_id: str
	versions: dict[str, Version] = {}

	def __init__(self, *args, **kwargs):
		if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
			kwargs = args[0]
		self.latest_release_id = kwargs.get("latest").get("release")
		self.latest_snapshot_id = kwargs.get("latest").get("snapshot")
		for version in kwargs.get("versions"):
			# print(f"parsing version manifest for version {version.get('id')}")
			self.versions[version.get('id')] = Version(**version)
		print(f"found {len(self.versions)} versions ({len([v for v in self.versions if self.versions[v].version_type == 'release'])} releases)")

	def get_latest_release(self):
		return self.versions.get(self.latest_release_id)


version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
fabric_installer_url = "https://meta.fabricmc.net/v2/versions/installer"
version_manifest = VersionStorage(json.load(request.urlopen(version_manifest_url)))
fabric_installer = json.load(request.urlopen(fabric_installer_url))
print("latest release:", version_manifest.latest_release_id)
print("latest fabric installer version:", latest_installer := fabric_installer[0].get("version"))
version_manifest.get_latest_release().start_server()

# subprocess.call(["java", "-jar", "server.jar"])
