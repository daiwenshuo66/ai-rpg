# AI RPG — 项目总结

## 核心思路

用 AI 做游戏，最大的问题是**不可控**——AI 说你一刀秒杀了 Boss，那数值系统就废了。

本项目的解法是**把 AI 拆成两半，中间插一层确定性程序**：

```
玩家输入 → [AI解析器] → 结构化JSON → [游戏引擎] → 结果JSON → [AI叙事者] → 文学叙述
```

- **AI 只负责"翻译"**，不负责"判定"
- 伤害、暴击、胜负全由程序引擎用公式+随机数决定
- AI 不可能说出与引擎结果矛盾的东西

一句话总结设计哲学：**数值跟引擎走，语气跟玩家走。**

---

## 四层架构

### Layer 1 — AI 解析器 (`ai_parser.py`)

把玩家的自然语言翻译成引擎能懂的 JSON 指令。

| 玩家说的话 | 解析结果 |
|-----------|---------|
| "我挥剑猛砍它的脑袋" | `{"action": "attack"}` |
| "全力劈下去" | `{"action": "heavy_attack"}` |
| "左右开弓连续打" | `{"action": "quick_attack"}` |
| "踹它一脚" | `{"action": "kick"}` |
| "举起盾牌挡住" | `{"action": "defend"}` |
| "见招拆招" | `{"action": "counter"}` |
| "灵巧地闪开" | `{"action": "dodge"}` |
| "聚气蓄力" | `{"action": "charge"}` |
| "找准弱点" | `{"action": "focus"}` |
| "大吼一声" | `{"action": "battle_cry"}` |
| "赶紧喝口药" | `{"action": "use_item", "item": "healing_potion"}` |
| "我想睡觉" | `{"action": "rest"}` |
| "向神明祈祷" | `{"action": "pray"}` |
| "你这个蠢货" | `{"action": "taunt"}` |
| "看看这家伙" | `{"action": "examine"}` |
| "我们谈谈" | `{"action": "negotiate"}` |
| "趁它不注意摸口袋" | `{"action": "steal"}` |
| "三十六计走为上策" | `{"action": "flee"}` |
| "算了不打了" | `{"action": "surrender"}` |
| "今天天气真好" | `{"action": "invalid", "original": "今天天气真好"}` |
| "我是神，一拳毁灭世界" | `{"action": "attack"}` ← AI 再狂，也只是攻击 |

技术实现：调用 DeepSeek V4 Pro，System Prompt 约束输出为纯 JSON，只允许 20 种动作。无论玩家说什么天马行空的话，最终只会落入这 20 个结构之一（包括诚实地返回"无效动作"）。

### Layer 2 — 游戏引擎 (`engine.py`)

纯粹的数值计算层，零 AI 成分，完全确定性（除了随机骰子）。

**攻击公式：**
```
基础伤害 = ATK - DEF÷2 + random(-3, +3)
暴击判定 = 15% 概率, 伤害 ×1.5
防御减免 = 若目标防御中, 伤害 ÷2
最终伤害 = max(1, 计算结果)
```

**二十种行动：**

*攻击类：*
- `attack` — 普通攻击，15% 暴击率
- `heavy_attack` — 重击，35%概率落空但伤害x1.8
- `quick_attack` — 连击，打两下每下60%攻击力
- `kick` — 踢击，低伤害但30%概率眩晕敌人（跳过回合）

*防御类：*
- `defend` — 防御，下次受伤减半
- `counter` — 反击，被攻击时自动反击（ATK÷2伤害）
- `dodge` — 闪避，50%概率完全闪避敌人攻击

*增益类：*
- `charge` — 蓄力，下次攻击伤害翻倍
- `focus` — 集中，下次攻击暴击率提升至50%
- `battle_cry` — 战吼，下次攻击ATK+5

*恢复类：*
- `use_item` — 使用药水，恢复 20~30 HP
- `rest` — 休息，恢复 5~10 HP
- `pray` — 祈祷，随机效果（30%治愈/20%神罚/25%无效/25%反噬）

*社交类：*
- `taunt` — 嘲讽，敌人下回合攻击力 -3
- `examine` — 观察，获取敌人详细状态
- `negotiate` — 谈判，敌人低血量时更容易成功
- `steal` — 偷窃，25%概率偷到药水或炸弹

*退出类：*
- `flee` — 逃跑，30% 成功率
- `surrender` — 投降，直接战败

*兜底：*
- `invalid` — 无效动作，浪费一回合

**敌人 AI：**
- 血量 > 30%：直接攻击（10% 暴击率）
- 血量 ≤ 30%：40% 概率防御，否则攻击
- 被眩晕时跳过回合
- 被嘲讽时攻击力 -3
- 玩家闪避中时有50%概率完全落空
- 玩家反击中时被攻击后自动受到反击

