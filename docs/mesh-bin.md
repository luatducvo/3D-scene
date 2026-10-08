# mesh.bin version 1

Little-endian binary file, with no padding between sections:

| Offset | Data |
| --- | --- |
| 0 | ASCII magic `S3DM` |
| 4 | `uint32` version = 1 |
| 8 | `uint32` vertex count `N` |
| 12 | `uint32` index count `M` |
| 16 | `N × 3` `float32` aligned XYZ, in original mesh vertex order |
| next | `N × 3` `uint8` RGB colors |
| next | `M` `uint32` triangle indices |
| next | `N` `int32` Instance IDs; `-1` means no Instance |

No geometry compression is applied, because client/server Instance masks refer to the
original vertex order.
