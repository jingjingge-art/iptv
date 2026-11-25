"""Offline regression tests for playlist parsing and classification."""

import unittest

from scan_iptv import Channel, SOURCES, classify, parse_playlist


class PlaylistParserTests(unittest.TestCase):
    def test_m3u_keeps_title_group_and_url(self):
        source = """#EXTM3U
#EXTINF:-1 tvg-name=\"CCTV-5+体育赛事\" group-title=\"央视\",CCTV-5+体育赛事
#EXTVLCOPT:http-user-agent=Test
https://example.test/live.m3u8?token=a=b
"""
        channels = parse_playlist(source, "sample")
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0], Channel(
            "CCTV-5+体育赛事", "https://example.test/live.m3u8?token=a=b", "央视"
        ))
        self.assertEqual(classify(channels[0]), "央视卫视地方直播")

    def test_tvbox_genre_rows_apply_group_to_channels(self):
        source = """央视,#genre#
CCTV1综合,http://example.test/cctv1.m3u8
CCTV17农业农村,rtp://239.1.1.17:1234
影视,#genre#
电影频道,http://example.test/movie.m3u8
"""
        channels = parse_playlist(source, "sample")
        self.assertEqual(len(channels), 3)
        self.assertEqual(classify(channels[0]), "央视卫视地方直播")
        self.assertEqual(classify(channels[1]), "央视卫视地方直播")
        self.assertEqual(classify(channels[2]), "影视线路")

    def test_all_cctv_variants_go_to_live_output(self):
        names = (
            "CCTV1[1080][S]", "CCTV-13 新闻", "CCTV5+体育赛事", "CCTV4K",
            "CCTV央视台球", "央视文化精品", "CCTV-6电影",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(classify(Channel(name, "http://example.test/live")), "央视卫视地方直播")

    def test_new_playlist_source_is_configured(self):
        self.assertIn(
            ("新增直播源", "https://live.yang-1989.eu.org/Live.m3u"), SOURCES
        )


if __name__ == "__main__":
    unittest.main()
