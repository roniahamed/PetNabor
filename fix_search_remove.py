import glob
import re

for filepath in glob.glob('/home/roni/Desktop/PatNabor/api/*/admin.py'):
    with open(filepath, 'r') as f:
        content = f.read()

    def replace_id_in_search_fields(match):
        inner_content = match.group(1)
        # Remove "=id" or "id" completely along with trailing comma/space
        inner_content = re.sub(r'([\"|\'])=?id([\"|\']),\s*', '', inner_content)
        # If it was the last or only element
        inner_content = re.sub(r',\s*([\"|\'])=?id([\"|\'])', '', inner_content)
        inner_content = re.sub(r'([\"|\'])=?id([\"|\'])', '', inner_content)
        return 'search_fields = ' + inner_content

    new_content = re.sub(r'search_fields\s*=\s*(\(.*?\)|\[.*?\])', replace_id_in_search_fields, content, flags=re.DOTALL)
    
    with open(filepath, 'w') as f:
        f.write(new_content)

print("Safely removed id from search_fields.")