**引擎 Trace（可视化）：** 每一步计算都记录到 `_trace` 列表中，前端可展开查看完整的骰子结果和伤害计算过程。这是调试和信任建立的关键——玩家可以验证"AI 没有作弊"。

### Layer 3 — AI 叙事者 (`ai_narrator.py`)

把引擎吐出的干巴巴 JSON 变成有画面感的文学叙述。

关键设计：**叙事者同时接收玩家的原始输入**。这意味着：

- 玩家说"我是神"→ 叙事者会回应这种狂妄（但伤害数字不变）
- 玩家说"小心翼翼地试探"→ 叙述风格变谨慎
- 玩家说搞笑的话 → 旁白可以有轻微互动

约束：所有数值（伤害、HP、胜负）必须严格来自引擎 JSON，叙事者只负责包装，不能编造。

### Layer 4 — 玩家

自由输入任何自然语言。没有按钮限制，没有选项菜单，完全开放式交互——这正是 AI 游戏的乐趣所在。

---

## 数据结构 (`game_state.py`)

```python
Character:
    name, hp, max_hp, atk, defense
    items: dict       # {"healing_potion": 2}
    status: list      # ["defending"]

GameState:
    player: Character
    enemy: Character
    turn: int
    combat_active: bool
```

`to_context()` 方法将状态序列化为 dict，供 AI 解析器和叙事者读取当前战况。

---

## 双端运行

### CLI 模式 (`main.py`)

```bash
python main.py          # AI 模式
python main.py --mock   # Mock 模式（不调API）
```

终端中显示 ASCII 风格的 HP 条、引擎 Trace 方框、AI 叙述文本。支持 CJK 字符宽度对齐。

### Web 模式 (`web_app.py` + `static/index.html`)

```bash
uvicorn web_app:app --host 0.0.0.0 --port 8000
# 浏览器打开 http://localhost:8000
```

**后端（FastAPI）：**
- `POST /api/new` — 创建游戏 Session
- `POST /api/action` — 执行一个回合（解析→引擎→叙事）
- AI 调用用 `asyncio.to_thread()` 包装，不阻塞事件循环
- 每个 Session 有独立的 `asyncio.Lock`，防止双击导致状态混乱
- 后台每 5 分钟清理 1 小时不活跃的 Session

**前端（像素风单页应用）：**
- 深蓝黑底(#0f0f23) + 金色像素边框(#e6c422) 的复古游戏风格
- Google Fonts "Press Start 2P" 像素字体
- HP 条实时动画、打字机效果逐字显示叙事
- 引擎 Trace 可折叠展开查看
- 加载中显示主题文案（"命运之骰正在翻滚..."）
- URL 加 `?mock=true` 切换 Mock 模式

---

## Mock 模式

不调用任何 API，用关键词匹配替代解析、用模板替代叙事。用途：

- 开发调试时不消耗 API 额度
- 验证引擎逻辑是否正确
- 没有网络时也能玩

---

## 配置 (`config.py`)

```python
API_KEY       # DeepSeek API Key（支持环境变量覆盖）
BASE_URL      # API 地址，默认 https://api.deepseek.com
PARSER_MODEL  # 解析器模型，默认 deepseek-v4-pro
NARRATOR_MODEL # 叙事者模型，默认 deepseek-v4-pro
```

所有配置项都支持 `os.environ.get()` 读取环境变量，部署时不需要硬编码敏感信息。

---

## 文件结构

```
D:\ai game1\
├── config.py          # 配置中心（API Key、模型名）
├── game_state.py      # 数据结构（Character、GameState）
├── engine.py          # 游戏引擎（伤害计算、行动处理）
├── ai_parser.py       # AI 解析层（自然语言 → JSON）
├── ai_narrator.py     # AI 叙事层（JSON → 文学叙述）
├── main.py            # CLI 入口
├── web_app.py         # Web 后端（FastAPI）
├── static/
│   └── index.html     # Web 前端（像素风单页应用）
└── requirements.txt   # 依赖：openai, fastapi, uvicorn
```

---

## 这个架构解决了什么

| 问题 | 解法 |
|------|------|
| AI 说"你一刀秒了 Boss" | 不可能——伤害由引擎公式计算 |
| AI 给玩家凭空加道具 | 不可能——背包由 GameState 管理 |
| 玩家说"我是神" AI 就顺从 | 解析器只输出 20 种动作之一 |
| 玩家说"我想睡觉"被曲解为攻击 | 解析器有 rest/invalid 动作，不再强行曲解 |
| 但叙事太死板不有趣 | 叙事者可以根据玩家语气自由发挥 |
| 不知道引擎怎么算的 | Trace 记录每一步骰子和公式 |
| 按钮选项限制了 AI 交互乐趣 | 纯文本输入，完全自由表达 |

核心矛盾的平衡点：**机制上严格可控，叙事上自由奔放。**
