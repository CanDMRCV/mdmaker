"""mdmaker CLI — format-agnostic e-book to Markdown converter (BRIEF_FRONTEND).

Usage: mdmaker <eingabe>... -o <ausgabe>/ [-j <n>] [-r] [--dry-run] [--force] [--check]
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .pipeline import convert_batch, check_all_dependencies


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mdmaker",
        description="Convert e-books to clean Markdown. 'pandoc for e-books.'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mdmaker book.epub                        # Single file
  mdmaker books/ -o markdown/              # Whole directory
  mdmaker books/ -j 4 --recursive          # Recursive, 4 workers
  mdmaker books/ --dry-run                 # Preview
  mdmaker --check                          # Verify dependencies
""",
    )
    parser.add_argument("paths", nargs="*", type=Path, help="Files/directories to convert")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("_md_output"),
                        help="Output directory (default: _md_output)")
    parser.add_argument("-j", "--jobs", type=int, default=1,
                        help="Parallel workers (default: 1)")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Recurse into subdirectories")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Re-convert even if .md exists")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without converting")
    parser.add_argument("--check", action="store_true",
                        help="Check dependencies and exit")
    parser.add_argument("-V", "--version", action="version",
                        version=f"mdmaker {__version__}")

    args = parser.parse_args(argv)

    # --check mode
    if args.check:
        print("mdmaker — dependency check\n")
        issues = check_all_dependencies()
        if not issues:
            print("[OK] All converters ready.")
            return 0
        print("[!] Missing dependencies:\n")
        for label, msgs in issues.items():
            print(f"  [{label}]")
            for msg in msgs:
                for line in msg.split("\n"):
                    print(f"    {line}")
            print()
        return 1

    # No paths given
    if not args.paths:
        parser.print_help()
        return 0

    # Convert
    print(f"mdmaker {__version__} — output: {args.output_dir}\n")

    summary = convert_batch(
        args.paths, args.output_dir,
        force=args.force, dry_run=args.dry_run,
        recursive=args.recursive, jobs=args.jobs,
    )

    # Summary (BatchSummary is a dataclass now)
    if args.dry_run:
        print(f"\n[*] Dry run: {summary.total} file(s) would be processed.")
    else:
        print(
            f"\n{'='*50}\n"
            f"  [OK] {summary.ok}  [SKIP] {summary.skipped}  "
            f"[FAIL] {summary.failed}  —  {summary.elapsed_s:.1f}s\n"
            f"{'='*50}"
        )
        # A1: Show failed files with reason
        if summary.failed:
            print("\nFailed files:")
            for fr in summary.results:
                if fr.status == "failed":
                    print(f"  {fr.path.name}  [{fr.converter}]  —  {fr.error}")
        # B6: Show time breakdown
        if summary.converter_times:
            print("\nTime by converter:")
            for label, secs in sorted(summary.converter_times.items(),
                                       key=lambda x: -x[1]):
                print(f"  {label}: {secs:.1f}s")
        if summary.failed:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
