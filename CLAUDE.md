# CLAUDE.md —— 给 AI 助手（Claude）的项目说明

> 这份文件是「项目记忆」。在任何一台电脑用 Claude（Claude Code / Cowork / claude.ai）打开这个项目时，
> 先读这份文件，就能接着之前的工作做下去。**改了项目结构、规则流程或工作习惯，请同步更新这份文件。**
> 完整计分规则在 `Docs/成就奖计分规则.md`；每个版本改了什么在 `CHANGELOG.md`。

## 1. 这是什么

- **Achievement-Award-Viewer**（启动画面名称 Individual's Utmost Achievement Calculator，成就奖履历查看网站），当前版本见 `achievement/__init__.py`（2026-09-28：v1.5.1），维护者：ZhiJie Chong（循人中学 Tsun Jin High School）。
- 读取 `Result/` 里每位高三学生的「联课活动个人表现履历表」（`.xlsx` / `.pdf`），按**上级**（负责老师）定下的规则，
  统计「高三最高成就奖」：执委/职务数、中层管理数、筹委数、服务时数、活动、团内工作、比赛与获奖；
  「资料总览」页按学校评审 Google 表格的格式输出每年数字，让维护者贴进 Google 表格。
- 本地 Flask 网站 + 用 PyInstaller 打包成单一 exe（`scripts\build_exe.bat` → `Achievement-Award-Viewer.exe`），给不懂程序的老师双击使用。
- 项目文件夹 / GitHub 仓库名：`Achievement-Award-Viewer`（2026-09-28 起，旧名 Individual's Utmost Achievement）。exe 不进 git（.gitignore 有 `*.exe`）。
- GitHub：`TJHS-Co-Curricular/Achievement-Award-Viewer`。`Result/`、`data/`、`output/`、`logs/` 不进 git（学生个人资料）。

## 2. 和维护者沟通的方式

- **一律用简体中文回复**，用词浅白；维护者不是专业程序员，说明「改了什么、在哪里、要不要重新打包」即可，不要长篇技术细节。
- 规则由上级决定。维护者转达上级的修正时，**照做，不要自己发明规则**；遇到有歧义、会影响很多学生的情况，先举例问清楚。
- 每次改完告诉他：网页版按 Ctrl+F5 即可；改了 `static/`、`templates/`、`achievement/` 的话 exe 要重新跑 `scripts\build_exe.bat`；
  只改 `config/` 的 JSON 则不用重新打包（exe 旁边放 `config\` 会优先采用）。
- 可能有另一个 Claude 对话同时在改这个项目：动手前先看文件的最新版本，**合并**而不是覆盖别人的改动。

## 3. 文件结构（改动前先看这里）

```
app.py                入口，只有几行 → achievement/cli.py 的 main()
achievement/
  __init__.py         __version__（版本号唯一来源）、APP_NAME
  cli.py              参数（argparse）、启动画面、--export / --list-roles / --list-awards、开网站
  web.py              Flask：create_app(store, settings)、所有路由、离线版 HTML、导出
  store.py            Store：读取 Result（指纹有变才重读）、手动调整 data/成就奖_手动调整.json
  input_sheet.py      「资料总览」页：按评审表格式排列的统计（栏位、排序、每年数字、Excel）
  paths.py            ★ 所有文件夹位置：APP_DIR / RESOURCE_DIR、config 查找顺序、data/output/logs、旧文件搬迁
  logs.py             logs/app.log（RotatingFileHandler 1MB×5），未捕获的错误也写进去
  settings.py         读取 config/config.ini（[server] access/port/port_fallback/open_browser/lan_allow_edit；[data] result_folder/output_folder；[input_sheet] title/years/grades/year_notes/optional_grades/optional_years）
  reader.py           读 .xlsx（python-calamine）/ .pdf（pdfplumber）
  rules.py            计分流程：parse_rows、classify_role、standard_roles_from、move_event_roles、compute_exclusions、parse_hours、compute_stats …
  member_rules.py     读取 config/member_rules.json（职位归类、移栏、不计、特别标记）
  award_rules.py      读取 config/award.json（算不算获奖、是否代表本学会）
  work_rules.py       读取 config/work.json（资料总览「活动 / 工作」：服务栏 = 工作，比赛和服务以外 = 活动）
  engine.py           整个文件夹：多线程解析 + (mtime,size) 缓存、年份子文件夹（届别）、folder_version 指纹（含规则文件）
  excel.py            Excel 总表 / 明细 / 计分规则（RULES_TEXT 是给老师看的规则摘要，规则变了要一起改）
