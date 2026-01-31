### !!! WARNING: This is a pretty powerful radio frequency (RF) toolkit in terms of potential trouble you can get yourself in. !!!
**Use this ONLY in isolated, controlled environments, and only on property and equipment you own or have explicit authorization to use.**
Radio transmission, jamming, and spoofing are heavily regulated activities.
**Seriously - you can get in legal trouble real fast.**

### LEGAL DISCLAIMER (READ CAREFULLY)

I, as a developer of this RFToolkit do not take ANY responsibility for your(user's) actions. By using this software, you acknowledge that **YOU are solely responsible** for complying with all applicable local, national, and international laws and regulations concerning radio communication, transmission, and interference.

#### DSD (Digital Speech Decoding) Patent Warning

The DSD feature relies on the **dsdccx** utility, which uses an underlying library called **mbelib** to decode digital voice standards (like DMR). This vocoder technology (AMBE/MBE) **may be covered by one or more U.S. patents owned by DVSI Inc.** The GPL license of this software grants you copyright rights, but it **does not** grant you patent rights. Proceed with caution and ensure compliance with patent law in your jurisdiction if using the DSD feature.

==================================================
### DO NOT CONTRIBUTE ANY LLM GENERATED CODE, EVEN IF YOU THINK IT WORKS, EVEN IF YOU TESTED IT, I DONT CARE
==================================================

### "What even is this?"

This is my RFToolkit, made for the **HackRF One SDR**, currently in development, but all the features added right now seem to work just fine.

### "Will it work with rtlsdr/bladesdr/whateversdr?"

No, right now this toolkit is made only for **HackRF One SDR**, simply because it is the only SDR I have, and I am not distributing untested code to public use (shoutout to y'all kernel source posters).

### "Why pythoooooon~, are you not a hardcore c/cpp coderrrrrrr?"

I CAN code in c or cpp, but it will take a lot more time to develop new features, make it harder for others to understand what is going on in my code and also make it more complicated to use since compiling and blah blah.

### "When `X` or `Y` feature will be added?"

You gotta curb your appetite, i am the only developer, and i am currently in college so my free time is limited to how much a human can live without sleep, if you want something to be done sooner - send an issue report with:
1. Idea
2. General purpose
3. What can be used to do it
4. Some code

Otherwise your words mean nothing, and i will dunk on you for trying to get spoonfed all the juice

### "How can i support/sponsor the project?"
Dont... seriously, i will not take the money, first - because transferring funds to where i live is basically watching your debit card desintegrate before your very eyes, second - i am doing this project for my own use in the first place, so keep that in mind and lastly third - you cannot sponsor someone, that doesnt give a sheesh about when to push updates(monke see cool sdr related article online, monke code)

==================================================

### General Usage Guide

1.  **First Step:** Run `python3 setup.py`(or `chmod +x setup.py` so you can ./setup.py) to check for all needed system dependencies and to create the necessary directories.
2.  **Run Toolkit:** Then, run the main script: `python3 rftoolkit.py` or `./rftoolkit.py`(if you chmod-ed it).
3.  **Navigate:** Navigate the menus from there using numbers and **Enter** keypresses.

### About Functions:

* **RF_Replay** - Does exactly what it sounds like: record a signal, store it, and replay when needed.
* **GPS_Spoof** - Allows you to spoof a GPS signal on devices nearby using an ephemeris satellite data file (publicly available from NASA sites).
* **RF_Jamming** - Literally a jammer that allows you to either block one frequency or sweep a wide range of frequencies.
    * **NOTE:** Jamming a wide range of frequencies using sweeping/random methods is not as effective, simply because we cannot cover much with just one device.
* **Protocols** - Contains protocol-specific tools. For now includes:
    * **ADS-B Protocol Scan:** Decodes aircraft transmissions on 1090 MHz. **NEW: now fully works(also added Local/Global CPR decoding method switch)** **(If you want to learn more about Compact Position Reporting, this is what i used to make adsb.py stuff: https://shemesh.larc.nasa.gov/fm/papers/FAOC2021-draft.pdf and https://shemesh.larc.nasa.gov/fm/papers/FM2018-draft.pdf ALSO check nasa's github, there are examples in cpp i think, thank them for making adsb.py possible!)**
    * **DSD (Digital Speech Decoder) (BETA):** Captures and decodes digital voice communications (DMR, dPMR, etc.). **Needs further testing.**
* **Samples/Scripts (Portapack/FZ)** - Menu for using pre-recorded samples or activating interesting scripts taken from different Portapack and Flipper Zero firmwares (Coming Soon).

==================================================

### Bug Reports & Testing

I don't expect this thing to work for everyone and everywhere. I try to test all functions I add before pushing commits to GitHub. **BUT**, I can't test some features myself (like ADS-B or DSD, because I don't have planes flying here, and active DSD transmission in my range).

**PLEASE** - submit **ANY** issues, and I mean **ANY** issues to the GitHub issue tracker. Your reports are highly appreciated and will really help the project development. I will answer to anything if you are not rage-baiting and need genuine help.

### TODO:

* It's so ugly... (Will add coloring in near future).
* gps_spoof.py kinda sucks balls, the reason being - it only works on L1 and not all of them(L1, L2, L5, or however tf many are there), also GPS epoch exists
* Actually make the `Samples/Scripts` tab functional.
* Add more stuff to the `Protocols` tab + test already pushed features.
* Remove all swears and хихи-хаха from the code comments if I want to present this as a college coding project (the reason why I'm making this in Python, lol(also gnuradio, scripts coming soon too:D)).
* Upgrade dsd.py error handling, add some other features and checks to it
* Add a sound output support for nethunter chroot-ed devices, currently only record function for DSD will work
* Add IMSI scanner
* Add drone scanner(really hard, MAYBE impossible with hackrf, altho doubt that)
