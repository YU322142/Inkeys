"""Embed a locally compiled candidate DLL into a COPY of an official Inkeys EXE.
Never edits the input executable. Does not bypass Inkeys' resource verification.
The resulting executable is unsigned and must be labelled as a local test build.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
from pathlib import Path
import shutil
import struct
import sys

kernel = C.WinDLL('kernel32', use_last_error=True)
kernel.LoadLibraryExW.argtypes = [W.LPCWSTR, W.HANDLE, W.DWORD]
kernel.LoadLibraryExW.restype = W.HMODULE
kernel.FindResourceW.argtypes = [W.HMODULE, C.c_void_p, W.LPCWSTR]
kernel.FindResourceW.restype = W.HRSRC
kernel.SizeofResource.argtypes = [W.HMODULE, W.HRSRC]
kernel.SizeofResource.restype = W.DWORD
kernel.LoadResource.argtypes = [W.HMODULE, W.HRSRC]
kernel.LoadResource.restype = W.HGLOBAL
kernel.LockResource.argtypes = [W.HGLOBAL]
kernel.LockResource.restype = C.c_void_p
kernel.FreeLibrary.argtypes = [W.HMODULE]
kernel.BeginUpdateResourceW.argtypes = [W.LPCWSTR, W.BOOL]
kernel.BeginUpdateResourceW.restype = W.HANDLE
kernel.UpdateResourceW.argtypes = [W.HANDLE, W.LPCWSTR, C.c_void_p, W.WORD, C.c_void_p, W.DWORD]
kernel.UpdateResourceW.restype = W.BOOL
kernel.EndUpdateResourceW.argtypes = [W.HANDLE, W.BOOL]
kernel.EndUpdateResourceW.restype = W.BOOL
callback_type = C.WINFUNCTYPE(W.BOOL, W.HMODULE, W.LPCWSTR, C.c_void_p, W.WORD, C.c_ssize_t)
kernel.EnumResourceLanguagesW.argtypes = [W.HMODULE, W.LPCWSTR, C.c_void_p, callback_type, C.c_ssize_t]
kernel.EnumResourceLanguagesW.restype = W.BOOL

def sha(value): return hashlib.sha256(value).hexdigest()

def read_embedded(path):
    module = kernel.LoadLibraryExW(str(path), None, 2)
    if not module: raise C.WinError(C.get_last_error())
    try:
        resource = kernel.FindResourceW(module, 222, 'DLL')
        if not resource: raise C.WinError(C.get_last_error())
        size = kernel.SizeofResource(module, resource)
        address = kernel.LockResource(kernel.LoadResource(module, resource))
        if not address or not size: raise RuntimeError('Invalid embedded PPT DLL')
        languages = []
        @callback_type
        def collect(module, kind, name, lang, context):
            languages.append(lang)
            return True
        if not kernel.EnumResourceLanguagesW(module, 'DLL', 222, collect, 0):
            raise C.WinError(C.get_last_error())
        return C.string_at(address, size), languages
    finally:
        kernel.FreeLibrary(module)

def main():
    source, dll_path, output = [Path(p).resolve() for p in sys.argv[1:]]
    if output == source or output.exists(): raise RuntimeError('Output must be a new file, distinct from source')
    original = source.read_bytes()
    dll = dll_path.read_bytes()
    old_dll, languages = read_embedded(source)
    print('official_exe_sha256=' + sha(original))
    print('original_embedded_dll_sha256=' + sha(old_dll))
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    # Authenticode cannot remain valid after a resource edit. Explicitly remove
    # the certificate directory from the new copy rather than retaining a broken signature.
    data = bytearray(output.read_bytes())
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    optional = pe + 24
    magic = struct.unpack_from('<H', data, optional)[0]
    if magic not in (0x10b, 0x20b): raise RuntimeError('Unsupported PE optional header')
    security = optional + (112 if magic == 0x20b else 96) + 4 * 8
    cert_offset, cert_size = struct.unpack_from('<II', data, security)
    struct.pack_into('<II', data, security, 0, 0)
    if cert_offset and cert_size and cert_offset + cert_size == len(data):
        del data[cert_offset:]
    output.write_bytes(data)
    update = kernel.BeginUpdateResourceW(str(output), False)
    if not update: raise C.WinError(C.get_last_error())
    try:
        buffer = C.create_string_buffer(dll)
        for lang in languages:
            if not kernel.UpdateResourceW(update, 'DLL', 222, lang, buffer, len(dll)):
                raise C.WinError(C.get_last_error())
        if not kernel.EndUpdateResourceW(update, False):
            raise C.WinError(C.get_last_error())
        update = None
    finally:
        if update: kernel.EndUpdateResourceW(update, True)
    embedded, _ = read_embedded(output)
    if embedded != dll: raise RuntimeError('Embedded DLL differs from candidate')
    if source.read_bytes() != original: raise RuntimeError('Input changed unexpectedly')
    print('candidate_dll_sha256=' + sha(dll))
    print('candidate_exe_sha256=' + sha(output.read_bytes()))
    print('PASS: copied EXE embeds exactly the candidate DLL; original unchanged; output unsigned')

if __name__ == '__main__': main()
