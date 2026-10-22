# CLAUDE.md —— Achievement-Award-Viewer 项目规范

> Claude Code 每次打开这个项目都会读这份文件。**改了项目结构、规则流程或工作习惯，请同步更新这份文件。**
> 完整计分规则在 `docs/成就奖计分规则.md`；每个版本改了什么在 `CHANGELOG.md`；一次性交接在 `HANDOFF.md`（如果还在）。

## 1. 项目概要

- **Achievement-Award-Viewer**（启动画面名称 Individual's Utmost Achievement Calculator，成就奖履历查看网站）。
  维护者：ZhiJie Chong（循人中学 Tsun Jin High School）。当前版本以 `achievement/__init__.py` 的 `__version__` 为准（2026-09-28：1.5.1）。
- 读取 `Result/` 里每位高三学生的「联课活动个人表现履历表」（`.xlsx` / `.pdf`），按**上级**（负责老师）定的规则统计「高三最高成就奖」：
  执委 / 职务数、中层管理数、筹委数、服务时数、服务数量、活动 / 工作 / 比赛、获奖。
  「资料总览」页按学校评审 Google 表格的格式排好每年的数字，让维护者贴进 Google 表格。
- 交付方式：本地 Flask 网站，用 PyInstaller 打包成单一 exe，给不懂程序的老师双击使用。
- GitHub：`TJHS-Co-Curricular/Achievement-Award-Viewer`（2026-09-28 起改名，旧名 Individual's Utmost Achievement）。

## 2. 和维护者沟通

- **一律用简体中文回复，用词浅白。** 维护者不是专业程序员，说明「改了什么、在哪里、要不要重新打包」就够了，不要长篇技术细节。
- **规则由上级决定。** 维护者转达上级的修正时照做，**不要自己发明规则**。遇到有歧义、会影响很多学生的情况，先举实际例子问清楚。
- 每次改完都要告诉维护者：
  - 网页版按 Ctrl+F5 刷新就行。
  - 改了 `achievement/`、`static/`、`templates/` → exe 要重新跑 `scripts\build_exe.bat`。
  - 只改 `config/` 的 JSON → 不用重新打包（exe 旁边放 `config\` 会优先采用）。
- 改规则或 `parse_rows` 后，用 `Result/2024`、`Result/2025`、`Result/2026` 三届资料比对改动前后的统计，在回报里说明影响几个人、数字怎么变。
- 维护者的 `todo.md` 是他自己的待办清单，可以读来参考，但要等他在对话里提出才动手。

## 3. 技术栈与版本

- **语言：** Python 3。仓库没有写明最低版本【待确认】；浏览器端是原生 JavaScript（没有框架、没有打包工具）。
- **依赖**（`requirements.txt`）：`flask>=3.0`、`python-calamine>=0.2`（读 .xlsx）、`pdfplumber>=0.10`（读 .pdf）、`openpyxl>=3.1`（写 Excel）。
- **打包：** PyInstaller，由 `scripts\build_exe.bat` 在临时 venv `.buildenv` 里安装，`--onefile --console`。
- **模板：** Jinja2（Flask 自带）。
- **平台：** 主要在 Windows 使用（exe、.bat）；Python 版可以跨平台运行。
- **测试：** 标准库 `unittest`（`tests/test_rules.py`，2026-09-28 有 59 个测试）。
- **可选工具：** `pyflakes`（Python 静态检查），`node --check`（检查 JS 语法）。

## 4. 目录结构

```
app.py                入口，只有几行 → achievement/cli.py 的 main()
achievement/
  __init__.py         __version__（版本号唯一来源）、APP_NAME
  cli.py              参数（argparse）、启动画面、--export / --list-roles / --list-awards、开网站
  web.py              Flask：create_app(store, settings)、所有路由、离线版 HTML、导出
  store.py            Store：读取 Result（指纹变了才重读）、手动调整 data/成就奖_手动调整.json
  input_sheet.py      「资料总览」页：按评审表格式排列的统计（栏位、排序、每年数字、Excel）
  paths.py            ★ 所有文件夹位置：APP_DIR / RESOURCE_DIR、config 查找顺序、data/output/logs、旧文件搬迁
  logs.py             logs/app.log（RotatingFileHandler 1MB×5），未捕获的错误也写进去
  settings.py         读取 config/config.ini（[server] [data] [input_sheet]）
  reader.py           读 .xlsx（python-calamine）/ .pdf（pdfplumber）
  rules.py            计分流程：parse_rows、clean_role、classify_role、standard_roles_from、move_event_roles、
                      compute_exclusions、parse_hours、_mark_work、_mark_svc、compute_stats …
  member_rules.py     读取 config/member_rules.json（职位归类、移栏、不计、特别标记）
  award_rules.py      读取 config/award.json（算不算获奖、是否代表本学会）
  work_rules.py       读取 config/work.json（资料总览「活动 / 工作」和「服务（数量）」）
  engine.py           整个文件夹：多线程解析 + (mtime,size) 缓存、年份子文件夹（届别）、folder_version 指纹（含规则文件）
  excel.py            Excel 总表 / 明细 / 计分规则（RULES_TEXT 是给老师看的规则摘要，规则变了要一起改）