config/               ★ 所有 .ini / .json 设定都只放这里：config.ini、member_rules.json、award.json、work.json
templates/            base.html、index.html（Jinja；**不要用 Prettier 等格式化工具整理，会弄坏 {{ }}**）
static/               app.js（界面）、core.js（浏览器端即时重算）、input.js（「资料总览」页，经 window.App 用 app.js 的资料）、style.css、favicon.svg
scripts/              build_exe.bat、start_lan.bat、allow_firewall.bat（**必须纯 ASCII + CRLF 换行**）
tests/test_rules.py   unittest：规则判断、工作 / 比赛 / 服务时数、资料总览年份、结构（版本号、config 位置、运行时文件夹、路由）
Docs/                 成就奖计分规则.md（完整规则，给上级核对）、履历表指南.md（学生填写范例）、给上级校对的 docx（旧版，未跟着更新）
运行时自动产生：data/（手动调整）、output/（导出）、logs/（日志）——python 版和 exe 版都在程序旁边
```

- 设定文件查找顺序（`paths.config_candidates`）：环境变量 → 程序旁边 `config/` → 程序根目录（旧放法，会提示）→ exe 内置 `config/`。
- 规则 JSON 改了会自动重载（mtime 指纹），网页几秒内重算，不用重启。

## 4. 规则怎么改（最常见的工作）

1. **职位 / 执委 / 筹委 / 中层管理 / 不计 / 特别标记** → 改 `config/member_rules.json`（五部分：一、不计 二、执委栏移到筹委栏 三、筹委栏移到执委栏 四、职位归类 五、特别标记；文件开头有「说明」）。
   每条规则的字段：`名称`、`包含任一`、`正则`、`并且包含任一`、`不包含`、`学会或内容包含任一`、`适用栏目`、`归类`、`例子` 等。
2. **获奖 / 是否代表本学会** → 改 `config/award.json`。
   **资料总览的「活动 / 工作」**算哪几栏 → 改 `config/work.json`（「工作的栏目」「活动的栏目」）。
3. 只有 JSON 做不到的流程（服务时数、B 类、双学会重复、拆句）才改 `achievement/rules.py`。
4. **浏览器端要同步**：`static/core.js` 的 `rolesFrom` 必须和 Python 的 `standard_roles_from` 结果一致（职务列表、数量、中层管理）。
   每个 block 预先算好的字段：`b.rc`、`b.ex`、`b.aw`、`b.hr`、`b.sp`、`b.mv`、`b.nk`、`b.wk` / `b.wr`（工作）。
5. 每条上级确认的规则，在 `tests/test_rules.py` 加一个测试；然后跑 `python -m unittest discover tests -v`。
6. 更新说明：`Docs/成就奖计分规则.md`（写明「上级定」和日期）、网页「说明」页（templates/index.html 的 tab-help）、Excel 的 `excel.RULES_TEXT`、`README.md`；需要时用 `python app.py --list-roles` / `--list-awards` 产生参考清单到 `output/`。

## 5. 已确认的重要规则（摘要，细节看 Docs/成就奖计分规则.md）

- 标准职称：主席、秘书、事务（事务 = 事物 = 总务）、财政（正/副）、查账（不分正副）、总学长（正/副）、助理总学长；没写正副当「正」；
  其它职位写成「执委(XXX)」；有上下文的写成「执委(联课处工委联课表扬大会-事务(副))」这类。
- 主席级：合唱团音乐主席、节令鼓队长类、例常活动副主席 = 主席(副)。
- 中层管理（另计，不算职务数）：助理类、授课人类、队长类、监督/督导/顾问/教练/领队类、首席/组长/领养人类、家族职位、联课组别、
  校内服务负责人（「校内服务负责人：A、B」拆成两条）、制服负责人、课务股、队伍管理、师徒制度·师傅、
  小队常委、体能关主、口令员、堂主、队副 / 小队副。
- 会员（不计职务数）：分团职位、职衔（Koperal 等）、XX培训、实习学长、单写「学长」、小组组员 / 成员（组长才算中层管理）；同年有其它职位就不另列会员。
- 移到筹委：执委栏里的演出 / 公演工委 / 带领人、写了工作时数的活动职位、为活动组成的筹委团职位、「监督/督导XX主席」、运动会/田径赛筹委、交流志工团职位；写在筹委栏的监督/督导/顾问类移到执委栏。
- 上级 2026-09-28（2024 校准）：科代表不计；主教、乐器组总务 / 财政 / 谱务、活动负责人 = 中层管理；（活动 / 工作的条件后来已由维护者重新定义取代，见 §8）。小组里只有组长 = 中层管理，其他一律 = 会员：XX小组组员 / 成员、只写「XX小组」、礼仪小组组员（团内工作栏移到执委栏，member_rules「三之二」）及礼仪小组其它职位（member_rules「四」第一条）。
- 不计：班级活动（含班级歌曲比赛、运动会写生/号码布/短片比赛）、B 类、高三毕联会（含编辑/广告/教师节工委会）、感恩聚会、
  学会在运动会的义卖、校内服务里的教师节相关、模范学长、教师节演出负责人、《校讯》主编。
- 特别标记 ★（只标记不计分）：联课处工委、文娱工委、XXX志工工委、国际交流筹委/负责人。
- 校准资料：Result/2024、Result/2025、Result/2026 三届（2026-09-28 v1.3.8 三届校验，output/三届校验_2024-2026.xlsx 列出全部条目的归类）。2026-09-28 用 2024 届整体校准（v1.3.5）：「26.5小时」曾被当编号读成 5 小时（rules.strip_num）；parse_rows 处理年份行写在中间（暂定格 provisional）、只写班级没写年份（年份往前推）、表格式履历表（_parse_table_layout）。改 parse_rows 后用两届资料比对前后差异再交付。服务时数（v1.3.7）：总数有两种读法时存 totalAlts，_pick_total 选和逐项相加相差 ≤0.5 的；备注栏的总数不改变当前类别；parse_hours 支持中文数字、×N天。
- 服务时数：优先学生自填总数；「11h，筹备6h，活动5h」这种「总数 + 细分」只算总数；「总服务时数」一格里同一个数字重复写只算一次（rules._declared_total）；被排除条目的时数要扣掉。
- 比赛须代表本学会，判断不了标「待确认」暂时计入；以年为单位，每年各自算；同一学会同一栏重复的项目各自算。
- 还没得到上级答复：「二线执委--制服股」算不算中层管理；校内服务以外栏目的教师节条目；执委(A,B) 算 2、筹委每条算 1；比赛一行算一个（比赛名称那一行也算）；资料问题：B08 C04 21806 蔡佳芯 的舞蹈团职位被读进 B08 那一格，需人工看原件。

## 6. 版本号与日志

- 版本号只改 `achievement/__init__.py` 的 `__version__`（语义化版本：修 bug +0.0.1、新功能 / 改界面 +0.1.0、结构大改 +1.0.0），
  同时在 `CHANGELOG.md` 最上面加一段（测试会检查）。只改 config/ 规则不用改版本号。
- 版本号显示在：网页底部、启动画面、`/api/version`、日志、`python app.py --version`。
- 日志 `logs/app.log`：排查「读取失败」、闪退时先看它；`--dev` 记录每次请求。新代码用 `logging.getLogger(__name__)` 记重要事件和错误，不要只用 print。

## 7. 改完的检查清单

- `python -m unittest discover tests -v` 全部 OK。
- `python -m pyflakes app.py achievement` 没有警告（有装的话）；改了 JS 跑 `node --check static/app.js static/core.js`。
- 开网站实际看一次（简单 / 详细页、学生列表在 1280 宽屏幕不用左右拉）。
- 改了 `scripts\*.bat`：确认纯 ASCII、CRLF。
- 更新说明文件：`README.md`、`Docs/成就奖计分规则.md`、网页「说明」页、`excel.RULES_TEXT`、这份 `CLAUDE.md`、`CHANGELOG.md`；Project 里的 `claude/成就奖计分规则.md`、`claude/CLAUDE_项目说明.md` 也同步。

## 8. 「资料总览」页（v1.2.0 起）

- 用途：把学生列表的统计按学校 Google 表格「2026 高三最高成就奖评审」的格式排好，让维护者复制贴进 Google 表格（**只显示，不能在网页里改**）。
- 栏位：序、学号、班级、姓名(中)，每个年份一组：执委（数量）= 职务数、中层管理（数量）、筹委（数量）、服务（小时）、服务（数量）、
  服务（数量）（维护者 2026-09-28）= 服务栏条数，例常（work.json「服务（数量）→ 例常（不算）」）不算、同一年同一项只算 1 个（同一类算一个 + rules._work_key）；rules._mark_svc → b.sc（1 算 / 0 例常 / 2 同年已算过）、说明在 b.wr；stats 的 svcN（Python 与 core.js 一致）。
  活动/工作/比赛 = 三个数字分开写，例 4/6/2。维护者 2026-09-28 重新定义（取代之前所有条件）：工作 = 服务栏（校内 / 校外服务）条数；活动 = 比赛和服务以外的栏目一律算（校内 / 校外活动、团内工作/表演、考章、团内荣誉）；rules._mark_work → b.wk：1 工作 / 3 活动，Python compute_stats 与 core.js 一致；设定在 config/work.json。比赛 = 校内外比赛条数（参加就算，不只获奖）。比赛以年为单位：每年各自算，同一学会同一栏重复出现的项目各自算，「双学会重复」只用在两个学会。维护者定：该年没有履历的格子放 0 并用红色标出（网页 td.miss、Excel 红底）；全部年份都没资料的学生，名字也标红。留级（optional_grades）没资料只放 0、不标红。已套用「计入 / 不计」手动调整。
- 没有「评审」「顾问建议」栏（维护者定：那两栏在 Google 表格里自己填）。
- 排序：学会代号 → 学号。年份栏（维护者 2026-09-28 定：自动）：`years = auto` → Result 里最新的年份 = 高三，往前推 grades（高三…初一、留级）；`year_notes`（2022:MCO）跟着年份走；`optional_grades = 留级` 没资料不标红。input_sheet.year_columns / sheet_config(settings, students)，网页资料更新时重新取 /api/input。
- 网页端（static/input.js）用 App.statsFor 计算；Excel（`/export/input.xlsx`，achievement/input_sheet.py）用 rules.compute_stats，两边数字必须一致。
