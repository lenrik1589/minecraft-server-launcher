import hashlib
import json
import os
import pathlib
import shutil
import urllib.request

__all__ = ["ResourceLocation", "MinecraftServerVersion"]


class ResourceLocation:
	def __init__(self, url: str, sha1: str | None = None, size: int | None = None):
		self.url = url
		self.sha1 = sha1
		self.size = size

	filename = property(lambda self: self.url.split("/")[-1], None, None, "Resource filename")

	def download(self, folder, force: bool = False, check: bool = True):
		folder = folder if isinstance(folder, pathlib.Path) else pathlib.Path(folder)
		if not folder.exists():
			folder.mkdir(parents=True, exist_ok=True)
		if not os.path.exists(folder / self.filename) or (check and not self.check(folder)) or force:
			if self.url.startswith("http://") or self.url.startswith("https://"):
				with urllib.request.urlopen(self.url) as remote, open(folder / self.filename, "wb") as owo:
					print(f"Downloading {self.filename}")
					downloaded = 0
					self.size = remote.length if self.size is None else self.size
					while remote.length > 0:
						data = remote.read(8192)
						# for data in remote.iter_content(chunk_size=8192):
						owo.write(data)
						downloaded += len(data)
						done = (downloaded * 30) / (self.size if self.size != 0 else downloaded * 30)
						tiles = round(done)
						print(f"[{'█' * tiles}{' ' * (30 - tiles)}] {100 * done / 30:.2f}% ", end="\r", flush=True)
					print()
			elif os.path.exists(self.url):
				shutil.copy2(self.url, folder)
			else:
				raise FileNotFoundError(f"Resource {self.filename} ({self.url}) could not be found")
			return True

	def check(self, folder: str | pathlib.Path):
		folder = folder if isinstance(folder, pathlib.Path) else pathlib.Path(folder)
		if not (folder / self.filename).exists():
			return False
		with open(folder / self.filename, "rb") as owo:
			return self.sha1 is None or self.sha1 == hashlib.sha1(owo.read()).hexdigest()


class MinecraftServerVersion:
	version: str
	version_manifest: ResourceLocation
	version_jar: ResourceLocation

	def __init__(self, version, version_manifest: ResourceLocation | None = None, version_jar: ResourceLocation | None = None):
		self.version = version
		self.version_manifest = version_manifest
		self.version_jar = version_jar

	def download(self, folder, force: bool = False, check: bool = False):
		self.version_manifest.download("cache/versions/", force, check)
		with open("cache/versions/" + self.version_manifest.filename, "r") as manifest:
			self.version_jar = ResourceLocation(**json.loads(manifest.read())["downloads"]["server"])
		self.version_jar.download(folder, force, check)

	def check(self, folder):
		return self.version_manifest.check("cache/versions") and os.path.exists(f"cache/versions/{self.version_manifest.filename}") and self.version_jar.check(folder)

	def __str__(self):
		return f"MC server {self.version}"
