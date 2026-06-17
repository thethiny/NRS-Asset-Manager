# Task List

## UE3 Asset
- [ ] Compression: None  
- [x] Compression: Oodle  
- [x] Compression: ZLIB  
- [x] Packages  
- [x] Extra Packages  
- [x] PSF Data  
- [x] Bulk Data  
- [x] UPK Extra Data  

## Midway Asset
- [x] Compression: Yes  
- [x] Compression: No  

## Data Handlers
- [x] Database (MK11 + IJ2)
- [x] Texture2D (MK11 + IJ2)
- [x] Coalesced / Localization
- [ ] Audio (NRSAudioBank / NRSAudioEvent)
- [ ] SkeletalMesh
- [ ] MaterialInstanceConstant

## MKScript (.mko)
- [x] IJ2 MKO parser (333/333 files)
- [x] MKO JSON dumper
- [ ] MK11 MKO parser (180/243 — function header struct needs RE)
- [ ] MKO disassembler (bytecode → readable instructions)
- [ ] Older games (MKX, IJ1, MK9) MKO support

## VFS / Asset Browser
- [x] VFS mount system (mount/unmount/ls/tree)
- [x] LRU midway buffer cache
- [x] CLI commands (vfs mount/ls/tree)
- [x] DearPyGui browser (folder scan, multi-select, mount, tree view, export details)
- [ ] Export preview (texture preview, JSON view, hex view)
- [ ] Export extraction from browser

## Game Support
- [x] MK11 - Full extraction pipeline
- [x] IJ2 - Full extraction pipeline + TFC textures
- [ ] IJ1 - Not started (DCF codename, version < 0x23E)
- [ ] MK9 - Not started
- [ ] MKX - Not started (MK10 codename, version ~0x240+)
- [ ] MK1 - Not in this repo

## Research / Documentation
- [x] IJ2 decompiled code vs Python comparison (Documentation/task1)
- [x] Version branches for older games (Documentation/task2)
- [x] MKO file format (Documentation/task3)
- [x] TFC bulk data format (Documentation/tfc_bulk_data_research)

## BUGS
- [x] FObjectExport ComponentMap (variable-size handling)
- [x] Texture2D proper bulk data parsing (replaced hardcoded 0x3C skip)
