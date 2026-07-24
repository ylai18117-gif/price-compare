import groupbuyData from '../../data/groupbuy.json';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function corsHeaders(extra = {}) {
  return { ...CORS_HEADERS, ...extra };
}

/**
 * 模糊匹配
 */
function fuzzyMatch(text, keyword) {
  const t = text.replace(/\s+/g, '').toLowerCase();
  const k = keyword.replace(/\s+/g, '').toLowerCase();
  return t.includes(k);
}

/**
 * 综合评分：价格折扣比 + 评分 + 销量
 */
function rankDeals(items) {
  if (!items.length) return items;
  const maxSales = Math.max(...items.map(i => i.sales || 0), 1);

  return items
    .map(item => {
      const discount = item.originalPrice
        ? (1 - item.price / item.originalPrice)
        : 0;
      const discountScore = discount * 100 * 0.4;
      const ratingScore = ((item.rating || 0) / 5) * 100 * 0.35;
      const salesScore = ((item.sales || 0) / maxSales) * 100 * 0.25;
      const score = discountScore + ratingScore + salesScore;
      return { ...item, score: Math.round(score * 100) / 100 };
    })
    .sort((a, b) => b.score - a.score);
}

/**
 * 从缓存数据搜索团购
 */
function searchCachedData(keyword) {
  const results = [];
  for (const [key, items] of Object.entries(groupbuyData.keywords || {})) {
    if (key.includes(keyword) || keyword.includes(key)) {
      results.push(...items);
    } else {
      const matched = items.filter(
        item =>
          fuzzyMatch(item.title, keyword) || fuzzyMatch(item.shop || '', keyword)
      );
      results.push(...matched);
    }
  }
  return results;
}

/**
 * 生成模拟团购数据
 */
function generateSimulatedDeals(keyword) {
  const templates = [
    {
      platform: 'meituan',
      shop: `${keyword}·品质优选店`,
      title: `${keyword}超值双人套餐`,
      base: 68,
      rating: 4.6,
    },
    {
      platform: 'douyin',
      shop: `${keyword}·网红打卡店`,
      title: `${keyword}单人特惠套餐`,
      base: 39,
      rating: 4.4,
    },
    {
      platform: 'meituan',
      shop: `${keyword}·家庭欢聚店`,
      title: `${keyword}家庭4人套餐`,
      base: 128,
      rating: 4.7,
    },
    {
      platform: 'douyin',
      shop: `${keyword}·直播专享店`,
      title: `${keyword}限时秒杀套餐`,
      base: 29,
      rating: 4.3,
    },
    {
      platform: 'meituan',
      shop: `${keyword}·老字号`,
      title: `${keyword}经典传承套餐`,
      base: 88,
      rating: 4.8,
    },
  ];

  const count = 3 + Math.floor(Math.random() * 2); // 3-4条
  return templates.slice(0, count).map((t, i) => {
    const price = Math.round(t.base * (0.7 + Math.random() * 0.2) * 100) / 100;
    return {
      id: `sim_tuan_${Date.now()}_${i}`,
      title: t.title,
      price,
      originalPrice: Math.round(price * (1.3 + Math.random() * 0.5) * 100) / 100,
      platform: t.platform,
      shop: t.shop,
      rating: t.rating,
      sales: Math.floor(Math.random() * 3000) + 100,
      details: `含${keyword}主食+小食+饮品，到店核销`,
      expireDate: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
      source: 'simulated',
    };
  });
}

export async function onRequest(context) {
  const { request } = context;

  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders() });
  }

  if (request.method !== 'GET') {
    return Response.json(
      { success: false, error: '仅支持GET请求' },
      { status: 405, headers: corsHeaders() }
    );
  }

  try {
    const url = new URL(request.url);
    const query = (url.searchParams.get('q') || '').trim();

    if (!query) {
      return Response.json(
        { success: false, error: '请提供搜索关键词 ?q=xxx' },
        { status: 400, headers: corsHeaders() }
      );
    }

    // 1. 缓存搜索
    let items = searchCachedData(query);
    let source = 'cached';

    // 2. 无缓存 → 模拟数据
    if (!items.length) {
      items = generateSimulatedDeals(query);
      source = 'simulated';
    }

    // 3. 排序
    items = rankDeals(items);

    return Response.json(
      {
        success: true,
        query,
        total: items.length,
        items,
        source,
        platforms: ['meituan', 'douyin'],
        timestamp: Date.now(),
      },
      { status: 200, headers: corsHeaders() }
    );
  } catch (err) {
    console.error('Tuan API error:', err);
    return Response.json(
      { success: false, error: '团购搜索服务暂时不可用', detail: err.message },
      { status: 500, headers: corsHeaders() }
    );
  }
}
