import requests
import time
import re
import socket

# Github token 填入，强烈建议配置token，大幅提升限额
GITHUB_TOKEN = ""
HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

CHANNEL_NAME_FILE_URL = "https://raw.githubusercontent.com/jingjingge-art/SHEYE/refs/heads/main/%E5%8F%B0%E6%B9%BE%E9%A2%91%E9%81%93%E5%90%8D%E5%90%88%E9%9B%86.txt"
OUTPUT_FILE = "scaniptv.txt"

CONNECT_TIMEOUT = 8
READ_TIMEOUT = 12
SKIP_ALIVE_CHECK = True # 先设置True，关闭存活检测！优先验证能不能搜到源，调试完成再改为False


def clean_keyword(name):
    # 清理关键词，去掉括号英文后缀，提升搜索命中率
    name = re.sub(r'[（(].*?[）)]', '', name)
    return name.strip()


def get_channel_names():
    resp = requests.get(CHANNEL_NAME_FILE_URL, timeout=30)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    channel_list = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.endswith(",#genre#"):
            continue
        channel_list.append(line)
    return list(set(channel_list))


def github_search_code(keyword):
    results = []
    clean_word = clean_keyword(keyword)
    # ✅ 修复搜索语法
    query = f'"{clean_word}" extension:m3u OR "{clean_word}" extension:txt in:file'
    url = f"https://api.github.com/search/code?q={query}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"[Search] keyword:{clean_word} status:{r.status_code}")
        if r.status_code == 403:
            print("⚠️ Github API 403 限流！")
            time.sleep(120)
            r = requests.get(url, headers=HEADERS, timeout=20)
        data = r.json()
        items = data.get("items", [])
        print(f"      搜索命中仓库文件数量: {len(items)}")
        for item in items:
            repo_full_name = item["repository"]["full_name"]
            file_path = item["path"]
            branch = item["repository"].get("default_branch","main")
            download_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{file_path}"
            results.append(download_url)
    except Exception as e:
        print(f"搜索异常 {keyword}: {e}")
    return list(set(results))


def parse_source_file(file_url, target_channel):
    out = []
    try:
        resp = requests.get(file_url, timeout=20)
        text = resp.text
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                name_match = re.search(r',([^,\n]+)$', line)
                if name_match:
                    ch_name = name_match.group(1).strip()
                    if clean_keyword(target_channel) in clean_keyword(ch_name):
                        i += 1
                        while i < len(lines) and lines[i].strip().startswith("#"):
                            i += 1
                        if i < len(lines):
                            url = lines[i].strip()
                            if url.startswith("http"):
                                out.append((ch_name, url))
            elif "," in line and not line.startswith("#"):
                sp = line.split(",", maxsplit=1)
                if len(sp) == 2 and sp[1].startswith("http"):
                    ch_name, ch_url = sp[0].strip(), sp[1].strip()
                    if clean_keyword(target_channel) in clean_keyword(ch_name):
                        out.append((ch_name, ch_url))
            i += 1
    except Exception as e:
        print(f"读取文件失败 {file_url} : {e}")
    return out


def check_stream_alive(stream_url) -> bool:
    try:
        resp = requests.head(
            stream_url,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True
        )
        if resp.status_code >= 200 and resp.status_code < 400:
            return True
    except (requests.exceptions.RequestException, socket.timeout):
        pass
    try:
        resp = requests.get(
            stream_url,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True,
            stream=True
        )
        next(resp.iter_content(chunk_size=2048), b'')
        if resp.status_code >= 200 and resp.status_code < 400:
            return True
    except (requests.exceptions.RequestException, socket.timeout):
        return False
    return False


def main():
    channels = get_channel_names()
    print(f"✅ 加载频道总数 {len(channels)}")
    raw_results = []
    seen_url = set()

    for ch in channels:
        print(f"\n🔍 当前频道：{ch}")
        source_url_list = github_search_code(ch)
        for src_url in source_url_list:
            match_list = parse_source_file(src_url, ch)
            print(f"       在该文件匹配到频道线路数量：{len(match_list)}")
            for name, link in match_list:
                if link not in seen_url:
                    seen_url.add(link)
                    raw_results.append((name, link))
        time.sleep(2)

    print(f"\n📋 收集候选线路总数：{len(raw_results)}")

    valid_list = []
    if not SKIP_ALIVE_CHECK:
        print("开始活性检测...")
        for idx, (ch_name, ch_url) in enumerate(raw_results):
            print(f"[{idx+1}/{len(raw_results)}]检测 {ch_name}")
            if check_stream_alive(ch_url):
                print(f"✅存活 {ch_name}")
                valid_list.append((ch_name, ch_url))
    else:
        valid_list = raw_results

    output_lines = []
    output_lines.append("扫描采集,#genre#")
    for ch_name, ch_url in valid_list:
        output_lines.append(f"{ch_name},{ch_url}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print(f"\n✅ 完成，输出文件 scaniptv.txt，有效线路：{len(valid_list)}")


if __name__ == "__main__":
    main()
