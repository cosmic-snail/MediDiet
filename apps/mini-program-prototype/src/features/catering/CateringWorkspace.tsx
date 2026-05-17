import { ChefHat, Save, ToggleLeft } from 'lucide-react';
import type { Dispatch, SetStateAction } from 'react';
import { formatPrice, mealLabelName } from '../../contracts';
import { updateFulfillmentStatus, updateMenuItemAvailability, type PrototypeState } from '../../state';

interface CateringWorkspaceProps {
  state: PrototypeState;
  onStateChange: Dispatch<SetStateAction<PrototypeState>>;
}

const fulfillmentLabels = {
  pending: '待准备',
  prepared: '已备餐',
  delivered: '已送达',
  cancelled: '取消'
};

export function CateringWorkspace({ state, onStateChange }: CateringWorkspaceProps) {
  const primaryItem = state.menuItems[0];

  if (!primaryItem) {
    return (
      <section className="card">
        <p className="eyebrow">配餐管理</p>
        <h2>暂无菜单数据</h2>
        <p className="muted">新增菜品后会在这里维护营养、过敏原和可售状态。</p>
      </section>
    );
  }

  return (
    <div className="workspace-stack">
      <section className="hero-panel catering-hero">
        <div>
          <p className="eyebrow">配餐管理</p>
          <h2>菜单数据维护优先</h2>
          <p>维护营养值、过敏原、禁忌标签、置信度和可售状态，让推荐候选更可信。</p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">菜单列表</p>
            <h2>今日菜品</h2>
          </div>
          <ChefHat size={20} aria-hidden="true" />
        </div>
        <div className="list">
          {state.menuItems.map((item) => (
            <div className="list-row" key={item.itemId}>
              <div>
                <strong>{item.name}</strong>
                <p>{formatPrice(item.priceCents)}</p>
                <p>nutritionConfidence {item.nutritionConfidence}</p>
                <p>{item.nutritionTags.join('、') || '营养标签待补'}</p>
              </div>
              <span className={item.available ? 'status good' : 'status danger'}>
                {item.available ? '可售' : '下架'}
              </span>
            </div>
          ))}
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => onStateChange((current) => updateMenuItemAvailability(current, primaryItem.itemId, false))}
        >
          <ToggleLeft size={18} aria-hidden="true" />
          下架{primaryItem.name}
        </button>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">菜品详情</p>
            <h2>营养详情</h2>
          </div>
          <Save size={20} aria-hidden="true" />
        </div>
        <div className="nutrition-grid">
          <div>
            能量 <strong>{primaryItem.nutrients.energyKcal} kcal</strong>
          </div>
          <div>
            碳水 <strong>{primaryItem.nutrients.carbsG}g</strong>
          </div>
          <div>
            蛋白质 <strong>{primaryItem.nutrients.proteinG}g</strong>
          </div>
          <div>
            钠 <strong>{primaryItem.nutrients.sodiumMg}mg</strong>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">轻量履约</p>
            <h2>已确认餐食</h2>
          </div>
        </div>
        {state.fulfillments.length === 0 && (
          <div>
            <strong>暂无已确认餐食</strong>
            <p className="muted">患者选择或营养师确认后会出现在这里。</p>
          </div>
        )}
        {state.fulfillments.map((fulfillment) => (
          <div className="list-row" key={fulfillment.fulfillmentId}>
            <div>
              <strong>
                {fulfillment.patientDisplayName} · {fulfillment.itemName}
              </strong>
              <p>{mealLabelName(fulfillment.mealLabel)}</p>
            </div>
            {fulfillment.status === 'pending' ? (
              <div className="button-row">
                <span className="status good">{fulfillmentLabels[fulfillment.status]}</span>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() =>
                    onStateChange((current) => updateFulfillmentStatus(current, fulfillment.fulfillmentId, 'prepared'))
                  }
                >
                  标记已备餐
                </button>
              </div>
            ) : (
              <span className={fulfillment.status === 'cancelled' ? 'status danger' : 'status good'}>
                {fulfillmentLabels[fulfillment.status]}
              </span>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
