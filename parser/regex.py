"""Regex-based resource extraction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import re
from pathlib import Path
import config


def extract_resources(text: str) -> dict:
    """Detect resources using regular expressions."""
    resources = {
        "urls": set(),
        "github_repos": set(),
        "emails": set(),
        "instagram_handles": set(),
        "twitter_handles": set(),
        "youtube_links": set(),
        "discord_links": set(),
        "hashtags": set(),
        "phone_numbers": set(),
    }
    # URLs
    for match in re.finditer(config.URL_PATTERN, text):
        url = match.group(0)
        resources["urls"].add(url)
    # GitHub repos
    for match in re.finditer(config.GITHUB_REPO, text):
        resources["github_repos"].add(match.group(0))
    # Emails
    for match in re.finditer(config.EMAIL_PATTERN, text):
        resources["emails"].add(match.group(0))
    # Instagram handles
    for match in re.finditer(config.INSTAGRAM_HANDLE, text):
        resources["instagram_handles"].add(match.group(1) if match.group(1) else match.group(0))
    # Twitter handles
    for match in re.finditer(config.TWITTER_HANDLE, text):
        handle = match.group(1) or match.group(2)
        if handle:
            resources["twitter_handles"].add(handle)
    # YouTube links
    for match in re.finditer(config.YOUTUBE_LINK, text):
        resources["youtube_links"].add(match.group(0))
    # Discord links
    for match in re.finditer(config.DISCORD_LINK, text):
        resources["discord_links"].add(match.group(0))
    # Hashtags
    for match in re.finditer(config.HASHTAG, text):
        resources["hashtags"].add(match.group(0))
    # Phone numbers
    for match in re.finditer(config.PHONE_NUMBER, text):
        resources["phone_numbers"].add(match.group(0))
    # Convert sets to sorted lists
    for key in resources:
        resources[key] = sorted(resources[key])
    return resources
