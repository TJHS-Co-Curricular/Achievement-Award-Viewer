"""规则的自动测试（不需要额外安装东西）。

在项目根目录运行：
    python -m unittest discover tests -v

改了 config/ 里的规则或 achievement/ 的程序后跑一次：全部 OK 就表示下面这些已确认的判断都没被改坏。
如果是「故意改了规则」导致某条测试不通过，把那条测试的预期结果一起改掉即可。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from achievement import award_rules, member_rules, rules  # noqa: E402


class ConfigFiles(unittest.TestCase):
    def test_rule_files_are_in_config(self):
        self.assertEqual(member_rules.path().parent.name, "config")
        self.assertEqual(award_rules.path().parent.name, "config")

    def test_rule_files_load(self):
        self.assertTrue(member_rules.get().roles)
        self.assertTrue(award_rules.get().club_kw)


class Roles(unittest.TestCase):
    def cls(self, text, club=""):
        return rules.classify_role(text, club)

    def test_standard_titles(self):
        self.assertEqual(self.cls("副主席"), {"std": "主席(副)"})
        self.assertEqual(self.cls("主席"), {"std": "主席(正)"})          # 没写正副 → 正
        self.assertEqual(self.cls("查账"), {"std": "查账"})              # 查账不分正副
        self.assertEqual(self.cls("音乐主席"), {"std": "主席(正)"})      # 合唱团音乐主席 = 主席级

    def test_shiwu_aliases(self):   # 事务 = 事物 = 总务
        self.assertEqual(self.cls("副总务"), {"std": "事务(副)"})
        self.assertEqual(self.cls("正事物"), {"std": "事务(正)"})
        self.assertNotEqual(self.cls("总务股"), {"std": "事务(正)"})

    def test_title_with_context(self):
        self.assertEqual(self.cls("担任联课处工委联课表扬大会——副总务"), {"other": "联课处工委联课表扬大会-事务(副)"})

    def test_member(self):
        self.assertEqual(self.cls("会员"), {"std": "会员"})

    def test_mid_management(self):
        self.assertEqual(self.cls("华乐团副弹拨首席。", "华乐团")["mid"], ["副弹拨首席"])
        self.assertEqual(self.cls("秘书助理")["mid"], ["秘书助理"])
        self.assertEqual(self.cls("学生顾问")["mid"], ["学生顾问"])
        self.assertEqual(self.cls("校内服务负责人：新春快闪、运动会开幕及闭幕仪式演出")["mid"],
                         ["校内服务负责人-新春快闪", "校内服务负责人-运动会开幕及闭幕仪式演出"])

    def test_moves(self):
        R = member_rules.get()
        self.assertTrue(R.moves_to_comm("《弈德杯》筹委主席"))
        self.assertTrue(R.moves_to_comm("监督成果汇报主席"))
        self.assertTrue(R.moves_to_comm("运动会主席"))
        self.assertFalse(R.moves_to_comm("2024/2025 联课处工委"))
        self.assertTrue(R.moves_to_role("高三欢送会——学生顾问"))

    def test_exclusions(self):
        R = member_rules.get()
        self.assertIsNotNone(R.exclusion("高三毕联会广告工委", "role"))
        self.assertIsNotNone(R.exclusion("感恩聚会-灯光服务（19.5小时）", "intSvc"))
        self.assertIsNotNone(R.exclusion("教师节场布服务（2小时）", "intSvc"))
        self.assertIsNone(R.exclusion("教师节场布服务（2小时）", "comm"))     # 只限校内服务栏
        self.assertIsNotNone(R.exclusion("心动不如 Sing 动", "intComp"))
        self.assertIsNone(R.exclusion("班级歌曲比赛票务股", "comm"))          # 学会的筹委照算


class Awards(unittest.TestCase):
    def test_award(self):
        self.assertTrue(rules.is_award("全国华乐比赛——第五名"))
        self.assertTrue(rules.is_award("Individual pattern - Bronze medal"))
        self.assertTrue(rules.is_award("参加 XX 比赛并获得团体第三名"))
        self.assertFalse(rules.is_award("参与步操比赛"))

    def test_represents_club(self):
        self.assertIsNone(rules.comp_judge("全国舞蹈比赛", "C04"))
        self.assertIn("非代表本学会", rules.comp_judge("武术比赛", "C04"))
        self.assertIn("体育", rules.comp_judge("参与运动会跳高比赛", "A01"))


class Work(unittest.TestCase):
    """资料总览的「工作」（config/work.json）"""

    def judge(self, text, cat="intSvc"):
        from achievement import work_rules
        return work_rules.get().judge(text, cat)[0]

    def test_routine_not_work(self):
        self.assertFalse(self.judge("参与周会站岗服务"))          # 维护者：周会每个月都有，算例常
        self.assertFalse(self.judge("例常早操服务（2小时）"))
        self.assertTrue(self.judge("周会演出"))                   # 周会上的演出是特殊的

    def test_special_is_work(self):
        self.assertTrue(self.judge("校园大扫除（5小时）"))
        self.assertTrue(self.judge("文娱汇演《聚星》——演员", "team"))
        self.assertTrue(self.judge("接待台湾永平高中交流团", "extAct"))   # 活动栏的接待改算工作
        self.assertFalse(self.judge("参与台湾交流会", "extAct"))          # 活动栏的交流 → 活动

    def test_performance_in_activity_is_work(self):
        self.assertTrue(self.judge("2026 年文东文化交流演出活动 —— 演员。", "extAct"))
        self.assertFalse(self.judge("观看《颂》天地人和民族乐团演出。", "extAct"))   # 观看 → 还是活动

    def test_same_work_once_per_year(self):
        # 同一年搬椅子写了 5 次 → 只算 1 个工作；不同年份各算
        svc = ["%d/6 搬椅子服务（1小时）" % d for d in range(1, 6)] + ["校园开放日服务"]
        blk = lambda y: {"year": y, "clubCode": "A01", "clubName": "学长团", "exBlock": None, "hours": 6,
                         "cats": {"intSvc": list(svc)}}
        s = {"sid": "1", "blocks": [blk(2025), blk(2026)]}
        rules.compute_exclusions(s)
        for y in (2025, 2026):
            st, _ = rules.compute_stats(s, {}, y)
            self.assertEqual(st["work"], 2)
            self.assertEqual(st["intSvc"], 6)        # 服务条数、时数照算

    def test_same_competition_each_year(self):
        # 不同比赛底下都写「自选南棍—第一名」：同一年同一栏重复出现，各自计算（吴则融 20390）
        blk = lambda y: {"year": y, "clubCode": "C06", "clubName": "中华武术团", "exBlock": None,
                         "cats": {"extComp": ["全国赛", "自选南棍—第一名", "州赛", "自选南棍—第一名"]}}
        s = {"sid": "1", "blocks": [blk(2025), blk(2026)]}
        rules.compute_exclusions(s)
        for b in s["blocks"]:
            self.assertFalse(any("重复" in (e or "") for e in b["ex"]["extComp"]))


class SheetYears(unittest.TestCase):
    """资料总览的年份栏：自动以 Result 里最新的年份当高三，往前推"""

    def test_auto_years(self):
        from achievement import input_sheet, settings
        st = settings.Settings()
        cols = input_sheet.year_columns(st, [{"blocks": [{"year": 2027}, {"year": 2025}]}])
        self.assertEqual(cols[0][:2], ("2027", "高三"))
        self.assertEqual(cols[5][:2], ("2022", "初一 MCO"))     # 特别标注跟着年份走
        cfg = input_sheet.sheet_config(st, [{"blocks": [{"year": 2026}]}])
        self.assertEqual([y["y"] for y in cfg["years"]][:2], ["2026", "2025"])
        self.assertTrue(cfg["years"][-1]["optional"])          # 留级：没资料不标红

    def test_manual_years(self):
        from achievement import input_sheet, settings
        st = settings.Settings(sheet_years=[("2026", "高三"), ("2025", "高二")])
        self.assertEqual([y for y, _, _ in input_sheet.year_columns(st, [])], ["2026", "2025"])


class Hours(unittest.TestCase):
    def test_parse_hours(self):
        self.assertEqual(rules.parse_hours("3小时"), 3.0)
        self.assertEqual(rules.parse_hours("（5小时5分钟）"), 5.08)
        self.assertEqual(rules.parse_hours("60M / 120M"), 1.0)
        self.assertEqual(rules.parse_hours("（11h，筹备6h，活动5h）"), 11.0)   # 总数 + 细分 → 只算总数
        self.assertEqual(rules.parse_hours("2小时35分钟+ 9小时50分钟"), 12.42)

    def test_declared_total(self):
        # 标题「总服务时数：168小时」下面又写「1. 168小时」→ 只算一次（何伟琦 21824）
        self.assertEqual(rules._declared_total([168.0, 168.0]), 168.0)
        self.assertEqual(rules._declared_total([168.0, 100.0, 68.0]), 168.0)   # 总数 + 细分
        self.assertEqual(rules._declared_total([48.0, 20.0]), 68.0)            # 分开写校内、校外 → 相加


class Reference2025(unittest.TestCase):
    """2026-09-25 用 Result/2025、Result/2026 两届资料补充的写法。"""

    def test_template_heading(self):
        self.assertEqual(rules.match_header("执委层/中层管理/联课处工委/会员："), ("role", ""))

    def test_radicals(self):
        from achievement.reader import fix_radicals
        self.assertEqual(fix_radicals("后台授课⼈"), "后台授课人")

    def test_not_positions(self):
        R = member_rules.get()
        for t in ("暂无", "考获Craft专章", "参与Citizenship专章课程及考试"):
            self.assertTrue(R.exclusion(t, "role"), t)
        self.assertIsNone(R.exclusion("正课程", "role"))

    def test_grade_committees(self):
        R = member_rules.get()
        for t in ("高三编辑工委", "担任教师节工委副主席", "工委：教师节师生赛工委——总务", "毕业特刊编辑工委会--查账"):
            self.assertTrue(R.exclusion(t, "role"), t)
        self.assertIsNone(R.exclusion("编辑小组专题组组员", "role"))

    def test_hours_move_to_comm(self):
        R = member_rules.get()
        self.assertTrue(R.moves_to_comm("园游会——场地（35小时）"))
        self.assertFalse(R.moves_to_comm("联课处工委-52.5小时"))

    def test_roles(self):
        self.assertEqual(rules.classify_role("学长"), {"std": "会员"})
        self.assertIn("mid", rules.classify_role("Harimau Rajawali 小队 队副"))
        self.assertNotIn("std", rules.classify_role("担任循中+永平高中国际志工工委 - 主席"))
        self.assertEqual(rules.classify_role("执委层，摄影及网站制作股"), {"other": "摄影及网站制作股"})
        self.assertEqual(member_rules.get().special_label("2023/2024 联科处工委"), "联课处工委")

    def test_awards(self):
        A = award_rules.get()
        for t in ("参与Pertandingan Memanah Tradisional Pelabuhan Klang --Johan", "- Naib Johan",
                  "UCMAS National Competition -- 2nd runner up", "DANCE IN DIVERSITY 2024 —— CONSOLATION PRIZE",
                  "ICAS数学比赛 - Credit", "《童行童善》- 机智奖", "CABARAN MEMANAH ALFA SIRI 3 --TEMPART KE-2"):
            self.assertTrue(A.why(t), t)
        for t in ("参与Kejohanan Memanah Tradisional Remaja", "PEARL ISLAND INVITATIONAL CHAMPIONSHIP 2025",
                  "参加NATD OPEN DANCESPORT MEDALIST COMPETITION", "参加全国中小学生广告配音大赛(奖项未公布）",
                  "参加The One Academy - Malaysia TOP 10 OUTSTANDING YOUNG ARTISTS AWARDS 2025"):
            self.assertFalse(A.why(t), t)

    def test_representing_club(self):
        A = award_rules.get()
        self.assertIsNone(A.comp_judge("4th MFA Taekwon-Do Invitational Championship 2024 ——Bronze", "D24"))
        self.assertIsNone(A.comp_judge("2023年年终成果汇报之书面报告——团体特优奖", "C06"))
        self.assertIn("时事常识", A.comp_judge("参与422地球日系列活动之常识比赛", "A01"))   # 「地球」不再当成球类
        self.assertIn("学业成绩", A.comp_judge("2024年 第二学期 单科进步奖", "E03"))
        self.assertIn("体育", A.comp_judge("参与Tactical Archery League Of Kuala Lumpur--Johan", "A01"))
        self.assertNotIn("D12", A.comp_judge("- Naib Johan", "A01") or "")    # 「Naib」里的 ai 不再当成 AI


class SupervisorReply20260925(unittest.TestCase):
    """上级 2026-09-25 对 2025 / 2026 参考数据问题的回复。"""

    def test_mid(self):
        for t in ("第一小队副常委", "中层干部-体能关主", "步操口令员", "例常活动堂主-朱雀堂堂主"):
            self.assertIn("mid", rules.classify_role(t), t)

    def test_member(self):
        for t in ("职衔Lans Koperal", "Sarjan（职衔）", "财政/查账培训", "执委服装培训人员", "实习学长"):
            self.assertEqual(rules.classify_role(t), {"std": "会员"}, t)

    def test_newsletter_editor(self):
        R = member_rules.get()
        for t in ("第114期校讯--主编", "校训学生主编（3个月）"):
            self.assertTrue(R.exclusion(t, "role"), t)

    def test_performers_to_comm(self):
        R = member_rules.get()
        for t in ("团内活动演员", "《寄憶》-演奏员", "武踪舞影《爻》-工委主席", "武踪舞影《爻》—《傣族》带领人"):
            self.assertTrue(R.moves_to_comm(t), t)

    def test_biology_science(self):
        A = award_rules.get()
        for t in ("参与K3M化学比赛", "参加2025厦门大学物理杯竞赛"):
            self.assertIsNone(A.comp_judge(t, "D05"), t)
        self.assertTrue(A.comp_judge("参与K3M化学比赛", "A01"))   # 其它学会照旧不计


class WholeFolder(unittest.TestCase):
    """有 Result/ 文件夹时，确认整个文件夹都读得进来、算得出来。"""

    def test_load_result_folder(self):
        folder = ROOT / "Result"
        if not folder.is_dir():
            self.skipTest("没有 Result/ 文件夹")
        from achievement.engine import current_folder, load_folder
        students, files, failed = load_folder(current_folder(folder))   # 只有年份子文件夹时读最新一届
        self.assertTrue(students)
        for s in students:
            st, _ = rules.compute_stats(s)
            self.assertGreaterEqual(st["hours"], 0)


class Structure(unittest.TestCase):
    """项目结构：设定都在 config/，运行时文件夹、版本号、网站路由都正常。"""

    def test_version(self):
        import re as _re
        from achievement import __version__
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {__version__}", changelog, "改了版本号要在 CHANGELOG.md 记一笔")
        self.assertTrue(_re.search(r"^## \d", changelog, _re.M))

    def test_settings_in_config(self):
        from achievement import paths, settings
        st = settings.load()
        self.assertEqual(Path(st.source).parent.name, "config")
        for name in ("config.ini", "member_rules.json", "award.json"):
            self.assertTrue((ROOT / "config" / name).is_file(), name)
            self.assertFalse((ROOT / name).exists(), f"{name} 应该放在 config/ 里")
        self.assertEqual(paths.config_candidates("x.json")[0], ROOT / "config" / "x.json")

    def test_runtime_dirs(self):
        from achievement import paths
        d = paths.make_dirs("Result", "output")
        self.assertEqual(d.data, ROOT / "data")
        self.assertEqual(d.output, ROOT / "output")
        self.assertEqual(d.logs, ROOT / "logs")
        self.assertEqual(d.overrides.name, "成就奖_手动调整.json")

    def test_web_routes(self):
        import tempfile
        from achievement import paths, settings, store, web
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            dirs = paths.Dirs(result=t / "Result", data=t / "data", output=t / "output", logs=t / "logs")
            app = web.create_app(store.Store(dirs), settings.Settings())
            c = app.test_client()
            self.assertEqual(c.get("/api/version").status_code, 200)
            self.assertIn(b"v", c.get("/").data)
            r = c.post("/api/overrides", json={"a": "in", "b": "bad"})
            self.assertEqual(r.get_json()["count"], 1)
            self.assertTrue(dirs.overrides.is_file())
            # 资料总览（评审表格式）
            d = c.get("/api/input").get_json()
            self.assertEqual(len(d["config"]["fields"]), 5)
            self.assertTrue(d["config"]["years"])
            self.assertEqual(c.get("/export/input.xlsx").status_code, 200)


if __name__ == "__main__":
    unittest.main()
