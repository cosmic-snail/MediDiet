# MediDiet 前端功能端到端验证文档

版本：0.1.0  
目标读者：前端开发、QA、产品验收人员、后端联调人员。

## 1. 验证目标

本文档用于验证推荐引擎微信小程序前端原型在真实 HTTP 后端下的端到端功能表现，并引入大模型作为辅助验收器，检查页面语义、角色流程和解释文本是否符合产品预期。

端到端验证覆盖三类角色：

- 患者：补录摄入、发起推荐、查看推荐结果、查看后端错误兜底。
- 营养师：查看待审核队列、阅读 trace 证据链、确认/修改/驳回推荐。
- 配餐管理人员：查看菜单质量、切换可售状态、处理轻量履约。

大模型只用于辅助判断页面是否“表达正确、信息完整、风险提示合理”。确定性功能仍必须由 Playwright、Vitest、HTTP 响应断言和后端测试兜底。

## 2. 验证边界

必须由确定性断言验证：

- 页面是否加载成功。
- 按钮是否可点击。
- API 是否按预期调用。
- 推荐结果是否包含后端返回的 `traceId`。
- 推荐状态是否从本地初始状态更新为后端结果。
- 后端错误时是否保留当前推荐结果。
- 三类角色切换入口是否存在。

可以由大模型辅助验证：

- 患者端文案是否能让普通患者理解。
- 营养师端 trace 信息是否足够支持审核判断。
- 配餐端菜单质量和可售状态是否表达清楚。
- 页面是否像移动端小程序，不像桌面后台或营销页。
- 异常状态是否明确、不过度吓人、不提供未经审核的医学结论。

大模型不得作为唯一通过依据：

- 不用大模型判断接口是否真的调用成功。
- 不用大模型判断医学规则是否正确。
- 不用大模型覆盖敏感字段脱敏、鉴权、审计等合规测试。
- 不用大模型替代后端推荐引擎单元测试。

## 3. 环境准备

在仓库根目录启动后端：

```bash
uvicorn medidiet.server:app --app-dir src --host 127.0.0.1 --port 8000
```

在前端目录启动 Vite：

```bash
cd apps/mini-program-prototype
npm install
npm run dev -- --host 127.0.0.1
```

默认访问地址：

```text
http://127.0.0.1:5173/
```

前端会把 `/api/*` 代理到：

```text
http://127.0.0.1:8000/*
```

## 4. 基础自动化验证

每次端到端验证前先运行本地确定性测试：

```bash
cd apps/mini-program-prototype
npm run test
npm run build
```

预期结果：

- `npm run test` 全部通过。
- `npm run build` 成功生成 `dist`。

后端基础测试：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

如果只做前端联调烟测，至少确认：

```bash
curl http://127.0.0.1:8000/health
```

预期返回服务健康状态。

## 5. 端到端主流程

### 5.1 患者获取后端推荐

步骤：

1. 打开 `http://127.0.0.1:5173/`。
2. 确认默认进入“患者”角色。
3. 点击“获取下一餐推荐”。
4. 等待推荐结果区域刷新。

确定性断言：

- 页面出现“推荐状态：已生成推荐”。
- 页面出现“清蒸鱼套餐”。
- 页面 trace id 不再是本地初始值 `trace-7c4e3608`。
- 页面不出现“推荐服务暂不可用”。
- 后端日志出现 `GET /debug/state`、`PUT /patients/demo-patient`、`PUT /menus/today`、`POST /recommendations`。

大模型辅助验收问题：

```text
你是医疗营养小程序的前端验收助手。请根据页面截图和页面文本判断：
1. 当前页面是否清楚表达了患者已经获得下一餐推荐？
2. 推荐原因是否面向患者可理解，且没有给出越界医学承诺？
3. trace id 是否以辅助追溯信息呈现，而不是干扰患者主要决策？
请只输出 JSON：{"pass": boolean, "risks": string[], "suggestions": string[]}
```

通过标准：

