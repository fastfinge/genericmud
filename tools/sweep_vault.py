"""Headless sweep of the mudsoundpack.com vault: install + activate every supported pack.

The dev host can't run the Windows UI, so this exercises the real install/activation path
end to end without wx: for each catalogue pack genericMud can install (Mush/VIPMud, with a
downloadable archive) it downloads the pack (cached), runs the real ``detect_entry`` +
``setup_pack`` install into a throwaway :class:`PackStore`, then activates it against a
headless :class:`AutomationEngine` and reports the registered trigger/alias/key counts plus
how many of the pack's own ``#play`` references resolve to real files.

A pack that loads with triggers > 0 and resolving sounds is live; triggers == 0, a load
error, or no detectable entry is the signature of a broken pack -- the bug classes this
sweep hunts. Run it after a dialect/loader change to confirm nothing regressed.

    python -m tools.sweep_vault [--client {mush,vipmud,all}] [--limit N] [--max-mb 600]

Run from the repo root (it imports ``genericmud`` off the cwd). Downloads are cached under
``--cache`` (default ``/tmp/gm-vault-cache``) so re-runs are fast.
"""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path

from genericmud.automation.engine import AutomationEngine
from genericmud.packs import git_sources, manifest_sources, vault
from genericmud.packs.loader import activate_world
from genericmud.packs.setup import (
    detect_entry,
    entry_problem,
    setup_pack,
    setup_pack_from_git,
    setup_pack_from_manifest,
)
from genericmud.packs.store import PackStore, extract_pack
from genericmud.scripting.api import ScriptApi
from genericmud.scripting.vipmud_dialect import VipMudPack, _expand_sound_variant

_SWEEP_WORLD = "sweep"  # dummy world to enable each pack for, so activate_world will run it
_DEFAULT_MAX_MB = 600  # skip a download past this; the installer-follow source repos are huge
_PLAY_RE = re.compile(r"#play(?:loop)?\s*\{([^}]*?\.wav)\}", re.IGNORECASE)
_SOUND_SAMPLE = 20  # how many distinct #play references to spot-check for resolution
_DEFERRED_FLOOR = 50  # below this, look for a SoundpackLoader the pack loads on connect


@dataclass
class PackReport:
    name: str
    mud: str
    client: str
    status: str = "?"  # catalogue/install/activation outcome
    entry: str | None = None
    world: str | None = None
    triggers: int = 0
    aliases: int = 0
    keys: int = 0
    sounds_ok: int = 0
    sounds_total: int = 0
    sounds_remote: int = 0
    detail: str = ""


def _cache_path(cache: Path, pack: vault.VaultPack, url: str) -> Path:
    suffix = ".zip" if url.lower().split("?")[0].endswith(".zip") else ".bin"
    return cache / f"{pack.id}-{pack.client.lower()}{suffix}"


def _download(pack: vault.VaultPack, url: str, cache: Path, max_bytes: int) -> Path:
    """Download ``url`` to the cache (skipping if already present). Raises on cap/IO error."""
    dest = _cache_path(cache, pack, url)
    if dest.exists() and dest.stat().st_size > 0:
        if zipfile.is_zipfile(dest):
            return dest
        dest.unlink()  # stale HTML/error response from an earlier sweep
    cache.mkdir(parents=True, exist_ok=True)
    try:
        vault.download(url, dest, max_bytes=max_bytes)
    except BaseException:
        dest.unlink(missing_ok=True)  # never leave a truncated archive to poison re-runs
        raise
    return dest


def _sample_sounds(
    pack_dir: Path,
    api: ScriptApi,
    *,
    scripts: list[Path] | None = None,
    live_pack: object = None,
) -> tuple[int, int, int]:
    """Spot-check that the pack's own ``#play`` references resolve to files that exist."""
    base = str(pack_dir)
    sounds = api.get_var("sppath") or base
    scripts_root = api.get_var("scpath") or base
    refs: list[str] = []
    seen: set[str] = set()
    candidates = scripts if scripts is not None else sorted(pack_dir.rglob("*"))
    for script in candidates:
        if script.suffix.lower() != ".set" or not script.is_file():
            continue
        for raw in _PLAY_RE.findall(script.read_text(encoding="latin-1", errors="ignore")):
            # @sppath/@scpath default to the pack dir; substitute so the check matches runtime.
            ref = (
                _expand_sound_variant(raw)
                .replace("@sppath", sounds)
                .replace("@scpath", scripts_root)
            )
            if "@" in ref or "%" in ref:
                continue  # path built from a runtime/server variable -- not statically checkable
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
        if len(refs) >= _SOUND_SAMPLE:
            break
    refs = refs[:_SOUND_SAMPLE]
    hits = 0
    remote = 0
    can_fetch = getattr(live_pack, "can_fetch_sound", lambda _ref: False)
    for ref in refs:
        if api.sound_exists(ref):
            hits += 1
        elif can_fetch(ref):
            hits += 1
            remote += 1
    return hits, len(refs), remote


