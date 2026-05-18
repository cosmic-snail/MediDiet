# MediDiet 演示使用文档

版本：0.1.2
目标读者：产品演示人员、评审人员、前后端联调人员。

## 1. 演示目标

这份文档用于演示 MediDiet 医院餐食推荐助手的 MVP 能力：

- 为患者建立慢病、过敏和口味偏好档案。
- 录入一顿已经吃过的餐食摄入记录。
- 上传今天医院食谱。
- 记录营养师评审意见。
- 请求下一餐推荐，并展示推荐菜单、推荐原因、LLM 增强解释和 trace id。
- 展示缺少关键数据或 LLM 故障时的安全降级。

演示使用本地 FastAPI server 和内存状态，不需要数据库。服务重启后，患者、食谱、摄入记录和评审意见会清空。

## 2. 演示前准备

进入项目根目录：

```bash
cd /path/to/MediDiet
```

安装依赖：

```bash
python -m pip install -e .
```

启动 HTTP server：

```bash
uvicorn medidiet.server:app --app-dir src --reload
```

确认服务可用：

```bash
curl -s http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok","version":"0.1.1","ruleVersion":"baseline-2026-05-15"}
```

演示讲解重点：

- `version` 是 Python 包版本。
- `ruleVersion` 是当前规则包版本，推荐 trace 会记录它。
- HTTP server 只用于本地或可信内网联调，生产前还需要鉴权、授权、审计和持久化。

## 3. 标准演示流程

以下命令默认 server 运行在 `http://127.0.0.1:8000`。

### 3.1 创建患者档案

```bash
curl -s -X PUT http://127.0.0.1:8000/patients/patient-001 \
  -H "Content-Type: application/json" \
  -d '{
    "age": 65,
    "heightCm": 170,
    "weightKg": 72,
    "conditions": [
      {"kind": "condition", "value": "hypertension"},
      {"kind": "condition", "value": "diabetes"}
    ],
    "allergens": [
      {"kind": "allergen", "value": "peanut"}
    ],
    "contraindications": [],
    "preferences": {
      "tasteTags": [
        {"kind": "taste_tag", "value": "light"}
      ],
      "dislikedIngredients": [],
      "maxPriceCents": 4000,
      "maxDistanceMeters": 2000
    },
    "keyRiskFieldsConfirmed": true
  }'
```

预期返回：

```json
{"patientId":"patient-001","stored":true}
```

演示讲解重点：

- 疾病、过敏、禁忌、口味都使用 `kind + value` 的结构化 code。
- `mealLabel`、安全事件和排除原因在系统内部使用枚举或整数 code，避免自然语言字符串匹配。
- 花生过敏会参与安全检查；标准推荐流程先使用安全菜单，异常场景再展示过敏或禁忌阻断。

### 3.2 记录今天已经摄入的食物

```bash
curl -s -X POST http://127.0.0.1:8000/patients/patient-001/intake-records \
  -H "Content-Type: application/json" \
  -d '{
    "foodLabel": "早餐小米粥和鸡蛋",
    "occurredAt": "2026-05-18T08:00:00+08:00",
    "mealLabel": 1,
    "portion": "1碗小米粥，1个鸡蛋",
    "nutrients": {
      "energyKcal": 260,
      "carbsG": 38,
      "proteinG": 13,
      "fatG": 7,
      "sodiumMg": 180,
      "sugarG": 3,
      "fiberG": 2
    },
    "confidence": 0.92,
    "manuallyCorrected": false
  }'
```

预期返回：

```json
{"patientId":"patient-001","intakeRecordCount":1}
```

演示讲解重点：

- 这里模拟“手机拍照识别后得到结构化营养数据”的结果。
- 当前 MVP 不直接上传图片，图片识别服务后续应作为适配器接入。
- `confidence` 低且未人工修正时，会触发人工审核的不确定性路径。

### 3.3 上传今天医院食谱