- 大模型输出 `pass: true`。
- 如存在 `risks`，必须由人工确认是否为真实问题。
- 即使大模型通过，确定性断言失败时仍判定不通过。

### 5.2 后端服务不可用兜底

步骤：

1. 停止后端服务。
2. 保持前端服务运行。
3. 打开患者工作台。
4. 点击“获取下一餐推荐”。

确定性断言：

- 页面出现“推荐服务暂不可用”。
- 页面保留上一条推荐结果，不清空推荐区域。
- 页面仍可切换到营养师和配餐角色。

大模型辅助验收问题：

```text
请检查这个小程序错误状态是否适合患者端展示：
1. 是否明确告诉用户推荐服务暂不可用？
2. 是否保留了已有推荐，避免页面突然空白？
3. 文案是否避免制造医疗恐慌？
输出 JSON：{"pass": boolean, "risks": string[], "suggestions": string[]}
```

### 5.3 营养师审核闭环

步骤：

1. 在患者端点击“模拟等待营养师审核”。
2. 切换到“营养师”。
3. 查看待审核队列和 trace 证据链。
4. 点击“确认推荐”。
5. 切回“患者”。

确定性断言：

- 营养师端出现待审核推荐。
- trace 区域包含 outcome、risk、safety、rule、scores 等证据。
- 点击确认后营养师端显示“暂无待审核推荐”。
- 患者端显示“推荐状态：已生成推荐”。
- 患者端解释包含营养师确认后的说明。

大模型辅助验收问题：

```text
你是医疗审核工作台验收助手。请根据页面截图和文本判断：
1. 营养师是否能看到足够的推荐证据链？
2. 审核动作是否清晰区分确认、修改、驳回？
3. 审核通过后，患者端是否能理解这是已确认结果？
输出 JSON：{"pass": boolean, "risks": string[], "suggestions": string[]}
```

### 5.4 营养师驳回闭环

步骤：

1. 切换到“营养师”。
2. 点击“驳回推荐”。
3. 切回“患者”。

确定性断言：

- 患者端标题出现“需要处理”。
- 页面出现“推荐状态：拒绝推荐”。
- 页面解释包含营养师未通过原因。

大模型辅助验收问题：

```text
请判断患者端驳回状态是否清楚、安全：
1. 是否明确说明当前推荐未通过？
2. 是否避免把驳回说成患者病情恶化？
3. 是否给出了下一步处理方向？
输出 JSON：{"pass": boolean, "risks": string[], "suggestions": string[]}
```

### 5.5 配餐管理端菜单质量

步骤：

1. 切换到“配餐”。
2. 查看菜单列表。
3. 点击“下架清蒸鱼套餐”。
4. 查看营养详情和“已确认餐食”区域。
5. 点击“标记已备餐”。

确定性断言：

- 菜单列表展示菜品名、价格、营养置信度、标签和可售状态。
- 下架后对应菜品状态发生变化。
- 营养详情包含能量、碳水、蛋白质、钠。
- 履约状态可从待处理变为已备餐。

大模型辅助验收问题：

```text
你是医院配餐管理端验收助手。请根据页面截图和文本判断：
1. 菜单可售状态是否清晰？
2. 营养置信度是否足够显眼，方便运营识别“数据待补”的菜品？
3. 履约动作是否明确，不会和营养审核混淆？
输出 JSON：{"pass": boolean, "risks": string[], "suggestions": string[]}
```

## 6. 大模型验收接入建议

建议新增独立 E2E 脚本目录：

```text
apps/mini-program-prototype/e2e/
```

建议脚本分层：

- `smoke.spec.ts`：Playwright 确定性端到端测试。
- `llm-review.ts`：调用大模型，对截图和 DOM 文本做语义验收。
- `prompts.ts`：集中维护验收 prompt。
- `fixtures.ts`：维护角色路径、预期文案和风险关键词。

建议环境变量：

```bash
FRONTEND_E2E_LLM_PROVIDER=openai_compatible
FRONTEND_E2E_LLM_BASE_URL=https://example.com/v1
FRONTEND_E2E_LLM_API_KEY=...
FRONTEND_E2E_LLM_MODEL=...
FRONTEND_E2E_LLM_ENABLED=1
```

