/* ============================================================
 * 省钱比价 · 前端交互逻辑（纯原生 JS，无任何框架）
 * 功能：搜索比价 / Tab 切换 / 前端排序 / AI 流式分析 / 搜索历史
 * ============================================================ */
(function () {
  'use strict';

  /* ---------------- 常量 ---------------- */
  var SEARCH_TIMEOUT = 15000;      // 搜索总超时 15s
  var SLOW_HINT_DELAY = 8000;      // 8s 后提示「正在努力搜索中...」
  var DEBOUNCE_DELAY = 300;        // 输入防抖 300ms
  var HISTORY_KEY = 'pc_search_history';
  var HISTORY_MAX = 5;
  var TYPE_SPEED = 22;             // 打字机每 tick 毫秒
  var AI_MAX_ITEMS = 10;           // 发给 AI 的最大商品数

  // 平台样式映射
  var PLATFORM_CLASS = {
    jd: 'platform-badge--jd',
    taobao: 'platform-badge--taobao',
    pdd: 'platform-badge--pdd',
    meituan: 'platform-badge--meituan',
    douyin: 'platform-badge--douyin'
  };

  /* ---------------- DOM 引用 ---------------- */
  function $(id) { return document.getElementById(id); }

  var searchForm   = $('search-form');
  var searchInput  = $('search-input');
  var resultsEl    = $('results');
  var loadingEl    = $('loading');
  var loadingText  = $('loading-text');
  var errorEl      = $('error-state');
  var errorText    = $('error-text');
  var retryBtn     = $('error-retry');
  var emptyEl      = $('empty-state');
  var toolbarEl    = $('toolbar');
  var resultCount  = $('result-count');
  var aiPanel      = $('ai-panel');
  var aiToggle     = $('ai-toggle');
  var aiBody       = $('ai-body');
  var aiContent    = $('ai-content');
  var aiAnalyzeBtn = $('ai-analyze-btn');
  var aiCloseBtn   = $('ai-close');
  var historyWrap  = $('search-history');
  var historyChips = $('history-chips');
  var historyClear = $('history-clear');
  var tabButtons   = document.querySelectorAll('.tab');
  var sortButtons  = document.querySelectorAll('.sort-btn');

  /* ---------------- 全局状态 ---------------- */
  var state = {
    mode: 'shopping',      // shopping | tuan
    sort: 'recommend',     // recommend | price | sales
    query: '',
    items: [],
    searchCtrl: null,      // 当前搜索请求的 AbortController（去重用）
    aiCtrl: null           // 当前 AI 请求的 AbortController
  };
  var debounceTimer = null;
  var timedOut = false;    // 标记本次搜索是否因超时被中止

  /* ---------------- 工具函数 ---------------- */
  function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // 销量格式化：12000 -> 已售1.2万
  function formatSales(n) {
    n = Number(n) || 0;
    if (n <= 0) return '';
    if (n >= 10000) return '已售' + (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    if (n >= 1000) return '已售' + (n / 1000).toFixed(1).replace(/\.0$/, '') + '千';
    return '已售' + n;
  }

  // 价格格式化，保留必要小数
  function formatPrice(p) {
    p = Number(p);
    if (!isFinite(p)) return '--';
    return p % 1 === 0 ? String(p) : p.toFixed(2);
  }

  /* ---------------- 区块显隐 ---------------- */
  function hideAllStates() {
    loadingEl.hidden = true;
    errorEl.hidden = true;
    emptyEl.hidden = true;
    toolbarEl.hidden = true;
    resultsEl.innerHTML = '';
  }

  function showLoading() {
    hideAllStates();
    aiPanel.hidden = true;
    loadingText.textContent = '正在搜索各大平台...';
    loadingEl.hidden = false;
  }

  function showError(msg) {
    hideAllStates();
    aiPanel.hidden = true;
    errorText.textContent = msg;
    errorEl.hidden = false;
  }

  function showEmpty(query) {
    hideAllStates();
    aiPanel.hidden = true;
    emptyEl.querySelector('.empty-state__title').textContent =
      '没有找到「' + query + '」的相关商品';
    emptyEl.hidden = false;
  }

  /* ---------------- 搜索主流程 ---------------- */
  function doSearch(rawQuery) {
    var query = (rawQuery || '').trim();
    if (!query) {
      searchInput.focus();
      return;
    }
    state.query = query;
    searchInput.value = query;
    clearTimeout(debounceTimer);

    // 请求去重：中止上一次未完成的搜索
    if (state.searchCtrl) {
      state.searchCtrl.abort();
    }
    abortAI(); // 新搜索时同时中止 AI 分析

    var ctrl = new AbortController();
    state.searchCtrl = ctrl;
    timedOut = false;

    showLoading();

    // 8s 慢提示
    var slowTimer = setTimeout(function () {
      if (!ctrl.signal.aborted) loadingText.textContent = '正在努力搜索中...';
    }, SLOW_HINT_DELAY);

    // 15s 强制超时
    var hardTimer = setTimeout(function () {
      timedOut = true;
      ctrl.abort();
    }, SEARCH_TIMEOUT);

    var endpoint = state.mode === 'tuan' ? '/api/tuan' : '/api/search';
    var url = endpoint + '?q=' + encodeURIComponent(query);

    fetch(url, { signal: ctrl.signal })
      .then(function (resp) {
        if (!resp.ok) throw new Error('HTTP_' + resp.status);
        return resp.json();
      })
      .then(function (data) {
        clearTimeout(slowTimer);
        clearTimeout(hardTimer);
        if (ctrl.signal.aborted) return; // 已被更新的搜索取代

        if (!data || data.success === false) {
          showError((data && data.message) || '搜索服务开小差了，请稍后再试');
          return;
        }

        addHistory(query);
        state.items = Array.isArray(data.items) ? data.items : [];

        if (state.items.length === 0) {
          showEmpty(query);
          return;
        }
        renderResults();
      })
      .catch(function (err) {
        clearTimeout(slowTimer);
        clearTimeout(hardTimer);
        // 被新请求中止 → 静默忽略
        if (err && err.name === 'AbortError' && !timedOut) return;
        if (timedOut) {
          showError('搜索超时了（15秒），请稍后重试');
        } else if (/^HTTP_\d+$/.test(String(err && err.message))) {
          showError('服务异常（' + err.message.slice(5) + '），请稍后再试');
        } else {
          showError('网络连接失败，请检查网络后重试');
        }
      });
  }

  /* ---------------- 结果渲染 ---------------- */
  function sortItems(items) {
    var list = items.slice();
    switch (state.sort) {
      case 'price':
        list.sort(function (a, b) { return (Number(a.price) || 0) - (Number(b.price) || 0); });
        break;
      case 'sales':
        list.sort(function (a, b) { return (Number(b.sales) || 0) - (Number(a.sales) || 0); });
        break;
      default: // recommend：评分优先，销量次之
        list.sort(function (a, b) {
          var d = (Number(b.rating) || 0) - (Number(a.rating) || 0);
          return d !== 0 ? d : (Number(b.sales) || 0) - (Number(a.sales) || 0);
        });
    }
    return list;
  }

  function buildCard(item, isBest) {
    var pCls = PLATFORM_CLASS[item.platform] || 'platform-badge--default';
    var pName = esc(item.platform_name || item.platform || '其他');
    var sales = formatSales(item.sales);
    var sourceBadge = item.source === 'real'
      ? '<span class="source-badge source-badge--real">实时数据</span>'
      : '<span class="source-badge source-badge--mock">模拟数据</span>';
    var coupon = item.coupon
      ? '<span class="coupon-tag">券 ' + esc(item.coupon) + '</span>'
      : '';
    var original = (Number(item.original_price) > Number(item.price))
      ? '<span class="price-original">¥' + esc(formatPrice(item.original_price)) + '</span>'
      : '';
    var rating = (Number(item.rating) > 0)
      ? '<span class="rating">★ ' + esc(formatPrice(item.rating)) + '</span>'
      : '';
    var url = item.url ? esc(item.url) : 'javascript:void(0)';
    var imgHtml = item.image
      ? '<img class="p-img" src="' + esc(item.image) + '" alt="' + esc(item.title || '商品图') + '" loading="lazy">'
      : '<div class="img-placeholder">📦</div>';

    return '' +
      '<a class="product-card' + (isBest ? ' product-card--best' : '') + '" href="' + url +
        '" target="_blank" rel="noopener noreferrer">' +
        '<div class="product-card__img">' + imgHtml + '</div>' +
        '<div class="product-card__body">' +
          '<h3 class="product-card__title">' + esc(item.title || '商品') + '</h3>' +
          '<div class="product-card__tags">' +
            '<span class="platform-badge ' + pCls + '">' + pName + '</span>' +
            coupon +
          '</div>' +
          '<div class="product-card__price-row">' +
            '<span class="price"><span class="price-symbol">¥</span>' + esc(formatPrice(item.price)) + '</span>' +
            original +
          '</div>' +
          '<div class="product-card__meta">' +
            (sales ? '<span class="sales">' + sales + '</span>' : '') +
            rating +
            (item.shop_name ? '<span class="shop-name">' + esc(item.shop_name) + '</span>' : '') +
            sourceBadge +
          '</div>' +
        '</div>' +
      '</a>';
  }

  function renderResults() {
    hideAllStates();

    var list = sortItems(state.items);

    // 找出全网最低价，打上「👑 全网最低」标记
    var minPrice = Infinity;
    list.forEach(function (it) {
      var p = Number(it.price);
      if (isFinite(p) && p < minPrice) minPrice = p;
    });

    var html = list.map(function (it) {
      var isBest = list.length >= 2 && Number(it.price) === minPrice;
      return buildCard(it, isBest);
    }).join('');

    resultsEl.innerHTML = html;

    // 图片加载失败 → 占位图（灰色背景 + 📦）
    resultsEl.querySelectorAll('img.p-img').forEach(function (img) {
      img.addEventListener('error', function () {
        var ph = document.createElement('div');
        ph.className = 'img-placeholder';
        ph.textContent = '📦';
        img.replaceWith(ph);
      }, { once: true });
    });

    // 工具栏与统计
    resultCount.innerHTML = '「' + esc(state.query) + '」共 <strong>' +
      esc(list.length) + '</strong> 件商品';
    toolbarEl.hidden = false;

    // 展示 AI 面板（重置为初始引导态）
    resetAIPanel();
    aiPanel.hidden = false;
  }

  /* ---------------- 排序切换 ---------------- */
  sortButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (state.sort === btn.dataset.sort) return;
      state.sort = btn.dataset.sort;
      sortButtons.forEach(function (b) {
        b.classList.toggle('is-active', b === btn);
      });
      if (state.items.length) renderResults();
    });
  });

  /* ---------------- Tab 切换 ---------------- */
  tabButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (state.mode === btn.dataset.mode) return;
      state.mode = btn.dataset.mode;
      tabButtons.forEach(function (b) {
        var active = b === btn;
        b.classList.toggle('is-active', active);
        b.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      // 切换模式：清空结果，有查询词则重新搜索
      state.items = [];
      if (state.query) {
        doSearch(state.query);
      } else {
        hideAllStates();
        aiPanel.hidden = true;
      }
    });
  });

  /* ---------------- 搜索框事件 ---------------- */
  searchForm.addEventListener('submit', function (e) {
    e.preventDefault();
    doSearch(searchInput.value);
  });

  // 防抖：停止输入 300ms 后自动搜索
  searchInput.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    var value = searchInput.value.trim();
    if (value.length >= 2) {
      debounceTimer = setTimeout(function () {
        doSearch(value);
      }, DEBOUNCE_DELAY);
    }
  });

  retryBtn.addEventListener('click', function () {
    if (state.query) doSearch(state.query);
  });

  /* ---------------- 搜索历史 ---------------- */
  function loadHistory() {
    try {
      var raw = localStorage.getItem(HISTORY_KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) {
      return [];
    }
  }

  function saveHistory(arr) {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(arr));
    } catch (e) { /* 隐私模式等场景静默失败 */ }
  }

  function addHistory(query) {
    var arr = loadHistory().filter(function (q) { return q !== query; });
    arr.unshift(query);
    saveHistory(arr.slice(0, HISTORY_MAX));
    renderHistory();
  }

  function renderHistory() {
    var arr = loadHistory();
    historyChips.innerHTML = '';
    historyWrap.hidden = arr.length === 0;
    arr.forEach(function (q) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'history-chip';
      chip.textContent = q;
      chip.addEventListener('click', function () {
        doSearch(q);
      });
      historyChips.appendChild(chip);
    });
  }

  historyClear.addEventListener('click', function () {
    saveHistory([]);
    renderHistory();
  });

  /* ---------------- AI 智能分析 ---------------- */
  var typewriter = {
    full: '',        // 已收到的完整文本
    shown: 0,        // 已显示的字符数
    timer: null,
    textNode: null,
    cursor: null,

    reset: function () {
      this.stop();
      this.full = '';
      this.shown = 0;
      aiContent.innerHTML = '';
      this.textNode = document.createTextNode('');
      this.cursor = document.createElement('span');
      this.cursor.className = 'ai-cursor';
      aiContent.appendChild(this.textNode);
      aiContent.appendChild(this.cursor);
    },

    append: function (chunk) {
      this.full += chunk;
      if (!this.timer) this.tick();
    },

    tick: function () {
      var self = this;
      this.timer = setInterval(function () {
        // 逐步追上已收到的文本，积压多时加速
        var step = self.full.length - self.shown > 60 ? 4 : 2;
        self.shown = Math.min(self.full.length, self.shown + step);
        self.textNode.data = self.full.slice(0, self.shown);
        if (self.shown >= self.full.length) {
          clearInterval(self.timer);
          self.timer = null;
        }
      }, TYPE_SPEED);
    },

    stop: function () {
      if (this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
    },

    finish: function () {
      var self = this;
      var waitDone = setInterval(function () {
        if (!self.timer) { // 打字机追平后移除光标
          self.shown = self.full.length;
          if (self.textNode) self.textNode.data = self.full;
          if (self.cursor && self.cursor.parentNode) self.cursor.remove();
          clearInterval(waitDone);
        }
      }, TYPE_SPEED * 2);
    }
  };

  function resetAIPanel() {
    abortAI();
    typewriter.stop();
    aiContent.innerHTML =
      '<p class="ai-placeholder">点击上方按钮，AI 将综合价格、优惠券、销量和店铺信誉，<br>告诉你哪一件最值得入手 🤔</p>';
    aiCloseBtn.hidden = true;
    aiAnalyzeBtn.disabled = false;
    aiAnalyzeBtn.innerHTML = '<span class="ai-analyze-btn__spark" aria-hidden="true">⚡</span>让 AI 帮我选最划算的';
    aiPanel.classList.remove('is-collapsed');
    aiToggle.setAttribute('aria-expanded', 'true');
  }

  function abortAI() {
    if (state.aiCtrl) {
      state.aiCtrl.abort();
      state.aiCtrl = null;
    }
    typewriter.stop();
  }

  // 解析一条 SSE data 载荷，返回文本片段
  function extractChunk(payload) {
    if (!payload || payload === '[DONE]') return '';
    try {
      var obj = JSON.parse(payload);
      if (typeof obj === 'string') return obj;
      if (obj.choices && obj.choices[0]) {          // OpenAI 风格
        var delta = obj.choices[0].delta || obj.choices[0];
        return delta.content || delta.text || '';
      }
      return obj.text || obj.content || obj.delta || obj.data || obj.message || '';
    } catch (e) {
      return payload; // 纯文本载荷
    }
  }

  function startAIAnalyze() {
    if (!state.items.length || !state.query) return;

    abortAI();
    var ctrl = new AbortController();
    state.aiCtrl = ctrl;

    // 展开面板并进入打字机状态
    aiPanel.hidden = false;
    aiPanel.classList.remove('is-collapsed');
    aiToggle.setAttribute('aria-expanded', 'true');
    typewriter.reset();

    aiAnalyzeBtn.disabled = true;
    aiAnalyzeBtn.textContent = 'AI 分析中...';

    var payload = {
      query: state.query,
      items: state.items.slice(0, AI_MAX_ITEMS).map(function (it) {
        return {
          id: it.id,
          title: it.title,
          price: it.price,
          original_price: it.original_price,
          platform: it.platform_name || it.platform,
          coupon: it.coupon || '',
          sales: it.sales,
          rating: it.rating,
          shop_name: it.shop_name,
          source: it.source
        };
      })
    };

    fetch('/api/ai-analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify(payload),
      signal: ctrl.signal
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error('HTTP_' + resp.status);
        var ctype = (resp.headers.get('content-type') || '').toLowerCase();

        // SSE 流式响应
        if (ctype.indexOf('text/event-stream') !== -1 && resp.body) {
          return readSSEStream(resp.body, ctrl);
        }
        // 兜底：一次性 JSON / 纯文本响应
        return resp.text().then(function (text) {
          var out = text;
          try {
            var j = JSON.parse(text);
            out = j.text || j.content || j.analysis || j.data || text;
            if (typeof out !== 'string') out = JSON.stringify(out, null, 2);
          } catch (e) { /* 按纯文本处理 */ }
          typewriter.append(String(out));
        });
      })
      .then(function () {
        if (ctrl.signal.aborted) return;
        typewriter.finish();
        aiCloseBtn.hidden = false;
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        typewriter.append('\n⚠️ AI 分析暂时不可用，请稍后再试');
        typewriter.finish();
      })
      .finally(function () {
        if (state.aiCtrl === ctrl) state.aiCtrl = null;
        aiAnalyzeBtn.disabled = false;
        aiAnalyzeBtn.innerHTML =
          '<span class="ai-analyze-btn__spark" aria-hidden="true">⚡</span>让 AI 帮我选最划算的';
      });
  }

  // 逐块读取 SSE 流
  function readSSEStream(body, ctrl) {
    var reader = body.getReader();
    var decoder = new TextDecoder('utf-8');
    var buffer = '';

    function pump() {
      return reader.read().then(function (result) {
        if (result.done) return;
        if (ctrl.signal.aborted) return;

        buffer += decoder.decode(result.value, { stream: true });
        var idx;
        while ((idx = buffer.indexOf('\n')) !== -1) {
          var line = buffer.slice(0, idx).replace(/\r$/, '').trim();
          buffer = buffer.slice(idx + 1);

          if (!line || line.charAt(0) === ':') continue; // 空行 / SSE 心跳注释
          if (line.indexOf('data:') === 0) {
            var payload = line.slice(5).trim();
            if (payload === '[DONE]') return;
            var chunk = extractChunk(payload);
            if (chunk) typewriter.append(String(chunk));
          }
        }
        return pump();
      });
    }

    return pump();
  }

  aiAnalyzeBtn.addEventListener('click', startAIAnalyze);

  // 折叠 / 展开
  aiToggle.addEventListener('click', function () {
    var collapsed = aiPanel.classList.toggle('is-collapsed');
    aiToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  });

  aiCloseBtn.addEventListener('click', function () {
    aiPanel.classList.add('is-collapsed');
    aiToggle.setAttribute('aria-expanded', 'false');
  });

  /* ---------------- 初始化 ---------------- */
  renderHistory();
  searchInput.focus();
})();
