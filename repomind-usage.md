# OnePTeam / RepoMind 使用方式整理

> 说明：当前代码仓库中没有出现 `OnePTeam` 这个名称，实际插件名、Skill 名和运行时目录均为 `RepoMind` / `repomind`。本文档按当前代码实现整理所有可用方式。

## 1. Codex 插件方式

Codex 插件是当前 README 中优先推荐的使用方式。用户通过 Codex 安装 RepoMind 后，在新会话里直接让 Codex 使用 RepoMind 进行公开代码库研究。

安装输入：

```bash
codex plugin marketplace add gynnash/RepoMind --ref main
codex plugin add repomind@repomind
```

使用输入：

```text
Use RepoMind to find reusable architectures for a multi-agent task scheduler.
```

也可以提出更泛化的工程研究问题：

```text
Use RepoMind to compare how mature CLI tools implement resumable downloads.
Use RepoMind to research design rationale for append-only event logs.
Use RepoMind to find engineering patterns for safe plugin upgrade workflows.
```

预期输出：

```text
complete|partial|needs_clarification|out_of_scope|unavailable
```

在 `complete` 或 `partial` 状态下，RepoMind 会输出一份综合研究报告，包含相关开源仓库、设计模式、关键文件证据、适用边界、权衡分析、对当前项目的适配建议，以及证据的新鲜度说明。

主要功能：

- 根据明确问题研究公开代码库中的可复用工程设计。
- 使用项目上下文做适配分析，但不会静默改写用户问题。
- 优先复用项目本地 `.repomind/` 缓存。
- 缓存不足时再通过 GitHub 搜索候选仓库。
- 输出基于证据的设计建议，而不是泛泛的项目列表。

## 2. Claude Code 插件方式

Claude Code 插件方式使用同一份 `plugins/repomind` 插件目录，但通过 Claude Code 的 marketplace 和命名空间命令安装与调用。

安装输入：

```bash
claude plugin marketplace add gynnash/RepoMind
claude plugin install repomind@repomind
```

使用输入：

```text
/repomind:repomind design an agent scheduling layer with priority queues
```

预期输出：

Claude Code 会按 RepoMind Skill 的流程执行：先确认研究问题，再检查本地缓存，必要时搜索 GitHub，最后输出一份包含比较证据、设计权衡和适配建议的研究结果。

主要功能：

- 以 Claude Code plugin skill 的形式调用 RepoMind。
- 支持显式研究问题。
- 对没有明确问题的上下文，会先提出一个推荐方向和 2-3 个备选方向，等待用户确认。
- 对语法问题、单个 API 用法、常规调试问题会拒绝使用 RepoMind，转为普通编码或文档帮助。

## 3. Standalone Agent Skill 方式

RepoMind 的核心能力在 `plugins/repomind/skills/repomind` 目录下，因此也可以不通过插件市场，直接把 Skill 目录复制到 Codex 或 Claude Code 的 skills 目录。

安装输入：

```bash
git clone https://github.com/gynnash/RepoMind.git
cd RepoMind

# Claude Code
cp -R plugins/repomind/skills/repomind ~/.claude/skills/

# Codex
cp -R plugins/repomind/skills/repomind ~/.codex/skills/
```

Claude Code 使用输入：

```text
/repomind design a plugin-based event processing architecture
```

Codex 使用输入：

```text
Use RepoMind to design a plugin-based event processing architecture.
```

预期输出：

输出结构和插件方式一致，都是围绕公开实现证据生成的研究报告。运行时状态会写入当前项目根目录下的 `.repomind/`。

主要功能：

- 复用同一份 Skill 实现。
- 不依赖 marketplace 安装流程。
- 适合本地开发、调试、私有分发或在不同 agent host 中复用。

## 4. 自动触发和显式触发

RepoMind 的 OpenAI metadata 中设置了 `allow_implicit_invocation: true`，因此在 Codex 环境中，符合条件的问题可以被隐式触发；用户也可以显式写出 `Use RepoMind ...`。

有效输入示例：

