# Meteor Lake GPIO port draft — NOT a bootable kext

The captured Latitude controller is INTC1083 with five 64KiB resource regions. Intel's Linux driver maps INTC1083 to Meteor Lake-P: 289 pads, five communities. Upstream VoodooGPIO lacks this platform, and its interrupt-status register is hardcoded to 0x100; Meteor Lake uses 0x200. A device-ID rename cannot fix these differences.

This draft adds Meteor Lake-P pad groups and offsets, an ACPI matching personality, and a per-community interrupt-status offset with the legacy default preserved. Pin-mux groups/functions are deliberately absent: this draft targets GPIO interrupt handling only. Further controller review, compilation and hardware validation are required.

Integration: start with upstream VoodooGPIO. Replace its VoodooGPIOIntel.hpp, VoodooGPIOIntel.cpp and Info.plist with these versions; add the MeteorLake-P source/header to the Xcode target. Rebuild the whole VoodooGPIO target because its internal community struct changed. Do not mix modified headers with older objects. A Mac with Xcode and matching kernel SDK is needed; none is available in this Windows environment. No executable has been produced or inserted into any EFI.

Before enabling GPIO in the touchscreen SSDT, expose TPL0's initialized SBFB and SBFG via the resource method and remove force-polling. Use firmware INT1/GNUM(T0GI), never an invented pin. The current failure to parse serial-bus resources must also be resolved. Pressure/pen behavior is not verified or promised.

Sources:
- https://github.com/torvalds/linux/blob/master/drivers/pinctrl/intel/pinctrl-meteorlake.c
- https://github.com/VoodooI2C/VoodooGPIO
- https://github.com/VoodooI2C/VoodooI2C/blob/master/Documentation/GPIO%20Pinning.md

Checks completed: exact 289-pad coverage, Linux community ranges and BAR indices, four interrupt-status register uses migrated. No compiler or runtime checks performed.
