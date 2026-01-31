#!/usr/bin/env python3
"""
Migration script for hvym_stellar v0.19 breaking changes.

Breaking changes in v0.19:
1. Parameter renames (no backward compatibility):
   - recieverPub -> receiverPub
   - recieverKeyPair -> receiverKeyPair
   - reciever_kp -> receiver_kp (variable naming convention)

2. decrypt() now requires from_address parameter:
   - Old: decryptor.decrypt(ciphertext)
   - New: decryptor.decrypt(ciphertext, from_address=sender_address)

Usage:
    python migrate_to_v019.py [--dry-run] [--verbose] <file_or_directory>

Examples:
    python migrate_to_v019.py --dry-run crypto_test/
    python migrate_to_v019.py crypto_test/HvymStellarTokenHarness.py
    python migrate_to_v019.py .
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional


# Spelling fixes (simple replacements)
SPELLING_FIXES = [
    (r'\brecieverPub\b', 'receiverPub'),
    (r'\brecieverKeyPair\b', 'receiverKeyPair'),
    (r'\breciever_kp\b', 'receiver_kp'),
    (r'\breciever_stellar_kp\b', 'receiver_stellar_kp'),
    (r'\breciever\b(?![\w])', 'receiver'),  # Standalone 'reciever' not followed by word char
]

# Patterns to identify decrypt calls that need from_address
# These are StellarSharedDecryption.decrypt() calls, not other decrypt methods
DECRYPT_VAR_NAMES = [
    'shared_decrypt', 'sharedDecrypt', 'decryptor', 'receiver_key',
    'decrypt_key', 'receiver_decrypt', 'receiver_decrypt_key',
    'bad_decryptor', 'decryptor1', 'decryptor2', 'shared_decryption'
]

# Known sender variable patterns to help identify from_address
SENDER_PATTERNS = [
    (r'sender_stellar_kp', 'sender_stellar_kp.public_key'),
    (r'sender_kp', 'sender_kp.base_stellar_keypair().public_key'),
    (r'self\.sender_stellar', 'self.sender_stellar.public_key'),
    (r'self\.sender', 'self.sender.base_stellar_keypair().public_key'),
]


def find_sender_address(content: str, line_num: int) -> Optional[str]:
    """
    Try to find the sender address variable based on context.
    Looks for common patterns in the file.
    """
    lines = content.split('\n')

    # Look backwards from the current line for sender variable definitions
    search_start = max(0, line_num - 50)
    search_region = '\n'.join(lines[search_start:line_num])

    # Check for common sender patterns
    for pattern, replacement in SENDER_PATTERNS:
        if re.search(pattern, search_region):
            return replacement

    # Check the whole file for sender patterns
    for pattern, replacement in SENDER_PATTERNS:
        if re.search(pattern, content):
            return replacement

    return None


def migrate_spelling(content: str) -> Tuple[str, List[str]]:
    """Apply spelling fixes to content."""
    changes = []

    for pattern, replacement in SPELLING_FIXES:
        matches = list(re.finditer(pattern, content))
        if matches:
            changes.append(f"  - '{pattern}' -> '{replacement}' ({len(matches)} occurrences)")
            content = re.sub(pattern, replacement, content)

    return content, changes


def migrate_decrypt_calls(content: str, filepath: str) -> Tuple[str, List[str]]:
    """
    Migrate decrypt() calls to include from_address parameter.

    This is complex because we need to:
    1. Identify StellarSharedDecryption.decrypt() calls (not other decrypt methods)
    2. Determine the appropriate sender address variable
    3. Add the from_address parameter
    """
    changes = []
    lines = content.split('\n')
    modified_lines = []

    for i, line in enumerate(lines):
        modified = False

        # Skip if already has from_address
        if 'from_address' in line:
            modified_lines.append(line)
            continue

        # Skip asymmetric_decrypt calls
        if 'asymmetric_decrypt' in line:
            modified_lines.append(line)
            continue

        # Check for each known decrypt variable name
        for var_name in DECRYPT_VAR_NAMES:
            # Look for var_name.decrypt( and then find matching closing paren
            decrypt_start = f'{var_name}.decrypt('
            idx = line.find(decrypt_start)

            if idx == -1:
                continue

            # Find the matching closing parenthesis
            start_paren = idx + len(decrypt_start)
            paren_count = 1
            end_paren = start_paren

            for j, char in enumerate(line[start_paren:], start_paren):
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        end_paren = j
                        break

            if paren_count != 0:
                continue  # Unbalanced parentheses, skip

            arg = line[start_paren:end_paren]
            full_match = line[idx:end_paren + 1]

            # Try to find sender address
            sender_addr = find_sender_address(content, i)

            if sender_addr:
                # Replace the decrypt call
                new_call = f'{var_name}.decrypt({arg}, from_address={sender_addr})'
                line = line.replace(full_match, new_call)
                modified = True
                changes.append(f"  - Line {i+1}: Added from_address={sender_addr}")
            else:
                # Mark for manual review
                changes.append(f"  - Line {i+1}: MANUAL REVIEW NEEDED - decrypt() call needs from_address")
                # Add a comment to help
                if '# TODO' not in line and '#' not in line.split('.decrypt')[0]:
                    line = line.rstrip() + '  # TODO: Add from_address=sender_address'
                    modified = True

            break  # Only process one match per line

        modified_lines.append(line)

    return '\n'.join(modified_lines), changes


def migrate_file(filepath: Path, dry_run: bool = False, verbose: bool = False) -> Tuple[bool, List[str]]:
    """Migrate a single file."""
    all_changes = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        return False, [f"Error reading file: {e}"]

    content = original_content

    # Apply spelling fixes
    content, spelling_changes = migrate_spelling(content)
    if spelling_changes:
        all_changes.append("Spelling fixes:")
        all_changes.extend(spelling_changes)

    # Apply decrypt migration
    content, decrypt_changes = migrate_decrypt_calls(content, str(filepath))
    if decrypt_changes:
        all_changes.append("Decrypt call updates:")
        all_changes.extend(decrypt_changes)

    # Check if anything changed
    if content == original_content:
        return False, ["No changes needed"]

    # Write changes (unless dry run)
    if not dry_run:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return False, [f"Error writing file: {e}"]

    return True, all_changes


def find_python_files(path: Path) -> List[Path]:
    """Find all Python files in a path."""
    if path.is_file():
        if path.suffix == '.py':
            return [path]
        return []

    files = []
    for root, dirs, filenames in os.walk(path):
        # Skip common non-source directories
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.venv', 'venv', 'node_modules'}]

        for filename in filenames:
            if filename.endswith('.py'):
                files.append(Path(root) / filename)

    return files


def main():
    parser = argparse.ArgumentParser(
        description='Migrate code to hvym_stellar v0.19',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('path', help='File or directory to migrate')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be changed without modifying files')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed output')

    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path '{path}' does not exist")
        sys.exit(1)

    files = find_python_files(path)
    if not files:
        print(f"No Python files found in '{path}'")
        sys.exit(0)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Migrating {len(files)} file(s)...")
    print()

    total_changed = 0
    manual_review_needed = []

    for filepath in files:
        changed, changes = migrate_file(filepath, args.dry_run, args.verbose)

        if changed or args.verbose:
            print(f"{'[WOULD CHANGE]' if args.dry_run else '[CHANGED]'} {filepath}")
            for change in changes:
                print(f"  {change}")
            print()

        if changed:
            total_changed += 1

        # Check for manual review items
        for change in changes:
            if 'MANUAL REVIEW' in change:
                manual_review_needed.append((filepath, change))

    print(f"{'Would modify' if args.dry_run else 'Modified'} {total_changed} of {len(files)} files")

    if manual_review_needed:
        print()
        print("=" * 60)
        print("MANUAL REVIEW REQUIRED:")
        print("The following decrypt() calls need manual addition of from_address:")
        print()
        for filepath, change in manual_review_needed:
            print(f"  {filepath}:")
            print(f"    {change}")
        print()
        print("You need to identify the sender's Stellar public key and add:")
        print("  .decrypt(ciphertext, from_address=sender_stellar_keypair.public_key)")
        print()


if __name__ == '__main__':
    main()
