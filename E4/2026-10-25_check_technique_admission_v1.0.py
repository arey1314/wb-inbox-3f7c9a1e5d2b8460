#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_technique_admission.py v1.0（置位版）
E4 合规 · 2026-10-25
研究轨 → 商用轨技法入库唯一闸门（C0 正式采信）

v0.1 → v1.0 变更：
  1. LEGAL_BLOCK_ENABLED 默认 True —— C0 2026-10-25 裁决「C0 即背书人，按 A★ 正式拦截」，
     G4 黑名单命中即拒（不再仅告警）。回退须 C0 书面指令。
  2. 兼容 E1 规范 v1.1 引用格式：legal_signoff 与 approval_ref 互为别名。
  3. 内置自检 main：四条实测用例（受限源拦截 / 合成语料拦截 / 缺字段拦截 / 干净条目放行）。

依据：
  - A★ 裁定（2026-10-22_研究产出商用边界_裁定_v1.0）
  - L0 四类锚点 + R-DATA-01~04（2026-10-22_数据集授权补判与红线改版_v1.1）
  - C0 置位裁决（E4_20261024_gate_enable / E4_20261025_zhamen_zhiwei）
"""

# ───────────────────────── 常量 ─────────────────────────

LEGAL_BLOCK_ENABLED = True  # 🔴 2026-10-25 C0 置位。回退须 C0 书面指令。

# L0 合规锚点四类（商用轨唯一合法来源，v1.1 定稿）
L0_ANCHORS = {
    "customer_kb":   "客户授权知识库/SOP（须授权书 + PII 脱敏）",
    "public_rules":  "公开行业规则资料（非对话，如退换货/退费政策）",
    "paid_dataset":  "付费数据集（须归档授权书/发票，范围覆盖产品化）",
    "confirmed_llm": "大模型行业知识，经客户书面确认后升格",
}

# 商用轨源黑名单（合同/许可限制型 → C 硬禁，最终名单）
RESEARCH_ONLY_SOURCES = {
    "JDDC":         "京东对话语料：学术协议禁止商业产品直接或间接使用",
    "CallCenterEN": "CC BY-NC 4.0：NC 条件对演绎/改编同样生效，商用派生违规",
}

# 合成源：语料禁入；仅允许 schema_only（框架/标签体系借鉴）
SYNTHETIC_SOURCES = {"Kapibala", "SalesLLM-10k", "CCSE-CS", "QingshanAI"}

ALLOWED_LICENSE_STATUS = {"owned", "public", "licensed"}
FORBIDDEN_LICENSE_STATUS = {"unconfirmed", "synthetic_pending", None}
ALLOWED_DERIVATION = {"clean_room", "schema_only", "human_authored"}
FORBIDDEN_DERIVATION = {"extracted_from_research", "verbatim_from_research"}
COMMERCIAL_TRACK = "commercial"

REQUIRED_FIELDS = ("technique_id", "source", "anchor_type", "license_status",
                   "derivation", "origin_track")


# ─────────────────────── 断言函数 ───────────────────────

def check_technique_admission(entry, legal_block_enabled=LEGAL_BLOCK_ENABLED):
    """商用轨技法入库前置断言。

    entry 必含 REQUIRED_FIELDS；可选字段：
      legal_signoff / approval_ref（别名，任一即可）
      analysis_origin（分析原点来源列表）
      similarity_hit（E3 相似度扫描器预计算注入；None=未扫描）
      technique_text（条目正文）

    返回 (ok, reasons, warnings)
      ok=False        → 拒绝入库（reasons 逐条列明闸门命中）
      ok=True         → 放行；warnings 非空 = 放行但强制人工复核（降级/转人工）
      warnings 为空   → 干净放行
    """
    reasons = []    # 拦截项（命中即拒）
    warnings = []   # 转人工项（放行但必须人工复核）

    # G0 必填字段（缺省等同 unconfirmed → 拒）
    for f in REQUIRED_FIELDS:
        if not entry.get(f):
            reasons.append("G0 缺必填字段: %s" % f)

    # G1 轨道隔离：研究轨产物不得直接进商用库
    if entry.get("origin_track") != COMMERCIAL_TRACK:
        reasons.append("G1 origin_track 必须为 commercial；研究轨产物须经清洁室再派生")

    # G2 许可状态白名单
    if entry.get("license_status") not in ALLOWED_LICENSE_STATUS:
        reasons.append("G2 license_status 须为 owned/public/licensed 之一")

    # G3 锚点类型（仅四类 L0）
    if entry.get("anchor_type") not in L0_ANCHORS:
        reasons.append("G3 anchor_type 须属 L0 四类锚点: %s" % "/".join(sorted(L0_ANCHORS)))

    # G4 商用源黑名单（合同/许可限制型）
    src = entry.get("source") or ""
    if src in RESEARCH_ONLY_SOURCES:
        reasons.append("G4 【已拦截】源 %s 属合同/许可限制型，商用轨禁入（%s）"
                       % (src, RESEARCH_ONLY_SOURCES[src])
                       if legal_block_enabled else
                       "G4 【仅告警】源 %s 属受限源（法务拦截未启用）" % src)

    # G4b 合成源：仅允许 schema_only（框架借鉴），语料/逐字禁入
    if src in SYNTHETIC_SOURCES and entry.get("derivation") != "schema_only":
        reasons.append("G4b 【已拦截】合成源 %s 仅允许 derivation=schema_only；"
                       "语料入库或逐字沿用一律拒" % src)

    # G5 派生方式黑名单
    if entry.get("derivation") in FORBIDDEN_DERIVATION:
        reasons.append("G5 【已拦截】derivation=%s 含研究轨提取/逐字沿用" % entry.get("derivation"))

    # G6 分析原点回溯受限/合成源 → 强制法务签字（legal_signoff 与 approval_ref 等效）
    signoff = entry.get("legal_signoff") or entry.get("approval_ref")
    origins = entry.get("analysis_origin") or []
    if isinstance(origins, str):
        origins = [origins]
    hit = [o for o in origins if o in RESEARCH_ONLY_SOURCES or o in SYNTHETIC_SOURCES]
    if hit and not signoff:
        reasons.append("G6 【已拦截】分析原点含受限/合成源 %s，须 legal_signoff/approval_ref 法务签字" % hit)

    # G7 无近接（E3 相似度扫描器外部注入，降级契约见交付 E3 文档）
    #   True=命中 → 拦；False=已扫描未命中 → 放行；None/缺失=未扫描 → 降级放行+强制人工复核
    if entry.get("similarity_hit") is True:
        reasons.append("G7 【已拦截】条目文本与研究轨语料近接（连续>=12 词命中）")
    elif entry.get("similarity_hit") is None:
        warnings.append("G7 【降级】相似度扫描器未交付（similarity_hit=None）："
                        "放行但强制人工复核，条目须进合规抽检池")

    # G8 零对话原文：超长自然语言疑含原文 → 放行但强制人工复核
    text = entry.get("technique_text") or ""
    if len(text) > 400:
        warnings.append("G8 转人工：technique_text 超长（>400 字符），疑含对话原文")

    return (len(reasons) == 0, reasons, warnings)


# ─────────────────────── 自检实测 ───────────────────────

if __name__ == "__main__":
    print("LEGAL_BLOCK_ENABLED =", LEGAL_BLOCK_ENABLED)
    print("=" * 60)

    # 实测 1：受限源 JDDC（研究轨产物直投）→ 必须被拦
    t1 = {"technique_id": "T-TEST-001", "source": "JDDC",
          "anchor_type": "customer_kb", "license_status": "licensed",
          "derivation": "extracted_from_research", "origin_track": "research"}
    ok1, r1, w1 = check_technique_admission(t1)
    print("实测1 JDDC受限源      ->", "被拦" if not ok1 else "!!漏放!!")
    for x in r1: print("   -", x)

    # 实测 2：CC BY-NC 源 → 必须被拦
    t2 = {"technique_id": "T-TEST-002", "source": "CallCenterEN",
          "anchor_type": "paid_dataset", "license_status": "licensed",
          "derivation": "clean_room", "origin_track": "commercial"}
    ok2, r2, w2 = check_technique_admission(t2)
    print("实测2 CallCenterEN    ->", "被拦" if not ok2 else "!!漏放!!")
    for x in r2: print("   -", x)

    # 实测 3：合成源作语料（非 schema_only）→ 必须被拦
    t3 = {"technique_id": "T-TEST-003", "source": "Kapibala",
          "anchor_type": "public_rules", "license_status": "public",
          "derivation": "clean_room", "origin_track": "commercial",
          "similarity_hit": False}
    ok3, r3, w3 = check_technique_admission(t3)
    print("实测3 合成源作语料    ->", "被拦" if not ok3 else "!!漏放!!")
    for x in r3: print("   -", x)

    # 实测 4：干净条目（L0-A 客户知识库 + 人工撰写）→ 必须放行且零告警
    t4 = {"technique_id": "T-TEST-004", "source": "customer_kb:faq_v3",
          "anchor_type": "customer_kb", "license_status": "owned",
          "derivation": "human_authored", "origin_track": "commercial",
          "similarity_hit": False, "technique_text": "客户表达不满时，先确认情绪再给方案。"}
    ok4, r4, w4 = check_technique_admission(t4)
    print("实测4 干净条目        ->", "干净放行" if ok4 and not r4 and not w4 else "!!异常!!")
    for x in r4 + w4: print("   -", x)

    # 实测 5：G7 降级（扫描器未交付）→ 放行但强制人工复核（warning，非拒绝）
    t5 = dict(t4, technique_id="T-TEST-005", similarity_hit=None)
    ok5, r5, w5 = check_technique_admission(t5)
    g7 = [x for x in w5 if x.startswith("G7")]
    print("实测5 G7降级          ->", "放行+强制人工复核" if ok5 and g7 else "!!异常!!")
    for x in g7: print("   -", x)

    # 实测 6：G8 超长疑含原文 → 放行但转人工
    t6 = dict(t4, technique_id="T-TEST-006", technique_text="长" * 401)
    ok6, r6, w6 = check_technique_admission(t6)
    g8 = [x for x in w6 if x.startswith("G8")]
    print("实测6 G8超长转人工    ->", "放行+转人工" if ok6 and g8 else "!!异常!!")
    for x in g8: print("   -", x)

    print("=" * 60)
    verdict = (not ok1) and (not ok2) and (not ok3) and ok4 and ok5 and ok6
    print("置位验证总结论：", "PASS（真拦截，非仅告警）" if verdict else "FAIL")
