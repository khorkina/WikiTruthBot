"""
Patch for telepot library to work with Python 3.11+
"""

import sys
import collections.abc
import importlib.util
import inspect
import os

# In Python 3.11+, collections.Hashable is moved to collections.abc.Hashable
if not hasattr(collections, 'Hashable'):
    # Monkey patch collections module
    collections.Hashable = collections.abc.Hashable

# Check if we can find the telepot module
spec = importlib.util.find_spec('telepot')
if spec:
    # Find the file path
    telepot_path = spec.origin
    if telepot_path:
        print(f"Found telepot module at: {telepot_path}")
        
        # Path to the directory containing the aio/__init__.py file 
        telepot_dir = os.path.dirname(telepot_path)
        aio_init_path = os.path.join(telepot_dir, 'aio', '__init__.py')
        
        if os.path.exists(aio_init_path):
            print(f"Found telepot.aio.__init__ at: {aio_init_path}")
            
            # Read the file
            with open(aio_init_path, 'r') as f:
                content = f.read()
            
            # Check if we need to patch
            if 'collections.Hashable' in content and 'collections.abc.Hashable' not in content:
                # Create backup
                backup_path = aio_init_path + '.bak'
                with open(backup_path, 'w') as f:
                    f.write(content)
                print(f"Created backup at: {backup_path}")
                
                # Patch the file
                patched_content = content.replace('collections.Hashable', 'collections.abc.Hashable')
                
                with open(aio_init_path, 'w') as f:
                    f.write(patched_content)
                    
                print("Successfully patched telepot.aio.__init__.py")
            else:
                print("File does not need patching or already patched")
        else:
            print(f"Could not find telepot.aio.__init__ at: {aio_init_path}")
    else:
        print("Could not determine telepot module path")
else:
    print("Could not find telepot module")