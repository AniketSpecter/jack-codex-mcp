# Testing

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build-native.ps1
```

The native build runs `capture_contract.exe` using mocked SDK state (600 entities,
1600 brushes, selection and invalid-chain checks). It does not launch JACK.
The ABI unit test loads the DLL and verifies rejected API/table inputs.
File-only tests skip that ABI test if no DLL is built.

Windows CI builds the plugin and runs automated tests. JACK is proprietary and
not bundled on CI; CI cannot establish real-host rendering/editing compatibility.

## Real-host acceptance tests

Use your own supported editor and a generated disposable fixture. Record editor
hash, plugin hash, operation inputs and outcomes. Do not publish local paths,
private maps, endpoint tokens or session dumps.

1. Read a fresh snapshot; manually select entities/brushes and compare IDs.
2. Create a box, move it, rotate Z 90 degrees, duplicate it; compare actual
   geometric bounds against expected bounds, not only the operation response.
3. Create a point entity, change its targetname and move it; inspect properties.
4. Exercise ordinary editor Undo/Redo for every operation, not just creation.
5. Save As JMF, close/reopen, and compare all changed objects.
6. Reject consumed/stale/expired plans, wrong tokens, different documents,
   modal dialogs, invalid geometry and unsupported fingerprints.
7. Test disconnect/timeout without replay and inspect recovery receipts.
8. Only then consider a separately approved edit on a backed-up real map copy.

## Recorded alpha evidence (2 November 2026)

On J.A.C.K. 1.1.3773 Freeware x64, a disposable eight-brush map passed 24 live
checks covering automatic snapshots, all seven operations, geometric bounds,
consumed-plan rejection and checkpoint creation. Save As/reopen preserved three
entities and ten brushes, including the transformed duplicate and point entity.
Ordinary Ctrl+Z/Ctrl+Y reversed/reapplied brush creation.

These live results predate packaging-only warning changes. They are not a claim
that every fault path or every operation's Undo/Redo has passed. Full transform/
property Undo/Redo coverage, reliable modified-document notification, exact
document-path identity and broader host compatibility remain release gates.
