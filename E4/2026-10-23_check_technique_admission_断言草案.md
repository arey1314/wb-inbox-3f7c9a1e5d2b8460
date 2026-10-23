# check_technique_admission() 技法入库断言 · 草案 v0.1

**编号**：2026-10-23_E4　**性质**：🔴 **草案·未复核·未交付 E3 施工**
**依据**：`2026-10-22_研究产出商用边界_裁定_v1.0.md`（A★ 裁定）+ `2026-10-22_数据集授权补判与红线改版_v1.1.md`（L0 四类锚点 + R-DATA-01~04）
**用途**：商用轨技法库入库前置断言 —— 研究轨 → 商用轨的**唯一闸门**

---

## 〇、定位（与既有断言的关系）

| 层 | 函数 | 管什么 |
|---|---|---|
| 语料层 | `check_dataset_admission()`（v1.1 已交付） | 数据集能否进研究轨/商用轨 |
| **技法层** | **`check_technique_admission()`（本草案）** | 技法条目能否进**商用轨技法库** |

两层串联：语料过 `check_dataset_admission()` → 产出技法再过 `check_technique_admission()`。

---

## 一、常量定义

```python
# L0 合规锚点四类（v1.1 定稿，商用轨唯一合法来源）
L0_ANCHORS = {
    "customer_kb":   "客户授权知识库/SOP（须授权书 + PII 脱敏）",
    "public_rules":  "公开行业规则资料（非对话，如退换货/退费政策）",
    "paid_dataset":  "付费数据集（须归档授权书/发票，范围覆盖产品化）",
    "confirmed_llm": "大模型行业知识，经客户书面确认后升格",
}

# 商用轨源黑名单（合同/许可限制型 → C 硬禁）
# 🔴 须法务书面背书后置 legal_block_enabled=True；未背书前仅告警不拦截
RESEARCH_ONLY_SOURCES = {
    "JDDC":         "学术协议：商业产品不得直接或间接使用",
    "CallCenterEN": "CC BY-NC 4.0：NC 条件对演绎/改编同样生效，商用派生违规",
}

# 合成源：语料禁入，仅框架/方法论可借鉴（须 schema_only 去语料化）
SYNTHETIC_SOURCES = {"Kapibala", "SalesLLM-10k", "CCSE-CS", "QingshanAI"}

ALLOWED_LICENSE_STATUS = {"owned", "public", "licensed"}
FORBIDDEN_LICENSE_STATUS = {"unconfirmed", "synthetic_pending", None}
ALLOWED_DERIVATION = {"clean_room", "schema_only", "human_authored"}
FORBIDDEN_DERIVATION = {"extracted_from_research", "verbatim_from_research"}
COMMERCIAL_TRACK = "commercial"

REQUIRED_FIELDS = ("technique_id", "source", "anchor_type", "license_status",
                   "derivation", "origin_track")
```

---

## 二、断言函数

