interface DetailGoalFormProps {
  targetSliceCount: number;
  sellingPointsInput: string;
  styleNotes: string;
  extraRequirements: string;
  preferMainResultFirst: boolean;
  onTargetSliceCountChange: (value: number) => void;
  onSellingPointsChange: (value: string) => void;
  onStyleNotesChange: (value: string) => void;
  onExtraRequirementsChange: (value: string) => void;
  onPreferMainResultFirstChange: (value: boolean) => void;
  onReset: () => void;
  onBackToMain: () => void;
}

/** 目标与补充要求表单。 */
export function DetailGoalForm({
  targetSliceCount,
  sellingPointsInput,
  styleNotes,
  extraRequirements,
  preferMainResultFirst,
  onTargetSliceCountChange,
  onSellingPointsChange,
  onStyleNotesChange,
  onExtraRequirementsChange,
  onPreferMainResultFirstChange,
  onReset,
  onBackToMain,
}: DetailGoalFormProps) {
  return (
    <div className="detail-stack">
      <div className="detail-field">
        <label htmlFor="detail-target-slices">目标屏数</label>
        <select
          id="detail-target-slices"
          className="detail-input"
          value={String(targetSliceCount)}
          onChange={(event) => onTargetSliceCountChange(Number(event.target.value))}
        >
          {[8, 9, 10, 11, 12].map((item) => (
            <option key={item} value={item}>
              {item} 屏
            </option>
          ))}
        </select>
      </div>

      <div className="detail-field">
        <label htmlFor="detail-selling-points">卖点补充</label>
        <textarea
          id="detail-selling-points"
          className="detail-textarea"
          rows={5}
          value={sellingPointsInput}
          onChange={(event) => onSellingPointsChange(event.target.value)}
          placeholder="每行一个卖点"
        />
      </div>

      <div className="detail-field">
        <label htmlFor="detail-style-notes">风格补充</label>
        <textarea
          id="detail-style-notes"
          className="detail-textarea"
          rows={3}
          value={styleNotes}
          onChange={(event) => onStyleNotesChange(event.target.value)}
        />
      </div>

      <div className="detail-field">
        <label htmlFor="detail-extra-requirements">额外要求</label>
        <textarea
          id="detail-extra-requirements"
          className="detail-textarea"
          rows={4}
          value={extraRequirements}
          onChange={(event) => onExtraRequirementsChange(event.target.value)}
        />
      </div>

      <label className="detail-checkbox">
        <input
          type="checkbox"
          checked={preferMainResultFirst}
          onChange={(event) => onPreferMainResultFirstChange(event.target.checked)}
        />
        <span>优先引用主图结果作为详情图主包装参考</span>
      </label>

      <div className="detail-inline-actions">
        <button type="button" className="btn-secondary" onClick={onReset}>
          清空当前任务
        </button>
        <button type="button" className="btn-secondary" onClick={onBackToMain}>
          返回主图工作台
        </button>
      </div>
    </div>
  );
}
