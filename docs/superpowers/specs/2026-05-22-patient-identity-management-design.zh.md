# MediDiet 患者身份管理原型设计

日期：2026-05-22

## 1. 背景

当前 `apps/mini-program-prototype` 是一个本地 React/Vite 移动端原型，已经覆盖患者、营养师、配餐三类角色工作台。患者端目前固定使用 `fixtures.ts` 中的单个 `demo-patient` 和 `王女士`，患者资料、今日摄入、推荐结果和后端推荐请求都默认绑定这一个患者。

本需求聚焦原型层的患者身份管理：支持多个演示患者档案，并允许患者端切换当前患者。切换后，页面展示、摄入记录、推荐结果和后端推荐请求都应围绕当前患者展开。

## 2. 目标

- 在前端原型中支持多个患者档案。
- 患者端可选择当前患者身份。
- 患者资料卡展示当前患者的健康资料摘要。
- 今日摄入记录按患者隔离。
- 推荐结果按患者隔离。
- 获取下一餐推荐时使用当前患者的 `patientId`、患者资料和摄入记录。
- 保持营养师和配餐工作台的现有演示能力，不把本需求扩展为真实认证或权限系统。

## 3. 非目标

- 不实现真实登录、认证、授权、患者绑定或家属关系。
- 不新增后端患者列表、查询、删除等 API。
- 不改变 Python 推荐引擎的患者模型。
- 不把营养师审核队列改造成完整多患者生产工作流。
- 不引入持久化存储；刷新页面仍回到 fixtures 初始状态。

## 4. 推荐方案

采用“前端本地多患者档案 + 当前患者切换”的方案。

在 `PrototypeState` 中引入患者集合和当前患者 id，将原来的全局 `intakeRecords` 与 `recommendation` 扩展为按 `patientId` 分组的数据结构。患者工作台根据 `activePatientId` 派生当前患者上下文。这样可以让原型展示真正的数据隔离，又不会提前引入后端身份、权限和绑定关系。

被放弃的两个方案：

- 只做患者资料下拉切换：改动小，但摄入与推荐仍共享，容易误导身份管理的产品语义。
- 先做后端患者列表 API：更接近生产形态，但会把范围扩大到 API、服务状态同步和权限边界，不适合当前原型需求。

## 5. 数据模型

`PatientProfileDto` 保持不变，继续承载患者档案：

- `patientId`
- `displayName`
- 年龄、身高、体重
- 慢病、过敏、禁忌
- 口味偏好、忌口、预算和距离偏好
- `keyRiskFieldsConfirmed`
- `source`

`PrototypeState` 调整为包含患者上下文：

```ts
interface PrototypeState {
  activeRole: Role;
  patients: PatientProfileDto[];
  activePatientId: string;
  intakeRecordsByPatientId: Record<string, IntakeRecordDto[]>;
  recommendationsByPatientId: Record<string, RecommendationResponseDto | null>;
  menuItems: MenuItemDto[];
  reviewCases: ReviewCaseDto[];
  fulfillments: FulfillmentDto[];
}
```

为减少组件改动和保持可读性，状态层提供选择器：

- `selectActivePatient(state): PatientProfileDto`
- `selectActivePatientIntakeRecords(state): IntakeRecordDto[]`
- `selectActivePatientRecommendation(state): RecommendationResponseDto | null`

并提供状态操作：

- `setActivePatient(state, patientId)`
- `addCorrectedIntake(state, foodLabel, mealLabel)`
- `requestRecommendation(state, mode)`
- `applyBackendRecommendation(state, patientId, recommendation)`

这些操作都以当前患者或显式 `patientId` 为边界更新数据。

## 6. 初始数据

`fixtures.ts` 增加至少两个患者档案：

- `demo-patient`：王女士，保持现有高血压、糖尿病、虾过敏、偏好清淡。
- `demo-patient-ckd`：新增一位慢性肾病相关演示患者，用于展示不同慢病、过敏和偏好组合。

摄入记录也按患者拆分：

