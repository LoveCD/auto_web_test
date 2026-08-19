# -*- coding: utf-8 -*-
"""工程统一配置模块。

职责：
  - 加载工程根 .env（极简实现，无第三方依赖）
  - 解析 ${VAR} / ${VAR:-default} 占位符（用于 profile.json / 用例 JSON）

设计动机：
  真机地址与账号等敏感信息不写死在配置文件中，而是由环境变量或
  本地 .env 注入（.env 已被 .gitignore 排除），从而可将本工程安全地
  公开发布到 GitHub，他人克隆后只需复制 .env.example 为 .env 并填写
  自己的设备信息即可运行。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RE_ENV_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def load_dotenv(path=None):
    """加载 .env 文件到 os.environ（已存在的变量不覆盖）。"""
    p = path or os.path.join(ROOT, ".env")
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ.setdefault(key, value)


def resolve_env_value(value):
    """把字符串中的 ${VAR} / ${VAR:-default} 替换为环境变量值。"""
    if not isinstance(value, str):
        return value

    def substitute(m):
        name, default = m.group(1), m.group(2)
        if name in os.environ and os.environ[name] != "":
            return os.environ[name]
        return default if default is not None else ""

    return RE_ENV_PLACEHOLDER.sub(substitute, value)


def resolve_config(obj):
    """递归解析 dict/list 中所有字符串值的环境变量占位符（就地修改）。"""
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            obj[k] = resolve_config(obj[k])
        return obj
    if isinstance(obj, list):
        return [resolve_config(item) for item in obj]
    return resolve_env_value(obj)


# 模块导入时加载一次 .env，保证各入口（runner/generator）无需重复调用
load_dotenv()
