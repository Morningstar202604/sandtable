# 贡献指南（Contributing）

感谢关注 Sandtable。这是一个研究"军队组织如何指挥与协同"的多智能体推演系统，
欢迎贡献新场景、新机制、新评估指标与文档改进。

## 开发环境

```bash
git clone <你的 fork>
cd sandtable
pip install -e .            # 或 pip install -e ".[dev]" 安装 pytest
python -m pytest -q         # 确认基线全绿
python -m wargame.cli serve # 本地起服务，浏览器 http://127.0.0.1:8300
```

## 提交前检查

1. `python -m pytest -q` 全部通过；
2. 新功能/新场景附带冒烟测试（参考 `tests/test_smoke.py`）；
3. 代码注释使用中文、只解释"为什么"而非"做了什么"；
4. **绝不提交**：`.env`、API Key、远程仓库令牌、`runs/` 推演日志。
   这些已在 `.gitignore`，提交前请再自查一遍 `git status` 与 `git diff --staged`。

## 如何新增一个场景

在 `src/wargame/scenarios/` 下新建模块，导出统一接口：

```python
SCENARIO_NAME = "我的战役"
FACTIONS = [{"id": "a", "name": "甲方"}, {"id": "b", "name": "乙方"}]
WAR_PAIRS = [["a", "b"]]           # 交战关系；缺省所有异阵营互为敌对
DEFAULT_INTENTS = {"a": "...", "b": "..."}
PLANS = {"a": [...], "b": [...]}   # 参谋方案选项
RECON_TARGET = {"a": [x, y], "b": [x, y]}

def build_world() -> World:
    ...
```

然后在 `scenarios/__init__.py` 的 `SCENARIOS` 里注册一行，主界面立即可选。

## 如何新增引擎机制

世界引擎是确定性的（`engine/world.py`）：所有随机性走注入的 `rng`，
所有可调参数进 `DEFAULT_TUNING`（设置面板会自动暴露）。新机制请遵循：

1. 结算放在 `step()` 的子步骤里，产生类型化事件（供前端与复盘消费）；
2. 需要调参的量一律走 `self.tuning`，并在 `DEFAULT_TUNING` 给默认值；
3. 附带测试。

## 提交规范

- 提交信息：`feat: 新增XX` / `fix: 修复XX` / `docs: 文档XX` / `test: 测试XX`；
- 一次 PR 聚焦一件事；
- 大改动先开 Issue 讨论。

## License

提交即表示你同意以 [MIT](LICENSE) 许可证发布你的贡献。
