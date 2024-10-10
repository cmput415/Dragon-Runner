import os
import sys
import subprocess
import argparse

def compile_shared_library(compiler, input_file, output_file, is_macos):
    flags = ["-fPIC"]
    if is_macos:
        # NOTE: These are the flags required to compile a dynamic library
        # on the macos-latest github action runner as of 10/10/2024
        flags.extend([
            "-dynamiclib",
            "-arch", "arm64e",
            "-install_name", "@rpath/" + os.path.basename(output_file),
            "-mmacosx-version-min=11.0"
        ])
        flags.extend(["-dynamiclib"])
    else:
        flags.extend(["-shared"])
    
    cmd = [compiler] + flags + [input_file, "-o", output_file]
  
    try:
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
        print(f"Successfully compiled: {os.path.basename(output_file)}")
    except subprocess.CalledProcessError as e:
        print(f"Error compiling {input_file}:")
        print(e.stderr.decode())

def main():
    parser = argparse.ArgumentParser(description="Compile C files into shared libraries.")
    parser.add_argument("input_dir", help="Directory containing .c files")
    parser.add_argument("output_dir", help="Directory to store compiled libraries")
    parser.add_argument("--compiler", default="/usr/bin/gcc", help="Path to the compiler (default: /usr/bin/gcc)")
    args = parser.parse_args()

    is_macos = sys.platform == "darwin"
    extension = ".dylib" if is_macos else ".so"

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    c_files = [f for f in os.listdir(args.input_dir) if f.endswith(".c")]
    
    if not c_files:
        print(f"No .c files found in {args.input_dir}")
        sys.exit(1)

    for c_file in c_files:
        base_name = os.path.splitext(c_file)[0]
        input_path = os.path.join(args.input_dir, c_file)
        output_path = os.path.join(args.output_dir, f"lib{base_name}{extension}")
        compile_shared_library(args.compiler, input_path, output_path, is_macos)

    print(f"Compilation complete. Shared libraries are in {args.output_dir}")

if __name__ == "__main__":
    main()