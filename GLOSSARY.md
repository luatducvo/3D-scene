# S3D

S3D ingests preprocessed Scan data to create a Scene and supports question answering
about objects within the Scene.

## Language

**Scan**:
An RGB-D scan from ScanNet, identified by a scan ID; the same room may have multiple Scans.
_Avoid_: recording, capture

**Preprocessing**:
Normalizing data and aligning coordinates of a Scan completely outside the system to produce a Package usable for Import.
_Avoid_: Import, Scene processing

**Package**:
Preprocessed and coordinate-aligned data of a Scan, serving as the sole input unit to Import into a Scene.
_Avoid_: raw package, bundle, archive

**Scene**:
The internal representation of a Scan within the system; each Scan has at most one Scene.
_Avoid_: Scan (when referring to ingested data), Room

**Import**:
Bringing a Package into the system to create or replace a Scene.
_Avoid_: Preprocessing, upload (which is merely the transport mechanism for a Package)