config/               ★ 所有设定只放这里：config.ini、member_rules.json、award.json、work.json
templates/            base.html、index.html（Jinja）
static/               app.js（界面）、core.js（浏览器端即时重算）、input.js（资料总览页）、style.css、favicon.svg
scripts/              build_exe.bat、start_lan.bat、allow_firewall.bat
tests/test_rules.py   unittest：规则判断、工作 / 比赛 / 服务时数、资料总览年份、结构（版本号、config 位置、运行时文件夹、路由）
docs/                 成就奖计分规则.md（完整规则，给上级核对）、履历表指南.md（学生填写范例）、给上级校对的 docx（旧版）
运行时自动产生（不进 git）：data/（手动调整）、output/（导出）、logs/（日志）—— python 版和 exe 版都放在程序旁边
Result/               学生履历表（不进 git）。有年份子文件夹（Result/2024、2025、2026）时网站读最新一届
```

- 设定文件查找顺序（`paths.config_candidates`）：环境变量 → 程序旁边的 `config/` → 程序根目录（旧放法，会提示）→ exe 内置的 `config/`。
- 规则 JSON 改了会自动重载（mtime 指纹），网页几秒内重算，不用重启。

## 5. 编码规范与命名约定

- **规则优先写进 JSON，不写进代码：**
  - 职位、执委、筹委、中层管理、会员、不计、★ 标记 → `config/member_rules.json`。共有「一、不计」「二、执委栏移到筹委栏」「三、筹委栏移到执委栏」「三之二、团内工作栏移到执委栏」「四、职位归类」「五、特别标记」几部分，**从上往下找第一条符合的**。
  - 获奖、是否代表本学会 → `config/award.json`。
  - 资料总览的「活动 / 工作」和「服务（数量）」 → `config/work.json`。
  - 规则字段用中文：`名称`、`包含任一`、`正则`、`并且包含任一`、`不包含`、`学会或内容包含任一`、`适用栏目`、`归类`、`例子`、`备注`。比对时忽略空格和大小写。
  - 新规则要写明来源和日期：「上级定（YYYY-MM-DD）」或「维护者定（YYYY-MM-DD）」。
  - 只有 JSON 做不到的流程（服务时数、B 类、双学会重复、拆句）才改 `achievement/rules.py`。
- **Python 和浏览器端必须一致：**
  - `static/core.js` 的 `rolesFrom` 要和 Python 的 `standard_roles_from` 结果一致（职务列表、数量、中层管理）。
  - `computeStats` 要和 `rules.compute_stats` 一致。
  - 资料总览的网页版（`input.js`，用 `App.statsFor`）和 Excel 版（`input_sheet.py`，用 `compute_stats`）数字必须一样。
  - 每个 block 预先算好的字段：`b.rc`（职位归类）、`b.ex`（不计原因）、`b.aw`（获奖）、`b.hr`（时数）、`b.sp`、`b.mv`（移栏）、`b.nk`（比对 key）、`b.wk`（1 工作 / 3 活动）、`b.wr`（说明）、`b.sc`（服务数量：1 算 / 0 例常 / 2 同年已算过）。
- **内部栏目 key：** `role` 执委 / 职务、`comm` 筹委、`extComp` / `intComp` 校外 / 校内比赛、`extAct` / `intAct` 活动、`extSvc` / `intSvc` 服务、`total` 总服务时数、`team` 团内工作/表演、`badge` 考章、`honor` 团内荣誉。
- **日志：** 新代码用 `logging.getLogger(__name__)` 记录重要事件和错误，不要只用 `print`。
- **注释和用户看到的文字用简体中文；** 函数名、变量名用英文（照现有写法）。
- **测试：** 每条上级确认的规则都要在 `tests/test_rules.py` 加一个测试。
- **版本号**（语义化版本）：修 bug、规则微调 +0.0.1；新功能、改界面 +0.1.0；结构大改 +1.0.0。
  只改 `achievement/__init__.py` 的 `__version__`，同时在 `CHANGELOG.md` 最上面加一段（测试会检查）。只改 `config/` 规则不用改版本号。

## 6. 运行、测试、部署

```bash
pip install -r requirements.txt