def _activate(store: PackStore, pack_id: str) -> tuple[AutomationEngine, dict, object, object]:
    store.enable(pack_id, _SWEEP_WORLD)
    store.trust(pack_id)
    engine = AutomationEngine()
    result = activate_world(store, _SWEEP_WORLD, engine)
    if pack_id in result.failed:
        raise RuntimeError(result.failed[pack_id])
    pack = result.packs.get(pack_id)
    if hasattr(pack, "dispatch_install"):
        pack.dispatch_install()
        pack.dispatch_connect()
    counts = engine.registrations_by_source().get(pack_id, {"trigger": [], "alias": [], "key": []})
    return engine, counts, result, pack


def _deferred_loader_counts(pack_dir: Path) -> dict | None:
    """Measure the deferred-load potential of a pack headlessly.

    Miriani/Prometheus register most of their scripts only on connect, via a
    ``SoundpackLoader.set`` fired from a login trigger + ``#alarm``. The sweep can't see the
    login line, so it loads that loader directly to report what the pack would register live.
    """
    loader = next(
        (p for p in sorted(pack_dir.rglob("*")) if p.name.lower() == "soundpackloader.set"), None
    )
    if loader is None:
        return None
    engine = AutomationEngine()
    api = ScriptApi(engine, source="loader", base_dir=str(pack_dir))
    try:
        VipMudPack(api).load_source(loader.read_text(encoding="latin-1", errors="ignore"))
    except Exception:  # noqa: BLE001 - best-effort measurement, never fail the sweep over it
        return None
    return engine.registrations_by_source().get("loader", {"trigger": [], "alias": [], "key": []})


def _measure(report: PackReport, store: PackStore, result) -> PackReport:
    report.entry = result.manifest.entry
    report.world = f"{result.world.host}:{result.world.port}" if result.world else None
    pack_dir = store.pack_dir(result.manifest.id)
    engine, counts, activation, live_pack = _activate(store, result.manifest.id)
    report.triggers = len(counts["trigger"])
    report.aliases = len(counts["alias"])
    report.keys = len(counts["key"])
    if report.triggers < _DEFERRED_FLOOR:
        deferred = _deferred_loader_counts(pack_dir)
        if deferred and len(deferred["trigger"]) > report.triggers:
            report.triggers = len(deferred["trigger"])
            report.aliases = len(deferred["alias"])
            report.keys = len(deferred["key"])
            report.detail = "loads on connect via SoundpackLoader.set"
    api = ScriptApi(engine, source="sample", base_dir=str(pack_dir))
    sample_scripts = None
    if isinstance(live_pack, VipMudPack):
        sample_scripts = [
            store.entry_path(result.manifest.id),
            *(Path(path) for path in live_pack._loaded),
        ]
        api.set_var("sppath", live_pack._api.get_var("sppath") or str(pack_dir))
    else:
        api.set_var("sppath", str(pack_dir))
    report.sounds_ok, report.sounds_total, report.sounds_remote = _sample_sounds(
        pack_dir, api, scripts=sample_scripts, live_pack=live_pack
    )
    if report.sounds_remote:
        note = f"{report.sounds_remote} checked sounds fetched on demand"
        report.detail = f"{report.detail}; {note}" if report.detail else note
    report.status = "ok" if report.triggers > 0 else "inert"
    skipped_plugins = len(activation.skipped_plugins.get(result.manifest.id, []))
    skipped_rules = len(activation.skipped_rules.get(result.manifest.id, []))
    if skipped_plugins or skipped_rules:
        note = f"compatibility skips: {skipped_plugins} plugins, {skipped_rules} rules"
        report.detail = f"{report.detail}; {note}" if report.detail else note
    plugin_errors = len(activation.plugin_errors.get(result.manifest.id, []))
    script_errors = len(activation.external_script_errors.get(result.manifest.id, []))
    module_errors = len(activation.module_errors.get(result.manifest.id, []))
    if plugin_errors or script_errors or module_errors:
        report.status = "degraded"
        note = (
            f"compatibility errors: {plugin_errors} plugins, {script_errors} scripts, "
            f"{module_errors} modules"
        )
        report.detail = f"{report.detail}; {note}" if report.detail else note
    hook_error_items = getattr(live_pack, "_hook_errors", [])
    hook_errors = len(hook_error_items)
    if hook_errors:
        report.status = "degraded"
        hook, reason = hook_error_items[0]
        first = reason.splitlines()[0]
        note = f"lifecycle errors: {hook_errors}; first {hook}: {first}"
        report.detail = f"{report.detail}; {note}" if report.detail else note
    return report


def _sweep_git_source(pack, source, report, cache: Path, max_bytes: int) -> PackReport:
    cache_file = cache / f"source-{source.id}.zip"

    def fetch(url, dest, **kwargs):
        if cache_file.exists() and not zipfile.is_zipfile(cache_file):
            cache_file.unlink()
        if not cache_file.exists():
            limit = min(int(kwargs.get("max_bytes", max_bytes)), max_bytes)
            vault.download(url, cache_file, max_bytes=limit)
        shutil.copyfile(cache_file, dest)

    try:
        with tempfile.TemporaryDirectory(prefix="gm-sweep-source-") as tmp:
            store = PackStore(Path(tmp) / "store")
            result = setup_pack_from_git(store, source, download=fetch)
            return _measure(report, store, result)
    except vault.DownloadTooLarge as exc:
        report.status = "skipped-large"
        report.detail = str(exc)
    except Exception as exc:  # noqa: BLE001 - one source must not stop the catalogue sweep
        report.status = "load-error"
        report.detail = f"{type(exc).__name__}: {exc}"
    return report


