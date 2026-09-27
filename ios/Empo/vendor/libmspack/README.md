# libmspack (CAB decompression subset)

Vendored from libmspack **v1.11** (https://github.com/kyz/libmspack,
tag `v1.11`), LGPL-2.1 — see `COPYING.LIB`.

Only the files needed to *read* Microsoft Cabinet archives are
included: `cabd.c` (CAB decoder, including `search()` which locates
cabinets embedded inside self-extracting `.exe` stubs), the LZX /
MSZIP / Quantum decompressors, and the shared system layer. The
compressor halves (`*c.c`) and the CHM/HLP/LIT/SZDD/KWAJ/OAB codecs
are intentionally omitted.

Why this exists instead of using libarchive (which the app already
links for zip/7z/rar): libarchive's CAB reader mis-locates the
cabinet inside RPG Maker self-extracting installers (it latches onto
a decoy `MSCF` byte sequence in the PE stub) and, worse, its LZX
decoder fails partway through real-world cabinets that 7-Zip and
libmspack decode fine (verified July 2026 against upstream libarchive
3.8.7). libmspack is the reference implementation used by cabextract
and Wine.

Local modifications:

1. The sources' angled includes of sibling headers
   (`#include <system.h>` etc.) are converted to quoted form so they
   resolve against this directory instead of the project-wide header
   search paths:

   ```sh
   sed -i '' -E 's/# *include <(mspack|system|cab|chm|lzx|lzss|mszip|qtm|macros|readbits|readhuff|crc32)\.h>/#include "\1.h"/' *.c *.h
   ```

2. `system.h` is renamed to `mspack_system.h` (and its includes
   updated). Xcode's target headermap is keyed by basename, so an
   in-target `system.h` would hijack mkxp-z's `#include "system.h"`
   (`src/system/system.h`) in bitmap.cpp / systemImpl.mm.

The sources are also compiled with `-UHAVE_CONFIG_H` (see
`project.yml`) because the project-wide `HAVE_CONFIG_H` define is
meant for mkxp-z and would make libmspack include mkxp-z's config.h.

Consumed by `src/Library/ArchiveExtractor.swift` via the bridging
header. To upgrade: copy the same file list from the new tag, re-run
the sed above, and update the version above.
