import glob
import re

for filepath in glob.glob('/home/roni/Desktop/PatNabor/api/*/admin.py'):
    with open(filepath, 'r') as f:
        content = f.read()

    # We need to find `list_display = (...)` or `list_display = [...]`
    # and insert `"id", ` right after the opening bracket if it's not already there.
    
    def replacer(match):
        prefix = match.group(1) # `list_display = `
        opening = match.group(2) # `(` or `[`
        rest = match.group(3)
        
        # Check if id is already present at the start or inside
        if '"id"' in rest or "'id'" in rest:
            return match.group(0)
            
        # Add id as the first element
        return f'{prefix}{opening}\n        "id",\n{rest}'

    # The regex looks for `list_display = ` followed by `(` or `[` and captures the rest recursively?
    # No, we can just look for the first newline or bracket
    # Since they are mostly multiline tuples like:
    # list_display = (
    #     "..."
    # )
    # OR list_display = ["...", "..." ]
    
    content = re.sub(r'(list_display\s*=\s*)([\(\[])(?!\s*[\"\']id[\"\'])(.*?[\)\]])', replacer, content, flags=re.DOTALL)
    
    with open(filepath, 'w') as f:
        f.write(content)

print("Injected 'id' into list_display across admin models.")
