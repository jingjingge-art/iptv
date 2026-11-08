import requests
import time
import re

# Github token建议在仓库secrets配置，防止请求被限流
GITHUB_TOKEN = ""
HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# 读取你仓库里面的台湾频道名称词库地址
CHANNEL_NAME_FILE_URL = "https://raw.githubusercontent.com/jingjingge-art/SHEYE/refs/heads/main/%E5%8F%B0%E6%B9%BE%E9%A2%91%E9%81%93%E5%90%8D%E5%90%88%E9%9B%86.txt"

OUTPUT_FILE = "scaniptv.txt"

def get_channel_names():
    """读取频道名称词库"""
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
    """github代码搜索，查找包含频道名的m3u / txt 文件"""
    results = []
    query = f"{keyword} m3u OR txt in:file extension:m3u,txt"
    url = f"https://api.github.com/search/code?q={query}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 403:
            print("Github API 触发限流，等待...")
            time.sleep(60)
            r = requests.get(url, headers=HEADERS, timeout=20)
        data = r.json()
        items = data.get("items", [])
        for item in items:
            repo_full_name = item["repository"]["full_name"]
            file_path = item["path"]
            download_url = f"https://raw.githubusercontent.com/{repo_full_name}/{item['default_branch']}/{file_path}"
            results.append(download_url)
    except Exception as e:
        print(f"搜索 {keyword} 异常: {e}")
    return list(set(results))


def parse_source_file(file_url, target_channel):
    """打开远程播放列表，匹配频道名称，提取直播链接"""
    out = []
    try:
        resp = requests.get(file_url, timeout=20)
        text = resp.text
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # m3u #EXTINF
            if line.startswith("#EXTINF"):
                name_match = re.search(r',([^,\n]+)$', line)
                if name_match:
                    ch_name = name_match.group(1).strip()
                    if target_channel in ch_name:
                        i +=1
                        while i < len(lines) and lines[i].strip().startswith("#"):
                            i +=1
                        if i < len(lines):
                            url = lines[i].strip()
                            if url.startswith("http"):
                                out.append((ch_name, url))
            # tvbox txt name,url
            elif "," in line and not line.startswith("#"):
                sp = line.split(",", maxsplit=1)
                if len(sp) ==2 and sp[1].startswith("http"):
                    ch_name, ch_url = sp[0].strip(), sp[1].strip()
                    if target_channel in ch_name:
                        out.append((ch_name, ch_url))
            i +=1
    except Exception as e:
        print(f"读取源文件失败 {file_url} : {e}")
    return out


def main():
    channels = get_channel_names()
    print(f"一共加载 {len(channels)} 个频道名称")
    final_result = []
    seen_url = set()

    for ch in channels:
        print(f"正在搜索频道：{ch}")
        source_url_list = github_search_code(ch)
        for src_url in source_url_list:
            match_list = parse_source_file(src_url, ch)
            for name, link in match_list:
                if link not in seen_url:
                    seen_url.add(link)
                    final_result.append((name, link))
        time.sleep(3)

    # 输出格式 scaniptv.txt
    output_lines = []
    output_lines.append("扫描采集,#genre#")
    for ch_name, ch_url in final_result:
        output_lines.append(f"{ch_name},{ch_url}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"✅ 文件生成完成 根目录 {OUTPUT_FILE}，一共找到 {len(final_result)} 条直播线路")


if __name__ == "__main__":
    main()
