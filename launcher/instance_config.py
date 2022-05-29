import os.path
import subprocess

import jsonpickle

from launcher.resource_location import MinecraftServerVersion, ResourceLocation
from launcher.version_storage import VersionStorage


# REQUESTS_SESSION = requests.session()
# REQUESTS_SESSION.mount('file://', LocalFileAdapter())


class InvalidVersionException(Exception):
	def __init__(self, version, component):
		super().__init__(f"Version {version} does not seem in the {component} version manifest, please check your config and modify with \"launcher config modify\" if needed.")


class InstanceConfig:
	folder: str
	name: str
	mc_version: MinecraftServerVersion | str = None
	custom_jar: ResourceLocation | None = None
	snap: bool = False
	mod_loader: str | None = None
	mod_loader_version: str | None = None
	mod_loader_installed: bool = False
	java_args: list[str] | None = None
	server_args: list[str] | None = None
	installed = False

	def __init__(self, name=None, version=None, mod_loader=None, mod_loader_version=None, snap=False, folder=None, custom_jar=None, server_args=["-nogui"]):
		self.snap = snap or False
		self.mc_version = VersionStorage.resolve_mc_version(version, self.snap)
		self.custom_jar = custom_jar
		self.name = name or self.mc_version
		print(name, folder)
		self.folder = (folder or self.name).replace(" ", "_")
		self.folder = self.folder if os.path.isabs(self.folder) else ("instances/" + self.folder)
		self.mod_loader = mod_loader
		if mod_loader:
			self.mod_loader_version = getattr(VersionStorage, f"resolve_{self.mod_loader}_version")(mod_loader_version)

	def install(self):
		if not (
				(
						mc_valid := VersionStorage.validate_mc_version(self.mc_version)
				) and (
				self.mod_loader is None or
				self.mod_loader_version is None or
				getattr(VersionStorage, f"validate_{self.mod_loader}_version")(self.mod_loader_version))
		):
			if not mc_valid:
				raise InvalidVersionException(self.mc_version, "Minecraft")
			else:
				raise InvalidVersionException(self.mod_loader_version, self.mod_loader)
		if self.mod_loader is not None and self.mod_loader_version is None:
			self.mod_loader_version = getattr(VersionStorage, f"latest_{self.mod_loader}_loader")
			self.save()
		if self.custom_jar:
			pass
		else:
			if not isinstance(self.mc_version, MinecraftServerVersion):
				self.mc_version = VersionStorage.resolve_mc_jar(self.mc_version)
			self.mc_version.download(self.folder, check=True)
			self.save()
			if self.mod_loader:
				if not self.mod_loader_version:
					self.mod_loader_version = getattr(VersionStorage, f"resolve_{self.mod_loader}_version")(None)
					self.save()
				self.mod_loader_installed = VersionStorage.install_mod_loader(self.mod_loader, self.mc_version, self.mod_loader_version, self.folder)
				self.save()
			try:
				with open(f"{self.folder}/eula.txt", "x") as eula:
					eula.write("eula=true")
			except FileExistsError:
				pass


	def run(self):
		if not self.installed:
			try:
				self.install()
			except Exception as e:
				raise
		if self.mod_loader:
			match self.mod_loader:
				case "quilt":
					os.chdir(self.folder)
					cmd = f'screen -d -m -S "{self.name}" zsh -c "{VersionStorage.default_java}{" " + " ".join(self.java_args) if self.java_args else ""} -jar quilt-server-launch.jar{" " + " ".join(self.server_args) if self.server_args else ""}"'
					os.popen(cmd)
					exit(f'Server "{self.name}" has been started, use "screen -r {self.name}" to view output')
				case "fabric":
					pass
		else:
			pass


	def toJson(self):
		import jsonpickle
		return jsonpickle.dumps(self, indent="\t")

	@classmethod
	def fromJson(cls, json):
		return jsonpickle.loads(json)

	def save(self):
		with open(self.folder + "/config.json", "w+") as file:
			file.truncate(0)
			file.seek(0)
			file.write(self.toJson())

	@classmethod
	def load(cls, path):
		with open(path + "/config.json", "r+") as file:
			file.seek(0)
			return cls.fromJson(file.read())
