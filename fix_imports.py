import glob

for filepath in glob.glob('/home/roni/Desktop/PatNabor/api/*/admin.py'):
    with open(filepath, 'r') as f:
        content = f.read()

    broken_import = "from unfold.admin import ModelAdmin as UnfoldModelAdmin\nfrom api.core.admin_mixins import UUIDSearchMixin\n, TabularInline"
    fixed_import = "from unfold.admin import ModelAdmin as UnfoldModelAdmin, TabularInline\nfrom api.core.admin_mixins import UUIDSearchMixin\n"
    
    if broken_import in content:
        content = content.replace(broken_import, fixed_import)
    
    # Also handle some edge cases
    broken_import_2 = "from unfold.admin import ModelAdmin as UnfoldModelAdmin\nfrom api.core.admin_mixins import UUIDSearchMixin\n, StackedInline"
    fixed_import_2 = "from unfold.admin import ModelAdmin as UnfoldModelAdmin, StackedInline\nfrom api.core.admin_mixins import UUIDSearchMixin\n"
    if broken_import_2 in content:
        content = content.replace(broken_import_2, fixed_import_2)

    with open(filepath, 'w') as f:
        f.write(content)

print('Fixed syntax errors')
