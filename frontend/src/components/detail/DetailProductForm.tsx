interface DetailProductFormProps {
  brandName: string;
  productName: string;
  teaType: string;
  platform: string;
  stylePreset: string;
  priceBand: string;
  brewSuggestion: string;
  specs: {
    net_content: string;
    origin: string;
    ingredients: string;
    shelf_life: string;
    storage: string;
  };
  onBrandNameChange: (value: string) => void;
  onProductNameChange: (value: string) => void;
  onTeaTypeChange: (value: string) => void;
  onPlatformChange: (value: string) => void;
  onStylePresetChange: (value: string) => void;
  onPriceBandChange: (value: string) => void;
  onBrewSuggestionChange: (value: string) => void;
  onSpecChange: (key: "net_content" | "origin" | "ingredients" | "shelf_life" | "storage", value: string) => void;
}

/** 商品信息表单。 */
export function DetailProductForm(props: DetailProductFormProps) {
  const {
    brandName,
    productName,
    teaType,
    platform,
    stylePreset,
    priceBand,
    brewSuggestion,
    specs,
    onBrandNameChange,
    onProductNameChange,
    onTeaTypeChange,
    onPlatformChange,
    onStylePresetChange,
    onPriceBandChange,
    onBrewSuggestionChange,
    onSpecChange,
  } = props;

  return (
    <div className="detail-form-grid">
      <div className="detail-field detail-field--full">
        <label htmlFor="detail-brand-name">品牌名</label>
        <input id="detail-brand-name" className="detail-input" value={brandName} onChange={(event) => onBrandNameChange(event.target.value)} />
      </div>
      <div className="detail-field detail-field--full">
        <label htmlFor="detail-product-name">商品名</label>
        <input id="detail-product-name" className="detail-input" value={productName} onChange={(event) => onProductNameChange(event.target.value)} />
      </div>
      <div className="detail-field">
        <label htmlFor="detail-tea-type">茶类</label>
        <input id="detail-tea-type" className="detail-input" value={teaType} onChange={(event) => onTeaTypeChange(event.target.value)} />
      </div>
      <div className="detail-field">
        <label htmlFor="detail-platform">平台</label>
        <select id="detail-platform" className="detail-input" value={platform} onChange={(event) => onPlatformChange(event.target.value)}>
          <option value="tmall">天猫</option>
        </select>
      </div>
      <div className="detail-field">
        <label htmlFor="detail-style-preset">风格 preset</label>
        <select id="detail-style-preset" className="detail-input" value={stylePreset} onChange={(event) => onStylePresetChange(event.target.value)}>
          <option value="tea_tmall_premium_light">tea_tmall_premium_light</option>
        </select>
      </div>
      <div className="detail-field">
        <label htmlFor="detail-price-band">价格带</label>
        <input id="detail-price-band" className="detail-input" value={priceBand} onChange={(event) => onPriceBandChange(event.target.value)} />
      </div>
      <div className="detail-field">
        <label htmlFor="detail-net-content">净含量</label>
        <input id="detail-net-content" className="detail-input" value={specs.net_content} onChange={(event) => onSpecChange("net_content", event.target.value)} />
      </div>
      <div className="detail-field">
        <label htmlFor="detail-origin">产地</label>
        <input id="detail-origin" className="detail-input" value={specs.origin} onChange={(event) => onSpecChange("origin", event.target.value)} />
      </div>
      <div className="detail-field detail-field--full">
        <label htmlFor="detail-ingredients">配料</label>
        <input id="detail-ingredients" className="detail-input" value={specs.ingredients} onChange={(event) => onSpecChange("ingredients", event.target.value)} />
      </div>
      <div className="detail-field">
        <label htmlFor="detail-shelf-life">保质期</label>
        <input id="detail-shelf-life" className="detail-input" value={specs.shelf_life} onChange={(event) => onSpecChange("shelf_life", event.target.value)} />
      </div>
      <div className="detail-field">
        <label htmlFor="detail-storage">储存方式</label>
        <input id="detail-storage" className="detail-input" value={specs.storage} onChange={(event) => onSpecChange("storage", event.target.value)} />
      </div>
      <div className="detail-field detail-field--full">
        <label htmlFor="detail-brew-suggestion">冲泡建议</label>
        <textarea
          id="detail-brew-suggestion"
          className="detail-textarea"
          rows={3}
          value={brewSuggestion}
          onChange={(event) => onBrewSuggestionChange(event.target.value)}
        />
      </div>
    </div>
  );
}