```text
Research plugin lifecycle and isolation designs in public codebases.
Compare scheduler retry patterns across repositories.
Find reusable Agent Skill workflow designs and rationale.
```

不适合 RepoMind 的输入示例：

```text
How do I implement React useState?
What arguments does this API accept?
Debug this failing unit test.
```

预期输出：

- 对有效输入：进入 RepoMind 研究流程。
- 对无明确问题但有上下文的输入：给出候选研究方向并等待确认。
- 对无关输入：拒绝 RepoMind 工作流，改用普通编码、调试或文档回答。

主要功能：

- 防止把普通 API 问答误判为架构/设计研究。
- 明确区分“研究前确认”和“确认后研究”两个阶段。
- 保证用户的显式问题是权威输入。

## 5. Helper CLI：初始化和配置

RepoMind 的 Skill 内部通过 `scripts/search.py` 管理本地 SQLite 数据库。脚本会自动发现当前 Git 项目根目录，也可以用 `--project-root` 指定项目根目录。

通用输入形式：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py <command>
python3 plugins/repomind/skills/repomind/scripts/search.py --project-root /path/to/project <command>
```

初始化输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py init
```

预期输出：

```json
{
  "status": "ok",
  "message": "Database initialized"
}
```

读取配置输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py config
```

预期输出：

```json
{
  "max_search_repos": 20,
  "min_relevance_score": 3.5,
  "card_similarity_threshold": 0.7,
  "empty_query_ttl_hours": 24,
  "freshness_min_days": 1,
  "freshness_max_days": 30,
  "freshness_default_days": 7,
  "freshness_commit_sample_size": 20,
  "freshness_stability_growth": 1.5,
  "freshness_change_decay": 0.5
}
```

主要功能：

- 创建 `.repomind/repomind.db`。
- 加载默认配置 `config/defaults.json`。
- 支持项目级 `.repomind/config.json` 覆盖默认配置，但不允许未知配置项。

## 6. Helper CLI：查询本地卡片

查询卡片数量输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py count
```

预期输出：

```json
{
  "count": 0
}
```

按关键词搜索输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py search scheduler workflow executor
```

预期输出：

```json
[
  {
    "id": 1,
    "dimension": "architecture",
    "title": "Airflow DAG Scheduling Architecture",
    "keywords": "scheduling,DAG,workflow,airflow,executor,orchestration",
    "created_at": "2026-07-12 08:00:00",
    "full_name": "apache/airflow",
    "url": "https://github.com/apache/airflow",
    "stars": 38000,
    "language": "Python",
    "is_stale": false,
    "relevance": 5.0
  }
]
```

读取所有卡片输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py all-cards
```

按 ID 读取完整卡片输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py get-cards 2 1
```

预期输出：

按传入 ID 顺序返回完整卡片内容，并带上仓库信息、freshness 字段和 `is_stale` 标记。

主要功能：

- 快速判断本地缓存是否有可用证据。
- 根据关键词计算简单相关性。
- 根据配置中的 freshness 上限标记过期证据。
- 为最终综合报告提供完整卡片内容。

## 7. Helper CLI：写入仓库和卡片

写入或更新仓库输入：

```bash
printf '%s' '{"full_name":"apache/airflow","url":"https://github.com/apache/airflow","language":"Python","topics":["workflow","scheduler"],"stars":38000,"description":"Airflow"}' \
  | python3 plugins/repomind/skills/repomind/scripts/search.py insert-repo -
```

预期输出：

```json
{
  "repo_id": 1
}
```

检查仓库是否存在输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py check-repo apache/airflow
```

预期输出：

```json
{
  "exists": true,
  "repo": {
    "id": 1,
    "full_name": "apache/airflow",
    "url": "https://github.com/apache/airflow"
  }
}
```

写入卡片输入：

