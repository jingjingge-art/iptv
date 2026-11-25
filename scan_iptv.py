#!/usr/bin/env python3
"""Fetch public IPTV playlists and export categorized channel lists."""

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
    ("新增直播源", "https://live.yang-1989.eu.org/Live.m3u"),
    ("联通线路", "https://supprise0901.github.io/TVBox_live/live.txt"),
    ("综合直播源1", "https://raw.githubusercontent.com/wnhhh/iptv-list/refs/heads/main/iptv.txt"),
    ("组播汇总源", "https://raw.githubusercontent.com/adminouyang/231006/refs/heads/main/py/udpxy/output/all.txt"),
    ("大陆频道源", "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u"),
    ("香港频道源", "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/hk.m3u"),
    ("台湾频道源", "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/tw.m3u"),
    ("综合直播源2", "https://raw.githubusercontent.com/ly36143614-byte/iptv-pub/refs/heads/main/tv.m3u"),
    ("优选直播源1", "https://raw.githubusercontent.com/zilong7728/Collect-IPTV/refs/heads/main/best_sorted.m3u8"),
    ("ITV直播源", "https://raw.githubusercontent.com/zzgpy1/ITV/refs/heads/main/output/tv.txt"),
    ("Gitee直播源", "https://gitee.com/hw2837/iptv/raw/master/iptv"),
    ("免费电视源", "https://raw.githubusercontent.com/adminouyang/jy/refs/heads/main/freetv/freetv.txt"),
    ("酒店直播源1", "https://raw.githubusercontent.com/adminouyang/jy/refs/heads/main/Hotel/IPTV.txt"),
    ("IPv4直播源", "https://raw.githubusercontent.com/adminouyang/TV/refs/heads/master/output/ipv4/result.txt"),
    ("酒店直播源2", "https://raw.githubusercontent.com/adminouyang/jy/refs/heads/main/Hotel/HSMDTV/hsmd.m3u8"),
    ("优选直播源2", "https://raw.githubusercontent.com/yanghanhanyingshi/GYYS/refs/heads/main/best_sorted.m3u"),
    ("CDN直播源", "https://cdn.qd.je/live.m3u"),
    ("电视直播30", "https://cnb.cool/fgvss/dszb1/-/git/raw/main/zbtv30.txt"),
    ("MyTV直播源", "https://raw.githubusercontent.com/qingtian6325-lang/IPTV/main/mytv.m3u"),
    ("上海电信组播", "https://raw.githubusercontent.com/adminouyang/231006/refs/heads/main/py/udpxy/output/%E4%B8%8A%E6%B5%B7%E7%94%B5%E4%BF%A1.txt"),
    ("江苏电信组播", "https://raw.githubusercontent.com/adminouyang/231006/refs/heads/main/py/udpxy/output/%E6%B1%9F%E8%8B%8F%E7%94%B5%E4%BF%A1.txt"),

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

# CCTV is deliberately classified before film/region keywords: every entry
# whose channel name or M3U group identifies it as a CCTV/央视 channel belongs
# in the live TV output, including CCTV-6, CCTV-5+, CCTV4K and CCTV specialty channels.
CCTV_PATTERN = re.compile(r"CCTV|央视|中央电视台|中央臺", re.IGNORECASE)
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
    """Handle common playlist encodings, including UTF-8 BOM and GB18030."""
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
    # rtp is used by some text playlists; pipe parameters and query strings are
    # intentionally left intact because players may need them.
    return bool(re.match(r"^(?:https?|rtmp|rtsp|rtp|udp|p3p|tvbus)://", value, re.IGNORECASE))


def parse_playlist(text: str, source_label: str) -> list[Channel]:
    """Parse M3U/M3U8 and TVBox-style text (name,URL) playlists."""
    channels: list[Channel] = []
    pending_name = ""
    current_group = ""

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue

        # TVBox text playlists mark sections as "group name,#genre#".
        if ",#genre#" in line.lower():
            current_group = line.split(",", 1)[0].strip()
            pending_name = ""
            continue

        if line.startswith("#EXTINF"):
            group_match = re.search(r'group-title=["\']([^"\']+)', line, re.IGNORECASE)
            group = group_match.group(1).strip() if group_match else current_group
            title = line.rsplit(",", 1)[-1].strip() if "," in line else ""
            name_match = re.search(r'tvg-name=["\']([^"\']+)', line, re.IGNORECASE)
            pending_name = (name_match.group(1).strip() if name_match else title) or source_label
            current_group = group
            continue

        if line.startswith("#"):
            # Skip M3U headers/options while retaining the pending EXTINF title.
            continue

        if is_stream_url(line):
            channels.append(Channel(pending_name or source_label, line, current_group))
            pending_name = ""
            continue

        # Plain text/TVBox format. Only treat the right-hand side as a channel
        # when it starts with a supported stream scheme, not just any comma row.
        if "," in line:
            name, candidate_url = line.split(",", 1)
            name, candidate_url = name.strip(), candidate_url.strip()
            if is_stream_url(candidate_url):
                channels.append(Channel(name or source_label, candidate_url, current_group))
                pending_name = ""

    return channels


def classify(channel: Channel) -> str:
    searchable = f"{channel.name} {channel.group}"
    if CCTV_PATTERN.search(searchable):
        return "央视卫视地方直播"
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


def write_outputs(grouped: dict[str, list[Channel]]) -> None:
    for category, path in OUTPUTS.items():
        content = render(grouped[category])
        with open(path, "w", encoding="utf-8", newline="\n") as output:
            output.write(f"{category},#genre#\n")
            output.write(content)
        print(f"Wrote {path}: {len(content.splitlines())} channels")

    with open(ALL_OUTPUT, "w", encoding="utf-8", newline="\n") as output:
        for category in OUTPUTS:
            output.write(f"{category},#genre#\n")
            output.write(render(grouped[category]))
            output.write("\n")
    print(f"Updated {ALL_OUTPUT}")


def main() -> int:
    grouped: dict[str, list[Channel]] = {category: [] for category in OUTPUTS}
    successful_sources = 0
    parsed_count = 0

    for label, url in SOURCES:
        try:
            text = fetch_source(label, url)
            entries = parse_playlist(text, label)
            if not entries:
                print(f"WARNING: fetched {label}, but found no supported channel entries", file=sys.stderr)
                continue
            successful_sources += 1
            parsed_count += len(entries)
            for channel in entries:
                grouped[classify(channel)].append(channel)
            print(f"  parsed {len(entries)} channels")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            print(f"WARNING: failed to read {label} ({url}): {error}", file=sys.stderr)
        time.sleep(0.2)

    # Do not replace good playlists with empty files if a site returned an HTML
    # error page or all configured sources were temporarily unavailable.
    if successful_sources == 0 or parsed_count == 0:
        print("ERROR: no channels were parsed; existing output files were not changed.", file=sys.stderr)
        return 1

    write_outputs(grouped)
    print(f"Completed: {parsed_count} entries from {successful_sources}/{len(SOURCES)} sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
