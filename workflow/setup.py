#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
setup.py - Setup script for Calendar NLP Workflow
This script:
1. Creates necessary directories
2. Installs required dependencies in the lib directory
3. Sets up proper file permissions
4. Creates required configuration files
5. Verifies installations
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path

class WorkflowSetup:
    def __init__(self):
        self.workflow_dir = os.path.dirname(os.path.realpath(__file__))
        self.lib_dir = os.path.join(self.workflow_dir, 'lib')
        self.data_dir = os.path.expanduser('~/Library/Application Support/Alfred/Workflow Data/com.ariestwn.calendar.nlp')
        self.required_packages = [
            'python-dateutil'
        ]

    def create_directories(self):
        """Create necessary directories if they don't exist"""
        print("Creating directories...")
        
        directories = [
            self.lib_dir,
            self.data_dir
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")
            else:
                print(f"Directory already exists: {directory}")

    def clear_lib_directory(self):
        """Clear existing lib directory to ensure clean installation"""
        if os.path.exists(self.lib_dir):
            print(f"Clearing existing lib directory: {self.lib_dir}")
            shutil.rmtree(self.lib_dir)
            os.makedirs(self.lib_dir)
            print("Created fresh lib directory")

    def verify_installation(self):
        """Verify that packages are correctly installed"""
        print("\nVerifying installations...")
        sys.path.insert(0, self.lib_dir)
        
        for package in self.required_packages:
            try:
                if package == 'python-dateutil':
                    from dateutil import parser
                    print(f"✓ {package} successfully installed and importable")
            except ImportError as e:
                print(f"✗ Failed to import {package}: {str(e)}")
                return False
        return True

    def install_dependencies(self):
        """Install required Python packages to lib directory"""
        print("\nInstalling dependencies...")
        
        # Create __init__.py in lib directory
        init_file = os.path.join(self.lib_dir, '__init__.py')
        if not os.path.exists(init_file):
            Path(init_file).touch()
            print("Created lib/__init__.py")

        # Install required packages
        for package in self.required_packages:
            print(f"\nInstalling {package}...")
            try:
                subprocess.run([
                    sys.executable,
                    '-m', 'pip',
                    'install',
                    '--target', self.lib_dir,
                    '--upgrade',
                    '--no-cache-dir',
                    package
                ], check=True)
                
                if not self.verify_installation():
                    raise Exception(f"Failed to verify {package} installation")
                
                print(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                print(f"Error installing {package}: {e}")
                sys.exit(1)

    def create_config(self):
        """Create initial configuration file"""
        print("\nSetting up configuration...")
        
        config_file = os.path.join(self.data_dir, 'calendar_config.json')
        default_config = {
            "default_calendar": "Calendar"
        }
        
        if not os.path.exists(config_file):
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            print("Created default configuration file")
        else:
            print("Configuration file already exists")

    def set_permissions(self):
        """Set proper file permissions"""
        print("\nSetting file permissions...")
        
        # Make Python files executable
        executable_files = [
            'calendar_nlp.py',
            'preview.py',
            'calendar_profile.py'
        ]
        
        for file in executable_files:
            file_path = os.path.join(self.workflow_dir, file)
            if os.path.exists(file_path):
                os.chmod(file_path, 0o755)
                print(f"Set executable permissions for {file}")
            else:
                print(f"Warning: {file} not found")

    def cleanup(self):
        """Clean up temporary files and directories"""
        print("\nCleaning up...")
        
        # Remove Python cache directories
        for root, dirs, files in os.walk(self.workflow_dir):
            for dir in dirs:
                if dir == '__pycache__':
                    cache_dir = os.path.join(root, dir)
                    shutil.rmtree(cache_dir)
                    print(f"Removed cache directory: {cache_dir}")

    def setup(self):
        """Run complete setup process"""
        print("Starting Calendar NLP Workflow setup...")
        
        try:
            self.create_directories()
            self.clear_lib_directory()  # Start fresh
            self.install_dependencies()
            self.create_config()
            self.set_permissions()
            self.cleanup()
            
            print("\n✅ Setup completed successfully!")
            print("\nNotes:")
            print("1. The workflow is now ready to use")
            print("2. Use 'cl' to add calendar events")
            print("3. Use 'clprofile' to set your default calendar")
            
        except Exception as e:
            print(f"\n❌ Error during setup: {str(e)}")
            sys.exit(1)

def main():
    setup = WorkflowSetup()
    setup.setup()

if __name__ == '__main__':
    main()