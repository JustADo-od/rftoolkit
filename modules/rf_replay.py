import os
import time
from pathlib import Path
import subprocess
import json

# defining stuff
class RFReplay:
    def __init__(self):
        self.recording = False
        self.base_dir = Path.home() / ".rf_toolkit" / "recordings"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.base_dir / "rf_replay_config.json"
        self._set_default_config()
        self._load_config()

    def _set_default_config(self):
        self.config = {
            "sample_rate": 2000000,
            "rx_lna": 16,
            "rx_vga": 20,
            "tx_gain": 0,
        }

    def _load_config(self):
        try:
            with self.config_path.open("r") as f:
                self.config.update(json.load(f))
        except Exception:
            self._save_config()

    def _save_config(self):
        try:
            with self.config_path.open("w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def configure_settings(self):
        while True:
            os.system("clear")

            print("====== RF SETTINGS ======")
            print(f"1. Sample Rate : {self.config['sample_rate']}")
            print(f"2. RX LNA Gain : {self.config['rx_lna']}")
            print(f"3. RX VGA Gain : {self.config['rx_vga']}")
            print(f"4. TX Gain     : {self.config['tx_gain']}")
            print("5. Save & Return")

            choice = input("Select option: ").strip()

            if choice == "5":
                self._save_config()
                return

            setting_map = {
                "1": ("sample_rate", int, "Enter sample rate: "),
                "2": ("rx_lna", int, "Enter RX LNA (0-40): "),
                "3": ("rx_vga", int, "Enter RX VGA (0-62): "),
                "4": ("tx_gain", int, "Enter TX gain (0-47): "),
            }

            if choice in setting_map:
                key, dtype, prompt = setting_map[choice]
                try:
                    val = input(prompt).strip()
                    if val:
                        self.config[key] = dtype(val)
                except Exception:
                    print("Invalid input")

            input("Press Enter...")

    def run(self):
        while True:
            # cool ass logo for the looks (coloring needed, it sucks D:)
            os.system("clear")
            print("======================================")
            print("            RF REPLAY MENU            ")
            print("======================================")
            print("1. Record RF Signal")
            print("2. Replay Recorded Signal")
            print("3. List Recordings")
            print("4. Configure RF Settings")
            print("5. Back to Main Menu")

            choice = input("\nEnter choice (1-5): ").strip()

            if choice == "1":
                self.record_signal()
            elif choice == "2":
                self.replay_signal()
            elif choice == "3":
                self.list_recordings()
            elif choice == "4":
                self.configure_settings()
            elif choice == "5":
                return
            else:
                print("Invalid choice!")
                input("Press Enter to continue...")

    # stuff for signal recording
    def record_signal(self):
        try:
            freq = input("Enter frequency in MHz (e.g., 433.92): ").strip()
            if not freq.replace(".", "").isdigit():
                print("Invalid frequency!")
                return

            filename = input("Enter filename (without extension): ").strip()
            if not filename:
                filename = f"recording_{int(time.time())}"

            filepath = self.base_dir / f"{filename}.iq"

            print(f"\nRecording on {freq} MHz...")
            print("Press Ctrl+C to stop recording")

            # using hackrf_transfer to do stuff
            cmd = [
                "hackrf_transfer",
                "-r",
                str(filepath),
                "-f",
                f"{float(freq) * 1e6}",
                "-s",
                str(self.config["sample_rate"]),
                "-g",
                str(self.config["rx_vga"]),
                "-l",
                str(self.config["rx_lna"]),
            ]

            process = subprocess.Popen(cmd)

            try:
                process.wait()
            except KeyboardInterrupt:
                process.terminate()
                print("\nRecording stopped!")
                time.sleep(1)
        except Exception as e:
            print(f"Recording error: {e}")

        input("Press Enter to continue...")

    # the replaying itself
    def replay_signal(self):
        recordings = list(self.base_dir.glob("*.iq"))
        if not recordings:
            print("No recordings found!")
            input("Press Enter to continue...")
            return

        print("\nAvailable recordings:")
        for i, rec in enumerate(recordings):
            print(f"{i + 1}. {rec.name}")

        try:
            choice = int(input("\nSelect recording to replay: ")) - 1
            if 0 <= choice < len(recordings):
                freq = input("Enter replay frequency in MHz: ").strip()
                repeat = (
                    input("Repeat transmission? (y/n, default n): ").strip().lower() or "n"
                )

                print(f"Replaying {recordings[choice].name} on {freq} MHz...")

                cmd = [
                    "hackrf_transfer",
                    "-t",
                    str(recordings[choice]),
                    "-f",
                    f"{float(freq) * 1e6}",
                    "-s",
                    str(self.config["sample_rate"]),
                    "-x",
                    str(self.config["tx_gain"]),
                ]

                # Adding repeat option if requested
                if repeat == "y":
                    cmd.append("-R")
                    print("Mode: Continuous repeat - Press Ctrl+C to stop")
                else:
                    print("Mode: Single transmission - Will stop automatically")

                process = subprocess.Popen(cmd)

                try:
                    process.wait()
                except KeyboardInterrupt:
                    if repeat == "y":
                        print("\nStopping repeated transmission...")
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
            else:
                print("Invalid selection!")
        except (ValueError, KeyboardInterrupt):
            print("Operation cancelled!")

        input("Press Enter to continue...")

    # list of all recordings saved
    def list_recordings(self):
        recordings = list(self.base_dir.glob("*.iq"))
        if not recordings:
            print("No recordings found!")
        else:
            print("\nRecorded files:")
            for rec in recordings:
                size = rec.stat().st_size / (1024 * 1024)  # size in MB
                print(f"  {rec.name} ({size:.2f} MB)")

        input("\nPress Enter to continue...")