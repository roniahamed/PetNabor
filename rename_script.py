import os
import re

extensions_to_include = {'.py', '.md', '.json', '.sql', '.yml'}
# Files to explicitly exclude (like migrations)
exclude_patterns = ['/migrations/', '__pycache__', '.venv', 'venv', '.git']
exclude_files = {'rename_script.py'}

def replace_in_string(content):
    # PATNABOR -> PETNABOR
    content = re.sub(r'PATNABOR', 'PETNABOR', content)
    # Patnabor -> Petnabor
    content = re.sub(r'Patnabor', 'Petnabor', content)
    # patnabor -> petnabor
    content = re.sub(r'patnabor', 'petnabor', content)
    
    # PATPAL -> PETPAL
    content = re.sub(r'PATPAL', 'PETPAL', content)
    # Patpal -> Petpal
    content = re.sub(r'Patpal', 'Petpal', content)
    # patpal -> petpal
    content = re.sub(r'patpal', 'petpal', content)
    
    # Typos
    content = re.sub(r'PATBAL', 'PETPAL', content)
    content = re.sub(r'Patbal', 'Petpal', content)
    content = re.sub(r'patbal', 'petpal', content)
    
    # Handle PatNabor and PatPal
    content = re.sub(r'PatNabor', 'PetNabor', content)
    content = re.sub(r'PatPal', 'PetPal', content)
    
    return content

for root, dirs, files in os.walk('.'):
    # Skip hidden directories and migrations
    skip_dir = False
    for excl in exclude_patterns:
        if excl in root or root.endswith(excl.replace('/', '')):
            skip_dir = True
            break
    if skip_dir:
        continue
    
    for file in files:
        if file in exclude_files:
            continue
        ext = os.path.splitext(file)[1]
        if ext in extensions_to_include:
            filepath = os.path.join(root, file)
            # Skip migrations if it's uniquely matched
            if '/migrations/' in filepath:
                continue
                
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = replace_in_string(content)
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
