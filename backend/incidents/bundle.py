import io
from pathlib import PurePosixPath
import re
import stat
import zipfile

MAX_PROJECT_BYTES = 256 * 1024
MAX_FILE_BYTES = 32 * 1024
EXTENSIONS = {'.py', '.json', '.md', '.txt', '.toml', '.html', '.css', '.js', '.sql'}


def safe_path(name):
    if not isinstance(name, str) or len(name) > 150 or '\\' in name:
        raise ValueError('Use relative project paths with forward slashes.')
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in {'.', '..'} or p.startswith('.') for p in path.parts) or str(path) != name:
        raise ValueError('Project paths must stay inside the uploaded folder; omit hidden files and credentials.')
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', name) or any(p in {'node_modules', '__pycache__', 'venv'} for p in path.parts):
        raise ValueError('Remove dependencies and generated folders from the project upload.')
    return name


def validate_files(files):
    if not isinstance(files, dict) or not 1 <= len(files) <= 30:
        raise ValueError('Upload between 1 and 30 text project files.')
    total = 0
    for name, text in files.items():
        safe_path(name)
        if PurePosixPath(name).suffix.lower() not in EXTENSIONS or not isinstance(text, str) or '\x00' in text:
            raise ValueError('Only source and text files are supported; omit credentials, binaries and database files.')
        size = len(text.encode('utf-8'))
        if size > MAX_FILE_BYTES:
            raise ValueError('Each project file must be at most 32 KiB.')
        total += size
    if total > MAX_PROJECT_BYTES or not any(name.endswith('.py') for name in files):
        raise ValueError('Use a Python project up to 256 KiB of extracted text.')
    return files


def read_project(data, filename):
    if not data or len(data) > 1024 * 1024:
        raise ValueError('Upload a non-empty Python file or ZIP up to 1 MiB.')
    try:
        if filename.lower().endswith('.py'):
            return validate_files({safe_path(filename): data.decode('utf-8-sig')})
        if not filename.lower().endswith('.zip'):
            raise ValueError('Choose a .py app or a ZIP of a Python HTTP project.')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [info for info in archive.infolist() if not info.is_dir()]
            if not 1 <= len(entries) <= 30 or sum(info.file_size for info in entries) > MAX_PROJECT_BYTES:
                raise ValueError('ZIP must contain at most 30 files and 256 KiB of extracted text.')
            files = {}
            for info in entries:
                name = safe_path(info.filename)
                if name in files or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1 or info.file_size > MAX_FILE_BYTES:
                    raise ValueError('Omit duplicate paths, links, encrypted files and files over 32 KiB.')
                files[name] = archive.read(info).decode('utf-8-sig')
            return validate_files(files)
    except (zipfile.BadZipFile, UnicodeDecodeError, RuntimeError) as error:
        raise ValueError('Use a valid ZIP containing UTF-8 text, without encrypted or binary files.') from error