```bash
printf '%s' '{"repo_id":1,"dimension":"architecture","title":"Airflow DAG Scheduling Architecture","content":"full content","keywords":"scheduling,DAG,workflow,airflow,executor,orchestration","research_object":"scheduler design","evidence_paths":["airflow/jobs/scheduler_job_runner.py"],"related_modules":["airflow/jobs"],"source_sha":"abc123","freshness_status":"fresh","card_updated_at":"2026-07-12T08:00:00Z"}' \
  | python3 plugins/repomind/skills/repomind/scripts/search.py insert-card -
```

预期输出：

```json
{
  "card_id": 1
}
```

去重写入卡片输入：

```bash
printf '%s' '{"repo_id":1,"dimension":"architecture","title":"Airflow DAG Scheduling Architecture","content":"full content","keywords":"scheduling,DAG,workflow,airflow,executor,orchestration"}' \
  | python3 plugins/repomind/skills/repomind/scripts/search.py insert-card-if-new -
```

预期输出：

```json
{
  "inserted": true,
  "card_id": 1,
  "duplicate_id": null
}
```

如果检测到相似卡片，则输出：

```json
{
  "inserted": false,
  "card_id": null,
  "duplicate_id": 1
}
```

主要功能：

- 持久化候选仓库元数据。
- 持久化结构化研究卡片。
- 通过标题和关键词相似度避免重复卡片。
- 保存证据路径、相关模块、source SHA 和 freshness 状态，为后续增量刷新提供依据。

## 8. Helper CLI：相似卡片检测

输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py check-similar "Airflow Task Scheduling Design" "scheduling,DAG,airflow,workflow,executor"
```

预期输出：

```json
{
  "similar_exists": true
}
```

主要功能：

- 使用标题 token 的 Jaccard 相似度和关键词 overlap coefficient。
- 阈值来自配置项 `card_similarity_threshold`，默认是 `0.7`。
- 用于插入前判断是否已有重复研究卡片。

## 9. Helper CLI：缓存新鲜度和仓库刷新

根据卡片 ID 查询对应仓库输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py repos-for-cards 1 2
```

预期输出：

```json
[
  {
    "id": 1,
    "full_name": "apache/airflow",
    "card_ids": [1, 2],
    "check_due": true
  }
]
```

记录一次仓库检查输入：

```bash
printf '%s' '{"repo_id":1,"outcome":"unchanged","head_sha":"abc123","default_branch":"main","checked_at":"2026-07-12T08:00:00Z","commit_timestamps":["2026-07-08T08:00:00Z","2026-07-10T08:00:00Z","2026-07-12T08:00:00Z"]}' \
  | python3 plugins/repomind/skills/repomind/scripts/search.py record-repo-check -
```

预期输出：

```json
{
  "repo_id": 1,
  "outcome": "unchanged",
  "last_checked_at": "2026-07-12T08:00:00Z",
  "next_check_at": "2026-07-15T08:00:00Z",
  "check_interval_days": 3.0,
  "stability_runs": 1
}
```

查询受影响卡片输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py affected-cards 1 src/core
```

也可以从 JSON 输入：

```bash
printf '%s' '{"repo_id":1,"paths":["src/core"]}' \
  | python3 plugins/repomind/skills/repomind/scripts/search.py affected-cards -
```

预期输出：

```json
{
  "card_ids": [1]
}
```

刷新卡片输入：

```bash
printf '%s' '{"repo_id":1,"head_sha":"newsha","status":"fresh","updated_at":"2026-07-12T08:00:00Z","outcome":"localized","replacements":[{"id":1,"repo_id":1,"dimension":"architecture","title":"Updated scheduler architecture","content":"updated evidence","keywords":"scheduler,executor","evidence_paths":["src/core.py"],"related_modules":["src"]}]}' \
  | python3 plugins/repomind/skills/repomind/scripts/search.py refresh-cards -
