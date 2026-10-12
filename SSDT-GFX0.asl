DefinitionBlock ("", "SSDT", 2, "CUSTOM", "CoreUtra", 0x00000001)
{
    // Namespace measured in the supplied Linux report. Still not deployable:
    // inspect the original DSDT for an existing _DSM and EFI rename patches first.
    External (_SB_.PC00.GFX0, DeviceObj)

    Scope (_SB.PC00.GFX0)
    {
        Method (_DSM, 4, NotSerialized)
        {
            If (!Arg2)
            {
                Return (Buffer (One) { 0x03 })
            }

            Return (Package ()
            {
                "vendor-id", Buffer (0x04) { 0x86, 0x80, 0x00, 0x00 },
                "device-id", Buffer (0x04) { 0x45, 0x7D, 0x00, 0x00 },
                "model", Buffer () { "Intel Arc Graphics (Meteor Lake)" },
                "AAPL,slot-name", Buffer () { "Internal" },
                "device_type", Buffer () { "VGA compatible controller" }
            })
        }
    }
}
