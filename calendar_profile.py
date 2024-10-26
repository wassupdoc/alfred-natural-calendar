#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import subprocess
import os
import re
import logging

logging.basicConfig(filename='calendar_profile.log', level=logging.DEBUG)

class CalendarProfileManager:
    def __init__(self):
        self.calendars = self.get_available_calendars()
        self.config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calendar_config.json')
        self.config = {}  # Inisialisasi config sebagai dictionary kosong
        self.load_config()  # Panggil load_config untuk mengisi self.config
        logging.debug(f"Calendars: {self.calendars}")
        logging.debug(f"Config: {self.config}")

    def get_available_calendars(self):
        """Get list of available calendars"""
        logging.debug("Mengambil daftar kalender yang tersedia")
        script = '''
        tell application "Calendar"
            return name of calendars
        end tell
        '''
        try:
            result = subprocess.run(['osascript', '-e', script],
                                  capture_output=True,
                                  text=True,
                                  check=True)
            calendars = [cal.strip() for cal in result.stdout.strip().split(',')]
            return self.sort_calendars(calendars)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error saat menjalankan AppleScript: {e}")
            print(f"Error saat menjalankan AppleScript: {e}", file=sys.stderr)
            return ["Calendar"]
        except Exception as e:
            logging.error(f"Error tidak terduga: {e}")
            print(f"Error tidak terduga: {e}", file=sys.stderr)
            return ["Calendar"]

    def sort_calendars(self, calendars):
        """Sort calendars with numbers and alphabetically"""
        def sort_key(name):
            parts = re.split(r'(\d+)', name)  # Tambahkan 'r' sebelum string untuk raw string
            parts = [int(part) if part.isdigit() else part.lower() for part in parts]
            return parts
        
        return sorted(calendars, key=sort_key)

    def load_config(self):
        """Muat konfigurasi dari file"""
        logging.debug("Memuat konfigurasi")
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                    if self.config.get('default_calendar') not in self.calendars:
                        self.config['default_calendar'] = self.calendars[0] if self.calendars else 'Calendar'
                logging.debug(f"Konfigurasi dimuat: {self.config}")
            except json.JSONDecodeError:
                logging.error("File konfigurasi rusak. Membuat konfigurasi baru.")
                print("Error: File konfigurasi rusak. Membuat konfigurasi baru.")
                self.create_default_config()
            except Exception as e:
                logging.error(f"Gagal memuat konfigurasi: {str(e)}")
                print(f"Error: Gagal memuat konfigurasi: {str(e)}")
                self.create_default_config()
        else:
            logging.debug("File konfigurasi tidak ditemukan. Membuat konfigurasi baru.")
            self.create_default_config()

    def create_default_config(self):
        """Buat konfigurasi default"""
        self.config = {"default_calendar": self.calendars[0] if self.calendars else 'Calendar'}
        self.save_config(self.config['default_calendar'])

    def save_config(self, calendar_name):
        """Simpan konfigurasi ke file"""
        if calendar_name in self.calendars:
            self.config["default_calendar"] = calendar_name
            try:
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                return True
            except Exception as e:
                print(f"Error: Gagal menyimpan konfigurasi: {str(e)}")
        return False

    def generate_items(self, query=None):
        """Generate Alfred items"""
        items = []
        query_lower = query.lower() if query else ""
        default_cal = self.config.get('default_calendar', '')  # Gunakan .get() dengan nilai default
        
        # Filter calendars
        matching_calendars = [
            cal for cal in self.calendars 
            if not query_lower or query_lower in cal.lower()
        ]
        
        # Move default to top
        if default_cal in matching_calendars:
            matching_calendars.remove(default_cal)
            items.append({
                "title": f"✓ {default_cal}",
                "subtitle": "Current default calendar",
                "valid": False,
                "icon": {
                    "path": "icon.png"
                }
            })
        
        # Add other calendars
        for cal in matching_calendars:
            items.append({
                "title": cal,
                "subtitle": "Press Enter to set as default calendar",
                "arg": f"--set:{cal}",
                "valid": True,
                "icon": {
                    "path": "icon.png"
                }
            })
        
        return items

def main():
    logging.debug("Memulai program")
    manager = CalendarProfileManager()
    
    if len(sys.argv) > 1:
        arg = " ".join(sys.argv[1:])
        logging.debug(f"Argumen yang diterima: {arg}")
        if arg.startswith("--set:"):
            # Hapus semua kemunculan "--set:" dari argumen
            calendar_name = arg.replace("--set:", "").strip()
            logging.debug(f"Mencoba mengatur kalender: {calendar_name}")
            if calendar_name in manager.calendars:
                if manager.save_config(calendar_name):
                    output = json.dumps({"alfredworkflow": {"arg": f"Kalender default diatur ke: {calendar_name}", "variables": {"calendar": calendar_name}}})
                    logging.debug(f"Output: {output}")
                    print(output)
                else:
                    output = json.dumps({"alfredworkflow": {"arg": f"Error: Gagal mengatur kalender '{calendar_name}'", "variables": {"error": "true"}}})
                    logging.error(f"Gagal mengatur kalender: {calendar_name}")
                    print(output)
            else:
                output = json.dumps({"alfredworkflow": {"arg": f"Error: Kalender '{calendar_name}' tidak ditemukan", "variables": {"error": "true"}}})
                logging.error(f"Kalender tidak ditemukan: {calendar_name}")
                print(output)
        else:
            # Tampilkan daftar yang difilter
            items = manager.generate_items(arg)
            output = json.dumps({"items": items})
            logging.debug(f"Output: {output}")
            print(output)
    else:
        # Tampilkan semua kalender
        items = manager.generate_items()
        output = json.dumps({"items": items})
        logging.debug(f"Output: {output}")
        print(output)

if __name__ == "__main__":
    main()