# Unofficial PPT process-retention fix

This fork is maintained by YU322142 for a small PPT cleanup fix. Inkeys and its original work remain credited to [Alan-CRL/Inkeys](https://github.com/Alan-CRL/Inkeys). This is not an official release.

## Base and change

Base: upstream Canary `86bf8645b0e29bb84aca44d496eb27f80f44a7d8` (20261109a).

When reading `ActivePresentation` throws a supported busy error, the original code exits the inner handler before checking independent `Presentations.Count` evidence. This can retain the binding even when the document count is zero. The fix allows that existing zero-count confirmation to run. Disconnected objects keep their existing fast path; a positive or unreadable count retains the recoverable binding and the original exception handling.

Cleanup still runs on the existing service owner, through its existing finally, including event unsubscription and owned COM releases. No public COM ABI change, forced Office quit, GC cleanup or FinalRelease was introduced.

## Evidence

- Added regressions failed in four places before the fix and passed after it with the full managed suite.
- Coverage includes three supported busy HRESULTs, no documents, a live/cancelled-close document, unavailable counts, recovery, and service/event cleanup without setting the Inkeys stop signal.
- Before/after TLBs exported with the same local tool were byte-identical. Public COM method order, signatures, GUIDs and CLSID match the DLL embedded in the official EXE.
- Packaged native resource verification test exited 0.
- The reporter confirmed on 2026-11-13 that the original process-retention symptom was resolved on Office 2024 LTSC after running the test launcher.

The exact original failure HRESULT was not independently captured. User acceptance establishes the reported symptom was resolved; it does not prove every possible reference-retention path or every Office/WPS environment has been covered.

## Binary provenance and limits

The x64 test executable is a **copy of the official 20261109a executable with its embedded PptCOM DLL resource replaced**. It is not a complete native rebuild. Its invalidated Authenticode signature was explicitly removed, so the binary is **unsigned**. The official input was left unchanged.

The required Debug x64 solution build was attempted but blocked by missing C++ targets (MSB4019) and .NET Framework 4 reference assemblies (MSB3644). Native dispatch fixture tests were not run. These limitations are retained in the release notes.

The runtime ZIP is the exact tested artifact. Its internal validation files describe the earlier pre-user-test state; the release notes and separate validation receipt provide the later user confirmation. Raw user-session logs are not release assets.

## Reproducing the managed build

Use `tools/ppt-close-fix/Build-Managed.ps1` with a modern .NET SDK compiler, the .NET Framework 4 runtime/reference files and Office interop assemblies installed locally. It builds the library and the complete managed test executable into a separate output directory and runs the suite. It does not overwrite the tracked binary resources.

For a full native build follow the upstream solution and dependency instructions. Synchronize the same-build DLL/TLB into `Inkeys/` before building the native executable. `tools/ppt-close-fix/Embed-PptFix.py` documents the alternative used for this test package: replace the DLL resource in a new EXE copy and explicitly remove the invalidated signature.

The repository retains its upstream LICENSE and NOTICE. A complete corresponding source archive is provided with this release.
