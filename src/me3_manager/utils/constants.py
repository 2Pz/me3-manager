# Shared constants used across the application

# Folders considered valid contents for a package mod
ACCEPTABLE_FOLDERS = [
    "_backup",
    "_unknown",
    "action",
    "asset",
    "chr",
    "cutscene",
    "event",
    "font",
    "map",
    "material",
    "menu",
    "movie",
    "msg",
    "other",
    "param",
    "parts",
    "script",
    "sd",
    "sfx",
    "shader",
    "sound",
]

# DLLs belonging to mod loaders (ModEngine 2, ME3) — skip during mod scanning
IGNORED_DLLS: set[str] = {
    "dinput8.dll",
    "modengine2.dll",
    "mod_loader.dll",
    "lua.dll",
    "zlib1.dll",
    "hooklibraryx64.dll",
    "minhook.x64.dll",
    "me3_mod_host.dll",
    "libzstd.dll"
}