```python
def check_technique_admission(entry, legal_block_enabled=False):
    """商用轨技法入库前置断言。

    参数
        entry: dict，必含 REQUIRED_FIELDS；可选 legal_signoff / analysis_origin /
               similarity_hit / technique_text
        legal_block_enabled: bool，法务对 RESEARCH_ONLY_SOURCES 黑名单背书后置 True

    返回
        (ok: bool, reasons: list[str])  —— 任一闸门不满足即拒，reasons 逐条列明
    """
    reasons = []

    # G0 必填字段（缺省等同 unconfirmed → 拒）
    for f in REQUIRED_FIELDS:
        if not entry.get(f):
            reasons.append("G0 缺必填字段: %s" % f)

    # G1 轨道隔离：研究轨产物不得直接进商用库
    if entry.get("origin_track") != COMMERCIAL_TRACK:
        reasons.append("G1 origin_track 必须为 commercial；"
                       "研究轨产物须经清洁室再派生后方可申请")

    # G2 许可状态白名单
    if entry.get("license_status") not in ALLOWED_LICENSE_STATUS:
        reasons.append("G2 license_status 须为 owned/public/licensed 之一"
                       "（unconfirmed/synthetic_pending/None 一律拒）")

    # G3 锚点类型（仅四类 L0）
    if entry.get("anchor_type") not in L0_ANCHORS:
        reasons.append("G3 anchor_type 须属 L0 四类锚点: %s"
                       % "/".join(sorted(L0_ANCHORS)))

    # G4 源黑名单（合同/许可限制型）
    src = entry.get("source") or ""
    if src in RESEARCH_ONLY_SOURCES:
        msg = "G4 源 %s 属合同/许可限制型，商用轨禁入（%s）" % (
            src, RESEARCH_ONLY_SOURCES[src])
        reasons.append(msg + ("【法务拦截已启用】" if legal_block_enabled
                              else "【⚠️未启用法务拦截，仅告警——须法务背书】"))

    # G4b 合成源：仅允许框架借鉴（schema_only），语料/逐字禁入
    if src in SYNTHETIC_SOURCES and entry.get("derivation") != "schema_only":
        reasons.append("G4b 合成源仅允许 derivation=schema_only（框架借鉴）；"
                       "语料入库或逐字沿用一律拒")

    # G5 派生方式黑名单
    if entry.get("derivation") in FORBIDDEN_DERIVATION:
        reasons.append("G5 derivation 含研究轨提取/逐字沿用，禁入")

    # G6 分析原点回溯受限/合成源 → 强制法务签字
    origins = entry.get("analysis_origin") or []
    if isinstance(origins, str):
        origins = [origins]
    hit = [o for o in origins
           if o in RESEARCH_ONLY_SOURCES or o in SYNTHETIC_SOURCES]
    if hit and not entry.get("legal_signoff"):
        reasons.append("G6 分析原点含受限/合成源 %s，须 legal_signoff 法务签字" % hit)

    # G7 无近接：与研究轨语料的相似度闸门结果（由扫描器预计算后注入）
    if entry.get("similarity_hit"):
        reasons.append("G7 条目文本与研究轨语料近接（相似度闸门命中），禁入")

    # G8 零对话原文：超长自然语言疑含原文，转人工
    text = entry.get("technique_text") or ""
    if len(text) > 400:
        reasons.append("G8 technique_text 超长（>400 字符），疑含对话原文，转人工复核")

    return (len(reasons) == 0, reasons)
```

---

## 三、使用示例

```python
entry_ok = {
    "technique_id": "T-EMO-014",
    "source": "customer_kb:chuanyunbao_faq_v3",
    "anchor_type": "customer_kb",
    "license_status": "owned",
    "derivation": "human_authored",
    "origin_track": "commercial",
    "analysis_origin": ["public_rules"],
    "legal_signoff": "",
    "similarity_hit": False,
    "technique_text": "客户表达不满时，先确认情绪再给方案，避免直接跳转结论。",
}
# check_technique_admission(entry_ok)  -> (True, [])

entry_bad = {
    "technique_id": "T-EMO-015",
    "source": "JDDC",
    "anchor_type": "customer_kb",
    "license_status": "licensed",
    "derivation": "extracted_from_research",
    "origin_track": "research",
    "technique_text": "……（长段对话原文）……",
}
# -> (False, ["G1 ...", "G4 源 JDDC ...", "G5 ...", "G8 ..."])
```

---

## 四、待办 / 边界

1. 🔴 **G4 黑名单段须法务书面背书**后方可 `legal_block_enabled=True`；未背书前仅告警（已按此实现，防误伤）。
2. G7 相似度闸门为**外部注入**：由 E3 相似度扫描器对研究轨全量语料预计算（阈值：任意连续 ≥12 词命中即 `similarity_hit=True`），本函数不内嵌扫描逻辑。
3. 物理隔离（独立 repo/DB/环境）与 `origin_track` 字段落地归 E3；本草案只定义**判定逻辑**。
4. 🔴 本文件为**草案**，未经 C0 批准不得进生产；不得据此直接改动线上库。
5. 与 v1.1 `check_dataset_admission()` 共用 `L0_ANCHORS` / `SYNTHETIC_SOURCES` 常量，避免两处定义漂移——建议提取为同一 `admission_constants.py`。

> 边界说明：本草案 0 服务器写操作、不含任何凭据/客户信息/未脱敏数据；涉 JDDC/CC BY-NC 的禁入判定为合同与许可层判断，**最终以法务书面意见为准**。
