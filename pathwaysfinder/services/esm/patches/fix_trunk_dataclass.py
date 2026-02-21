"""Patch ESM dataclasses to fix Python 3.11 mutable default errors.

Fixes all `field: Type = Type()` patterns in dataclasses to use
`field: Type = field(default_factory=Type)` instead.
"""
import re
import sys
import glob

site = sys.argv[1]
patterns = [
    (f"{site}/esm/esmfold/v1/trunk.py",
     "structure_module: StructureModuleConfig = StructureModuleConfig()",
     "structure_module: StructureModuleConfig = field(default_factory=StructureModuleConfig)"),
    (f"{site}/esm/esmfold/v1/esmfold.py",
     "trunk: T.Any = FoldingTrunkConfig()",
     "trunk: T.Any = field(default_factory=FoldingTrunkConfig)"),
]

for filepath, old, new in patterns:
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        # Ensure 'field' is imported from dataclasses
        if 'from dataclasses import' in content:
            dc_line = re.search(r'from dataclasses import (.+)', content)
            if dc_line and 'field' not in dc_line.group(1):
                content = content.replace(dc_line.group(0), dc_line.group(0) + ', field')

        content = content.replace(old, new)

        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Patched {filepath}")
    except Exception as e:
        print(f"Error patching {filepath}: {e}")
