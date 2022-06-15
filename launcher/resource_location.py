import datetime
import hashlib
import json
import os
import pathlib
import shutil
import urllib.request

__all__ = ["ResourceLocation", "MinecraftServerVersion"]

from functools import partial

from math import floor


class ResourceLocation:
	def __init__(self, url: str, sha1: str | None = None, size: int | None = None, filename: str | None = None):
		self.url = url
		self.sha1 = sha1
		self.size = size
		self._filename = filename

	_filename = None
	filename = property(
		lambda self: self._filename or setattr(self, "_filename", self.url.split("/")[-1]) or self._filename,
		lambda self, new: setattr(self, "_filename", new),
		None, "Resource filename"
	)

	def download(self, folder: str | pathlib.Path, force: bool = False, check: bool = True):
		folder = folder if isinstance(folder, pathlib.Path) else pathlib.Path(folder)
		if not folder.exists():
			folder.mkdir(parents=True, exist_ok=True)
		if not os.path.exists(folder / self.filename) or (check and not self.check(folder)) or force:
			if self.url.startswith("http://") or self.url.startswith("https://"):
				with urllib.request.urlopen(self.url, timeout=3) as remote, open(folder / self.filename, "w+b") as owo:
					print(f"Downloading {self.filename}")
					downloaded = 0
					self.size = remote.length if self.size is None else self.size
					time_start = datetime.datetime.now()
					period = 20
					amplitude = 30
					x = lambda: datetime.datetime.now().timestamp() - time_start.timestamp()
					if remote.length is None:
						for data in iter(partial(remote.read, 64), b''):
							owo.write(data)
							pos = floor(2 * amplitude / period * abs(((x() - period / 2) % period) - period / 2) + .5)
							print("[" + " " * pos + "█" + " " * (amplitude - pos) + "] downloading, unknown size…", end="\r", flush=True)
					else:
						while remote.length > 0:
							data = remote.read(1024)
							owo.write(data)
							downloaded += len(data)
							done = (downloaded * 30) / (self.size if self.size != 0 else downloaded * 30)
							tiles = round(done)
							p = period - tiles / 1.6
							pos = floor(2 * (amplitude - tiles) / p * abs(((x() - p / 2) % p) - p / 2) + .5)
							print(f"[{' ' * pos}{'█' * tiles}{' ' * (30 - tiles - pos)}] {100 * done / 30:.2f}% ", end="\r", flush=True)
					print(f"downloaded in {datetime.datetime.now() - time_start}, {owo.tell()} bytes")
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
