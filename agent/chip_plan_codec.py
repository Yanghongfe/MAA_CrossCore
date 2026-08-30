# -*- coding: utf-8 -*-
"""Portable, offline share codes for chip lock-filter plans."""

from __future__ import annotations

import base64
import hashlib
import json
import zlib

from chip_filter_flow import MAIN_SKILLS, SUB_SKILLS


CODE_PREFIX = "LAA-CF1"
MAX_CODE_LENGTH = 32768
MAX_JSON_BYTES = 65536


class PlanCodeError(ValueError):
    pass


def _level(value, label):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise PlanCodeError("%s必须是1、2或3" % label) from exc
    if result not in (1, 2, 3):
        raise PlanCodeError("%s必须是1、2或3" % label)
    return result


def normalize_plan(plan):
    """Keep only portable filter semantics and return canonical rule ordering."""
    if not isinstance(plan, dict):
        raise PlanCodeError("方案数据格式错误")
    name = str(plan.get("name", "")).strip()
    if not name or len(name) > 40:
        raise PlanCodeError("方案名称不能为空且不能超过40个字符")

    source_rules = plan.get("rules")
    if not isinstance(source_rules, list) or not 1 <= len(source_rules) <= 100:
        raise PlanCodeError("方案必须包含1至100条主技能规则")

    rules = []
    for source in source_rules:
        if not isinstance(source, dict):
            raise PlanCodeError("主技能规则格式错误")
        main_skill = str(source.get("main_skill", ""))
        if main_skill not in MAIN_SKILLS:
            raise PlanCodeError("未知主技能：%s" % main_skill)
        main_level = _level(source.get("main_level"), "主技能最低等级")

        source_subs = source.get("sub_skills", [])
        if not isinstance(source_subs, list) or len(source_subs) > len(SUB_SKILLS):
            raise PlanCodeError("副技能条件格式错误")
        sub_map = {}
        for sub in source_subs:
            if not isinstance(sub, dict):
                raise PlanCodeError("副技能条件格式错误")
            sub_name = str(sub.get("name", ""))
            if sub_name not in SUB_SKILLS:
                raise PlanCodeError("未知副技能：%s" % sub_name)
            if sub_name in sub_map:
                raise PlanCodeError("副技能重复：%s" % sub_name)
            sub_map[sub_name] = _level(sub.get("level"), "%s最低等级" % sub_name)

        try:
            required = int(source.get("sub_required", len(sub_map)))
        except (TypeError, ValueError) as exc:
            raise PlanCodeError("副技能满足数量必须是整数") from exc
        if not 0 <= required <= len(sub_map):
            raise PlanCodeError("副技能满足数量超出已选条件范围")

        rules.append({
            "main_skill": main_skill,
            "main_level": main_level,
            "sub_skills": [
                {"name": sub_name, "level": sub_map[sub_name]}
                for sub_name in SUB_SKILLS if sub_name in sub_map
            ],
            "sub_required": required,
        })

    main_order = {name: index for index, name in enumerate(MAIN_SKILLS)}
    rules.sort(key=lambda rule: (
        main_order[rule["main_skill"]],
        rule["main_level"],
        json.dumps(rule["sub_skills"], ensure_ascii=False, sort_keys=True),
        rule["sub_required"],
    ))
    return {"version": 1, "name": name, "rules": rules}


def encode_plan_code(plan):
    normalized = normalize_plan(plan)
    raw = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    packed = zlib.compress(raw, level=9)
    checksum = hashlib.sha256(packed).hexdigest()[:10]
    payload = base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")
    return "%s-%s-%s" % (CODE_PREFIX, checksum, payload)


def decode_plan_code(code):
    value = "".join(str(code or "").split())
    if len(value) > MAX_CODE_LENGTH:
        raise PlanCodeError("方案码过长")
    prefix = CODE_PREFIX + "-"
    if not value.startswith(prefix):
        raise PlanCodeError("不是受支持的LAA芯片方案码")
    remainder = value[len(prefix):]
    try:
        checksum, payload = remainder.split("-", 1)
        packed = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    except Exception as exc:
        raise PlanCodeError("方案码内容损坏") from exc
    if hashlib.sha256(packed).hexdigest()[:10] != checksum:
        raise PlanCodeError("方案码校验失败")

    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(packed, MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES or decompressor.unconsumed_tail:
            raise PlanCodeError("方案数据过大")
        raw += decompressor.flush()
        if len(raw) > MAX_JSON_BYTES:
            raise PlanCodeError("方案数据过大")
        decoded = json.loads(raw.decode("utf-8"))
    except PlanCodeError:
        raise
    except Exception as exc:
        raise PlanCodeError("方案码无法解析") from exc
    return normalize_plan(decoded)