def _sweep_manifest_source(pack, source, report, cache: Path) -> PackReport:
    try:
        store = PackStore(cache / "manifest-store")
        result = setup_pack_from_manifest(store, source)
        return _measure(report, store, result)
    except Exception as exc:  # noqa: BLE001 - one source must not stop the catalogue sweep
        report.status = "load-error"
        report.detail = f"{type(exc).__name__}: {exc}"
        return report


def _sweep_one(pack: vault.VaultPack, cache: Path, max_bytes: int) -> PackReport:
    report = PackReport(name=pack.name, mud=pack.mud, client=pack.client)
    manifest_source = manifest_sources.for_labels(pack.mud, pack.name)
    if manifest_source is not None:
        return _sweep_manifest_source(pack, manifest_source, report, cache)
    git_source = git_sources.for_labels(pack.mud, pack.name)
    if git_source is not None:
        return _sweep_git_source(pack, git_source, report, cache, max_bytes)

    candidates = [item for item in vault.pack_downloads(pack.id) if item.installable]
    if not candidates:
        report.status = "source-unavailable"
        report.detail = "no installable archive (exe/source only)"
        return report
    archive = None
    selected = None
    errors: list[str] = []
    for candidate in candidates:
        try:
            downloaded = _download(pack, candidate.url, cache, max_bytes)
        except vault.DownloadTooLarge as exc:
            report.status = "skipped-large"
            report.detail = str(exc)
            return report
        except Exception as exc:  # noqa: BLE001 - try the next published source
            errors.append(f"{candidate.role}: {type(exc).__name__}: {exc}")
            continue
        if zipfile.is_zipfile(downloaded):
            archive, selected = downloaded, candidate
            break
        errors.append(f"{candidate.role}: response was not a ZIP archive")
    if archive is None:
        report.status = "source-unavailable"
        report.detail = "; ".join(errors)
        return report

    with tempfile.TemporaryDirectory(prefix="gm-sweep-") as tmp:
        extracted = Path(tmp) / "pack"
        try:
            extract_pack(archive, extracted)  # descends nested zips (Miriani: sounds + scripts)
        except zipfile.BadZipFile:
            report.status = "download-error"
            report.detail = "not a zip (site may have served HTML)"
            return report

        entry = detect_entry(extracted, mud_name=pack.mud)
        report.entry = entry
        if entry is None:
            report.status = "no-entry"
            report.detail = entry_problem(extracted)
            return report
        try:
            store = PackStore(Path(tmp) / "store")
            result = setup_pack(store, extracted, entry=entry, origin=selected.url)
            return _measure(report, store, result)
        except Exception as exc:  # noqa: BLE001 - record the failure, keep sweeping
            report.status = "load-error"
            report.detail = f"{type(exc).__name__}: {exc}"
            report.detail += "\n" + "".join(traceback.format_exception(exc))[-800:]
    return report


def _installable(pack: vault.VaultPack, want_client: str) -> bool:
    if not pack.supported:
        return False
    if want_client != "all" and pack.client.strip().lower() != want_client:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep the soundpack vault headlessly.")
    parser.add_argument("--client", choices=("mush", "vipmud", "all"), default="all")
    parser.add_argument("--limit", type=int, default=0, help="stop after N packs (0 = all)")
    parser.add_argument("--max-mb", type=int, default=_DEFAULT_MAX_MB)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/gm-vault-cache"))
    args = parser.parse_args()

    packs = [p for p in vault.list_packs() if _installable(p, args.client)]
    if args.limit:
        packs = packs[: args.limit]
    print(f"sweeping {len(packs)} packs (client={args.client}, max={args.max_mb} MB)\n")

    reports: list[PackReport] = []
    for pack in packs:
        print(f"  ... {pack.mud} ({pack.client})", flush=True)
        reports.append(_sweep_one(pack, args.cache, args.max_mb * 1_000_000))

    print(f"\n{'STATUS':13} {'CLIENT':8} {'TRG':>4} {'ALI':>4} {'KEY':>4} {'SND':>6}  MUD / detail")
    print("-" * 92)
    for r in reports:
        snd = f"{r.sounds_ok}/{r.sounds_total}" if r.sounds_total else "-"
        line = (
            f"{r.status:13} {r.client:8} {r.triggers:>4} {r.aliases:>4} {r.keys:>4} "
            f"{snd:>6}  {r.mud}"
        )
        if r.detail:
            line += f"  | {r.detail.splitlines()[0]}"
        print(line)

    ok = sum(1 for r in reports if r.status == "ok")
    print(f"\n{ok}/{len(reports)} live (triggers > 0). "
          f"non-ok: {sorted({r.status for r in reports if r.status != 'ok'})}")


if __name__ == "__main__":
    main()
