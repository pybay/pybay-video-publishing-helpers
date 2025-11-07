#!/usr/bin/env python3
"""
PyBay Talk List Scraper

Scrapes talk information from PyBay website and outputs to CSV.
Extracts: room, start_time, talk_title, description, firstname, lastname
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup


def parse_speaker_name(speaker_text: str) -> tuple[str, str]:
    """
    Parse speaker name into first and last name.

    Args:
        speaker_text: Full name string (e.g., "Chris Brousseau")

    Returns:
        Tuple of (firstname, lastname)
    """
    parts = speaker_text.strip().split()
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        # First name is first part, last name is everything else
        firstname = parts[0]
        lastname = " ".join(parts[1:])
        return firstname, lastname


def parse_time(time_text: str) -> str:
    """
    Parse time string and extract start time.

    Examples:
        "Sat 10:00 am - 10:25 am" -> "10:00 am"
        "10:00 am - 10:25 am" -> "10:00 am"

    Args:
        time_text: Time range string

    Returns:
        Start time string
    """
    # Remove day prefix if present
    time_text = time_text.strip()

    # Split on " - " to get start time
    if " - " in time_text:
        start_part = time_text.split(" - ")[0].strip()

        # Remove day prefix (e.g., "Sat ")
        parts = start_part.split()
        if len(parts) >= 3:  # e.g., ["Sat", "10:00", "am"]
            return " ".join(parts[1:])  # "10:00 am"
        else:
            return start_part

    return time_text


def scrape_pybay_talks(url: str) -> List[Dict[str, str]]:
    """
    Scrape talk information from PyBay website.

    Args:
        url: URL to scrape (e.g., https://pybay.org/speaking/talk-list-2025/)

    Returns:
        List of talk dictionaries with keys:
            room, start_time, talk_title, description, firstname, lastname
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Extract the Sessionize API URL from the page
    print(f"Fetching {url}...", file=sys.stderr)
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')

    # Look for Sessionize API endpoint in page source
    page_text = response.text
    if 'sessionize.com/api' in page_text:
        import re
        match = re.search(r'(https://sessionize\.com/api/v2/[^/]+/view/Sessions)', page_text)
        if match:
            api_url = match.group(1) + '?under=True'
            print(f"Found Sessionize API: {api_url}", file=sys.stderr)

            # Fetch rendered HTML from Sessionize API
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

    # Find all session list items
    sessions = soup.find_all('li', class_='sz-session')

    if not sessions:
        print(f"[WARNING] No sessions found on page. Check if the page structure has changed.", file=sys.stderr)
        return []

    print(f"Found {len(sessions)} sessions", file=sys.stderr)

    talks = []

    for session in sessions:
        # Extract session ID from id attribute (e.g., "sz-session-1058159")
        session_id = session.get('id', '').replace('sz-session-', '') if session.get('id') else ""

        # Extract speaker names (handle multiple speakers)
        speakers = []
        speaker_list_elem = session.find('ul', class_='sz-session__speakers')
        if speaker_list_elem:
            speaker_items = speaker_list_elem.find_all('li')
            for speaker_li in speaker_items:
                speaker_span = speaker_li.find('span')
                if speaker_span:
                    speaker_name = speaker_span.get_text(strip=True)
                    firstname, lastname = parse_speaker_name(speaker_name)
                    speakers.append({
                        'firstname': firstname,
                        'lastname': lastname
                    })

        # Extract talk title
        title_elem = session.find('h3', class_='sz-session__title')
        talk_title = title_elem.get_text(strip=True) if title_elem else ""

        # Extract description
        desc_elem = session.find('p', class_='sz-session__description')
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Extract room
        room_elem = session.find('div', class_='sz-session__room')
        room = room_elem.get_text(strip=True) if room_elem else ""

        # Extract time
        time_elem = session.find('div', class_='sz-session__time')
        time_text = time_elem.get_text(strip=True) if time_elem else ""
        start_time = parse_time(time_text)

        talks.append({
            'room': room,
            'start_time': start_time,
            'talk_title': talk_title,
            'description': description,
            'speakers': speakers,
            'id': session_id
        })

    return talks


def write_output(talks: List[Dict[str, str]], output_path: Path, format: str = 'csv') -> None:
    """
    Write talks to output file.

    Args:
        talks: List of talk dictionaries
        output_path: Path to output file
        format: Output format ('csv' or 'json')
    """
    if not talks:
        print("[ERROR] No talks to write", file=sys.stderr)
        return

    if format == 'json':
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(talks, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Wrote {len(talks)} talks to {output_path} (JSON)", file=sys.stderr)
    else:  # csv
        # Flatten speakers array for CSV output
        fieldnames = ['room', 'start_time', 'talk_title', 'description', 'speakers', 'id']
        flattened_talks = []
        for talk in talks:
            # Join speakers with " & "
            speaker_names = []
            for speaker in talk.get('speakers', []):
                firstname = speaker.get('firstname', '')
                lastname = speaker.get('lastname', '')
                if firstname and lastname:
                    speaker_names.append(f"{firstname} {lastname}")
                elif firstname:
                    speaker_names.append(firstname)
                elif lastname:
                    speaker_names.append(lastname)

            flattened_talk = {
                'room': talk['room'],
                'start_time': talk['start_time'],
                'talk_title': talk['talk_title'],
                'description': talk['description'],
                'speakers': ' & '.join(speaker_names),
                'id': talk['id']
            }
            flattened_talks.append(flattened_talk)

        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flattened_talks)
        print(f"\n[OK] Wrote {len(talks)} talks to {output_path} (CSV)", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Scrape PyBay talk list and output to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default URL (2025)
  python src/scraper_pybayorg_talk_metadata.py --output pybay_2025_talks.csv

  # Specify custom URL
  python src/scraper_pybayorg_talk_metadata.py --url https://pybay.org/speaking/talk-list-2024/ --output talks.csv

  # Output to stdout
  python src/scraper_pybayorg_talk_metadata.py --output -
        """
    )

    parser.add_argument(
        '--url',
        type=str,
        default='https://pybay.org/speaking/talk-list-2025/',
        help='URL to scrape (default: https://pybay.org/speaking/talk-list-2025/)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default='pybay_videos_destination/_pybay_2025_talk_data.json',
        help='Output file path (default: pybay_videos_destination/_pybay_2025_talk_data.json, use "-" for stdout)'
    )

    parser.add_argument(
        '--format', '-f',
        type=str,
        choices=['csv', 'json'],
        default='json',
        help='Output format: csv or json (default: json)'
    )

    args = parser.parse_args()

    try:
        # Scrape talks
        talks = scrape_pybay_talks(args.url)

        if not talks:
            print("[ERROR] No talks found. The page may be empty or the structure may have changed.", file=sys.stderr)
            sys.exit(1)

        # Write output
        if args.output == '-':
            # Write to stdout
            if args.format == 'json':
                json.dump(talks, sys.stdout, indent=2, ensure_ascii=False)
            else:
                writer = csv.DictWriter(sys.stdout, fieldnames=['room', 'start_time', 'talk_title', 'description', 'firstname', 'lastname', 'id'])
                writer.writeheader()
                writer.writerows(talks)
        else:
            output_path = Path(args.output).expanduser()
            write_output(talks, output_path, args.format)

            # Print summary
            print(f"\nSummary:")
            print(f"  Total talks: {len(talks)}")
            print(f"  Rooms: {len(set(t['room'] for t in talks if t['room']))}")

            # Count unique speakers from speakers array
            speaker_names = set()
            for talk in talks:
                for speaker in talk.get('speakers', []):
                    firstname = speaker.get('firstname', '')
                    lastname = speaker.get('lastname', '')
                    if firstname or lastname:
                        speaker_names.add(f"{firstname} {lastname}".strip())
            print(f"  Speakers: {len(speaker_names)}")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch URL: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