```bash
curl -s -X PUT http://127.0.0.1:8000/menus/today \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "itemId": "steamed-fish-set",
        "name": "清蒸鱼杂粮饭套餐",
        "ingredients": [
          {"kind": "ingredient", "value": "fish"},
          {"kind": "ingredient", "value": "brown_rice"},
          {"kind": "ingredient", "value": "greens"}
        ],
        "allergens": [],
        "tasteTags": [
          {"kind": "taste_tag", "value": "light"}
        ],
        "nutritionTags": [
          {"kind": "nutrition_tag", "value": "low_sodium"},
          {"kind": "nutrition_tag", "value": "controlled_carbs"},
          {"kind": "nutrition_tag", "value": "vegetable_rich"},
          {"kind": "nutrition_tag", "value": "lean_protein"}
        ],
        "contraindicationTags": [],
        "nutrients": {
          "energyKcal": 520,
          "carbsG": 52,
          "proteinG": 35,
          "fatG": 14,
          "sodiumMg": 430,
          "sugarG": 5,
          "fiberG": 7
        }
      },
      {
        "itemId": "vegetable-tofu-set",
        "name": "时蔬豆腐套餐",
        "ingredients": [
          {"kind": "ingredient", "value": "tofu"},
          {"kind": "ingredient", "value": "greens"},
          {"kind": "ingredient", "value": "brown_rice"}
        ],
        "allergens": [],
        "tasteTags": [
          {"kind": "taste_tag", "value": "light"}
        ],
        "nutritionTags": [
          {"kind": "nutrition_tag", "value": "low_sodium"},
          {"kind": "nutrition_tag", "value": "vegetable_rich"}
        ],
        "contraindicationTags": [],
        "nutrients": {
          "energyKcal": 540,
          "carbsG": 60,
          "proteinG": 24,
          "fatG": 16,
          "sodiumMg": 520,
          "sugarG": 6,
          "fiberG": 8
        }
      }
    ]
  }'
```

预期返回：

```json
{"menuItemCount":2}
```

演示讲解重点：

- 医院食谱是高置信度输入，因此默认 `source=human_curated`、`nutritionConfidence=0.95`。
- 第一个菜品符合低钠、控主食和清淡偏好。
- 第二个菜品同样安全，但营养标签少于第一个，用于展示排序选择。

### 3.4 记录营养师评审意见

```bash
curl -s -X POST http://127.0.0.1:8000/reviews/nutritionist \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "patient-001",
    "reviewerId": "nutritionist-1",
    "note": "患者高血压合并糖尿病，晚餐优先选择低钠、控主食、清淡套餐。",
    "createdAt": "2026-05-18T10:00:00+08:00"
  }'
```

预期返回包含：

```json
{
  "stored": true,
  "review": {
    "patientId": "patient-001",
    "reviewerId": "nutritionist-1"
  }
}
```

演示讲解重点：

- MVP 会保存营养师意见并返回给前端展示。
- 当前营养师意见不改变规则结果，也不会传入 LLM prompt。
- 后续可扩展为营养师审核、覆盖或复核工作流。

### 3.5 请求晚餐推荐

```bash
curl -s -X POST http://127.0.0.1:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "patient-001",
    "mealLabel": 3,
    "temporaryTasteTags": [
      {"kind": "taste_tag", "value": "light"}
    ],
    "debug": true
  }'
```

预期返回重点：

```json
{
  "outcome": "recommended",
  "recommendedItems": [
    {
      "itemId": "steamed-fish-set",
      "name": "清蒸鱼杂粮饭套餐"
    }
  ],
  "explanation": {
    "patient": "...",
    "clinician": "...",
    "llm": {
      "usedFallback": true,
      "fallbackReason": 6001
    }
  },
  "nutritionistReviews": [
    {
      "note": "患者高血压合并糖尿病，晚餐优先选择低钠、控主食、清淡套餐。"
    }
  ],
  "traceId": "trace-..."
}
```

演示讲解重点：

- `outcome=recommended` 表示系统自动推荐成功。
- `recommendedItems[0]` 是当前最佳推荐菜单。
- `explanation.patient` 面向患者，语言更通俗。
- `explanation.clinician` 面向营养师或医生，保留规则命中和评分依据。
- `traceId` 用于后续审计、排查和人工复核。
- 如果没有配置 LLM，`usedFallback=true` 且 `fallbackReason=6001`，系统仍会使用规则模板解释。

## 4. 可选：展示真实 LLM 增强解释

如果 `.env` 已经配置真实 DeepSeek/OpenAI-compatible API：

```bash
set -a; source .env; set +a
uvicorn medidiet.server:app --app-dir src --reload
```

重新执行第 3 节标准演示流程。请求推荐时，预期：

```json
{
  "explanation": {
    "llm": {
      "usedFallback": false,
      "fallbackReason": null
    }
  }
}
```

