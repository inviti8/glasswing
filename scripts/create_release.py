#!/usr/bin/env python3
"""
Create version tags and trigger GitHub Actions installer builds.

Usage:
  python scripts/create_release.py v1.0.0     # Create release
  python scripts/create_release.py --list      # Show existing tags
  python scripts/create_release.py --suggest   # Suggest next version
"""

import subprocess
import sys
import re


def get_current_version():
    """Get current version from git tags."""
    try:
        result = subprocess.run(
            ['git', 'tag', '--sort=-version:refname'],
            capture_output=True, text=True, check=True,
        )
        tags = result.stdout.strip().split('\n')
        version_tags = [t for t in tags if t.startswith('v') and re.match(r'^v\d+\.\d+', t)]
        return version_tags[0] if version_tags else None
    except subprocess.CalledProcessError:
        return None


def suggest_next_version(current_version):
    """Suggest next version based on current version."""
    if not current_version:
        return 'v0.1.0'
    match = re.match(r'^v(\d+)\.(\d+)(?:\.(\d+))?$', current_version)
    if not match:
        return 'v0.1.0'
    major, minor = int(match.group(1)), int(match.group(2))
    patch = int(match.group(3)) if match.group(3) else 0
    return f'v{major}.{minor}.{patch + 1}'


def create_tag(version):
    """Create and push a version tag."""
    try:
        print(f'Creating tag: {version}')
        subprocess.run(['git', 'tag', version], check=True)
        print(f'Pushing tag: {version}')
        subprocess.run(['git', 'push', 'origin', version], check=True)
        print(f'Tag {version} created and pushed.')
        print('GitHub Actions installer build will start automatically.')
        return True
    except subprocess.CalledProcessError as e:
        print(f'Error creating tag: {e}')
        return False


def list_recent_tags():
    """List recent version tags."""
    try:
        result = subprocess.run(
            ['git', 'tag', '--sort=-version:refname', '-l', 'v*'],
            capture_output=True, text=True, check=True,
        )
        tags = result.stdout.strip().split('\n')
        if tags and tags[0]:
            print('Recent version tags:')
            for tag in tags[:10]:
                print(f'  {tag}')
        else:
            print('No version tags found')
    except subprocess.CalledProcessError as e:
        print(f'Error listing tags: {e}')


def main():
    if len(sys.argv) < 2:
        print('Usage: python scripts/create_release.py <version>')
        print('       python scripts/create_release.py --suggest')
        print('       python scripts/create_release.py --list')
        print()
        print('Examples:')
        print('  python scripts/create_release.py v0.1.0')
        print('  python scripts/create_release.py v1.0.0')
        sys.exit(1)

    if sys.argv[1] == '--suggest':
        current = get_current_version()
        suggested = suggest_next_version(current)
        print(f'Current version: {current or "None"}')
        print(f'Suggested next:  {suggested}')
        return

    if sys.argv[1] == '--list':
        list_recent_tags()
        return

    version = sys.argv[1]
    if not re.match(r'^v\d+\.\d+(?:\.\d+)?$', version):
        print(f'Invalid version format: {version}')
        print('Expected: v0.1.0, v1.0.0, v2.1.3, etc.')
        sys.exit(1)

    # Check if tag exists
    try:
        result = subprocess.run(
            ['git', 'tag', '-l', version],
            capture_output=True, text=True, check=True,
        )
        if result.stdout.strip():
            print(f'Tag {version} already exists!')
            sys.exit(1)
    except subprocess.CalledProcessError:
        pass

    print(f'About to create tag: {version}')
    print('This will trigger GitHub Actions installer builds for all platforms.')
    response = input('Continue? (y/N): ')
    if response.lower() in ('y', 'yes'):
        create_tag(version)
    else:
        print('Cancelled.')


if __name__ == '__main__':
    main()
