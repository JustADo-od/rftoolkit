import os
import subprocess
import threading
import time
import datetime
import shutil
import signal
import atexit
import json
import re
import math # god fucking damn it, i need math for CPR calculations *AUGH dies of cringe.mp3*
from pathlib import Path
from queue import Queue, Empty

class ADSB:
    # CPR constants and other magic numbers
    NZ = 15.0 
    CPR_MAX_VALUE = 131072.0 # its 2^17
    
    # CPR Latitude Zone Table (yoinked from mayhem))
    # will leave this here for now, MAY not be needed, but im not sure after all this mindfuckery
    ADSB_LAT_LUT = [
        10.47047130, 14.82817437, 18.18626357, 21.02939493,
        23.54504487, 25.82924707, 27.93898710, 29.91135686,
        31.77209708, 33.53993436, 35.22899598, 36.85025108,
        38.41241892, 39.92256684, 41.38651832, 42.80914012,
        44.19454951, 45.54626723, 46.86733252, 48.16039128,
        49.42776439, 50.67150166, 51.89342469, 53.09516153,
        54.27817472, 55.44378444, 56.59318756, 57.72747354,
        58.84763776, 59.95459277, 61.04917774, 62.13216659,
        63.20427479, 64.26616523, 65.31845310, 66.36171008,
        67.39646774, 68.42322022, 69.44242631, 70.45451075,
        71.45986473, 72.45884545, 73.45177442, 74.43893416,
        75.42056257, 76.39684391, 77.36789461, 78.33374083,
        79.29428225, 80.24923213, 81.19801349, 82.13956981,
        83.07199445, 83.99173563, 84.89166191, 85.75541621,
        86.53536998, 87.00000000
    ]

    def __init__(self):
        # setup base dir for logs and config
        self.base_dir = Path.home() / ".rf_toolkit" / "protocols"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.base_dir / "adsb_config.json"
        
        # load default config
        self._set_default_config()
        self._load_config()
        
        # proc management and blah blah
        self.adsb_process = None
        self.monitoring = False
        self.aircraft_data = {}
        self.current_icao = None
        self.current_message_block = []
        #track time for cleanup
        self.last_cleanup = time.time()
        self.debug_mode = False
        self.raw_output_queue = Queue() 
        self.raw_output_buffer = []
        self.has_received_data = False
        
        # CPR data for position decoding
        self.cpr_data = {}
        
        #ensure cleanup runs on exit
        atexit.register(self._exit_cleanup)
    
    def _set_default_config(self):
        # default config
        self.config = {
            "gain": 20,
            "freq": 1090000000,
            "lat": 0.0,
            "lon": 0.0,
            "stats_every": 10,
            "max_display_aircraft": 30,
            # Local decoding option (needs GPS coords in config)
            # Default to False to prevent bad data if location isn't set
            "local_decoding": False
        }

    def _save_config(self):
        #save to json
        try:
            with self.config_path.open('w') as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def _load_config(self):
        # load the config from json if it exists
        try:
            with self.config_path.open('r') as f:
                loaded_config = json.load(f)
                self.config.update(loaded_config)
        except Exception:
            self._save_config()

    def _exit_cleanup(self):
        # make sure we stopped the process on user exit
        if self.monitoring or self.adsb_process:
            self.stop_adsb()
    
    def run(self):
        #main menu
        try:
            while True:
                os.system('clear')
                print("========================================")
                print("       ADS-B AIRCRAFT MONITORING")
                print("========================================")
                debug_status = "ON(raw data)" if self.debug_mode else "OFF (table view)"
                print(f"Debug Mode: {debug_status}")
                local_dec_status = "ON" if self.config.get('local_decoding') else "OFF"
                print(f"Local Decoding: {local_dec_status}")
                print("----------------------------------------")
                print("1. Start ADS-B Monitoring")
                print("2. View Current Aircraft Output")
                print("3. Stop ADS-B Monitoring")
                print("4. Install readsb")
                print("5. Configure HackRF/Display Settings")
                print("6. Toggle Debug Mode")
                print("7. Back to Protocols Menu")
                
                choice = input("\nEnter choice (1-7): ").strip()
                
                if choice == '1':
                    self.start_adsb_monitoring()
                elif choice == '2':
                    self.view_aircraft()
                elif choice == '3':
                    self.stop_adsb()
                elif choice == '4':
                    self.install_readsb()
                elif choice == '5':
                    self.configure_settings()
                elif choice == '6':
                    self.debug_mode = not self.debug_mode
                    print(f"Debug Mode set to {'ON' if self.debug_mode else 'OFF'}.")
                    input("Press Enter to continue...")
                elif choice == '7':
                    self.stop_adsb()
                    return
                else:
                    print("Invalid choice!")
                    input("Press Enter to continue...")
        except KeyboardInterrupt:
            self.stop_adsb()
            return
    
    def is_readsb_available(self):
        # check for readsb
        try:
            if subprocess.run(['which', 'readsb'], capture_output=True, text=True).returncode == 0:
                return True
            if (self.base_dir / 'readsb' / 'readsb').exists():
                return True
            return False
        except:
            return False
    
    def install_readsb(self):
        print("Installing readsb...")
        
        # try apt install
        try:
            subprocess.run(['sudo', 'apt', 'update'], check=True, capture_output=True)
            install_cmd = ['sudo', 'apt', 'install', '-y', 'readsb']
            subprocess.run(install_cmd, check=True, capture_output=True, text=True)
            print("Successfully installed readsb from repositories!")
            return
        except subprocess.CalledProcessError:
            print("System package installation failed. Proceeding to source build...")
        except Exception as e:
            print(f"Error during repository check: {e}")

        #build from source if shit doesnt work
        try:
            readsb_dir = self.base_dir / "readsb"
            if readsb_dir.exists():
                shutil.rmtree(readsb_dir)
            
            print("Cloning readsb repository...")
            subprocess.run(['git', 'clone', 'https://github.com/wiedehopf/readsb.git', str(readsb_dir)], check=True)
            
            print("Building readsb...")
            build_cmd = ['make', 'RTLSDR=yes']
            subprocess.run(build_cmd, cwd=readsb_dir, check=True, capture_output=True, text=True)
            
            print("readsb built successfully locally!")
        except subprocess.CalledProcessError as e:
            print("readsb source build failed.")
            print(f"Errors:\n{e.stderr}")
        except Exception as e:
            print(f"Source build failed: {e}")
            
        input("Press Enter to continue...")
    
    def get_readsb_path(self):
        # path to the binary
        local_path = str(self.base_dir / 'readsb' / 'readsb')
        if Path(local_path).exists():
            return local_path
        
        try:
            result = subprocess.run(['which', 'readsb'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        return None
        
    def configure_settings(self):
        # config menu
        while True:
            os.system('clear')
            print("========================================")
            print("     CONFIGURE ADS-B SETTINGS")
            print("========================================")
            print(f"1. HackRF Gain (dB):        {self.config['gain']}")
            print(f"2. Frequency (Hz):          {self.config['freq']}")
            print(f"3. Receiver Latitude:       {self.config['lat']}")
            print(f"4. Receiver Longitude:      {self.config['lon']}")
            print(f"5. Max Aircraft to Display: {self.config['max_display_aircraft']}")
            # added local decoding switch(needs user's lat and lon numbers)
            local_status = "Enabled" if self.config.get('local_decoding') else "Disabled"
            print(f"6. Local Decoding:          {local_status}")
            print("7. Save & Back to Main Menu")
            print("----------------------------------------")
            
            choice = input("\nEnter choice to change (1-7): ").strip()

            if choice == '7':
                self._save_config()
                break
            
            if choice == '6':
                #the toggle for local decoding itself
                self.config['local_decoding'] = not self.config.get('local_decoding', False)
                print(f"\nLocal decoding is now {'Enabled' if self.config['local_decoding'] else 'Disabled'}.")
                input("Press Enter to continue...")
                continue

            setting_map = {
                '1': ('gain', int, "Enter HackRF Gain (dB, e.g., 20): "),
                '2': ('freq', int, "Enter Frequency (Hz, e.g., 1090000000): "),
                '3': ('lat', float, "Enter Receiver Latitude (e.g., 34.05): "),
                '4': ('lon', float, "Enter Receiver Longitude (e.g., -118.24): "),
                '5': ('max_display_aircraft', int, "Enter Max Aircraft Rows to Display (e.g., 30): "),
            }
            
            if choice in setting_map:
                key, type_func, prompt = setting_map[choice]
                try:
                    new_value = input(prompt).strip()
                    if new_value:
                        self.config[key] = type_func(new_value)
                        print(f"\n{key.replace('_', ' ').title()} updated to {self.config[key]}.")
                    else:
                        print("\nNo change made.")
                except ValueError:
                    print("\nInvalid input. Please enter the correct data type.")
                except Exception as e:
                    print(f"\nAn error occurred: {e}")
            else:
                print("\nInvalid choice.")

            input("Press Enter to continue...")

    def start_adsb_monitoring(self):
        # start readsb process and blah blah
        if not self.is_readsb_available():
            print("readsb not found! Please install it first using option 4.")
            input("Press Enter to continue...")
            return
        
        readsb_path = self.get_readsb_path()
        if not readsb_path:
            print("Could not find readsb executable!")
            input("Press Enter to continue...")
            return
        
        try:
            self.stop_adsb() #stop any running process
            print("Starting ADS-B monitoring...")
            
            # readsb command
            cmd = [
                readsb_path,
                '--device-type', 'hackrf',
                '--gain', str(self.config['gain']),
                '--freq', str(self.config['freq']),
                '--lat', str(self.config['lat']),
                '--lon', str(self.config['lon']),
                '--stats-every', str(self.config['stats_every']),
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            
            #reset state variables
            self.monitoring = True
            self.aircraft_data = {}
            self.raw_output_buffer = []
            self.has_received_data = False
            self.current_icao = None
            self.current_message_block = []
            self.cpr_data = {}
            
            #start readsb subprocess
            self.adsb_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                preexec_fn=os.setsid # Create new process group
            )
            
            #threads for output processing, separate since forever cause its easier that way and it broke when i tr
            threading.Thread(target=self._enqueue_output, daemon=True).start()
            threading.Thread(target=self._process_data, daemon=True).start()
            
            print("ADS-B monitoring process initiated. Data will be available shortly.")
            time.sleep(2)
            
        except Exception as e:
            print(f"\n Error starting ADS-B monitoring: {e}")
            #stderr output if available
            if self.adsb_process and self.adsb_process.stderr:
                try:
                    err_output = self.adsb_process.stderr.read().strip()
                    if err_output:
                        print("\n--- readsb stderr output ---")
                        print(err_output)
                        print("--- end of stderr ---\n")
                except Exception:
                    pass
            print("Monitoring not started.")
            self.monitoring = False
            
        input("Press Enter to continue...")

    def _enqueue_output(self):
        # read through stdout/stderr from subprocess and enqueue for all the juicy stuff(processing)
        def read_pipe(pipe, source):
            while self.monitoring:
                try:
                    line = pipe.readline()
                    if line:
                        self.raw_output_queue.put(line)
                    else:
                        if self.adsb_process.poll() is not None:
                            break
                        time.sleep(0.1)
                except Exception:
                    break

        # separate threads for stdout and stderr reading (same as the previous comment on this)
        if self.adsb_process and self.adsb_process.stdout:
            threading.Thread(target=read_pipe, args=(self.adsb_process.stdout, 'stdout'), daemon=True).start()
        if self.adsb_process and self.adsb_process.stderr:
            threading.Thread(target=read_pipe, args=(self.adsb_process.stderr, 'stderr'), daemon=True).start()

    def _process_data(self):
        # pull data and parse it
        while self.monitoring:
            try:
                line = self.raw_output_queue.get_nowait()
                line_str = line.strip()
                
                if not line_str:
                    continue
                
                # data reception check
                if not self.has_received_data and len(line_str) > 5 and line_str.startswith('*'):
                    self.has_received_data = True

                # output for debug
                self.raw_output_buffer.append(line_str)
                if len(self.raw_output_buffer) > 200: 
                    self.raw_output_buffer = self.raw_output_buffer[-100:]

                # Process complete message blocks for data extraction
                self._process_message_line(line_str)

                # non critical DOGSHIT THAT WASTED TOO MUCH OF MY FUCKING TIME
                non_critical_errors = [
                    'cpr attempts that failed the range check',
                    'cpr attempts that failed the speed check',
                    'cpr messages that look like transponder failures filtered',
                    'accepted with 1-bit error repaired'
                ]
                
                is_critical_error = any(err in line_str.lower() for err in ['fail', 'fatal', 'error', 'cannot open', 'device not found'])
                
                if is_critical_error and not any(non_crit in line_str.lower() for non_crit in non_critical_errors):
                    # print CRITICAL shit into the console
                    print(f"\nREADSB ERROR: {line_str}")
                    
            except Empty:
                time.sleep(0.1) # wait if queue is as big as diddy's sentence
            except Exception:
                pass

    def _process_message_line(self, line):
        # complete message blocks for parsing based on start markers
        if line.startswith('*'):
            # Process the previous message block if we have one(we do have one, right?)
            if self.current_message_block:
                self._parse_complete_message_block()
            
            # start of a new message block
            self.current_message_block = [line]
            self.current_icao = None
        #ensure block exists and isnt empty
        elif self.current_message_block:
            # Continue adding to current message block... they are message blocks... from a message block factory.... theyaremessageblo-
            self.current_message_block.append(line)
            
            # if the block is SUS(sorry)piciously long or ends, process it
            if not line.strip() or len(self.current_message_block) > 20:
                self._parse_complete_message_block()
                self.current_message_block = []

    def _parse_complete_message_block(self):
        # Parse a block of readsb output for data, translation: BUTCHER THE SUCKER
        if not self.current_message_block:
            return
            
        block_text = '\n'.join(self.current_message_block)

        # Reverted ICAO extraction to regex, still will have the DF: stuff for reliability
        icao = None
        icao_match = re.search(r'hex:\s*[~]?([0-9a-fA-F]{6})', block_text)
        if icao_match:
            icao = icao_match.group(1).upper()
            self.current_icao = icao
        elif 'DF:' in block_text:
            match_df = re.search(r'AA:([0-9a-fA-F]{6})', block_text)
            if match_df:
                icao = match_df.group(1).upper()
                self.current_icao = icao

        if self.current_icao:
            aircraft = self._get_aircraft_defaults(self.current_icao)
            self._parse_message_block_fields(block_text, aircraft)

    def _parse_message_block_fields(self, block_text, aircraft):
        # Extract callsign, altitude, speed, V-rate, heading, lon/lat using regex (holy fuck i wanna kill myself)
        
        #callsign
        callsign_match = re.search(r'Ident:\s*([A-Z0-9]{2,8})\s', block_text)
        if callsign_match:
            callsign = callsign_match.group(1).strip()
            if callsign and len(callsign) >= 2 and callsign != 'unknown':
                aircraft['callsign'] = callsign

        #altitude (baro or geom, whatever tf works)
        alt_patterns = [r'(?:Baro|Geom) altitude:\s*([0-9,]+)\s*ft', r'Altitude:\s*([0-9,]+)\s*ft']
        for pattern in alt_patterns:
            alt_match = re.search(pattern, block_text)
            if alt_match:
                altitude = alt_match.group(1).replace(',', '')
                if altitude and altitude != 'N/A':
                    aircraft['altitude'] = altitude
                    break

        # SPEED (groundspeed, TAS or IAS)
        speed_patterns = [r'Groundspeed:\s*([0-9.]+)\s*kt', r'True Airspeed:\s*([0-9.]+)\s*kt', r'IAS:\s*([0-9.]+)\s*kt']
        for pattern in speed_patterns:
            speed_match = re.search(pattern, block_text)
            if speed_match:
                speed = speed_match.group(1)
                if speed and speed != 'N/A':
                    if 'True Airspeed' in pattern:
                        aircraft['speed'] = f"{speed} kt (TAS)"
                    else:
                        aircraft['speed'] = f"{speed} kt"
                    break

        # heading/track
        heading_match = re.search(r'(?:Track/Heading|True Track|Heading|Mag heading)\s+([0-9.]+)', block_text)
        if heading_match:
            heading = heading_match.group(1)
            if heading and heading != 'N/A':
                aircraft['heading'] = heading

        # V-rate, also called vertical rate, hm, i learned something new today
        vrate_match = re.search(r'(?:Vertical Rate|Baro rate|Airborne rate|Surface rate):\s*([+-]?[0-9.]+)\s*ft/min', block_text)
        if vrate_match:
            v_rate = vrate_match.group(1)
            if v_rate and v_rate != 'N/A':
                aircraft['v_rate'] = v_rate

        # parse and store cpr
        self._parse_position_data_from_block(block_text, aircraft)

    def _parse_position_data_from_block(self, block_text, aircraft):
        # Store CPR frames and try to decode position
        icao = aircraft['hex']

        cpr_type_match = re.search(r'CPR type:\s*(Airborne|Surface)', block_text)
        cpr_type = cpr_type_match.group(1) if cpr_type_match else None

        #check for local decoding toggle from config
        use_local = self.config.get('local_decoding', False)

        if not cpr_type:
            pos_match = re.search(r'Latitude:\s*([+-]?\d+\.?\d*)\s+Longitude:\s*([+-]?\d+\.?\d*)', block_text)
            if pos_match:
                aircraft['lat'] = pos_match.group(1)
                aircraft['lon'] = pos_match.group(2)
            return

        odd_match = re.search(r'CPR odd flag:\s*odd', block_text)
        even_match = re.search(r'CPR odd flag:\s*even', block_text)
        lat_match = re.search(r'CPR latitude:\s*\(([0-9]+)\)', block_text)
        lon_match = re.search(r'CPR longitude:\s*\(([0-9]+)\)', block_text)

        if (odd_match or even_match) and lat_match and lon_match:
            is_odd = bool(odd_match)
            lat = int(lat_match.group(1))
            lon = int(lon_match.group(1))

            if icao not in self.cpr_data:
                self.cpr_data[icao] = {}

            current_time = time.time()
            frame_data = {'lat': lat, 'lon': lon, 'time': current_time, 'type': cpr_type}

             #if local decoding is enabled, try to decode immediately with reference position
            decoded_locally = False
            # determine format bit 'i': 0 for even, 1 for odd
            if use_local:
                i = 1 if is_odd else 0
                try:
                    ref_lat = float(self.config.get('lat', 0.0))
                    ref_lon = float(self.config.get('lon', 0.0))

                    #decode latitude
                    rec_lat = self._local_decode_lat(ref_lat, lat, i)
                    # if no lat - cannot proceed
                    if rec_lat is not None:
                        # calculate NL using recovered latitude
                        nl = self._cpr_NL(rec_lat)
                        # decode longitude
                        rec_lon = self._local_decode_lon(ref_lon, lon, i, nl)
                        
                        if rec_lon is not None:
                            aircraft['lat'] = f"{rec_lat:.4f}"
                            aircraft['lon'] = f"{rec_lon:.4f}"
                            decoded_locally = True
                except Exception:
                    pass # fallback to global if local fails

            if is_odd:
                self.cpr_data[icao]['odd'] = frame_data
                self.cpr_data[icao]['last_odd'] = current_time
            else:
                self.cpr_data[icao]['even'] = frame_data
                self.cpr_data[icao]['last_even'] = current_time

            # Only try global decode if local didn't happen (or failed)
            if not decoded_locally:
                self._try_decode_cpr_position(icao, aircraft)

        pos_match = re.search(r'Latitude:\s*([+-]?\d+\.?\d*)\s+Longitude:\s*([+-]?\d+\.?\d*)', block_text)
        if pos_match:
            aircraft['lat'] = pos_match.group(1)
            aircraft['lon'] = pos_match.group(2)

    def _get_aircraft_defaults(self, icao):
        # Initialize or update an aircraft entry and its last_seen
        if icao not in self.aircraft_data:
            self.aircraft_data[icao] = {
                'hex': icao,
                # use time.time() float for logic, convert to string only for display
                'last_seen': time.time(),
                'callsign': 'N/A',
                'altitude': 'N/A',
                'speed': 'N/A',
                'heading': 'N/A',
                'v_rate': 'N/A',
                'lat': 'N/A',
                'lon': 'N/A',
            }
        self.aircraft_data[icao]['last_seen'] = time.time()
        return self.aircraft_data[icao]
        
    def _cleanup_old_aircraft(self):
        #remove aircraft tracks that havent updated in 60 seconds
        cutoff_time = time.time() - 60
        # create list of keys to remove to avoid runtime errors during iteration
        to_remove = [k for k, v in self.aircraft_data.items() if v['last_seen'] < cutoff_time]
        for k in to_remove:
            del self.aircraft_data[k]

    def _cpr_NL(self, lat):
        # ICAO specified NL function
        if lat == 0:
            return 59
        
        # fixed threshold for nl=1
        if abs(lat) >= 87.0:
            return 1

        lat_rad = math.radians(abs(lat))
        try:
            t = 1 - math.cos(math.pi / 30) / math.cos(lat_rad)
            if t <= 0:
                return 1
            #Note: whaat is happening????? i think this works
            acos_arg = t
            if acos_arg < -1:
                acos_arg = -1
            if acos_arg > 1:
                acos_arg = 1

            nl = int(math.floor(2 * math.pi / math.acos(acos_arg)))
            return nl
        except ValueError:
            return 1

    def _cpr_Dlat(self, i):
        return 360.0 / (60 - i)

    def _cpr_Dlon(self, i, nl):
        ni = max(1.0, nl - i)
        return 360.0 / ni

    def _cpr_mod(self, a, b):
        r = a % b
        return r if r >= 0 else r + b

    # updated global cecoding logic to match NASA article(i fucked up, now fixed)
    def _decode_cpr(self, even_lat, even_lon, odd_lat, odd_lon, even_ts, odd_ts, cpr_type, ref_lat, ref_lon):
        # max time difference check
        dt = abs(even_ts - odd_ts)
        if dt > 10.0:
            return None

        # integer math for zone Index, using integer division // to mimic floor
        j = (59 * even_lat - 60 * odd_lat + 65536) // 131072

        dlat_even = 360.0 / 60.0
        dlat_odd = 360.0 / 59.0

        # find latitude for both even and odd frames
        #rlat = dlat * ( (zin - nz * floor(zin/nz)) + YZ/2^17 )
        
        #even frame (i=0)
        rlat_even = dlat_even * (self._cpr_mod(j, 60) + even_lat / 131072.0)
        # odd frame (i=1)
        rlat_odd = dlat_odd * (self._cpr_mod(j, 59) + odd_lat / 131072.0)

        # select most recent latitude
        if even_ts >= odd_ts:
            rlat = rlat_even
            i = 0
            xz = even_lon
        else:
            rlat = rlat_odd
            i = 1
            xz = odd_lon

        #removed a hack, cause it fucks shit up
        if rlat < -90.0 or rlat > 90.0:
            return None

        #check NL consistency
        # global decoding of lon is valid only if NL(rlat_even) == NL(rlat_odd)
        nl_even = self._cpr_NL(rlat_even)
        nl_odd = self._cpr_NL(rlat_odd)
        
        if nl_even != nl_odd:
            return None
            
        nl = nl_even # common NL value

        # lon decoding
        if nl == 1:
            rlon = 360.0 * xz / 131072.0
        else:
            #correct modulus is nli = max(nl - i, 1)
            nli = max(nl - i, 1)
            dlon = 360.0 / nli
            
            #integer math for lon zone index
            m = ((nl - 1) * even_lon - nl * odd_lon + 65536) // 131072
            
            rlon = dlon * (self._cpr_mod(m, nli) + xz / 131072.0)

        # normalize lon to standard [-180, 180]
        if rlon >= 180.0: rlon -= 360.0
        
        return rlat, rlon

    def _local_decode_lat(self, lat_ref, lat_msg, i):
        # new - added validity check for local decoding
        
        if not (0 <= lat_msg < self.CPR_MAX_VALUE):
            raise ValueError("lat_msg out of 17-bit range")

        dlati = self._cpr_Dlat(i)
        
        #local decoding formula
        encoded_term = lat_msg / self.CPR_MAX_VALUE
        j1 = math.floor(lat_ref / dlati)
        mod_term = self._cpr_mod(lat_ref, dlati) / dlati
        j2 = math.floor(0.5 + mod_term - encoded_term)
        j = j1 + j2
        
        rlat = dlati * (j + encoded_term)
        
        #removed wrap, check bounds(same hack as in the global decode)
        if rlat < -90.0 or rlat > 90.0:
            return None 
            
        # range check
        limit = dlati/2.0 - dlati/262144.0 
        if abs(rlat - lat_ref) > limit:
            return None # Too far from reference

        return rlat

    def _local_decode_lon(self, lon_ref, lon_msg, i, nl):
        # normalize reference lon
        lon_ref = (lon_ref + 360.0) % 360.0
        
        if not (0 <= lon_msg < self.CPR_MAX_VALUE):
            raise ValueError("lon_msg out of 17-bit range")

        #use correct nli for local decode
        nli = max(nl - i, 1)
        dloni = 360.0 / nli 
        
        encoded_term = lon_msg / self.CPR_MAX_VALUE
        m1 = math.floor(lon_ref / dloni)
        mod_term = self._cpr_mod(lon_ref, dloni) / dloni
        m2 = math.floor(0.5 + mod_term - encoded_term)
        m = m1 + m2
        
        rlon = dloni * (m + encoded_term)
        
        #normalize result
        if rlon > 180.0: rlon -= 360.0
        
        #wrap-around distance for longitude
        diff = abs(rlon - ((lon_ref + 180) % 360 - 180)) 
        if diff > 180: diff = 360 - diff
        
        limit = dloni/2.0 - dloni/262144.0
        if diff > limit:
            return None

        return rlon

    def _try_decode_cpr_position(self, icao, aircraft):
        if icao not in self.cpr_data:
            return

        cpr_data = self.cpr_data[icao]

        if 'odd' not in cpr_data or 'even' not in cpr_data:
            return

        last_odd_ts = cpr_data.get('last_odd', 0.0)
        last_even_ts = cpr_data.get('last_even', 0.0)

        odd_type = cpr_data['odd'].get('type')
        even_type = cpr_data['even'].get('type')
        if odd_type != even_type or not odd_type:
            return

        if abs(last_odd_ts - last_even_ts) >= 10.0:
            return

        odd_data = cpr_data['odd']
        even_data = cpr_data['even']

        ref_lat = self.config.get('lat', 0.0)
        ref_lon = self.config.get('lon', 0.0)

        try:
            result = self._decode_cpr(
                even_data['lat'], even_data['lon'],
                odd_data['lat'], odd_data['lon'],
                last_even_ts, last_odd_ts,
                odd_type, ref_lat, ref_lon
            )

            if result is not None:
                lat_deg, lon_deg = result
                aircraft['lat'] = f"{lat_deg:.4f}"
                aircraft['lon'] = f"{lon_deg:.4f}"

            if last_odd_ts > last_even_ts:
                cpr_data.pop('even', None)
                cpr_data.pop('last_even', None)
            else:
                cpr_data.pop('odd', None)
                cpr_data.pop('last_odd', None)

        except ValueError:
            pass
        except Exception:
            pass

    def view_aircraft(self):
        if not self.monitoring or not self.adsb_process:
            print("ADS-B monitoring is not running! Start monitoring first using option 1.")
            input("Press Enter to continue...")
            return

        try:
            while True:
                os.system('clear')

                print("=" * 125)
                print("         AIRCRAFT DATA - ADS-B")
                print("=" * 125)

                # cleanup old aircraft before displaying
                self._cleanup_old_aircraft()

                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"Last Update: {now_str}")
                print(f"Mode: {'RAW DATA (DEBUG)' if self.debug_mode else 'DECODED DATA'}")
                monitor_status = 'data is being received' if self.has_received_data else 'waiting for first message... (Check device and antenna)'
                print(f"Monitoring status: {monitor_status}")

                if self.debug_mode:
                    print("--- RAW READSB OUTPUT (Last 50 lines) ---")
                    if self.raw_output_buffer:
                        for line in self.raw_output_buffer[-50:]:
                            print(line)
                    else:
                        print("No raw data buffer available yet.")
                else:
                    total_tracks = len(self.aircraft_data)
                    max_rows = self.config['max_display_aircraft']

                    print(f"Aircraft tracks seen (Last 60 seconds): {total_tracks} (Displaying top {min(total_tracks, max_rows)})")
                    print("=" * 125)

                    if not self.aircraft_data:
                        print("No aircraft tracks currently active.")
                    else:
                        header = f"{'ICAO Hex':<10} {'Callsign':<12} {'Altitude':<12} {'Speed':<12} {'Heading':<10} {'V-Rate':<10} {'Lat/Lon':<25} {'Last Seen':<10}"
                        print(header)
                        print("-" * 125)

                        sorted_aircraft = sorted(
                            self.aircraft_data.values(),
                            key=lambda x: x.get('last_seen', 0.0), 
                            reverse=True
                        )

                        for aircraft in sorted_aircraft[:max_rows]:
                            hex_code = aircraft.get('hex', '---')
                            callsign = aircraft.get('callsign', 'N/A')
                            altitude = aircraft.get('altitude', 'N/A')
                            speed = aircraft.get('speed', 'N/A')
                            heading = aircraft.get('heading', 'N/A')
                            v_rate = aircraft.get('v_rate', 'N/A')
                            
                            # convert timestamp to string only for display
                            ts = aircraft.get('last_seen', 0.0)
                            if isinstance(ts, float):
                                last_seen = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                            else:
                                last_seen = str(ts) # fallback if something broke

                            lat_lon = f"{aircraft.get('lat', 'N/A')}/{aircraft.get('lon', 'N/A')}"

                            if v_rate not in ('N/A', '0') and v_rate.replace('+', '').replace('-', '').replace('.', '').isdigit():
                                v_rate_display = f"{int(float(v_rate)):+} ft/m"
                            else:
                                v_rate_display = v_rate

                            if altitude != 'N/A' and altitude.replace(',', '').replace(' ft', '').isdigit():
                                altitude_display = f"{int(altitude.replace(',', ''))} ft"
                            else:
                                altitude_display = altitude

                            speed_display = speed
                            if speed != 'N/A' and ' kt' not in speed and '(TAS)' not in speed:
                                speed_display = f"{speed} kt"

                            print(f"{hex_code:<10} {callsign:<12} {altitude_display:<12} {speed_display:<12} {heading:<10} {v_rate_display:<10} {lat_lon:<25} {last_seen:<10}")

                print("\nPress Ctrl+C to return to the menu.")
                time.sleep(1)

        except KeyboardInterrupt:
            return

    def stop_adsb(self):
        if self.adsb_process:
            try:
                os.killpg(os.getpgid(self.adsb_process.pid), signal.SIGTERM)
            except Exception:
                try:
                    self.adsb_process.terminate()
                except Exception:
                    pass
            self.adsb_process = None
        self.monitoring = False


if __name__ == "__main__":
    adsb = ADSB()
    adsb.run()