```

预期输出：

```json
{
  "repo_id": 1,
  "card_ids": [1],
  "head_sha": "newsha",
  "status": "fresh",
  "updated_at": "2026-07-12T08:00:00Z",
  "next_check_at": "2026-07-19T08:00:00Z",
  "check_interval_days": 7.0,
  "stability_runs": 0
}
```

主要功能：

- 判断缓存仓库是否到期需要检查。
- 记录 unchanged、unrelated、localized、global 四类检查结果。
- 根据 commit 间隔、稳定次数和变更类型自适应计算下次检查时间。
- 对 localized 变更只刷新受影响卡片。
- 对 legacy 映射不可靠的卡片要求 full refresh。
- `refresh-cards` 使用事务，失败时不会留下半更新状态。

## 10. Helper CLI：空查询记录

记录空结果查询输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py record-empty-query "agent scheduler"
```

预期输出：

```json
{
  "recorded": true
}
```

检查近期是否已经搜过且为空输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py recent-empty-query " agent   scheduler "
```

预期输出：

```json
{
  "recent": true
}
```

主要功能：

- 避免短时间内重复对同一个无结果 query 做 GitHub 搜索。
- query 会被 normalize，连续空格和大小写差异不会影响判断。
- TTL 来自配置项 `empty_query_ttl_hours`，默认是 24 小时。

## 11. Helper CLI：重置本地数据库

输入：

```bash
python3 plugins/repomind/skills/repomind/scripts/search.py reset-db
```

预期输出：

```json
{
  "status": "ok",
  "message": "Database reset"
}
```

主要功能：

- 删除 `.repomind/repomind.db` 以及 SQLite WAL/SHM 文件。
- 重新初始化数据库结构。
- 适合本地测试和开发调试，不适合作为普通用户的日常操作。

## 12. 内部 freshness.py 工具函数

`plugins/repomind/skills/repomind/scripts/freshness.py` 不是面向用户的 CLI，而是被 `search.py` 调用的确定性工具模块。

主要输入：

- `classify_repository_change(observation)`：接收仓库变更观察对象。
- `median_commit_interval_days(timestamps)`：接收提交时间戳数组。
- `calculate_check_interval(...)`：接收提交间隔、稳定次数、变更类型和配置边界。
- `is_check_due(next_check_at, now)`：接收下次检查时间和当前时间。

预期输出：

- `classify_repository_change` 输出 `unchanged`、`unrelated`、`localized` 或 `global`。
- `median_commit_interval_days` 输出提交间隔中位数，单位是天。
- `calculate_check_interval` 输出被最小值和最大值约束后的检查间隔。
- `is_check_due` 输出布尔值。

主要功能：

- 不依赖网络和外部服务。
- 通过路径重叠判断变更是否影响已有证据。
- 避免仅凭 commit 数量判断仓库是否需要刷新。
- 为本地缓存的新鲜度调度提供确定性逻辑。

## 13. 运行时文件和输入来源

RepoMind 的运行时状态默认写入当前项目根目录：

```text
.repomind/
  config.json
  repomind.db
  repomind.db-wal
  repomind.db-shm
```

项目根目录发现规则：

- 如果设置了 `REPOMIND_PROJECT_ROOT`，优先使用该路径。
- 否则执行 `git rev-parse --show-toplevel`。
- 如果当前目录不是 Git 仓库，则使用当前工作目录。
- CLI 也支持 `--project-root /path/to/project` 显式覆盖。

输入来源：

- 用户显式研究问题。
- 当前会话上下文。
- 轻量本地项目上下文，例如 README 或任务相关代码。
- 本地 `.repomind/` 缓存。
- 缓存不足时，通过 `gh` 搜索公开 GitHub 仓库。

预期输出位置：

- 面向用户的研究结果输出在 agent 对话中。
- 结构化仓库和卡片数据存入 SQLite。
- 配置覆盖写入 `.repomind/config.json`。

## 14. 总结

当前代码实现的使用方法可以分成两层：

面向最终用户的入口是 Codex 插件、Claude Code 插件和 standalone Agent Skill。它们的核心输入是一个工程设计或实现研究问题，核心输出是一份带证据、权衡和适配建议的研究报告。

面向 Skill 内部和开发调试的入口是 `scripts/search.py` 和 `freshness.py`。它们负责初始化数据库、读写卡片、去重、查询缓存、记录空查询、判断缓存新鲜度和执行增量刷新。

