import glob
import re

for filepath in glob.glob('/home/roni/Desktop/PatNabor/api/*/admin.py'):
    with open(filepath, 'r') as f:
        content = f.read()

    # We want to replace "id" or 'id' with "=id" ONLY within the search_fields definition.
    # We can do this safely by first extracting the search_fields = (...) or [...]
    # and then replacing within it.

    def replace_id_in_search_fields(match):
        inner_content = match.group(1)
        # replace "id" or 'id' with "=id"
        inner_content = re.sub(r'([\"|\'])id([\"|\'])', r'\1=id\2', inner_content)
        return 'search_fields = ' + inner_content

    new_content = re.sub(r'search_fields\s*=\s*(\(.*?\)|\[.*?\])', replace_id_in_search_fields, content, flags=re.DOTALL)
    
    with open(filepath, 'w') as f:
        f.write(new_content)

print("Safely replaced id with =id in search_fields.")
