import shoppingData from '../../data/shopping.json';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function corsHeaders(extra = {}) {
  return { ...CORS_HEADERS, ...extra };
}

/**
 * 模糊匹配：标题包含关键词（忽略空格、大小写）
 */
function fuzzyMatch(title, keyword) {
  const t = title.replace(/\s+/g, '').toLowerCase();
  const k = keyword.replace(/\s+/g, '').toLowerCase();
  return t.includes(k);
}

/**
 * 综合评分排序：score = (1/price)*0.4 + sales*0.3 + rating*0.3
 * 归一化处理后加权
 */
function rankItems(items) {
  if (!items.length) return items;

  const prices = items.map(i => i.price || 1);
  const sales = items.map(i => i.sales || 0);
  const ratings = items.map(i => i.rating || 0);

  const maxSales = Math.max(...sales, 1);
  const maxRating = Math.max(...ratings, 1);

  return items
    .map(item => {
      const priceScore = (1 / (item.price || 1)) * 100; // 放大低价优势
      const salesScore = ((item.sales || 0) / maxSales) * 100;
      const ratingScore = ((item.rating || 0) / maxRating) * 100;
      const score = priceScore * 0.4 + salesScore * 0.3 + ratingScore * 0.3;
      return { ...item, score: Math.round(score * 100) / 100 };
    })
    .sort((a, b) => b.score - a.score);
}

/**
 * 从预抓取数据中搜索
 */
function searchCachedData(keyword) {
  const results = [];
  for (const [key, items] of Object.entries(shoppingData.keywords || {})) {
    // 关键词匹配：数据key匹配 或 商品标题匹配
    if (key.includes(keyword) || keyword.includes(key)) {
      results.push(...items);
    } else {
      // 逐条标题模糊匹配
      const matched = items.filter(item => fuzzyMatch(item.title, keyword));
      results.push(...matched);
    }
  }
  return results;
}

/**
 * 实时抓取京东移动端搜索API
 */
async function fetchJDSearch(keyword) {
  const url = `https://so.m.jd.com/ware/search.action?keyword=${encodeURIComponent(keyword)}&datatype=json`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);

  try {
    const resp = await fetch(url, {
      headers: {
        'User-Agent':
          'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://so.m.jd.com/',
      },
      signal: controller.signal,
    });

    if (!resp.ok) return null;
    const data = await resp.json();

    // 京东移动端返回格式可能变化，尝试多种解析
    const wareList =
      data?.wareList || data?.data?.wareList || data?.result?.wareList || [];
    if (!wareList.length) return null;

    return wareList.slice(0, 8).map((w, idx) => ({
      id: `jd_live_${idx}`,
      title: w.wname || w.name || w.title || '京东商品',
      price: parseFloat(w.jdPrice || w.price || w.finalPrice || 0),
      originalPrice: parseFloat(w.mPrice || w.jdPrice || w.price || 0),
      platform: 'jd',
      image: w.imageurl || w.img || '',
      url: w.wareId ? `https://item.m.jd.com/product/${w.wareId}.html` : '',
      rating: parseFloat(w.good || w.commentScore || '4.5'),
      sales: parseInt(w.comments || w.commentCount || '0') || 0,
      shop: w.shopName || '京东自营',
      source: 'live',
    }));
  } catch (e) {
    console.error('JD live fetch failed:', e.message);
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * 生成模拟数据（兜底方案）
 */
function generateSimulatedData(keyword) {
  const platforms = [
    { name: 'jd', shop: '京东自营' },
    { name: 'taobao', shop: '天猫旗舰店' },
    { name: 'pdd', shop: '拼多多百亿补贴' },
    { name: 'jd', shop: '京东超市' },
    { name: 'taobao', shop: '淘宝严选' },
  ];

  const count = 3 + Math.floor(Math.random() * 3); // 3-5条
  const items = [];

  for (let i = 0; i < count; i++) {
    const p = platforms[i % platforms.length];
    const basePrice = 19.9 + Math.random() * 80;
    const price = Math.round(basePrice * 100) / 100;

    items.push({
      id: `sim_${Date.now()}_${i}`,
      title: `${keyword} 优质${['经典款', '升级版', '家庭装', '特惠装', '旗舰款'][i % 5]}`,
      price,
      originalPrice: Math.round(price * (1.1 + Math.random() * 0.4) * 100) / 100,
      platform: p.name,
      image: '',
      url: '',
      rating: Math.round((4.0 + Math.random() * 0.9) * 10) / 10,
      sales: Math.floor(Math.random() * 50000) + 500,
      shop: p.shop,
      source: 'simulated',
    });
  }
  return items;
}

export async function onRequest(context) {
  const { request } = context;

  // 处理预检请求
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

    // 1. 从缓存数据中搜索
    let items = searchCachedData(query);
    let source = 'cached';

    // 2. 缓存无结果 → 实时抓取京东
    if (!items.length) {
      const liveItems = await fetchJDSearch(query);
      if (liveItems && liveItems.length) {
        items = liveItems;
        source = 'live';
      }
    }

    // 3. 实时抓取也失败 → 模拟数据
    if (!items.length) {
      items = generateSimulatedData(query);
      source = 'simulated';
    }

    // 4. 综合评分排序
    items = rankItems(items);

    return Response.json(
      {
        success: true,
        query,
        total: items.length,
        items,
        source,
        timestamp: Date.now(),
      },
      { status: 200, headers: corsHeaders() }
    );
  } catch (err) {
    console.error('Search API error:', err);
    return Response.json(
      { success: false, error: '搜索服务暂时不可用', detail: err.message },
      { status: 500, headers: corsHeaders() }
    );
  }
}