- 王女士保留“咸汤面”午餐记录。
- 第二位患者提供一条不同餐次或不同营养风险的摄入记录。

推荐结果初始只需要保证当前默认患者有可展示结果。其他患者初始为 `null`，用户点击“获取下一餐推荐”后再生成或通过本地模拟按钮生成。

## 7. 患者端交互

患者工作台增加“当前患者”身份区域，位置在主行动区下方、健康资料卡之前，展示：

- 患者姓名。
- 年龄。
- 关键风险确认状态。
- 可切换患者的控件。

切换患者后：

- 今日概览中的摄入数量和推荐状态更新。
- 健康资料卡展示新患者的条件、过敏、口味偏好和预算。
- 今日摄入列表展示新患者的记录。
- 推荐结果展示新患者对应结果；没有推荐时显示简洁的空状态。
- “手动补录低糖酸奶”只追加到当前患者。
- “获取下一餐推荐”使用当前患者。

控件形态使用移动端适合的原生 `select`。后续如果需要更接近微信小程序体验，再改为患者身份弹层。

## 8. 推荐请求数据流

`App.tsx` 的后端推荐请求从全局 fixture 切换为当前患者上下文：

1. 从 state 中读取当前患者。
2. 读取当前患者摄入记录。
3. 调用 `medidietApi.seedDemoData({ patientProfile, intakeRecords, menuItems })`。
4. 调用 `requestRecommendation({ patientId: patientProfile.patientId, mealLabel: 3 })`。
5. 成功后把推荐结果写入 `recommendationsByPatientId[patientId]`。

后端仍然使用已有接口：

- `GET /debug/state`
- `PUT /patients/{patient_id}`
- `POST /patients/{patient_id}/intake-records`
- `PUT /menus/today`
- `POST /recommendations`

不新增 API。

## 9. 营养师与配餐影响

本需求不重构营养师和配餐工作台。它们继续消费现有 `reviewCases`、`menuItems` 和 `fulfillments`。

为了避免类型和运行时破坏，需要同步调整：

- `selectWorkbenchSummary(state, 'patient')` 按当前患者计算摄入数量和推荐状态。
- 营养师提交审核时，如果审核 trace 能对应当前推荐，则回写对应患者；当前 fixtures 中审核 case 仍可维持 `demo-patient`。
- 配餐工作台不依赖当前患者，保持不变。

## 10. 错误与空状态

- 如果 `activePatientId` 找不到对应患者，选择器回退到第一位患者，避免页面崩溃。
- 如果当前患者没有摄入记录，今日摄入卡显示空状态，并保留手动补录入口。
- 如果当前患者没有推荐结果，第一版沿用当前结构：推荐结果卡不显示，用户可通过主按钮生成推荐。
- 后端请求失败时，只显示服务错误，不清空当前患者已有推荐。

## 11. 测试计划

前端测试覆盖：

- 初始状态包含多个患者，并默认选中 `demo-patient`。
- `setActivePatient` 可以切换当前患者。
- `selectWorkbenchSummary` 按当前患者计算摄入与推荐状态。
- `addCorrectedIntake` 只更新当前患者摄入记录。
- `requestRecommendation` 只更新当前患者推荐。
- `PatientWorkspace` 展示当前患者姓名和资料摘要。
- 用户切换患者后，摄入列表和推荐状态随之变化。
- `App` 发起后端推荐时使用当前患者资料和当前患者摄入记录。

验证命令：

```bash
cd apps/mini-program-prototype
npm run test
npm run build
```

如本次实现只改前端原型，不需要运行 Python 单元测试；若修改 HTTP 适配或服务层契约，再补充后端测试。

## 12. 验收标准

- 患者端能看到并切换至少两个患者身份。
- 切换患者后，健康资料摘要不同。
- 切换患者后，今日摄入记录不同或可独立为空。
- 手动补录摄入只影响当前患者。
- 获取推荐时使用当前患者 `patientId`。
- 推荐结果按患者隔离，不会在患者切换后串台。
- 现有营养师和配餐演示仍能运行。
- 前端测试和构建通过。
