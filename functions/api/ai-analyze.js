const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function corsHeaders(extra = {}) {
  return { ...CORS_HEADERS, ...extra };
}

/**
 * 构造分析 prompt
 */
function buildPrompt(query, items) {
  const platformNames = {
    jd: '京东',
    taobao: '淘宝',
    pdd: '拼多多',
    meituan: '美团',
    douyin: '抖音',
  };

  const itemDesc = items
    .map((item, i) => {
      const platform = platformNames[item.platform] || item.platform;
      const original = (item.original_price || item.originalPrice) ? `（原价 ¥${item.original_price || item.originalPrice}）` : '';
      const rating = item.rating ? `评分 ${item.rating}` : '';
      const sales = item.sales ? `销量 ${item.sales}` : '';
      const shop = (item.shop_name || item.shop) ? `店铺: ${item.shop_name || item.shop}` : '';
      return `${i + 1}. [${platform}] ${item.title} - ¥${item.price}${original} ${rating} ${sales} ${shop}`;
    })
    .join('\n');

  return `你是一位专业的消费顾问。请根据以下「${query}」的搜索结果，为用户提供购物分析和建议。

搜索结果：
${itemDesc}

请从以下角度分析：
1. **价格对比**：各平台价格差异，哪个最便宜
2. **性价比分析**：综合考虑价格、评分、销量
3. **最佳推荐**：推荐1-2个最值得购买的选择，说明理由
4. **购买建议**：需要注意的事项（如保质期、规格差异等）

请用简洁明了的语言，适当使用emoji让内容更生动。`;
}

export async function onRequest(context) {
  const { request, env } = context;

  // 预检请求
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders() });
  }

  if (request.method !== 'POST') {
    return Response.json(
      { success: false, error: '仅支持POST请求' },
      { status: 405, headers: corsHeaders() }
    );
  }

  try {
    const body = await request.json();
    const { query, items } = body;

    if (!query || !items || !items.length) {
      return Response.json(
        { success: false, error: '请提供 query 和 items 参数' },
        { status: 400, headers: corsHeaders() }
      );
    }

    // 检查 API Key
    const apiKey = env.SENSENOVA_API_KEY;
    if (!apiKey) {
      // 无 API Key 时返回固定提示
      return new Response(
        `data: ${JSON.stringify({
          type: 'content',
          text: `📊 「${query}」快速分析\n\n`,
        })}\n\n` +
          `data: ${JSON.stringify({
            type: 'content',
            text: `💡 最低价格：¥${Math.min(...items.map(i => i.price)).toFixed(2)}\n`,
          })}\n\n` +
          `data: ${JSON.stringify({
            type: 'content',
            text: `🏆 综合评分最高的商品已排在前面\n\n`,
          })}\n\n` +
          `data: ${JSON.stringify({
            type: 'content',
            text: `⚠️ 未配置AI分析服务（SENSENOVA_API_KEY），当前为基础分析模式。配置后可获得更详细的智能对比分析。`,
          })}\n\n` +
          `data: ${JSON.stringify({ type: 'done' })}\n\n`,
        {
          status: 200,
          headers: corsHeaders({
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive',
          }),
        }
      );
    }

    // 构造 prompt
    const prompt = buildPrompt(query, items);

    // 调用商汤 API（流式）
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);

    const aiResp = await fetch('https://token.sensenova.cn/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'deepseek-v4-flash',
        stream: true,
        messages: [
          {
            role: 'system',
            content:
              '你是一位专业的消费顾问和比价专家，擅长分析各平台商品价格、性价比，给出实用的购物建议。',
          },
          { role: 'user', content: prompt },
        ],
        temperature: 0.7,
        max_tokens: 1500,
      }),
      signal: controller.signal,
    });

    if (!aiResp.ok) {
      const errText = await aiResp.text().catch(() => '');
      clearTimeout(timeout);
      return Response.json(
        {
          success: false,
          error: `AI服务调用失败: ${aiResp.status}`,
          detail: errText.slice(0, 200),
        },
        { status: 502, headers: corsHeaders() }
      );
    }

    // SSE 流式转发
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();

    // 后台处理流
    (async () => {
      try {
        const reader = aiResp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data:')) continue;
            const dataStr = trimmed.slice(5).trim();
            if (dataStr === '[DONE]') {
              await writer.write(
                encoder.encode(
                  `data: ${JSON.stringify({ type: 'done' })}\n\n`
                )
              );
              continue;
            }

            try {
              const parsed = JSON.parse(dataStr);
              const delta = parsed?.choices?.[0]?.delta?.content;
              if (delta) {
                await writer.write(
                  encoder.encode(
                    `data: ${JSON.stringify({ type: 'content', text: delta })}\n\n`
                  )
                );
              }
            } catch {
              // 跳过无法解析的行
            }
          }
        }

        // 确保发送 done
        await writer.write(
          encoder.encode(`data: ${JSON.stringify({ type: 'done' })}\n\n`)
        );
      } catch (e) {
        await writer.write(
          encoder.encode(
            `data: ${JSON.stringify({ type: 'error', text: e.message })}\n\n`
          )
        );
      } finally {
        clearTimeout(timeout);
        await writer.close();
      }
    })();

    return new Response(readable, {
      status: 200,
      headers: corsHeaders({
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      }),
    });
  } catch (err) {
    console.error('AI Analyze error:', err);
    return Response.json(
      { success: false, error: 'AI分析服务暂时不可用', detail: err.message },
      { status: 500, headers: corsHeaders() }
    );
  }
}
