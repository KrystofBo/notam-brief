# Pre-filter timing

Snapshot `2026-09-22`: 945 NOTAMs (NL + DE). 300 runs per route. CPython 3.9.13 on Windows AMD64 (Intel64 Family 6 Model 158 Stepping 10, GenuineIntel).

Parsing both bulletin HTML files (done once per bulletin refresh, then cached): median 50.1 ms, p95 56.6 ms.

| Route | NOTAMs scanned | Kept | Median | p95 | Per NOTAM |
|---|---|---|---|---|---|
| 1 EHLE Lelystad - EHHV Hilversum | 945 | 25 | 4.45 ms | 8.73 ms | 4.7 µs |
| 2 EHTE Teuge - EHHO Hoogeveen | 945 | 17 | 4.44 ms | 8.58 ms | 4.7 µs |
| 3 EHRD Rotterdam - EHTX Texel | 945 | 59 | 11.24 ms | 19.53 ms | 11.9 µs |
| 4 EHTW Twente - EDDG Muenster-Osnabrueck | 945 | 24 | 4.84 ms | 10.87 ms | 5.1 µs |
| 5 EHGG Groningen - EDWE Emden | 945 | 23 | 4.44 ms | 8.82 ms | 4.7 µs |
