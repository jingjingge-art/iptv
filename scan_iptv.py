#!/usr/bin/env python3
"""Fetch public IPTV playlists and export channels into four categorized TXT files."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SOURCES = (
    ("综合源", "https://raw.githubusercontent.com/best-fan/iptv-sources/refs/heads/main/cn_all_status.m3u8"),
    ("综合源", "https://kakaxi.indevs.in/iptv.txt"),
    ("IPv4源", "https://kakaxi.indevs.in/ipv4.txt"),
    ("联通线路", "https://raw.githubusercontent.com/Supprise0901/TVBox_live/refs/heads/main/live.txt"),
    ("虎牙一起看", "https://sub.ottiptv.cc/huyayqk.m3u"),
    ("斗鱼一起看", "https://sub.ottiptv.cc/douyuyqk.m3u"),
    ("B站直播", "https://sub.ottiptv.cc/bililive.m3u"),
    ("YY轮播", "https://sub.ottiptv.cc/yylunbo.m3u"),
)

OUTPUTS = {
    "央视卫视地方直播": "央视卫视地方直播.txt",
    "影视线路": "影视线路.txt",
    "港澳台地区源": "港澳台地区源.txt",
    "其他": "其他.txt",
}
ALL_OUTPUT = "iptv_all.txt"
MAX_SOURCE_BYTES = 32 * 1024 * 1024
REQUEST_TIMEOUT = 30

PATTERNS = {
    "港澳台地区源": re.compile(
        r"港澳台|香港|澳门|澳門|台湾|臺灣|台灣|凤凰|鳳凰|TVB|翡翠台|明珠台|Jade|Pearl|"
        r"HOY|ViuTV|Now\s?TV|澳视|澳視|中天|民视|民視|华视|華視|东森|東森|三立|TVBS|Hami",
        re.IGNORECASE,
    ),
    "影视线路": re.compile(
        r"电影|影视频道|影视|剧场|戲劇|戏剧|影院|电视剧|紀錄片|纪录片|动作片|院线|"
        r"CHC|HBO|CINEMAX|电影频道|電影|Movie|Movies|Film|Cinema|Drama|STAR\s?MOVIES|动作电影|动作影院",
        re.IGNORECASE,
    ),
    "央视卫视地方直播": re.compile(
        r"(^|[^A-Z])CCTV\s?[-_]?[1-17](?:\s|$|[-_])|央视|中央电视台|中央臺|"
        r"卫视|衛視|地方台|省级|市级|新闻综合|新聞綜合|综合频道|綜合頻道|"
        r"北京台|上海台|东方卫视|東方衛視|江苏台|浙江台|湖南台|广东台|廣東台|"
        r"深圳台|山东台|山東台|安徽台|福建台|江西台|四川台|重庆台|重慶台|"
        r"天津台|河北台|河南台|湖北台|广西台|廣西台|云南台|雲南台|贵州台|貴州台|"
        r"辽宁台|遼寧台|吉林台|黑龙江台|黑龍江台|陕西台|陝西台|甘肃台|甘肅台|"
        r"青海台|宁夏台|新疆台|内蒙古台|內蒙古台|海南台|厦门台|廈門台|大连台|大連台",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class Channel:
    name: str
    url: str
    group: str = ""


def decode_source(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def fetch_source(label: str, url: str) -> str:
    request = Request(url, headers={"User-Agent": "iptv-list-builder/1.0"})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        data = response.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    text = decode_source(data)
    print(f"Fetched {label}: {len(data)} bytes from {url}")
    return text


def is_stream_url(value: str) -> bool:
    return bool(re.match(r"^(?:https?|rtmp|rtsp|udp|p3p|tvbus)://", value, re.IGNORECASE))


def parse_playlist(text: str, source_label: str) -> list[Channel]:
    channels: list[Channel] = []
    pending_name = ""
    pending_group = ""

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        if line.startswith("#EXTINF"):
            pending_group = ""
            group_match = re.search(r'group-title=["\']([^"\']+)', line, re.IGNORECASE)
            if group_match:
                pending_group = group_match.group(1).strip()
            title = line.rsplit(",", 1)[-1].strip() if "," in line else ""
            name_match = re.search(r'tvg-name=["\']([^"\']+)', line, re.IGNORECASE)
            pending_name = (name_match.group(1).strip() if name_match else title) or source_label
            continue
        if line.startswith("#"):
            if ",#genre#" in line.lower():
                pending_group = line.split(",", 1)[0].strip()
            continue

        if is_stream_url(line):
            channels.append(Channel(pending_name or source_label, line, pending_group))
            pending_name = ""
            continue

        if "," in line:
            name, candidate_url = line.split(",", 1)
            name, candidate_url = name.strip(), candidate_url.strip()
            if is_stream_url(candidate_url):
                channels.append(Channel(name or source_label, candidate_url, pending_group))
                pending_name = ""

    return channels


def classify(channel: Channel) -> str:
    searchable = f"{channel.name} {channel.group}"
    for category, pattern in PATTERNS.items():
        if pattern.search(searchable):
            return category
    return "其他"


def render(channels: Iterable[Channel]) -> str:
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for channel in channels:
        key = (channel.name.casefold(), channel.url)
        if key in seen:
            continue
        seen.add(key)
        name = channel.name.replace("\r", " ").replace("\n", " ").replace(",", " ").strip()
        lines.append(f"{name or '未命名频道'},{channel.url}")
    return "\n".join(lines) + ("\n" if lines else "")


def main() -> int:
    grouped: dict[str, list[Channel]] = {category: [] for category in OUTPUTS}
    successful_sources = 0

    for label, url in SOURCES:
        try:
            text = fetch_source(label, url)
            entries = parse_playlist(text, label)
            successful_sources += 1
            for channel in entries:
                grouped[classify(channel)].append(channel)
            print(f"  parsed {len(entries)} channels")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            print(f"WARNING: failed to read {label} ({url}): {error}", file=sys.stderr)
        time.sleep(0.2)

    if successful_sources == 0:
        print("ERROR: all playlist sources failed; keeping existing output files.", file=sys.stderr)
        return 1

    for category, path in OUTPUTS.items():
        content = render(grouped[category])
        with open(path, "w", encoding="utf-8", newline="\n") as output:
            output.write(f"{category},#genre#\n")
            output.write(content)
        unique_count = sum(1 for line in content.splitlines() if "," in line)
        print(f"Wrote {path}: {unique_count} channels")

    with open(ALL_OUTPUT, "w", encoding="utf-8", newline="\n") as output:
        for category, _path in OUTPUTS.items():
            output.write(f"{category},#genre#\n")
            output.write(render(grouped[category]))
            output.write("\n")
    print(f"Updated {ALL_OUTPUT}; {successful_sources}/{len(SOURCES)} sources fetched successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
