import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

import jsonpickle

from launcher.resource_location import ResourceLocation, MinecraftServerVersion
from .instance_config import InstanceConfig, InvalidVersionException
from .version_storage import VersionStorage

__all__ = ["InstanceConfig", "VersionStorage", "main", "ResourceLocation", "MinecraftServerVersion"]


def main():
	config_commands = ['list', 'create', 'modify', 'show', 'remove']
	args = sys.argv[1:]
	command = False
	version_storage_params = {}
	while not command and args:
		match args:
			case ('--refresh-manifests' | '--refresh' | "-r"), *more:
				version_storage_params["refresh"] = True
				args = more
			case '--find-java', *more:
				version_storage_params["find_java"] = True
				args = more
			case _:
				command = True
	VersionStorage(**version_storage_params)
	match args:
		case "help", *_:

			exit(
				f"""\
usage:
	launcher config {{{" | ".join(config_commands)}}}
		create [version / name] [args]
			creates config for a new instance, not installing it, to install use launcher install
		
			"version / name" string will go through all arguments and add everything to name or version until it hits first argument
			and it will be determined whether a "word" belongs to a version simply by assigning first valid version to version and everything else to name
			valid version aka version defined in minecraft_versions.json provided by Mojang/Microsoft
			
			arguments:
				--fabric [loader_version] shorthand for --mod-loader fabric [--mod-loader-version loader_version]
				--quilt [loader_version]  shorthand for --mod-loader quilt [--mod-loader-version loader_version]
				--mod-loader              specifies mod loader that the instance should use
				--mod-loader-version      specifies version of the loader to use, must go after the --mod-loader
				--version | -v            explicitly sets the version for the instance
		modify {{param}} {{new_value}}
			modifies 
		delete | remove {{instance name}}
			deletes instance and all related files CAUTION: operation is irreversible
	launcher\
"""
			)
		case "config", *config_args:
			match config_args:
				case "list", *more:
					if more:
						print("ignoring extra arguments as 'list' doesn't take any")
					if os.path.exists("instances"):
						program_config = load_config()
						count = len(program_config["instances"].keys())
						print(f"There {'is' if count == 1 else 'are'} {count or 'no'} instance{'s' if count != 1 else ''}{count and ':'}")
						for instance in program_config["instances"].values():
							config: InstanceConfig = InstanceConfig.load(instance)
							print(f"{config.name}: on minecraft {config.mc_version}{f' with {config.mod_loader} {config.mod_loader_version or str()}' if config.mod_loader else ''}")
					else:
						print('Currently there are no configs, create one using "install" or "config create"')
				case "create", *args:
					parsed_args = {}
					arg = False
					while args:
						match args:
							case "--quilt", *more:
								if "mod_loader" in parsed_args:
									exit(f"multiple mod loaders specified")
								if len(more) > 0 and VersionStorage.validate_quilt_version(more[0]):
									parsed_args["mod_loader_version"] = more.pop()
								parsed_args["mod_loader"] = "quilt"
								args = more
								arg = True
							case "--fabric", *more:
								if "mod_loader" in parsed_args:
									exit(f"mod loader specified multiple times")
								if len(more) > 0 and VersionStorage.validate_fabric_version(more[0]):
									parsed_args["mod_loader_version"] = more.pop()
								parsed_args["mod_loader"] = "fabric"
								args = more
								arg = True
							case ("--snapshot" | "--snapshots"), *more:
								args = more
								parsed_args["snap"] = True
							case ("--mod-loader"), *more:
								if len(more < 1):
									exit("You need to specify mod loader when using --mod-loader")
								if more[0] not in ["fabric", "quilt"]:
									exit("Right now only two supported loaders are fabric and quilt")
								if "mod_loader" in parsed_args:
									exit(f"mod loader specified multiple times")
								parsed_args["mod_loader"] = more.pop()
								args = more
								arg = True
							case ("--mod-loader-version"), *more:
								if "mod_loader" not in parsed_args:
									exit("There is no mod loader to specify version for")
								if len(more < 1):
									exit("You need to specify version when using --mod-loader-version")
								if not getattr(VersionStorage, f"validate_{parsed_args['mod_loader']}_version")(more[0]):
									exit(InvalidVersionException(more[0], parsed_args["mod_loader"]))
								parsed_args["mod_loader_version"] = more.pop()
								args = more
								arg = True
							case ("--version" | '-v'), *more:
								if len(more) > 0 and VersionStorage.validate_mc_version(more[0]):
									parsed_args['version'] = more.pop(0)
								else:
									exit(InvalidVersionException(more[0], "minecraft"))
								args = more
								arg = True
							case name, *more if not arg:
								args = more
								if "--version" not in more and VersionStorage.validate_mc_version(name) and "version" not in parsed_args:
									parsed_args["version"] = name
								else:
									if 'name' not in parsed_args:
										parsed_args["name"] = name
									else:
										parsed_args["name"] += " " + name
							case (*a, ):
								exit(f"extraneous arguments to config create: {' '.join(a)}")
					config = InstanceConfig(**parsed_args)
					os.makedirs(config.folder, exist_ok=True)
					subprocess.Popen(("git", "init"), cwd=config.folder).wait()
					try:
						open(config.folder + "/config.json", "x").close()
					except FileExistsError:
						exit("specified config already exists, to change it use 'config modify'")
					config.save()
					try:
						open("instances/config.json", "x").close()
					except FileExistsError:
						pass
					program_config = load_config()
					program_config["instances"][config.name] = config.folder
					save_config(program_config)
					print(f"created a config named '{config.name}' on {config.mc_version}{f' with {config.mod_loader}' if config.mod_loader else ''}")
				case ("delete" | "remove"), *args:
					if os.path.exists("instances"):
						program_config = load_config()
						name_length = 0
						found = None
						while not found:
							name_length += 1
							if len(args) < name_length:
								exit("you need to specify the instance name you want to remove, use config list to get existing instances.")
							elif (name := " ".join(args[:name_length])) in program_config["instances"]:
								found = program_config["instances"][name]
								config = InstanceConfig.load(found)
								if config:
									if input(f"If you are sure that you want to delete the config please type \"{config.name}\"\n") == config.name:
										try:
											shutil.rmtree(config.folder)
											del program_config["instances"][config.name]
											save_config(program_config)
										except Exception as e:
											exit(e)
									else:
										exit("Not sure, not deleting")
					else:
						exit("No configs exist")
				case 'modify', *args:
					if os.path.exists("instances"):
						program_config = load_config()
						name_length = 0
						found = None
						while not found:
							name_length += 1
							if len(args) < name_length + 2:
								exit("you need to specify at least the name, option and a new value.")
							elif (name := " ".join(args[:name_length])) in program_config["instances"]:
								found = program_config["instances"][name]
								config = InstanceConfig.load(found)
								args = args[name_length:]
								match args:
									case "name", *new_name:
										name = " ".join(new_name)
										del program_config["instances"][config.name]
										program_config["instances"][name] = config.folder
										save_config(program_config)
										old_name = config.name
										config.name = name
										config.save()
										print(f"Renamed instance {old_name} to {name} successfully.")
									case "move", *new_dir:
										folder = pathlib.Path(" ".join(new_dir).replace(" ", "_"))
										try:
											folder.mkdir(parents=True)
										except OSError:
											if not (folder.exists() and folder.is_dir()):
												exit("failed to create new folder")
										program_config["instances"][config.name] = str(folder)
										save_config(program_config)
										os.rename(config.folder, folder)
										old_folder = config.folder
										config.folder = str(folder)
										config.save()
										print(f"Moved instance {config.name} from {old_folder} to {folder}")
									case ["version", "modloader", *new] | ["version", "mod", "loader", *new]:
										if config.mod_loader is None:
											exit(f"Instance {config.name} does not have mod loader selected")
										version = " ".join(new)
										if not getattr(VersionStorage, f"validate_{config.mod_loader}_version")(version):
											exit(f"{version} is not a valid version of {config.mod_loader}.")
										config.mod_loader_version = version
										config.installed = False
										config.save()
									case ["version", *new] | ["version", "minecraft", *new]:
										print(*new)
										exit()
										version = " ".join(new)
										if not VersionStorage.validate_mc_version(version):
											exit(f"{version} is not a valid version of minecraft.")
										config.mc_version = version
										config.installed = False
										config.save()
									case ("custom", "jar" | "custom_jar"), "none":
										config.custom_jar = None
										config.installed = False
										config.save()
									case ("custom", "jar" | "custom_jar"), jar, sha1:
										config.custom_jar = ResourceLocation(jar, sha1, os.stat(jar, follow_symlinks=True).st_size)
										config.save()
									case ("custom", "jar" | "custom_jar"), jar:
										with open(jar, "rb") as jar_file:
											config.custom_jar = ResourceLocation(jar, hashlib.sha1(jar_file.read()).hexdigest(), os.stat(jar, follow_symlinks=True).st_size)
										config.save()
									case "java", "args", *args:
										if len(args) == 0:
											config.java_args = None
										else:
											config.java_args = args
										config.save()
									case "server", "args", *args:
										if len(args) == 0:
											config.server_args = None
										else:
											config.server_args = args
										config.save()
									case ("mod_loader", loader) | ("mod", "loader", loader) if loader.lower().removesuffix("mc") in ("none", None, "quilt", "fabric"):
										config.mod_loader = loader.lower().removesuffix("mc") if loader.lower() != "none" else None
										config.mod_loader_version = None
										config.save()
				case "show", *args:
					if os.path.exists("instances"):
						program_config = load_config()
						name_length = 0
						found = None
						while not found:
							name_length += 1
							if len(args) < name_length:
								exit("You need to specify a valid instance name.")
							elif (name := " ".join(args[:name_length])) in program_config["instances"]:
								found = program_config["instances"][name]
								config = InstanceConfig.load(found)
								args = args[name_length:]
								print(
									f"""\
Name: {config.name}
Version: {config.mc_version}{f'''
Custom jar: {config.custom_jar}''' if config.custom_jar else ""}{f'''
Mod loader: {config.mod_loader}
Loader version: {config.mod_loader_version}''' if config.mod_loader else ""}{f'''
Java args: {config.java_args}''' if config.java_args else ""}{f'''
Server args: {config.server_args}''' if config.server_args else ""}\
"""
								)
				case a if len(a) < 1:
					print(f"config usage: \"config {{{' | '.join(config_commands)}}}\"")
				case _:
					print(f"command \"config {config_args[0]}\" is not found, possible: {', '.join(config_commands)}")
		case ("install", *install_args):
			print("install stub")
		case ("run", *args):
			if os.path.exists("instances"):
				program_config = load_config()
				name_length = 0
				found = None
				while not found:
					name_length += 1
					if len(args) < name_length:
						exit("You need to specify a valid instance name.")
					elif (name := " ".join(args[:name_length])) in program_config["instances"]:
						found = program_config["instances"][name]
						config = InstanceConfig.load(found)
						args = args[name_length:]
						config.run()
		case a if len(a) < 1:
			print(f"basic usage: \"config create\" ")
		case _:
			print(f"command \"{sys.argv[1]}\" is not found, possible: {['config']}")


def load_config():
	try:
		with open("instances/config.json", "r+") as instances_file:
			program_config = jsonpickle.loads(instances_file.read())
		return program_config
	except FileNotFoundError:
		return {"instances": {}}
	except	json.JSONDecodeError:
		return {"instances": {}}


def save_config(program_config):
	with open("instances/config.json", "w+") as config_file:
		config_file.write(jsonpickle.dumps(program_config, indent="\t"))


if __name__ == '__main__':
	main()
