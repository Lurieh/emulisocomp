import os
import subprocess
import shutil
import datetime
from pathlib import Path
import tomllib  # Lecture (Standard lib 3.11+)
import tomlkit  # Écriture (Préservation du style)

class CHDManager:
    def __init__(self, rom_path):
        self.rom_path = Path(rom_path).resolve()
        self.base_script_path = Path(__file__).parent
        self.config_file = self.base_script_path / "config.toml"
        self.log_dir = self.base_script_path / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        self.config = self.load_config()
        # Extensions qui servent de point d'entrée pour chdman
        self.master_exts = [".cue", ".gdi", ".cdi", ".iso", ".mds", ".ccd"]

    def load_config(self):
        default_data = {
            "categories": {
                "game": [".iso", ".cue", ".bin", ".cdi", ".gdi", ".mdf", ".mds", ".ccd", ".img", ".sub", ".cdi"],
                "save": [".state", ".state.auto", ".srm", ".bcr", ".bkr", ".smpc", ".vmu", ".state.auto"],
                "ignore": [".url", ".txt", ".pdf", ".jpg", ".png", ".xml", ".db"]
            }
        }
        if self.config_file.exists():
            return tomlkit.parse(self.config_file.read_text())
        return tomlkit.item(default_data)

    def save_config(self):
        self.config_file.write_text(tomlkit.dumps(self.config))

    def classify(self, file_path):
        ext = "".join(file_path.suffixes).lower() # Gère .state.auto
        if not ext: ext = file_path.suffix.lower()

        for cat in ["game", "save", "ignore"]:
            if ext in self.config["categories"][cat]:
                return cat
        return "unknown"

    def audit_folder(self, folder):
        items = list(folder.iterdir())
        report = {"game": [], "save": [], "ignore": [], "unknown": []}
        
        for item in items:
            if item.is_dir():
                report["ignore"].append(item)
                continue
            
            cat = self.classify(item)
            if cat == "unknown":
                print(f"\n[?] Fichier non classé : {item.name}")
                choice = input("Action : (g)ame, (s)ave, (i)gnore ? ").lower()
                mapping = {"g": "game", "s": "save", "i": "ignore"}
                cat = mapping.get(choice, "ignore")
                self.config["categories"][cat].append("".join(item.suffixes).lower())
                self.save_config()
            
            report[cat].append(item)
        return report

    def run(self):
        folders = sorted([f for f in self.rom_path.iterdir() if f.is_dir()])
        
        print(f"\n--- Atelier de conversion CHD | {self.rom_path} ---")
        for i, f in enumerate(folders):
            print(f"[{i}] {f.name}")
        
        selection = input("\nNuméros à traiter (ex: 1,3-5) ou 'all' : ")
        to_process = self.parse_selection(selection, folders)

        for folder in to_process:
            report = self.audit_folder(folder)
            self.print_folder_summary(folder, report)
            
            confirm = input(f"\nValider conversion pour '{folder.name}' ? [y/N] ").lower()
            if confirm == 'y':
                self.convert(folder, report)

    def parse_selection(self, selection, folders):
        if selection.lower() == 'all': return folders
        indices = []
        for part in selection.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                indices.extend(range(start, end + 1))
            else:
                indices.append(int(part))
        return [folders[i] for i in indices if i < len(folders)]

    def print_folder_summary(self, folder, report):
        print(f"\n--- Plan d'action : {folder.name} ---")
        print(f"  📦 CHD Source  : {[f.name for f in report['game']]}")
        print(f"  💾 Persistant  : {[f.name for f in report['save']]}")
        print(f"  📁 Ignoré      : {[f.name for f in report['ignore']]}")

    def convert(self, folder, report):
        # Trouver le fichier maître
        masters = [f for f in report['game'] if f.suffix.lower() in self.master_exts]
        if not masters:
            print("Erreur : Aucun point d'entrée (CUE, ISO, CDI...) trouvé.")
            return

        master = masters[0]
        output = master.with_suffix(".chd")
        log_file = self.log_dir / f"log_{datetime.date.today()}.txt"

        print(f"Executing: chdman createcd -i {master.name}")
        
        res = subprocess.run(["chdman", "createcd", "-i", str(master), "-o", str(output)], 
                             capture_output=True, text=True)

        with open(log_file, "a") as l:
            l.write(f"\n--- {datetime.datetime.now()} | {folder.name} ---\n{res.stdout}\n")

        if res.returncode == 0:
            print("✓ Succès. Nettoyage des sources...")
            for f in report['game']:
                f.unlink()
        else:
            print(f"X Échec. Consultez {log_file.name}")

if __name__ == "__main__":
    path = input("Dossier des jeux [.] : ") or "."
    CHDManager(path).run()
