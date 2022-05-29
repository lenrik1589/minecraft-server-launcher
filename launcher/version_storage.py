import os
import pathlib
import subprocess
import sys
import urllib.error

import jsonpickle

import launcher
from launcher.resource_location import ResourceLocation


class VersionStorage:
	initialized = None
	default_java = "java"
	minecraft_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
	minecraft_manifest = ResourceLocation(minecraft_manifest_url)
	fabric_manifest_url = "https://meta.fabricmc.net/v2/versions"
	fabric_manifest = ResourceLocation(fabric_manifest_url)
	quilt_manifest_url = "https://meta.quiltmc.org/v3/versions"
	quilt_manifest = ResourceLocation(quilt_manifest_url)
	minecraft_versions = {}
	fabric_versions = {}
	quilt_versions = {}
	latest_mc_release: str
	latest_mc_snapshot: str
	latest_fabric_installer: str
	latest_fabric_loader: str
	latest_quilt_installer: str
	latest_quilt_loader: str
	java = {}
	MANIFESTS_UNAVAILABLE = """\
Neither are manifests cached nor are they accessible from the web
(as either Mojang, FabricMC or QuiltMC manifest files are inaccessible,
please check your internet connection, or notify the developer of filepath change)."""
	USING_CACHES = """\
WARNING: using cached version manifests as either Mojang, FabricMC orr QuiltMC manifest files are inaccessible,
please check your internet connection, or notify the developer."""

	def __new__(cls, *args, refresh=False, find_java=False, **kwargs):
		import json
		from urllib import request
		import datetime
		if cls.initialized:
			return cls.initialized
		try:
			if refresh or not (os.path.exists("cache") and datetime.datetime.now().timestamp() - os.stat("cache/minecraft manifest.json").st_mtime < 6 * 60 * 60):
				pathlib.Path("cache/versions").mkdir(exist_ok=True)
				for man in ["minecraft", "quilt", "fabric"]:
					try:
						open(f"cache/{man} manifest.json", "x").close()
					except FileExistsError:
						pass
				with open("cache/minecraft manifest.json", "r+") as mc_man, \
						open("cache/fabric manifest.json", "r+") as fmc_man, \
						open("cache/quilt manifest.json", "r+") as qmc_man:
					qmc_request = request.urlopen(cls.quilt_manifest_url)
					fmc_request = request.urlopen(cls.fabric_manifest_url)
					mc_request = request.urlopen(cls.minecraft_manifest_url)
					print("Using version manifests provided by Mojang and FabricMc")
					json.dump(json.load(mc_request), mc_man)
					json.dump(json.load(fmc_request), fmc_man)
					json.dump(json.load(qmc_request), qmc_man)
		except urllib.error.URLError:
			if os.path.exists("cache"):
				print(cls.USING_CACHES)
			else:
				raise RuntimeError(cls.MANIFESTS_UNAVAILABLE)
		try:
			with open("cache/minecraft manifest.json") as mc_man, \
					open("cache/fabric manifest.json") as fmc_man, \
					open("cache/quilt manifest.json") as qmc_man:
				minecraft_versions = json.load(mc_man)
				fabric_versions = json.load(fmc_man)
				quilt_versions = json.load(qmc_man)
		except json.JSONDecodeError as e:
			print("failed to read cached manifests, try running launcher config --refresh")
			exit(-1)
		program_config = launcher.load_config()
		if find_java:
			try:
				program_config["javas"] = VersionStorage.find_java()
			except:
				raise
			launcher.save_config(program_config)

		# noinspection PyArgumentList
		VersionStorage.latest_mc_release = minecraft_versions["latest"]["release"]
		VersionStorage.latest_mc_snapshot = minecraft_versions["latest"]["snapshot"]
		VersionStorage.latest_fabric_installer = list(filter(lambda data: data["stable"], fabric_versions['installer']))[0]["version"]
		VersionStorage.latest_fabric_loader = list(filter(lambda data: data["stable"], fabric_versions['loader']))[0]["version"]
		VersionStorage.latest_quilt_installer = quilt_versions['installer'][0]["version"]
		VersionStorage.latest_quilt_loader = quilt_versions['loader'][0]["version"]
		VersionStorage.minecraft_versions = minecraft_versions
		VersionStorage.fabric_versions = fabric_versions
		VersionStorage.quilt_versions = quilt_versions
		cls.initialized = True
		return cls.initialized

	@classmethod
	def resolve_mc_version(cls, version: str | None, snapshots: bool = False) -> str:
		if not cls.initialized:
			VersionStorage()
		if version in [v["id"] for v in cls.minecraft_versions["versions"]]:
			return version
		elif version is not None:
			raise RuntimeError(f"please check your input, {version} is not a valid minecraft version (or maybe not in mojank's manifest or my parsing is broken)!")
		else:
			return cls.latest_mc_snapshot if snapshots else cls.latest_mc_release

	@classmethod
	def resolve_fabric_version(cls, version: str) -> str:
		if not cls.initialized:
			VersionStorage()
		if version in [v["version"] for v in cls.fabric_versions["loader"]]:
			return version
		elif version is not None:
			raise RuntimeError(f"please check your input, {version} is not a valid loader version (or maybe not in fabricMC's manifest or my parsing is broken)!")
		else:
			return cls.latest_fabric_loader

	@classmethod
	def resolve_quilt_version(cls, version: str) -> str:
		if not VersionStorage.initialized:
			VersionStorage()
		if version in [v["version"] for v in VersionStorage.quilt_versions["loader"]]:
			return version
		elif version is not None:
			raise RuntimeError(f"please check your input, {version} is not a valid loader version (or maybe not in fabricMC's manifest or my parsing is broken)!")
		else:
			return VersionStorage.latest_quilt_loader

	@classmethod
	def validate_mc_version(cls, version) -> bool:
		from launcher import MinecraftServerVersion
		if isinstance(version, MinecraftServerVersion):
			return True
		try:
			cls.resolve_mc_version(version, True)
			return True
		except RuntimeError:
			return False

	@classmethod
	def validate_fabric_version(cls, version) -> bool:
		if isinstance(version, ResourceLocation):
			return True
		try:
			cls.resolve_fabric_version(version)
			return True
		except RuntimeError:
			return False

	@classmethod
	def validate_quilt_version(cls, version) -> bool:
		if isinstance(version, ResourceLocation):
			return True
		try:
			cls.resolve_quilt_version(version)
			return True
		except RuntimeError:
			return False

	@classmethod
	def resolve_mc_jar(cls, version: str):
		with open("cache/minecraft manifest.json") as file:
			manifest = jsonpickle.loads(file.read())
		# print()
		data = list(filter(lambda ver: ver["id"] == version, manifest["versions"]))[0]
		from launcher import MinecraftServerVersion
		return MinecraftServerVersion(version, ResourceLocation(data["url"], data["sha1"], 0))

	@classmethod
	def install_mod_loader(cls, loader, minecraft_version, loader_version, folder):
		program_config = launcher.load_config()
		if loader not in program_config.setdefault("mod loaders", {}) or program_config["mod loaders"][loader].url:
			latest_installer = getattr(VersionStorage, f"{loader}_versions")["installer"][0]
			program_config["mod loaders"][loader] = ResourceLocation(latest_installer["url"], None, None)
		program_config["mod loaders"][loader].download("mod loaders installers")
		match loader:
			case "quilt":
				cmd = [
					VersionStorage.default_java, "-jar",
					f"mod loaders installers/{program_config['mod loaders'][loader].filename}",
					"install", "server",
					minecraft_version.version, loader_version, f"--install-dir=\"{folder}\""
				]
				prg = subprocess.Popen(cmd)
				prg.wait()
			case "fabric":
				cmd = [
					VersionStorage.default_java, "-jar",
					f"mod loaders installers/{program_config['mod loaders'][loader].filename}",
					"install", "server",
					minecraft_version.version, loader_version, f"-dir=\"{folder}\""
				]
				prg = subprocess.Popen(cmd)
				prg.wait()
		launcher.save_config(program_config)

	@classmethod
	def find_java(cls):
		match sys.platform:
			case "linux":
				with os.popen("which java") as which_java:
					which = which_java.read()
					print(which)
			case "nt":
				pass
			case p:
				print()