演示讲解重点：

- LLM 只增强解释，不改变 `outcome`、推荐菜单、安全事件、排除原因或评分。
- 传给 LLM 的上下文经过脱敏，不包含 `patient_id`。
- LLM 失败时，接口仍返回推荐结果，并降级到规则模板解释。

也可以直接运行真实 HTTP LLM smoke test：

```bash
set -a; source .env; set +a
PYTHONPATH=src python -m unittest tests.test_http_llm_smoke -v
```

## 5. 异常场景演示

### 5.1 未上传菜单时请求推荐

重启 server 清空内存状态，只创建患者档案，不上传菜单，然后请求推荐。

预期 HTTP 状态码：`409`

预期错误：

```json
{
  "error": {
    "code": "MENU_NOT_CONFIGURED",
    "message": "Today menu has not been configured",
    "details": {}
  }
}
```

讲解重点：缺少高置信度食谱时，系统不会凭空生成推荐。

### 5.2 患者不存在时请求推荐

```bash
curl -s -X POST http://127.0.0.1:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"patientId":"missing-patient","mealLabel":3}'
```

预期 HTTP 状态码：`404`

预期错误：

```json
{
  "error": {
    "code": "PATIENT_NOT_FOUND",
    "message": "Patient profile not found"
  }
}
```

讲解重点：前端需要先完成患者档案创建或从后端加载患者档案。

### 5.3 错误 code kind

```bash
curl -s -X PUT http://127.0.0.1:8000/patients/patient-002 \
  -H "Content-Type: application/json" \
  -d '{
    "age": 65,
    "heightCm": 170,
    "weightKg": 72,
    "conditions": [
      {"kind": "allergen", "value": "peanut"}
    ],
    "allergens": [],
    "contraindications": [],
    "keyRiskFieldsConfirmed": true
  }'
```

预期 HTTP 状态码：`422`

预期错误 code：

```json
{"error":{"code":"INVALID_CODE_KIND"}}
```

讲解重点：疾病、过敏、禁忌、营养标签、口味标签必须使用正确枚举类型，避免字符串误匹配。

### 5.4 过敏或高风险菜单触发人工审核

重新上传只包含花生过敏原的菜单：

```bash
curl -s -X PUT http://127.0.0.1:8000/menus/today \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "itemId": "peanut-noodle",
        "name": "花生酱拌面",
        "ingredients": [
          {"kind": "ingredient", "value": "noodle"},
          {"kind": "ingredient", "value": "peanut"}
        ],
        "allergens": [
          {"kind": "allergen", "value": "peanut"}
        ],
        "tasteTags": [],
        "nutritionTags": [],
        "contraindicationTags": [
          {"kind": "contraindication", "value": "high_sodium"}
        ],
        "nutrients": {
          "energyKcal": 680,
          "carbsG": 88,
          "proteinG": 20,
          "fatG": 25,
          "sodiumMg": 980,
          "sugarG": 10,
          "fiberG": 3
        }
      }
    ]
  }'
```

再次请求推荐：

```bash
curl -s -X POST http://127.0.0.1:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"patientId":"patient-001","mealLabel":3,"debug":true}'
```

预期返回重点：

```json
{
  "outcome": "human_review_required",
  "recommendedItems": [],
  "trace": {
    "safetyEvents": [
      {
        "code": 1001,
        "codeName": "ALLERGY_MATCH"
      }
    ]
  }
}
```

讲解重点：过敏命中属于高风险安全事件，系统不会自动推荐，而是转人工审核。

## 6. 演示收尾检查

查看当前内存状态：

```bash
curl -s http://127.0.0.1:8000/debug/state
```

预期可以看到：

```json
{
  "patients": ["patient-001"],
  "todayMenuCount": 2
}
```

演示结束后按 `Ctrl-C` 停止 server。

## 7. 演示注意事项

- 不要在演示中录入真实患者姓名、身份证号、手机号、住址或完整病历。
- `.env` 不要提交到 git，也不要在屏幕上展示 API key。
- 当前 server 使用内存状态，重启即清空。
- `/debug/state` 仅用于开发演示，生产环境必须移除、禁用或加权限保护。
- 当前医学规则是 baseline 演示规则，生产前必须经过医院营养师或医生审核。
- 当前图片识别、外卖平台、HIS/EMR 都是后续适配器扩展方向，不在本地演示中直接调用。
