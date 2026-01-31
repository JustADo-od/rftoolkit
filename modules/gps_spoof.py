import os
import subprocess
from pathlib import Path
import time
import sys
import datetime
import shutil
import math
import threading
import glob

class GPSSpoof:
    def __init__(self):
        self.gps_sim_dir = Path.home() / ".rf_toolkit" / "gps_sdr_sim"
        self.motion_dir = self.gps_sim_dir / "motion_files"
        # check if dirs exist
        self.gps_sim_dir.mkdir(parents=True, exist_ok=True)
        self.motion_dir.mkdir(exist_ok=True)
        
    def run(self):
        while True:
            os.system('clear')
            print("========================================")
            print("             GPS SPOOFING")
            print("========================================")
            print("1. Setup/Update GPS-SDR-SIM")
            print("2. Ephemeris Manager (Check/Download)")
            print("3. Configure & Generate Signal")
            print("4. Transmit Signal")
            print("5. Back to Main Menu")
            
            choice = input("\nEnter choice (1-5): ").strip()
            
            if choice == '1':
                self.setup_gps_sdr_sim()
            elif choice == '2':
                self.ephemeris_menu()
            elif choice == '3':
                self.generate_signal_menu()
            elif choice == '4':
                self.transmit_menu()
            elif choice == '5':
                return
            else:
                print("Invalid choice!")
                input("Press Enter to continue...")

    def setup_gps_sdr_sim(self):
        print("\n--- Setup GPS-SDR-SIM ---")
        
        # dir state check
        if (self.gps_sim_dir / ".git").exists():
            print("Repository detected. Pulling updates...")
            try:
                subprocess.run(['git', 'pull'], cwd=self.gps_sim_dir, check=True)
            except Exception as e:
                print(f"[WARN] Git pull failed: {e}")
        elif any(self.gps_sim_dir.iterdir()):
            # if directory exists and is not empty, but not a git repo SOMEHOW
            print(f"[!] Directory {self.gps_sim_dir} exists and is not empty.")
            print("[!] It is NOT a git repository.")
            ans = input("Delete and re-clone? (y/n): ").lower()
            if ans == 'y':
                shutil.rmtree(self.gps_sim_dir)
                self.gps_sim_dir.mkdir()
                self._clone_repo()
            else:
                print("Skipping clone. Trying to compile what is there...")
        else:
            # if the directory is empty or just created
            self._clone_repo()

        # recreate motion_files because rmtree overwrites the folder and shit breaks
        self.motion_dir.mkdir(exist_ok=True)

        # compile the sucker
        print("\nCompiling...")
        try:
            # -DUSER_MOTION_SIZE=4000 for longer motion files
            cmd = ['gcc', 'gpssim.c', '-lm', '-O3', '-o', 'gps-sdr-sim', '-DUSER_MOTION_SIZE=4000']
            subprocess.run(cmd, cwd=self.gps_sim_dir, check=True)
            
            if (self.gps_sim_dir / "gps-sdr-sim").exists():
                print("\ngps-sdr-sim compiled successfully.")
            else:
                print("\nCompilation command ran but binary not found.")
        except subprocess.CalledProcessError as e:
            print(f"\nCompilation failed: {e}")
            print("Ensure 'build-essential' is installed: sudo apt install build-essential")
        
        input("Press Enter to continue...")

    def _clone_repo(self):
        print("Cloning https://github.com/osqzss/gps-sdr-sim.git ...")
        subprocess.run(['git', 'clone', 'https://github.com/osqzss/gps-sdr-sim.git', str(self.gps_sim_dir)], check=True)

    def ephemeris_menu(self):
        print("\n--- Ephemeris Manager ---")
        print("GPS-SDR-SIM requires a RINEX GPS navigation file (.n or .19n, .20n etc).")
        print("It does NOT support GLONASS (.g) files for the main simulation.")
        
        #search for existing ephemeras
        found_files = list(self.gps_sim_dir.glob("brdc*"))
        valid_gps_file = None
        
        if found_files:
            print(f"\nFound {len(found_files)} candidate files in {self.gps_sim_dir}:")
            for f in found_files:
                status = ""
                # check for gzip
                if f.suffix == '.gz':
                    print(f"  - {f.name} [GZIP] -> Extracting...")
                    try:
                        subprocess.run(['gunzip', '-k', '-f', str(f)], check=True)
                        unzipped = f.with_suffix('')
                        if 'n' in unzipped.suffix:
                            valid_gps_file = unzipped
                            status = "[OK - GPS]"
                        elif 'g' in unzipped.suffix:
                            status = "[WARNING - GLONASS?]"
                        print(f"    -> Extracted: {unzipped.name} {status}")
                    except Exception as e:
                        print(f"    -> Extraction failed: {e}")
                else:
                    # check suffix for n(gps only) or g(GLONASS shit, CAN work, but its better to not take chances)
                    #standard naming: brdcDDD0.YYn
                    if 'n' in f.suffix or f.suffix.endswith('n'):
                        valid_gps_file = f
                        status = "OK - GPS"
                    elif 'g' in f.suffix:
                        status = "WARNING - THIS IS GLONASS, NOT GPS, you need the n file, not the g one"
                    print(f"  - {f.name} {status}")
        else:
            print(f"\nNo 'brdc*' files found in {self.gps_sim_dir}")

        if not valid_gps_file:
            print("\nNo valid GPS Ephemeris (.n) file found.")
            print("Please download it manually:")
            print("1. Go to https://cddis.nasa.gov/archive/gnss/data/daily/")
            print("2. Select Year -> 'brdc'")
            print("3. Download a file ending in 'n.gz' (e.g., brdc0310.26n.gz)")
            print(f"4. Place it in: {self.gps_sim_dir}")
        else:
            print(f"\nUsing ephemeris: {valid_gps_file.name}")
            #store filename for gen step
            self.ephemeris_file = valid_gps_file

        input("Press Enter to continue...")

    def generate_signal_menu(self):
        if not (self.gps_sim_dir / "gps-sdr-sim").exists():
            print("\ngps-sdr-sim binary not found. Run Setup first.")
            input("Press Enter to continue...")
            return

        # check if we found a valid ephemeris previously and If not - try to find one again quickly
        if not hasattr(self, 'ephemeris_file') or not self.ephemeris_file.exists():
            n_files = list(self.gps_sim_dir.glob("*.*n")) # check for n suffix extension
            if not n_files:
                print("\nNo .n ephemeris file found. Go to Option 2.")
                input("Press Enter to continue...")
                return
            self.ephemeris_file = n_files[0]

        while True:
            os.system('clear')
            print(f"--- Generate Signal (Using {self.ephemeris_file.name}) ---")
            print("1. Static Location (Fixed Point)")
            print("2. Dynamic Circle (Loiter Mode)")
            print("3. Back")
            
            choice = input("Choice: ").strip()
            if choice == '1':
                self._gen_static()
                break
            elif choice == '2':
                self._gen_circle()
                break
            elif choice == '3':
                return

    def _get_time_args(self):
        # extract the year from the ephemeris filename to know the date
        # filename format typically: brdcDDD0.YYn
        filename = self.ephemeris_file.name
        
        try:
            # NOTE: this is retarded, but works and i dont see how this can fail unless the user is just like this method
            if filename.startswith("brdc"):
                day_of_year = int(filename[4:7])
                year_short = int(filename[9:11])
                year = 2000 + year_short
                
                # convert day of year to month/day
                date = datetime.datetime(year, 1, 1) + datetime.timedelta(day_of_year - 1)
                
                #start simulation at the beginning of that day +1 hour to ensure valid ephemeris coverage
                time_str = date.strftime("%Y/%m/%d,01:00:00")
                print(f"Detected Ephemeris Date: {time_str}")
                print("Using -t to align simulation with ephemeris data.")
                return ["-t", time_str]
        except:
            print("[WARN] Could not parse date from filename. Using default time (might fail).")
        
        return []

    def _gen_static(self):
        lat = input("Latitude (e.g. 37.7749): ").strip()
        lon = input("Longitude (e.g. -122.4194): ").strip()
        alt = input("Altitude (m): ").strip() or "100"
        
        # validate input basic
        if not lat or not lon:
            print("Latitude and Longitude required.")
            input("Press Enter...")
            return

        cmd = ['./gps-sdr-sim', '-e', self.ephemeris_file.name, '-b', '8', 
               '-l', f"{lat},{lon},{alt}"]
        
        cmd += self._get_time_args()
        self._run_gen_cmd(cmd)

    def _gen_circle(self):
        #use -x for LLH
        #-x does NOT want time column
        
        lat0_str = input("Center Lat: ")
        lon0_str = input("Center Lon: ")
        if not lat0_str or not lon0_str: return
        
        lat0 = float(lat0_str)
        lon0 = float(lon0_str)
        radius = float(input("Radius (m) [def: 50]: ") or 50)
        speed = float(input("Speed (m/s) [def: 10]: ") or 10)
        duration = int(input("Duration (sec): ") or 300)
        
        #ensure motion directory exists before trying to write to it
        if not self.motion_dir.exists():
            self.motion_dir.mkdir(parents=True, exist_ok=True)

        csv_path = self.motion_dir / "circle_llh.csv"
        
        print("Generating LLH trajectory CSV...")
        try:
            with open(csv_path, 'w') as f:
                # 10hz resolution
                steps = duration * 10 
                for i in range(steps):
                    t = i / 10.0
                    angle = (speed * t / radius) # radians
                    
                    # offsets in meters
                    dx = radius * math.cos(angle)
                    dy = radius * math.sin(angle)
                    
                    # offsets in degrees (flat earth approx)
                    dlat = dy / 111111.0
                    dlon = dx / (111111.0 * math.cos(math.radians(lat0)))
                    
                    # Format: lat,lon,height (No time column for -x)
                    f.write(f"{lat0 + dlat},{lon0 + dlon},100.0\n")
        except Exception as e:
            print(f"[ERROR] Failed to write CSV: {e}")
            input("Press Enter...")
            return
                
        # use -x for LLH CSV, not -u or -g, im retarded D:
        cmd = ['./gps-sdr-sim', '-e', self.ephemeris_file.name, '-b', '8', 
               '-x', str(csv_path), '-d', str(duration)]
        
        cmd += self._get_time_args()
        self._run_gen_cmd(cmd)

    def _run_gen_cmd(self, cmd):
        print(f"\nExecuting: {' '.join(cmd)}")
        print("Processing... (This uses heavy CPU)")
        
        try:
            # run in the gps_sim_dir so it finds the ephemeris file easily
            subprocess.run(cmd, cwd=self.gps_sim_dir, check=True)
            
            bin_path = self.gps_sim_dir / "gpssim.bin"
            if bin_path.exists() and bin_path.stat().st_size > 0:
                print(f"\nSignal binary created: {bin_path.name}")
                print(f"Size: {bin_path.stat().st_size / (1024*1024):.2f} MB")
            else:
                print("\nCommand finished but 'gpssim.bin' is missing or empty.")
        except subprocess.CalledProcessError as e:
            print(f"\nGeneration failed with exit code {e.returncode}")
        
        input("Press Enter to continue...")

    def transmit_menu(self):
        bin_file = self.gps_sim_dir / "gpssim.bin"
        if not bin_file.exists():
            print("\ngpssim.bin not found. You must generate a signal first (Option 3).")
            input("Press Enter to continue...")
            return

        # check for the god damn hackrf bc SOMEHOW my linux machine decided to delete hackrf tools:/, this took quite a while to figure out, lol
        print("\nChecking for HackRF...")
        try:
            result = subprocess.run(['hackrf_info'], capture_output=True, text=True)
            if "Found HackRF" not in result.stdout:
                print("No HackRF device detected.")
                input("Press Enter to continue...")
                return
            else:
                print("HackRF detected.")
        except FileNotFoundError:
            print("hackrf_info command not found. Is hackrf package installed?")
            input("Press Enter to continue...")
            return

        print("\n--- Transmission ---")
        print("Frequency: 1575.42 MHz (GPS L1)")
        print("Sample Rate: 2.6 Msps (Matched to simulation)")
        gain = input("TX Gain (0-47) [def: 25]: ").strip() or "25"
        
        cmd = [
            'hackrf_transfer',
            '-t', 'gpssim.bin',
            '-f', '1575420000',
            '-s', '2600000',
            '-a', '1',       # amp on
            '-x', gain,      # TX Gain
            '-R'             # repeat
        ]
        
        print(f"\nRunning: {' '.join(cmd)}")
        print("Press Ctrl+C to stop transmission.")
        
        try:
            subprocess.run(cmd, cwd=self.gps_sim_dir)
        except KeyboardInterrupt:
            print("\nTransmission ended.")
        except Exception as e:
            print(f"\nTransmission failed: {e}")
            
        input("Press Enter to return to menu...")
