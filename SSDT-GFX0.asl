DefinitionBlock ("", "SSDT", 2, "CUSTOM", "CoreUltra", 0x00000001)
{
    External (_SB_.PCI0.GFX0, DeviceObj)

    Scope (_SB.PCI0.GFX0)
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
                "device-id", Buffer (0x04) { 0x12, 0x7D, 0x00, 0x00 },
                "model", Buffer () { "Intel Arc Graphics (Meteor Lake)" },
                "AAPL,slot-name", Buffer () { "Internal" },
                "device_type", Buffer () { "VGA compatible controller" }
            })
        }
    }
}