如果复用后端已有 OpenAI-compatible 配置，也可以直接使用：

```bash
MEDIDIET_LLM_PROVIDER=openai_compatible
MEDIDIET_LLM_BASE_URL=...
MEDIDIET_LLM_API_KEY=...
MEDIDIET_LLM_MODEL=...
```

大模型输入建议包含：

- 当前角色。
- 当前测试场景。
- 页面可见文本。
- 移动端截图。
- 确定性断言结果摘要。
- 不允许模型做出的判断边界。

大模型输出必须要求 JSON，便于 CI 或本地脚本解析：

```json
{
  "pass": true,
  "risks": [],
  "suggestions": []
}
```

## 7. 推荐 Playwright 骨架

建议安装：

```bash
cd apps/mini-program-prototype
npm install -D @playwright/test
npx playwright install chromium
```

建议添加脚本：

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:llm": "FRONTEND_E2E_LLM_ENABLED=1 playwright test"
  }
}
```

示例测试骨架：

```ts
import { expect, test } from '@playwright/test';

test('patient can request backend recommendation', async ({ page }) => {
  await page.goto('http://127.0.0.1:5173/');
  await page.getByRole('button', { name: '获取下一餐推荐' }).click();

  await expect(page.getByText('推荐状态：已生成推荐')).toBeVisible();
  await expect(page.getByText('清蒸鱼套餐')).toBeVisible();
  await expect(page.getByText('推荐服务暂不可用')).toHaveCount(0);

  const body = await page.locator('body').innerText();
  expect(body).not.toContain('trace-7c4e3608');
});
```

大模型验收应在确定性断言之后执行：

```ts
const visibleText = await page.locator('body').innerText();
const screenshot = await page.screenshot({ fullPage: true });
const llmReview = await reviewPageWithLLM({
  role: 'patient',
  scenario: 'backend recommendation success',
  visibleText,
  screenshot,
  deterministicAssertionsPassed: true
});

expect(llmReview.pass).toBe(true);
```

## 8. CI 分层建议

每次提交必须跑：

```bash
cd apps/mini-program-prototype
npm run test
npm run build
```

每次合并前建议跑：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
cd apps/mini-program-prototype
npm run test:e2e
```

大模型 E2E 不建议作为每次提交的硬门禁，原因是：

- 网络和供应商可用性不稳定。
- 模型输出存在随机性。
- 成本和耗时高于普通测试。

建议触发时机：

- 重要 UI 调整后。
- 角色流程调整后。
- 推荐解释文案调整后。
- 发布候选版本前。

CI 中的大模型验收建议作为“人工复核信号”：

- `pass: true` 且无高风险项：可以继续。
- `pass: false` 或存在高风险项：阻断发布候选，需要人工复核。
- 模型调用失败：不直接判定产品失败，但记录为待复核。

## 9. 验收记录模板

```text
验证日期：
验证人员：
代码分支：
前端 commit：
后端 commit：
浏览器尺寸：
后端地址：
大模型 provider/model：

确定性验证：
- npm run test：
- npm run build：
- 后端 health：
- 患者推荐成功：
- 后端错误兜底：
- 营养师确认闭环：
- 营养师驳回闭环：
- 配餐菜单与履约：

大模型辅助验收：
- 患者推荐语义：
- 错误兜底语义：
- 营养师 trace 可审性：
- 配餐管理清晰度：

问题记录：
1.
2.
3.

结论：
```

## 10. 当前版本验收结论口径

当前前端原型可以用于验证三类角色在同一个小程序内的入口切换、患者端后端推荐请求、营养师本地审核闭环和配餐本地管理流程。

当前不应宣称已经完成：

- 真实微信小程序运行时适配。
- 生产鉴权和角色权限体系。
- 真实图片识别。
- 真实支付、配送或取餐履约。
- 生产级医学审核和临床有效性验证。
- 大模型全自动医疗结论判断。