python app.py                    # 开网站（自动开浏览器，预设 http://127.0.0.1:5000）
python app.py D:\某个\Result      # 指定 Result 文件夹
python app.py --lan              # 局域网共享（也可以在 config.ini 设 access = lan）
python app.py --port 5050 --no-browser
python app.py --dev              # 开发者模式：每次请求都写进日志
python app.py --export           # 导出离线版 HTML + Excel 到 output/
python app.py --list-roles       # output/已知职位一览.xlsx
python app.py --list-awards      # output/已知获奖一览.xlsx
python app.py --version

python -m unittest discover tests -v          # 测试（必须全部 OK）
python -m pyflakes app.py achievement         # 有装才跑
node --check static/app.js static/core.js static/input.js   # 改了 JS 才跑
```

- **打包 exe（Windows）：** 双击或运行 `scripts\build_exe.bat`，会在项目根目录产生 `Achievement-Award-Viewer.exe`。
  exe 可携带：把 exe、`Result` 文件夹（需要时再加 `config\`）拷到别的 Windows 电脑，双击就能用。
- **局域网：** `scripts\start_lan.bat`；第一次要用 `scripts\allow_firewall.bat` 开放防火墙。
- **排查问题**（读取失败、闪退）：先看 `logs/app.log`。

### 改完的检查清单
1. `python -m unittest discover tests -v` 全部 OK。
2. 有装 pyflakes 就跑一次，没有警告；改了 JS 就跑 `node --check`。
3. 开网站实际看一次：简单页、详细页、资料总览；学生列表在 1280 宽的屏幕上不用左右拉。
4. 改了规则或 `parse_rows`：用三届资料比对改动前后的统计，向维护者报告影响。
5. 更新说明：`docs/成就奖计分规则.md`、网页「说明」页（`templates/index.html` 的 tab-help）、`excel.RULES_TEXT`、`README.md`、这份 `CLAUDE.md`、`CHANGELOG.md`。
6. 告诉维护者要不要重新打包 exe。

## 7. 绝对不能做 / 约束

- **不要把学生资料推上 git：** `Result/`、`data/`、`output/`、`logs/` 都是学生个人资料，`.gitignore` 已经排除。exe 也不进 git。
- **不要自己发明规则。** 规则一律以上级 / 维护者的决定为准（写在 `docs/成就奖计分规则.md` 的决定记录里）。
- **不要用 Prettier 等格式化工具整理 `templates/*.html`**，会弄坏 Jinja 的 `{{ }}`。
- **`scripts\*.bat` 必须纯 ASCII + CRLF 换行。** 不要写中文，不要改成 LF。`.gitattributes` 已设定 `*.bat text eol=crlf`，git 取出文件时会自动转成 CRLF（git 内部仍存 LF，这是正常的）。
- **所有设定文件只能放在 `config/`**（测试会检查位置）。不要把 .ini / .json 放回根目录。
- **版本号只在 `achievement/__init__.py` 改**，不要在别处写死。
- **JSON 规则文件给非程序员手改：** 保持中文字段名和「说明」段，不要改字段名或结构；改结构要同时改对应的 `*_rules.py` 并保持向下兼容。
- **不要单独改 Python 端或 JS 端的计分逻辑。** 两边必须同时改，结果一致。
- **不要覆盖维护者自己的改动：** 动手前先看文件的最新版本和 `git status`，用合并的方式改。
- **手动调整文件 `data/成就奖_手动调整.json` 的 key 格式**（学号 | 年份 | 学会 | 栏目 | 条目）不要随便改，改了会让已经存好的「计入 / 不计」全部失效。

## 8. 已确认的重要规则（摘要，细节看 docs/成就奖计分规则.md）

- **标准职称：** 主席、秘书、事务（事务 = 事物 = 总务）、财政（正/副）、查账（不分正副）、总学长（正/副）、助理总学长；没写正副当「正」。
  其它职位写成「执委(XXX)」，有上下文的写成「执委(联课处工委联课表扬大会-事务(副))」这类。
- **主席级：** 合唱团音乐主席、节令鼓队长类、例常活动主席（副主席 = 主席(副)）。
- **中层管理**（另计，不算职务数）：
  - 助理类、授课人类（含主教）、队长类、监督 / 督导 / 顾问 / 教练 / 领队类、首席 / 组长 / 领养人类、家族职位、联课组别。
  - 乐器组的总务 / 财政 / 谱务；没移到筹委的活动负责人。
  - 校内服务负责人（「校内服务负责人：A、B」拆成两条）、制服负责人、课务股、队伍管理、师徒制度·师傅。
  - 小队常委、体能关主、口令员、堂主、队副 / 小队副。
- **会员**（不计职务数；同一年有其它职位就不另列会员）：
  - 分团职位、职衔（Koperal 等）、XX培训、实习学长、单写「学长」。
  - 小组里只有组长算中层管理，其他一律算会员：组员 / 成员、只写「XX小组」、礼仪小组组员和礼仪小组的其它职位（上级 2026-09-28）。
- **移到筹委：**
  - 执委栏里的演出 / 公演工委 / 带领人。
  - 写了工作时数的活动职位（联课处工委除外）。
  - 为活动组成的筹委团职位、「监督 / 督导XX主席」、运动会 / 田径赛筹委、交流志工团职位。
  - 反过来，写在筹委栏的监督 / 督导 / 顾问类移到执委栏。
- **不计：**
  - 班级活动（含班级歌曲比赛、运动会写生 / 号码布 / 短片比赛）、科代表、B 类整年。
  - 高三毕联会（含编辑 / 广告 / 教师节工委会、毕业特刊）、感恩聚会、学会在运动会的义卖、校内服务里的教师节相关。
  - 模范学长、教师节演出负责人、《校讯》主编。
- **★ 特别标记**（只标记不计分）：联课处工委（含联科处、联课活动处）、文娱工委、XXX志工工委、国际交流筹委 / 负责人。
- **服务时数：**
  - 优先用学生自填的总数。「总数 + 细分」只算总数；同一个数字重复写只算一次；被排除条目的时数要扣掉。
  - 会读中文数字和「×N天」；「1.18小时」开头的「1.」是编号。
- **比赛：**
  - 要代表本学会，判断不了的标「待确认」暂时计入。
  - 以年为单位，每年各自算；同一学会同一栏重复的项目各自算；同一年同一比赛写在两个学会只算一次。
  - 获奖靠名次 / 奖项字眼自动识别；Championship、Kejohanan、Medalist、Participation、奖项未公布不算获奖。
- **资料总览：**
  - 工作 = 服务栏条数（每条都算）；活动 = 比赛和服务以外的栏目一律算；比赛 = 比赛栏条数（参加就算）。
  - 服务（数量）= 服务栏条数，扣掉例常，同一年同一项只算 1 个。
  - 年份栏自动；没资料的格子放 0 并标红（留级不标红）。
- **还没得到上级答复：** 二线执委制服股；校内服务以外栏目的教师节条目；执委(A,B) 算几个、筹委要不要合并；比赛名称那一行算不算；
  `work.json` 例常清单的大部分条目。详见 `HANDOFF.md` §7 或 `docs/成就奖计分规则.md` 第八节。
