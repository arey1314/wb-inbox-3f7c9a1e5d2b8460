# E2 正式回报 2026-10-24（第三十六轮：D2 角色改造交付）

## 一、D2 主体：客服视野只剩「粘贴 + 选档位」（C0 定稿一次做对）
- **删除 4 块选择器**：选择角色 / 客户性别 / 方言 / 高级设置（方言浓度）——HTML+JS 全下线
- grep 实证：选择角色=0、id="roleList"=0、id="genderSeg"=0、id="dialectSel"=0、id="dlSeg"=0、请先选择角色=0
- 新增只读「当前配置」行（cfgHint）：显示 行业·岗位·称呼（由开通配置决定，零动作）
- 档位选择保留（lite/standard/deep + deep 1/3 条）；粘贴框+生成按钮保留

## 二、D1 收尾：role_alias 兼容读（uid291 旧格式实测通过）
- 后端 /api/wecom/prefs 读侧增强：旧格式 {role,gender,dialect} → 自动派生 {industry,post,channel,salutation}
- uid291 实测：旧 {role:service_ec_pre,...} → industry=service_ec_pre / channel=online / salutation=["您"] / banned=["亲爱的"]，engine/deep_num 档位不丢，旧字段保留可回滚
- 存量已转存新格式：industry=service_ec_pre / post=ec_after / channel=online（回读 alias_from=None=干净）

## 三、称呼跟行业走（P0 项，已接入流式链）
- prefs GET 返回 salutation/salutation_banned（源=shared/industry_role_map.json）
- 流式链注入：gather→handler→call_main_stream_first→_build_reply_prompt 全链透传 salutation
- prompt 注入行：「称呼要求：对客户使用「您」类称呼；禁用「亲爱的」…」（银行/航司禁亲爱的用您；美业已去"姐"=映射表内 CAT15 配置）
- 端到端冒烟：uid291 standard 生成扣费 14 积分（余额 8000→7867）、流式正常、[DONE] 收尾

## 四、基线与安全
- rsp 新基线 md5 0a88fff5（size ~248KB，链 .bak_d2_pre→现值）；py_compile OK；restart 后 active
- 公网首页/登录页双 200；V17.2 受保护块（老板拍板/_AUTO_SCENE_RULES）完好未碰
- 阻塞链（8080 serve_blocking）未动；性别/方言后端 if 守卫保留（不传不注入，天然兼容）

## 五、待办
- 四环接线（decision_cards 加 official_fail→hard/缺环≥2→soft，观测模式）
- 埋点四事件（复制/直发/编辑后发/弃用）
