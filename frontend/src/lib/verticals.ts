// 各搜尋領域(vertical):每個有自己的入口架構(說明、範例、提示、強調欄位)
export interface Vertical {
  key: string;
  label: string;
  icon: string;
  tagline: string;
  placeholder: string;
  examples: string[];
  kind: "product" | "article"; // product=重視價格/圖;article=重視標題/摘要/來源
}

export const VERTICALS: Vertical[] = [
  { key: "merch", label: "周邊/商品", icon: "🧸", kind: "product",
    tagline: "動漫角色周邊、公仔、立牌比價", placeholder: "多聞 立牌\n多聞 壓克力",
    examples: ["多聞 立牌", "多聞 公仔", "多聞 吊飾"] },
  { key: "food", label: "美食", icon: "🍜", kind: "article",
    tagline: "餐廳、小吃、團購美食情報", placeholder: "台北 拉麵 推薦\n宅配 牛肉麵",
    examples: ["台北 拉麵 推薦", "宅配 甜點", "高雄 早午餐"] },
  { key: "pet", label: "寵物", icon: "🐾", kind: "product",
    tagline: "飼料、用品、寵物服務比價", placeholder: "貓飼料 無穀\n狗 自動餵食器",
    examples: ["貓飼料 無穀", "狗 自動餵食器", "貓砂 推薦"] },
  { key: "animal", label: "動物/生態", icon: "🦊", kind: "article",
    tagline: "動物知識、生態、認養資訊", placeholder: "狐狸 生態\n貓頭鷹 認養",
    examples: ["狐狸 生態", "水獺 棲地", "野生動物 保育"] },
  { key: "travel", label: "旅遊", icon: "✈️", kind: "article",
    tagline: "景點、行程、機票住宿", placeholder: "京都 自由行 行程\n沖繩 親子",
    examples: ["京都 自由行", "沖繩 親子景點", "花蓮 民宿 推薦"] },
  { key: "stock", label: "股市/投資", icon: "📈", kind: "article",
    tagline: "個股、ETF、財報與市場分析", placeholder: "0050 配息\n台積電 財報",
    examples: ["0050 配息", "台積電 財報", "美股 ETF 推薦"] },
  { key: "startup", label: "創業", icon: "🚀", kind: "article",
    tagline: "商業模式、補助、資源與案例", placeholder: "新創 補助 申請\n餐飲 創業 成本",
    examples: ["新創 政府補助", "餐飲 創業 成本", "電商 經營 心得"] },
  { key: "realestate", label: "房地產", icon: "🏠", kind: "article",
    tagline: "買房、租屋、實價登錄", placeholder: "新北 中古屋\n租屋 注意事項",
    examples: ["實價登錄 查詢", "新北 中古屋", "首購 貸款"] },
  { key: "job", label: "工作職缺", icon: "💼", kind: "article",
    tagline: "職缺、薪資、面試情報", placeholder: "前端工程師 職缺\n面試 準備",
    examples: ["前端工程師 職缺", "遠端工作", "薪資 行情"] },
  { key: "course", label: "學習/課程", icon: "📚", kind: "article",
    tagline: "線上課程、證照、教學", placeholder: "Python 線上課程\n多益 準備",
    examples: ["Python 線上課程", "多益 準備", "設計 證照"] },
  { key: "health", label: "健康/醫療", icon: "🩺", kind: "article",
    tagline: "保健、營養、醫療資訊", placeholder: "維他命D 補充\n睡眠 改善",
    examples: ["維他命D 補充", "睡眠 改善", "膝蓋 保養"] },
  { key: "tech", label: "3C/科技", icon: "💻", kind: "product",
    tagline: "手機、筆電、配件比價", placeholder: "機械鍵盤 推薦\n降噪耳機",
    examples: ["機械鍵盤 推薦", "降噪耳機", "行動電源"] },
  { key: "car", label: "汽車", icon: "🚗", kind: "article",
    tagline: "車款、保養、二手車", placeholder: "Toyota 油耗\n二手車 注意",
    examples: ["休旅車 推薦", "二手車 注意事項", "輪胎 比較"] },
  { key: "secondhand", label: "二手", icon: "♻️", kind: "product",
    tagline: "二手拍賣、收購、交換", placeholder: "二手 相機\n二手 家具",
    examples: ["二手 相機", "二手 家具", "二手 球鞋"] },
  { key: "ticket", label: "票券/活動", icon: "🎫", kind: "product",
    tagline: "演唱會、展覽、活動票券與轉售", placeholder: "演唱會 門票\n展覽 早鳥",
    examples: ["演唱會 門票", "音樂祭 票", "展覽 早鳥票"] },
  { key: "rent", label: "租屋", icon: "🔑", kind: "article",
    tagline: "租金、格局、捷運生活圈", placeholder: "台北 套房 租\n新北 兩房 捷運",
    examples: ["台北 套房 租屋", "新北 兩房 捷運", "可養寵 租屋"] },
  { key: "game", label: "遊戲/虛寶", icon: "🎮", kind: "product",
    tagline: "遊戲帳號、虛寶、點數交易行情", placeholder: "原神 帳號\n楓之谷 楓幣",
    examples: ["遊戲 帳號 交易", "虛寶 點數", "代儲 點卡"] },
  { key: "crypto", label: "加密貨幣", icon: "₿", kind: "article",
    tagline: "幣價、漲跌、市值與消息", placeholder: "比特幣 價格\nETH 走勢",
    examples: ["比特幣 價格", "以太幣 走勢", "迷因幣 分析"] },
  { key: "flight", label: "機票/住宿", icon: "🛫", kind: "product",
    tagline: "航線、日期、每晚房價比價", placeholder: "東京 機票\n大阪 飯店",
    examples: ["東京 機票 來回", "大阪 飯店 親子", "廉航 促銷"] },
  { key: "clinic", label: "醫美/補教", icon: "💉", kind: "article",
    tagline: "療程、課程、評價與方案比較", placeholder: "雷射 除斑 價格\n數學 家教",
    examples: ["醫美 雷射 價格", "牙齒矯正 費用", "數學 家教 行情"] },
];

export const DEFAULT_VERTICAL = VERTICALS[0];
export function getVertical(key: string): Vertical {
  return VERTICALS.find((v) => v.key === key) ?? DEFAULT_VERTICAL;
}
