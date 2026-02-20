import os
import shutil
import re

def extract_example_from_rst(rst_file, output_root, title):
    os.makedirs(output_root, exist_ok=True)
    parsing = False
    stack = [(output_root, -1)]  # Stack to keep track of folders and levels
    rst_dir = os.path.dirname(os.path.abspath(rst_file))

    with open(rst_file, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            # Start parsing after the title
            if not parsing:
                if stripped.startswith(title):
                    parsing = True
                continue

            # Stop parsing when a line with dashes is encountered
            if parsing and stripped.startswith("---"):
                break

            # Detect folder
            folder_match = re.match(r"\.\. dropdown:: 📁 ``(.+)/``", stripped)
            if folder_match:
                folder_name = folder_match.group(1)
                # Pop from the stack if we go up a level
                while indent <= stack[-1][1]:
                    stack.pop()
                folder_path = os.path.join(stack[-1][0], folder_name)
                os.makedirs(folder_path, exist_ok=True)
                stack.append((folder_path, indent))
                continue

            # Detect file
            file_match = re.match(r"\.\. dropdown:: 📄 ``(.+)``", stripped)
            if file_match:
                file_name = file_match.group(1)
                while indent <= stack[-1][1]:
                    stack.pop()
                file_path = os.path.join(stack[-1][0], file_name)
                stack.append((file_path, indent))  # Temporary file for literalinclude
                continue

            # Detect literalinclude
            literal_match = re.match(r"\.\. literalinclude:: (.+)", stripped)
            if literal_match:
                source_rel_path = literal_match.group(1).strip()
                source_path = os.path.normpath(os.path.join(rst_dir, source_rel_path))
                file_path = stack[-1][0]

                # Copy the actual file if it exists
                if os.path.exists(source_path):
                    shutil.copy(source_path, file_path)
                
                stack.pop()  # Remove the file from the stack after processing
                continue

def update_yaml_content(yaml_file,old_text,new_text):
    with open(yaml_file, 'r+') as file:
            content = file.read()  
            content = content.replace(old_text,new_text)
            file.seek(0)
            file.write(content)  
            file.truncate()

def append_yaml_content(yaml_file,new_text):
    with open(yaml_file, 'a') as file:
        file.write(new_text)