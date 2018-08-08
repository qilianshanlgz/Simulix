"""
Simulix generates an FMU from a simulink model source code.
 
Copyright (C) 2018 Scania CV AB and Simulix contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
from os import listdir, getcwd, path, makedirs, walk, rename
import sys
import argparse
from shutil import copy2, copytree, copyfile
import zipfile
import re

TEMPLATE_REPLACE = {
}

PATTERN = re.compile(r"^(R20)\d\d[a-b]")


def generate_template_file(src, dst, template_file_name, file_name):
    with open(path.join(dst, file_name), 'w') as generated_file:
        with open(path.join(src, template_file_name), 'r') as template_file:
            generated_file.write(template_file.read().format(**TEMPLATE_REPLACE))

def find_definitions(dst):
    for root, dirs, files in walk(dst):
        if "defines.txt" in files:
            return path.join(root, "defines.txt")
    return None

def add_definitions(dst):
    path_to_define = find_definitions(dst)
    if path_to_define:
        with open(path.join(dst, "CMakeLists.txt"), 'r+') as cmake_file:
            content = cmake_file.read()
            cmake_file.seek(0,0)
            cmake_file.write('add_definitions(-DSIMULIX ')
            with open(path_to_define, 'r+') as defines_file:
                defines_file.write("SIMULIX")
                for line in defines_file:
                    cmake_file.write("-D{0} ".format(line.rstrip('\r\n')))
            cmake_file.write(')\n' + content)
    


def generate_template_files(src, dst):
    generate_template_file(src, dst, "templates/capi_utils_template.c", "includes/capi_utils.c")
    generate_template_file(src, dst, "templates/exemain_template.c", "exemain.c")
    generate_template_file(src, dst, "templates/CMakeLists_template.txt", "CMakeLists.txt")


def handle_extension(extension_path, src, dst):
    if path.isfile(path.join(extension_path, "extension.py")):
        sys.path.append(extension_path)
        import extension
        try:
            TEMPLATE_REPLACE.update(extension.get_template_info(TEMPLATE_REPLACE))
        except AttributeError:
            pass
        if path.isdir(path.join(extension_path, "templates")):
            if path.isfile(path.join(extension_path, "templates/exemain_template.c")):
                generate_template_file(extension_path, dst, "templates/exemain_template.c", "exemain.c")
            else:
                generate_template_file(src, dst,"templates/exemain_template.c", "exemain.c")

            if path.isfile(path.join(extension_path, "templates/CMakeLists_template.txt")):
                generate_template_file(extension_path, dst, "templates/CMakeLists_template.txt", "CMakeLists.txt")
            else:
                generate_template_file(src, dst, "templates/CMakeLists_template.txt", "CMakeLists.txt")

            if path.isfile(path.join(extension_path, "templates/capi_utils_template.c")):
                generate_template_file(extension_path, dst, "templates/capi_utils_template.c", "includes/capi_utils.c")
            else:
                generate_template_file(src, dst, "templates/capi_utils_template.c", "includes/capi_utils.c")
        else:
            generate_template_files(src, dst)   
        return True
    else:
        return False
    return False


def copy_directory(src, dst):
    if not path.exists(dst):
        makedirs(dst)
    for item in listdir(src):
        s = path.join(src, item)
        d = path.join(dst, item)
        if path.isdir(s):
            copytree(s, d, False, None)
        else:
            copy2(s, d)

def copy_directories(src, dst):
    copy_directory(path.join(src, 'includes'), path.join(dst, 'includes'))
    copy_directory(path.join(src, 'libraryincludes'), path.join(dst, 'libraryincludes'))

def handle_zip(dst, zip_path):
    zip_ref = zipfile.ZipFile(zip_path, 'r')
    zip_ref.extractall(dst)
    root_dirs = []
    for f in zip_ref.namelist():
        r_dir = f.split('/')[0]
        if r_dir not in root_dirs:
            root_dirs.append(r_dir)
    zip_ref.close()
    for line in root_dirs:
        if PATTERN.match(line):
            TEMPLATE_REPLACE['matlabVersion'] = line
        elif line != "otherFiles":
            TEMPLATE_REPLACE['folderName'] = line
            # The model name in a generated grt code is inside a folder called <model_name>_grt_rtw
            # Inside this zip there's only 2-3 folders. One of them is neither matching the pattern regex nor called "otherFiles"
            # This folder contains the mentioned folder above. When we find a directory following the rules above we do the following:
            # Look for directories in the above mentioned folder:
            # listdir(path.join(dst, line))[0]
            # This will produce a list with only one element which we will access. 
            # Next, we split it with '_' in order to get rid of _grt_rtw
            # And we join together all elements except the last two so we support model names with underscores.
            # '_'.join(<code-in-here>.split('_')[:-2])
            TEMPLATE_REPLACE['modelName'] = '_'.join(listdir(path.join(dst, line))[0].split('_')[:-2])
            if len(TEMPLATE_REPLACE['modelName']) > 28:
                TEMPLATE_REPLACE['modelNameS'] = TEMPLATE_REPLACE['modelName'][:28]
            else:
                TEMPLATE_REPLACE['modelNameS'] = TEMPLATE_REPLACE['modelName']

def handle_fmu(dst, fmu_path):
    file_name, file_ext = path.splitext(fmu_path)
    zip_path = file_name + ".zip"
    print(zip_path)
    model_name = file_name.split('\\')[-1]
    TEMPLATE_REPLACE['modelName'] = model_name
    copyfile(fmu_path, zip_path)
    #rename(fmu_path, path.join("\\".join(fmu_path.split('\\')[:-1]), "old_" + fmu_path.split('\\')[-1]))
    zip_ref = zipfile.ZipFile(zip_path, 'r')
    zip_ref.extractall(path.join(dst, model_name))
    
    
def generate_files_fmu(src, dst, fmu_path, fmu_name):
    TEMPLATE_REPLACE['path'] = path.dirname(path.realpath(__file__)).replace('\\', '/')
    if fmu_name.split('.')[-1] == "fmu":
        fmu_path = path.join(fmu_path, fmu_name)
    else:
        fmu_path = path.join(fmu_path, fmu_name + ".fmu")
    if not path.isfile(fmu_path):
        exit("Couldn't find the specified FMU file")
    handle_fmu(dst, fmu_path)
    generate_template_file(src, dst, 'templates/CMakeLists.txt', 'CMakeLists.txt')

def generate_files(src, dst, zip_path, zip_name, extension_path):
    """
    Extracts content from zip in zip_path
    Generates and copies neccesary files
    

    Parameters:
        src:
            Source of template files, should be 
            {path_to_cgen.py}/includes unless specified otherwise.

        dst:
            Destination of generated file(s).

        zip_path:
            Path to generated Zip.
    """

    TEMPLATE_REPLACE['path'] = path.dirname(path.realpath(__file__)).replace('\\', '/')

    if zip_name.split('.')[-1] == "zip":
        zip_path = path.join(zip_path, zip_name)
    else:
        zip_path = path.join(zip_path, zip_name + ".zip")
    if not path.isfile(zip_path):
        exit("Couldn't find the specified ZIP file")
    handle_zip(dst, zip_path)
    copy_directories(src, dst)
    # Extensions will overwrite whatever handle_zip has put in the TEMPLATE_REPLACE
    # This can be useful and harmful so use extensions carefully
    extension = False
    if extension_path:
        extension = handle_extension(extension_path, src, dst) 
    if not extension or not extension_path:
        generate_template_files(src, dst)
    add_definitions(dst)


def main():
    generate_files(args.t, args.p, args.zp, args.ZN, args.e)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generating necessary files for an FMU",prog="unpack",usage="%(prog)s [options]")
    parser.add_argument('-p', default=getcwd(), help='Path for generated files')
    parser.add_argument('-t', help='Path to templates and includes folders', default=path.abspath(path.dirname(sys.argv[0])))
    parser.add_argument('ZN', nargs='?', help='Name of zipfile generated from matlab', default='default')
    parser.add_argument('-zp', help='Path to zipfile, if not executing folder', default=getcwd())
    parser.add_argument('-e', help='Path to extension')
    args = parser.parse_args()
    main()
